"""Dramatisches, spoilerfreies Thumbnail pro Episode — ein Poster-Motiv mit
kurzer Hook-Textzeile, in zwei Seitenverhältnissen (Video-Thumbnail 16:9 und
Podcast-Episodenbild 1:1).

Läuft automatisch nach jeder Episode (script_writer.generate_episode()/
generate_episode.py's imported-Zweig), genau wie generate_episode_meta —
ein Fehlschlag hier lässt die Episode NICHT scheitern (nice-to-have, wie
Titel/Beschreibung). Ohne OPENAI_API_KEY wird der Schritt übersprungen statt
abzubrechen, weil er sonst bei jedem Lauf ohne gesetzten Key die ganze
Episoden-Generierung als "fehlgeschlagen" markieren würde.

Ein einzelner Bild-PROMPT (Text) wird erzeugt und dann für BEIDE Größen an
gpt-image-1-mini geschickt — ein Claude-Call, zwei Bild-Calls.
"""

from __future__ import annotations

import os
import time

from fabrik.writing import image_backends
from fabrik.writing.script_writer import call_claude, MAX_RETRIES, RETRY_DELAY

# 1536x1024 ist die größte Querformat-Option von gpt-image-1-mini (wie
# location_prompts.py) — nicht exakt 16:9, aber die einzige verfügbare
# Landscape-Größe. 1024x1024 spiegelt cover_art.py fürs quadratische
# Podcast-Episodenbild.
IMAGE_SIZES = {"wide": "1536x1024", "square": "1024x1024"}
MAX_HOOK_CHARS = 40


def build_hook_prompt(data, episode) -> str:
    series_title = data.get("series_title", "")
    language = data.get("language", "German")
    sections_text = "\n".join(f"- {s}" for s in episode["sections"])

    return (
        f"You are a poster tagline writer for \"{series_title}\", an audio "
        f"drama podcast (dialogue language: {language}). This episode is "
        f"about {episode['figure']}.\n\n"
        f"Core theme: {episode['theme']}\n\n"
        f"The episode covers these chapters:\n{sections_text}\n\n"
        f"Write ONE short, dramatic tagline for this episode's THUMBNAIL "
        f"image — the kind of bold 2-5 word phrase you'd see on a movie "
        f"poster or a streaming-service episode tile. In {language}.\n\n"
        f"Requirements:\n"
        f"- Maximum {MAX_HOOK_CHARS} characters, no ending punctuation.\n"
        f"- Tied to this episode's specific theme/dilemma/tension — not a "
        f"generic genre phrase that could sit on any episode.\n"
        f"- Must NOT reveal or hint at the ending, the twist, or how the "
        f"theme resolves — a viewer who has only seen the thumbnail must "
        f"learn nothing about the outcome.\n"
        f"- No trivia/recall phrasing (not a question, not 'find out "
        f"what...'), just the dramatic phrase itself.\n\n"
        f"Answer with EXACTLY the tagline and nothing else — no quotation "
        f"marks, no preamble, no markdown."
    )


def build_image_prompt(data, episode, hook_text: str) -> str:
    style_guidelines = data.get("style_guidelines", "")

    return (
        f"I am producing a dramatic THUMBNAIL image for one episode of an "
        f"audio drama podcast. Episode theme: {episode['theme']}. Series "
        f"tone/style notes: {style_guidelines}\n\n"
        f"Write ONE image-generation prompt (in English — image models "
        f"work best with English prompts) for a poster-style thumbnail "
        f"that will be rendered at TWO different sizes from this same "
        f"prompt (a wide 16:9 crop and a square 1:1 crop) — keep the focal "
        f"point and the text centered enough to survive both crops, not "
        f"pushed into a corner that only one aspect ratio keeps.\n\n"
        f"Requirements:\n"
        f"- Style: masterpiece, best quality, painted lo-fi animation "
        f"style, hand-drawn texture, warm muted color palette, cinematic — "
        f"the same visual language as this show's cover art and character "
        f"portraits, so the thumbnail feels part of the same world.\n"
        f"- Find the ONE symbolic object, gesture, or moment that captures "
        f"THIS episode's specific central tension — not a generic mood "
        f"board, and not a depiction of how the episode resolves or ends. "
        f"The image may only tease the conflict, never the outcome.\n"
        f"- Must read clearly as a small thumbnail: one strong, clear "
        f"focal point, bold silhouette and composition — not a busy wide "
        f"scene full of small detail that disappears at thumbnail size.\n"
        f"- NO close-up human faces (AI-generated faces read as uncanny "
        f"at thumbnail size) — implied presence, silhouette, or a "
        f"symbolic object instead.\n"
        f"- The tagline \"{hook_text}\" must appear as bold, dramatic "
        f"movie-poster typography integrated into the composition — "
        f"placed where it stays legible at thumbnail size (e.g. lower "
        f"third, against a calm area of the image, not over busy detail), "
        f"in a typeface that matches the hand-painted lo-fi mood. Spell it "
        f"EXACTLY as given, nothing added or changed. This is the ONLY "
        f"text allowed in the image — no other words, letters, or logos "
        f"anywhere else.\n"
        f"- One paragraph, no camera jargon lists, no numbered options.\n\n"
        f"Answer with EXACTLY this and nothing else — no preamble, no "
        f"markdown, just the prompt text itself."
    )


