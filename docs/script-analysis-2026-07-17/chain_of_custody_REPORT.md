# chain_of_custody — Tiefenanalyse

## Serien-Überblick

**Prämisse:** Detective Mei Lin sperrt sich off-the-books mit dem Verdächtigen Jonas Voss in einen Verhörraum, um den vermissten Daniel Wu zu finden — und liefert Voss damit exakt die Bedingung, die er seit Monaten konstruiert. 10 Episoden, soap_opera, 4 Threads: **The Missing Man**, **The Lock-In**, **The Detective's Secret**, **The Captain's Ledger**.

**Gesamturteil: 5/10.** Auf Szenenebene ist das die bisher stärkste Schreibe der Pipeline (Stand 12.07., Beats + Review aktiv): Voss ist eine durchgehend exzellente Figur, die Machtumkehr Detective↔Suspect wird glaubwürdig über Wochen aufgebaut, Cliffhanger sitzen, Recaps existieren ab Ep2. Aber die Serie scheitert auf **Staffelebene**: Die case-Daten in episodes.json wurden pro Episode neu erfunden statt fortgeschrieben — Mei Lins Geheimnis hat VIER inkompatible Versionen (Grace Ito → Lily Okafor → Marcus Delgado → Bruder-Zeugenaussage), der Ledger dauert je nach Episode 18 Monate bis 15 Jahre, Zoes Artikel erscheint zweimal, und Ep10 spult den Lock-In zurück, obwohl Ep8 die Tür bereits aufgebrochen hat. Die Skripte folgen den Beats treu — d. h. die Drift ist ein **Planungsproblem (Stage-1-Kontinuität), kein Prosaproblem**.

## Episode 1: Forty-Eight Hours

- **Stärken:** Starker Auftakt über alle Figuren; Anna Wus Stundenzählen (P1) ist emotional präzise; Suns "Not now. Not him." (P4) setzt den Ledger-Thread mit einer einzigen Zeile. Kais Datums-Anomalie (P9) ist sauber im knows-Slice.
- **Schwächen:** P3 (165 W.) und P4 (167 W.) inhaltlich dünn — die Sun-Szene trägt nur einen Beat, deswegen unter Budget.
- **Fehler (korrigierbar):**
  - **P12/P13 doppeln dasselbe Ereignis:** In P12 schickt Mei Lin den Watch-Officer weg („Ortiz. I need you off this door") und der Recorder klickt aus (`[SFX: the recorder light clicking off]`); in P13 schickt sie ihn NOCHMAL weg („Go grab coffee. I've got this one") und schaltet NOCHMAL die Aufnahme ab („The recording light above the door goes dark"). Ursache: Sections 12+13 im Plan beschreiben dieselbe Handlung, die Beats (Scene 12/13) haben das übernommen.
  - P13: „Interrogation Room Two" — ab Ep7 heißt der Raum kanonisch „Interrogation Room 3" (inkl. objective_fact, dass Voss Raum 3 angefordert hat).
  - P12: Mei Lin schickt den Officer zum „Delgado intake" — Namenskollision mit dem späteren Geheimnis-Opfer Marcus Delgado (Ep7) und „Officer Delgado" (Ep5 P9).
- **REVIEW-Abgleich:** Der Flag zu P11 (Sun koordiniert aktiv Unterdrückung) wurde **teilweise behoben** — die zitierte Zeile „Nobody needs to hear from him…" ist raus, die Szene liest sich jetzt als Distanzierung. ✔

## Episode 2: The Door Locks

- **Stärken:** Erster „Previously on"-Recap der Serie (P1). Der Grace-Moment (P7: „Grace." — Atemzug — „I don't know what that's supposed to mean") ist der beste Einzelbeat der Staffel. P8 („Funny. I didn't say a last name.") exzellente Verhör-Logik.
- **Schwächen:** P5 mit 134 W. sehr dünn (Tür-Dialog, eine Information); Zeitachse wackelt (P2 „same night", P9 „same afternoon", P7 „well past midnight").
- **Fehler (korrigierbar):**
  - **P5: Regieanweisung als Sprechzeile:** `[JONAS_VOSS | style: quiet amusement]` gefolgt von `(not addressed to Kai Yang)` — die TTS spricht „not addressed to Kai Yang" laut. Zeile löschen oder in NARRATOR umwandeln.
  - **P7: Thread-Label leakt in die Narration:** „…the thread still The Lock-In — until Voss decides otherwise." Interner Planungsbegriff on-air.
  - P7: „Interrogation Room Two, the department's **fourth floor**" — der Raum ist laut Location-Definition und Ep4+ ein **Basement**-Raum.
  - P3: „The window on you closes in **two days**" — in Ep1 P8 waren es noch **sieben Stunden** bis zum Ablauf der 48h. Die Uhr wurde stillschweigend neu aufgezogen.
- **REVIEW-Abgleich:** Beide Flags **unbehoben**: P10 sagt Mei Lin selbst „paperwork nobody's seen in **eight years**" (verrät ihr Wissen trotz Leugnung in P8); P11 zieht Kai Yang die Grace-Ito-Akte, obwohl er im Detective's-Secret-Thread keinen Slice hat. ✘

## Episode 3: Old Files

- **Stärken:** Voss' Detailbeweise (P1 Dispatch-Wortlaut, P10 „Eleven forty-two p.m.") sind großartige Eskalation; Zoes Dock-Stakeout (P8) mit Voice-Memo ist die beste Zoe-Szene; die Zufallsbegegnung Kai/Zoe an der Bar (P11, „You too, Detective." / „Wait — how'd you—") ist elegantes Soap-Handwerk.
- **Schwächen:** P9 nur 143 W. (einseitiges Telefonat, dünn geplant); P13 (125 W.) unter Budget, aber als Cliffhanger-Stinger okay.
- **Fehler (korrigierbar):**
  - **P10: „the recorder light still blinking red… the hum of the recorder"** — Mei Lin hat die Aufzeichnung in Ep1/2 deaktiviert; das rote Licht widerspricht der Grundprämisse des Lock-In.
  - P13: „night deepening outside its **one window**" — der Verhörraum ist laut Location-Beschreibung **fensterlos** („a windowless basement room").
  - P3: Die Bar heißt „**The Anchor**, a dive bar" — die geplante Location war THE_BLUE_LANTERN; der Ort taucht so nie wieder auf.
  - P9: NARRATOR beginnt „**The Captain's Ledger.** Sun steps into…" — Thread-Label-Leak Nr. 2.
