# Design: Beat-Schicht für die Skriptgenerierung

Status: **Implementiert** (`generation.use_beats`, opt-in, Default aus) —
siehe CLAUDE.md Abschnitt "Beat layer" für die verifizierte Endfassung.
Datum: 2026-07-12

Dieses Dokument hält den abgestimmten Umbau der Skriptgenerierung fest, bevor
Code entsteht. Es beschreibt den ganzen Bogen: die bestehende Logik-Absicherung
(Knowledge-Split), die neue Beat-Schicht dazwischen, und wie diese die alte
Section-Architektur vereinfacht.

---

## 1. Ausgangslage & Problem

### Was heute existiert

Die Generierung läuft dreistufig, aber zwei der Stufen sind vermischt:

1. **Bibel** (`create_series.py`): Ein Claude-Call erzeugt die ganze
   `episodes.json` inkl. `case`/`objective_facts`/`character_knowledge`
   (Knowledge-Split, siehe Abschnitt 2).
2. **Skript** (`script_writer.py::generate_episode`): iteriert
   `episode["sections"]` und generiert jede Section mit *einem* Claude-Call
   direkt zu fertigem, getaggtem Dialog (`build_section_prompt` →
   `call_claude_with_retry`).

Die `sections` sind bereits einzeilige Klartext-Beschreibungen einer Szene,
z.B.:

> `"Marcus gets the call at Voss Tower and gives a guarded, lawyer-shaped statement"`

Das ist ein **Beat-Keim** — grobe, logische, einfache Sprache. Aber er geht
ungeprüft direkt in die Dialoggenerierung.

### Die Section-Architektur ist ein Chunking-Werkzeug, keine Erzählstruktur

Die `sections` → `parts`-Hierarchie entstand ursprünglich für eine 90-min-
Einzelsprecher-Dokumentation über 4 Persönlichkeiten: Ein ~13.500-Wörter-
Monolog geht nicht in einem Schuss, also wurde in Sektionen + Parts zerlegt,
um jeden Call zu begrenzen und Tiefe zu erzwingen. Für die Doku war
"Section = Themenblock" und "Generierungs-Chunk" dasselbe.

Im Drama fällt das auseinander. Belege aus dem Code:

- soap_opera hat `parts_per_section: 1` — die Section *ist* dort schon eine
  Szene = eine Generierungseinheit; der Parts-Apparat ist flach.
- Eine dramatische Szene hat ihre eigene natürliche Länge (scharfe
  Konfrontation ~150 Wörter, langsames Abendessen ~600). Das feste
  `words_per_part_min/max` presst alle in dasselbe Korsett.

Daher stammt das ganze Reparatur-Arsenal: der Best-Effort-Fallback (siehe
`validate_parts` / `call_claude_with_retry`, Fälle mit 5 Versuchen um ein
Wort-Minimum oszillierend), `check_section_words_gaps`, `SECTION_WORDS_MIN_GAP`,
die `section_words`-Overrides. Alles Pflaster auf demselben Mismatch: ein
Längen-Erzwingungs-Mechanismus trifft auf Inhalt, der sich nicht gleichmäßig
portionieren lässt.

### Die Kontinuitäts-Lücke

`build_section_prompt` reicht als Kontext nur die **vorige Section** weiter
(`prev_parts[-parts_per_section:]`), nicht die ganze Folge/Serie. Cross-
Episoden-Kontinuität hängt komplett an hand-/KI-verfassten
`intro_note`/`outro_note`/`theme`/`case`. Der Dialog-Schreiber kann Logik also
nicht szenenübergreifend planen — er sieht immer nur einen Schritt zurück.

---

## 2. Die bestehende Logik-Absicherung: Knowledge-Split (bleibt)

Der Kern gegen "die KI vergisst, wer der Täter ist": Die Wahrheit steht
*einmal* in `case.solution` und wird nie neu erfunden. Jede Figur bekommt nur
ihre Wissens-Scheibe:

```
character_knowledge: { ROLLE: { knows: [...], hides: [...], believes_falsely: [...] } }
```

Widersprüche und Lügen entstehen dadurch *organisch* aus der
Perspektivbeschränkung statt vom Modell behauptet. Validiert wird das heute
zweistufig:

- `review_series` (bei Serien-Erstellung): Spoiler-Leaks vor dem Finale,
  Widersprüche über `objective_facts`/`character_knowledge`, Folgen-Überlappung.
