import glob
import json
import os
import re
import sys
import subprocess
import time
from pydub import AudioSegment
from pydub.utils import mediainfo

import generate_episode as ge

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "podcast_output")
EPISODES_FILE = os.path.join(SCRIPT_DIR, "episodes.json")
ANTHOLOGY_META_FILE = os.path.join(SCRIPT_DIR, "ANTHOLOGY_META.txt")
SILENCE_BETWEEN_EPISODES_MS = 6000
ANTHOLOGY_FILENAME = "ANTHOLOGY_COMPLETE.mp3"
SCRIPT_PREFIX = "figur"


def load_batch_config():
    """Liest Pause und Datei-Präfix aus episodes.json (Fallback: eingebaute Defaults)."""
    global SILENCE_BETWEEN_EPISODES_MS, SCRIPT_PREFIX
    try:
        with open(EPISODES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Warnung: episodes.json nicht gefunden — nutze eingebaute Defaults.")
        return
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"FEHLER: episodes.json ist kein gültiges JSON "
            f"(Zeile {e.lineno}, Spalte {e.colno}: {e.msg}). Abbruch."
        )
    SILENCE_BETWEEN_EPISODES_MS = data.get("audio", {}).get(
        "pause_between_episodes_ms", SILENCE_BETWEEN_EPISODES_MS)
    SCRIPT_PREFIX = data.get("output_prefix", SCRIPT_PREFIX)


def merge_episodes(episode_paths, output_path):
    """Konkateniert die Episoden-MP3s per ffmpeg-Stream-Copy: konstanter
    Speicherverbrauch (nichts wird dekodiert) und kein weiterer Re-Encode.
    Voraussetzung: alle Episoden stammen aus podcast_maker.py und haben
    daher identische Audio-Parameter."""
    print(f"\nMerge {len(episode_paths)} Episoden → {os.path.basename(output_path)}")

    # Pausen-MP3 mit denselben Parametern wie die Episoden erzeugen
    info = mediainfo(episode_paths[0])
    silence = AudioSegment.silent(
        duration=SILENCE_BETWEEN_EPISODES_MS,
        frame_rate=int(info.get("sample_rate", 44100)),
    ).set_channels(int(info.get("channels", 1)))
    silence_path = os.path.join(OUTPUT_DIR, ".silence_gap.mp3")
    silence.export(silence_path, format="mp3", bitrate="192k")

    def quoted(path):
        return "'" + path.replace("'", "'\\''") + "'"

    list_path = os.path.join(OUTPUT_DIR, ".concat_list.txt")
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


def parse_meta_file(meta_path):
    """Liest TITEL/BESCHREIBUNG aus einer *_META.txt (Format wie von
    generate_episode_meta()/generate_anthology_meta() geschrieben)."""
    if not os.path.exists(meta_path):
        return None, None
    with open(meta_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"TITEL:\s*(.+?)\s*BESCHREIBUNG:\s*(.+)", content, re.DOTALL)
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2).strip()


def generate_upload_index(episode_pairs, anthology_path, data):
    """Schreibt eine durchsuchbare Übersicht (Dateiname -> Titel/Beschreibung)
    nach podcast_output/UPLOAD_INDEX.md — sonst muss man beim Hochladen jede
    figurN_META.txt einzeln öffnen, um zu sehen, welcher Titel zu welcher
    MP3-Datei gehört."""
    index_path = os.path.join(OUTPUT_DIR, "UPLOAD_INDEX.md")
    lines = [f"# Upload-Index — {data.get('series_title', '')}\n"]

    for script, episode_file in episode_pairs:
        stem = os.path.splitext(os.path.basename(script))[0]
        meta_path = os.path.join(SCRIPT_DIR, f"{stem}_META.txt")
        title, desc = parse_meta_file(meta_path)
        lines.append(f"## {os.path.basename(episode_file)}")
        lines.append(f"**Titel:** {title or '(kein Titel generiert)'}\n")
        lines.append(f"**Beschreibung:**\n{desc or '(keine Beschreibung generiert)'}\n")
        lines.append("---\n")

    if os.path.exists(anthology_path):
        title, desc = parse_meta_file(ANTHOLOGY_META_FILE)
        lines.append(f"## {os.path.basename(anthology_path)}  (Gesamt-Anthologie)")
        lines.append(f"**Titel:** {title or '(kein Titel generiert)'}\n")
        lines.append(f"**Beschreibung:**\n{desc or '(keine Beschreibung generiert)'}\n")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nUpload-Index geschrieben: {os.path.basename(index_path)}")


