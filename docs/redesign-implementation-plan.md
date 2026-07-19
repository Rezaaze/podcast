# Podcast Factory — Rewrite-Implementierungsplan (v1)

> **STATUS (Stand: letzte Session):** Phase 0–7 **fertig** + echter Provider-Adapter (§10.8).
> **154 Tests grün.** Code liegt in [`../rewrite/`](../rewrite/) (Kontext: `../rewrite/CLAUDE.md`).
> Der bewiesene Teil (§1–8 + §10-Revisionen + §7.1 + §14) ist komplett und mit echtem Claude
> lauffähig (`pip install anthropic` + Credentials). **T2.11 (§10.6) ist ENTSCHIEDEN
> (19.07.2026, echter Lauf): zwei Pfade bleiben** — siehe Task unten. **Offen:** die
> gegatete Phase 8 (§12/§13, braucht T8.0) und der One-Shot-Pfad für simple Formate
> (Folge der T2.11-Entscheidung, noch nicht gebaut).

> Umsetzungsplan zum [redesign-blueprint.md](redesign-blueprint.md). **Ground-up-Rewrite**,
> Umfang: erst die *bewiesenen* Cleanups (§10-Revisionen von Anfang an eingebaut,
> §7.1-Migration, §14-Konstanten). §12 (Charaktertiefe) und §13 (Seam-Contracts) sind
> als **gegatete Phase 8** hinten angehängt — sie werden erst gebaut, wenn der
> §12-Falsifikationstest grün ist.
>
> Die §-Verweise zeigen in den Blueprint. Wo der Blueprint eine Entscheidung revidiert
> hat (§10), baut dieser Plan die *revidierte* Fassung — nie die alte, die dann gepatcht
> wird. Das ist der Sinn des Rewrites.

---

## 0. Leitplanken für den ganzen Rewrite

**Test-Philosophie (auf dieses Projekt zugeschnitten).** Das Altrepo hat bewusst keine
Test-Suite; Verifikation lief über Smoke-Runs. Ein Rewrite ist der *richtige* Moment,
das genau dort zu ändern, wo es zahlt — und nur dort:

- **Deterministischer Kern bekommt echte Unit-Tests** (pytest, leichtgewichtig). Das
  sind exakt die Garanten: Validator, Seam-Checks, Migration, State-Record, Work-Queue,
  Hazard-Checks, Retry-Loop-Logik. Diese Dinge *dürfen nie* still brechen — sie sind
  die "correctness enforced"-Hälfte (§1).
- **Kreative LLM-Stufen bleiben Smoke-verifiziert** — Mini-Serie, `check`-Kommando,
  Cockpit-Durchklick. Man testet die *Struktur* des Outputs deterministisch, nie die
  Prosa selbst.
- **Jede Phase endet mit einem `TEST-GATE`.** Kommt das Gate nicht grün durch, geht die
  nächste Phase nicht los. Das ist die "Bugs sofort korrigieren"-Regel — Fehler werden
  an der Phasengrenze gefangen, nicht drei Phasen später.

**Rewrite ≠ alles neu schreiben — nur die Autoren-Schicht (§9 keep-vs-incidental).**
Der Rewrite betrifft die Stufen, in denen die §10-Altlasten sitzen: die *Autoren*-Schicht
(Stage A/B). Die *Media*-Stufen (C Vertonung, D Bilder/SFX, E Packaging) sind §9-„incidental":
die TTS-Engine, ffmpeg-Mastering und Anthologie-Merge sind austauschbar, aber der
**produktionserprobte Code dafür existiert bereits** in `fabrik/audio/` (u.a.
`pipeline.py`, `tts_backends.py`) und erfüllt die §Stage-C-Invarianten schon sauber
(part_offsets-Point-of-no-Return, Chunk-Normalisierung, Voice-Manifest-Guard, Self-Healing,
Cloud-Batching). Der Blueprint nennt den Audio-Merge sogar „the existing proof that
cast-once works" (§2/§13.6) — das ist die *Referenz*, nicht etwas zum Neuschreiben.

Regel: **Media-Stufen werden aus `fabrik/` adaptiert, nicht reimplementiert.** Neu ist nur
ein dünner Adapter je Stufe (neues Series-Record → die Eingaben, die der bewährte Kern
erwartet; Brücke zu State-Record/Work-Queue). Das ist auch praktisch nötig: echte
Synthese/ffmpeg lässt sich in dieser Umgebung nicht testen — ein Neuschrieb wäre ungetestet
*und* schlechter als das Bewährte. Nur der Adapter (reine Übersetzungslogik) wird mit Fakes
deterministisch getestet.

