# MWP-Umbau: Podcast-Fabrik als Model Workspace Protocol

Detaillierter Umbauplan nach dem Paper *"Interpretable Context Methodology:
Folder Structure as Agent Architecture"* (Van Clief & McDermott).
Beschlossene Rahmenbedingungen (13.07.2026):

- **Scope: beides** — (A) Produktions-Pipeline: jeder Serien-Ordner wird ein
  MWP-Workspace mit nummerierten Stages und CONTEXT.md-Verträgen; (B)
  Repo-Kontext: das monolithische 732-Zeilen-CLAUDE.md wird in geschichtete
  Kontext-Dateien aufgeteilt.
- **Review-Gates: optional pro Lauf** — die Stage-Grenzen sind natürliche
  Haltepunkte, der Ein-Klick-Durchlauf im WebUI bleibt erhalten.
- **Kompatibilität: harter Umbau** — der Code unterstützt NUR das neue
  Layout. Alte Serien werden nicht migriert, sondern nach
  `data/archive/pre_mwp/` verschoben und ignoriert.
- **⚠️ Laufender Render:** `chain_of_custody` rendert aktuell die letzte
  Stage. Phasen 0–2 sind gefahrlos parallel möglich (reine Doku/Design,
  keine Pfadänderungen). **Phase 3+ darf erst starten, wenn der Render
  abgeschlossen ist** (Check: `ANTHOLOGY_COMPLETE.mp3` bzw. alle
  Episoden-MP3s vorhanden, kein laufender batch.py/podcast_maker-Prozess).

## Ehrliche Einordnung: was der Umbau bringt (und was nicht)

Die Kontext-Scopierung, die MWP über Ordner erreicht, macht
`build_section_prompt()` heute schon programmatisch (jede Section sieht nur
Template + Case + Beats + vorige Section — kein 40k-Monolith). Der reale
Gewinn des Umbaus liegt woanders:

1. **Editierbarkeit:** Prompts werden pro Serie kopiert statt global gelesen
   → eine Serie kann ihren Ton ändern, ohne `templates/` für alle zu ändern
   ("configure the factory").
2. **Inspizierbarkeit:** jede Stage dokumentiert sich selbst (CONTEXT.md =
   Vertrag), Zwischenstände liegen als lesbare Dateien an vorhersagbaren
   Orten.
3. **Review-Gates:** definierte Haltepunkte, an denen editiert werden kann
   und die nächste Stage einfach liest, was da liegt.
4. **Layer-3/4-Trennung:** stabile Regeln (references/) vs. Lauf-Artefakte
   (output/) — auch für Claude-Code-Sessions im Repo selbst.

Nicht Ziel: die Python-Orchestrierung durch einen "Agent liest Ordner"
ersetzen. Die CLIs bleiben die Maschine; MWP strukturiert, WAS sie lesen
und WOHIN sie schreiben.

## Ziel-Layout eines Serien-Workspace

```
data/series/<slug>/
├── CLAUDE.md                  Layer 0 — Identität: was dieser Workspace ist,
│                              welcher Template-Typ, wo was liegt (~40 Zeilen)
├── CONTEXT.md                 Layer 1 — Routing: welche Stage macht was,
│                              Reihenfolge, Status-Konvention
├── stages/
│   ├── 01_concept/
│   │   ├── CONTEXT.md         Layer 2 — Vertrag: Inputs (Topic-Brief,
│   │   │                      figure_history), Process (create_series),
│   │   │                      Outputs (episodes.json)
│   │   └── output/
│   │       └── episodes.json  ← Single Source of Truth, zieht hierher um
│   ├── 02_scripts/
│   │   ├── CONTEXT.md         Vertrag: liest 01/output + references/,
│   │   │                      schreibt epN.txt, BEATS, REVIEWs
│   │   └── output/            ← ersetzt scripts/
│   ├── 03_audio/
│   │   ├── CONTEXT.md         Vertrag: liest 02/output + episodes.json,
│   │   │                      schreibt MP3/SRT/SPEAKERS/…, Checkpoints
│   │   └── output/            ← ersetzt output/ (inkl. .checkpoints/)
│   └── 04_visuals/
│       ├── CONTEXT.md         Vertrag: Porträts, Orte, Cover
│       └── output/
│           ├── characters/    ← ersetzt characters/
│           └── locations/     ← ersetzt locations/
├── references/                Layer 3 — die "Fabrik", stabil über alle Läufe:
│   ├── PROMPT_TEMPLATE.md     bei Serien-Erstellung aus templates/<t>/ KOPIERT
│   ├── EPISODES_CREATOR_PROMPT.md  (Doku, womit die Serie erzeugt wurde)
│   └── voice_notes.md         Accent-Casting-Regeln, Stimmen-Entscheidungen
└── assets/                    intro.mp3/outro.mp3/transition.mp3 (optional)
```

