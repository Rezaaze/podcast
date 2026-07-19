# Podcast Factory — Rewrite

Ground-up-Rewrite nach [../docs/redesign-blueprint.md](../docs/redesign-blueprint.md),
umgesetzt entlang [../docs/redesign-implementation-plan.md](../docs/redesign-implementation-plan.md).
Isoliert vom produktiven `fabrik/`-Code; der laufende Betrieb bleibt unberührt.

**Stand:** Phase 0–7 fertig + echter Provider-Adapter. **154 Tests grün**, ~4.200 Zeilen
`factory/` + ~1.900 Zeilen Tests. Der bewiesene Teil (§1–8 des Blueprints, mit den
§10-Revisionen von Anfang an eingebaut, plus §7.1-Migration und §14-Konstanten) ist
komplett; nur die empirisch gegatete Phase 8 (§12/§13) fehlt.

## Warum ein Rewrite (und was NICHT neu geschrieben wurde)

Der Rewrite betrifft nur die **Autoren-Schicht** (Stage A/B), wo die §10-Altlasten saßen —
dort werden die *ersten* Entscheidungen anders getroffen (structured output statt Subprocess,
State-Record statt Datei-Existenz, eine Work-Queue, eine Kontinuitätsstrategie). Die
**Media-Schicht** (Stage C/D/E: TTS, ffmpeg, Bild/SFX, Packaging) ist §9-„incidental" und wurde
aus `fabrik/` **adaptiert, nicht neu geschrieben** — der produktionserprobte Audio-Kern ist
1:1 kopiert und entkoppelt, nur ein dünner Adapter je Stufe ist neu.

## Layout

| Paket | Inhalt | Umgebung |
|---|---|---|
| `factory/core/` | model, state, queue, retry, checkpoint, schema, validator, migrate, workspace, textproc | stdlib-only |
| `factory/authoring/` | Stage A (conceive) + Stage B (script_writer) + deterministische Bausteine | stdlib-only, LLM via Model-Injektion |
| `factory/media/` | Stage C/D/E: kopierter Audio-Kern (audio_pipeline, tts_backends) + Adapter | venv (pydub/ffmpeg) für den Kern |
| `factory/orchestration/` | benannte resumbare Stufen, Device-Lock, Status, Cockpit | stdlib-only |
| `factory/providers/` | echter Model-Adapter (Anthropic-SDK) | braucht `anthropic` |
| `factory/cli/` | Entry-Points | je nach Ziel |
| `tests/` | Unit-/Integrationstests (stdlib `unittest`) | stdlib-only |

**Harte Import-Regel (§2):** `core` und `authoring` dürfen `media` NIE importieren — erzwungen
von `tests/test_import_boundary.py` (AST-Scan).

## Tests

Deterministischer Kern hat echte Tests, keine Dependencies:

```bash
cd rewrite && python3 -m unittest discover -s tests -v
```

Kreative LLM-Stufen sind mit `FakeModel` integrationsgetestet (Struktur des Outputs, nie die
Prosa). Der Media-Kern (pydub/ffmpeg) und der echte Provider (anthropic) werden NICHT von den
stdlib-Tests importiert — ihre Adapter schon.

## Echter Lauf

Stage A+B mit echtem Claude (kein TTS nötig):

```bash
cd rewrite && pip install anthropic          # + Credentials: ANTHROPIC_API_KEY oder `ant auth login`
PYTHONPATH=. python3 -m factory.cli.create_series "Topic" --format crime_drama
```

Schreibt `data/series/<slug>/stages/01_concept/output/series.json` + Skripte unter `02_scripts/`.
Vertonung (Stage C) läuft separat im venv/TTS-Pfad (`factory/media/`, adaptiert aus `fabrik/`).

## Phasen-Status

- [x] Phase 0 — Fundament: Model-Interface (structured output), State-Record, Work-Queue, Retry-Loop
- [x] Phase 1 — Domänenmodell, Validator, Migration (schema_version), Workspace (atomare Slug-Reservierung)
- [x] Phase 2 — Stage A: Conceive (Canon → Arc → Episode, Turning-Point-Allokation, Exclusion-List) — T2.11 (§10.6) offen, braucht echten Lauf
- [x] Phase 3 — Stage B: Skripte (eine Kontinuitätsstrategie §10.1, Hazard-Checks, Phrase-Guard, resumbar)
- [x] Phase 4 — Stage C: Vertonung (Audio-Kern aus fabrik/ kopiert + Adapter: Record→Jobs, State-Bridge, Voice-Guard)
- [x] Phase 5 — Stage D: Bild-/Sound-Assets (Emotion-Cap, Prompt/Render-Split, SFX-Palette, Asset-Reuse-Audit)
- [x] Phase 6 — Stage E: Packaging (Anthologie-Kapitel, Upload-Index + Spoiler-Guard, Highlights via Cue-Indizes)
- [x] Phase 7 — Orchestrierung + E2E (benannte resumbare Stufen, Device-Lock, Filesystem-Status, Cockpit-Isolation)
- [x] Provider — echter Anthropic-Adapter (§10.8) + Entry-Point
- [ ] Phase 8 — GEGATET: §12 Charaktertiefe / §13 Seams (Start nur bei grünem §12-Falsifikationstest T8.0)

## §9-Fallen (strukturell ausgeschlossen)

| # | Falle | ausgeschlossen durch |
|---|---|---|
| 1 | Failed check als „passed" gecacht | State-Record (unknown≠clean) |
| 2 | Post-Merge nach Point-of-no-Return | kopierter Audio-Kern + State-Bridge |
| 3 | Repair am schwächsten Finding | split-by-scope Dispatcher |
| 4 | Event-Allokation an Batch-Grenze | zentrale Turning-Point-Allokation |
| 5 | Audio nach Dateiname trotz Voice-Änderung | Voice-Manifest-Guard |
| 6 | Missing-Flag als unchecked | `get_flag` (missing⇒default) |
| 7 | Zu große Calls truncaten | eine Work-Queue + kleine Units |