**Die §10-Entscheidungen, die von Anfang an drinstecken** (nicht nachrüsten):

| # | Erste Entscheidung (revidiert) | ersetzt die alte |
|---|---|---|
| §10.8 | Modell-Interface mit **structured output**, nativer Concurrency, Streaming | Subprocess + JSON-Scavenging + Heartbeat |
| §10.3 | **Per-Unit-State-Record** (complete/degraded/unknown) | "Datei existiert ⇒ fertig" |
| §10.7 | **Eine** Work-Queue, ein Concurrency-Limit | viele Ad-hoc-Caps + Semaphore |
| §10.1 | **Eine** Kontinuitätsstrategie (lean two: Plan-vorher + dünner Check-nachher) | Notes + Beat-Layer + schweres Review |
| §10.2 | Zentrale Allokation mit **Exclusion-List**, kein Multi-Vote-Judge | Nachbar-Summaries + teurer Judge |
| §10.4 | **Deklarierte** Capabilities am Format | Ableitung aus Datenform |
| §10.5 | **Season-Fold**-Primitive (einmal) | 3× kopierte Akkumulation |
| §7.1 | `schema_version` + Migrationen ab Tag 1 | — (existierte nie) |

**Trap-Checkliste (§9).** Jede Phase listet die §9-Fallen, die sie strukturell
ausschließen muss. Eine Phase ist erst „fert", wenn ihre Fallen *by design* unmöglich
sind, nicht bloß „gerade nicht aufgetreten".

---

## Phase 0 — Fundament (das Interface, das alles andere billiger macht)

**Ziel:** die vier Bausteine, die §10 als „erste Entscheidung" verlangt. Zuerst, weil
jede spätere Stufe darauf steht.

- [x] **T0.1 — Projekt-Skelett & Umgebungs-Split (§2).** Zwei Import-Zonen: Authoring
      (LLM-only, stdlib) und Media (venv + ffmpeg + GPU). Harte Regel als Lint/Import-
      Check: Authoring darf Media *nie* importieren. → `rewrite/factory/{core,authoring,media}/`,
      Guard in `tests/test_import_boundary.py`.
- [x] **T0.2 — Modell-Interface mit structured output (§10.8).** Ein Adapter, der ein
      JSON-Schema erzwingt und validiertes Objekt zurückgibt. Streaming bei großem
      max_tokens. **Kein** JSON-Scavenging, kein Heartbeat, kein stdin-Trick. → Interface:
      `factory/core/model.py` (Model-Protocol + FakeModel). **Echter Adapter gebaut:**
      `factory/providers/anthropic_model.py` (Anthropic-SDK, `output_config.format`,
      Tier→Modell Opus4.8/Haiku4.5, refusal→fatal) + `schema_prep.py`; mit Fake-Client
      getestet (braucht `pip install anthropic` + Credentials für echten Lauf). Entry:
      `factory/cli/create_series.py`.
- [x] **T0.3 — Per-Unit-State-Record (§10.3).** `{unit_id, status: complete|degraded|
      unknown, produced_what, meta}`. „Datei da, Status unknown" ist ein normaler
      resumbarer Zustand, keine stille Lüge. Ersetzt jede „Datei existiert"-Inferenz.
      → `factory/core/state.py` (atomares Schreiben, `is_done` nur bei COMPLETE).
- [x] **T0.4 — Eine Work-Queue, ein Concurrency-Limit (§10.7).** Ein globales Queue-
      Primitiv (Start: 4–8 in flight, §14). Alle Stufen enqueuen hier — keine lokalen Caps.
      → `factory/core/queue.py` (BoundedSemaphore, stabile Reihenfolge, Peak-Tracking).
- [x] **T0.5 — Universeller Retry-Loop (§5, §10.8-Carve-out).** `generate → validate →
      (ok | best-effort-fallback | feedback+retry)`, mit Eskalation. **Bleibt trotz
      structured output** — der garantiert parsebares JSON, nie korrekten Inhalt.
      `(ok, fatal, badness, detail)`-Signatur. → `factory/core/retry.py`.

**TEST-GATE 0** ✅ — 29/29 Tests grün (`python3 -m unittest discover -s tests`):
- State-Record: complete/degraded/unknown werden korrekt geschrieben/gelesen; „degraded"
  triggert Resume, nicht Skip.
- Queue: Concurrency-Limit hält unter Last; kein Deadlock; Reihenfolge stabil.
- Retry-Loop: fatal → nie akzeptiert; soft nach letztem Versuch → least-bad-safe; Feedback
  wird tatsächlich angehängt; Eskalation feuert an der Schwelle.
