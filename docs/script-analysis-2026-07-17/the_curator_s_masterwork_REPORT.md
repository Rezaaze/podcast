# the_curator_s_masterwork — Tiefenanalyse

## Serien-Überblick

**Prämisse:** Soap-Opera-Krimi (10 Episoden, 15 Parts/Episode): Detective Marcus Reid wird von einem Serienmörder ("The Curator", Ex-Linguistikprofessor Arthur Lin) per Cipher-Briefen persönlich adressiert. Drei Threads: **The Cipher Killings** (der Curator formt Reid heimlich zum Vollstrecker seines "Masterwork"), **The Frame-Up** (der Unschuldige Daniel/Danny Chen wird als Ablenkung geopfert, Schwester Joy kämpft öffentlich), **The Marriage Collapse / The Reid Marriage** (Mia driftet in Anwältin/Auszug).

**Gesamturteil: 6/10.** Die Prosa- und Dialogqualität ist über weite Strecken die beste, die ich in dieser Pipeline-Phase erwarten würde: konsequent "clipped and loaded", starke Subtext-Duelle (Park/Reid-Diner-Szenen, Hollis-Warnungen), eine glaubwürdig gestufte Erosion Reids und ein Curator, der nie seinen Plan monologisiert, sondern nur in Metaphern von Grammatik und Komposition spricht — genau wie die style_guidelines es verlangen. ABER: Die harte Faktenkontinuität ist über die Staffel hinweg brüchig (Beweislage gegen Chen wird 3× ausgetauscht, Zeitachse explodiert von Wochen auf "zwei Jahre", der Finale-Treffpunkt wechselt zwischen ep9 und ep10 den Ort), der NARRATOR spricht 22× Produktions-Thread-Labels hörbar aus (inkl. ~10× wörtlich "The Frame-Up thread" — das Label selbst spoilert Dannys Unschuld), und der einzige LLM-Review-Befund der Staffel (ep4) wurde nie behoben.

**Fairness-Einordnung:** Serie vom 14.07 — Episoden-Review und Beat-Layer aktiv, SFX-Hörbarkeits-Regel noch nicht (die ~60 nicht-hörbaren Cues aus det_findings sind zeitgemäß und hier nicht angelastet). `generation.use_beats: false` steht in episodes.json, BEATS-Dateien existieren aber.

---

## Episode 1: First Correspondence

**Stärken:**
- Sehr starker Cold Open (Wache findet arrangierte Leiche, Umschlag mit Reids Namen); die Curator-Soloszenen (P4, P10) etablieren den Sammler-Ton perfekt ("Patience is the only signature that matters", "Soon, Marcus").
- Mias Warteszene (P3) mit dem Beginn ihrer privaten Liste ist elegantes Setup des objective_fact "private notes".
- Reids Verschweigen wird gezeigt, nicht erklärt (P2: "He doesn't correct her").

**Schwächen:**
- P5/P13/P14/P15 sind vier fast identische "Reid allein nachts mit dem Cipher"-Szenen — die Episode tritt in der zweiten Hälfte auf der Stelle.
- Drei Parts unter Wortbudget (P3, P4, P8 — det_findings), P4 und P8 weil die Szenen inhaltlich Ein-Beat-Szenen sind.

**Fehler (korrigierbar):**
1. **P1 vs. P2 — Konzeptbruch beim Kern-Geheimnis:** P1 zeigt den Umschlag öffentlich adressiert ("Not 'Homicide Division'… Just a name — Detective Marcus Reid"), eine Streifenpolizistin liest ihn zweimal. In P2 liest Park den Brief als Rang-Adresse vor ("'To the detective who will carry this.' … Killer's addressing rank, not a person") und schließt "Lead detective. Courtesy address. Nothing weirder than that." Damit ist Reids `hides` ("er verschweigt Hollis, dass der Brief ihn persönlich nennt") von der Inszenierung selbst unterlaufen — jeder am Fundort hat seinen Namen auf dem Umschlag gesehen.
2. **P2 vs. P15 — Doppelte Enthüllung:** P2-Narrator: "his name, and a date only he and one other person would recognize" + "the two words that named him and the day he married Mia". P15 inszeniert exakt diese Erkenntnis ("That's our anniversary. Mine and Mia's… cold realization") als Episoden-Cliffhanger — der Schluss-Beat ist beim Hörer längst verbraucht.
3. **P2 vs. P13 — Opfer wechselt das Geschlecht:** P2 Park: "Machinery arranged around **him**"; P13 Reid am selben Tableau: "He didn't just leave **her** here — he set **her** here."
4. **P14 — Datumslogik:** "Anniversary. Four months out. He knew that before I did." — der Jahrestag war laut P3/P7 an diesem Tag.

