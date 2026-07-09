import os
import re
import json
import time
import shutil
import numpy as np
import pyloudnorm as pyln
from pydub import AudioSegment, silence, effects

from tts_backends import build_backend

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = "skript.txt"
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "podcast_output")
CHECKPOINT_DIR = os.path.join(SCRIPT_DIR, "podcast_output", ".checkpoints")
EPISODES_FILE = os.path.join(SCRIPT_DIR, "episodes.json")
VOICE_NAME = "MyVoice"         # Name deiner gespeicherten/geklonten Stimme in der WebUI
AUDIO_CONFIG = {}              # roher "audio"-Block aus episodes.json, für build_backend()
MAX_RETRIES = 3
RETRY_DELAY = 5
SILENCE_BETWEEN_CHUNKS_MS = 250
FADE_MS = 15
CHUNK_MAX_CHARS = 350
TARGET_LUFS = -16.0
PEAK_CEILING_DBFS = -1.0
SILENCE_BETWEEN_PARTS_MS = 4000

# Fallback-Werte — werden von load_podcast_config() aus episodes.json überschrieben
DEFAULT_STYLE = "Read like an audiobook narrator, calm, steady, and engaging"
OUTPUT_PREFIX = "figur"
PARTS_PER_SECTION = 2


os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)


def load_podcast_config():
    """Liest Audio-/Format-Konfiguration aus episodes.json — die JSON ist die
    Single Source of Truth für alles, was den Podcast betrifft."""
    global VOICE_NAME, AUDIO_CONFIG, DEFAULT_STYLE, TARGET_LUFS, OUTPUT_PREFIX, PARTS_PER_SECTION
    global SILENCE_BETWEEN_CHUNKS_MS, SILENCE_BETWEEN_PARTS_MS
    try:
        with open(EPISODES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("  Warnung: episodes.json nicht gefunden — nutze eingebaute Defaults.")
        return
    except json.JSONDecodeError as e:
        # Bewusst harter Abbruch: stilles Weiterlaufen mit Default-Stimme/-Pausen
        # würde stundenlang falsches Audio produzieren.
        raise SystemExit(
            f"FEHLER: episodes.json ist kein gültiges JSON "
            f"(Zeile {e.lineno}, Spalte {e.colno}: {e.msg}). Abbruch."
        )

    audio = data.get("audio", {})
    fmt = data.get("format", {})
    AUDIO_CONFIG = audio
    VOICE_NAME = audio.get("voice", VOICE_NAME)
    DEFAULT_STYLE = audio.get("default_style", DEFAULT_STYLE)
    TARGET_LUFS = audio.get("target_lufs", TARGET_LUFS)
    SILENCE_BETWEEN_CHUNKS_MS = audio.get("pause_between_chunks_ms", SILENCE_BETWEEN_CHUNKS_MS)
    SILENCE_BETWEEN_PARTS_MS = audio.get("pause_between_parts_ms", SILENCE_BETWEEN_PARTS_MS)
    OUTPUT_PREFIX = data.get("output_prefix", OUTPUT_PREFIX)
    PARTS_PER_SECTION = fmt.get("parts_per_section", PARTS_PER_SECTION)


def load_section_styles(input_file):
    """Lädt die Section-Styles aus episodes.json anhand der Dateinummer (figur1 → Index 0)."""
    try:
        match = re.search(rf'{re.escape(OUTPUT_PREFIX)}(\d+)', os.path.basename(input_file), re.IGNORECASE)
        if not match:
            return {}
        ep_idx = int(match.group(1)) - 1

        with open(EPISODES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        episodes = data.get("episodes", [])
        if ep_idx < 0 or ep_idx >= len(episodes):
            return {}

        styles = episodes[ep_idx].get("section_styles", [])
        # Mappe Part-Nummer → Style (alle Parts einer Section teilen sich einen Style)
        part_styles = {}
        for sec_idx, style in enumerate(styles):
            for k in range(1, PARTS_PER_SECTION + 1):
                part_styles[sec_idx * PARTS_PER_SECTION + k] = style
        return part_styles

    except Exception as e:
        print(f"  Warnung: Styles konnten nicht geladen werden ({e}). Nutze Standard-Style.")
        return {}


def episode_name_from_file(file_path):
    """Leitet den Episodennamen aus dem Dateinamen ab (figur1.txt → Figur1).
    Muss identisch zu batch.py sein, damit batch.py fertige Episoden erkennt."""
    stem = os.path.splitext(os.path.basename(file_path))[0]
    return stem.capitalize()


def split_script(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    parts = re.split(r'--- PART \d+ ---', content)
    return [p.strip() for p in parts if p.strip()]


_ABBREV = re.compile(
    r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|approx|dept|est|govt|'
    r'max|min|no|vol|fig|ed|rev|repr|incl|excl|Capt|Col|Gen|Lt|Sgt)\.'
)

def split_into_sentences(text):
    # Temporarily mask abbreviation periods so they don't trigger splits
    masked = _ABBREV.sub(lambda m: m.group().replace('.', '\x00'), text.strip())
    sentences = re.split(r'(?<=[.!?])\s+', masked)
    return [s.replace('\x00', '.').strip() for s in sentences if s.strip()]


def chunk_sentences(sentences, max_chars=CHUNK_MAX_CHARS):
    chunks = []
    current = []
    current_len = 0
    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(sentence)
        current_len += len(sentence) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def format_eta(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def trim_silence(segment):
    start_trim = silence.detect_leading_silence(segment, silence_threshold=-40)
    end_trim = silence.detect_leading_silence(segment.reverse(), silence_threshold=-40)
    return segment[start_trim: len(segment) - end_trim] if end_trim > 0 else segment[start_trim:]


def is_suspicious_duration(segment, text):
    expected_ms = max(300, (len(text) / 12.5) * 1000)
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


def master_episode(segment):
    compressed = effects.compress_dynamic_range(segment, threshold=-20.0, ratio=2.5, attack=5.0, release=50.0)
    try:
        current_lufs = measure_lufs(compressed)
        if current_lufs != float("-inf"):
            gain = TARGET_LUFS - current_lufs
            mastered = compressed.apply_gain(gain)
            if mastered.max_dBFS > PEAK_CEILING_DBFS:
                mastered = mastered.apply_gain(PEAK_CEILING_DBFS - mastered.max_dBFS)
            return mastered
    except Exception as e:
        print(f"  Warnung: LUFS-Normalisierung fehlgeschlagen ({e}), nutze Peak-Normalisierung.")
    return effects.normalize(compressed)


def generate_chunk(backend, voice, text, style=None):
    """Generiert Audio über das gewählte TTS-Backend mit Retry +
    Plausibilitätsprüfung.

    voice: Tupel aus backend.resolve_voice()."""
    for attempt in range(1, MAX_RETRIES + 1):
        segment, error = backend.generate_chunk(voice, text, style=style)
        if segment is not None:
            segment = trim_silence(segment)
            suspicious, reason = is_suspicious_duration(segment, text)
            if not suspicious:
                return segment
            print(f"\n    Versuch {attempt}: Verdächtige Ausgabe – {reason}")
        else:
            print(f"\n    Versuch {attempt}: {error}")

        if attempt < MAX_RETRIES:
            print(f"    Warte {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    return None


def checkpoint_path(part_name, c_idx):
    part_dir = os.path.join(CHECKPOINT_DIR, part_name)
    os.makedirs(part_dir, exist_ok=True)
    return os.path.join(part_dir, f"chunk_{c_idx:03d}.wav")


def clear_checkpoint(part_name):
    part_dir = os.path.join(CHECKPOINT_DIR, part_name)
    if os.path.exists(part_dir):
        shutil.rmtree(part_dir)


def merge_parts_to_episode(person, part_paths, episode_path):
    print(f"\nFüge {len(part_paths)} Parts zur Gesamtepisode zusammen...")
    pause = AudioSegment.silent(duration=SILENCE_BETWEEN_PARTS_MS)
    combined = AudioSegment.empty()
    for i, path in enumerate(part_paths):
        part_audio = AudioSegment.from_file(path, format="wav")
        part_audio = part_audio.fade_in(FADE_MS).fade_out(FADE_MS)
        combined = part_audio if i == 0 else combined + pause + part_audio
    mastered = master_episode(combined)
    mastered.export(episode_path, format="mp3", bitrate="192k")
    size_mb = os.path.getsize(episode_path) / (1024 * 1024)
    duration_min = len(mastered) / 1000 / 60
    print(f"Gesamtepisode gespeichert: {os.path.basename(episode_path)} ({size_mb:.1f} MB, {duration_min:.1f} Min.)")
    for path in part_paths:
        os.remove(path)
    print(f"{len(part_paths)} Einzeldateien gelöscht.")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", nargs="?", default=INPUT_FILE, help="Pfad zur Skript-Datei")
    parser.add_argument("--name", default=None, help="Name der Episode (überschreibt Auto-Erkennung)")
    args = parser.parse_args()

    load_podcast_config()

    current_person = args.name if args.name else episode_name_from_file(args.input_file)

    # Style-Prompts laden (optional — funktioniert auch ohne)
    part_styles = load_section_styles(args.input_file)
    if part_styles:
        print(f"Style-Prompts geladen: {len(set(part_styles.values()))} verschiedene Styles für {len(part_styles)} Parts.")
    else:
        print(f"Kein Style-Mapping gefunden — nutze Standard-Style für alle Parts.")

    backend = build_backend(AUDIO_CONFIG)
    print(f"Prüfe Verbindung zu Qwen3-TTS API ({backend.base_url}) ...")
    if not backend.check_api():
        print(f"FEHLER: API nicht erreichbar. Ist der Qwen3-TTS Server gestartet?")
        print(f"  Tipp: Port prüfen und in episodes.json unter 'audio.api_url' eintragen.")
        return

    kind, voice_id = backend.resolve_voice(VOICE_NAME)
    if kind is None:
        print(f"FEHLER: Stimme '{VOICE_NAME}' nicht gefunden.")
        if voice_id:
            print(f"  Details: {', '.join(voice_id)}")
        print(f"  Stimme in episodes.json unter 'audio.voice' anpassen.")
        return
    voice = (kind, voice_id)

    if kind == "prompt":
        print(f"API erreichbar. Geklonte Stimme: '{VOICE_NAME}' (prompt_id {voice_id[:8]}…)")
        if part_styles:
            print(f"  HINWEIS: Diese API-Version unterstützt keine Style-Anweisungen für geklonte")
            print(f"  Stimmen — die section_styles aus episodes.json werden ignoriert.")
    elif kind == "clone":
        print(f"API erreichbar. Voice-Clone-Backend aktiv (Referenzaudio: {AUDIO_CONFIG.get('ref_audio')})")
        if part_styles:
            print(f"  HINWEIS: Voice Clone unterstützt kein 'instruct' — die section_styles")
            print(f"  aus episodes.json werden ignoriert.")
    else:
        print(f"API erreichbar. Built-in-Stimme: '{VOICE_NAME}' (Styles aktiv via 'instruct')")
    print(f"Episodenname: {current_person}")

    episode_path = os.path.join(OUTPUT_DIR, f"{current_person}_FULL_EPISODE.mp3")
    if os.path.exists(episode_path):
        size_mb = os.path.getsize(episode_path) / (1024 * 1024)
        print(f"Gesamtepisode existiert bereits: {os.path.basename(episode_path)} ({size_mb:.1f} MB). Nichts zu tun.")
        return

    parts = split_script(args.input_file)
    all_chunks = [chunk_sentences(split_into_sentences(p)) for p in parts]
    total_chunks = sum(len(c) for c in all_chunks)
    print(f"{len(parts)} Parts / {total_chunks} Chunks (~{CHUNK_MAX_CHARS} Zeichen je Chunk).\n")

    pause = AudioSegment.silent(duration=SILENCE_BETWEEN_CHUNKS_MS)
    skipped = 0
    success = 0
    failed = []
    chunks_done = 0
    global_start = time.time()
    part_paths = []
    # ETA-Basis getrennt von chunks_done: gen_time/gen_count zählen NUR echte
    # generate_chunk()-Aufrufe. Checkpoint-Reads (~0s) dürfen den Schnitt
    # nicht verwässern, sonst ist die ETA nach einem fortgesetzten Lauf mit
    # vielen Checkpoints erst mal deutlich zu optimistisch.
    gen_time = 0.0
    gen_count = 0

    for idx, (_, chunks) in enumerate(zip(parts, all_chunks), start=1):
        template_name = f"Part_{idx:02d}"
        # Parts als WAV zwischenspeichern: MP3-kodiert wird nur einmal,
        # beim Export der fertigen Gesamtepisode (kein Generationsverlust).
        filename = f"{current_person}_{template_name}.wav"
        part_path = os.path.join(OUTPUT_DIR, filename)
        part_paths.append(part_path)

        if os.path.exists(part_path):
            size = os.path.getsize(part_path) // 1024
            print(f"[{idx}/{len(parts)}] Übersprungen: {filename} ({size} KB)")
            chunks_done += len(chunks)
            skipped += 1
            continue

        style = part_styles.get(idx, DEFAULT_STYLE)
        print(f"[{idx}/{len(parts)}] {filename} – {len(chunks)} Chunks | Style: \"{style}\"")

        segments = []
        part_failed = False

        for c_idx, chunk_text in enumerate(chunks, start=1):
            ckpt = checkpoint_path(template_name, c_idx)

            if os.path.exists(ckpt):
                segment = AudioSegment.from_file(ckpt, format="wav")
                chunks_done += 1
                avg = gen_time / gen_count if gen_count > 0 else None
                eta = format_eta((total_chunks - chunks_done) * avg) if avg is not None else "?"
                msg = f"  Chunk {c_idx}/{len(chunks)} | {chunks_done}/{total_chunks} | ETA: {eta} [checkpoint]"
                print(msg.ljust(90), end="\r")
                segments.append(segment)
                continue

            # ETA für den GERADE STARTENDEN Chunk beruht auf dem Schnitt der
            # bisher abgeschlossenen echten Generierungen — chunks_done wird
            # erst NACH generate_chunk() erhöht, sonst zählt der laufende
            # Chunk im Nenner schon als fertig, bevor seine Zeit überhaupt
            # in die Statistik eingeflossen ist.
            avg = gen_time / gen_count if gen_count > 0 else None
            eta = format_eta((total_chunks - chunks_done) * avg) if avg is not None else "?"
            msg = f"  Chunk {c_idx}/{len(chunks)} | {chunks_done + 1}/{total_chunks} | ETA: {eta}"
            print(msg.ljust(90), end="\r")

            chunk_start = time.time()
            segment = generate_chunk(backend, voice, chunk_text, style=style)

            chunks_done += 1
            if segment:
                gen_time += time.time() - chunk_start
                gen_count += 1
                segment.export(ckpt, format="wav")
                segments.append(segment)
            else:
                print(f"\n  FEHLER bei Chunk {c_idx}: '{chunk_text[:60]}'")
                part_failed = True
                break

        print()

        if not part_failed and segments:
            combined = AudioSegment.empty()
            for i, seg in enumerate(segments):
                seg = seg.fade_in(FADE_MS).fade_out(FADE_MS)
                combined = seg if i == 0 else combined + pause + seg
            combined.export(part_path, format="wav")
            size = os.path.getsize(part_path) // 1024
            print(f"  Gespeichert: {filename} ({size} KB)")
            clear_checkpoint(template_name)
            success += 1
        else:
            failed.append(idx)

    total_time = time.time() - global_start
    print(f"\nAlle Parts fertig in {format_eta(total_time)}!")
    print(f"  Neu generiert: {success} | Übersprungen: {skipped} | Fehlgeschlagen: {len(failed)}")

    if failed:
        print(f"  Fehlgeschlagene Parts: {failed} – Script neu starten zum Fortsetzen.")
        print(f"  Merge zur Gesamtepisode übersprungen (erst wenn alle Parts vorhanden sind).")
        return

    merge_parts_to_episode(current_person, part_paths, episode_path)


if __name__ == "__main__":
    main()