- Import-Check: ein Testimport Authoring→Media schlägt fehl (CI-Guard).
- **Fallen ausgeschlossen:** #1 (unknown≠clean), #6 (missing⇒default), #7 (Batch-Größe —
  Queue erzwingt kleine Calls).

---

## Phase 1 — Domänenmodell, Validierung, Migration, Workspace

**Ziel:** das „single source of truth"-Record und der Rahmen, der es über Schema-
Versionen hinweg am Leben hält.

- [x] **T1.1 — Series-Record-Schema mit `schema_version` (§3.1, §7).** Flach-vor-tief
      (§7: freitext-Wissensslices statt tiefer Nestung — Nestungstiefe bricht JSON, nicht
      Textmenge). Frozen canon strikt, Episoden-Zusätze locker. → `factory/core/schema.py`
      (SERIES_SCHEMA, MODES/FORMATS, `minimal_valid_record()`).
- [x] **T1.2 — Ein wiederverwendeter Validator (§5).** Struktur-invalid → harter Fehler
      *vor* Arbeit; legal-aber-verdächtig → Warnung; unbekanntes Feld → Warnung. Genau
      eine Stelle — Concept-Generierung validiert, indem sie ein Kandidat-Record baut und
      *denselben* Validator laufen lässt. → `factory/core/validator.py` (Struktur + Semantik:
      Doppel-Voice, dangling thread, unknown fields).
- [x] **T1.3 — Deklarierte Capabilities (§10.4).** `needs_continuity_review`,
      `has_knowledge_split` etc. explizit am Format — nie aus „hat ein case-Block"
      abgeleitet. → `KNOWN_CAPABILITIES` in schema.py, validiert in validator.py.
- [x] **T1.4 — Migrations-Framework (§7.1).** `schema_version` + forward-only,
      idempotente `migrate_vN_to_vN+1`. Fehlende Version ⇒ *älteste*, nicht „aktuell".
      Neue Pflichtfelder → `needs-backfill`-Marker, nie erfundener Wert. Frozen canon wird
      migriert, nie neu-abgeleitet. → `factory/core/migrate.py` (Registry, `_migrate_0_to_1`).
- [x] **T1.5 — Workspace = Pipeline (§3.2).** Ordner-Layout = Stufen; `references/`
      pro-Serie editierbare Contract-Kopien; Pointer-Datei für „aktuelle Serie";
      **atomare Slug-Reservierung** (`os.mkdir`, leerer Ordner = Reservierung) gegen
      parallele Kollision. Layout trägt eigene Version (§7.1). → `factory/core/workspace.py`.

**TEST-GATE 1** ✅ — 54/54 Tests grün (25 neu + 29 Regression):
- Validator: gültig/ungültig/unbekanntes-Feld liefern hart/warn/warn — Tabellen-getrieben.
- Migration: `migrate(migrate(x)) == migrate(x)` (Idempotenz); fehlende Version → älteste;
  neues Pflichtfeld → `unknown`, kein Fabrikat; frozen fact bleibt bitgleich.
- Slug: zwei parallele Creator auf denselben Namen → genau einer gewinnt.
- Capabilities: Feature-Gate liest die Deklaration, nicht die Datenform (Regressionstest
  gegen §10.4-Kopplung).
- **Fallen ausgeschlossen:** #1, #6; plus die *neue* Migrations-Falle (neues Feld als
  Zero-Value auf altem Record).

---

## Phase 2 — Stage A: Conceive (der Kern-Insight)

**Ziel:** aus einem Topic das Source-of-Truth-Record — mit zentraler Turning-Point-
Allokation, damit Event-Allokation *nie* an eine Batch-Grenze leckt (§9 Falle #4).

- [x] **T2.1 — Single-Source-Substitution (§5).** Voice-Roster/Modellnamen/Limits werden
      zur Build-Zeit in Prompts injiziert; nicht-ersetzte Platzhalter warnen laut.
      → `factory/authoring/substitution.py`.
- [x] **T2.2 — Season-Fold-Primitive (§10.5).** „Iteriere Einheiten in Reihenfolge, jede
      sieht das Aggregat der vorigen." → `factory/authoring/season_fold.py` (sieht ALLE
      vorigen, nicht nur den unmittelbaren Vorgänger; `skip_on_error` für non-fatale Steps).
- [x] **T2.3 — Canon-Tier (ein Call).** Welt, Cast, Locations, Threads: je Thread label +
      wahre Lösung + harte Fakten. Frozen. → `conceive.py::CANON_SCHEMA` + A1-Schritt.