## Episode 2: The Wrong Name

**Stärken:**
- Joys zwei Courthouse-Auftritte (P3, P10) haben echte Steigerung und eigene Stimme ("laziness dressed up as police work").
- P12 (Park verhört Daniel erneut, Daniel nur per Narrator paraphrasiert) ist ein sauberer Workaround für die fehlende Daniel-Stimme.
- Curator P4 bleibt vorbildlich indirekt ("A tidy little chapter…").

**Schwächen:**
- P2-Verhör: Reid fragt Daniel, aber Park antwortet aus der Akte — funktioniert, liest sich aber gestelzt.
- Der dritte Brief, der Reid am Ende von ep1 im Diner persönlich zugesteckt wurde, wird nie wieder erwähnt (Recap nennt nur "a second cipher") — verlorener Faden.

**Fehler (korrigierbar):**
1. **P3 vs. P10 — Trespassing-Alter:** P3 Joy: "when he was nineteen"; P10 Joy: "on a dare when he was twenty-two" (P1 Park: "four years back" bei Alter 26 ⇒ 22).
2. **P6 — Ortsfehler im Narrator:** "Riverside Overlook… a new letter has been found where the first tableau stood" — das erste Tableau stand in der Mill, nicht am Overlook.
3. **P5 vs. ep1 P9 — Zeitachse:** Hollis ep2: "Two months, two ciphers, no suspect"; ep1 P9 Hollis: "Second one in a week."
4. P1: "One priors" (Grammatik).

## Episode 3: Rules of the Game

**Stärken:**
- Das Kernstück (Cipher aus Reids altem Fall) trägt: P1s stiller Schock und P11s Mill-Erkenntnis ("They were there. Before I ever touched the case") sind die stärkste Cipher-Eskalation der Staffel.
- P4 (Reid lässt den Log-Eintrag unvollendet) inszeniert die erste echte Prozedur-Verletzung als Mini-Drama — genau die "graduelle Erosion" der style_guidelines.
- P7/P14 Park-Diner-Doppel ("I checked with records. They don't have it.") — präziser Druckaufbau.

**Schwächen:**
- Mia-Szenen P2 und P10 sind nahezu dieselbe Szene (Reid liest, Mia erreicht ihn nicht).

**Fehler (korrigierbar):**
1. **P8 — Sprecher-Fehlzuordnung (gravierend):** Die Argumentation der Pflichtverteidigerin liegt auf REID: "[REID | style: clipped] No corroborating witness. No motive on record… You want us to build the rest of it on a torn receipt he could've dropped six months before…" — direkt nachdem Reid selbst "So the physical link holds" gesagt hat. Die Verteidigerin hat keinen Voice-Slot; ihre Rede wurde Reid in den Mund gelegt und kehrt seine Position mitten in der Szene um.
2. **P1 vs. P11 — Altfall-Alter:** P1: "a night eight years gone"; P11: "Case closed nine years ago" (derselbe Ashworth-Fall).
3. P8: "[DET_PARK | style: gentle, to DANIEL]" — Zeile geht inhaltlich an Reid, nicht an Daniel.
4. P3 Curator "Twelve years of careful strokes" vs. Reids "Ten years" (P2) / "more than a decade" (Konzept) — weiche Drift.

## Episode 4: The Gallery Opens