- `review_episode_script` / `--fix` (nach dem Schreiben): liest die *fertige*
  Prosa und prüft, ob eine Figur aus ihrer Scheibe gedriftet ist.

Diese Schicht bleibt unverändert. Die Beat-Schicht setzt *darüber* an.

---

## 3. Die Beat-Schicht (neu)

### Grundidee

Zwischen "Section auswählen" und "Dialog schreiben" eine explizite
Klartext-Logikschicht einziehen: kurze Beats, die festhalten *was* in der Szene
passiert und *warum* (wer lügt, wer merkt es, was verschiebt sich, was weiß das
Publikum, das eine Figur nicht weiß) — **ohne Dialogzeilen, ohne Stil**.

Wir erweitern damit die schon existierenden Section-Einzeiler, wir erfinden
nichts Neues.

### Getroffene Entscheidungen

- **Speicherort:** eigene Datei `scripts/epN_BEATS.txt` (überprüf- und
  editierbar vor dem Prosa-Schritt, resume-fähig wie die Parts-Datei) — *nicht*
  in `episodes.json`.
- **Zeitpunkt:** just-in-time pro Folge (ein Beat-Call direkt vor dem Schreiben
  dieser Folge) — *nicht* alle Folgen bei Serien-Erstellung.

### Neuer Fluss in `generate_episode`, pro Folge

1. **Beats generieren (ein Call/Folge)**
   Input: alle Section-Einzeiler der Folge + `case`/`character_knowledge` + die
   Beats der *vorigen* Folge (als Kontinuität). Output: pro Szene 3–6
   Klartext-Beats. → `scripts/epN_BEATS.txt`.

   Beispiel für die Marcus-Szene:
   > 1. Marcus nimmt den Anruf entgegen, erfährt vom Podcast.
   > 2. Er diktiert ein Statement, ändert "researcher" zu "former colleague" — distanziert sich bewusst.
   > 3. Unbewachter Moment: er erwähnt, wo Mei am Fenster stand.
   > 4. Er verbietet, das zu drucken. Publikum spürt Schuld, die Figur gibt sie nicht zu.

2. **(Optional) Beats prüfen**
   Deterministischer/LLM-Check gegen `character_knowledge` und
   Spoiler-vor-Finale — auf den kurzen Beats statt auf Prosa. Manuelle Edits an
   der Datei sind hier möglich, bevor es weitergeht.

3. **Dialog pro Section**
   Wie heute (`call_claude_with_retry`, `[SPEAKER | style]`-Tags, Validierung),
   aber der Prompt bekommt die **Beats dieser Szene** + die **Beats der
   Nachbarszenen** als Kontext — statt des Section-Einzeilers + der
   200-Wörter-Vorszene.

### Schicht-Kontrakt (Prinzip für eine mehrschichtige Erweiterung)

Aktuell ist die Beat-Schicht einstufig (ein Call/Folge). Externe Referenzen
(Dramatron, DOC, WritingPath — grob→fein-Outlining vor Prosa) legen nahe, dass
sich höchstens **eine** zusätzliche Verfeinerungsstufe lohnt (grobe Beats →
verfeinerte Beats), nicht mehr — mehr Schichten sind in keiner der Arbeiten
belegt, erhöhen aber nachweislich das Drift-Risiko. Falls diese zweite Stufe
später gebaut wird, gilt ab dann ein Kontrakt, der Drift über die Kette
verhindert:

- **Jede Schicht besitzt eine eigene, nicht überlappende Entscheidung.** Grobe
  Beats legen fest *was* passiert und *warum* (Wissensstand-Änderungen: wer
  lügt, wer merkt was, was verschiebt sich). Eine verfeinernde Schicht legt
  *Szenenstruktur/Timing* fest (Reihenfolge, emotionaler Bogen, Anzahl
  Momente) — erfindet aber keine neuen Fakten. Der Dialog-Schritt legt fest
  *wie* es gesagt wird (Wortwahl, Stil, Subtext). Sobald zwei Schichten
  dieselbe Art Entscheidung treffen dürfen, schleichen sich Widersprüche ein.
- **Jede Schicht validiert gegen die Wahrheitsquelle, nicht nur gegen die
  Vorschicht.** Referenzpunkt ist immer `case`/`character_knowledge` direkt,
  nie nur die Ausgabe der vorigen Stufe — sonst akkumuliert sich Drift über
  die Kette ("stille Post": Stufe 2 weicht leicht von Stufe 1 ab, Stufe 3 weicht
  leicht von der bereits abgewichenen Stufe 2 ab statt vom Original).

