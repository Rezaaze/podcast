"""Audio-Helfer für die Vertonung: Chunk-Generierung mit Retry und
Plausibilitätsprüfung, Silence-Trimming, LUFS-Mastering, Episoden-Merge
und ID3-Tagging."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time

import numpy as np
import pyloudnorm as pyln
from pydub import AudioSegment, silence, effects

from ..core import textproc

MAX_RETRIES = 3
RETRY_DELAY = 5      # Basis-Backoff bei Transport-/Server-Fehlern, siehe generate_chunk()
RETRY_DELAY_CAP = 30  # oberes Limit für den Backoff, falls MAX_RETRIES mal steigt
FADE_MS = 15
PEAK_CEILING_DBFS = -1.0

# Pro-Chunk-Lautstärkeangleichung: master_episode() kompressiert/normalisiert
# nur die FERTIGE Gesamtepisode — laute Momente werden gedämpft, leise Zeilen
# aber nicht angehoben, und unterschiedliche TTS-Ausgabepegel je Stimme/Style
# bleiben bis dahin unangetastet nebeneinander stehen. CHUNK_NORM_TARGET_DBFS
# zieht jeden einzelnen Chunk sanft in Richtung eines gemeinsamen Zielpegels,
# BEVOR die Chunks zur Episode zusammengefügt werden — CHUNK_NORM_MAX_GAIN_DB
# deckelt den Eingriff, damit stilistisch gewollte Dynamik (Flüstern vs.
# Schreien) erhalten bleibt und nur echte Ausreißer eingefangen werden.
CHUNK_NORM_TARGET_DBFS = -20.0
CHUNK_NORM_MAX_GAIN_DB = 6.0


def trim_silence(segment):
    start_trim = silence.detect_leading_silence(segment, silence_threshold=-40)
    end_trim = silence.detect_leading_silence(segment.reverse(), silence_threshold=-40)
    return segment[start_trim: len(segment) - end_trim] if end_trim > 0 else segment[start_trim:]


def is_suspicious_duration(segment, text, speed=None):
    """CJK-bewusste Erwartung: chinesische Zeichen werden deutlich langsamer
    gesprochen (~5 Zeichen/s) als lateinische Buchstaben (~12.5 Zeichen/s);
    ein speed-Faktor unter 1.0 verlängert die erwartete Dauer zusätzlich."""
    cjk = textproc.count_cjk(text)
    latin = len(text) - cjk
    expected_ms = max(300, (latin / 12.5 + cjk / 5.0) * 1000 / (speed or 1.0))
    actual_ms = len(segment)
    if actual_ms < 200 or actual_ms < expected_ms * 0.3:
        return True, f"zu kurz ({actual_ms}ms, erwartet ~{int(expected_ms)}ms)"
    if actual_ms > expected_ms * 4:
        return True, f"zu lang ({actual_ms}ms, erwartet ~{int(expected_ms)}ms)"
    return False, None


def measure_lufs(segment):
    samples = np.array(segment.get_array_of_samples()).astype(np.float64)
    if segment.channels == 2:
        samples = samples.reshape((-1, 2))
    samples /= float(2 ** (8 * segment.sample_width - 1))
    meter = pyln.Meter(segment.frame_rate)
    return meter.integrated_loudness(samples)


def master_episode(segment, target_lufs):
    compressed = effects.compress_dynamic_range(segment, threshold=-20.0, ratio=2.5, attack=5.0, release=50.0)
    try:
        current_lufs = measure_lufs(compressed)
        if current_lufs != float("-inf"):
            gain = target_lufs - current_lufs
            mastered = compressed.apply_gain(gain)
            if mastered.max_dBFS > PEAK_CEILING_DBFS:
                mastered = mastered.apply_gain(PEAK_CEILING_DBFS - mastered.max_dBFS)
            return mastered
    except Exception as e:
        print(f"  Warnung: LUFS-Normalisierung fehlgeschlagen ({e}), nutze Peak-Normalisierung.")
    return effects.normalize(compressed)


def normalize_chunk_loudness(segment, target_dbfs=CHUNK_NORM_TARGET_DBFS,
                             max_gain_db=CHUNK_NORM_MAX_GAIN_DB):
    """Gleicht die Lautstärke EINES TTS-Chunks sanft an target_dbfs an, mit
    auf max_gain_db gedeckeltem Gain (siehe Konstanten-Kommentar oben) — für
    sehr kurze Chunks nutzt das die simple mittlere pydub-dBFS statt eines
    vollen LUFS-Meters (pyloudnorm braucht für ITU-R-BS.1770-Gating deutlich
    längere Blöcke, als ein einzelner Satz-Chunk oft liefert)."""
    if segment.dBFS == float("-inf"):
        return segment  # reine Stille (z.B. Pausen-Chunk) — nichts anzugleichen
    gain = max(-max_gain_db, min(max_gain_db, target_dbfs - segment.dBFS))
    return segment.apply_gain(gain)


def postprocess_chunk(segment, text, speed=None):
    """Die Per-Chunk-Nachbearbeitung, die JEDES frisch generierte Segment
    durchlaufen muss, bevor es committed/gecheckpointet wird: Silence-Trim,
    Plausibilitätsprüfung, Loudness-Angleichung. Als eigener Helper, damit
    der Batch-Pfad (podcast_maker ruft backend.generate_chunk_batch direkt)
    exakt dieselbe Kette anwendet wie der Einzel-Pfad (generate_chunk unten)
    — sonst klingen Cloud-gebatchte Episoden anders als lokal vertonte
    (Pegel-Sprünge, ungetrimmte Ränder) und schlechte Samples landen
    ungeprüft im Checkpoint.

    Gibt (segment, None) zurück oder (None, grund), wenn das Segment
    verdächtig ist (Aufrufer regeneriert dann, statt es zu verwenden)."""
    segment = trim_silence(segment)
    suspicious, reason = is_suspicious_duration(segment, text, speed=speed)
    if suspicious:
        return None, reason
    return normalize_chunk_loudness(segment), None


def generate_chunk(backend, voice, text, style=None, speed=None):
    """Generiert Audio über das gewählte TTS-Backend mit Retry +
    Plausibilitätsprüfung.

    voice: Tupel (kind, voice_id, seed) aus backend.resolve_voice() —
    seed wird vom Backend selbst ausgewertet (nur RestBackend + geklonte
    Stimme nutzen ihn tatsächlich, siehe tts_backends.py).

    Zwei Fehlerarten bekommen unterschiedliches Retry-Verhalten statt eines
    pauschalen Delays: ein Inhalts-Problem (Segment kam an, aber
    is_suspicious_duration schlägt an) heißt der Server funktioniert, das
    Ergebnis war nur ein schlechter stochastischer Sample — sofortiger
    erneuter Versuch ohne Wartezeit ist hier genauso gut. Ein Transport-/
    Server-Fehler (segment ist None — Timeout, Verbindungsfehler, HTTP-Fehler)
    bekommt stattdessen exponentiellen Backoff (RETRY_DELAY * 2^(Versuch-1),
    gedeckelt bei RETRY_DELAY_CAP): dem Server Zeit geben, sich zu erholen,
    statt ihn im selben Takt erneut zu treffen, während er überlastet ist
    oder gerade neu startet."""
    for attempt in range(1, MAX_RETRIES + 1):
        segment, error = backend.generate_chunk(voice, text, style=style, speed=speed)
        if segment is not None:
            processed, reason = postprocess_chunk(segment, text, speed=speed)
            if processed is not None:
                return processed
            print(f"\n    Versuch {attempt}: Verdächtige Ausgabe – {reason}")
            # Server hat geantwortet, nur der Sample war schlecht — sofort erneut
            # versuchen statt zu warten (siehe Docstring oben).
        else:
            print(f"\n    Versuch {attempt}: {error}")
            if attempt < MAX_RETRIES:
                delay = min(RETRY_DELAY_CAP, RETRY_DELAY * (2 ** (attempt - 1)))
                print(f"    Warte {delay}s (Backoff nach Transport-/Server-Fehler)...")
                time.sleep(delay)

    return None


JINGLE_GAP_MS = 800  # Atempause zwischen Jingle/Sting und Sprache


def part_offsets_path(episode_path):
    return os.path.splitext(episode_path)[0] + "_PART_OFFSETS.json"


def load_part_offsets(episode_path):
    """Liest die von merge_parts_to_episode() gespeicherten Part-Offsets
    zurück — erlaubt, die (billige, idempotente) Metadaten-Nachbearbeitung
    (Untertitel/SFX-Cues/Sprecher-/Location-Timeline) erneut anzustoßen, ohne
    die dafür nötigen Zeitgrenzen aus den Part-WAVs neu zu berechnen, die nach
    einem erfolgreichen Merge bereits gelöscht sind. None, wenn die Datei
    fehlt (Episode aus einem Lauf vor diesem Feature) — dann bleibt nur noch
    reines ID3-Tagging möglich, kein Nachholen der Timelines."""
    path = part_offsets_path(episode_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def merge_parts_to_episode(part_paths, episode_path, pause_between_parts_ms, target_lufs,
                           intro_path=None, outro_path=None, transition_path=None):
    """Fügt Part-WAVs zur fertigen Episoden-MP3 zusammen (mit Mastering).
    Rückgabe: Liste der ms-Offsets, an denen jeder Part in der fertigen
    Episode beginnt — für SFX-Cue-Sheet und Sprecher-Timeline im Drama-Modus
    (die Offsets enthalten damit automatisch auch einen etwaigen Intro-Jingle).

    intro/outro: einmal am Episodenanfang/-ende. transition: ersetzt die
    reine Stille zwischen Parts durch Pause + Szenenwechsel-Sting + Pause."""
    print(f"\nFüge {len(part_paths)} Parts zur Gesamtepisode zusammen...")
    pause = AudioSegment.silent(duration=pause_between_parts_ms)
    transition = None
    if transition_path:
        sting = AudioSegment.from_file(transition_path).fade_in(FADE_MS).fade_out(FADE_MS)
        half = AudioSegment.silent(duration=max(200, pause_between_parts_ms // 2))
        transition = half + sting + half
        print(f"  Szenenwechsel-Sting: {os.path.basename(transition_path)} ({len(sting)/1000:.1f}s)")

    combined = AudioSegment.empty()
    if intro_path:
        intro = AudioSegment.from_file(intro_path).fade_out(FADE_MS)
        combined = intro + AudioSegment.silent(duration=JINGLE_GAP_MS)
        print(f"  Intro-Jingle: {os.path.basename(intro_path)} ({len(intro)/1000:.1f}s)")

    part_offsets = []
    for i, path in enumerate(part_paths):
        part_audio = AudioSegment.from_file(path, format="wav")
        part_audio = part_audio.fade_in(FADE_MS).fade_out(FADE_MS)
        if i > 0:
            combined = combined + (transition if transition is not None else pause)
        part_offsets.append(len(combined))
        combined = combined + part_audio

    if outro_path:
        outro = AudioSegment.from_file(outro_path).fade_in(FADE_MS)
        combined = combined + AudioSegment.silent(duration=JINGLE_GAP_MS) + outro
        print(f"  Outro-Jingle: {os.path.basename(outro_path)} ({len(outro)/1000:.1f}s)")

    mastered = master_episode(combined, target_lufs)
    # temp + os.replace: main()s Resume-Check ist nur `os.path.exists` — eine
    # beim Kill truncierte MP3 gälte sonst für immer als fertig.
    tmp_episode_path = episode_path + ".tmp"
    mastered.export(tmp_episode_path, format="mp3", bitrate="192k")
    os.replace(tmp_episode_path, episode_path)
    size_mb = os.path.getsize(episode_path) / (1024 * 1024)
    duration_min = len(mastered) / 1000 / 60
    print(f"Gesamtepisode gespeichert: {os.path.basename(episode_path)} ({size_mb:.1f} MB, {duration_min:.1f} Min.)")

    # Offsets VOR dem Löschen der Part-WAVs persistieren — ein Kill dazwischen
    # ließe sonst weder WAVs noch Offsets zurück und die Post-Merge-Schritte
    # könnten nie nachgeholt werden (siehe Post-Merge-Invariante in CLAUDE.md).
    offsets_path = part_offsets_path(episode_path)
    tmp_offsets_path = offsets_path + ".tmp"
    with open(tmp_offsets_path, "w", encoding="utf-8") as f:
        json.dump(part_offsets, f)
    os.replace(tmp_offsets_path, offsets_path)

    for path in part_paths:
        os.remove(path)
    print(f"{len(part_paths)} Einzeldateien gelöscht.")

    return part_offsets


def parse_meta_file(meta_path):
    """Liest TITEL/BESCHREIBUNG/FRAGE aus einer *_META.txt (Format wie von
    script_writer.generate_episode_meta() geschrieben). FRAGE ist optional
    (ältere META-Dateien ohne Zuschauer-Frage) -- dann None."""
    if not os.path.exists(meta_path):
        return None, None, None
    with open(meta_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"TITEL:\s*(.+?)\s*BESCHREIBUNG:\s*(.+?)(?:\n\s*FRAGE:\s*(.+))?\s*$",
                      content, re.DOTALL)
    if not match:
        return None, None, None
    question = match.group(3).strip() if match.group(3) else None
    return match.group(1).strip(), match.group(2).strip(), question


def extract_episode_number(input_file, prefix):
    """figur3.txt, prefix='figur' -> 3. None bei Nicht-Übereinstimmung (z.B.
    Anthologie-Dateien oder ein untypisches Skript-Namensschema)."""
    stem = os.path.splitext(os.path.basename(input_file))[0]
    match = re.fullmatch(rf"{re.escape(prefix)}(\d+)", stem)
    return int(match.group(1)) if match else None


def format_season_title(series_title, season, episode_num, raw_title):
    """Staffel-Präfix für Serien, die bewusst Teil eines Mehr-Staffel-Podcast-
    Kanals sind (episodes.json 'season' gesetzt, siehe config.py) — z.B.
    'Vanishing Signal – S1E3: Elena — A Photograph That Might Be a Ghost'.
    Ohne 'season' (die meisten Serien, z.B. narration/language_course) bleibt
    der Titel unverändert — season ist ein bewusstes Opt-in pro Serie, kein
    automatisches Verhalten."""
    if season is None or episode_num is None or not raw_title:
        return raw_title
    return f"{series_title} – S{season}E{episode_num}: {raw_title}"


def tag_mp3(path, title=None, album=None, comment=None):
    """Schreibt ID3-Tags per ffmpeg-Stream-Copy (kein Re-Encode) in eine
    fertige MP3. Ohne das bleibt die Datei zwar inhaltlich fertig, trägt aber
    nirgends ihren Titel/ihre Beschreibung — die stehen sonst nur in den
    *_META.txt/UPLOAD_INDEX.md danebenliegenden Textdateien."""
    metadata_args = []
    if title:
        metadata_args += ["-metadata", f"title={title}"]
    if album:
        metadata_args += ["-metadata", f"album={album}"]
    if comment:
        metadata_args += ["-metadata", f"comment={comment}"]
    if not metadata_args:
        return False

    tmp_path = path + ".tagging.tmp.mp3"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-c", "copy"] + metadata_args + [tmp_path],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and os.path.exists(tmp_path):
        os.replace(tmp_path, path)
        return True
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    print(f"  Warnung: ID3-Tagging fehlgeschlagen für {os.path.basename(path)}: "
          f"{result.stderr.strip()[-300:]}")
    return False


def format_timestamp(ms):
    """ms → 'MM:SS.mmm' für das SFX-Cue-Sheet."""
    total_seconds, millis = divmod(int(ms), 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
