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

**TTS-Hazard-Checks in `validate_parts()` (17.07.2026):** zusätzlich zum
Format-Parse laufen drei Checks. (1) `find_narrator_leaks()` — NARRATOR-
Zeilen, die case-Thread-Labels, das Wort "thread"/"storyline" oder
Szenennummern hörbar aussprechen (in Produktion 15-43 Leaks/Serie, teils
spoilernd) = retryable Fehler, fallback-sicher, erhöht badness
(`_LEAK_BADNESS`); braucht `cfg["case_labels"]`, das `generate_episode()`
pro Episode in eine cfg-KOPIE injiziert. (2) `warn_stage_directions()` —
mutmaßliche 3.-Person-Regieanweisungen im Sprechtext ("He signs the
form.") = NUR Konsolen-Warnung (False-Positive-Risiko im Dialog);
entstehen, weil `script_parser.py` Fließtext nach einer Sprecherzeile an
deren Text ANHÄNGT statt zu erroren. (3) **`find_noise()`** (Stage-01-
Umbau Phase 4, docs/konzept-stage-umbau.md) — der EINE verbleibende
deterministische Check, der den gelöschten Section-Tiefe-/Kanon-Drift-
Checks aus create_series.py nachfolgt, aber eine andere Fehlerklasse
abdeckt (reines Modell-Rauschen, gegen das keine Prompt-Vorgabe hilft,
kein Struktur-/Kontinuitätsproblem): Sprechzeilen ohne einen einzigen
Buchstaben (`textproc.is_speakable()`), Platzhalter
(`placeholder`/`TODO`/`TBD`), Markdown-Reste (`**fett**`, `` `code` ``,
Listenpunkte) und fremdsprachige Zeichen mitten im Sprechtext (beobachtet:
`问题` in einem englischen Satz — Han/Hiragana-Katakana/Hangul-Ranges,
übersprungen bei `cfg["language"]` = Chinese/Mandarin). Retryable Fehler,
fallback-sicher, erhöht badness (`_NOISE_BADNESS`). Gegengeprüft an 236
Parts aus zwei echten Produktionsserien: 1 echter Fund (eine
Interpunktions-only-Zeile), 0 False Positives.

**Phrasen-Wächter (`phrase_stats.py`, stdlib-only, 17.07.2026):** zählt
3-5-Wort-n-Gramme + Style-Wörter über die bereits geschriebenen Episoden
("barely audible" 57x, style "quiet" 193x in Produktion). `generate_episode()`
baut daraus `cfg["avoid_block"]` (Eigennamen via `name_words(data)`
ausgenommen — Figuren/Orte MÜSSEN wiederkehren), `build_section_prompt()`
hängt ihn an; `generate_episode.py all` schreibt zusätzlich
`PHRASE_REPORT.txt` als Review-Gate neben die Skripte.

**Kontinuitäts-Wächter (`continuity.py`, stdlib-only, 19.07.2026):** prüft
die FERTIGEN Skripte einer Staffel deterministisch gegen den Kanon aus
episodes.json. Drei Checks, alle ohne Modellaufruf: (1) Orts-/Organisations-
Eigennamen gegen `locations[].name` + die in `threads` genannten Entitäten
(Produktion: eine Serie führte vier verschiedene Zeitungen, obwohl der Kanon
eine kennt); (2) Ortstyp am selben Besitzer, klassenweise verglichen — Kanon
"Renata's House" vs. Prosa "Renata's apartment" ist ein Fund, "Adrian's
precinct" neben "Adrian's Apartment" nicht (sein Arbeitsplatz); (3)
Zeitangaben nahe einem Kanon-**Eigennamen**, die keiner der für ihn
festgelegten Angaben entsprechen ("Six weeks" für Panopticon, das laut
`objective_facts` vier Monate läuft).

Zwei Verwendungen, wie bei `phrase_stats.py`: `build_continuity_report()` →
`CONTINUITY_REPORT.txt` (Review-Gate, schreibt `generate_episode all`
automatisch neben PHRASE_REPORT.txt; Knopf im Cockpit unter „Einzelschritte");
`build_continuity_block()` → Prompt-Block mit den harten Werten, die schon
feststehen (Kanon-Ortsnamen, erreichte Zählerstände).

**Kalibrierung — nicht ohne Messung anfassen.** Zwei Entwürfe scheiterten
vorher an echten Produktionsdaten: (a) generische Zähler-Regression über
jedes Nomen mit Zahl produzierte 127 Meldungen auf zwei Serien, praktisch
alle falsch ("drei Blocks", "94 Prozent" — Nomen mit Zahlen variieren
legitim); (b) Zeitanker über beliebige Eigennamen verankerte auf "Adrian",
"Captain", "Detective", die in jeder zweiten Zeile stehen, sodass jedes
Zeitfenster traf. Deshalb `_usable_anchors()`: Figurennamen (via
`phrase_stats.name_words`) und alles, was häufiger als 3x pro Episode
vorkommt, scheiden als Anker aus. Endstand auf denselben zwei Serien: 12
Meldungen, alle belegbar, darunter fünf, die ein LLM-Prüfpanel übersehen
hatte.

**Grenze, ehrlich benannt:** prosa-INTERNE Zahlenfehler ohne Kanon-Bezug
findet das Modul nicht (Ep1 "forty-two mornings" → Ep2 "Six weeks. Six
faces."; Foto "Forty-one" an Tag 48). Das ist die größere Hälfte der
gemessenen Brüche und braucht ein aus der Prosa gezogenes Zustands-Register
— bewusst noch nicht gebaut.

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
erreichen (in Produktion beobachtet: 5 Versuche oszillierten 176–200 gegen
Ziel 220, nie konvergiert — deshalb wurde MAX_RETRIES von 3 auf 2
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
`generate_episode_meta` (Titel/Beschreibung/Zuschauer-Frage), beide LLM-Reviews
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
  `{"issues": [{"part": N, "problem": "..."}]}`. Läuft seit 17.07.2026 auf
  `cfg["review_model"]` (Default = großes Schreibmodell, siehe
  fabrik/core/CLAUDE.md) und prüft drei Dinge (Wissens-Verstöße, Spoiler,
  **Fakten-Konsistenz** — Namen/Daten/Zeiten gegen objective_facts und
  gegeneinander); `build_review_context_block()` gibt Beats der Vorepisode
  + intro_note als Cross-Episode-Kontext mit.
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
- Ergebnisse idempotent gecacht in `<prefix>N_REVIEW.txt` — und der Cache
  wird ZURÜCKGELESEN (`parse_review_file`): ein Re-Run (auch mit `--fix`)
  reviewt ein unverändertes Skript nie erneut. "Keine Auffälligkeiten" →
  Review-Block komplett übersprungen; REVIEW.txt mit Befunden + `--fix` →
  gecachte Befunde gehen direkt in die Reparatur (nur das Bestätigungs-
  Review danach ist ein frischer Call, und nur wenn ≥1 Part wirklich
  repariert wurde). Nur `--force` (Skript regeneriert) reviewt neu;
  `--no-script-review` skippt komplett. Alle Flags laufen durch
  `generate_episode.py all`s Subprocess-Parallelität.

## Beat-Layer (`generation.use_beats`, Default **AN** via `DEFAULTS`)

Schließt dieselbe Kontinuitätslücke wie das Review, aber VOR der teuren
Prosa statt danach. Gated auf `cfg["use_beats"] and episode.get("case")`.
Volle Design-Begründung: `docs/beat-layer-design.md`.

**Diese Überschrift sagte bis 19.07.2026 "opt-in, Default aus" — das war
falsch.** `DEFAULTS["use_beats"]` (fabrik/core/config.py) steht auf `True`,
fehlt der Key in episodes.json, laufen die Beats also. Das WebUI las den
Wert mit hart kodiertem Default `False` und zeigte deshalb eine leere
Checkbox für Serien, in denen die Beat-Schicht sehr wohl lief (beide bei
der Drift-Messung untersuchten Produktionsserien hatten BEATS-Dateien, nur
eine hatte den Key gesetzt). Beides gefixt — wer den Default ändert, muss
`webui/app.py`s Rückfall NICHT nachziehen, der liest ihn jetzt aus
`DEFAULTS`.

**Beats sind nicht genug.** Die Messung (docs/kontinuitaets-messung-
2026-07-19.md) fand ~1,1 gegengeprüfte Kanon-Brüche pro Episode TROTZ
laufender Beat-Schicht. Der Grund ist strukturell: Beats entstehen VOR der
Prosa aus dem Plan und wissen nicht, was das Modell tatsächlich geschrieben
hat. Die Fehlerklasse, die dadurch durchrutscht (erfundene Ortsnamen,
Zeitangaben gegen die objective_facts), fängt `continuity.py` deterministisch
ab — siehe unten.

- `generate_beats()`: EIN Claude-Call sieht alle Section-Einzeiler +
  `case`-Block (`build_case_file_block()`, unverändert wiederverwendet) +
  **die Beats ALLER vorherigen Episoden** (Staffel-Gedächtnis, seit
  17.07.2026 — vorher nur die direkte Vorgängerin, weshalb Finali frühere
  Episoden "vergaßen": the_understudy hatte den Klimax zweimal mit
  entgegengesetztem Ausgang). Beat-Sheets sind klein (~1-2 KB/Episode).
  Szene 1 muss zusätzlich einen expliziten Zeit-Beat enthalten (wie viel
  Zeit seit der Vorepisode verging — gegen Zeitachsen-Drift). Liefert 3–6
  Beats pro Szene in `--- SCENE N ---`-Blöcken → `parse_beats()` →
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
- **Beats-Vorlauf bei `all --jobs > 1`:** generate_episode.py generiert
  alle Beat-Sheets VOR dem Pool seriell in Episodenreihenfolge (Kontinuität
  braucht die Beats der Vorgänger-Episode) und reicht `--beats-ready` an
  die Subprocesses durch — dort werden Beats dann auch mit `--force` nicht
  gelöscht/neu generiert, nur geladen (`beats_pregenerated` in
  generate_episode()). Fehlende Vorgänger-Beats (z. B. Beat-Call im
  Vorlauf gescheitert) = Info-Log, nie Crash.

## Asset-Module (leben hier wegen des No-venv-Pfads, nicht wegen "Writing")

Neben der Skript-Generierung liegen fünf stdlib-only Asset-Module in diesem
Paket, weil sie von claude-CLI-Pfad-CLIs (kein venv) importiert werden und
`fabrik/audio/` tabu ist:

- `character_library.py` / `location_library.py` / `sfx_library.py` —
  serienübergreifende Wiederverwendung von Porträts, Orts-Hintergründen
  und SFX-Assets (`data/sfx_library/`). Alle drei: exakter Hash-Treffer
  zuerst, sonst Fuzzy per Wortmengen-Überlappung (Jaccard) — bewusst kein
  API-Call/Embeddings, stdlib-only. **Belastbarkeitsgrenze** (16.07.2026,
  echte Produktionsdaten über 11 Serien geprüft): bei Charakteren/Orten
  bleibt Fuzzy praktisch wirkungslos (0 Aliase trotz 21 bzw. 36 Einträgen),
  weil Beschreibungen lang/plot-reich sind (Ø 39 Wörter bei Charakteren) und
  Wortüberlappung dadurch selbst bei echten Archetyp-Duplikaten sehr niedrig
  bleibt (~0.20–0.24) — in derselben Score-Spanne liegen aber auch klare
  FALSE POSITIVES (zwei Rollen, die nur eine Ethnizitäts-Formulierung teilen).
  `character_library.py::_archetype_clause()` vergleicht deshalb nur den Teil
  vor dem ersten ';' (Archetyp statt Plot-Rückblende, 97% der Beschreibungen
  haben dieses Muster) — verbessert die Signalqualität, OHNE
  `SIMILARITY_THRESHOLD` zu senken (kein sicherer Trennwert zwischen echtem
  Treffer und Zufallsüberlappung gefunden). Für Orte gibt es kein
  vergleichbares Trenner-Muster (nur primär-visueller Text, das Problem ist
  lexikalische Vielfalt, keine Wortmengen-Metrik löst das ohne Embeddings).
  Statt automatisch zu raten: `fabrik/cli/library_audit.py` listet
  Near-Miss-Kandidaten unterhalb der Produktiv-Schwelle auf (characters/
  locations/sfx) — reine Anzeige, der Mensch entscheidet beim Lesen.
- `elevenlabs_backend.py` — ElevenLabs SFX/Ambience-Generierung (urllib,
  `ELEVENLABS_API_KEY`), genutzt von sfx_assets/location_ambience.
- `image_backends.py` — OpenAI-Bildgenerierung (urllib, `OPENAI_API_KEY`),
  genutzt von character_prompts/location_prompts/cover_art/
  episode_thumbnails.
- `thumbnail_writer.py` — dramatisches, spoilerfreies Episoden-Thumbnail
  (Hook-Zeile + Poster-Bildprompt, je ein Render in 16:9 und 1:1); importiert
  `call_claude`/`MAX_RETRIES`/`RETRY_DELAY` aus `script_writer.py` (wie
  `cover_art.py`), der automatische Aufruf sitzt deshalb in
  `fabrik/cli/generate_episode.py`, nicht in `script_writer.py` selbst —
  sonst Zirkel-Import. Details: fabrik/cli/CLAUDE.md.

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