def _generate_hook(data, episode, model) -> str | None:
    prompt = build_hook_prompt(data, episode)
    for attempt in range(1, MAX_RETRIES + 1):
        output = call_claude(prompt, model, label="Thumbnail-Hook")
        if output:
            hook = output.strip().strip('"').strip("'")
            if hook and len(hook) <= MAX_HOOK_CHARS:
                return hook
        print(f"  Versuch {attempt}/{MAX_RETRIES}: unbrauchbare Hook-Zeile.")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    return None


def generate_episode_thumbnail(series, ep_idx, data, episodes, force, cfg) -> bool:
    """Erzeugt <prefix>N_wide.png (16:9) + <prefix>N_square.png (1:1) unter
    stages/04_visuals/output/thumbnails/. Nice-to-have wie
    generate_episode_meta: ein Fehlschlag/fehlender Key lässt die Episode
    nicht scheitern."""
    episode_num = ep_idx + 1
    episode = episodes[ep_idx]
    prefix = cfg["prefix"]
    out_files = {aspect: series.thumbnail_file(prefix, episode_num, aspect)
                 for aspect in IMAGE_SIZES}

    if all(os.path.exists(p) for p in out_files.values()) and not force:
        print(f"  Thumbnails bereits vorhanden: "
              f"{', '.join(os.path.basename(p) for p in out_files.values())} ✓")
        return True

    if not image_backends.api_key_available():
        print("  OPENAI_API_KEY nicht gesetzt — Episoden-Thumbnails übersprungen "
              "(nachholbar: python3 -m fabrik.cli.episode_thumbnails --episode "
              f"{episode_num}).")
        return True

    light_model = cfg.get("light_model", cfg["model"])
    print(f"\n  Generiere Thumbnail-Hook-Zeile (Modell: {light_model}) ...")
    hook_text = _generate_hook(data, episode, light_model)
    if not hook_text:
        print("  Thumbnail-Hook fehlgeschlagen — Episoden-Thumbnails übersprungen.")
        return False
    print(f"  → \"{hook_text}\"")

    image_prompt = None
    for attempt in range(1, MAX_RETRIES + 1):
        output = call_claude(build_image_prompt(data, episode, hook_text), light_model,
                             label="Thumbnail-Bildprompt")
        if output and output.strip():
            image_prompt = output.strip()
            break
        print(f"  Versuch {attempt}/{MAX_RETRIES}: kein Bildprompt.")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    if not image_prompt:
        print("  Thumbnail-Bildprompt fehlgeschlagen — Episoden-Thumbnails übersprungen.")
        return False

    os.makedirs(series.thumbnails_dir, exist_ok=True)
    failed = []
    for aspect, size in IMAGE_SIZES.items():
        out_path = out_files[aspect]
        if os.path.exists(out_path) and not force:
            continue
        try:
            image_backends.save_image(image_prompt, out_path, size=size)
            print(f"  ✓ {aspect} ({size}) → {os.path.basename(out_path)}")
        except RuntimeError as exc:
            print(f"  ✗ {aspect} ({size}) FEHLER: {exc}")
            failed.append(aspect)

    if failed:
        print(f"  Thumbnail-Bild(er) fehlgeschlagen ({', '.join(failed)}) — "
              f"nachholbar: python3 -m fabrik.cli.episode_thumbnails --episode "
              f"{episode_num} (nur die fehlenden Größen werden nachgeholt)")
        return False
    return True