**Stärken:**
- Die Galerie-Begehung P2 mit Reids gespieltem Schock ("performed shock") ist dramaturgisch die cleverste Szene der Staffel — der Hörer weiß, dass Reid schon dort war.
- Curator P12 (Verweildauer-Protokoll: "Eleven minutes at the third") ist gänsehautwürdig und rein beobachtend.
- Mias P11-Telefonat (Foto wandert ins Wohnzimmer, "I'm not ready to make it real by saying it out loud twice") — bestes Marriage-Material bisher.

**Schwächen:**
- Park bekommt mit P8 (Telefonat mit Freundin) eine Szene, die ihre ep3-Erkenntnisse (fehlender Brief!) auf "it's a feeling" zurücksetzt.

**Fehler (korrigierbar):**
1. **P1 — Recap widerspricht ep3:** "Captain Hollis… authorized Reid to keep working the cipher his own way" — ep3 P12 endete mit dem Gegenteil ("By-the-book… No exceptions"). Zudem sagt der Recap hörbar "Danny Chen's **frame-up**" — Auflösungs-Vokabular in Publikums-Narration.
2. **P1/P2 — Mill als Neuentdeckung:** Reid schlägt die Mill als frischen Lead vor, Hollis: "That's a stretch from one dead metaphor" — die Mill ist seit ep1 der zentrale Tatort (Leiche im Cold Open, Forensik-Sweeps, Parks Anwesenheit). Nur die versteckte Galerie dürfte neu sein; das Skript behandelt das ganze Gebäude als unbekannt.
3. **Beweis-Austausch (Staffelbruch beginnt hier):** Joy P3: "A shoe print outside a perimeter fence. **That's it. That's the case.**"; Hollis P4: "A shoe print at the perimeter. The argument with the victim, on camera." — Der thumbprint-Kassenbon aus ep2/3 (einziges Beweisstück, mehrfach zitiert) ist ersatzlos verschwunden. (Ursache: objective_facts-Drift in episodes.json ep4-6.)
4. **P5 + P12 — REVIEW-Befund nicht behoben:** ep4_REVIEW flaggt "All of it burning exactly where I set the kindling" (steht in P12) als vorzeitige Enthüllung, dass der Curator das Frame-Up inszeniert hat. Zeile ist unverändert drin; P5 leakt zusätzlich "I chose well" und "Every hour they spend on him is an hour they aren't spending on… me."
5. **P3 vs. P9 vs. P13 — Haftdauer:** Joy P3: "three weeks" (2×); Park P9: "Two weeks in that chair"; Joy P13: "standing on those steps for two weeks".
6. **P5 vs. P12 — Curator-Studierzimmer wandert:** P5 "a locked room above a shuttered print shop"; P12 "a windowless room above the old mill's east wing" (ep1: "the private room behind his house") — drei Orte für denselben Raum.
7. P13 — Ortssalat bei Joy: "A cramped office above a print shop… has turned her **apartment** into a war room" (und recycelt ausgerechnet die Print-Shop-Adresse des Curators aus P5).
8. P3: "a apartment" (Grammatik).

## Episode 5: Breaking Point

**Stärken:**
- P1 (Mia wartet im Mantel auf den Termin, der verstreicht) ist die beste stille Szene der Staffel — reine Audio-Dramaturgie ohne ein einziges Reid-Wort.
- Der Küchenstreit P6/P9 eskaliert glaubhaft ("What's new is I stopped believing you'd choose anything else").
- Curator P3 (Auswahl, welches Detail in den Cipher kommt: "A hammer where I need a needle") zeigt Manipulation als Handwerk — stark.

**Schwächen:**
- **Parks Entdeckung dreht sich im Kreis:** P2, P8 und P12 inszenieren dreimal in einer Episode "Park findet den Log-Widerspruch", mit inkompatiblen Details (P2: Item vier-elf, 40 Minuten; P8: Item einundvierzig, ~24 Stunden; P12: "Intake says the fourteenth. His notes say the twelfth. That's two days."). Als Eskalation geplant, als Wiederholung geschrieben.

