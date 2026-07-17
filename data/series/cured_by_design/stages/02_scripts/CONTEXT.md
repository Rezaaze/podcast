# Stage 02 — Skripte

## Inputs
- Layer 4: `../01_concept/output/episodes.json` (Episoden, Sections, case,
  Wortbudgets, Stimmen)
- Layer 3 (Serie): `../../references/PROMPT_TEMPLATE.md` — das
  Skript-Prompt dieser Serie
- Bei `use_beats`: eigene `output/ep<N>_BEATS.txt` der Vorepisode
  (Kontinuität)

## Process
Pro Section ein Claude-Call (Retry mit Fehler-Feedback, Wortbudget-
Validierung, Best-Effort-Fallback). Optional Beats vorab und Episode-Review
(`--fix`) danach. Details: `fabrik/writing/CLAUDE.md`.
Ausgeführt von: `python3 -m fabrik.cli.generate_episode N|all --series cured_by_design [--fix]`

## Outputs
- `output/ep<N>.txt` — Skript mit `--- PART k ---`-Markern
- `output/ep<N>_META.txt` — Titel/Beschreibung (ID3/Upload)
- `output/ep<N>_BEATS.txt`, `_BEATS_REVIEW.txt`, `_REVIEW.txt` (optional)
- `output/ANTHOLOGY_META.txt` (Serien-Meta, bei Anthologie-Formaten)

## Review-Gate: Skript-Feinschliff (letzter Halt vor der Vertonung)

Skripte sind reine Textdateien. Dies ist die letzte Stelle, an der eine
Korrektur nichts kostet — nach `batch` heißt jede Änderung: neu vertonen.
Wer hier editiert (Mensch oder Agent), hält sich an vier Regeln.

### 1. Format ist heilig (sonst crasht der TTS-Parser)
- `--- PART k ---`-Marker und die Tag-Zeilen `[SPEAKER | style: ... |
  speed: ...]` strukturell NIE anfassen. Sprechernamen nur aus dem
  `voices`-Block der episodes.json — kein neuer Name, keine Umbenennung.
- Gesprochenen Text umschreiben, kürzen, zuspitzen: frei und erwünscht.
- `[NOTE: ...]`-Zeilen (language_course) bleiben stehen — sie werden vor
  TTS gestrippt und der nächsten Section wieder vorgelegt.
- Gelöschte PART-Dateien/-Abschnitte werden beim Re-Run neu generiert;
  existierende bleiben unangetastet.

### 2. SFX-Cues möglichst unangetastet lassen
- `[SFX: ...]`-Cues sind über (Episode, Part, n-ter Cue) UND ihren Text
  im `SFX_PLAN.json` adressiert. Wer einen Cue umformuliert, löscht oder
  verschiebt, invalidiert den Plan-Eintrag — der Sound fällt still ins
  Alt-Verhalten (podcast_maker warnt, platziert aber nie den falschen).
- Nach absichtlichen Cue-Änderungen: `sfx_plan --force` (kostet die
  Handkorrekturen am Plan) oder inkrementell, wenn nur Cues dazukamen.

### 3. Reihenfolge einhalten
Skripte polieren → `sfx_plan` → `batch`. Editiere kein Skript, dessen MP3
in `../03_audio/output/` schon existiert, ohne die MP3 danach zu verwerfen
— sonst hörst du die alte Fassung. (`generate_episode all` startet
sfx_plan+batch automatisch; für dieses Review-Gate also episodenweise
arbeiten oder das WebUI nutzen, wo batch noch nicht lief.)

### 4. Die Review-Caches lügen nach Hand-Edits
`ep<N>_REVIEW.txt` / `_BEATS_REVIEW.txt` beschreiben das Skript VOR deiner
Änderung — nach dem Edit nicht mehr als Wahrheit lesen. Harmlos (der
Review läuft ohne `--force` nicht neu), nur nicht drauf verlassen.

## Kontinuität prüfen (auch über Staffeln)

Der Canon dieser Serie ist NICHT die Prosa, sondern:
`../01_concept/output/episodes.json` → `case`-Block (`solution`,
`objective_facts`, `character_knowledge`) + alle `output/ep<N>_META.txt`.
Das ist die „Wahrheit, der kein Skript widersprechen darf".

**Mehrstaffel:** Ist in episodes.json `previous_season: "<slug>"` gesetzt,
gehört der destillierte Canon jener Serie dazu —
`data/series/<slug>/stages/01_concept/output/episodes.json` (nur den
`case`-Block) + deren `ep<N>_META.txt`. Zeigt die genannte Serie ihrerseits
auf eine Vorgängerin, der Kette folgen; in der Praxis reichen für
Kontinuität die 1–2 unmittelbaren Vorstaffeln (ältere nur, wenn ein Thread
ausdrücklich weit zurückgreift).

Beim Reviewen auf: widersprochene `objective_facts`/`solution`, offene
Threads der Vorstaffel nicht aufgegriffen ODER fälschlich neu aufgelöst,
Namen/Biografien/Stimmen-Casting inkonsistent.

**Budget-/Zuverlässigkeitsregel (hart):** immer nur EINE Staffel Prosa am
Stück reviewen (~115 K Tokens). Vorstaffeln NUR als destillierter Canon
(~15 K/Staffel) laden, Roh-`ep<N>.txt` der Vorstaffel nur punktuell öffnen,
wenn eine konkrete Zeile verifiziert werden muss. Zwei volle Staffeln Prosa
auf einmal → der Review beginnt, feine Widersprüche zu übersehen.
