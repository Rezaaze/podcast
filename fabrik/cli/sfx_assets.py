#!/usr/bin/env python3
"""Erzeugt die One-Shot-SFX einer Serie über ElevenLabs.

Verwendung:
  python3 -m fabrik.cli.sfx_assets                    # aktuelle Serie
  python3 -m fabrik.cli.sfx_assets --series facades
  python3 -m fabrik.cli.sfx_assets --force             # vorhandene Dateien neu generieren

Zwei Quellen, in dieser Reihenfolge:

1. SFX_PLAN.json (fabrik.cli.sfx_plan) — der NORMALFALL. Generiert wird die
   kuratierte PALETTE: pro kanonischem Asset ein Sound aus einem sauber
   geschriebenen Generierungs-Prompt statt aus dem rohen Cue-Text, mit
   geplanter Dauer. Cues, die der Plan verworfen hat, kosten hier nichts
   mehr. Läuft VOR dem Vertonen (der Plan hängt nur an den Skripten).

2. Ohne Plan: das alte Verhalten — die Cue-Beschreibungen aus den bereits
   geschriebenen <Episode>_SFX_CUES.json (also erst nach dem Vertonen
   möglich), eine Datei pro eindeutigem Cue-Text.

Beide Wege legen die Datei unter series/<slug>/stages/03_audio/output/sfx/
oneshots/<hash>.mp3 ab. <hash> = sfx_asset_hash() des Textes, der an
ElevenLabs ging (Plan: der Palette-Prompt, sonst: der Cue-Text) — mit Plan
steht derselbe Hash als "asset" in der SFX_CUES.json, ohne Plan berechnet
Lolfi ihn wie bisher selbst aus dem Cue-Text.

Braucht ELEVENLABS_API_KEY. Vor jedem API-Aufruf wird zuerst die
serienübergreifende Sound-Bibliothek (fabrik/writing/sfx_library.py) auf
einen exakten oder ähnlichen vorhandenen Sound geprüft.

Braucht kein .venv — die Generierung selbst nutzt nur stdlib (urllib).
"""

import argparse
import glob
import json
import os
import sys
import time

from fabrik.cli import sfx_plan
from fabrik.core import paths
from fabrik.core.textproc import sfx_asset_hash
from fabrik.writing import elevenlabs_backend, sfx_library

# Transiente Fehlschläge (Rate-Limit, Netzwerk) sollen nicht dieselbe
# permanente Konsequenz haben wie ein echter Prompt-Fehler (siehe
# 'before'-Lücken-Kommentar in main()) — ein zweiter Versuch kostet wenig,
# eine dauerhaft leere Stille-Lücke im fertigen Video kostet mehr.
MAX_ASSET_RETRIES = 2
ASSET_RETRY_DELAY = 5


def oneshots_dir(series):
    return os.path.join(series.output_dir, "sfx", "oneshots")