**Fehler (korrigierbar):**
1. **P1 vs. P6 — Terminzeit:** P1: "Morning… dressed and ready for the counseling session"; P6 Mia: "Four o'clock. That's when it was supposed to start… past four, then four-thirty, then five."
2. **P11 — Regieanweisung im gesprochenen Text:** Curator-Zeile: "Tonight he sat in his car at the overlook for — **he checks his watch** — an hour and eleven minutes" — TTS spricht die Regieanweisung mit.
3. **P5 vs. P14 — Dauer:** Joy P5: "For six weeks my brother has been living like a man already convicted"; Joy im TV-Clip P14: "My brother has spent **months**…".
4. P4: "Ballistics finally cleared the second slug. Same weapon" — erstmals Schusswaffen; die Staffel hat die Tötungsart sonst bewusst offen gelassen (ep3: "a knife or a rope"), wirkt als Fremdkörper.

## Episode 6: The Captain's Warning

**Stärken:**
- Hollis' Doppel-Warnung (P1/P13) mit "This time I'm using the word 'last'" und seinem Solo P10 ("Same as always. That's not a no.") — Hollis wird hier zur besten Nebenfigur.
- P4 (Reid steckt Beweisstück in "drawer three. My drawer.") vollzieht die geplante bewusste Unterschlagung sauber und begründet ("That's not concealment. That's discipline").
- P15-Cliffhanger (Porch-Light-Detail, das nur Mia kannte) ist ein präziser Gruselbeat.

**Schwächen:**
- P9 (Danny bricht zusammen) komplett narratorisiert — angemessen, aber nach P2 und ep5 P7 die dritte reine Erzähl-Szene im Justizstrang; der Thread verliert hörbare Stimmen.

**Fehler (korrigierbar):**
1. **P9 — Dannys Job/Alter unmöglich:** "the warehouse let him go… **sixteen years, his father's old position**" — Danny ist 26 (ep2), hätte also mit 10 angefangen; ep5 P5 sagte "He fixes bicycles for a living."
2. **P9 — Opfer wieder weiblich:** "he was never inside, never near **that woman**" — ep1-Opfer war männlich (bzw. wechselte schon in ep1).
3. P6-Narration: "the **frame** has already done its work" — erneut Lösungs-Vokabular hörbar.

## Episode 7: Mirror Image

**Stärken:**
- Die Spiegel-Idee trägt die ganze Episode: P1 (Reid rutscht beim Analysieren in Curator-Kadenz, "That's not his line. That's mine."), P4 (Verhör mit Curator-Methode, Park zählt Sekunden hinterm Glas), P14 (Sprechen im Schlaf) — konsequent, unheimlich, hörbar.
- P7 (Park und Mia treffen sich zufällig) — die zwei Beobachterinnen synchronisieren sich, ohne Geheimnisse zu leaken; exakt die character_knowledge-Slices.
- P15 (alte Fotos, "He didn't find me in these letters. He made me in them.") — starker Akt-Schluss + Lab-Report-Hook.

**Schwächen:**
- P2/P10/P15 sind drei Varianten von "Cipher enthält privates Kindheitsdetail" — einzeln gut, zusammen redundant.

**Fehler (korrigierbar):**
1. **P8 — Erfundene Kinder:** Narrator: "in a kitchen gone quiet **after the children's bedtime**, Mia Reid waits for her husband" — die Reids haben in Konzept und allen Episoden keine Kinder.
2. **P5 — Haftdauer springt zurück:** "my brother… has been in this department's custody for **eleven days**" — ep4 sagte bereits "three weeks in a cell", ep5 "six weeks".
3. **P5 — Dritter Job in drei Episoden:** "Six months ago my brother was a man who **fixed vending machines** for a living" (ep5: Fahrräder; ep6: Warehouse seit 16 Jahren).
4. P5 vs. P12 — Verletzung wechselt: "six stitches above his left eye" (P5) → "a broken rib" (P12), derselbe Übergriff.

## Episode 8: Sacrifice Play

