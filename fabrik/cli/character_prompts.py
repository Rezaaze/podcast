#!/usr/bin/env python3
"""Erzeugt Bild-Prompts für Charakter-Porträts einer Drama-Serie — und,
falls OPENAI_API_KEY gesetzt ist, gleich die PNGs dazu.

Verwendung:
  python3 character_prompts.py                    # aktuelle Serie (series/LATEST)
  python3 character_prompts.py --series thin_walls
  python3 character_prompts.py --force             # vorhandene Prompts neu generieren
  python3 character_prompts.py --no-images         # nur Prompts, keine Bilder erzeugen

Für jede Rolle aus dem voices-Mapping (außer NARRATOR) baut Claude ein
neutrales Porträt PLUS ein Porträt je Emotion (siehe EMOTIONS unten, spiegelt
Lolfis Emotionserkennung) — alle mit einem für die Rolle IDENTISCHEN
Charakter und einem für alle Charaktere IDENTISCHEN Stil-Block, damit die
Bilder wie ein Ensemble aussehen und nur der Gesichtsausdruck variiert.

Ist OPENAI_API_KEY gesetzt (und --no-images nicht angegeben), wird für jede
Rolle+Emotion sofort ein PNG über gpt-image-1-mini erzeugt und als
series/<slug>/characters/<ROLLE>.png (neutral) bzw.
series/<slug>/characters/<ROLLE>_<emotion>.png abgelegt — ohne Key bleibt es
wie bisher bei den Text-Prompts zum manuellen Einfügen bei einem Bildmodell
deiner Wahl. Dort findet sie das Lolfi-Video-Rendering und blendet je
Sprech-Abschnitt automatisch das zur erkannten Emotion passende Bild ein
(Fallback: neutrales Bild), basierend auf der Sprecher-Timeline aus
podcast_maker.py/batch.py.

Braucht kein .venv — nur die Claude CLI (wie generate_episode.py); die
Bildgenerierung selbst nutzt nur stdlib (urllib), kein zusätzliches Paket.
"""

import argparse
import os
import re
import sys
import time

from fabrik.core import config, paths
from fabrik.writing import image_backends
from fabrik.writing.script_parser import ScriptFormatError, parse_drama_part
from fabrik.writing.script_writer import call_claude, MAX_RETRIES, RETRY_DELAY

PROMPTS_FILENAME = "PROMPTS.txt"

# Spiegelt EXAKT die Emotion-Keys aus Lolfis EMOTIONS-Dict
# (~/Downloads/Lolfi/lofi_system.py) — das ist eine separate Codebase ohne
# gemeinsamen Import, die Keys müssen also manuell synchron gehalten werden.
# Lolfi klassifiziert pro Sprech-Spanne aus dem Style-Regieanweisungstext eine
# dieser Emotionen und blendet dann, wenn eine Datei
# characters/<ROLLE>_<emotion>.png existiert, genau die statt des neutralen
# Porträts ein (Fallback: neutrales Bild, wenn die Variante fehlt).
EMOTIONS = {
    "anger": "angry, furious — glaring eyes, tense jaw, aggressive forward posture",
    "fear": "afraid, scared — wide eyes, tense shoulders, defensive/recoiling posture",
    "sadness": "sad, sorrowful — downcast eyes, heavy tired expression, slumped posture",
    "joy": "happy, joyful — genuine warm smile, bright eyes, relaxed open posture",
    "surprise": "surprised, shocked — wide eyes, raised eyebrows, mouth slightly open",
    "love": "tender, affectionate — soft warm gaze, gentle smile",
    "vulnerability": "guard slipping, raw — a crack in composure, caught off guard, unguarded eyes",
}