def collect_cue_descriptions(series):
    """Serienweit eindeutige Cue-Beschreibungen aus allen <Episode>_SFX_CUES.json."""
    descriptions = set()
    cue_files = sorted(glob.glob(os.path.join(series.output_dir, "*_SFX_CUES.json")))
    for cue_file in cue_files:
        with open(cue_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cue in data.get("cues", []):
            desc = cue.get("description", "").strip()
            if desc:
                descriptions.add(desc)
    return cue_files, descriptions


def jobs_from_plan(plan):
    """Palette -> [(label, prompt, dateiname_hash, dauer_s, palette_key)]. Der
    Hash kommt aus dem Plan (dort beim Schreiben aus dem Prompt berechnet) —
    er MUSS zu dem 'asset' passen, das podcast_maker in die SFX_CUES.json
    schreibt, sonst findet Lolfi die Datei nicht. palette_key wird separat
    mitgegeben (nicht nur im label eingebettet), damit der Aufrufer ihn gegen
    plan['cues'] (asset_key/placement) abgleichen kann, ohne den Label-String
    zu parsen."""
    jobs = []
    for asset in plan.get("palette", []):
        prompt = (asset.get("prompt") or "").strip()
        if not prompt or not asset.get("key"):
            continue
        jobs.append((
            f"{asset['key']} ({asset.get('cues', '?')}x)",
            prompt,
            asset.get("asset") or sfx_asset_hash(prompt),
            asset.get("duration_s"),
            asset["key"],
        ))
    return jobs


def main():
    parser = argparse.ArgumentParser(description="One-Shot-SFX einer Serie generieren (ElevenLabs)")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene SFX-Dateien neu generieren")
    paths.add_series_arg(parser)
    args = parser.parse_args()

    series = paths.resolve_series(args.series)
    plan = sfx_plan.load_plan(sfx_plan.plan_path(series))

    if plan and plan.get("palette"):
        jobs = jobs_from_plan(plan)
        is_planned = True
        kept = sum(1 for c in plan.get("cues", []) if c.get("keep"))
        dropped = len(plan.get("cues", [])) - kept
        print(f"Serie: {series.slug} — SFX-Plan gefunden: {len(jobs)} Palette-Asset(s) "
              f"für {kept} Cue(s) ({dropped} vom Plan verworfen, werden nicht generiert)")
    else:
        is_planned = False
        cue_files, descriptions = collect_cue_descriptions(series)
        if not cue_files:
            print(f"Serie '{series.slug}' hat weder einen SFX-Plan ({sfx_plan.PLAN_FILENAME} in "
                  f"{series.scripts_dir}/) noch *_SFX_CUES.json in {series.output_dir}/ — "
                  f"nichts zu tun.")
            print("  Empfohlen: 'python3 -m fabrik.cli.sfx_plan' (kuratiert Palette + "
                  "Platzierung, läuft schon vor dem Vertonen).")
            return
        if not descriptions:
            print(f"{len(cue_files)} SFX-Cue-Datei(en) gefunden, aber keine Cues darin — nichts zu tun.")
            return
        jobs = [(desc, desc, sfx_asset_hash(desc), None, None) for desc in sorted(descriptions)]
        print(f"Serie: {series.slug} — kein SFX-Plan, Alt-Pfad: {len(jobs)} eindeutige(r) "
              f"Cue-Text(e) aus {len(cue_files)} Episode(n)")
        print(f"  Tipp: 'python3 -m fabrik.cli.sfx_plan' clustert die Cues zu einer Palette "
              f"und spart die Sounds, die gar keine sind.")

    if not elevenlabs_backend.api_key_available():
        print("FEHLER: ELEVENLABS_API_KEY nicht gesetzt — 'export ELEVENLABS_API_KEY=...' vor dem Aufruf.")
        sys.exit(1)

    out_dir = oneshots_dir(series)
    os.makedirs(out_dir, exist_ok=True)

    # Palette-Keys, die mindestens einen behaltenen Cue mit placement="before"
    # bedienen — podcast_maker hat für die schon beim Vertonen eine feste
    # Stille-Lücke (300-1200ms) in die Episoden-WAV eingerechnet (siehe
    # assemble_part). Scheitert die Generierung hier, bleibt diese Lücke
    # zunächst leer — ein erneuter (erfolgreicher) sfx_assets-Lauf VOR dem
    # nächsten Lolfi-Render füllt sie nachträglich, ohne dass die Episode neu
    # vertont werden muss (die Podcast-MP3 selbst bleibt ohnehin immer ohne
    # gemischtes SFX, das war schon immer so — nur Lolfis Video mischt es ein).
    before_keys = {
        c["asset_key"] for c in (plan.get("cues", []) if is_planned else [])
        if c.get("keep") and c.get("placement") == "before" and c.get("asset_key")
    }

    generated, skipped, failed = 0, 0, []
    for label, prompt, asset_hash, duration_s, palette_key in jobs:
        out_path = os.path.join(out_dir, f"{asset_hash}.mp3")
        if os.path.exists(out_path) and not args.force:
            skipped += 1
            continue
        last_exc = None
        for attempt in range(1, MAX_ASSET_RETRIES + 1):
            try:
                # allow_fuzzy=False für geplante Palette-Assets: der SFX-Plan
                # hat schon kuratiert/geclustert, ein zusätzlicher Fuzzy-
                # Treffer kann hier nur noch falsch liegen und riskiert eine
                # Dauer-Abweichung von der geplanten duration_s (siehe
                # sfx_library.py-Docstring). Fuzzy bleibt nur im planlosen
                # Alt-Pfad an (dort gibt es keine Kurationsstufe, die
                # Gegensätze vorab trennt).
                sfx_library.resolve_or_generate(prompt, "oneshots", out_path,
                                                duration_seconds=duration_s,
                                                allow_fuzzy=not is_planned)
                print(f"  {label} → sfx/oneshots/{os.path.basename(out_path)}")
                generated += 1
                last_exc = None
                break
            except RuntimeError as exc:
                last_exc = exc
                if attempt < MAX_ASSET_RETRIES:
                    print(f"  {label}: Versuch {attempt}/{MAX_ASSET_RETRIES} fehlgeschlagen "
                          f"({exc}) — erneut ...")
                    time.sleep(ASSET_RETRY_DELAY)
        if last_exc is not None:
            print(f"  {label}: FEHLER nach {MAX_ASSET_RETRIES} Versuchen — {last_exc}")
            failed.append((label, palette_key))

    print(f"\n{generated} von {len(jobs)} Sound(s) generiert "
          f"({skipped} bereits vorhanden, {len(failed)} fehlgeschlagen).")
    if failed:
        print("Erneut starten, um Fehlgeschlagene nachzuholen (fertige werden übersprungen).")
        before_failed = [label for label, key in failed if key in before_keys]
        if before_failed:
            print(f"  ⚠️  Darunter {len(before_failed)} mit placement=\"before\" "
                  f"({', '.join(before_failed)}): die zugehörige Stille-Lücke ist bereits "
                  f"in der Episoden-Audio einvertont, aber noch ohne Sound gefüllt — "
                  f"unbedingt vor dem nächsten Lolfi-Render erneut versuchen.")


if __name__ == "__main__":
    main()
