# first_do_harm — Tiefenanalyse

## Serien-Überblick

**Prämisse:** Viktorianische Privatklinik; Nachtschwester Ada Kirwin entdeckt eine
gefälschte Einwilligungs-Signatur und rollt auf, dass Dr. Moorhouse "unbehandelbare"
Frauen unerlaubt psychochirurgisch operiert, Tote als "entlassen" verbucht und hinter
der Stationsmauer verscharrt — Assistent Wycliffe ist über Spielschulden gekauft.

**Threads:** 1 Micro-Thread ("The Discharged Ward"), in allen 5 Episoden identisch
mitgeführt, mit episodenspezifischen `character_knowledge`-Slices — sauberer
Shorts-Zuschnitt (Entdeckung → Spur → Beweis → Isolation → Geständnis ohne Sühne).

**Format-Compliance (shorts, 17.07-Maßstab):**
- Erste gesprochene Zeile = Hook: Ep1 ✓ ("This isn't her hand, Doctor."), Ep2 ✓,
  Ep3 ✓, Ep5 ✓ ("How many, Dr. Moorhouse?"). Ep4 nur bedingt (s. u.).
- NARRATOR: exakt 1 Zeile pro Episode, alle ≤12 Wörter ✓ (5/5).
- Satzlängen: fast durchgehend ≤12 Wörter, caption-tauglich; einziger Ausreißer
  Ep5 P2 mit 13 Wörtern ("The women behind that wall paid the same price surgeons
  have always asked.") — vernachlässigbar.
- Sting-Schluss: Ep1 ✓ (abgebrochene Frage + Tür-SFX), Ep2 ✓ (hängende Frage
  "Mrs. Hale?"), Ep3 ✓ (mitten im Satz gekappt), Ep4 ✓ ("You did *what*."),
  Ep5 ✗ — endet auf einer vollständigen, ruhigen Moorhouse-Zeile. Für ein Finale
  dramaturgisch vertretbar, verletzt aber die eigene Style-Guideline "every episode
  ends on an interrupted beat".
- Kein previously-on-Recap ✓ (Ep5-NARRATOR "Wycliffe's confession still hangs in
  the air" ist Orientierung, kein Recap — grenzwertig, aber innerhalb der 1-Zeilen-Regel).

**Gesamturteil: 8/10.** Für den ersten shorts-Lauf bemerkenswert regelkonform und
dramaturgisch dicht: echte Hooks, harte Stings, unterscheidbare Stimmen, konsequente
Objekt-Dramaturgie (Formular, Brief, Locket, Ledger). Abzüge für zwei unbehobene
REVIEW-Befunde, eine als Moorhouse-Text vertonte Regieanweisung (Ep5), einen nie
aufgelösten Cliffhanger (Atmen in Zelle 9) und einen Konzept-Widerspruch (wer fälschte
Mrs. Hales Unterschrift).

## Episode 1: The Signature Isn't Hers

- **Stärken:** Vorbildlicher Hook (Anklage als allererste Zeile, NARRATOR erst danach —
  genau die Shorts-Reihenfolge). Wycliffes Lügen-Eskalation in P2 ("clerical error" →
  "fever" → "I copied it") ist ein sauber gebautes Verhör in Miniatur. P3 als
  Solo-Flüstermonolog mit Sting ("How many women did he—" + Türknarren) exakt nach
  Plan. Detail "the loop on the H" gibt der Fälschung ein konkretes, wiederverwendbares
  Erkennungszeichen.
- **Schwächen:** P3 ist mit 50 Wörtern das dünnste Part der Serie (unter dem
  Soll-Minimum 60) — funktioniert als Sting, könnte aber 2–3 Zeilen Fundkontext
  mehr vertragen. Moorhouses "You've done fine work tonight" ist stark, doch sein
  Einsammeln des Formulars (laut Section-Plan "personally pockets the form") ist nur
  über den SFX "paper sliding off a metal tray" erzählt — im Audio kaum lesbar.
- **Fehler (korrigierbar):** Konzept-Ebene (episodes.json, case ep1): MOORHOUSE.knows
  "He forged the signature himself" widerspricht WYCLIFFE.knows "He personally forged
  Mrs. Hale's signature on Moorhouse's instruction" — beide beanspruchen dieselbe
  Fälschung. Das Skript bleibt zufällig ambivalent ("I copied it. From an earlier
  form."), aber die Quelle ist in sich widersprüchlich und kollidiert zusätzlich mit
  objective_facts ("handwriting … matches Dr. Moorhouse's private correspondence").

## Episode 2: Where the Discharged Go

- **Stärken:** Bester Hook-Gegenstand der Serie (retournierter Brief "Address
  Unknown"). Ada liest Körpersprache statt Worte ("Your hand's stopped on that bottle,
  Doctor." / "You said 'protocol' like it hurt to say.") — genau die "procedural fear"
  aus der Voice-Beschreibung. P3 (Zellen zählen, Gaslicht, Kettenschleifen, "An empty
  room doesn't breathe.") ist das atmosphärische Highlight der Staffel; speed-Absenkungen
  (0.95→0.85) modellieren die Anspannung hörbar.
- **Schwächen:** Wycliffes erfundener "cousin in Leeds" wird von Ada sofort widerlegt
  ("No cousin appears in her admission file.") — der Plan wollte, dass Ada die Lüge
  *hört*, das Skript lässt sie sie *aktenkundig* widerlegen; minimal glatter als geplant,
  nimmt Wycliffe etwas Restglaubwürdigkeit für Ep3.
- **Fehler (korrigierbar):** Keine im Skript selbst. Aber: der hier gesetzte
  Cliffhanger (Atmen + Kette hinter der als "vacated" markierten Zelle 9, Adas Hand
  am Riegel, "Mrs. Hale?") wird in Ep3–5 nie wieder aufgegriffen — s. Serienweite Muster.

## Episode 3: The Locket in the Ledger

- **Stärken:** P2 ist die beste Szene der Serie: Wycliffes "Have you told anyone?"
  als Frage, die alles beantwortet, plus Adas "That's your question. Not what happened
  to her." — Charakterisierung rein über Frage-Auswahl. Der stumme Beat
  ("[DR_JONAS_WYCLIFFE | style: silent, ashamed] ...") ist ein mutiger, wirksamer
  Audio-Moment. Sting exakt mitten im Satz ("…what you'd do with—").
- **Schwächen:** P2 mit 48 Wörtern sehr kurz (unter Minimum) — inhaltlich gewollt
  karg, aber zwei Zeilen mehr Wycliffe-Zerfall hätten Platz gehabt. Moorhouses
  "Initials prove a locket. Nothing more." ist stark, doch seine Souveränität in P3
  wiederholt tonal fast 1:1 den Ep1-P2-Auftritt (warm, allwissend, deeskalierend).
- **Fehler (korrigierbar):** REVIEW-Befund UNBEHOBEN (P3): "You've asked that question
  since your very first shift here." + "I've simply been waiting to see what you'd do
  with—" — Moorhouse plaudert exakt das aus, was sein `hides`-Slice verbirgt ("How long
  he has actually known … since her very first questions"). Wurzel: der Fehler steckt
  schon im Konzept — die `outro_note` derselben Episode ("Ada realizes he's known …
  since the day she started") widerspricht dem eigenen `hides`-Feld. Skript folgte der
  outro_note; Review flaggte korrekt; niemand hat entschieden.

## Episode 4: The Debt That Bought His Silence

- **Stärken:** Moorhouses Waffe ist reine Information ("eleven hundred pounds …
  Paid in full, this January.") — die Debt-Enthüllung folgt präzise dem objective_fact.
  Adas Umdeutung "Every hesitation. Every flinch. I called it conscience. / It was only
  ever fear of you." ist der beste Erkenntnis-Beat der Staffel. Härtester Sting der
  Serie: Wycliffes Geständnis ("I sent word Tuesday.") kippt die Machtachse in drei
  Zeilen, "You did *what*." als erste Fassungslosigkeit Moorhouses überhaupt.
- **Schwächen:** Erste gesprochene Zeile "Sit, Nurse Kirwin. I poured you a brandy."
  ist Einladung/Inszenierung, nicht "accusation, lie caught, or locked door" — der
  eigentliche Hook (Debt-Nennung) kommt erst in Zeile 4. Einzige Episode, die die
  Hook-first-Regel nur dem Geist, nicht dem Buchstaben nach erfüllt.
- **Fehler (korrigierbar):** P3, letzte Zeile: Markdown-Asterisken im TTS-Text
  ("You did *what*.") — je nach Backend werden sie mitgesprochen oder verschluckt;
  Betonung gehört ins style-Feld, nicht in den Prosa-Text.

## Episode 5: What the Ledger Can't Bury

- **Stärken:** Der Serien-beste Hook ("How many, Dr. Moorhouse?") und die geplante
  Confession-Zeile ("Enough to matter. / And not enough to stop.") sitzt wortgenau wie
  im Section-Plan — inklusive Pen-SFX. P2 (Moorhouse-Credo im Theatre) spielt die
  Template-Vorgabe "never sounds like a villain to himself" perfekt aus ("Paper burns,
  Nurse Kirwin. Results don't."). Das Anti-Payoff-Ende ("irregularities", nicht Mord)
  ist thematisch der mutigste Zug der Staffel.
- **Schwächen:** Kein Sting-Schnitt — Ep5 endet auf einer vollständigen, souveränen
  Moorhouse-Antwort statt eines abgebrochenen Beats (bewusster Finale-Ausklang, aber
  gegen die eigene Regel). Wycliffes Kipp zurück zur Komplizenschaft ("I can... manage
  figures.") kommt für die Kürze etwas unvermittelt nach seinem Ep4-Verrat, ist aber
  durch sein `hides`/`believes_falsely` (weichgespülter Report, Immunitätshoffnung) gedeckt.
- **Fehler (korrigierbar):**
  1. P3: Regieanweisung ohne Sprecher-Tag — "He signs the audit request without
     hesitation." steht als nackte Prosa unter Moorhouses Zeile "Manage them the way
     you've managed everything else." und wird damit in Moorhouses Stimme als
     Selbstbeschreibung in der 3. Person VERTONT. Zeile streichen oder als
     [SFX: pen scratching on paper] umsetzen.
  2. P3: REVIEW-Befund UNBEHOBEN — Ada: "You just told me the names. I heard you."
     Moorhouse hat nie Namen genannt ("Enough to matter", "The women behind that
     wall"). Fix: "You just admitted it. I heard you." o. ä.
  3. P1: NARRATOR "The ward office." widerspricht section_locations
     (DR_MOORHOUSE_STUDY) und der Szene selbst (Brandy-Anschluss aus Ep4, Stift auf
     Schreibtisch, "Close the door on your way to bed").

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)
1. **Zelle 9 / das Atmen hinter der "vacated"-Tür (Ep2 P3) wird nie aufgelöst.**
   Ep3-intro_note referenziert es noch ("The breathing behind the vacated cell…"),
   aber kein Skript ab Ep3 erwähnt je wieder, wer dort atmete, ob Ada den Riegel
   öffnete, oder wie das zum Ep5-Bild "Frauen HINTER der Mauer begraben" (tot) passt.
   Stärkster Cliffhanger der Serie → verhungert.
2. **Ep5 P1 Ort:** NARRATOR sagt "ward office", geplant und gespielt wird Moorhouses
   Study (direkte Fortsetzung der Ep4-Szene).
3. (Konzept-intern, wirkt episodenübergreifend) **Fälscher-Identität:** ep1-case lässt
   sowohl Moorhouse ("forged the signature himself") als auch Wycliffe ("personally
   forged Mrs. Hale's signature") dieselbe Unterschrift fälschen; Ep4 legt sich dann
   auf "Formulare von Moorhouse signiert, von Wycliffe countersigniert" fest.

### Wiederholte Phrasen/LLM-Tics (mit Zählung)
- Anaphorisches Verneinungs-Tripel "Not X. Not Y. (Not Z.)": 3× — Ep2 P1 ("Not once.
  Not for a single Sunday."), Ep2 P2 ("Not one line. Not one name."), Ep3 P1
  ("Not the ward. Not Moorhouse. Not yet."). Effektiv, aber schon in 5 Kurz-Episoden
  als Muster hörbar.
- Style-Tag-Recycling: "flat, controlled fury" wörtlich identisch Ep2 P1 und Ep3 P2;
  Adas Tags kreisen serienweit um flat/cold/steady/quiet (>20 von ~30 Ada-Zeilen) —
  für TTS-Varianz dürfte ihr Register breiter sein.
- Moorhouse-Formel "calm/warm + adversativ" ("warm, unsettlingly calibrated" 2× in
  Ep1 P2 wörtlich identisch hintereinander) — gewollte Signatur, aber exakte
  Tag-Dopplung in Folge ist Copy-Paste.
- Positiv-Tic: das "hand"-Motiv (Handschrift → stockende Hand → "my hand's on the
  bolt" → "signs with a steady hand") zieht sich als bewusstes Leitmotiv durch alle
  5 Episoden — behalten.

### Thread-Bilanz
Ein einziger Thread ("The Discharged Ward") — bekommt 5/5 Episoden, keine Konkurrenz,
kein Verhungern/Überfüttern möglich. Die Slice-Progression der character_knowledge
(Ada: isolierter Fehler → System → Beweis → Isolation → Confession reicht nicht;
Wycliffe: Einzelgefallen-Lüge → Adressen-Erfinder → ertappt → Verräter → Weichspüler)
ist sauber eskaliert. Einzige Ökonomie-Schwäche: der Zelle-9-Nebenstrang (s. o.).

### REVIEW-Abgleich-Ergebnis
- ep1, ep2, ep4: "Keine Auffälligkeiten" — deckt sich mit meinem Befund (die von mir
  gefundenen Punkte in ep4 — Asterisken, weicher Hook — liegen außerhalb des
  Review-Fokus Case-Treue).
- ep3: 1 Befund (Moorhouse leakt sein hides) — **UNBEHOBEN**, wörtlich noch im Skript.
- ep5: 1 Befund ("the names"-Ambiguität) — **UNBEHOBEN**, wörtlich noch im Skript.
- Vom Review NICHT gefunden: die vertonte Regieanweisung ep5 P3 (Format-, nicht
  Case-Problem) und der NARRATOR-Ortsfehler ep5 P1 — beides Kandidaten für eine
  Format-Checkliste im Review-Prompt.

## Top-5 konkrete Korrekturen (priorisiert, mit Fix-Weg)

1. **Ep5 P3 — Regieanweisung entfernen:** "He signs the audit request without
   hesitation." wird als Moorhouse-Text vertont. Zeile löschen oder durch
   `[SFX: pen scratching on paper]` ersetzen. (Hand-Edit, 10 Sekunden.)
2. **Ep5 P3 — REVIEW-Befund umsetzen:** "You just told me the names. I heard you."
   → "You just admitted it. To my face." — beseitigt die Behauptung von Wissen
   (Namen), das Ada laut Case nicht hat.
3. **Ep3 P3 + episodes.json — hides-Konflikt entscheiden:** Entweder outro_note ep3
   entschärfen (Ada *ahnt*, dass er es länger weiß) und die zwei Moorhouse-Zeilen
   auf Andeutung zurückschneiden ("You ask that question like you've asked it
   before."), oder das `hides`-Feld streichen. Aktuell widersprechen sich Konzept
   und Konzept — daher konnte das Review nur flaggen, nicht fixen.
4. **Ep5 P1 — NARRATOR-Zeile korrigieren:** "The ward office." → "Moorhouse's study.
   The brandy still untouched." (stellt zugleich Anschluss an Ep4 her, ≤12 Wörter).
5. **Serien-Patch Zelle 9:** In Ep5 P1 oder P2 eine einzige Ada-Zeile ergänzen, die
   den Ep2-Cliffhanger schließt (z. B. "Cell nine was empty by morning. Scrubbed."),
   sonst bleibt der stärkste Hook der Staffel ein Loch. Alternativ (billiger):
   Ep3-intro_note streichen, damit das Konzept den Strang nicht selbst als offen markiert.

Bonus (niedrige Prio): Ep4 P1 Hook härten — Episode mit Moorhouses Debt-Zeile
("Dr. Wycliffe owed eleven hundred pounds…") öffnen und die Brandy-Einladung dahinter
schieben; Ep4 P3 "*what*" → Asterisken raus, Betonung in den style-Tag.