# Spiegelt EXAKT die Keywords aus Lolfis classify_emotion() (lofi_system.py)
# — gleiche dict-Reihenfolge (= gleiche Match-Priorität, "vulnerability" zuerst
# aus demselben Grund wie dort: Fassade-bricht-Regieanweisungen dürfen nicht
# fälschlich als "joy" durchgehen). Manuell synchron halten, wie EMOTIONS oben
# — kein gemeinsamer Import zwischen den beiden Codebases.
EMOTION_KEYWORDS = {
    "vulnerability": ["crack", "raw", "unguarded", "breaking through",
                       "catching himself", "catching herself", "for one line",
                       "for one beat", "genuine", "real feeling", "something real",
                       "forced", "overcompensating", "overly bright", "deflecting"],
    "anger": ["angry", "furious", "rage", "snapp", "hissing", "seething",
              "aggressive", "heated", "bitter", "hostile", "accusing", "sharp",
              "cutting", "defensive", "dismissing"],
    "fear": ["afraid", "fear", "scared", "nervous", "anxious", "panic",
             "tense", "trembl", "terrified", "uneasy", "shaky", "shaken",
             "shakier", "unsteady", "reeling", "alarmed", "dread"],
    "sadness": ["sad", "tearful", "crying", "mournful", "grief", "resigned",
                "defeated", "hollow", "heavy-hearted", "somber", "wistful",
                "wounded"],
    "joy": ["happy", "joyful", "cheerful", "laughing", "bright", "playful",
            "amused", "excited", "delighted", "teasing", "lighthearted"],
    "surprise": ["surprised", "shocked", "stunned", "startled", "disbelief",
                 "astonished", "incredulous", "caught off"],
    "love": ["tender", "affectionate", "loving", "intimate", "adoring",
             "flirt", "longing", "yearning"],
}
assert set(EMOTION_KEYWORDS) == set(EMOTIONS), "EMOTION_KEYWORDS muss exakt zu EMOTIONS passen"


def classify_emotion(style_text):
    """Exakt Lolfis classify_emotion() gespiegelt — ordnet eine Style-Regie-
    anweisung ("whispering, afraid to be heard") der ersten passenden Emotion
    zu, None wenn nichts matcht. Nur wenn dieselbe Klassifikation hier auch
    tatsächlich matcht, würde Lolfi die entsprechende Emotionsvariante beim
    Video-Rendern je abrufen."""
    if not style_text:
        return None
    lowered = style_text.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return emotion
    return None


def find_used_emotions(series, roles):
    """Scannt alle vorhandenen Episoden-Skripte nach style-Regieanweisungen
    pro Rolle und klassifiziert sie über classify_emotion() — liefert pro
    Rolle nur die Emotionen, die Lolfi beim Video-Rendern für diese Rolle
    überhaupt einmal abrufen würde. Rollen ohne (noch) generierte Skripte
    bekommen eine leere Menge zurück (→ nur das Neutral-Porträt nötig)."""
    used = {role: set() for role in roles}
    scripts_dir = series.scripts_dir
    if not os.path.isdir(scripts_dir):
        return used

    script_files = [
        f for f in os.listdir(scripts_dir)
        if f.endswith(".txt") and not f.endswith("_META.txt") and not f.endswith("_REVIEW.txt")
    ]
    for fname in script_files:
        with open(os.path.join(scripts_dir, fname), "r", encoding="utf-8") as f:
            content = f.read()
        for part_text in re.split(r'--- PART \d+ ---', content):
            part_text = part_text.strip()
            if not part_text:
                continue
            try:
                items = parse_drama_part(part_text, voices=None, part_label=fname)
            except ScriptFormatError:
                # Formatfehler werden schon bei generate_episode.py/podcast_maker.py
                # hart geprüft — hier defensiv nur überspringen, nicht abbrechen.
                continue
            for item in items:
                if item.kind != "speech" or item.speaker not in used:
                    continue
                emotion = classify_emotion(item.style)
                if emotion:
                    used[item.speaker].add(emotion)
    return used


def characters_dir(series):
    return os.path.join(series.root, "characters")


def prompts_file(series):
    return os.path.join(characters_dir(series), PROMPTS_FILENAME)


def collect_roles(data):
    """Alle Charakter-Rollen aus voices — der NARRATOR ist Erzähler, keine
    Figur in der Geschichte, und bekommt daher kein Porträt."""
    voices = data.get("voices", {})
    return {role: vcfg for role, vcfg in voices.items() if role != "NARRATOR"}


