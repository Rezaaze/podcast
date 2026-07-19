# rewrite/ — Ground-up-Rewrite (Model Workspace Protocol, sauber neu)

Dieser Baum ist der **Ground-up-Rewrite** der Podcast-Fabrik nach
[../docs/redesign-blueprint.md](../docs/redesign-blueprint.md), umgesetzt entlang
[../docs/redesign-implementation-plan.md](../docs/redesign-implementation-plan.md).
Vollständig **isoliert** vom produktiven `../fabrik/`-Code — nichts hier verändert den
laufenden Betrieb. Details/Provenance in [README.md](README.md).

## Was das ist

Der Rewrite baut den *bewiesenen* Teil des Blueprints (§1–8) sauber neu, mit den
**§10-Revisionen von Anfang an eingebaut** statt nachträglich gepatcht. Umfang-Grenze:

- **Autoren-Schicht (Stage A/B) = echter Rewrite** — hier saßen die §10-Altlasten.
- **Media-Schicht (Stage C/D/E) = aus `../fabrik/` adaptiert** — §9-„incidental" (TTS/ffmpeg/
  Packaging austauschbar); der produktionserprobte Kern ist 1:1 kopiert + entkoppelt, nur ein
  dünner Adapter je Stufe ist neu.

## Die §10-Erstentscheidungen (das Herz des Rewrites)

| # | Erste Entscheidung (revidiert) | ersetzt die alte | wo |
|---|---|---|---|
| §10.8 | structured output erzwingt Schema | Subprocess + JSON-Scavenging + Heartbeat | `core/model.py`, `providers/anthropic_model.py` |
| §10.3 | Per-Unit-State-Record (complete/degraded/unknown) | „Datei existiert ⇒ fertig" | `core/state.py` |
| §10.7 | eine Work-Queue, ein Limit | viele Ad-hoc-Caps + Semaphore | `core/queue.py` |
| §10.1 | eine Kontinuitätsstrategie (lean two) | Notes + Beat-Layer + schweres Review | `authoring/script_writer.py` |
| §10.2 | zentrale Allokation + Exclusion-List | Nachbar-Summaries + Multi-Vote-Judge | `authoring/conceive.py`, `reconciliation.py` |
| §10.5 | eine Season-Fold-Primitive | 3× kopierte Akkumulation | `authoring/season_fold.py` |
| §7.1 | schema_version + Migrationen | — (existierte nie) | `core/migrate.py` |

## Harte Invarianten

- **Import-Regel (§2):** `factory/core/` und `factory/authoring/` importieren `factory/media/`
  NIE — sonst bräche der stdlib-reine Authoring-Pfad. Maschinell erzwungen von
  `tests/test_import_boundary.py` (AST-Scan). `media`/`orchestration`/`providers` dürfen aus
  `core`/`authoring` importieren, nie umgekehrt.
- **State-Record ist die Wahrheit (§10.3):** Resume/Status kommen aus `core/state.py`
  (`Status.COMPLETE` = fertig; fehlend/degraded/unknown = resumbar), nie aus Datei-Existenz.
- **Model wird injiziert:** Der Authoring-Pfad nimmt eine `Model`-Instanz entgegen (Protocol in
  `core/model.py`). Tests nutzen `FakeModel`; Produktion `providers/anthropic_model.py`. So
  bleibt `authoring` netz-/dependency-frei und testbar.
- **Retry-Loop bleibt trotz structured output (§10.8-Carve-out):** structured output garantiert
  *parsebares*, nie *korrektes* JSON — `core/retry.py` (validate→retry→feedback) lebt darüber.

## Routing — wo die Details stehen

| Wenn du arbeitest an … | lies / sieh |
|---|---|
| Modell-Interface, Provider, structured output | `core/model.py`, `providers/anthropic_model.py`, `providers/schema_prep.py` |
| Resume/Status/Checkpoint | `core/state.py`, `core/checkpoint.py`, `orchestration/status.py` |
| Series-Record-Schema, Validierung, Migration | `core/schema.py`, `core/validator.py`, `core/migrate.py` |
| Stage A (Canon/Arc/Episode, Allokation, Repair) | `authoring/conceive.py`, `reconciliation.py`, `repair.py`, `detail_band.py` |
| Stage B (Skripte, Kontinuität, Hazards, Phrase-Guard) | `authoring/script_writer.py`, `word_budget.py`, `hazard.py`, `phrase_guard.py` |
| Vertonung (Adapter + kopierter Kern) | `media/{jobs,voicing,voice_manifest}.py`; Kern: `media/{audio_pipeline,tts_backends}.py` |
| Bild-/Sound-Assets, Packaging | `media/{emotion_variants,prompt_render,sfx_plan,asset_reuse,anthology,upload_index,highlights}.py` |
| Pipeline verdrahten, Locks, Cockpit | `orchestration/{pipeline,locks,config,cockpit}.py` |
| Blueprint-Begründungen / Trade-offs | `../docs/redesign-blueprint.md` |
| Phasen-Task-Stand | `../docs/redesign-implementation-plan.md` |

## Verifikation

- **Deterministischer Kern → echte Unit-Tests** (stdlib `unittest`, keine Deps):
  `cd rewrite && python3 -m unittest discover -s tests -v` (154 Tests).
- **Kreative LLM-Stufen → Integrationstests mit `FakeModel`** (Struktur, nie Prosa).
- **Media-Kern (pydub/ffmpeg) + echter Provider (anthropic)** werden NICHT von stdlib-Tests
  importiert — ihre Adapter schon (mit Fakes). Echter Lauf braucht `pip install anthropic` +
  Credentials (bzw. venv+TTS für Vertonung).
- **Jede neue Phase endet mit einem TEST-GATE** — nächste Phase startet erst bei grünem Gate.

## Offen

Nur die empirisch **gegatete Phase 8** (§12 Charaktertiefe / §13 Seams). Start ausschließlich,
wenn der **§12-Falsifikationstest (T8.0)** grün ist — der braucht einen echten Modell-Vergleich
(stated vs. inferred motive an einer realen Episode). Ebenso **T2.11** (§10.6 ein/zwei
Conceive-Pfade): technisch entsperrt (Provider existiert), braucht echten Lauf. Nicht vorab
bauen — erst messen (siehe Blueprint §12-Kopf und §10.6-Note).