Globale Layer-3-Ressourcen bleiben global: `templates/` (die Master-Vorlagen,
Quelle der Kopien), `data/voices/`, `data/figure_history.json`.

**Kernentscheidung dabei:** `02_scripts` liest den Prompt aus
`references/PROMPT_TEMPLATE.md` der SERIE, nicht mehr aus `templates/<t>/`.
Master-Template-Verbesserungen erreichen nur neue Serien — genau das
Reproduzierbarkeits-Verhalten, das MWP will.

## Ziel-Layout Repo-Kontext (Scope B)

Claude Code lädt verschachtelte CLAUDE.md-Dateien automatisch, wenn in dem
Bereich gearbeitet wird — das ist exakt der Layer-2-Mechanismus des Papers.

```
CLAUDE.md                 Layer 0+1: was das Projekt ist, Layout-Tabelle,
                          Kommandos, Routing ("Audio-Fragen → fabrik/audio/"),
                          die 3 wichtigsten Gotchas. Ziel: ≤150 Zeilen.
fabrik/core/CLAUDE.md     episodes.json-Schema, validate_data, claude_cli-Regeln
fabrik/writing/CLAUDE.md  Section-Generierung, Retry/Fallback, Beats, Review
fabrik/audio/CLAUDE.md    Pipeline, Backends, Checkpoints, Post-Merge-Safety,
                          Voice-Manifest, Timelines (SPEAKERS/LOCATIONS/SRT)
fabrik/cli/CLAUDE.md      Entry-Points, Flags, Reihenfolge, Venv-Anforderungen
webui/CLAUDE.md           COMMANDS-Registry, JobRegistry/SSE, Lolfi-Kopplung,
                          Template-Autoreload-Gotcha, collectParams-Checkbox-Bug
templates/CLAUDE.md       Template-Anatomie, Platzhalter, Accent-Casting-Regel,
                          section_words-Gap-Lektion
```

Regel aus dem Paper (Edit-Source-Prinzip): eine Info lebt an genau EINEM Ort;
das Root-CLAUDE.md verweist, statt zu wiederholen.

---

## Phasen und Tasks

Jeder Task ist bewusst klein (eine Session, ein Commit, einzeln testbar).
Abhängigkeiten stehen dabei; innerhalb einer Phase gilt die Reihenfolge.

### Phase 0 — Absichern (sofort, gefahrlos bei laufendem Render)

- [x] **T0.1 Branch + Sicherung.** Erledigt 13.07.: Snapshot-Commit
      `24221db` auf `main`, Branch `mwp-umbau` angelegt — der gesamte
      Umbau passiert auf dem Branch.
- [x] **T0.2 Render-Wächter definieren.** Erledigt 13.07.: Kriterium war
      "kein laufender `batch.py`/`podcast_maker`-Prozess UND
      chain_of_custody vollständig" — beides geprüft und ERFÜLLT (10/10
      MP3s, keine offenen Checkpoints, kein Prozess). **Die Phase-3-Sperre
      ist damit aufgehoben.**
- [x] **T0.3 Alt-Serien inventarisieren.** Erledigt 13.07.:
      `docs/pre-mwp-serien-inventur.md` — 3 fertige soap_opera-Serien,
      2 unfertige, 1 leerer Test-Rest.

### Phase 1 — Repo-Kontext schichten (Scope B; gefahrlos, reine .md-Arbeit)

