"""episodes.json laden + vollständig validieren.

episodes.json ist die Single Source of Truth einer Serie: Inhalt, Format,
Modus, Stimmen und Audio-Konfiguration. Ziel der Validierung: Jede
fehlerhafte oder mehrdeutige Eingabe (z.B. von einer KI generiert) wird VOR
dem Start klar benannt, statt später kryptisch abzustürzen oder stumm mit
Defaults weiterzulaufen.

Neu gegenüber dem alten Ein-Serien-Layout:
  mode      "narration" (Default, Ein-Sprecher wie bisher) | "drama"
            (Multi-Voice-Skripte mit [SPRECHER]-Tags und [SFX]-Cues)
  template  Ordnername unter templates/ (Default: "narration")
  voices    nur mode=drama: Rolle → {voice, default_style, description, speed, seed}
            (seed: nur backend "rest" + geklonte Stimme, siehe VALID_VOICE_KEYS unten)
  course    optional (Sprachkurs): freie String-Felder, werden in den
            Schreib-Prompt gereicht (level, target_language_share, ...)
"""

from __future__ import annotations

import json
import os
import re
import sys

from .paths import TEMPLATES_DIR

# Fallbacks, falls episodes.json einzelne Schlüssel nicht definiert
DEFAULTS = {
    "language": "English",
    "writer_persona": "a brilliant scriptwriter for high-end documentaries",
    "style_guidelines": [],
    "mode": "narration",
    "template": "narration",
    "parts_per_section": 2,
    "words_per_part_min": 430,
    "words_per_part_max": 520,
    "words_per_part_target": "450 to 500",
    "model": "claude-sonnet-5",
    # Leichtes Modell für Nebenaufgaben (Episoden-Titel/Beschreibung, Beats-
    # und Episoden-Review): reine Extraktions-/Prüfaufgaben, die das teure
    # Schreibmodell nicht brauchen — das kreative Schreiben (Sections, Beats,
    # Part-Reparatur) bleibt auf generation.model.
    "light_model": "claude-haiku-4-5",
    "output_prefix": "figur",
    "use_beats": False,
}

VALID_MODES = {"narration", "drama"}

# Welche audio.backend-Werte "style"/"instruct"-Regieanweisungen überhaupt
# rendern (siehe fabrik/tts_backends.py-Docstrings) — script_writer.py nutzt
# das, um Style-Anweisungen erst gar nicht in den Schreib-Prompt aufzunehmen,
# wenn das konfigurierte Backend sie beim Vertonen ohnehin verwirft (spart
# Tokens + macht das Skript ehrlich). Bewusst hier statt in tts_backends.py
# definiert: dieses Modul darf KEINE schweren Abhängigkeiten (requests,
# pydub) ziehen, da generate_episode.py/create_series.py ohne .venv laufen.
# "gradio": True gilt nur für den Built-in-Speaker-Pfad (Custom Voice) —
# der Voice-Clone-Pfad derselben App ignoriert Style trotzdem (siehe
# GradioBackend-Docstring); dieselbe Ungenauigkeit nimmt "rest" schon länger
# in Kauf (dort ignoriert der Voice-Clone-Pfad Style ebenfalls).
BACKEND_SUPPORTS_STYLE = {"rest": True, "kokoro": False, "gradio": True}

# Die Built-in-Speaker der lokalen Qwen3-TTS-App (SPEAKER_MAP in deren
# webui.py/main.py). Nur Ryan/Aiden sind akzentfreie Englisch-Muttersprachler,
# alle anderen sind chinesisch-nativ — ihr Akzent ist in jeder gerenderten
# Zeile hörbar (Casting-Regeln dazu: templates/*/EPISODES_CREATOR_PROMPT.md).
# Ergänzt um das Roster der Cloud-App (GradioBackend.SPEAKERS in
# fabrik/audio/tts_backends.py, dort nicht importierbar — dieses Modul darf
# keine schweren Abhängigkeiten ziehen) — reine Vereinigungsmenge nur für
# diese Tippfehler-Warnung, keine echte Auflösung (die passiert pro Backend).
KNOWN_BUILTIN_SPEAKERS = {
    "Ryan", "Aiden", "Ethan", "Dylan", "Eric", "Uncle_Fu",
    "Chelsie", "Serena", "Vivian",
    "Ono_anna", "Sohee", "Uncle_fu",
}