- **REVIEW-Abgleich:** „Keine Auffälligkeiten" — das Review hat das rote Recorder-Licht (P10) übersehen.

## Episode 4: Favors Owed

- **Stärken:** Suns Log-Fälschung (P2) als kompakte 90-Wort-Szene mit Save-Ton ist filmisch; Voss' „Namen-Test" (P3: Reyes, Harmon — „You didn't flinch… There it is.") ist die beste Manipulationsszene; die Beats werden 1:1 umgesetzt (alle 13 Szenen verifiziert).
- **Schwächen:** P2 mit 90 W. deutlich unter Budget (bewusst als Mini-Szene geplant — section_words min 130 verfehlt); Zoes P7 ist ein einseitiges Gespräch, bei dem der Informant nie hörbar ist (funktioniert, wirkt aber über 300 Wörter monoton).
- **Fehler (korrigierbar):**
  - **Recap fehlt (deterministischer Flag VERIFIZIERT):** P1 startet kalt mit „Major Crimes bullpen, Precinct 14, morning." Ep2, 3, 5, 6, 7, 8, 9, 10 haben alle ein „Previously on Chain of Custody" — nur Ep4 nicht.
  - **P5: „that same word — docks — is already circling a detective who has never once heard Anna Wu's voice"** — falsch: Mei Lin hat in Ep1 P6 direkt mit Anna gesprochen (Bullpen-Konfrontation).
  - P5: Anna: „It's been **weeks** since anyone told me anything" — laut Staffeluhr sind seit Daniels Verschwinden ~5 Tage vergangen (Beginn der Zeitachsen-Inflation, s. Serienmuster).
  - P5/P8: Thread-Label-Leaks Nr. 3+4: „**The Missing Man thread returns.**" / „the **Captain's Ledger**, continuing in the dark".
  - P1: „Precinct **14**" — Ep9 P1 nennt „Precinct **Twelve**".