**Stärken:**
- P1/P2 (Reid liest den entlastenden Bericht und schließt die Schublade: "I haven't done anything yet.") — der moralische Tiefpunkt als Zwei-Parts-Kammerspiel, hervorragend.
- P3 (Tableau mit gekippter Waage + Schlüssel, "eleven forty… hours after he closed a drawer") — der Curator kommentiert Reids geheimste Tat in Objektsprache; beste Clue-Konstruktion der Staffel.
- P9 (Informanten-Erpressung: "I'm not threatening you. I'm describing Tuesday.") — kälteste, beste Reid-Zeile der Staffel.
- P14 (Reid will endlich einreichen — zu spät, Plea läuft schon) — die Ironie sitzt.

**Schwächen:**
- Parks Log-Entdeckung wird in P6 ERNEUT als Erstfund inszeniert ("Entry four-forty-one… That's not right") — nach ep5 (3×) und ep6; der Thread kommt vier Episoden lang nicht von der Stelle.

**Fehler (korrigierbar):**
1. **P13/P14 vs. P15 — Plea passiert zweimal:** P13 zeigt Daniel im Gerichtssaal "guilty" sagen; P14 Reid: "He plead **this afternoon**." P15-Schlussnarration: "Across the city… Daniel Chen **signs the plea** the state offered him" — das Konzept-outro wurde wörtlich übernommen, obwohl die Szene schon gespielt war.
2. **P14 — "eleven days" vs. Episoden-Chronologie:** Der Bericht kommt in P1 dieser Episode an; P14 ("later that same night" nach P13) behauptet elf Tage Wartezeit. Zusätzlich Handoff-Bruch zu ep7: dort lag der Report bereits auf dem Schreibtisch, "briefing starts in ten minutes" — ep8 lässt ihn neu per Kurier am Spätnachmittag ankommen.
3. **P9 — Grain-Depot-Lead versandet:** "The old grain depot. West side, past the rail cut. He's been going back there since before the first letter." — wird in ep9/ep10 nie wieder erwähnt; das Finale findet stattdessen in der Mill statt.
4. P12: Diner-Beleg von der "Ferris Street" um 21:40 vs. P9-Laundromat "past midnight" auf der Ninth Street — als Lügenbeweis gegen Reids "Precinct bis Mitternacht" ok, aber die Geografie bleibt Zufallssalat.

## Episode 9: The Puppet Strings

**Stärken:**
- P1 (Reid legt alle Ciphers chronologisch: "That's not a crime scene timeline. That's **my** timeline.") — die Erkenntnis-Szene, auf die die Staffel zulief; sauber gebaut.
- P6 (Park legt Reid die Akte vor: "I know the difference between a man under pressure and a man lying to my face. This is the second one.") — bester Dialog-Showdown der Staffel.
- P8 (Hollis eröffnet die Untersuchung sofort: "Because if I sit with it one more night, I'll find a reason not to.") — Figurenlogik perfekt.
- P10 (Auszugs-Streit, "So what, I'm supposed to let him win because you're lonely?") — der eine Satz, der die Ehe beendet; verdient.

**Schwächen:**
- Sieben von 15 Parts sind Solo-Monolog-Szenen; die Episode ist gesprächsärmer als jede andere.

**Fehler (korrigierbar):**
1. **P5 — Zeitachsen-GAU:** Joy: "Two years. He took the plea **two years ago** believing there was nothing else." — Der Plea war letzte Episode; die Staffel spielt in Wochen/Monaten.
2. **P12 — Zweite falsche Zahl:** "My brother signed a plea **eleven months ago**." — widerspricht sowohl P5 (zwei Jahre) als auch der realen Staffelchronologie; zwei inkompatible falsche Zeitangaben in derselben Episode.
3. **P13 vs. P14 — Brief-Zustand:** P13 öffnet und liest Reid das IA-Schreiben wörtlich vor; P14-Narrator: "notice of suspension **still unopened** beside him."
4. **P14 vs. ep10 P1 — Finale-Summons:** "**Pier Fourteen. Eleven o'clock** tomorrow night", unter der Tür durchgeschoben — ep10 P1 liest dieselbe Botschaft als "**Old Textile Mill. Tomorrow, nine o'clock**", gefunden am Riverside Overlook. Ort, Uhrzeit und Zustellweg des Staffel-Höhepunkt-Briefs widersprechen sich.
5. P1: "the week I buried the **Whitlock** report" — Name taucht nirgendwo sonst auf (der vergrabene Bericht ist der Chen-Lab-Report).

