#!/usr/bin/env python3
"""Erzeugt Ambience-Loops für die wiederverwendbaren Szenen-Orte einer
Serie über ElevenLabs — das Audio-Gegenstück zu location_prompts.py.

Verwendung:
  python3 -m fabrik.cli.location_ambience                    # aktuelle Serie
  python3 -m fabrik.cli.location_ambience --series facades
  python3 -m fabrik.cli.location_ambience --force             # vorhandene Dateien neu generieren

Zwei Ebenen, beide landen unter
series/<slug>/stages/03_audio/output/sfx/ambience/:

1. <ORT_KEY>.mp3 — die Basis-Schleife jedes Orts aus dem top-level
   "locations"-Mapping. Sie ist der FALLBACK: Lolfi nimmt sie, wenn eine
   Szene keine geplante Stimmungs-Variante hat (Serie ohne SFX-Plan, oder
   eine Episode, die der Plan nicht erfasst hat).

2. <ORT_KEY>__<mood>.mp3 — die Stimmungs-Varianten aus dem SFX-Plan
   (fabrik.cli.sfx_plan, Abschnitt "ambience"). Vorher hatte jeder Ort
   EINE Schleife für die ganze Serie: ein stilles Frühstück und eine
   Mitternachts-Eskalation im selben Raum klangen identisch. Der Plan
   weist jeder Szene eine Variante zu; Lolfi lädt sie über den Key aus der
   Location-Timeline (<Episode>_LOCATIONS.json, Feld "ambience").

Lolfi wechselt die Hintergrund-Ambience automatisch an den Grenzen dieser
Timeline (dieselbe wie beim Hintergrundbild-Wechsel) und blendet über.

Braucht ELEVENLABS_API_KEY. Vor jedem API-Aufruf wird zuerst die
serienübergreifende Sound-Bibliothek (fabrik/writing/sfx_library.py) auf
einen exakten oder ähnlichen vorhandenen Track geprüft.

Braucht kein .venv — die Generierung selbst nutzt nur stdlib (urllib).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from fabrik.cli import sfx_plan
from fabrik.core import config, paths
from fabrik.writing import elevenlabs_backend, sfx_library

# 10s waren hörbar repetitiv — bei einer 4-Minuten-Szene wiederholt sich die
# Schleife 24-mal, und jede Unregelmäßigkeit darin wird zum Metronom. 20s ist
# das, was die ElevenLabs-Sound-API in einem Rutsch liefert (Obergrenze 22s).
AMBIENCE_GEN_DURATION_SECONDS = 20.0

# ElevenLabs' Sound-Generation-API garantiert KEINEN nahtlosen Loop-Punkt —
# Anfang und Ende des generierten Clips können in Amplitude/Phase
# auseinanderlaufen. Lolfi tiled die Datei per ffmpeg -stream_loop, jede
# Szene länger als AMBIENCE_GEN_DURATION_SECONDS klickt/springt an dieser
# Nahtstelle hörbar, alle 20s erneut. _make_loop_seamless() faltet das Ende
# des Clips per Crossfade in den Anfang, BEVOR die Datei gespeichert wird —
# einmalig bei der Generierung, nicht bei jedem Lolfi-Render neu.
LOOP_CROSSFADE_SECONDS = 1.5
FFMPEG_TIMEOUT_SECONDS = 60


def _probe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    return float(result.stdout.strip())


def _make_loop_seamless(audio_bytes: bytes, crossfade_s: float = LOOP_CROSSFADE_SECONDS) -> bytes:
    """Faltet die letzten crossfade_s Sekunden per Crossfade in den Anfang
    des Clips — das Ergebnis ist um crossfade_s KÜRZER als das Original
    (die "Schwanz"-Energie steckt jetzt im Kopf statt angehängt zu sein),
    klingt aber beim -stream_loop-Tiling nahtlos an der alten Schnittstelle,
    weil Ende und Anfang jetzt sanft ineinander übergehen statt hart
    aufeinanderzutreffen. Bei jedem Fehler (ffmpeg/ffprobe fehlt, Clip zu
    kurz, kaputtes Audio) wird still auf die unveränderten Original-Bytes
    zurückgefallen — kein nahtloser Loop ist besser als gar kein Sound."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("  WARNUNG: ffmpeg/ffprobe nicht gefunden — Loop-Nahtlos-Behandlung übersprungen.")
        return audio_bytes
    with tempfile.TemporaryDirectory() as tmp_dir:
        in_path = os.path.join(tmp_dir, "in.mp3")
        out_path = os.path.join(tmp_dir, "out.mp3")
        with open(in_path, "wb") as f:
            f.write(audio_bytes)
        try:
            duration = _probe_duration(in_path)
            if duration <= 2 * crossfade_s:
                return audio_bytes  # zu kurz für eine sinnvolle Überblendung
            x = crossfade_s
            # WICHTIG: asetpts VOR afade bei [tail] — atrim() lässt die
            # ursprünglichen (absoluten) Timestamps stehen, afade's st=0
            # bezieht sich aber auf den PTS-Nullpunkt. Ohne den Reset zuerst
            # läge das Fade-Fenster [0, x] weit VOR dem tatsächlichen
            # PTS-Bereich des getrimmten Tail-Segments — afade hätte das als
            # "schon lange durchgefadet", also Stille, interpretiert (leerer
            # Sample-Anfang, empirisch verifiziert). normalize=0 auf amix wie
            # bei Lolfis eigenem Ambience-Mix (render.py) — amix' Default
            # würde die gemischte Kopf-Hälfte sonst gegenüber dem
            # unvermischten Rest halbieren, ein Pegel-Sprung an der Naht.
            filter_complex = (
                f"[0:a]atrim=0:{x},afade=t=in:st=0:d={x}[head];"
                f"[0:a]atrim={duration - x}:{duration},asetpts=PTS-STARTPTS,"
                f"afade=t=out:st=0:d={x}[tail];"
                f"[head][tail]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[blendedhead];"
                f"[0:a]atrim={x}:{duration - x},asetpts=PTS-STARTPTS[middle];"
                f"[blendedhead][middle]concat=n=2:v=0:a=1[out]"
            )
            subprocess.run(
                ["ffmpeg", "-y", "-i", in_path, "-filter_complex", filter_complex,
                 "-map", "[out]", out_path],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS,
            )
            with open(out_path, "rb") as f:
                seamless = f.read()
            if not seamless:
                raise RuntimeError("ffmpeg lieferte eine leere Ausgabedatei.")
            return seamless
        except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as exc:
            print(f"  WARNUNG: Loop-Nahtlos-Behandlung fehlgeschlagen ({exc}) — "
                  f"Datei bleibt mit hartem Loop-Punkt.")
            return audio_bytes