Solange nur eine Beat-Schicht existiert, greift dieser Kontrakt noch nicht —
er ist hier für den Fall festgehalten, dass sich eine zweite Verfeinerungsstufe
als nötig erweist.

### Resume & Backward-Compat

- `epN_BEATS.txt` verhält sich wie die Parts-Datei: existiert sie, wird sie
  übersprungen; `--force` erzwingt Neu-Generierung.
- Gate über ein Opt-in-Flag (Vorschlag: `generation.use_beats: true` in
  `episodes.json`, Default aus). Bestehende Serien (`vanishing_signal`,
  `facades`) und die Doku-Narration laufen unverändert weiter, bis das Flag
  bewusst gesetzt wird. Neue Drama-Serien können es per Default aus dem Template
  erhalten.

---

## 4. Wie die Beat-Schicht die Section-Architektur vereinfacht

Die Beat-Schicht löst den Section/Parts-Mismatch aus Abschnitt 1 auf, ohne die
Struktur rauszureißen:

- **Der Beat wird die natürliche Chunk-Einheit.** Länge folgt dem Inhalt des
  Beats, nicht einem erzwungenen Minimum. Eine kurze Konfrontation *darf* kurz
  sein. Das Fallback-/Gap-Check-Arsenal um `words_per_part_min` kann dadurch
  schrumpfen (nicht sofort entfernen — erst wenn der neue Pfad sich bewährt hat).
- **Chunking entlang erzählerischer Nähte** statt willkürlicher Wortgrenzen —
  genau das, was das Drama (im Gegensatz zum Monolog der Doku) gratis mitliefert.
- **Sections bleiben als Container.** `section_styles`/`section_locations`/
  `section_words` hängen weiter an den Sections; Beats hängen *innerhalb* einer
  Section. Kein invasiver Umbau der Datenstruktur.

### Der doppelte Gewinn

1. **Kontinuitätslücke geschlossen:** Der eine Beat-Call sieht die *ganze
   Folge* auf einmal und plant Logik szenenübergreifend — was der heutige
   Dialog-Schreiber (nur vorige Section) nicht kann.
2. **Validierung auf 5 Zeilen statt 500 Wörtern:** Logikfehler (Knowledge-
   Verstoß, Spoiler-Leak) fliegen *vor* der teuren Prosa auf. Der `--fix`-
   Nachbau-Review wird zum Ausnahmefall statt Regelfall.

---

## 5. Offene Details (erst beim Bauen zu klären)

Kein Blocker für die Grundarchitektur, aber vor der Implementierung zu
entscheiden:

- **Beat-Prompt-Format:** exakte Struktur/Nummerierung der Beats, wie sie
  robust parsebar bleibt (analog zu `--- PART k ---`).
- **Beat-Check:** deterministisch (Regel-basiert gegen `character_knowledge`)
  vs. LLM-basiert vs. beides. Der deterministische Teil wäre analog zu
  `check_section_words_gaps` — billig, kein Claude-Call.
- **Nachbar-Kontext für den Dialog-Call:** nur die eigene Szene, oder ±1
  Nachbarszene, oder alle Beats der Folge als Überblick + eigene Szene im Fokus.
- **Timeout-Skalierung** des Beat-Calls (analog `compute_timeout`/
  `compute_review_timeout`).
- **Interaktion mit `import_story`:** imported episodes haben keine
  Bibel-Logik — Beat-Schicht dort schlicht überspringen (wie schon beim Review).

---

## 6. Betroffene Dateien (voraussichtlich)

- `fabrik/writing/script_writer.py` — neuer Beat-Generierungsschritt in
  `generate_episode`, neue `build_beats_prompt`/`parse_beats`/Beat-Resume-Logik,
  Anpassung von `build_section_prompt` (Beats statt Vorszene als Kontext).
- `fabrik/core/config.py` — `generation.use_beats`-Flag validieren
  (`VALID_GENERATION_KEYS`).
- `templates/soap_opera/`, `templates/crime_drama/` — Beat-Prompt-Baustein,
  ggf. Default-Aktivierung.
- `webui/` — optional ein Schritt/Status "Beats" analog zu den bestehenden
  Wizard-Schritten; nicht zwingend für die erste Version.