def expected_block_ids(roles, needed_emotions):
    """Ein Block pro Rolle (neutrales Porträt, ID = Rollenname) plus ein
    Block pro Rolle+tatsächlich-gebrauchter-Emotion (ID = ROLLE__EMOTION,
    z.B. DETECTIVE__ANGER) — Emotionen, die diese Rolle in keiner Zeile
    ihres Skripts je auslöst, werden gar nicht erst angefordert."""
    ids = set(roles)
    for role in roles:
        for emotion in needed_emotions.get(role, set()):
            ids.add(f"{role}__{emotion.upper()}")
    return ids


def build_prompt(data, roles, needed_emotions):
    series_title = data.get("series_title", "")
    language = data.get("language", "German")
    style_guidelines = data.get("style_guidelines", "")

    role_lines = []
    for role, vcfg in roles.items():
        desc = vcfg.get("description", "(keine Beschreibung)")
        emotions_for_role = sorted(needed_emotions.get(role, set()))
        needs = f"NEUTRAL + {', '.join(e.upper() for e in emotions_for_role)}" if emotions_for_role else "NEUTRAL only"
        role_lines.append(f"- {role}: {desc}\n  Needs: {needs}")
    roles_text = "\n".join(role_lines)

    all_needed_emotions = sorted({e for emos in needed_emotions.values() for e in emos})
    emotion_lines = "\n".join(f"- {emo.upper()}: {EMOTIONS[emo]}" for emo in all_needed_emotions)

    return (
        f"\"{series_title}\" is an audio drama podcast (dialogue language: "
        f"{language}). Series tone/style notes: {style_guidelines}\n\n"
        f"These are the characters (role id: description):\n{roles_text}\n\n"
        f"I am producing a video version of the podcast: a dark, calm, "
        f"lofi-style ambient loop video. Whenever a character speaks, their "
        f"portrait is overlaid in a corner of the frame, and the portrait "
        f"switches to match the emotion of the current line so the video "
        f"visibly reflects what's happening in the scene. Each character only "
        f"ever needs the emotions that actually occur for them in the scripts "
        f"— see the 'Needs' line after each character above. I need a NEUTRAL "
        f"portrait for every character, plus exactly the emotion portraits "
        f"listed in their 'Needs' line (in English — image models work best "
        f"with English prompts). Emotion guidance:\n"
        f"{emotion_lines}\n\n"
        f"Requirements for EVERY prompt:\n"
        f"- Start with the exact same shared style block for all characters "
        f"AND all emotions of the same character, so every portrait of one "
        f"character reads as clearly the same person, and the whole cast "
        f"looks like one consistent ensemble. The style must suit a dark "
        f"ambient video: painted/illustrated look, bust portrait (head and "
        f"shoulders), subject facing slightly toward the viewer, plain very "
        f"dark neutral background, soft cinematic rim light, muted colors.\n"
        f"- Then describe the individual character: age, build, face, hair, "
        f"clothing that match their personality and situation from the "
        f"description above. Invent plausible visual details where the "
        f"description is silent — but never contradict it. Keep these "
        f"physical details IDENTICAL across all of that character's "
        f"emotion variants (same face, hair, clothing) — only the facial "
        f"expression and body language may change to fit the emotion.\n"
        f"- The NEUTRAL portrait gets a calm, composed, resting expression. "
        f"Every emotion portrait must clearly show that specific emotion "
        f"(see the guidance after each emotion name above), still true to "
        f"the character's personality.\n"
        f"- One paragraph per prompt, no camera jargon lists, no negative "
        f"prompts, no numbered options.\n\n"
        f"Answer in EXACTLY this format and nothing else: one NEUTRAL block "
        f"per character, plus one block per emotion listed in that "
        f"character's 'Needs' line above — skip any emotion not listed for "
        f"that character. Use the exact role ids and exact emotion names "
        f"given above:\n\n"
        f"=== ROLE_ID ===\n<neutral prompt>\n\n"
        f"=== ROLE_ID__ANGER ===\n<angry prompt>\n\n"
        f"(... exactly the blocks from each character's 'Needs' line, no more, no less ...)"
    )


def parse_blocks(output, expected_ids):
    chunks = re.split(r"===\s*([A-Z0-9_]+)\s*===", output)
    blocks = {}
    for i in range(1, len(chunks), 2):
        block_id = chunks[i].strip()
        text = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
        if block_id in expected_ids and text:
            blocks[block_id] = text
    return blocks