## Episode 10: The Masterwork

**Stärken:**
- P8 (Konfrontation: "I wasn't hunting a detective who could catch me, Marcus. I was looking for one I could **raise**." / "Not to be caught by you. To be finished by you.") — der Twist landet mit genau der kontrollierten Curator-Stimme, nie als Monolog des Gesamtplans.
- P7/P10 Parallelmontage (Park liest das Journal, während Reid unten steht: "He's finishing a painting somebody else already signed.") — strukturell das Beste der Staffel.
- P14 (Diner-Nachspiel: "You told me a version." / Vor- und Nachname als Nähe-Barometer) und P15 (kein Verdikt von Mia) — das bewusst Unaufgelöste des series_outro wird eingelöst.

**Schwächen:**
- **P9 — der Mord selbst ist 103 Wörter kurz** (det_findings: unter Budget) und akustisch nur "[SFX: a single decisive movement, cloth or metal]" + "It's done." Gewollt off-page, aber als Audio-Klimax zu dünn: der wichtigste Beat der Staffel ist ihr kürzester Part.
- Mia ist in P2 und P15 wie selbstverständlich in der Wohnung, obwohl sie in ep9 P10 ausgezogen ist ("I'll send someone for the rest this weekend") — kein Wort der Erklärung.

**Fehler (korrigierbar):**
1. **P1 — "Nowhere anyone's looked":** Reid über die Mill-Adresse: "Nowhere we've looked. Nowhere anyone's looked." — Die Mill ist seit ep1 Fundort, Galerie (ep4) und mehrfach forensisch bearbeitet; die Zeile ist im Kontext absurd.
2. **P1 vs. P6 — Uhrzeit:** Note sagt "nine o'clock", P6-Narrator: "The Old Textile Mill, **past midnight**."
3. **P3 vs. P12 — Dauer im selben Skript:** Joy P3: "**Six months ago**, my brother was arrested"; Joy P12: "He tried to die in a cell **eleven months ago**" + Narrator "after a **year** of being disbelieved".
4. **P3/P12 — Retcon Suizidversuch:** "My brother tried to end his life in a cell" wird als bekannte Vergangenheit behandelt — in ep1-9 nie erzählt (ep8 zeigte stattdessen den Plea); stammt aus der ep10-Konzeptfassung des Threads.
5. **P13 — Sprecher-Fehlzuordnung:** "A junior officer leans in." — die Zeile trägt aber das Tag [DET_PARK]: "Captain. The mill report's in… And — the journal transcript **Park sent over**." Park spricht über sich selbst in dritter Person; die Officer-Zeile wurde ihr zugeordnet (kein Voice-Slot für Nebenfiguren).
6. **P3/P4/P11 — dritte Beweis-Version:** "A torn ticket stub. A shift log with a typo" (P3), "a ticket stub, a shift-log discrepancy" (P4, P11) — ersetzt kommentarlos sowohl den Kassenbon+Daumenabdruck (ep2-3) als auch Schuhabdruck+Video (ep4-6).
7. P5 vs. P6: Park erzwingt Begleitung ("I'm driving separately. I'll be there before you finish parking"), P6 lässt Reid allein ankommen und Park erst überraschend nachkommen ("Park has followed him **after all**").

---

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)