def supports_style(backend_name: str) -> bool:
    return BACKEND_SUPPORTS_STYLE.get(backend_name, True)

# Erlaubte Schlüssel — unbekannte Schlüssel (z.B. KI-Tippfehler) erzeugen eine Warnung
VALID_TOP_KEYS = {
    "series_title", "language", "writer_persona", "style_guidelines",
    "format", "generation", "audio", "output_prefix",
    "series_intro", "series_outro", "episodes",
    "mode", "template", "voices", "course", "locations", "season",
}
VALID_FORMAT_KEYS = {
    "parts_per_section", "words_per_part_target",
    "words_per_part_min", "words_per_part_max",
}
VALID_GENERATION_KEYS = {"model", "light_model", "use_beats"}
VALID_AUDIO_BACKENDS = {"rest", "gradio", "kokoro"}
VALID_AUDIO_KEYS = {
    "api_url", "voice", "default_style", "target_lufs",
    "pause_between_chunks_ms", "pause_between_lines_ms",
    "pause_between_parts_ms", "pause_between_episodes_ms",
    "backend", "ref_audio", "ref_text", "model_size", "language", "chunk_gap", "chunk_max_chars",
    "model_path", "language_code", "sample_rate",  # Kokoro-spezifisch
    "merge_anthology",  # false: Episoden bleiben eigenständig, kein ANTHOLOGY_COMPLETE.mp3
    "seed",  # Default-Seed für alle Rollen ohne eigenen voices.<ROLLE>.seed (nur backend "rest" + geklonte
             # Stimmen/Prompts — siehe fabrik/audio/tts_backends.py::RestBackend, Built-in-Speaker haben
             # in dieser API keinen seed-Parameter, wird dort ignoriert)
}
VALID_EPISODE_KEYS = {
    "figure", "theme", "intro_note", "outro_note", "sections", "section_styles",
    "section_words", "section_locations", "case", "source",
}
VALID_LOCATION_KEYS = {"name", "description"}
VALID_SOURCE_VALUES = {"generated", "imported"}
VALID_SECTION_WORDS_KEYS = {"min", "max", "target"}
VALID_CASE_KEYS = {"label", "solution", "objective_facts", "character_knowledge"}
VALID_CHARACTER_KNOWLEDGE_KEYS = {"knows", "hides", "believes_falsely"}
VALID_VOICE_KEYS = {"voice", "default_style", "description", "speed", "seed"}