- [x] **T2.4 — Arc-Tier mit Exclusion-List (§10.2 revidiert).** Ein Call, sieht Canon,
      weist *jeden* Turning-Point genau einer Episode zu. Jeder Episode-Call bekommt die
      fremden Turning-Points als **Exclusion-List**, **nicht** als Nachbar-Summary.
      → `conceive.py::_episode_exclusion_list` (Test beweist: Ep0 sieht nur tp1, Ep1 nur tp0).
- [x] **T2.5 — Episode-Concept-Tier (parallel).** Ein Call pro Episode über die Work-Queue;
      nie den Parallel-Output der Geschwister. → `conceive.py::make_episode` (queue.map).
- [x] **T2.6 — Detail-Tiefe-Band als Gate (§ Stage A).** Jedes section-„what" im neutralen
      Längenband; Spread pro Episode ≤ 2 Tiers (§14). Vor Acceptance geprüft, mit Feedback
      via Retry-Loop. → `factory/authoring/detail_band.py`.
- [x] **T2.7 — Assembly + Validierung.** Canon + Arc + Concepts → Kandidat-Record →
      *derselbe* Validator (T1.2). → `conceive.py::_assemble` + `validate_series`.
- [x] **T2.8 — Reconciliation als deterministischer Check (§10.2 revidiert).** **Kein**
      Multi-Vote-LLM-Judge — billiger deterministischer Check: gleiche Turning-Point-ID in
      zwei Episoden → Flag (duplicated/missing/misplaced). → `factory/authoring/reconciliation.py`.