- [x] **T1.1 CLAUDE.md-Inventur.** Erledigt 13.07. — direkt beim Verteilen
      gemacht (voller Alt-Inhalt war im Session-Kontext), keine separate
      Wegwerf-Tabelle nötig.
- [x] **T1.2 Bereichs-CLAUDE.md schreiben.** Erledigt 13.07.: sechs Dateien
      (fabrik/core 74 Z., fabrik/writing 133 Z., fabrik/audio 136 Z.,
      fabrik/cli 118 Z., webui 79 Z., templates 70 Z.) — alle
      Produktions-Lektionen verschoben, nicht kopiert.
- [x] **T1.3 Root-CLAUDE.md eingedampft** auf 96 Zeilen (Ziel ≤150):
      Beschreibung, Layout-Tabelle, Kommandos, Routing-Tabelle,
      Top-Gotchas + Hinweis auf den laufenden MWP-Umbau.
- [ ] **T1.4 Gegenprobe.** In einer FRISCHEN Claude-Code-Session je eine
      typische Frage pro Bereich stellen (z. B. "warum retried
      validate_parts nicht bei Überlänge?") und prüfen, dass die Antwort
      aus dem Bereichs-CLAUDE.md kommt. (Selbst-Abgleich beim Schreiben
      ist erfolgt; der Frische-Session-Test steht noch aus — am besten
      einfach beim nächsten normalen Arbeiten beobachten.)

### Phase 2 — Workspace-Design (Scope A, noch kein Code)

- [x] **T2.1 Stage-Verträge schreiben.** Erledigt 13.07.:
      `templates/_workspace/` mit CLAUDE.md, CONTEXT.md und vier
      stage_NN_CONTEXT.md (Inputs/Process/Outputs + Review-Gate-Hinweis,
      Platzhalter {{SLUG}}/{{TEMPLATE}}/{{MODE}}/{{SERIES_TITLE}}/
      {{EPISODES_TOTAL}}/{{CREATED}}). Ursprünglicher Task-Text: Vier CONTEXT.md-Vorlagen (Inputs /
      Process / Outputs im Format des Papers, Abschnitt 3.3) + Layer-0/1-
      Vorlagen für den Workspace-Root. Ablage als neue Dateien
      `templates/_workspace/{CLAUDE.md,CONTEXT.md,stage_01…04_CONTEXT.md}`
      mit `{{PLACEHOLDER}}`-Konvention wie die bestehenden Templates.
      Wichtig: die Verträge beschreiben auch die MECHANIK ehrlich ("dieser
      Output wird von `python3 -m fabrik.cli.generate_episode` erzeugt"),
      damit sie als Doku für Menschen taugen.
- [x] **T2.2 Pfad-Inventur.** Erledigt 13.07.: `docs/mwp-pfad-inventur.md`.
      Zentraler Befund: fast alles läuft durch `paths.py::Series` — der
      Umbau ist kleiner als befürchtet. Lolfi hat 3 relevante
      Konsum-Stellen. Ursprünglicher Task-Text: Grep über
      `fabrik/`, `webui/`, `~/Downloads/Lolfi/` nach allen Vorkommen von
      `episodes.json`, `scripts/`, `output/`, `characters/`, `locations/`,
      `intro.mp3`, `.checkpoints`, `.voices_manifest` etc. Ergebnis: Tabelle
      Datei → Funktion → alter Pfad → neuer Pfad in
      `docs/mwp-pfad-inventur.md`. **Dieses Dokument ist die Checkliste für
      Phase 3–5**; nichts wird umgebaut, was hier nicht steht.
- [x] **T2.3 Review-Gate-Konzept festschreiben.** Erledigt 13.07.: steht in
      den Stage-Verträgen (Abschnitt "Review-Gate danach" je Stage) + in
      `templates/_workspace/CONTEXT.md`. Ursprünglicher Task-Text: (klein halten): Gates =
      die vorhandenen WebUI-Schritt-Karten + "Ordner öffnen"-Links pro
      Stage-Output. Kein Approval-Mechanismus, kein Marker-File — der
      Mensch editiert Dateien in `stages/NN_*/output/`, die nächste Stage
      liest, was da liegt (das tut die Pipeline durch ihre Resume-Logik
      heute schon: Teil-Dateien werden übernommen). Optionaler späterer
      Ausbau (T7.x) notieren, nicht bauen.

### Phase 3 — Core-Umbau (⛔ erst nach Render-Ende, T0.2)

Reihenfolge so gewählt, dass nach jedem Task ein lauffähiger Zustand mit
Smoke-Test existiert. Test-Vehikel: eine Mini-Serie (soap_opera, 1 Episode,
~5 Minuten) namens `mwp_smoke`, nach jedem Task neu erzeugt/weitergeführt.

- [ ] **T3.1 `fabrik/core/paths.py` auf neues Layout.** Neue Funktionen
      (`stage_dir(slug, n)`, `concept_output()`, `scripts_dir()` →
      `stages/02_scripts/output/`, …), alte Pfad-Helfer ersetzen — Aufrufer
      kompilieren weiter, weil nur die Rückgabepfade wechseln. Hier NUR
      paths.py + `fabrik/core/config.py` (episodes.json-Fundort), noch
      keine Verhaltensänderung sonst.
- [ ] **T3.2 `create_series.py` scaffoldet den Workspace.** Nach
      erfolgreicher Generierung: `stages/`-Baum anlegen, CONTEXT.md-Dateien
      aus `templates/_workspace/` befüllen (T2.1), `PROMPT_TEMPLATE.md` +
      `EPISODES_CREATOR_PROMPT.md` nach `references/` kopieren,
      episodes.json nach `stages/01_concept/output/`. Smoke-Test:
      `mwp_smoke` erzeugen, Baum von Hand prüfen.
- [ ] **T3.3 `script_writer.py` liest aus dem Workspace.** Prompt-Template
      aus `references/PROMPT_TEMPLATE.md` statt `templates/<t>/`; Skripte,
      BEATS, REVIEWs nach `stages/02_scripts/output/`. Smoke-Test: Episode 1
      von `mwp_smoke` generieren, Resume-Verhalten prüfen (Datei anfassen,
      erneut laufen lassen).
- [ ] **T3.4 `import_story.py` nachziehen** — gleiche Scaffold- und
      Ablage-Logik (kleiner Task, hängt nur an T3.2/T3.3).
- [ ] **T3.5 Audio-Pipeline umziehen.** `podcast_maker.py`, `batch.py`,
      `fabrik/audio/pipeline.py`: Skript-Quelle = `stages/02_scripts/output/`,
      alles Gerenderte (MP3, SRT, SPEAKERS, LOCATIONS, CHAPTERS,
      UPLOAD_INDEX, `.checkpoints/`, `.cues/`, `.voices_manifest.json`,
      `_PART_OFFSETS.json`) nach `stages/03_audio/output/`; `intro.mp3`
      etc. aus `assets/`. Smoke-Test: `mwp_smoke` vertonen (lokaler TTS),
      Checkpoint-Resume prüfen (Prozess mittendrin killen, neu starten).
- [ ] **T3.6 Visual-CLIs umziehen.** `character_prompts.py`,
      `location_prompts.py`, `cover_art.py` → `stages/04_visuals/output/`.
      Smoke-Test: Prompts-only-Lauf (ohne OPENAI_API_KEY).
- [ ] **T3.7 Restgrep gegen die Pfad-Inventur (T2.2).** Jede Zeile der
      Inventur abhaken; `history.py`, `textproc.py` etc. auf übersehene
      Pfadannahmen prüfen. Erst wenn die Tabelle leer ist, gilt Phase 3
      als fertig.

### Phase 4 — WebUI nachziehen

- [ ] **T4.1 `webui/status.py`** auf neue Pfade (Skript-/Audio-/Visual-
      Existenzchecks, `_list_podcast_episode_files`). Danach zeigen die
      Statuskarten für `mwp_smoke` wieder korrekt an.
- [ ] **T4.2 `webui/config.py` COMMANDS + `folders.py` + `prompt_blocks.py`**
      — Arbeitsverzeichnisse, "Ordner öffnen"-Ziele (jetzt pro Stage),
      Block-Erzeugung. Discard-Guard (`/api/pf/series/discard`) auf neues
      Layout: "keine Skripte/Outputs" heißt jetzt `stages/*/output/` leer.
- [ ] **T4.3 Stage-Karten als Review-Gates ausweisen** (T2.3): pro Stage
      ein "📂 Output prüfen"-Link; Texte klarstellen, dass zwischen den
      Schritten editiert werden darf. Kein neuer Mechanismus.
- [ ] **T4.4 WebUI-Durchklick-Test** mit `mwp_smoke`: Serie erstellen →
      Review-Panel → generieren → vertonen → Status/Logs — einmal komplett
      über die Oberfläche statt CLI.

### Phase 5 — Lolfi anbinden (separates Repo!)

- [ ] **T5.1 Pfad-Inventur-Einträge für `~/Downloads/Lolfi/lofi_system.py`**
      umsetzen: `characters/<ROLE>.png`, `locations/`, SPEAKERS/LOCATIONS/
      SUBS/CHAPTERS-JSONs, Episoden-MP3s — alle auf `stages/03_audio/output/`
      bzw. `stages/04_visuals/output/`. Test: ein `mwp_smoke`-Video rendern.

### Phase 6 — Abschluss

- [ ] **T6.1 End-to-End:** neue echte Serie (soap_opera, normale Länge)
      komplett durchziehen: erstellen → Skripte (--fix) → vertonen →
      Visuals → Lolfi-Video. Alles über WebUI.
- [ ] **T6.2 Alt-Serien wegräumen:** alle pre-MWP-Ordner (Inventur T0.3)
      nach `data/archive/pre_mwp/` verschieben, `LATEST` auf eine neue
      Serie zeigen lassen. (Vorher bestätigen, dass chain_of_custody
      fertig gerendert UND das Ergebnis gesichert/hochgeladen ist.)
- [ ] **T6.3 Doku finalisieren:** README, Root-CLAUDE.md (Kommandos/Layout
      auf neues Schema), `.gitignore` (`data/series/*/stages/*/output/`
      statt alter Muster — Achtung: episodes.json in 01_concept/output/
      muss GETRACKT bleiben, Negativ-Pattern nötig), dieses Dokument auf
      "umgesetzt" setzen.
- [ ] **T6.4 Merge** `mwp-umbau` → `main`.

### Phase 7 — Optionaler Ausbau (bewusst NICHT Teil des Umbaus)

Ideen aus dem Paper, erst nach stabilem Betrieb bewerten:

- **T7.1 Gate-Modus:** Checkbox "nach jeder Stage anhalten" im WebUI
  (Sequenz stoppt zwischen COMMANDS statt durchzulaufen).
- **T7.2 Edit-Source-Loop:** wiederkehrende manuelle Skript-Edits erkennen
  und als Vorschlag für `references/PROMPT_TEMPLATE.md`-Änderungen
  aufbereiten (Paper §6.3).
- **T7.3 Cross-Stage-Verify:** `Verify`-Abschnitt im Stage-Vertrag
  (Paper §6.2), z. B. "prüfe Skript gegen episodes.json-Case" — entspricht
  dem heutigen `--fix`-Review, könnte darüber formalisiert werden.

## Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Render läuft noch, Pfadänderung zerschießt Resume | Harte Sperre T0.2; Phase 3 erst nach Render-Ende; Umbau auf Branch |
| Vergessener Pfad-Konsument (Lolfi, cloud/, Hilfsskripte) | Pfad-Inventur T2.2 ist Pflicht-Checkliste, T3.7 hakt sie ab |
| .gitignore verliert episodes.json (neuer Ort unter output/) | Explizites Negativ-Pattern in T6.3, direkt nach T3.2 provisorisch setzen |
| WebUI/Pipeline divergieren mitten im Umbau | Phasen-Reihenfolge: WebUI (4) direkt nach Core (3), dazwischen nur CLI benutzen |
| Serien-Kopien der Templates veralten gegenüber Master | Gewollt (Reproduzierbarkeit); Master-Verbesserungen via neuer Serie |
