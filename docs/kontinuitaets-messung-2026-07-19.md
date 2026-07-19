# Kontinuitäts-Messung, 19.07.2026

Ausgangsfrage: Driftet die geschriebene Prosa vom festgelegten Kanon ab — und
lohnt ein Mechanismus, der nach jeder Episode eine verdichtete Fassung
weiterreicht?

**Antwort: ja, ~1,1 gegengeprüfte Brüche pro Episode — aber die Beat-Schicht,
also genau so ein Mechanismus, lief bereits und hat sie nicht verhindert.**

## Aufbau

Datenbasis: 16 fertige Produktionsepisoden aus zwei soap_opera-Serien
(`split_signal`, `the_midnight_frame`), je ~6.000 Wörter.

Zweistufig, weil LLM-Prüfer systematisch übermelden:

1. **Finden** — ein Prüfer pro Episode, sieht Kanon (`threads[].solution` +
   `objective_facts`, Besetzung, Orte), Episodenplan (inkl.
   `character_knowledge`) und die Prosa. Sucht Widersprüche, Wissens-Lecks
   und bindende neue Fakten. Ausschmückung, Figuren-Spekulation und
   dramaturgische Verdichtung sind ausdrücklich KEINE Befunde.
2. **Widerlegen** — ein Skeptiker pro Episode mit dem Auftrag, jeden Befund
   zu kippen; im Zweifel VERWORFEN. Bestätigt nur, was einen ernsthaften
   Angriff überlebt: Zitat wörtlich vorhanden, Kanon sagt eindeutig etwas
   anderes, ein Hörer würde es bemerken.

## Ergebnis

| | Zahl |
|---|---|
| Rohbefunde | 56 |
| davon widerlegt | 38 (**67% Falschbefunde**) |
| **bestätigt** | **18** |
| Schwere hoch / mittel / niedrig | 8 / 8 / 2 |
| Typ Widerspruch / Neuer Fakt / Wissens-Leck | 16 / 1 / 1 |

Verteilung `split_signal` 14, `the_midnight_frame` 4. Bei n=2 Serien ist
daraus nichts abzuleiten.

**Die 67% sind das methodisch wichtigste Ergebnis.** Wer so eine Prüfung ohne
Gegen-Instanz baut, misst überwiegend Rauschen.

## Der entscheidende Befund

Beide Serien haben je 8 `_BEATS.txt` — die Beat-Schicht lief überall.
`DEFAULTS["use_beats"]` steht auf `True`, `the_midnight_frame` setzte den Key
zusätzlich explizit.

Damit ist die Frage vom Anfang beantwortet: Eine verdichtete Fassung, die von
Episode zu Episode weitergereicht wird, EXISTIERT — und reicht nicht. Der
Grund ist strukturell: **Beats entstehen VOR der Prosa, aus dem Plan.** Sie
können nicht wissen, was das Modell tatsächlich geschrieben hat. Sagt Episode 1
„forty-two mornings", steht das in keinem Beat, und Episode 2 schreibt
„Six weeks. Six faces."

## Zwei Fehlerklassen, etwa hälftig

**A — prosa-intern, ohne Kanon-Bezug** (die für den Hörer auffälligsten):

- „Six weeks. Six faces." (Ep2) gegen 42 Morgen in Ep1
- Foto „Forty-one" angeheftet an Tag 48 (Ep7)
- Zhao gesteht „Six weeks", im selben Skript sagen andere „four months" (Ep8)
- dieselbe Blackout-Lücke: „three hours" (Teil 3) vs. „Fifty minutes" (Teil 11)

**B — Kanon ignoriert, Prosa in sich konsistent:**

- Kanon „The Herald Newsroom" → Prosa führt vier Zeitungen (Port Meridian
  Ledger, City Ledger, Port Meridian Gazette, Harbor City Herald)
- Kanon „Renata's House" → durchgehend „apartment"
- Tolls Körper: Kanon Cannery → Prosa Stiftungsgebäude bzw. Hospital-Consult
- Zhao und Voss als eingespielte Bekannte, obwohl Kanon „has never met" sagt

## Was daraus gebaut wurde

`fabrik/writing/continuity.py` (stdlib-only) deckt Klasse B ab plus den Teil
von A, der an einem Kanon-Eigennamen hängt. Ergebnis auf denselben zwei
Serien: **12 Meldungen, alle belegbar**, darunter fünf, die das LLM-Panel
übersehen hatte (`Fifth Precinct`, `Cold Case Division`,
`Meridian County courthouse`, `Harbor City Precinct`, `Harbor City Herald`).

Zwei Entwürfe scheiterten vorher an echten Daten und sind bewusst NICHT im
Modul — Details und Zahlen in `fabrik/writing/CLAUDE.md`:

- generische Zähler-Regression über jedes Nomen mit Zahl → 127 Meldungen,
  praktisch alle falsch
- Zeitanker über beliebige Eigennamen → verankert auf „Adrian"/„Captain",
  die in jeder zweiten Zeile stehen

## Offen

Klasse A ohne Kanon-Bezug — die größere Hälfte — findet das Modul nicht. Dafür
bräuchte es ein aus der fertigen Prosa gezogenes **Zustands-Register**
(Zählerstände, Daten, verwendete Eigennamen, Wissensänderungen), das gegen
harte Werte abgleicht statt gegen erzeugten Text. Bewusst noch nicht gebaut:
erst sollte ein Mensch einen Teil der 18 Befunde gegenlesen — die
„bestätigten" Befunde sind LLM-Urteile, keine menschlich verifizierten.

Andockpunkt im Neubau existiert bereits:
`rewrite/factory/authoring/script_writer.py::_episode_summary()` reicht heute
25 Wörter weiter.

## Einschränkungen

- zwei Serien, beide `soap_opera`, beide mit Beats — kein Vergleich ohne
- die Bestätigung stammt von einem zweiten LLM, nicht von einem Menschen
- der Skeptiker-Auftrag war einseitig („im Zweifel verwerfen"), die 18 sind
  also eher eine Untergrenze
