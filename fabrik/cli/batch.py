#!/usr/bin/env python3
"""Vertont alle Skripte einer Serie und merged sie zur Anthologie.

Verwendung:
  .venv/bin/python batch.py                      # aktuelle Serie (series/LATEST)
  .venv/bin/python batch.py --series tee_haus
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import time

from pydub import AudioSegment
from pydub.utils import mediainfo

from fabrik.audio import pipeline as audio
from fabrik.core import config, paths
from fabrik.writing.script_writer import call_claude, MAX_RETRIES, RETRY_DELAY

ANTHOLOGY_FILENAME = "ANTHOLOGY_COMPLETE.mp3"


def merge_episodes(episode_paths, output_path, output_dir, pause_ms):
    """Konkateniert die Episoden-MP3s per ffmpeg-Stream-Copy: konstanter
    Speicherverbrauch (nichts wird dekodiert) und kein weiterer Re-Encode.
    Voraussetzung: alle Episoden stammen aus podcast_maker.py und haben
    daher identische Audio-Parameter."""
    print(f"\nMerge {len(episode_paths)} Episoden → {os.path.basename(output_path)}")

    # Pausen-MP3 mit denselben Parametern wie die Episoden erzeugen
    info = mediainfo(episode_paths[0])
    silence = AudioSegment.silent(
        duration=pause_ms,
        frame_rate=int(info.get("sample_rate", 44100)),
    ).set_channels(int(info.get("channels", 1)))
    silence_path = os.path.join(output_dir, ".silence_gap.mp3")
    silence.export(silence_path, format="mp3", bitrate="192k")

    def quoted(path):
        return "'" + path.replace("'", "'\\''") + "'"

    list_path = os.path.join(output_dir, ".concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for i, path in enumerate(episode_paths):
            if i > 0:
                f.write(f"file {quoted(silence_path)}\n")
            f.write(f"file {quoted(path)}\n")

    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
         "-c", "copy", output_path],
        capture_output=True, text=True,
    )
    os.remove(list_path)
    os.remove(silence_path)

    if result.returncode != 0 or not os.path.exists(output_path):
        print(f"FEHLER: ffmpeg-Merge fehlgeschlagen:\n{result.stderr.strip()[-500:]}")
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    duration_min = float(mediainfo(output_path).get("duration", 0)) / 60
    print(f"Fertig: {os.path.basename(output_path)} ({size_mb:.1f} MB, {duration_min:.1f} Min.)")


def episode_name_from_file(filepath):
    stem = os.path.splitext(os.path.basename(filepath))[0]
    return stem.capitalize()


def url_reachable(url, timeout=5):
    """Reiner Erreichbarkeits-Check: jede HTTP-Antwort zählt, auch 404 — die
    Backends haben unterschiedliche Health-Endpoints, hier geht es nur um
    "Server an/aus", bevor ein zweiter Render-Worker daran gebunden wird."""
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def episode_offsets_ms(episode_paths, pause_ms):
    """Start-Offset jeder Episode in der gemergten Anthologie (MP3-Längen +
    Merge-Pause) — exakt wie merge_episodes() die Tonspur zusammensetzt."""
    offsets = []
    offset = 0.0
    for path in episode_paths:
        offsets.append(int(offset))
        offset += float(mediainfo(path).get("duration", 0)) * 1000 + pause_ms
    return offsets


def format_youtube_timestamp(ms):
    total_s = int(ms) // 1000
    hours, rem = divmod(total_s, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def write_chapters(episode_pairs, anthology_path, pause_ms):
    """Kapitelliste der Anthologie: Episoden-Offsets + Titel aus den META-
    Dateien. Schreibt ANTHOLOGY_COMPLETE_CHAPTERS.json (liest Lolfi für die
    Titelkarten-Einblendung) und gibt die Kapitel für den Upload-Index zurück."""
    import json as _json

    episode_paths = [ep for _, ep in episode_pairs]
    offsets = episode_offsets_ms(episode_paths, pause_ms)
    chapters = []
    for (script, episode_file), offset in zip(episode_pairs, offsets):
        title, _desc, _question = audio.parse_meta_file(os.path.splitext(script)[0] + "_META.txt")
        chapters.append({"start_ms": offset,
                         "title": title or episode_name_from_file(episode_file)})

    json_path = os.path.splitext(anthology_path)[0] + "_CHAPTERS.json"
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump({"chapters": chapters}, f, ensure_ascii=False, indent=1)
    print(f"Kapitel geschrieben: {os.path.basename(json_path)} ({len(chapters)} Kapitel)")
    return chapters


def merge_subtitles(episode_paths, anthology_path, pause_ms):
    """Setzt die pro Episode geschriebenen *_SUBS.json (podcast_maker.py) mit
    den Episoden-Offsets zur Untertitel-Datei der Anthologie zusammen
    (ANTHOLOGY_COMPLETE.srt — bei YouTube zum Video hochladen) UND zu
    ANTHOLOGY_COMPLETE_SUBS.json (behält das "role"-Feld pro Cue —
    Lolfi liest daraus die Sprechblasen-Einblendungen für die Anthologie,
    genau wie es *_SUBS.json einer Einzelepisode liest)."""
    import json as _json
    from fabrik.cli.podcast_maker import format_srt_timestamp

    cues = []
    missing = []
    for path, offset_ms in zip(episode_paths, episode_offsets_ms(episode_paths, pause_ms)):
        subs_file = os.path.splitext(path)[0] + "_SUBS.json"
        if not os.path.exists(subs_file):
            missing.append(os.path.basename(path))
            continue
        with open(subs_file, "r", encoding="utf-8") as f:
            for cue in _json.load(f).get("cues", []):
                cues.append({"start_ms": int(offset_ms + cue["start_ms"]),
                             "end_ms": int(offset_ms + cue["end_ms"]),
                             "text": cue["text"], "role": cue.get("role", "")})
    if missing:
        print(f"Hinweis: Keine Untertitel-Daten für {', '.join(missing)} — "
              f"Episode(n) neu vertonen, um sie zu erzeugen (Anthologie-SRT unvollständig).")
    if not cues:
        return

    srt_path = os.path.splitext(anthology_path)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for n, cue in enumerate(cues, start=1):
            f.write(f"{n}\n{format_srt_timestamp(cue['start_ms'])} --> "
                    f"{format_srt_timestamp(cue['end_ms'])}\n{cue['text']}\n\n")
    print(f"Anthologie-Untertitel geschrieben: {os.path.basename(srt_path)} ({len(cues)} Cues)")

    json_path = os.path.splitext(anthology_path)[0] + "_SUBS.json"
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump({"cues": cues}, f, ensure_ascii=False, indent=1)


def merge_speaker_timelines(episode_paths, anthology_path, pause_ms):
    """Kombiniert die pro Episode geschriebenen *_SPEAKERS.json (podcast_maker.py,
    nur Drama-Modus) zur Timeline der GESAMTEN Anthologie — Grundlage für
    automatische Charakter-Einblendungen im Video (Lolfi) und manuellen Schnitt.
    Episoden-Offsets werden aus den MP3-Längen + der Merge-Pause berechnet,
    exakt wie merge_episodes() die Tonspur zusammensetzt."""
    import json as _json

    spans = []
    scenes = []
    missing = []
    for path, offset_ms in zip(episode_paths, episode_offsets_ms(episode_paths, pause_ms)):
        speakers_file = os.path.splitext(path)[0] + "_SPEAKERS.json"
        if os.path.exists(speakers_file):
            with open(speakers_file, "r", encoding="utf-8") as f:
                episode_data = _json.load(f)
                for span in episode_data.get("spans", []):
                    spans.append({"start_ms": int(offset_ms + span["start_ms"]),
                                  "end_ms": int(offset_ms + span["end_ms"]),
                                  "role": span["role"], "style": span.get("style", "")})
                for scene in episode_data.get("scenes", []):
                    scenes.append({"start_ms": int(offset_ms + scene["start_ms"]),
                                   "end_ms": int(offset_ms + scene["end_ms"]),
                                   "roles": scene["roles"]})
        else:
            missing.append(os.path.basename(path))

    if missing:
        print(f"Hinweis: Keine Sprecher-Timeline für {', '.join(missing)} — "
              f"Episode(n) neu vertonen, um sie zu erzeugen (Anthologie-Timeline unvollständig).")
    if not spans:
        return

    json_path = os.path.splitext(anthology_path)[0] + "_SPEAKERS.json"
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump({"episode": os.path.basename(anthology_path), "spans": spans, "scenes": scenes},
                   f, ensure_ascii=False, indent=1)

    txt_path = os.path.splitext(anthology_path)[0] + "_SPEAKERS.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("# Sprecher-Timeline — komplette Anthologie\n\n")
        for span in spans:
            f.write(f"{audio.format_timestamp(span['start_ms'])} – "
                    f"{audio.format_timestamp(span['end_ms'])}  {span['role']}\n")
    print(f"Anthologie-Sprecher-Timeline geschrieben: {os.path.basename(json_path)} ({len(spans)} Spannen)")


def merge_location_timelines(episode_paths, anthology_path, pause_ms):
    """Kombiniert die pro Episode geschriebenen *_LOCATIONS.json
    (podcast_maker.py, modusunabhängig) zur Location-Timeline der GESAMTEN
    Anthologie — Grundlage für automatische Hintergrundwechsel im Video
    (Lolfi). Gleiches Offset-Verfahren wie merge_speaker_timelines()."""
    import json as _json

    locations = []
    missing = []
    for path, offset_ms in zip(episode_paths, episode_offsets_ms(episode_paths, pause_ms)):
        locations_file = os.path.splitext(path)[0] + "_LOCATIONS.json"
        if os.path.exists(locations_file):
            with open(locations_file, "r", encoding="utf-8") as f:
                episode_data = _json.load(f)
                for loc in episode_data.get("locations", []):
                    locations.append({"start_ms": int(offset_ms + loc["start_ms"]),
                                      "end_ms": int(offset_ms + loc["end_ms"]),
                                      "location": loc["location"]})
        else:
            missing.append(os.path.basename(path))

    if not locations:
        return  # Serie ohne 'locations' in episodes.json -- kein Hinweis nötig, ist der Normalfall

    if missing:
        print(f"Hinweis: Keine Location-Timeline für {', '.join(missing)} — "
              f"Episode(n) neu vertonen, um sie zu erzeugen (Anthologie-Timeline unvollständig).")

    json_path = os.path.splitext(anthology_path)[0] + "_LOCATIONS.json"
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump({"episode": os.path.basename(anthology_path), "locations": locations},
                   f, ensure_ascii=False, indent=1)
    print(f"Anthologie-Location-Timeline geschrieben: {os.path.basename(json_path)} ({len(locations)} Abschnitt(e))")


def generate_upload_index(series, episode_pairs, anthology_path, data, chapters=None):
    """Schreibt eine durchsuchbare Übersicht (Dateiname -> Titel/Beschreibung)
    nach output/UPLOAD_INDEX.md — sonst muss man beim Hochladen jede
    *_META.txt einzeln öffnen, um zu sehen, welcher Titel zu welcher
    MP3-Datei gehört. chapters (aus write_chapters) ergänzt eine fertige
    YouTube-Kapitelliste für die Videobeschreibung."""
    index_path = os.path.join(series.output_dir, "UPLOAD_INDEX.md")
    series_title = data.get("series_title", "")
    season = data.get("season")
    prefix = data.get("output_prefix", config.DEFAULTS["output_prefix"])
    lines = [f"# Upload-Index — {series_title}\n"]

    if chapters:
        lines.append("## YouTube-Kapitel (unverändert in die Videobeschreibung kopieren)\n")
        lines.append("```")
        for ch in chapters:
            lines.append(f"{format_youtube_timestamp(ch['start_ms'])} {ch['title']}")
        lines.append("```\n")
        lines.append("---\n")

    for script, episode_file in episode_pairs:
        meta_path = os.path.splitext(script)[0] + "_META.txt"
        title, desc, question = audio.parse_meta_file(meta_path)
        episode_num = audio.extract_episode_number(script, prefix)
        display_title = audio.format_season_title(series_title, season, episode_num, title)
        lines.append(f"## {os.path.basename(episode_file)}")
        lines.append(f"**Titel:** {display_title or '(kein Titel generiert)'}\n")
        if season is not None and episode_num is not None:
            lines.append(f"**Spotify-Metadaten:** Staffel {season}, Folge {episode_num} "
                         f"(in die entsprechenden Felder bei Spotify for Podcasters eintragen)\n")
        lines.append(f"**Beschreibung:**\n{desc or '(keine Beschreibung generiert)'}\n")
        # Comment-Bait-Frage fürs Ende der Videobeschreibung/einen Community-Post —
        # bewusst spoilerfrei (siehe generate_episode_meta-Prompt), fehlt bei
        # Episoden von vor diesem Feature (keine FRAGE: in der META.txt).
        if question:
            lines.append(f"**Frage an die Zuschauer:** {question}\n")
        lines.append("---\n")

    if os.path.exists(anthology_path):
        title, desc, _question = audio.parse_meta_file(series.anthology_meta_file)
        lines.append(f"## {os.path.basename(anthology_path)}  (Gesamt-Anthologie)")
        lines.append(f"**Titel:** {title or '(kein Titel generiert)'}\n")
        lines.append(f"**Beschreibung:**\n{desc or '(keine Beschreibung generiert)'}\n")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nUpload-Index geschrieben: {os.path.basename(index_path)}")


def generate_anthology_meta(series, data, force=False) -> bool:
    """Erzeugt Titel + Beschreibung für die GESAMTE Anthologie (alle Episoden
    als eine durchgehende Tonspur) — analog zur Einzelepisoden-Meta, aber für
    die Serie als Ganzes. Nutzt dieselbe Claude-CLI-Logik, kein separater API-Key."""
    if os.path.exists(series.anthology_meta_file) and not force:
        print(f"Anthologie-Titel & Beschreibung bereits vorhanden: "
              f"{os.path.basename(series.anthology_meta_file)} ✓")
        return True

    episodes = data.get("episodes", [])
    persona = data.get("writer_persona", config.DEFAULTS["writer_persona"])
    language = data.get("language", config.DEFAULTS["language"])
    series_title = data.get("series_title", "")
    # light_model: reine Metadaten-Extraktion (analog Episoden-Meta), keine kreative
    # Skript-Arbeit — braucht nicht das teure Schreibmodell.
    model = data.get("generation", {}).get("light_model", config.DEFAULTS["light_model"])

    figures_text = "\n".join(f"- {ep['figure']}: {ep['theme']}" for ep in episodes)
    prompt = (
        f"You are {persona}. \"{series_title}\" is a complete anthology podcast "
        f"series that has just been assembled into ONE continuous long-form "
        f"video/audio, covering these figures in order:\n{figures_text}\n\n"
        f"Write metadata for publishing this COMPLETE anthology as a single "
        f"video, entirely in {language}:\n"
        f"1. A title for the whole anthology: atmospheric, evokes the "
        f"unifying theme across all figures, maximum 100 characters, no "
        f"quotation marks, no clickbait phrases.\n"
        f"2. A description: 150 to 220 words, matching the storyteller "
        f"tone of the series. Introduce the anthology as a whole and its "
        f"unifying theme, convey that it spans multiple figures across one "
        f"continuous long-form experience, without spoiling any single "
        f"episode's specific ending. Mention the series name once. No "
        f"hashtags, no emojis, no bullet points, no meta commentary.\n\n"
        f"Answer in EXACTLY this format and nothing else:\n"
        f"TITLE: <the title>\nDESCRIPTION:\n<the description>"
    )

    print("\nGeneriere Anthologie-Titel & Beschreibung ...")
    for attempt in range(1, MAX_RETRIES + 1):
        output = call_claude(prompt, model)
        if output:
            match = re.search(r"TITLE:\s*(.+?)\s*DESCRIPTION:\s*(.+)", output, re.DOTALL)
            if match:
                title = match.group(1).strip()
                description = match.group(2).strip()
                if title and len(title) <= 150 and len(description.split()) >= 80:
                    with open(series.anthology_meta_file, "w", encoding="utf-8") as f:
                        f.write(f"TITEL:\n{title}\n\nBESCHREIBUNG:\n{description}\n")
                    print(f"Gespeichert: {os.path.basename(series.anthology_meta_file)}")
                    print(f"  → {title}")
                    return True
        print(f"Versuch {attempt}/{MAX_RETRIES}: unbrauchbare Metadaten-Ausgabe.")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    print("Anthologie-Titel & Beschreibung fehlgeschlagen — batch.py erneut starten zum Nachholen.")
    return False


def main():
    parser = argparse.ArgumentParser(description="Alle Skripte einer Serie vertonen + Anthologie mergen")
    # Aufgeteilter Render (siehe podcast_maker.py --skip-merge/--merge-only):
    # reine TTS-Vertonung von der teuren GPU-Instanz trennen, Mastering lokal.
    parser.add_argument("--skip-merge", action="store_true",
                        help="Jede Episode NUR vertonen (Parts erzeugen), KEIN Merge/Mastering und "
                             "KEIN Anthology-Merge — für Remote-Rendern auf der GPU-Instanz.")
    parser.add_argument("--merge-only", action="store_true",
                        help="TTS überspringen; jede Episode nur aus vorhandenen Part-WAVs lokal "
                             "mastern + Anthologie mergen (kein TTS-Server nötig). Gegenstück zu --skip-merge.")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    if args.skip_merge and args.merge_only:
        print("FEHLER: --skip-merge und --merge-only schließen sich gegenseitig aus.")
        sys.exit(1)

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)
    series.ensure_dirs()

    prefix = data.get("output_prefix", config.DEFAULTS["output_prefix"])
    pause_ms = data.get("audio", {}).get("pause_between_episodes_ms", 6000)

    # Nur echte Episoden-Skripte (figur1.txt, figur2.txt, ...) — der reine
    # Glob "<prefix>*.txt" matchte sonst fälschlich auch die *_META.txt.
    all_txt = glob.glob(os.path.join(series.scripts_dir, f"{prefix}*.txt"))
    scripts = sorted(
        s for s in all_txt
        if re.fullmatch(rf"{re.escape(prefix)}\d+\.txt", os.path.basename(s))
    )

    if not scripts:
        print(f"Keine {prefix}*.txt Dateien in {series.scripts_dir}/ gefunden.")
        print(f"Erst Skripte generieren: python3 -m fabrik.cli.generate_episode all --series {series.slug}")
        return

    print(f"Serie: {series.slug} — {len(scripts)} Skript(e): "
          f"{', '.join(os.path.basename(s) for s in scripts)}\n")

    anthology_path = os.path.join(series.output_dir, ANTHOLOGY_FILENAME)
    if os.path.exists(anthology_path):
        print(f"Anthology existiert bereits: {ANTHOLOGY_FILENAME} – lösche sie zum Neu-Generieren.")

    # Ein einzelner Chunk-Timeout/eine kurze Server-Unterbrechung mitten in
    # einem langen "alle Episoden"-Lauf lässt bisher NUR diese eine Episode
    # fehlschlagen (podcast_maker.py bricht die Episode ab, sobald ein Part
    # nach MAX_RETRIES-Versuchen misslingt) — der Rest lief zwar weiter, aber
    # ein Fehlschlag blieb bis zum manuellen Neustart liegen. Da fertige
    # Chunks/Parts als Checkpoints erhalten bleiben (podcast_maker.py), ist
    # ein Retry hier billig (setzt mitten in der Episode fort, nicht von
    # vorn) — bis zu BATCH_RETRY_ROUNDS zusätzliche Durchläufe NUR über die
    # noch offenen Episoden, mit Pause dazwischen, bevor endgültig aufgegeben wird.
    BATCH_RETRY_ROUNDS = 2
    BATCH_RETRY_DELAY = 20

    # Optionaler zweiter TTS-Server: mit audio.secondary_api_url vertonen zwei
    # Worker parallel (Worker 2 rendert via podcast_maker --api-url). Der
    # Server muss dieselben Stimmen/Clones anbieten — sonst hard-failt dort
    # die Voice-Auflösung, die Episode landet in der Retry-Runde und damit
    # ggf. wieder beim Primär-Server.
    # merge-only läuft rein lokal (CPU), kein TTS-Server — der Zweit-Server-
    # Pfad (TTS-Lastverteilung) ist dann bedeutungslos und bleibt aus.
    secondary_url = None if args.merge_only else data.get("audio", {}).get("secondary_api_url")
    if secondary_url and not url_reachable(secondary_url):
        print(f"Hinweis: audio.secondary_api_url ({secondary_url}) nicht erreichbar — "
              f"vertone sequentiell über den Primär-Server.")
        secondary_url = None
    if secondary_url:
        print(f"Zweiter TTS-Server aktiv: {secondary_url} — vertone 2 Episoden parallel.")

    completed = {}  # Episoden-Index -> (script, episode_file); hält die Merge-Reihenfolge stabil

    def render_one(i, script, api_url=None) -> bool:
        """True, sobald die Episoden-MP3 existiert (frisch gerendert oder von
        einem früheren Lauf). list/dict-Zugriffe hier sind unter CPython atomar,
        die Worker teilen sich sonst keinen Zustand."""
        name = episode_name_from_file(script)
        episode_file = os.path.join(series.output_dir, f"{name}_FULL_EPISODE.mp3")

        # --skip-merge: die MP3 entsteht in diesem Modus NIE (nur Parts) — sie
        # taugt weder als "schon fertig"-Kürzel noch als Erfolgs-Marker.
        # podcast_maker überspringt bereits erzeugte Parts selbst (Checkpoints),
        # ein Re-Run ist also billig.
        if not args.skip_merge and os.path.exists(episode_file):
            size_mb = os.path.getsize(episode_file) / (1024 * 1024)
            print(f"[{i}/{len(scripts)}] Übersprungen (existiert): {name}_FULL_EPISODE.mp3 ({size_mb:.1f} MB)")
            completed[i] = (script, episode_file)
            return True

        via = f" via {api_url}" if api_url else ""
        ziel = "nur Parts (skip-merge)" if args.skip_merge else \
               "lokales Mastering (merge-only)" if args.merge_only else \
               f"{name}_FULL_EPISODE.mp3"
        print(f"[{i}/{len(scripts)}] Starte{via}: {os.path.basename(script)} → {ziel}")
        cmd = [sys.executable, "-m", "fabrik.cli.podcast_maker", script, "--name", name,
               "--series", series.slug]
        if api_url:
            cmd += ["--api-url", api_url]
        if args.skip_merge:
            cmd.append("--skip-merge")
        elif args.merge_only:
            cmd.append("--merge-only")
        result = subprocess.run(cmd, check=False, cwd=paths.BASE_DIR)

        if args.skip_merge:
            # Erfolg = Subprozess sauber beendet (keine MP3 als Marker).
            if result.returncode != 0:
                print(f"  FEHLER bei {script} – wird ggf. erneut versucht.")
                return False
            completed[i] = (script, None)
            print(f"  Parts fertig: {name}\n")
            return True

        if result.returncode != 0 or not os.path.exists(episode_file):
            print(f"  FEHLER bei {script} – wird ggf. erneut versucht.")
            return False

        completed[i] = (script, episode_file)
        print(f"  Fertig: {name}_FULL_EPISODE.mp3\n")
        return True

    pending = list(enumerate(scripts, 1))
    failed = []
    for round_num in range(BATCH_RETRY_ROUNDS + 1):
        if not pending:
            break
        if round_num > 0:
            print(f"\n── Retry-Runde {round_num}/{BATCH_RETRY_ROUNDS} für "
                  f"{len(pending)} fehlgeschlagene Episode(n) — warte {BATCH_RETRY_DELAY}s ──")
            time.sleep(BATCH_RETRY_DELAY)
        failed = []
        if secondary_url and len(pending) > 1:
            import queue
            import threading
            work = queue.Queue()
            for item in pending:
                work.put(item)
            failed_lock = threading.Lock()

            def worker(api_url):
                while True:
                    try:
                        i, script = work.get_nowait()
                    except queue.Empty:
                        return
                    if not render_one(i, script, api_url):
                        with failed_lock:
                            failed.append((i, script))

            threads = [threading.Thread(target=worker, args=(url,))
                       for url in (None, secondary_url)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            failed.sort()
        else:
            for i, script in pending:
                if not render_one(i, script):
                    failed.append((i, script))

        pending = failed

    episode_pairs = [completed[i] for i in sorted(completed)]  # für den Upload-Index
    episode_paths = [ep for _, ep in episode_pairs]

    print(f"\nEpisoden fertig: {len(episode_paths)} | Fehlgeschlagen: {len(failed)}")

    # Endgültige Fehlschläge als Datei persistieren, nicht nur als Log-Zeile:
    # webui/status.py pollt eh das Dateisystem und macht daraus eine rote
    # Statuskarte — sonst fällt eine liegengebliebene Episode erst auf, wenn
    # jemand das SSE-Log bis zum Ende liest. Ein späterer erfolgreicher Lauf
    # räumt die Datei wieder weg.
    import json as _json
    failed_marker = os.path.join(series.output_dir, "FAILED_EPISODES.json")
    if failed:
        with open(failed_marker, "w", encoding="utf-8") as f:
            _json.dump({
                "failed": [os.path.basename(s) for _, s in failed],
                "retry_rounds": BATCH_RETRY_ROUNDS,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }, f, ensure_ascii=False, indent=1)
        print(f"Endgültig fehlgeschlagen nach {BATCH_RETRY_ROUNDS} Retry-Runde(n): {[s for _, s in failed]}")
        print(f"Fehlschlag-Marker geschrieben: {os.path.basename(failed_marker)} (WebUI zeigt eine rote Karte).")
        print("Bitte TTS-Server/Log prüfen und Script danach neu starten – bereits fertige Episoden werden übersprungen.")
    elif os.path.exists(failed_marker):
        os.remove(failed_marker)

    if args.skip_merge:
        # Reine Vertonung fertig (nur Parts). Anthology-Merge + Upload-Index
        # brauchen die Episoden-MP3s, die es hier noch nicht gibt — beides
        # läuft lokal via 'batch.py --merge-only' (bzw. automatisch über
        # render_remote.sh --local-master) nach dem Download.
        print("\n--skip-merge: reine Vertonung fertig (nur Parts erzeugt), kein "
              "Merge/Mastering/Index. Lokal fertigstellen mit 'batch.py --merge-only'.")
        return

    if len(episode_paths) < 2:
        print("Weniger als 2 Episoden vorhanden – kein Anthology-Merge.")
        generate_upload_index(series, episode_pairs, anthology_path, data)
        return

    if not data.get("audio", {}).get("merge_anthology", True):
        print("audio.merge_anthology: false – Episoden bleiben eigenständig, kein Anthology-Merge.")
        generate_upload_index(series, episode_pairs, anthology_path, data)
        return

    if os.path.exists(anthology_path):
        print(f"\n{ANTHOLOGY_FILENAME} existiert bereits – Merge übersprungen.")
    else:
        merge_episodes(episode_paths, anthology_path, series.output_dir, pause_ms)

    if data.get("mode", "narration") == "drama":
        merge_speaker_timelines(episode_paths, anthology_path, pause_ms)
    merge_subtitles(episode_paths, anthology_path, pause_ms)
    merge_location_timelines(episode_paths, anthology_path, pause_ms)

    chapters = write_chapters(episode_pairs, anthology_path, pause_ms)

    # Titel & Beschreibung sind nice-to-have — ein Fehlschlag hier lässt den
    # Merge nicht scheitern (Skript erneut starten generiert sie nach).
    generate_anthology_meta(series, data)
    title, description, _question = audio.parse_meta_file(series.anthology_meta_file)
    if title:
        if audio.tag_mp3(anthology_path, title=title, album=data.get("series_title", ""), comment=description):
            print(f"ID3-Tags geschrieben (Titel: \"{title}\")")
    generate_upload_index(series, episode_pairs, anthology_path, data, chapters=chapters)


if __name__ == "__main__":
    main()
