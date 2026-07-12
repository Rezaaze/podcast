# fabrik/writing — Skript-Generierung (braucht nur den `claude` CLI, kein venv)

## Generierung ist section-weise und resumierbar (`script_writer.py`)

`generate_episode()` iteriert `episode["sections"]` und ruft pro Section
einmal Claude via `call_claude_with_retry` (bis `MAX_RETRIES=2`, Validierungs-
fehler werden wörtlich ins nächste Prompt zurückgefüttert;
`ESCALATION_FROM_ATTEMPT=2` verschärft die Formulierung im letzten Versuch:
"attempt N und IMMER NOCH falsch, füge einen konkreten Beat hinzu, schreib
nicht nur längere Sätze"). Jede fertige Section wird sofort in
`stages/02_scripts/output/<prefix>N.txt` geschrieben — `--- PART k ---`-Marker machen
Teildateien resumierbar: ein Re-Run überspringt Sections, deren Parts schon
existieren.

**Kontinuität:** Kontext ans Modell ist nur die *vorherige* Section, nicht
die ganze Episode/Serie — episodenübergreifende Kontinuität läuft komplett
über `intro_note`/`outro_note`/`theme`/`case`. Diese Lücke schließen
Episode-Review (nachträglich) und Beat-Layer (vorab), siehe unten.

## Wortbudget pro PART

- `format.words_per_part_min/max`, gemessen sprachneutral via
  `count_length_units` (fabrik/core/textproc.py).
- Optionaler Per-Section-Override `episodes[n].section_words[i]`
  (`{min,max,target}` oder `null`), aufgelöst von `resolve_section_cfg()`
  vor Prompt-Bau UND Validierung — so koexistieren kurze Konfrontation und
  lange Dialogszene in einer Episode.
- Toleranzband: `word_count_tolerance()` = 10% des Part-Minimums, Floor 15.
  Ein fixer Puffer lag früher im normalen Zähl-Rauschen des Modells —
  Retries wurden von Rauschen getriggert, nicht von echten Problemen.
- **Überlänge ist NIE ein Retry** (`validate_parts` akzeptiert mit
  Konsolen-Warnung): ein zu langer Part kostet Sekunden Laufzeit, eine
  Regenerierung kostet ein volles Prompt. Nur TOO SHORT und Formatfehler
  triggern Retries.

## Best-Effort-Fallback statt hartem Abbruch

Manche Szenen sind inhaltlich zu dünn, um das Minimum zuverlässig zu
erreichen (in Produktion beobachtet: 5 Versuche oszillierten 176–232 gegen
Minimum 220, nie konvergiert — deshalb wurde MAX_RETRIES von 3 auf 2
gesenkt). `validate_parts()` gibt `(ok, console, detail, fallback_safe,
badness)` zurück:

- `fallback_safe=False` nur bei fehlenden Parts oder `ScriptFormatError`
  (würde den TTS-Parser crashen, nie verwendbar).
- `badness` = summierter Wortbudget-Fehlbetrag.
- Scheitern alle Retries nur am Wortbudget, nimmt `call_claude_with_retry`
  den am wenigsten schlechten fallback-sicheren Versuch, statt `None` und
  Episoden-Abbruch. Ein Formatfehler wird auf diesem Weg NIE akzeptiert.
- **Early Fallback:** ein fallback-sicherer Versuch mit badness innerhalb
  `2 * word_count_tolerance()` wird SOFORT akzeptiert — der Fallback hätte
  ihn am Ende ohnehin genommen, weitere Regenerierungen brächten nichts.

## Leichtes Modell für nicht-kreative Calls

`generation.light_model` (Default `claude-haiku-4-5`) für:
`generate_episode_meta` (Titel/Beschreibung), beide LLM-Reviews
(`review_episode_script`, `review_episode_beats`), `import_story`s
Metadaten-Summarization. Kreatives (Sections, Beats, `repair_part`) bleibt
auf `generation.model`.

## Episode-Review (`--fix` auf generate_episode)

Weil jede Section nur die vorige sieht, kann ein Charakter aus seinem
`case`/`character_knowledge`-Slice driften oder eine `solution` zu früh
leaken, selbst bei sauberem Plan.

- `review_episode_script()` — zweiter Claude-Call auf dem FERTIGEN
  Skripttext, gated auf `episode.get("case")` (nicht `mode`!): plain
  narration/language_course haben keinen case und werden übersprungen;
  media_analysis hat einen und wird geprüft. Liefert strukturiert
  `{"issues": [{"part": N, "problem": "..."}]}`.
- Timeout skaliert mit Skriptlänge (`compute_review_timeout`, 300–1200s).
- **`None` vs. `[]`-Disziplin:** bei jedem Fehlschlag (Timeout/API/
  unparsebar) kommt `None` zurück — dann darf KEIN `<prefix>N_REVIEW.txt`
  geschrieben werden, sonst sieht ein späterer Lauf "existiert" und
  retried nie. `None` = "wissen wir nicht", `[]` = "wirklich sauber".
- Mit `--fix`: jeder geflaggte Part mit bekannter Nummer wird isoliert von
  `repair_part()` neu geschrieben (gleiche Validierung wie Erstentwurf,
  Prompt zeigt nur aktuellen Text + Problem, verlangt chirurgischen Fix)
  und via `replace_part_in_script()` zurückgesplict — Regex-Replace mit
  Replacement-*Funktion*, nicht -String (verhindert Backslash-/
  Gruppenreferenz-Fehlinterpretation von beliebigem Claude-Text). Danach
  wird die ganze Episode erneut reviewt, um zu bestätigen, dass der Fix
  gelandet ist.
- Ergebnisse idempotent gecacht in `<prefix>N_REVIEW.txt` (Re-Run skippt
  außer `--force`/`--fix`); `--no-script-review` skippt komplett. Beide
  Flags laufen durch `generate_episode.py all`s Subprocess-Parallelität.

## Beat-Layer (`generation.use_beats: true`, opt-in, Default aus)

Schließt dieselbe Kontinuitätslücke wie das Review, aber VOR der teuren
Prosa statt danach. Gated auf `cfg["use_beats"] and episode.get("case")`.
Volle Design-Begründung: `docs/beat-layer-design.md`.

- `generate_beats()`: EIN Claude-Call sieht alle Section-Einzeiler +
  `case`-Block (`build_case_file_block()`, unverändert wiederverwendet) +
  Beats-Text der *vorherigen Episode*, liefert 3–6 Beats pro Szene in
  `--- SCENE N ---`-Blöcken → `parse_beats()` →
  `stages/02_scripts/output/<prefix>N_BEATS.txt`.
- Resume = einfacher Existenz-Check (kein inkrementelles Schema wie bei
  PART-Dateien — ein Call erzeugt die ganze Datei, nichts zu resumen).
- Fehlgeschlagener/unparsebar Beat-Call ist NICHT fatal: `None`, keine
  Datei, `build_section_prompt()` fällt auf den alten
  Vorherige-Section-Prosa-Kontext zurück, exakt als wäre use_beats aus.
- Mit Beats ersetzt `build_section_prompt()` den Prosa-Block durch alle
  Szenen-Beats der Episode als Überblick, die aktuelle Szene markiert mit
  `<-- WRITE THIS SCENE NOW` — der Dialog-Writer plant über die ganze
  Episode statt nur die letzte Section zu sehen.
- `review_episode_beats()` (strukturgleich zu review_episode_script, gleiche
  None/[]‑Disziplin, warn-only, kein Auto-Repair) läuft direkt nach der
  Generierung → `<prefix>N_BEATS_REVIEW.txt`. `--force` löscht BEATS- und
  BEATS_REVIEW-Datei wie die Skriptdatei.
- **Known limitation:** `all --jobs N` submitted alle Episoden vorab
  (ThreadPoolExecutor) — Beats-Kontinuität (vorherige Episode lesen) ist
  nur bei geordneter Generierung zuverlässig. Fehlende Vorgänger-Beats
  unter `--jobs > 1` = Info-Log, nie Crash.

## Sonstiges

- `build_style_tag_rule()` / der Guard um den narration `VOCAL DELIVERY`-
  Absatz lassen Style-Anweisungen weg, wenn `cfg["supports_style"]` false
  ist (Backend würde sie verwerfen) — Quelle: `BACKEND_SUPPORTS_STYLE` in
  fabrik/core/config.py.
- `extract_vocab_notes` (language_course): `[NOTE: wort — pinyin —
  bedeutung]`-Zeilen werden aus dem GESAMTEN bisherigen Skript extrahiert
  (nicht nur dem getrimmten Kontinuitätskontext) und der nächsten Section
  wieder vorgelegt.
- `summarize_source_episode()` (für import_story): nur Titel+Theme-
  Metadaten, explizit verboten, Handlung zu erfinden; läuft auf dem
  light_model.
- `call_claude()` hier und in create_series.py: `stdin=subprocess.DEVNULL`
  Pflicht — Details in fabrik/core/CLAUDE.md.