- **REVIEW-Abgleich:** „Keine Auffälligkeiten" — Anna-Fehler (P5) übersehen.

## Episode 5: The Confession That Wasn't

- **Stärken:** Mei Lins Geständnis (P3) ist die stärkste emotionale Szene der Staffel („Maybe it changes nothing. Maybe it changes everything."); ihre Nachbetrachtung (P10: „That wasn't kindness. That was patience.") exzellent; Suns Parkhaus-Szene (P11) gibt ihm erstmals echte Ambivalenz („I move people, not muscle").
- **Schwächen:** Ab hier heißt das Opfer plötzlich **Lily Okafor** statt Grace Ito (Case-Drift in episodes.json ab Ep4); Voss führt den Namen in P2 neu ein, als hätte es Ep2/3 nie gegeben.
- **Fehler (korrigierbar):**
  - **P5: Falsche Sprecherzuordnung — die Bartender-Antworten liegen auf ZOE_HAN:** `[ZOE_HAN | style: guarded, noncommittal] Something like that.` und zwei weitere Zeilen. Zoe ist in der Szene gar nicht anwesend; die TTS spricht den Bartender mit Zoes Stimme. Schwerster Einzel-Bug der Staffel.
  - **P13: „Three years of phone calls. Voicemails nobody returns."** — Daniel ist je nach Episode Tage bis Monate weg, niemals drei Jahre.
  - P6/P7: „Reyes… Voss's man… handles the docks paperwork" / „Marcus Reyes" — in Ep4 P3 war Reyes ein **pensionierter Vice-Cop** („Reyes retired two years ago"), jetzt aktiver Voss-Fixer. Namensrecycling ohne Abgleich.
  - P11: Thread-Label-Leak Nr. 5 („The Captain's Ledger, away from the harbor now").
  - Ep5-Cliffhanger verpufft: „Tomorrow I don't ask the front desk… I put the name on the table" — Anna geht in Ep6 nie zum Precinct; stattdessen liest sie zu Hause den Artikel.
- **REVIEW-Abgleich:** „Keine Auffälligkeiten" — der ZOE_HAN-Bartender-Bug wurde übersehen (schwerste Review-Lücke).

## Episode 6: Off the Record

- **Stärken:** Artikel-Publikation als Bullpen-Kollektivszene (P1) sehr gut („Somebody in this building just stopped breathing right."); die Eskalation der Tauschgeschäfte (P6: Kestrel Row Unit 214 gegen ungeloggte Anrufe; Voss' halblautes „Good girl.") ist gruselig-effektiv; P9 (Vorname „Mei") markiert die Grenzverschiebung präzise.
- **Schwächen:** Innere Uhr kollabiert: P3 sagt „held here alone for two days", Anna sagt in P8 „It's been **months**, Zoe" — im selben Skript.
- **Fehler (korrigierbar):**
  - **P1: Mei Lin schlendert durchs Bullpen und plaudert mit Kai** („I've got a room upstairs I need to get back to") — Ep4/5 haben etabliert, dass sie komplett dunkel ist (Welfare-Check-Panik, „Where are you, Mei Lin"). Zusätzlich: „a room **upstairs**" — der Raum liegt im Basement.
  - P10: Kai entdeckt die 11:47-Lücke **zum dritten Mal** (nach Ep4 P10 und Ep5 P4, dort „eleven forty-six") — dieselbe Enthüllungsszene dreimal, einmal mit abweichender Uhrzeit.
  - P10/P11/P13: Thread-Label-Leaks Nr. 6–8 („This is the Lock-In thread now" / „The Captain's Ledger thread continues" / „Fourth thread — The Captain's Ledger meets The Lock-In").
  - P2: „Eighteen months of deposits" — Ledger-Dauer kollidiert mit „three years" (Ep4 P7), „eleven years" (Ep8 P3), „six years" (Ep10 P5/P12).
- **REVIEW-Abgleich:** Flag (Shell-Firma „Renner Logistics" vs. „Voss Maritime Solutions") wurde **behoben** — P8 sagt jetzt konsistent V.M.S. ✔ (Ironie: „Voss Maritime Solutions" als Tarnfirma, die den Namen des Strippenziehers trägt, ist inhaltlich unglücklich.)

## Episode 7: The Long Game

- **Stärken:** Beste Voss-Psychologie („Trust that arrives too fast isn't trust — it's just relief wearing its clothes", P2); das Override-/Notausgangs-Foreshadowing (P5) ist sauber gepflanzt; Suns Selbstverhör (P7: „Suspicion I can survive. Confirmation, I can't.") stark; Dreifach-Cliffhanger P13 („Three doors, three intentions, one hallway") vorbildlich.
- **Schwächen:** Der Geheimnis-Thread springt zum **dritten Namen**: P6 macht daraus „Marcus Delgado", Fall 8441, von Sun (damals Lieutenant „David") beerdigt — inkompatibel mit dem Lily-Okafor-Geständnis aus Ep5 UND mit Grace Ito aus Ep2/3.
- **Fehler (korrigierbar):**
  - **P9: „The Blue Lantern, a guesthouse near the harbor… the guest register"** — die Blue Lantern ist kanonisch eine Bar (Location-Definition, Ep3/4/5); hier wird sie zur Pension mit Gästebuch samt „Room 4".
  - P3: Shell-Firma heißt jetzt „**Pacific Rim Freight Solutions**" und Daniels Notiz steckt auf einem „receipt, in his desk drawer" — Ep6 hatte „Voss Maritime Solutions" und „notebook, page eleven" etabliert.
  - P5: Mei Lin hinterlässt Kai eine Voicemail und wandert durch Flure/Archiv — kollidiert weiter mit dem „sie ist seit Tagen im Raum verschwunden"-Bild, das Kai in P10 aus den Logs abliest („Door held open the entire time. She was never anywhere else").
- **REVIEW-Abgleich:** „Keine Auffälligkeiten" — Blue-Lantern-Retcon übersehen.

## Episode 8: Breach

- **Stärken:** Beste Episode der Staffel. Die Parallelmontage (Kai bricht die Tür, Sun im Korridor gefangen, der Override weckt still den Notausgang) ist echtes Thriller-Handwerk; P10 (Kamera-Flackern, Statuslicht „Disabled. Then active.") herausragend; Voss' Mikro-Reaktion beim Breach (P11) und Suns verdächtig schnelles Auftauchen (P12) sind präzise.
- **Schwächen:** P4 (128 W.) und P10 (117 W.) unter Budget, aber beide funktionieren als Beat-Stinger.
- **Fehler (korrigierbar):**
  - **P8: Voss: „There's a storage unit. Off Kestrel Street… Unit number I don't have memorized — I never went inside myself."** — In Ep6 P6 hat er wörtlich „Kestrel Row Self-Storage. **Unit 214**" geliefert. Direkter Widerspruch im selben Handlungsfaden.
  - **P3: Zoes Story geht ZUM ZWEITEN MAL live** („watches her own byline go live… It's up.") — sie wurde bereits in Ep6 P1 publiziert (und Ep7-Recap bestätigt das). Ursache: Ep8-Section „The Story Goes Live" dupliziert die Ep6-Section im Plan.
  - P3: „**eleven years** of numbers" (Ledger-Dauer-Drift); P13: „**Three years** he made sure that container never got a second look."
  - P2: Voss: „sitting in rooms like this one for **months**. Yours." — er ist seit wenigen Tagen in Gewahrsam.
- **REVIEW-Abgleich:** „Keine Auffälligkeiten" — Kestrel-Widerspruch übersehen.

## Episode 9: The Turn

- **Stärken:** Der leere Container (P11/P12) ist der beste Plot-Turn der Staffel — „He never gave me a location to find. He gave me a location to be looking at while it emptied out from under me." (P12) ist die These der ganzen Serie in einem Satz; die stumme Räum-Szene P11 (nur NARRATOR+SFX) ist formal mutig und funktioniert; „Next time on Chain of Custody"-Teaser am Ende ist ein guter neuer Mechanismus.
- **Schwächen:** P4 lässt ausgerechnet den kompromittierten Sun das Raid-Briefing leiten (planbedingt); P10 endet mit vier gestapelten SFX-Cues ohne Text (Budget-Füller).
- **Fehler (korrigierbar):**
  - **P1: „Six hours, no camera, no backup"** — der Lock-In dauerte laut Ep6 „two days", laut Ep10 „thirty-one hours"; sechs Stunden passt zu nichts.
  - P1: „Interrogation corridor, **Precinct Twelve**" vs. Ep4 „Precinct 14".
  - P4: „the one they shelved **eight months ago**" + Anna „I have been patient for **months**" — Zeitachsen-Inflation.
  - P6: Dialogzeilen stehen in wörtlichen Anführungszeichen („You've seen it, then.") — Formatbruch gegenüber allen anderen Episoden (TTS liest es zwar, aber inkonsistent).
- **REVIEW-Abgleich:** „Keine Auffälligkeiten".

## Episode 10: What the Room Cost

- **Stärken:** Voss' Abgang (P10: „Two doors. Two signatures. Between them, a corridor with one camera, angled wrong for a week") ist ein perfekt trockener Escape; Daniels Fund (P7, „Too easy. Somebody wanted him found today.") hält die Ambivalenz; das Finale P14 (Low Tide, „a debt… goes on, quietly, unpaid") trifft das geplante Serien-Outro exakt.
- **Schwächen:** Die Episode ist im Plan (episodes.json ep10 case) gegen Ep8/9 geschrieben — das Skript erbt den Bruch.
- **Fehler (korrigierbar):**
  - **P1/P2: Kompletter Rewind — der Lock-In läuft wieder:** Sun: „It's been over a day… She hasn't badged in"; NARRATOR: „Detective Mei Lin has held Jonas Voss here, alone and off the books, for more than a day." Aber Ep8 hat die Tür aufgebrochen, Voss kam in Ep9 nach „Holding Two, full escort", Mei Lin war von Voss-Kontakt gesperrt. Die Ereignisse von Ep8/9 werden ignoriert.
  - **P2/P13: VIERTE Geheimnis-Version:** „a witness statement. A younger brother whose name never appears in any file" — und P13: „There's no next piece, Kai. This was the one I was still holding onto." Damit werden das Lily-Okafor-Geständnis (Ep5 P3) und die Delgado-Akte (Ep7 P6) rückwirkend annulliert; Grace Ito (Ep2/3) bleibt für immer unaufgelöst.
  - P4 vs. P11: „**Nine months** of nothing" vs. „**Eight months** I stood outside that building" — Widerspruch innerhalb derselben Episode (und beide widersprechen der Staffeluhr).
  - P9: Mei Lin fälscht das Abschlussformular („Nine hours, not thirty-one") — gute Szene, aber unhaltbar, nachdem in Ep8/9 das halbe Precinct samt Oversight-Team den Breach miterlebt hat.
  - P11: Kai nennt Anna „**Mrs.** Wu" (sie ist Daniels Schwester; vorher „Ms. Wu").
  - P14: Daniels Echo-Zeile liegt auf `[JONAS_VOSS | style: recorded, distant]` — der Narrator erklärt es zwar („Not Voss. Only Daniel, echoing…"), aber auf Audio hört man zuerst unvermittelt Voss' Stimme. Riskantes Device, besser als NARRATOR-Zitat lösen.
- **REVIEW-Abgleich:** „Keine Auffälligkeiten" — Rewind und Geheimnis-Drift übersehen.

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)

1. **Mei Lins Geheimnis hat 4 Versionen:** Grace Ito (Ep2/3, Tipp 11:42pm, Dispatch-Records) → Lily Okafor (Ep5, on-air gestanden) → Marcus Delgado (Ep7, von Sun beerdigt — einzige Version, die Sun mitbelastet) → Bruder-Zeugenaussage (Ep10, „the one I was still holding onto"). Ursache: `case`-Blöcke in episodes.json wurden ab Ep4 und erneut ab Ep7/Ep10 neu erfunden.
2. **Ep10 spult zurück:** Lock-In läuft wieder / Mei Lin „gone dark", obwohl Ep8 Breach + Ep9 Booking bereits passiert sind.
3. **Lock-In-Mechanik wechselt:** Watch-Officer wegschicken + Recorder-Schalter (Ep1/2) vs. Supervisor-Override-Code 23:47 + Raum-3-Anforderung + Notausgangs-Circuit (Ep7+).
4. **Lock-In-Dauer:** „forty minutes" (Ep1) → „two days" (Ep4/6) → „weeks" (Ep6 P9) → „six hours" (Ep9) → „thirty-one hours" (Ep10).
5. **Zeitachsen-Inflation Daniel:** 32 Stunden (Ep1) → „weeks" (Ep4/5) → „months" (Ep6/9) → „three years of phone calls" (Ep5 P13!) → „eight/nine months" (Ep10, sogar intern widersprüchlich).
6. **Ledger-Dauer:** 3 Jahre (Ep4) → 18 Monate (Ep6) → 11 Jahre (Ep8) → 6 Jahre (Ep10). (Plan: 6 J. → 15 J. → 11 J. → 6 J.)
7. **Zoes Artikel erscheint zweimal** (Ep6 P1 und Ep8 P3) — Duplikat schon im Section-Plan.
8. **Raum-Nummer:** „Interrogation Room Two" (Ep1 P13, Ep2 P5/P7) vs. „Room 3" (Ep2 P4, Ep7–10); Stockwerk: „fourth floor" (Ep2) vs. Basement (Ep4+); Precinct 14 (Ep4) vs. Precinct Twelve (Ep9).
9. **Recorder-Licht blinkt rot** (Ep3 P10) trotz deaktivierter Aufzeichnung; Fenster im fensterlosen Raum (Ep3 P13).
10. **Mei Lins Sichtbarkeit:** angeblich seit Tagen verschwunden (Ep4/5), gleichzeitig plaudert sie im Bullpen (Ep6 P1), archiviert im Sub-Level (Ep7), sitzt am Schreibtisch (Ep9) — nie konsistent aufgelöst.
11. **Kestrel-Fragment:** Unit 214 genannt (Ep6) → „Unit number I don't have memorized" (Ep8). Voss' frühere Fragmente (Freight-Yard-Gebäude mit blauer Tür, Ep5) versanden.
12. **Shell-Firma:** „Voss Maritime Solutions"/Notizbuch (Ep6) → „Pacific Rim Freight Solutions"/Kassenbon (Ep7).
13. **Blue Lantern:** Bar (Definition, Ep3–5) → „guesthouse" mit Gästebuch (Ep7 P9); in Ep3 P3 zusätzlich durch Erfindung „The Anchor" ersetzt.
14. **Reyes:** pensionierter Vice-Cop (Ep4) vs. aktiver Docks-Fixer „Marcus Reyes" (Ep5).
15. **„Never once heard Anna Wu's voice"** (Ep4 P5) — widerlegt durch Ep1 P6.
16. Kai entdeckt dieselbe Log-Lücke dreimal (Ep4/5/6), einmal als 11:46 statt 11:47.

### Wiederholte Phrasen / LLM-Tics (gezählt via grep)

- **„You look tired(, Detective)"** — 7× (Ep4–7, 2× Ep6, 2× Ep10), fast immer Voss' Szenenauftakt.
- **„I'm not going anywhere"** — 8× über 7 Episoden (Voss' Signatur — 2–3× wäre Charakter, 8× ist Tic).
- **„Say that again(. Slower/Slowly)"** — 9× über 6 Episoden, von 4 verschiedenen Figuren (Sun, Zoe, Anna, Mei Lin) — nivelliert Figurenstimmen.
- **„That's not an answer"** — 9× über 7 Episoden.
- Style-Tag **„barely holding it together"** — 14×; NARRATOR-Floskel „lets the silence do the work/sit" — mehrfach.
- Kai wörtlich **„Not yet. Not until I know what I'm (actually) looking at"** — 4× (Ep2/3/4/6) als identischer Szenenschluss.
- SFX **„chair creak*"** — 59× in 10 Episoden; dazu die vielen nicht-hörbaren Pausen-Cues aus dem det-Check („long pause", „held breath", „exhale") — das SFX-Vokabular ist auf ~5 Gesten beschränkt.
- **NARRATOR leakt Thread-Labels on-air: 9×** (Ep2 P7, Ep3 P9, Ep4 P5+P8, Ep5 P11, Ep6 P10+P11+P13, Ep10 P7) — „The Captain's Ledger thread continues" etc. Interne Planungssprache im Hörtext.

### Thread-Bilanz

- **The Lock-In:** ~35 % Sendezeit — Rückgrat der Serie, gut dosiert, trägt bis Ep10.
- **The Detective's Secret:** ~25 % — dramaturgisch stark, aber durch die 4-Namen-Drift inhaltlich entwertet; Grace Ito wird nie aufgelöst.
- **The Captain's Ledger:** ~22 % — solide Eskalation (Zoe→Artikel→IA), aber Zahlen-Drift; Zoe verschwindet in Ep9/10 fast (nur Telefon + eine Dictate-Zeile im Finale).
- **The Missing Man:** ~18 % — Anna trägt ihn allein; zwischen Ep2 und Ep4 fast verhungert (in Ep2/3 kommt Anna gar nicht vor), im Finale stark zurück. Daniel selbst bleibt konsequent stimmlos — gute Entscheidung.

### REVIEW-Abgleich-Ergebnis

8 von 10 Reviews melden „Keine Auffälligkeiten" — das Review greift fast nur Case-Treue-Verstöße innerhalb einer Episode, keine Cross-Episoden-Kontinuität und keine Sprecher-/Location-Bugs. Bilanz: **Ep1 behoben ✔, Ep6 behoben ✔, Ep2 beide Flags unbehoben ✘.** Übersehen wurden u. a.: ZOE_HAN-als-Bartender (Ep5 P5), rotes Recorder-Licht (Ep3), Kestrel-Widerspruch (Ep8), Ep10-Rewind — das LLM-Review braucht ein Kontinuitäts-Gedächtnis (Vorepisoden-Summary als Kontext).

## Top-5 konkrete Korrekturen (priorisiert)

1. **Ep5 P5: Bartender-Zeilen von ZOE_HAN entfernen** — die drei Zeilen („Something like that." / „Lot of names come through this place…" / „…") in NARRATOR-Paraphrase umwandeln oder Anna einseitig sprechen lassen (wie Ep4 P7). Kleinster Eingriff, größter Audio-Schaden. 
2. **Geheimnis auf EINE Version vereinheitlichen (empfohlen: Grace Ito, da am tiefsten etabliert):** Ep5 P2/P3 „Lily Okafor"→Grace Ito, Ep7 P6 Delgado-Passagen angleichen, Ep10 P2+P13 auf die Ito-Geschichte umschreiben („destroyed witness statement" streichen). Alternativ nur Ep10 fixen und Ep5/7 als Vertiefungen derselben Ito-Akte umformulieren. Root-Fix für Zukunft: `case`-Blöcke bei create_series einmal erzeugen und in Folgeepisoden nur fortschreiben (previous_season/Pointer-Mechanik aus dem Editier-Vertrag auch innerhalb der Staffel anwenden).
3. **Ep10 P1/P2/P9 an Ep8/9 anschließen:** Sun weiß längst Bescheid (Breach war öffentlich); P1 auf „IA-Frist läuft" umstellen, P2 als offiziell begleitetes letztes Gespräch vor dem Transfer rahmen, P9-Formularfälschung in „Protokoll der Nachbefragung schönen" ändern. 
4. **Die 9 NARRATOR-Thread-Label-Leaks löschen** (Ep2 P7, Ep3 P9, Ep4 P5/P8, Ep5 P11, Ep6 P10/P11/P13, Ep10 P7) — reine Ein-Satz-Edits; zusätzlich Prompt-Regel: Thread-Labels sind Planungsmetadaten und dürfen nie in Prosa erscheinen.
5. **Ep4 Recap nachrüsten + Zeitreferenzen normalisieren:** Ep4 P1 eine „Previously on"-NARRATOR-Zeile voranstellen (Vorlage Ep5 P1); global „weeks/months/three years/eight-nine months" auf eine Tages-Uhr mappen (Suchliste: Ep4 P5, Ep5 P13, Ep6 P8, Ep8 P2/P3, Ep9 P4, Ep10 P4/P11). Root-Fix: Staffel-Zeitanker („Tag N seit Daniels Verschwinden") in den Stage-2-Kontext geben.