def load_episodes(episodes_file: str) -> dict:
    try:
        with open(episodes_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"FEHLER: episodes.json nicht gefunden: {episodes_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"FEHLER: {episodes_file} ist kein gültiges JSON.")
        print(f"  Zeile {e.lineno}, Spalte {e.colno}: {e.msg}")
        sys.exit(1)


def validate_data(data) -> tuple[list[str], list[str]]:
    """Prüft episodes.json vollständig und liefert (Fehler, Warnungen)."""
    errors: list[str] = []
    warnings: list[str] = []

    def is_int(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def is_str_list(v):
        return isinstance(v, list) and all(isinstance(s, str) and s.strip() for s in v)

    def validate_case_block(case, voices, path, require_label):
        """Prüft einen einzelnen case/thread-Block (solution/objective_facts/
        character_knowledge). Wird sowohl für ein einzelnes 'case'-Objekt
        (crime_drama: ein Fall) als auch pro Eintrag einer 'case'-Liste
        (soap_opera: mehrere parallele Handlungsstränge) aufgerufen."""
        if not isinstance(case, dict):
            errors.append(f"'{path}' muss ein Objekt sein")
            return
        for key in case:
            if key not in VALID_CASE_KEYS:
                warnings.append(f"Unbekannter Schlüssel '{path}.{key}' — wird ignoriert (Tippfehler?)")
        if require_label and (not isinstance(case.get("label"), str) or not case.get("label", "").strip()):
            errors.append(f"'{path}.label' fehlt oder ist kein nicht-leerer String "
                          f"(Name des Handlungsstrangs, z.B. 'The Affair')")
        if "solution" in case and (not isinstance(case["solution"], str) or not case["solution"].strip()):
            errors.append(f"'{path}.solution' muss ein nicht-leerer String sein")
        if "objective_facts" in case and not is_str_list(case["objective_facts"]):
            errors.append(f"'{path}.objective_facts' muss eine Liste nicht-leerer Strings sein")
        knowledge = case.get("character_knowledge")
        if knowledge is not None:
            if not isinstance(knowledge, dict):
                errors.append(f"'{path}.character_knowledge' muss ein Objekt sein (Rolle -> Wissens-Slice)")
            else:
                known_roles = set(voices) if isinstance(voices, dict) else set()
                for role, slice_ in knowledge.items():
                    if known_roles and role not in known_roles:
                        errors.append(
                            f"'{path}.character_knowledge.{role}' referenziert eine Rolle, "
                            f"die nicht in 'voices' definiert ist"
                        )
                    if not isinstance(slice_, dict):
                        errors.append(f"'{path}.character_knowledge.{role}' muss ein Objekt sein")
                        continue
                    for key in slice_:
                        if key not in VALID_CHARACTER_KNOWLEDGE_KEYS:
                            warnings.append(
                                f"Unbekannter Schlüssel '{path}.character_knowledge.{role}.{key}' "
                                f"— wird ignoriert (Tippfehler?)"
                            )
                    for key in VALID_CHARACTER_KNOWLEDGE_KEYS:
                        if key in slice_ and not is_str_list(slice_[key]):
                            errors.append(
                                f"'{path}.character_knowledge.{role}.{key}' muss eine Liste "
                                f"nicht-leerer Strings sein"
                            )
                if known_roles:
                    # NARRATOR (siehe templates/crime_drama, templates/soap_opera) ist keine
                    # Figur mit eigenem Wissen — braucht bewusst kein character_knowledge-Slice.
                    missing_roles = known_roles - set(knowledge) - {"NARRATOR"}
                    if missing_roles:
                        warnings.append(
                            f"'{path}.character_knowledge' hat keinen Eintrag für "
                            f"{sorted(missing_roles)} — diese Rollen bekommen kein Wissens-Slice "
                            f"und werden im Prompt wie unbeschränkt wissend behandelt"
                        )

    if not isinstance(data, dict):
        return ["Top-Level von episodes.json muss ein JSON-Objekt sein"], []

    for key in data:
        if key not in VALID_TOP_KEYS:
            warnings.append(f"Unbekannter Schlüssel '{key}' — wird ignoriert (Tippfehler?)")

    # --- Top-Level-Strings ---
    if not isinstance(data.get("series_title"), str) or not data.get("series_title", "").strip():
        errors.append("'series_title' fehlt oder ist kein nicht-leerer String")
    for key in ("language", "writer_persona", "series_intro", "series_outro"):
        if key in data and (not isinstance(data[key], str) or not data[key].strip()):
            errors.append(f"'{key}' muss ein nicht-leerer String sein")

    prefix = data.get("output_prefix")
    if prefix is not None:
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
            errors.append("'output_prefix' muss ein String aus Buchstaben, Zahlen, '-' oder '_' sein (wird Teil der Dateinamen)")

    # "season": optional, nur für Serien, die bewusst als Staffel eines
    # Mehr-Staffel-Podcast-Kanals veröffentlicht werden (siehe UPLOAD_INDEX.md/
    # ID3-Titel-Formatierung in batch.py/podcast_maker.py) — ohne dieses Feld
    # bleibt der Episodentitel unverändert wie bisher.
    if "season" in data and (not is_int(data["season"]) or data["season"] < 1):
        errors.append("'season' muss eine positive ganze Zahl sein (Staffelnummer für den Podcast-Kanal)")

    if "style_guidelines" in data and not is_str_list(data["style_guidelines"]):
        errors.append("'style_guidelines' muss eine Liste nicht-leerer Strings sein")

    # --- mode / template / voices / course ---
    mode = data.get("mode", DEFAULTS["mode"])
    if mode not in VALID_MODES:
        errors.append(f"'mode' muss eines von {sorted(VALID_MODES)} sein (ist: '{mode}')")
        mode = "narration"

    template = data.get("template", DEFAULTS["template"])
    if not isinstance(template, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", template or ""):
        errors.append("'template' muss ein Ordnername unter templates/ sein (Buchstaben, Zahlen, '-', '_')")
    elif not os.path.isdir(os.path.join(TEMPLATES_DIR, template)):
        errors.append(f"'template': templates/{template}/ existiert nicht")

    voices = data.get("voices")
    if mode == "drama":
        if not isinstance(voices, dict) or not voices:
            errors.append("mode 'drama' braucht 'voices': {ROLLE: {voice, default_style, description}, ...}")
            voices = {}
        for role, vcfg in voices.items():
            if not re.fullmatch(r"[A-Za-z0-9_]+", role):
                errors.append(f"'voices.{role}': Rollenname muss zu [A-Za-z0-9_]+ passen "
                              f"(wird als Sprecher-Tag [{role}] im Skript verwendet)")
            if not isinstance(vcfg, dict):
                errors.append(f"'voices.{role}' muss ein Objekt sein")
                continue
            for key in vcfg:
                if key not in VALID_VOICE_KEYS:
                    warnings.append(f"Unbekannter Schlüssel 'voices.{role}.{key}' — wird ignoriert (Tippfehler?)")
            if not isinstance(vcfg.get("voice"), str) or not vcfg.get("voice", "").strip():
                errors.append(f"'voices.{role}.voice' fehlt oder ist kein nicht-leerer String (Qwen3-Speaker-Name)")
            elif vcfg["voice"].strip() not in KNOWN_BUILTIN_SPEAKERS:
                warnings.append(
                    f"'voices.{role}.voice' = '{vcfg['voice']}' ist kein bekannter Built-in-Speaker "
                    f"des lokalen Qwen3-Servers ({', '.join(sorted(KNOWN_BUILTIN_SPEAKERS))}) — "
                    f"ok, falls es ein Voice-Clone ist, sonst Tippfehler")
            for key in ("default_style", "description"):
                if key in vcfg and (not isinstance(vcfg[key], str) or not vcfg[key].strip()):
                    errors.append(f"'voices.{role}.{key}' muss ein nicht-leerer String sein")
            if "speed" in vcfg and (not is_num(vcfg["speed"]) or not (0.5 <= vcfg["speed"] <= 2.0)):
                errors.append(f"'voices.{role}.speed' muss eine Zahl zwischen 0.5 und 2.0 sein")
            if "seed" in vcfg:
                if not is_int(vcfg["seed"]) or vcfg["seed"] < 0:
                    errors.append(f"'voices.{role}.seed' muss eine ganze Zahl >= 0 sein")
                elif isinstance(vcfg.get("voice"), str) and vcfg["voice"].strip() in KNOWN_BUILTIN_SPEAKERS:
                    warnings.append(
                        f"'voices.{role}.seed' ist gesetzt, aber '{vcfg['voice']}' ist ein Built-in-Speaker — "
                        f"der lokale Qwen3-Server bietet für Built-in-Speaker keinen seed-Parameter an, "
                        f"'seed' wirkt nur bei geklonten Stimmen (Voice-Clone-Prompts)"
                    )

        # Zwei Rollen mit derselben Stimme klingen für den Hörer ununterscheidbar
        # (bei geklonten Stimmen sogar identisch) — das ist immer ein Fehler,
        # nie beabsichtigt (siehe Stimmen-Konsistenz-Anforderung).
        roles_by_voice = {}
        for role, vcfg in voices.items():
            if isinstance(vcfg, dict) and isinstance(vcfg.get("voice"), str) and vcfg["voice"].strip():
                roles_by_voice.setdefault(vcfg["voice"].strip(), []).append(role)
        for voice_name, roles in roles_by_voice.items():
            if len(roles) > 1:
                errors.append(f"Stimme '{voice_name}' ist mehreren Rollen zugewiesen "
                              f"({', '.join(sorted(roles))}) — jede Rolle braucht eine eigene Stimme, "
                              f"sonst sind die Charaktere für den Hörer nicht unterscheidbar")
    elif voices:
        warnings.append("'voices' ist gesetzt, aber mode ist 'narration' — wird ignoriert")

    course = data.get("course")
    if course is not None:
        if not isinstance(course, dict):
            errors.append("'course' muss ein Objekt aus String-Feldern sein")
        else:
            for key, value in course.items():
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"'course.{key}' muss ein nicht-leerer String sein")

    # --- locations (optional, modusunabhängig) — wiederverwendbare Szenen-Orte
    # für die ganze Serie, per Kürzel aus episodes[n].section_locations referenziert ---
    locations = data.get("locations")
    if locations is not None:
        if not isinstance(locations, dict) or not locations:
            errors.append("'locations' muss ein nicht-leeres Objekt {ORT_KEY: {name, description}, ...} sein")
            locations = {}
        for key, lcfg in locations.items():
            if not re.fullmatch(r"[A-Za-z0-9_]+", key):
                errors.append(f"'locations.{key}': Key muss zu [A-Za-z0-9_]+ passen")
            if not isinstance(lcfg, dict):
                errors.append(f"'locations.{key}' muss ein Objekt sein")
                continue
            for k in lcfg:
                if k not in VALID_LOCATION_KEYS:
                    warnings.append(f"Unbekannter Schlüssel 'locations.{key}.{k}' — wird ignoriert (Tippfehler?)")
            for k in ("name", "description"):
                if not isinstance(lcfg.get(k), str) or not lcfg.get(k, "").strip():
                    errors.append(f"'locations.{key}.{k}' fehlt oder ist kein nicht-leerer String")

    # --- format ---
    fmt = data.get("format", {})
    if not isinstance(fmt, dict):
        errors.append("'format' muss ein Objekt sein")
        fmt = {}
    for key in fmt:
        if key not in VALID_FORMAT_KEYS:
            warnings.append(f"Unbekannter Schlüssel 'format.{key}' — wird ignoriert (Tippfehler?)")
    pps = fmt.get("parts_per_section", DEFAULTS["parts_per_section"])
    if not is_int(pps) or pps < 1:
        errors.append("'format.parts_per_section' muss eine ganze Zahl >= 1 sein")
    min_w = fmt.get("words_per_part_min", DEFAULTS["words_per_part_min"])
    max_w = fmt.get("words_per_part_max", DEFAULTS["words_per_part_max"])
    if not is_int(min_w) or min_w < 1:
        errors.append("'format.words_per_part_min' muss eine ganze Zahl >= 1 sein")
    if not is_int(max_w) or max_w < 1:
        errors.append("'format.words_per_part_max' muss eine ganze Zahl >= 1 sein")
    if is_int(min_w) and is_int(max_w) and min_w >= max_w:
        errors.append(f"'format.words_per_part_min' ({min_w}) muss kleiner als 'format.words_per_part_max' ({max_w}) sein")
    if "words_per_part_target" in fmt and (not isinstance(fmt["words_per_part_target"], str) or not fmt["words_per_part_target"].strip()):
        errors.append("'format.words_per_part_target' muss ein nicht-leerer String sein (z.B. \"450 to 500\")")

    # --- generation ---
    gen = data.get("generation", {})
    if not isinstance(gen, dict):
        errors.append("'generation' muss ein Objekt sein")
        gen = {}
    for key in gen:
        if key not in VALID_GENERATION_KEYS:
            warnings.append(f"Unbekannter Schlüssel 'generation.{key}' — wird ignoriert (Tippfehler?)")
    if "model" in gen and (not isinstance(gen["model"], str) or not gen["model"].strip()):
        errors.append("'generation.model' muss ein nicht-leerer String sein")
    if "light_model" in gen and (not isinstance(gen["light_model"], str) or not gen["light_model"].strip()):
        errors.append("'generation.light_model' muss ein nicht-leerer String sein")
    if "use_beats" in gen and not isinstance(gen["use_beats"], bool):
        errors.append("'generation.use_beats' muss ein Bool sein")

    # --- audio ---
    audio = data.get("audio", {})
    if not isinstance(audio, dict):
        errors.append("'audio' muss ein Objekt sein")
        audio = {}
    for key in audio:
        if key not in VALID_AUDIO_KEYS:
            warnings.append(f"Unbekannter Schlüssel 'audio.{key}' — wird ignoriert (Tippfehler?)")
    for key in ("voice", "default_style"):
        if key in audio and (not isinstance(audio[key], str) or not audio[key].strip()):
            errors.append(f"'audio.{key}' muss ein nicht-leerer String sein")
    if "api_url" in audio and (not isinstance(audio["api_url"], str)
                               or not re.match(r"https?://", audio["api_url"])):
        errors.append("'audio.api_url' muss eine URL sein (z.B. \"http://127.0.0.1:42003\")")
    if "target_lufs" in audio and not is_num(audio["target_lufs"]):
        errors.append("'audio.target_lufs' muss eine Zahl sein (z.B. -16.0)")
    for key in ("pause_between_chunks_ms", "pause_between_lines_ms",
                "pause_between_parts_ms", "pause_between_episodes_ms"):
        if key in audio and (not is_int(audio[key]) or audio[key] < 0):
            errors.append(f"'audio.{key}' muss eine ganze Zahl >= 0 sein (Millisekunden)")
    if "chunk_max_chars" in audio and (not is_int(audio["chunk_max_chars"]) or audio["chunk_max_chars"] < 1):
        errors.append("'audio.chunk_max_chars' muss eine ganze Zahl >= 1 sein")
    if "seed" in audio:
        if not is_int(audio["seed"]) or audio["seed"] < 0:
            errors.append("'audio.seed' muss eine ganze Zahl >= 0 sein")
        elif audio.get("backend", "rest") != "rest":
            warnings.append(
                f"'audio.seed' ist gesetzt, aber 'audio.backend' ist '{audio.get('backend', 'rest')}' — "
                f"seed wird aktuell nur vom backend 'rest' (Qwen3-TTS-MLX) für geklonte Stimmen genutzt, "
                f"hier also ignoriert"
            )
    if "backend" in audio and audio["backend"] not in VALID_AUDIO_BACKENDS:
        errors.append(f"'audio.backend' muss eines von {sorted(VALID_AUDIO_BACKENDS)} sein "
                      f"(ist: '{audio['backend']}')")
    if "sample_rate" in audio and (not is_int(audio["sample_rate"]) or audio["sample_rate"] < 1):
        errors.append("'audio.sample_rate' muss eine ganze Zahl >= 1 sein (Kokoro, z.B. 24000)")
    # --- episodes ---
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        errors.append("'episodes' fehlt oder ist keine nicht-leere Liste")
        episodes = []

    section_counts = set()
    for i, ep in enumerate(episodes):
        path = f"episodes[{i}]"
        if not isinstance(ep, dict):
            errors.append(f"'{path}' muss ein Objekt sein")
            continue
        for key in ep:
            if key not in VALID_EPISODE_KEYS:
                warnings.append(f"Unbekannter Schlüssel '{path}.{key}' — wird ignoriert (Tippfehler?)")
        for key in ("figure", "theme"):
            if not isinstance(ep.get(key), str) or not ep.get(key, "").strip():
                errors.append(f"'{path}.{key}' fehlt oder ist kein nicht-leerer String")
        for key in ("intro_note", "outro_note"):
            if key in ep and not isinstance(ep[key], str):
                errors.append(f"'{path}.{key}' muss ein String sein (leerer String \"\" = keine Vorgabe)")

        if "source" in ep and ep["source"] not in VALID_SOURCE_VALUES:
            errors.append(f"'{path}.source' muss eines von {sorted(VALID_SOURCE_VALUES)} sein "
                          f"(ist: '{ep['source']}') — 'imported' markiert von import_story.py "
                          f"bereits geschriebene Skripte, die generate_episode.py überspringen soll")

        secs = ep.get("sections")
        if not is_str_list(secs) or not secs:
            errors.append(f"'{path}.sections' fehlt oder ist keine nicht-leere Liste von Strings")
            continue
        section_counts.add(len(secs))

        styles = ep.get("section_styles")
        if styles is not None:
            if mode == "drama":
                warnings.append(f"'{path}.section_styles' wird in mode 'drama' ignoriert — "
                                f"Styles stehen dort pro Zeile im Skript ([ROLLE | style: ...])")
            elif not is_str_list(styles):
                errors.append(f"'{path}.section_styles' muss eine Liste nicht-leerer Strings sein")
            elif len(styles) != len(secs):
                errors.append(
                    f"'{path}.section_styles' hat {len(styles)} Einträge, aber es gibt "
                    f"{len(secs)} Sections — pro Section genau ein Style"
                )
        elif mode == "narration":
            warnings.append(f"'{path}.section_styles' fehlt — alle Parts bekommen den audio.default_style")

        section_words = ep.get("section_words")
        if section_words is not None:
            if not isinstance(section_words, list) or len(section_words) != len(secs):
                errors.append(
                    f"'{path}.section_words' muss eine Liste mit {len(secs)} Einträgen sein "
                    f"(einer pro Section, 'null' = format-Default verwenden)"
                )
            else:
                for j, sw in enumerate(section_words):
                    swpath = f"{path}.section_words[{j}]"
                    if sw is None:
                        continue
                    if not isinstance(sw, dict):
                        errors.append(f"'{swpath}' muss ein Objekt ({{min, max, target}}) oder 'null' sein")
                        continue
                    for key in sw:
                        if key not in VALID_SECTION_WORDS_KEYS:
                            warnings.append(f"Unbekannter Schlüssel '{swpath}.{key}' — wird ignoriert (Tippfehler?)")
                    sw_min, sw_max = sw.get("min"), sw.get("max")
                    if "min" in sw and (not is_int(sw_min) or sw_min < 1):
                        errors.append(f"'{swpath}.min' muss eine ganze Zahl >= 1 sein")
                    if "max" in sw and (not is_int(sw_max) or sw_max < 1):
                        errors.append(f"'{swpath}.max' muss eine ganze Zahl >= 1 sein")
                    if is_int(sw_min) and is_int(sw_max) and sw_min >= sw_max:
                        errors.append(f"'{swpath}.min' ({sw_min}) muss kleiner als '{swpath}.max' ({sw_max}) sein")
                    if "target" in sw and (not isinstance(sw["target"], str) or not sw["target"].strip()):
                        errors.append(f"'{swpath}.target' muss ein nicht-leerer String sein (z.B. \"150 to 250\")")

        section_locations = ep.get("section_locations")
        if section_locations is not None:
            if not isinstance(section_locations, list) or len(section_locations) != len(secs):
                errors.append(
                    f"'{path}.section_locations' muss eine Liste mit {len(secs)} Einträgen sein "
                    f"(einer pro Section, 'null' = kein Orts-Wechsel/Hintergrund bleibt wie zuvor)"
                )
            elif not locations:
                errors.append(f"'{path}.section_locations' ist gesetzt, aber es gibt keine 'locations' "
                              f"auf oberster Ebene, aus denen die Keys stammen könnten")
            else:
                for j, loc_key in enumerate(section_locations):
                    if loc_key is None:
                        continue
                    if not isinstance(loc_key, str) or loc_key not in locations:
                        errors.append(f"'{path}.section_locations[{j}]' = '{loc_key}' ist kein Key aus "
                                      f"'locations' ({', '.join(sorted(locations))})")

        case = ep.get("case")
        if case is not None:
            if isinstance(case, list):
                if not case:
                    errors.append(f"'{path}.case' ist eine leere Liste — mindestens ein Handlungsstrang nötig")
                for j, thread in enumerate(case):
                    validate_case_block(thread, voices, f"{path}.case[{j}]", require_label=True)
            else:
                validate_case_block(case, voices, f"{path}.case", require_label=False)
        elif mode == "drama" and data.get("template") in ("crime_drama", "soap_opera"):
            warnings.append(f"'{path}.case' fehlt — ohne Wissens-Trennung schreibt Claude alle "
                            f"Figuren ohne echte Wissensgrenzen (siehe templates/{data.get('template')})")

    if len(section_counts) > 1:
        warnings.append(
            f"Episoden haben unterschiedlich viele Sections ({sorted(section_counts)}) — "
            f"die Episoden werden dadurch unterschiedlich lang"
        )

    return errors, warnings


def validate_or_exit(data):
    """Druckt alle Warnungen/Fehler; bricht bei Fehlern ab, bevor etwas Teures startet."""
    errors, warnings = validate_data(data)
    for w in warnings:
        print(f"WARNUNG: {w}")
    if errors:
        print(f"\nFEHLER: episodes.json hat {len(errors)} Problem(e):")
        for e in errors:
            print(f"  - {e}")
        print("\nBitte episodes.json korrigieren und erneut starten.")
        sys.exit(1)


def build_config(data) -> dict:
    """Extrahiert die Format-/Generierungs-Konfiguration aus episodes.json."""
    fmt = data.get("format", {})
    gen = data.get("generation", {})
    return {
        "language": data.get("language", DEFAULTS["language"]),
        "persona": data.get("writer_persona", DEFAULTS["writer_persona"]),
        "style_guidelines": data.get("style_guidelines", DEFAULTS["style_guidelines"]),
        "mode": data.get("mode", DEFAULTS["mode"]),
        "template": data.get("template", DEFAULTS["template"]),
        "voices": data.get("voices", {}),
        "course": data.get("course", {}),
        "locations": data.get("locations", {}),
        "parts_per_section": fmt.get("parts_per_section", DEFAULTS["parts_per_section"]),
        "min_words": fmt.get("words_per_part_min", DEFAULTS["words_per_part_min"]),
        "max_words": fmt.get("words_per_part_max", DEFAULTS["words_per_part_max"]),
        "words_target": fmt.get("words_per_part_target", DEFAULTS["words_per_part_target"]),
        "model": gen.get("model", DEFAULTS["model"]),
        "light_model": gen.get("light_model", DEFAULTS["light_model"]),
        "use_beats": gen.get("use_beats", DEFAULTS["use_beats"]),
        "prefix": data.get("output_prefix", DEFAULTS["output_prefix"]),
        # Ob das konfigurierte TTS-Backend style/instruct-Regieanweisungen
        # überhaupt rendert — steuert, ob script_writer.py Style-Anweisungen
        # in den Schreib-Prompt aufnimmt (spart Tokens, wenn nicht).
        "supports_style": supports_style(data.get("audio", {}).get("backend", "rest")),
    }