- [x] **T2.9 — Repair-Dispatcher split-by-scope (§ Stage A).** Findings nach Scope; Truncation
      bricht ab statt blind zu retryen; Partial behalten. → `factory/authoring/repair.py`
      (Test beweist: scope-loses Finding kippt NICHT alles in Full-Rebuild — §9 Falle #3).
- [x] **T2.10 — Checkpointing (§ Stage A).** Canon/Arc/jede Episode als eigene Cache-Einheit,
      gekeyt auf *Call-Parameter*. → `factory/core/checkpoint.py` (Test: 2. Lauf ruft Modell
      0× — alles aus Cache).
- [x] **T2.11 — §10.6-Entscheidung (der Test). ERGEBNIS: ZWEI PFADE BLEIBEN.**
      Gemessen 19.07.2026 am ersten echten Lauf (ClaudeCliModel/sonnet, Serie
      `t211_libraries`: Topic "great libraries", `--format narration --mode narration`,
      2 Episoden à ~3 Min) gegen einen äquivalenten One-Shot-Call:
      - **(a) Qualität: decomposed VERZERRT das simple Format.** Trotz mode=narration
        erfand der Kanon einen 5-Personen-Cast mit Stimmen + 6 Locations + Threads,
        und Stage B schrieb DIALOG (Ep0: 6 Sprecher, nur 5/18 Zeilen NARRATOR) statt
        Ein-Stimmen-Narration. Der One-Shot-Call respektierte die Narration-Vorgabe
        (reine figure/theme/sections-Struktur, kein Cast).
      - **(b) Kosten: 4 Concept-Calls + mehrere Minuten (decomposed) vs. 1 Call/12s/
        1,3 KB (one-shot)** für dieselbe Konzept-Aufgabe.
      - **(c) Degenerierte Dokumente sind NICHT klein:** canon 3,5 KB + arc 1,9 KB +
        2 Episoden-Konzepte ≈ 7,9 KB — canon/arc tragen echtes Gewicht, genau die
        "neue Kompensation", vor der das §10.6-Verdict warnt.
      **Konsequenz:** Blueprint-Verdict (specialization, not redundancy) empirisch
      bestätigt — kein Merge. **Folge-Task:** One-Shot-Pfad für simple Formate
      (narration/import) im Rewrite bauen; bis dahin können nur case-based Formate
      durch `factory/cli/create_series.py` laufen. Nebenbefund desselben Laufs: der
      decomposed Pfad erzwingt die mode=narration-Vorgabe nicht (Kanon-Prompt kennt
      kein "kein Cast") — beim Bau des One-Shot-Pfads simple Formate dorthin ROUTEN
      statt den Kanon-Prompt aufzurüsten.

**TEST-GATE 2** ✅ — 77/77 Tests grün (23 neu + 54 Regression):
- Deterministisch: T2.8-Dup-Check fängt einen künstlich duplizierten Turning-Point;
  Band-Gate (T2.6) lehnt eine Episode mit 3 üppigen + 1 Stub-Szene ab; Dispatcher routet
  ein scope-loses Finding *nicht* in den Full-Rebuild (Regression gegen §9 Falle #3);
  Truncation-Erkennung greift bei abgeschnittenem Output.
- Smoke: **Mini-Serie** (2–3 Episoden) end-to-end erzeugen; manuell prüfen — jeder
  Turning-Point genau einmal, kein Doppel-Climax, keine fehlende Auflösung.
- Checkpoint: Lauf killen, identisch neu starten → nur Fehlendes wird regeneriert.
- **§10.6-Testergebnis liegt schriftlich vor** (ein Pfad oder zwei).
- **Fallen ausgeschlossen:** #3 (scope-split), #4 (zentrale Allokation), #7 (kleine Calls).

---

## Phase 3 — Stage B: Skripte schreiben

**Ziel:** section-Liste → TTS-fertiger Text, mit **einer** Kontinuitätsstrategie statt
drei (§10.1 revidiert: lean two).

- [x] **T3.1 — Eine Kontinuitätsstrategie (§10.1 lean two).** Der section-Call sieht den
      *vollen Episodenplan* + eine laufende Zusammenfassung der Vorepisoden (Season-Fold).
      **Kein** separater Beat-Layer, **kein** schweres Review. Jede fertige section sofort
      geschrieben + Status als State-Record (resumbar). → `authoring/script_writer.py`.
- [x] **T3.2 — Wortbudget mit Toleranz (§ Stage B, §14).** Neutrale Längenmetrik, Band ±15%.
      **Overlength retryt nie** (akzeptieren + Warnung); nur too-short retryt. Safe-Attempt
      innerhalb 1.5× Toleranz sofort akzeptieren. → `authoring/word_budget.py`.
- [x] **T3.3 — Deterministische Hazard-Checks (§ Stage B).** Narrator-Leaks, buchstabenlose
      „Rede", Platzhalter, Restmarkup, Fremdschrift mitten im Satz (sprach-aware: ZH erlaubt).
      Retrybar, fallback-safe, erhöhen badness. → `authoring/hazard.py`.
- [x] **T3.4 — Phrase-Guard cross-episode (§ Stage B, Season-Fold).** N-Gramme über
      geschriebene Episoden, schlimmste als „avoid"-Block zurückgespeist; Eigennamen
      ausgenommen; menschenlesbarer Report. → `authoring/phrase_guard.py`.
- [x] **T3.5 — Lean Post-Check (§10.1).** Nur Spoiler + Fakt-Konsistenz, billiges Modell,
      gated auf `needs_continuity_review`; fehlt die Capability ⇒ kein stilles „clean".
      → `script_writer.py::review_episode`.
- [x] **T3.6 — Light-vs-Heavy-Modell (§ Stage B).** sections → `tier="strong"`, Review →
      `tier="cheap"`. → via `Model.generate_structured(..., tier=...)`.

**TEST-GATE 3** ✅ — 97/97 Tests grün (20 neu + 77 Regression):
- Deterministisch: Hazard-Checks fangen je ein synthetisches Beispiel pro Klasse;
  Phrase-Guard findet ein injiziertes wiederholtes N-Gramm, ignoriert einen Eigennamen;
  Overlength triggert *keinen* Retry, too-short schon.
- Smoke: `check`-Äquivalent auf der Mini-Serie; ein Skript vertonungsfertig durchziehen.
- Resume: Lauf mitten in Episode killen → Neustart überspringt geschriebene Parts.
- **Fallen ausgeschlossen:** #1 (Review schreibt bei „nicht gelaufen" keine leere „clean"-
  Cache), #7.

---

## Phase 4 — Stage C: Vertonung (Media-Pfad — **adaptieren, nicht neuschreiben**)

**Ziel:** Skript → gemasterte Audio + Seitenartefakte. **Der bewährte Audio-Kern aus
`fabrik/audio/` (`pipeline.py`, `tts_backends.py`) wird wiederverwendet** — er erfüllt die
§Stage-C-Invarianten bereits (Point-of-no-Return, Chunk-Normalisierung, Voice-Manifest-Guard,
Self-Healing, Cloud-Batching). Neu ist nur ein dünner **Adapter** in `factory/media/`.

*Reuse-1:1 (kein Neuschrieb — nur nach `factory/media/` einbinden/verschieben):*
`pipeline.py::{postprocess_chunk, normalize_chunk_loudness, master_episode,
merge_parts_to_episode, load_part_offsets, tag_mp3}` + `tts_backends.py` (rest/gradio/kokoro,
`resolve_voice`, Batching). Diese tragen bereits T4.2, T4.3, T4.6.

*Kopiert nach `factory/` (voll entkoppelt, kein Import auf `fabrik/`):*
`factory/core/textproc.py` (stdlib, getestet), `factory/media/audio_pipeline.py` +
`factory/media/tts_backends.py` (Provenance-Header, brauchen venv → nicht unit-getestet,
Syntax via py_compile geprüft).

*Neu (der Adapter — die einzige zu bauende + testbare Logik):*

- [x] **T4.1 — Record→Jobs-Übersetzung.** Neues Series-Record + Episode-Script → Chunk-Jobs
      (Voice/Style/Speed/Seed pro Chunk, **NARRATOR-Style-Override**, unsprechbare Chunks →
      Stille). Ersetzt `podcast_maker.build_drama_jobs`. → `factory/media/jobs.py`.
- [x] **T4.4 — State-Bridge für Chunk-Checkpoints (§10.3).** Resume kommt aus dem State-Record
      (COMPLETE), nicht aus WAV-Existenz; Chunk-Pfade im Checkpoint. Merge in stabiler
      Reihenfolge. → `factory/media/voicing.py::voice_episode`.
- [x] **T4.5 — Voice-Manifest-Guard an neues Record hängen (§9 Falle #5).** Vergleich +
      Hard-Stop vor jedem Dateizugriff bei Voice/Speed/Seed-Drift; No-op ohne Baseline.
      → `factory/media/voice_manifest.py`.
- [x] **T4.7 — Queue-Anbindung (§10.7).** Chunk-Rendering über die *eine* Work-Queue;
      stabile Merge-Reihenfolge nach Job-/Episoden-Index. → `voicing.py` (queue.map).

**TEST-GATE 4** ✅ — 111/111 Tests grün (14 neu + 97 Regression); nur der Adapter getestet:
- Record→Jobs mit NARRATOR-Override, Voice-Auflösung, Stille für unsprechbare Chunks, Chunking.
- Voice-Drift (geänderte Voice) → Hard-Stop **vor** jedem `backend.render` (0 Renders).
- Resume: zweiter Lauf rendert 0 Chunks (alles aus State+Checkpoint).
- Stabile Merge-Reihenfolge trotz paralleler Queue; Episoden in Index-Reihenfolge.
- **Fallen ausgeschlossen:** #2 (Point-of-no-Return — vom kopierten Kern), #5 (Manifest-Drift
  — Guard am neuen Record).
- Offen für echtes Setup (außerhalb dieser Umgebung): eine Episode real vertonen (venv+TTS).

---

## Phase 5 — Stage D: Bild- & Sound-Assets (**adaptieren, nicht neuschreiben**)

**Ziel:** Bilder + kuratierte Sounds. Alles „nice-to-have" — ein Fehler killt nie die Episode.
Wie Stage C §9-„incidental": der bestehende Code aus `fabrik/` (Bild-Prompt-CLIs, SFX-Plan,
Ambience, Cross-Series-Reuse) wird wiederverwendet; neu ist nur der Adapter aufs Series-Record.
Die Tasks unten beschreiben die zu *erhaltende Logik* — gebaut wird davon nur die Übersetzung.

