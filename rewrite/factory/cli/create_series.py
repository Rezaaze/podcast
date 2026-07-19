"""Entry-Point: echte Serie erzeugen (Stage A + B) mit dem Anthropic-Provider.

    python3 -m factory.cli.create_series "Topic" [--slug S] [--format F] [--series-root DIR]

Verdrahtet den echten AnthropicModel-Adapter (§10.8) mit der getesteten Pipeline
(run_concept → run_scripts). Stage C (Vertonung) läuft NICHT hier — die braucht den
venv/TTS-Pfad; nach diesem Lauf steht das Series-Record + die Skripte im Workspace.

Voraussetzung: `pip install anthropic` + Credentials (ANTHROPIC_API_KEY oder `ant auth login`).
"""

from __future__ import annotations

import argparse
import os
import re
import sys


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "series"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Erzeuge eine Serie (Concept + Skripte).")
    parser.add_argument("topic")
    parser.add_argument("--slug", default=None)
    parser.add_argument("--format", default="crime_drama")
    parser.add_argument("--language", default="en")
    parser.add_argument("--mode", default="drama")
    parser.add_argument("--series-root", default="data/series")
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--episodes", type=int, default=None,
                        help="Ziel-Staffellänge (Arc-Tier). Weglassen = Modell wählt.")
    parser.add_argument("--minutes", type=int, default=None,
                        help="Ziel-Spielzeit pro Episode. Weglassen = Modell wählt.")
    parser.add_argument(
        "--provider", choices=["cli", "sdk"], default="cli",
        help="cli = `claude` CLI (Abo-Auth, kein API-Key); sdk = anthropic SDK (API-Billing).",
    )
    args = parser.parse_args(argv)

    # Importe erst hier, damit --help ohne Provider-Deps funktioniert.
    from factory.core.checkpoint import CheckpointStore
    from factory.core.state import StateStore
    from factory.core.workspace import reserve_series, set_latest, SlugCollision
    from factory.authoring.conceive import ConceiveConfig
    from factory.orchestration.pipeline import PipelineContext, run_concept, run_scripts

    slug = args.slug or _slugify(args.topic)
    try:
        ws = reserve_series(args.series_root, slug)
    except SlugCollision:
        print(f"Slug {slug!r} existiert bereits — anderen --slug wählen.", file=sys.stderr)
        return 2
    set_latest(args.series_root, slug)

    try:
        if args.provider == "cli":
            from factory.providers.claude_cli_model import ClaudeCliModel
            model = ClaudeCliModel()
        else:
            from factory.providers.anthropic_model import AnthropicModel
            model = AnthropicModel(max_tokens=args.max_tokens)
    except Exception as exc:  # Provider-Dep fehlt oder keine Credentials
        hint = ("`claude` CLI muss installiert + eingeloggt sein (`claude` / Abo)."
                if args.provider == "cli"
                else "`pip install anthropic` + Credentials (API-Key / `ant auth login`).")
        print(f"Kein Modell verfügbar ({exc}). {hint}", file=sys.stderr)
        return 3

    state = StateStore(os.path.join(ws.path, ".state"))
    checkpoints = CheckpointStore(os.path.join(ws.path, ".checkpoints"))
    ctx = PipelineContext(workspace=ws, model=model, state=state, checkpoints=checkpoints)

    cfg = ConceiveConfig(topic=args.topic, language=args.language, mode=args.mode,
                         format=args.format, target_episodes=args.episodes,
                         target_minutes=args.minutes)

    print(f"[1/2] Concept … ({slug})")
    record = run_concept(ctx, cfg)
    print(f"      {len(record['episodes'])} Episoden, Series-Record geschrieben.")

    print("[2/2] Skripte …")
    scripts = run_scripts(ctx, record)
    print(f"      {len(scripts['episodes'])} Episoden vertont-bereit unter {ws.stage_output('02_scripts')}")
    print("Fertig. Vertonung (Stage C) separat im venv/TTS-Pfad starten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