def parse_prompts_file(content, expected_ids):
    """Wie parse_blocks(), aber für das bereits geschriebene PROMPTS.txt-
    Format (Block-Marker trägt zusätzlich den Datei-Hinweis '(→ characters/
    ...)') — damit ein Re-Lauf mit vorhandener PROMPTS.txt die Prompts
    wiederverwenden kann, statt sie erneut per Claude zu erzeugen, nur um
    danach doch bei der Bildgenerierung anzukommen."""
    chunks = re.split(r"===\s*([A-Z0-9_]+)\s*===\s*\(→[^)]*\)\s*\n", content)
    blocks = {}
    for i in range(1, len(chunks), 2):
        block_id = chunks[i].strip()
        text = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
        if block_id in expected_ids and text:
            blocks[block_id] = text
    return blocks


def main():
    parser = argparse.ArgumentParser(description="Porträt-Prompts für die Charaktere einer Drama-Serie")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene PROMPTS.txt neu generieren")
    parser.add_argument("--no-images", action="store_true",
                        help="Nur Text-Prompts erzeugen, auch wenn OPENAI_API_KEY gesetzt ist")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)

    if data.get("mode", "narration") != "drama":
        print(f"Serie '{series.slug}' ist eine Ein-Sprecher-Narration — es gibt keine "
              f"Charakter-Rollen, für die Porträts gebraucht würden.")
        return

    roles = collect_roles(data)
    if not roles:
        print("Keine Charakter-Rollen im voices-Mapping gefunden.")
        return

    out_file = prompts_file(series)
    needed_emotions = find_used_emotions(series, roles)
    print(f"Serie: {series.slug} — {len(roles)} Charakter(e): {', '.join(roles)}")
    if any(needed_emotions.values()):
        for role in roles:
            emos = sorted(needed_emotions.get(role, set()))
            print(f"  {role}: {', '.join(emos) if emos else '(keine — nur Neutral)'}")
    else:
        print("  Keine Skripte gefunden (oder keine Emotion darin erkannt) — "
              "es wird vorerst nur je ein Neutral-Porträt erzeugt. Erneut mit "
              "--force starten, sobald Skripte existieren, um die passenden "
              "Emotionsvarianten nachzuziehen.")

    expected_ids = expected_block_ids(roles, needed_emotions)

    # (block_id, rolle, dateiname, emotion) je Rolle: neutral zuerst (emotion=None),
    # dann je tatsächlich gebrauchte Emotion — diese Reihenfolge ist Voraussetzung
    # für die Bildgenerierung unten (Emotionen brauchen das schon erzeugte Neutral-
    # Bild derselben Rolle als Referenz).
    targets = []
    for role in roles:
        targets.append((role, role, f"{role}.png", None))
        for emotion in sorted(needed_emotions.get(role, set())):
            targets.append((f"{role}__{emotion.upper()}", role, f"{role}_{emotion}.png", emotion))

    # Vorhandene PROMPTS.txt heißt nur "der TEXT ist fertig" — nicht "die
    # Bilder sind fertig" (die Datei wird auch im reinen Text-Modus ohne
    # OPENAI_API_KEY geschrieben). Ein Re-Lauf, nachdem der Key nachträglich
    # gesetzt wurde, muss die vorhandenen Prompts wiederverwenden können,
    # statt sie erneut per Claude zu erzeugen — und darf danach nicht
    # abbrechen, sondern MUSS bei der Bildgenerierung unten ankommen.
    blocks = {}
    if os.path.exists(out_file) and not args.force:
        with open(out_file, "r", encoding="utf-8") as f:
            existing = f.read()
        blocks = parse_prompts_file(existing, expected_ids)
        if len(blocks) == len(expected_ids):
            print(f"Porträt-Prompts bereits vorhanden: {out_file} (--force zum Neu-Generieren) "
                  f"— prüfe/erzeuge fehlende Porträt-Bilder ...")
        else:
            missing = sorted(expected_ids - set(blocks))
            print(f"Vorhandene Prompts decken nicht alle benötigten Blöcke ab (fehlen: "
                  f"{', '.join(missing)}, z.B. neue Emotionen aus inzwischen generierten "
                  f"Skripten) — generiere Prompts neu ...")
            blocks = {}

    if not blocks:
        model = data.get("generation", {}).get("model", config.DEFAULTS["model"])
        n_blocks = len(expected_ids)
        print(f"Generiere Porträt-Prompts ({n_blocks} Blöcke, nur tatsächlich "
              f"gebrauchte Emotionen, Modell: {model}) ...")

        prompt = build_prompt(data, roles, needed_emotions)
        for attempt in range(1, MAX_RETRIES + 1):
            output = call_claude(prompt, model)
            if output:
                blocks = parse_blocks(output, expected_ids)
                if len(blocks) == len(expected_ids):
                    break
                missing = sorted(expected_ids - set(blocks))
                print(f"Versuch {attempt}/{MAX_RETRIES}: Blöcke fehlen für {', '.join(missing)}.")
            else:
                print(f"Versuch {attempt}/{MAX_RETRIES}: keine Ausgabe.")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        if len(blocks) != len(expected_ids):
            print("FEHLER: Porträt-Prompts unvollständig — erneut starten.")
            sys.exit(1)

        os.makedirs(characters_dir(series), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(f"# Charakter-Porträt-Prompts — {data.get('series_title', series.slug)}\n")
            f.write("# Jedes Bild extern generieren und hier im Ordner ablegen unter dem genannten\n")
            f.write("# Dateinamen (neutral: <ROLLE>.png, je Emotion: <ROLLE>_<emotion>.png) —\n")
            f.write("# Lolfi blendet dann automatisch das zur Szene passende Bild ein.\n\n")
            for block_id, _role, fname, _emotion in targets:
                f.write(f"=== {block_id} === (→ characters/{fname})\n{blocks[block_id]}\n\n")

        print(f"\nGespeichert: {out_file}")

    if args.no_images or not image_backends.api_key_available():
        for block_id, _role, fname, _emotion in targets:
            print(f"  === {block_id} ===  →  characters/{fname}")
        if not image_backends.api_key_available():
            print("\nOPENAI_API_KEY nicht gesetzt — Prompts manuell bei einem Bildmodell "
                  "einfügen, PNGs unter den genannten Dateinamen in characters/ ablegen.")
        else:
            print("\n--no-images gesetzt — Prompts manuell bei einem Bildmodell einfügen, "
                  "PNGs unter den genannten Dateinamen in characters/ ablegen.")
        return

    print(f"\nErzeuge Porträts (gpt-image-1-mini, {len(targets)} Bilder) — Emotionsvarianten "
          f"per Bild-Edit auf dem Neutral-Porträt derselben Rolle, für konsistentes Aussehen ...")
    failed = []
    neutral_bytes_by_role = {}
    for block_id, role, fname, emotion in targets:
        img_path = os.path.join(characters_dir(series), fname)
        if os.path.exists(img_path):
            print(f"  {fname}: übersprungen (existiert bereits)")
            if emotion is None:
                with open(img_path, "rb") as f:
                    neutral_bytes_by_role[role] = f.read()
            continue
        try:
            if emotion is None:
                png_bytes = image_backends.generate_image(blocks[block_id])
                neutral_bytes_by_role[role] = png_bytes
            else:
                reference = neutral_bytes_by_role.get(role)
                if reference is None:
                    # Neutral-Bild fehlgeschlagen/übersprungen ohne Cache — Fallback
                    # auf reine Text-Generierung statt ganz abzubrechen.
                    png_bytes = image_backends.generate_image(blocks[block_id])
                else:
                    png_bytes = image_backends.edit_image(reference, blocks[block_id])
            with open(img_path, "wb") as f:
                f.write(png_bytes)
            print(f"  {fname}: gespeichert → characters/{fname}")
        except RuntimeError as exc:
            print(f"  {fname}: FEHLER — {exc}")
            failed.append(fname)

    if failed:
        print(f"\n{len(failed)} Porträt(s) fehlgeschlagen ({', '.join(failed)}) — "
              f"Skript erneut starten (fertige Porträts werden übersprungen).")


if __name__ == "__main__":
    main()