- [x] **T5.1 — Prompt-Stufe getrennt von Render-Stufe (§ Stage D).** Render hängt an
      `has_render`, nicht an `has_prompt` — ein neu ergänzter Bildschlüssel erreicht den
      Render trotz existierender Prompt-Dateien. → `factory/media/prompt_render.py`.
- [x] **T5.2 — Emotion-Varianten cost-capped (§ Stage D, §14).** Keyword-Klassifikation
      (Priorität wie Altsystem), Top-4 pro Rolle, fehlende → neutrales Portrait.
      → `factory/media/emotion_variants.py`.
- [x] **T5.3 — Cross-Series-Reuse, human-gated (§ Stage D).** Exact-Hash → reuse; Fuzzy ≥
      confident → auto-reuse; Band [audit, confident) → **Near-Miss-Audit** (Mensch); darunter
      neu. → `factory/media/asset_reuse.py`.
- [x] **T5.4 — SFX-Plan mit wachsender Palette (§ Stage D, Season-Fold).** `grow_palette`
      (früheste Definition gewinnt) + `reconcile_cues`: adressiert per Position, stale Plan
      (Cue-Text-Mismatch) → **kein Sound, nie der falsche**. → `factory/media/sfx_plan.py`.
- [~] **T5.5 — Ambience per-Mood (§ Stage D).** Aus `fabrik/cli/location_ambience.py`
      adaptieren (Paid-Step, ElevenLabs) — Struktur wie SFX-Plan; Mood-Wechsel bricht
      Location-Span (in Stage C bereits als Derivat). Adapter analog, wenn benötigt.