1. **Beweislage gegen Chen — drei inkompatible Versionen:** ep2-3: zerrissener Kassenbon mit Daumenabdruck (einziges Beweisstück, wörtlich "That's the entire physical case"); ep4-6: Schuhabdruck + aufgezeichneter Streit + Kamera-Timestamp ("That's it. That's the case"); ep10: Ticket-Stub + Schichtplan-Diskrepanz. Nie wird ein Wechsel erklärt. (Wurzel: episodes.json trägt pro Episode andere objective_facts.)
2. **Zeitachse:** ep1 "second one in a week" → ep2 "two months, two ciphers" → ep8 Plea → ep9 "two years ago"/"eleven months ago" → ep10 "six months"/"eleven months"/"a year". Die Staffel hat keine konsistente Dauer.
3. **Finale-Summons:** ep9 "Pier Fourteen, eleven o'clock, unter der Tür" vs. ep10 "Old Textile Mill, nine o'clock, am Overlook" (und dann "past midnight" gespielt).
4. **Mill-Status:** zentraler Tatort ab ep1, in ep4 als Neuentdeckung inszeniert, in ep10 "nowhere anyone's looked".
5. **Danny/Daniels Job:** Fahrradmechaniker (ep5) → Warehouse seit 16 Jahren (ep6, unmöglich bei Alter 26) → Vending-Machine-Techniker (ep7). Plus Laundromat-Vergangenheit (ep2).
6. **Haftdauer-Regression:** 2 Tage (ep2) → 3 Wochen (ep4) → 6 Wochen (ep5) → 11 Tage (ep7).
7. **Name Daniel ↔ Danny:** ep1-3 Daniel, ep4-6 überwiegend Danny, ep7-10 wieder Daniel (folgt der Konzept-Drift).
8. **Marriage-Thread-Label wandert im Konzept** (The Marriage Collapse ↔ The Reid Marriage) samt dreier Lösungs-Fassungen — die Skripte gleichen es leidlich, aber Anwalts-Timeline ("once", "two weeks ago", "already scheduled follow-up") springt.
9. **Curators Versteck:** hinterm Haus (ep1) / über Print-Shop (ep4 P5) / über dem Mill-Ostflügel (ep4 P12) / "Stone room" (ep8) — vier Orte.
10. **Opfer-Geschlecht** wechselt innerhalb ep1 (him→her) und erneut ep6 ("that woman").
11. **Erfundene Kinder** der Reids (ep7 P8) — einmalig, widerspricht allem.
12. **Suizidversuch Daniels** (ep10) nie zuvor erzählt; ep8 zeigte stattdessen den Plea — inkompatible Frame-Up-Endgames beider Konzeptfassungen wurden beide verfilmt.
13. **Mias Auszug** (ep9) vs. Anwesenheit in der Wohnung (ep10 P2/P15) unerklärt.
14. **Ep1-Diner-Note** (dritter Brief) und **ep8-Grain-Depot-Lead** versanden vollständig.

### Wiederholte Phrasen / LLM-Tics (Zählung über alle 10 Skripte)

- **"Not yet."** — 38× (Reid, Park, Hollis, Mia, Curator — jede Figur benutzt denselben Cliffhanger-Verschluss; pro Episode 3-5×).
- **Narrator-Thread-Ansagen** — 22 hörbare Meta-Ansagen ("The Frame-Up thread returns/resumes/continues", "Cipher Killings thread", "the marriage thread") — Produktionsvokabular in der Erzählstimme.
- **"barely audible"** als Style — 64× (Dauerflüstern; TTS-Styles, nicht hörbar, aber monotonisierend).
- **Chair creak** — 50 SFX-Cues; **clock ticking** — 32 SFX-Cues (das det_findings-Muster "Stille+Uhr/Stuhl" ist der Default-Szenenschluss).
- **"a moment longer than …(the moment requires/the conversation calls for)"** — 11× Narrator-Formel.
- **"a beat too long/too fast"** — 9×.
- **"That's all this is."** — 9× (Selbstberuhigungs-Formel von Reid UND Park UND Joy).
- **"folds the note/letter along its original crease"** — 5×.
- **"Nobody needs to know (I was here)"** — 5× Reid.
- **"There you are."** — 6× (Curator-Signature — hier als bewusstes Motiv vertretbar, aber auch Mia benutzt es ep1).
- Szenenformel: fast jede Reid-Soloszene beginnt "past midnight" + "alone" + endet mit ungeloggtem Abgang — mindestens 9 strukturell identische Parts (ep1 P13/15, ep2 P11, ep3 P9/P11, ep4 P10/15, ep6 P8/15, ep7 P11).
- Namens-Tic "Ferris": Ferris-Einbruch (ep1), Ferris Street Kindheit (ep7), Diner an der Ferris Street (ep8).