# Was jede Ambience-Generierung braucht, egal ob Basis oder Variante: ein
# Loop ohne Einzelereignisse — ein einzelner Türknall IN der Schleife knallt
# alle 20 Sekunden erneut und verrät sie sofort. Bleibt beim Kappen
# (elevenlabs_backend.fit_prompt) IMMER unangetastet — die Anti-Metronom/
# Anti-Einzelereignis-Regel darin ist der wichtigste Teil jedes Loop-Prompts.
LOOP_SUFFIX = ("seamless continuous background ambience loop, steady room tone, "
               "no music, no voices, no speech, no discrete events, no sudden bangs")


def ambience_dir(series):
    return os.path.join(series.output_dir, "sfx", "ambience")


def collect_locations(data):
    return data.get("locations", {})


def build_ambience_prompt(lcfg):
    name = lcfg.get("name", "")
    desc = lcfg.get("description", "")
    base = f"{name} — {desc}" if name else desc
    return elevenlabs_backend.fit_prompt(base, suffix=LOOP_SUFFIX)


def main():
    parser = argparse.ArgumentParser(description="Ambience-Loops für die Szenen-Orte einer Serie (ElevenLabs)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene Ambience-Dateien neu generieren")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    data = config.load_episodes(series.episodes_file)
    config.validate_or_exit(data)

    locations = collect_locations(data)
    if not locations:
        print(f"Serie '{series.slug}' hat kein 'locations'-Mapping in episodes.json — "
              f"nichts zu tun (nur Templates mit Location-Unterstützung, z.B. soap_opera, "
              f"legen dieses Feld an).")
        return

    if not elevenlabs_backend.api_key_available():
        print("FEHLER: ELEVENLABS_API_KEY nicht gesetzt — 'export ELEVENLABS_API_KEY=...' vor dem Aufruf.")
        sys.exit(1)

    out_dir = ambience_dir(series)
    os.makedirs(out_dir, exist_ok=True)

    # Jobs = Basis-Schleife pro Ort (Fallback) + geplante Stimmungs-Varianten.
    jobs = [(key, build_ambience_prompt(lcfg), "Basis")
            for key, lcfg in locations.items()]

    plan = sfx_plan.load_plan(sfx_plan.plan_path(series))
    variants = sfx_plan.ambience_variants(plan)
    for var in variants:
        if var["location"] not in locations:
            print(f"  WARNUNG: Variante '{var['key']}' zeigt auf unbekannten Ort "
                  f"'{var['location']}' — übersprungen.")
            continue
        if var["key"] in locations:
            # Key = Dateiname: ein Varianten-Key, der einem Orts-Key gleicht,
            # würde dessen Basis-Fallback-Schleife überschreiben. sfx_plan
            # validiert das Format inzwischen, alte Pläne evtl. noch nicht.
            print(f"  WARNUNG: Varianten-Key '{var['key']}' kollidiert mit einem "
                  f"Orts-Key — übersprungen (würde die Basis-Schleife überschreiben).")
            continue
        jobs.append((var["key"], elevenlabs_backend.fit_prompt(var["prompt"], suffix=LOOP_SUFFIX),
                     f"{var['location']} · {var.get('mood', '')}"))

    print(f"Serie: {series.slug} — {len(locations)} Ort(e): {', '.join(locations)}")
    if variants:
        print(f"SFX-Plan gefunden: {len(variants)} Stimmungs-Variante(n) zusätzlich zu den "
              f"Basis-Schleifen")
    else:
        print("Kein SFX-Plan (oder kein Ambience-Teil darin) — nur eine Schleife pro Ort. "
              "Tipp: 'python3 -m fabrik.cli.sfx_plan' plant Stimmungs-Varianten pro Szene.")

    failed = []
    for key, prompt, label in jobs:
        out_path = os.path.join(out_dir, f"{key}.mp3")
        if os.path.exists(out_path) and not args.force:
            print(f"  {key}: übersprungen (existiert bereits)")
            continue
        try:
            # allow_fuzzy=False: Basis-Loop und Stimmungs-Varianten teilen
            # sich sonst einen Fuzzy-Pool ohne Trennung nach Stimmung — eine
            # ruhige Basis-Ambience könnte fälschlich mit einer angespannten
            # Variante desselben (oder eines anderen) Orts verschmelzen, da
            # beide Prompts naturgemäß viel Orts-Vokabular teilen. Anders als
            # bei One-Shot-SFX gibt es hier keinen "planlosen Alt-Pfad" —
            # jede Ambience-Generierung ist bereits kuratiert (Orts-
            # description oder SFX-Plan-Variante), Fuzzy bringt nur Risiko.
            sfx_library.resolve_or_generate(prompt, "ambience", out_path,
                                            duration_seconds=AMBIENCE_GEN_DURATION_SECONDS,
                                            allow_fuzzy=False,
                                            post_process=_make_loop_seamless)
            print(f"  {key} ({label}): gespeichert → sfx/ambience/{key}.mp3")
        except RuntimeError as exc:
            print(f"  {key}: FEHLER — {exc}")
            failed.append(key)

    if failed:
        print(f"\n{len(failed)} Ambience-Track(s) fehlgeschlagen ({', '.join(failed)}) — "
              f"Skript erneut starten (fertige Dateien werden übersprungen).")


if __name__ == "__main__":
    main()