def generate_anthology_meta(data: dict, force: bool = False) -> bool:
    """Erzeugt Titel + Beschreibung für die GESAMTE Anthologie (alle Episoden
    als eine durchgehende Tonspur) — analog zu generate_episode_meta() pro
    Einzelepisode, aber für die Serie als Ganzes. Nutzt dieselbe Claude-CLI-
    Logik wie generate_episode.py (call_claude), kein separater API-Key."""
    if os.path.exists(ANTHOLOGY_META_FILE) and not force:
        print(f"Anthologie-Titel & Beschreibung bereits vorhanden: {os.path.basename(ANTHOLOGY_META_FILE)} ✓")
        return True

    episodes = data.get("episodes", [])
    persona = data.get("writer_persona", ge.DEFAULTS["writer_persona"])
    language = data.get("language", ge.DEFAULTS["language"])
    series_title = data.get("series_title", "")
    model = data.get("generation", {}).get("model", ge.DEFAULTS["model"])

    figures_text = "\n".join(f"- {ep['figure']}: {ep['theme']}" for ep in episodes)
    prompt = (
        f"You are {persona}. \"{series_title}\" is a complete anthology podcast "
        f"series that has just been assembled into ONE continuous long-form "
        f"video/audio, covering these figures in order:\n{figures_text}\n\n"
        f"Write metadata for publishing this COMPLETE anthology as a single "
        f"video, entirely in {language}:\n"
        f"1. A title for the whole anthology: dark, atmospheric, evokes the "
        f"unifying theme across all figures, maximum 100 characters, no "
        f"quotation marks, no clickbait phrases.\n"
        f"2. A description: 150 to 220 words, matching the dark storyteller "
        f"tone of the series. Introduce the anthology as a whole and its "
        f"unifying theme, convey that it spans multiple figures across one "
        f"continuous long-form experience, without spoiling any single "
        f"episode's specific ending. Mention the series name once. No "
        f"hashtags, no emojis, no bullet points, no meta commentary.\n\n"
        f"Answer in EXACTLY this format and nothing else:\n"
        f"TITLE: <the title>\nDESCRIPTION:\n<the description>"
    )

    print("\nGeneriere Anthologie-Titel & Beschreibung ...")
    for attempt in range(1, ge.MAX_RETRIES + 1):
        output = ge.call_claude(prompt, model)
        if output:
            match = re.search(r"TITLE:\s*(.+?)\s*DESCRIPTION:\s*(.+)", output, re.DOTALL)
            if match:
                title = match.group(1).strip()
                description = match.group(2).strip()
                if title and len(title) <= 150 and len(description.split()) >= 80:
                    with open(ANTHOLOGY_META_FILE, "w", encoding="utf-8") as f:
                        f.write(f"TITEL:\n{title}\n\nBESCHREIBUNG:\n{description}\n")
                    print(f"Gespeichert: {os.path.basename(ANTHOLOGY_META_FILE)}")
                    print(f"  → {title}")
                    return True
        print(f"Versuch {attempt}/{ge.MAX_RETRIES}: unbrauchbare Metadaten-Ausgabe.")
        if attempt < ge.MAX_RETRIES:
            time.sleep(ge.RETRY_DELAY)

    print("Anthologie-Titel & Beschreibung fehlgeschlagen — batch.py erneut starten zum Nachholen.")
    return False


def main():
    load_batch_config()
    # Nur echte Episoden-Skripte (figur1.txt, figur2.txt, ...) — der reine
    # Glob "figur*.txt" matchte bisher fälschlich auch figurN_META.txt
    # (Titel/Beschreibung), die dadurch mitvertont und in die Anthologie
    # gemischt wurden.
    all_txt = glob.glob(os.path.join(SCRIPT_DIR, f"{SCRIPT_PREFIX}*.txt"))
    scripts = sorted(
        s for s in all_txt
        if re.fullmatch(rf"{re.escape(SCRIPT_PREFIX)}\d+\.txt", os.path.basename(s))
    )

    if not scripts:
        print(f"Keine {SCRIPT_PREFIX}*.txt Dateien gefunden.")
        print(f"Benenne deine Skript-Dateien: {SCRIPT_PREFIX}1.txt, {SCRIPT_PREFIX}2.txt, ...")
        return

    print(f"{len(scripts)} Skript(e) gefunden: {', '.join(os.path.basename(s) for s in scripts)}\n")

    anthology_path = os.path.join(OUTPUT_DIR, ANTHOLOGY_FILENAME)
    if os.path.exists(anthology_path):
        print(f"Anthology existiert bereits: {ANTHOLOGY_FILENAME} – lösche sie zum Neu-Generieren.")

    episode_pairs = []  # (script_path, episode_file) — für den Upload-Index
    failed = []

    for i, script in enumerate(scripts, 1):
        name = episode_name_from_file(script)
        episode_file = os.path.join(OUTPUT_DIR, f"{name}_FULL_EPISODE.mp3")

        if os.path.exists(episode_file):
            size_mb = os.path.getsize(episode_file) / (1024 * 1024)
            print(f"[{i}/{len(scripts)}] Übersprungen (existiert): {name}_FULL_EPISODE.mp3 ({size_mb:.1f} MB)")
            episode_pairs.append((script, episode_file))
            continue

        print(f"[{i}/{len(scripts)}] Starte: {os.path.basename(script)} → {name}_FULL_EPISODE.mp3")
        podcast_maker_py = os.path.join(SCRIPT_DIR, "podcast_maker.py")
        result = subprocess.run(
            [sys.executable, podcast_maker_py, script, "--name", name],
            check=False
        )

        if result.returncode != 0 or not os.path.exists(episode_file):
            print(f"  FEHLER bei {script} – übersprungen.")
            failed.append(script)
            continue

        episode_pairs.append((script, episode_file))
        print(f"  Fertig: {name}_FULL_EPISODE.mp3\n")

    episode_paths = [ep for _, ep in episode_pairs]

    print(f"\nEpisoden fertig: {len(episode_paths)} | Fehlgeschlagen: {len(failed)}")

    if failed:
        print(f"Fehlgeschlagen: {failed}")
        print("Bitte Script neu starten – bereits fertige Episoden werden übersprungen.")

    data = ge.load_episodes()

    if len(episode_paths) < 2:
        print("Weniger als 2 Episoden vorhanden – kein Anthology-Merge.")
        generate_upload_index(episode_pairs, anthology_path, data)
        return

    if os.path.exists(anthology_path):
        print(f"\n{ANTHOLOGY_FILENAME} existiert bereits – Merge übersprungen.")
    else:
        merge_episodes(episode_paths, anthology_path)

    # Titel & Beschreibung sind nice-to-have — ein Fehlschlag hier lässt den
    # Merge nicht scheitern (Skript erneut starten generiert sie nach).
    generate_anthology_meta(data)
    generate_upload_index(episode_pairs, anthology_path, data)


if __name__ == "__main__":
    main()