### Thread-Bilanz

- **Cipher Killings: ~55-60%** der Parts — dominiert, aber inhaltlich gerechtfertigt; Schwäche: 4 Episoden lang (ep5-8) besteht Parks Anteil aus derselben, sich widersprechenden Log-Entdeckung.
- **Frame-Up: ~25%** — gut versorgt, Joy hat in jeder Episode mindestens einen starken Auftritt; leidet am stärksten unter den Faktenwechseln (Beweise, Job, Dauer), weil er der faktenlastigste Thread ist.
- **Marriage: ~20%** — bestens dosiert, klarste Eskalationslinie (Liste → Anwältin → Ultimatum → Auszug → kein Verdikt); kein Thread verhungert.

### REVIEW-Abgleich-Ergebnis

- 9 von 10 Reviews: "Keine Auffälligkeiten." — angesichts von ~35 konkreten Fehlern ist das Review-Netz dieser Phase praktisch blind (es prüfte offenbar nur Spoiler-Logik, keine Faktenkontinuität).
- Der EINZIGE Befund (ep4: Curator-Zeile "kindling" leakt Frame-Up-Urheberschaft) ist **nicht behoben** — Zeile steht in P12 (Review nannte Part 5; auch die Partnummer im Review stimmt nicht), zusätzlich leakt P5 "I chose well". Konsequenz: Der Hörer weiß ab ep4 sicher, was das Konzept erst in ep10 auflösen wollte — verstärkt durch das ~10× hörbar gesprochene Label "Frame-Up" ab ep2.

---

## Top-5 konkrete Korrekturen (priorisiert)

1. **Finale-Handoff reparieren (ep9 P14 / ep10 P1+P6):** Summons vereinheitlichen — ein Ort (Old Textile Mill), eine Uhrzeit, ein Zustellweg; in ep10 P1 "Nowhere we've looked. Nowhere anyone's looked." streichen/ersetzen (z. B. "Der einzige Ort, den wir nie versiegelt bekommen haben"). Reiner Hand-Edit von ~6 Zeilen.
2. **Beweislage gegen Chen kanonisieren:** Eine Beweis-Trias festlegen (Kassenbon+Daumenabdruck als Kern, Schuhabdruck+Kamera als ep4-Zusätze) und ep4 P3/P4, ep10 P3/P4/P11 darauf umschreiben ("ticket stub"→"receipt"). Pipeline-Fix: `case[].objective_facts` müssen über Episoden stabil bleiben (create_series generiert sie derzeit pro Episode neu — Wurzel aller Frame-Up-Brüche).
3. **Zeitachsen-Sätze purgen:** ep9 P5 ("two years"), ep9 P12 + ep10 P12 ("eleven months"/"a year"), ep10 P3 ("six months") auf eine Staffeldauer (z. B. "Monate") normieren; ebenso Haftdauer (ep7 P5 "eleven days").
4. **Sprecher-Fehlzuordnungen fixen:** ep3 P8 (Verteidigerinnen-Rede unter REID → als Narrator-Paraphrase umbauen wie ep5 P7), ep10 P13 (Officer-Zeile unter DET_PARK → Narrator), ep5 P11 ("he checks his watch" aus dem Curator-Text streichen), ep7 P8 ("after the children's bedtime" streichen).
5. **Spoiler-Disziplin des Narrators:** Alle 22 Thread-Label-Ansagen entfernen (Ortsangabe genügt), Recap ep4 P1 "frame-up"→neutral ("the Chen arrest"), und die zwei ep4-Curator-Leaks (P5 "I chose well", P12 "kindling") entschärfen — damit wäre auch der offene REVIEW-Befund endlich umgesetzt. Pipeline-Fix: Template-Regel "NARRATOR nennt nie Thread-Labels oder Lösungs-Vokabular".