- [~] **T5.6 — Paid-Steps nie automatisch (§ Stage D).** Design-Regel, keine neue Logik:
      kostenpflichtige Generierung (SFX-Assets, Ambience, Cover) läuft nie automatisch,
      fertige Assets werden geskippt. Wird in der Orchestrierung/UI (Phase 7) verdrahtet.

**TEST-GATE 5** ✅ — 127/127 Tests grün (16 neu + 111 Regression):
- Neu ergänzter Bildschlüssel erreicht den Render trotz existierender Prompt-Datei.
- Stale SFX-Plan (Cue-Text geändert) platziert *keinen* Sound; verworfener Cue nicht platziert.
- Emotion-Cap hält bei Top-4, seltenste Emotion fällt raus, neutraler Fallback.
- Fuzzy-Reuse: exact/auto-reuse/audit/new sauber getrennt; Mid-Band geht zum Menschen.
- Offen (Paid/Media, außerhalb dieser Umgebung): echte Bild-/Sound-Generierung, T5.5-Ambience.

---

## Phase 6 — Stage E: Packen & Ausliefern (**adaptieren, nicht neuschreiben**)

Ebenfalls §9-„incidental": Anthologie-Merge (ffmpeg stream-copy), Upload-Index und
Teaser-Highlights existieren in `fabrik/` und werden wiederverwendet; neu nur der Adapter.


- [x] **T6.1 — Anthology-Merge (§ Stage E).** Kapitel = kumulative Offsets (deterministisch);
      Stream-Copy via injiziertem `merge_fn` (ffmpeg in Produktion), stabile Index-Reihenfolge.
      → `factory/media/anthology.py`.
- [x] **T6.2 — Upload-Index (§ Stage E).** Titel/Beschreibung/Kapitelliste + *spoiler-freie*
      Publikumsfrage; deterministischer `question_leaks_twist`-Guard flaggt Twist-Leaks gegen
      die Kanon-Auflösungen. → `factory/media/upload_index.py`.
- [x] **T6.3 — Teaser-Highlights (§ Stage E).** Modell wählt Cue-*Indizes*; Code rechnet ms
      aus Cue-Grenzen, klemmt Out-of-Range (nie halluzinierte Zeit), snappt auf Satzgrenzen,
      deckelt auf max 3. → `factory/media/highlights.py`.

**TEST-GATE 6** ✅ — 138/138 Tests grün (11 neu + 127 Regression):
- Highlight-Indizes außerhalb des Bereichs werden geklemmt, nie halluziniert; Reihenfolge
  normalisiert; max_n gedeckelt.
- Anthologie-Kapitel kumulativ korrekt; Merge in stabiler Index-Reihenfolge (Stream-Copy injiziert).
- Upload-Index enthält Frage + Kapitel; Spoiler-Guard fängt eine Twist-verratende Frage.
- Offen (Media, außerhalb dieser Umgebung): echter ffmpeg-Stream-Copy-Merge.

---

## Phase 7 — Orchestrierung & End-to-End

**Ziel:** die dünne Steuerschicht (aktuell Cockpit + optional Cloud-GPU), die benannte,
resumbare Stufen fährt und Status aus dem Dateisystem liest.

- [x] **T7.1 — Benannte, resumbare Stufen (§8).** `run_concept`/`run_scripts`/`run_audio`,
      jede resumt aus ihren Outputs (Stage-State + Unit-State); Outputs in physischen
      Stage-Ordnern. → `factory/orchestration/pipeline.py`.
- [x] **T7.2 — Parallel pro Serie, exklusiver Lock auf geteiltem Gerät (§8).** `DeviceLock`
      (fcntl.flock) um die Audio-Stufe; Authoring braucht keinen Lock. → `orchestration/locks.py`.
- [x] **T7.3 — Status aus Dateisystem (§8).** `series_status` leitet pro Stufe/Episode „done"
      rein aus dem State-Record ab. → `factory/orchestration/status.py`.
- [x] **T7.4 — Cockpit-Isolation (§8).** `Cockpit.adopt` entkoppelt die aktive Serie vom
      globalen Pointer. → `factory/orchestration/cockpit.py`.
- [x] **T7.5 — Missing-⇒-default überall (§8, §9 Falle #6).** `get_flag`: fehlender Key ⇒
      Default, vorhandenes `False`/`0` gilt. → `factory/orchestration/config.py`.

**TEST-GATE 7** ✅ — 144/144 Tests grün (6 neu + 138 Regression):
- **Voller E2E-Durchlauf A→B→C** durch die Steuerschicht auf echtem Workspace (FakeModel +
  FakeBackend): alle Stage-Outputs in ihren physischen Ordnern, Status aus State-Record.
- **Idempotenz/Resume:** zweiter Durchlauf → 0 Modell-Calls, 0 Backend-Renders.
- **Device-Lock serialisiert** zwei gleichzeitige TTS-Halter (keine Verschachtelung).
- **Cockpit-Isolation:** zwei Instanzen, eine adoptiert eigene Serie, globaler Pointer unberührt.
- **Missing⇒Default:** fehlendes Flag nimmt Default, invertiert keinen CLI-Default.
- Offen (nur mit echtem Setup): Cockpit-Durchklick im WebUI, echte Vertonung.

> **Meilenstein:** Nach Gate 7 existiert das bewiesene System (§1–8) als sauberer Rewrite
> mit den §10-Revisionen eingebaut, §7.1-Migration und §14-Konstanten. Das ist der
> vereinbarte Umfang. §12/§13 sind ab hier optional und **gegatet**.

---

## Phase 8 — GEGATET: §12 Charaktertiefe & §13 Seams

> **Startet nur, wenn der §12-Falsifikationstest grün ist.** Nicht vorher Struktur bauen.

- [ ] **T8.0 — §12-Falsifikationstest (das Gate).** Eine Episode, 2–3 Hauptfiguren,
      handgeschriebener spine+signature in den *bestehenden* section-Writer injiziert
      (kein Arc, keine Allokation, keine neue Pipeline). Regenerieren, gegen Baseline
      vergleichen: „stated motive" vs. „inferred motive" zählen + Blind-A/B.
      **Kill-Kriterium:** kein deutlicher Rückgang *und* keine Hörer-Präferenz → §12
      verworfen, Phase 8 endet hier. Ergebnis dokumentieren.

*Nur bei grünem Gate:*

- [ ] **T8.1 — Ein Character-Record (§12.3, §12.5).** Frozen core (want/need/wound/self-lie
      + signature) *und* epistemische Wissensslice in **einem** Record — nie zwei Modelle.
- [ ] **T8.2 — Character-Tiering (§12.5).** Protagonist + wenige Schlüsselfiguren: voller
      spine+arc; funktionale Rollen: minimaler spine, kein arc.
- [ ] **T8.3 — Seam-Contracts (§13).** Section- und Episode-Seams als frozen structured
      data neben der Prosa; deterministische Seam-Checks (Zeit monoton, Character-Sets
      konsistent, kein carried_facts-Widerspruch) — retrybar zur Cast-Zeit.
- [ ] **T8.4 — Arc-Layer als Pipeline (§12.3).** Plot/Motif-Spine in einem Call, dann
      **ein Call pro Character-Arc, seriell im Season-Fold** — sonst trifft ein einzelner
      Arc-Call die Truncation-Decke (§10.8). Internal Turning-Points an Episoden alloziert
      wie Plot-Points (§10.2-Disziplin).
- [ ] **T8.5 — Writing-Time-Direktive (§12.4).** spine+signature injiziert mit „dramatize,
      do not state"; Innate-Guard flaggt *stated motive* wie Narrator-Leaks.
- [ ] **T8.6 — Nicht-forcierte Kopplung (§12.3).** Wenn Character-Beat und Plot-Point nicht
      alignen: (a) Minor-Tension, (b) Nachbarepisode, (c) Figur bleibt statisch. Nie
      erzwingen.

**TEST-GATE 8**:
- T8.0 grün ist Vorbedingung (sonst kommt Phase 8 gar nicht so weit).
- Deterministisch: Seam-Checks fangen nicht-monotone Zeit / inkonsistente Character-Sets /
  carried_facts-Widerspruch; stated-motive-Guard flaggt „because he wanted…".
- Assembly (§13.5): benachbarte Seams matchen → Konkatenation, **keine** Regenerierung;
  ein Mismatch wird *gemeldet* (Marker), nie an der Assembly repariert.
- Smoke: Mini-Serie mit Tiefe, Blind-A/B gegen die Phase-3-Version.

---

## Anhang — Reihenfolge-Begründung in einem Satz

Fundament (das Interface) zuerst, weil §10.8 „die größte Reduktion inzidenteller
Komplexität" ist und alles darüber billiger macht; dann Modell→Validierung→Migration,
weil jede Stufe das Record braucht; dann Stage A, weil die zentrale Turning-Point-
Allokation der Kern-Insight ist, aus dem die meisten Qualitätsprobleme kommen, wenn man
ihn verletzt; B→C→D→E in Datenflussrichtung; Orchestrierung zuletzt, weil sie nur
benannte, schon getestete Stufen verdrahtet; §12/§13 ganz hinten und gegatet, weil sie
die einzige empirisch unbewiesene Hypothese im Blueprint sind.
