# amity_hollow — Tiefenanalyse

**Stand:** 16.07-Generation (8-Folgen-Format, Editier-Vertrag, Beats + LLM-Review aktiv). soap_opera, mode drama, 8 Episoden à 16–17 Parts, ~4.0–4.4k Wörter/Episode.

## Serien-Überblick

**Prämisse:** Ein Digital-Forensik-Team untersucht das spurlose Verschwinden aller 41 Bewohner des Bergdorfs Amity Hollow. Einziger "Überlebender": der stumme Junge Milo, der zwanghaft ein Symbol zeichnet. Die Spur führt über ein Infraschall-Signal in Smart-Home-Hubs zu einem Bunker des Konzerns Halcyon Vantage — und Milo entpuppt sich im letzten Frame als platzierter Köder.

**Threads:** (1) Das Signal/Halcyon-Experiment (Haupt), (2) Yunas Doppelleben, (3) Wei Zhous verheimlichte Familie (Zhao/Zhang), (4) Old Chens Bauherren-Schuld (ab Ep3), (5) Milos wahre Rolle (implizit ab Ep1, benannt ab Ep7).

**Gesamturteil: 6/10.** Auf Szenenebene ist das die bisher stärkste Schreibe der Pipeline: unterscheidbare Stimmen, konsequente Wissens-Slices, Subtext statt Exposition, sauber eskalierende Cliffhanger. Aber die serienweite Fakten-Kontinuität ist katastrophal — und die Wurzel liegt in der episodes.json selbst: Die case-Blöcke wurden pro Episoden-Paar neu generiert und mutieren dabei den Kanon (Enkelin *Mara* → *Iris* → *Grace*; vermisst seit *19* → *11* → *22* Jahren; Cousinen-Familie *Zhao, 14 Birch Lane, 4 Personen* → *Lian Zhang, 5 Personen*; Yunas Motiv *Mutter-Schulden* → *Jobangebot+Einwanderungspapiere*). Die Skripte übernehmen diese Drift ungefiltert, sodass ein Hörer harte Widersprüche zwischen Ep4/6/8 hört. Das LLM-Review hat davon fast nichts gefangen (7×"Keine Auffälligkeiten"), und den einen echten Fund nicht fixen lassen.

---

## Episode 1: Half-Eaten Dinners

- **Stärken:** Sehr starker Kalt-Einstieg (NARRATOR-Panorama des eingefrorenen Dorfs, PART 1); Jonahs Tatort-Monolog (PART 2) etabliert Figur + falscher Glaube ("Cult. Staged exodus") exakt nach `believes_falsely`; Wei Zhous 14-Birch-Lane-Moment (PART 13, speed 0.85) ist ein Muster-Beispiel für "zeigen statt ausplaudern"; Yunas nächtlicher Anruf (PART 12) verankert das Mutter-Schulden-Motiv aus dem Case.
- **Schwächen:** PART 12/13 unter Wortbudget, weil die Szenen als Solo-Vignetten inhaltlich dünn geplant sind (ein Beat, kein Gegenspieler); NARRATOR trägt in PART 1/6 viel Deutungsarbeit ("It's also… exactly wrong" — gewollt, aber nah an Overtelling).
- **Fehler (korrigierbar):**
  - PART 2: „still got steam coming off it an hour after nobody's touched it" — kollidiert mit dem Case-Fakt (letzte Pings 21:47 Uhr, Team kommt in der Abenddämmerung an) und mit allen späteren Zeitangaben. Steam nach Stunden/Tagen unmöglich.
  - PART 13: „Zhao. Two adults, two children" — Familiengröße 4; Ep3 sagt 5 („Five of them. Both kids"), Ep5+ heißt die Familie Zhang.

## Episode 2: The Symbol in the Static

- **Stärken:** Watermark-Erklärung (PART 2/3) als Konflikt Jonah↔Wei statt Vortrag — Jonahs Whistleblower-Trauma motiviert seine Skepsis („I've built a theory on a hunch before"); Milos platzierte Mikro-Variation der Zeichnung (PART 5) ist elegantes Audience-ahead; Cliffhanger (PART 17: Jonah sieht Yuna erstmals bewusst nach) genau nach Konzept.
- **Schwächen:** PART 16 (Milo allein, Flüster-Monolog) ist als Audio-Szene wackelig — sechs fast identische Whisper-Zeilen hintereinander; PART 4 und 5 sind zwei fast gleiche Safe-Room-Szenen direkt hintereinander (Konzept wollte assoziativen Ansatz vs. Zeichnungs-Variation, die Skripte doppeln den Aufbau).
- **Fehler (korrigierbar):**
  - PART 7: „Three weeks. Nobody unplugged it." — Ep2 spielt am Morgen nach Tag 1 (Ep1: Ankunft am Verschwinde-Abend, Renderjob über Nacht). „Drei Wochen" ist unmöglich und widerspricht Ep3 („eleven days") und Ep5 („two weeks").
  - PART 11: Wei verortet 14 Birch Lane „near the northeast corner" — Ep3 PART 14/15 legt dieselbe Adresse „beside the Last House" (Westrand, Ep1 PART 5: „Last house, west edge").

## Episode 3: Frequencies

- **Stärken:** Beste Episode der Staffel. Signal-Erklärung als Streit (PART 2: „It doesn't control anyone. It opens a door."); Wei Zhous Foto-Fund (PART 6, speed-Wechsel) und die anschließende Lüge (PART 7 „compression artifact") sind erstklassiges Slice-Schauspiel; Old Chens Einführung (PART 8/9, „Coincidence looks suspicious right up until it's just what happened") trifft die Erzähler-Kadenz aus dem Voice-Profil perfekt; PART 17 Bearing-Cliffhanger sauber.
- **Schwächen:** PART 10 (Chen allein am Radio) und PART 16 bewusst kurz geplant, aber PART 6 (174 W.) ist unter Budget, weil der Foto-Beat allein die Szene nicht füllt.
- **Fehler (korrigierbar):**
  - PART 4: „It's cold. Eleven days cold." — dritter, wieder anderer Zeitwert (Ep2: 3 Wochen, real: ~Tag 2–3).
  - PART 6: „Five of them. Both kids" vs. Ep1 „Two adults, two children" (=4).
  - PART 14: „Fourteen Birch Lane. Northeast corner" und zwei Absätze später „the Zhao property, the house beside the one the team calls the Last House" — beide Verortungen widersprechen sich innerhalb desselben Parts.

## Episode 4: What the Ridge Remembers

- **Stärken:** Jonahs Telefonate mit den Vorgesetzten (PART 1/4) als Ein-Seiten-Dialog funktionieren überraschend gut im Audio; Chens „vent stack"-Selbstverfluchung (PART 6) ist ein starkes Kammerspiel; Yunas belauschbarer Handler-Call (PART 11) mit „Containment. That's all this is." als bröckelnde Selbstrechtfertigung; PART 14 (Chen zeichnet die Karte) emotionaler Höhepunkt.
- **Schwächen:** PART 16 und 17 überlappen chronologisch: In PART 16 bricht das Team bereits die Maintenance-Road hinauf auf, PART 17 spult zurück zu „before dawn… loading gear" — beim Hören wirkt es wie eine Wiederholung derselben Aufbruchsszene.
- **Fehler (korrigierbar):**
  - PART 5 vs. PART 6: Chen sagt im Dialog „Number two exhaust plenum", erinnert sich in PART 6 aber wörtlich an „Vent stack. I said 'vent stack.'" — das verratende Wort wechselt innerhalb der Episode.
  - PART 9: NARRATOR: „The Last House, once home to Wei Zhou's cousin's family" — falsch: Das Last House ist Milos Fundort; die Cousinen-Familie wohnt nebenan (Ep3 PART 14/15).
  - PART 14: „Nineteen years I told myself waiting cost nothing" — widerspricht PART 6 derselben Episode („eleven years") und Ep6 („eleven years of silence"). (Quelle: der Konzept-Kanon wechselt hier gerade von Mara/19 auf Iris/11.)
  - SFX PART 10/17: „a few keys tapped, then stillness" / „radio crackling once, then silence" — hörbares Kern-Event vorhanden, nur der Stille-Schwanz ist nicht renderbar (siehe Serienmuster).

## Episode 5: Beneath the Checkpoint

- **Stärken:** Checkpoint-Einbruch als langer Spannungsbogen über 6 Parts mit sauberer Eskalation Meridian-Sentry-Name → Manifest → Yuna beim Einstecken erwischt (PART 9–12); Jonahs Korridor-Konfrontation (PART 12, „You've never panicked once this whole investigation… Not until this.") ist der beste Dialog der Staffel; Wei Zhous stiller Serial-Match (PART 13) hält den Slice.
- **Schwächen:** PART 1–5 re-inszenieren eine Aufbruchs-Entscheidung, die Ep4 PART 16 schon getroffen und begonnen hatte („we move at first light" → Team läuft los) — die Episodennaht wirkt wie ein Reset; Chen bietet in PART 5 „seine" Ostgrat-Service-Road an, als wäre die Karten-Übergabe aus Ep4 nie passiert.
- **Fehler (korrigierbar):**
  - PART 13: „Zhang residence… I logged that serial myself. Off the record. Three weeks ago." — (a) Namenswechsel Zhao→Zhang ohne jede Überleitung, (b) „three weeks ago" unmöglich (Wei fand die Adresse in Ep1-Nacht; Handlung ist bei ~Tag 4–5).
  - PART 16: DR_MEI_LIN spricht am Ridge-Hatch („You went very still just now. Same as when you saw the drone map") — sie war weder bei der Drohnenkarte noch im Feldteam; **vom eigenen REVIEW geflaggt und nicht behoben.** Ep4 PART 16 hatte zudem etabliert, dass sie bei Milo bleibt, und PART 6 derselben Nacht zeigt sie im Safe Room.
  - SFX PART 10/12: „a beat of silence, then …" — führende Stille nicht renderbar; Events dahinter (papers set down / boot scuffing) sind ok.

## Episode 6: Rows of Empty Chambers

- **Stärken:** Bunker-Abstieg mit gutem Raumgefühl (PART 1/2); Chens Nummernsystem-Enthüllung über Funk (PART 11, „Didn't think anyone would still be reading my handwriting.") ist ein Serien-Highlight; Iris-Chen-Tür (PART 13) und Geständnis (PART 14) emotional präzise; Doppel-Geständnis-Struktur (Wei PART 9, Chen PART 14) + Rotlicht-Cliffhanger exakt nach Konzept.
- **Schwächen:** Milo spricht in PART 10 zum ersten Mal überhaupt („Doors." / „All of them.") — und niemand, auch Mei Lin nicht, registriert, dass der seit Wochen stumme Junge gerade gesprochen hat. Der größte verpasste Beat der Staffel; ab hier plaudert Milo in Ep7/8 wie selbstverständlich.
- **Fehler (korrigierbar):**
  - PART 7: Zufalls-Bewohnerin heißt „Doyle, Grace" — kollidiert vorausschauend mit Ep8, wo Chens Enkelin plötzlich „Grace" heißt (in Ep6 heißt sie Iris). Zwei Graces, eine davon die falsche.
  - PART 8: Zhang-Kammer bei „Chamber forty-one. Chamber forty-two." — Ep7/8 sagen durchgehend „Chamber nineteen".
  - PART 13/14: „Iris Chen", „Eleven years" — vs. Ep4 („nineteen years") und Ep8 („Grace… Twenty-two years back").
  - SFX PART 5/13: 2× „a single footstep, then silence" — Halbcue (siehe Muster).

## Episode 7: Sealed In

- **Stärken:** Lockdown-Kaltstart (PART 1) mit hartem SFX-Schnitt; Yunas Entlarvung über das eingenähte Zweitgerät (PART 9) und das erpresste „Continuity Trial"-Geständnis (PART 13: „It was never supposed to stay just this village.") sitzen dramaturgisch; Chens Solo-Aufbruch (PART 12, Schlüssel aus der Kaffeedose, „Read it after, not before") rührend konkret.
- **Schwächen:** PART 8 und PART 11 sind reine NARRATOR-Blöcke (Field-Ops-Abwägung, Konvoi) — verständlicher Workaround für Szenen ohne gecastete Sprecher, aber im soap_opera-Format zwei dialogfreie Fremdkörper, die zusammen ~600 Wörter Erzähltext am Stück bedeuten.
- **Fehler (korrigierbar):**
  - PART 4: „Two adults. Left side. And the girl between them. That's my aunt. My uncle. That's Lian." — Lian ist hier ein Mädchen zwischen Onkel/Tante. In Ep4 PART 9 war Lian die Mutter (Frauenstimme im Voice-Memo: „the kids won't stop looking at the speaker"), laut Ep5/6-Kanon die Cousine mit Ehenamen Zhang.
  - PART 6: „the trailer he's called home for thirty years" + „Held that seam shut twenty years" — vs. Ep3 PART 9 („Eleven years, the county says") und Ep6 („eleven years").
  - PART 4/13: Kammer „nineteen" — vs. Ep6 PART 8 (Zhang bei Kammer ~42).
  - SFX PART 1/13/15: „…, then dead silence" / „exhale caught by nothing, then silence" / „fan motor winding down to silence" — der Fan-Cue ist sogar komplett hörbar (False Positive des Checkers); die anderen zwei brauchen nur den Stille-Schwanz gestrichen.

## Episode 8: The Last Frame

- **Stärken:** Shaft-Funk-Anleitung (PART 2) mit Störgeräusch-Dramaturgie; Wei an Kammer 19 (PART 4, „I'm not leaving them in a box a second time") als moralischer Höhepunkt; Broadcast-Countdown (PART 9/12) und Halcyon-Lobby-Panik (PART 10) geben echtes Finale-Tempo; Schluss-Doppel (PART 16 Frame-Fund im Dialog, PART 17 NARRATOR-Zoom auf Milos Kamerablick) ist ein exzellenter Serien-Ausstieg.
- **Schwächen:** PART 11/12 sehr kurz (78/66 W., beide unter selbst dem reduzierten Budget) — Yunas Nicht-Anruf hätte mehr Raum verdient; PART 15 (Mei Lin + Milo vor dem Broadcast) lässt Milos inzwischen flüssiges Sprechen erneut unkommentiert.
- **Fehler (korrigierbar):**
  - PART 1 vs. PART 13: Chen steigt in PART 1 in den Schacht ein („lowers himself through the hatch, into the dark"), das Team klettert in PART 6 denselben Schacht hoch, ohne ihm zu begegnen, der Hatch ist offen, Chen weg — und in PART 13 ist er kommentarlos zurück im Field-Ops-Zelt. Bewegungslogik fehlt.
  - PART 13 vs. PART 14: PART 13 zeigt Jonah und Wei im Field-Ops-Zelt beim Broadcast; PART 14 („minutes later") lässt Jonah, Wei **und Yuna** gemeinsam aus der Baumgrenze am Checkpoint treten, wo Yuna verhaftet wird. Wo Yuna während PART 13 war und warum Jonah/Wei wieder am Zaun sind, ist unauflösbar (Konzept-Reihenfolge 13→14 wurde übernommen, ohne die Ortslogik zu reparieren).
  - PART 1/13: „Grace… Twenty-two years back" — vs. Ep6 „Iris… eleven years". Zusätzlich P4/P5: „he's right there" / „I looked him in the face" — Lian ist jetzt männlich (Ep4: Frau, Ep7: Mädchen).
  - SFX PART 2/9: „static swallowing the voice, one sharp crackle" (Misch-Anweisung, aber Crackle hörbar) / „van door hinge creaking as it's held ajar" (voll hörbar — False Positive).

---

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)

1. **Chens Enkelin:** Iris (Ep6, vermisst 11 Jahre) → Grace (Ep8, vermisst 22 Jahre); Ep4 nennt zusätzlich „nineteen years" Warten. Quelle: episodes.json-Kanon wechselt Mara(19)→Iris(11)→Grace(22) zwischen den Episoden-Blöcken.
2. **Wei Zhous Familie:** Zhao, 14 Birch Lane, 4 Personen (Ep1) → Zhao, 5 Personen (Ep3) → Zhang/Lian (Ep5+); Lian = Mutter (Ep4) → Mädchen (Ep7) → „he/him" (Ep8).
3. **Zeitachse:** Dampfendes Essen ~1 h nach Verschwinden (Ep1) → „three weeks" (Ep2, Tag 2!) → „eleven days" (Ep3) → „two weeks" (Ep5) → „three weeks ago" für Ep1-Ereignis (Ep5). Kein Wert passt zum anderen.
4. **Chens Zahlen:** Cabin 11 Jahre (Ep3) vs. „trailer… thirty years" (Ep7); Bau 1988 (Ep6) vs. „thirty years ago" (Ep4) vs. „forty years" (Ep7/8); Schacht versiegelt „twenty years" (Ep7) vs. „forty years" (Ep8 P1).
5. **Zhang-Kammer:** Nr. ~42 (Ep6 P8) vs. Nr. 19 (Ep7/8).
6. **Verräter-Wort:** „exhaust plenum" (Ep4 P5) → erinnert als „vent stack" (Ep4 P6) → zitiert als „egress corridor" (Ep5 P2).
7. **Ortslogik Cousinen-Haus:** 14 Birch Lane „northeast corner" (Ep2/3) vs. „beside the Last House" am Westrand (Ep3) vs. „The Last House, once home to Wei Zhou's cousin's family" (Ep4 P9).
8. **Episodennaht Ep4→Ep5:** Ep4 endet mit begonnenem Aufbruch über die Maintenance-Road samt Chen-Karte; Ep5 beginnt mit der noch nicht getroffenen Entscheidung, zum Checkpoint zu gehen, und Chen bietet die Route „neu" an.
9. **Ep8 Schlussgeographie:** Chen im Schacht (P1) → Field Ops (P13); Jonah/Wei Field Ops (P13) → mit Yuna aus der Baumgrenze (P14).
10. **Mei Lins Ortswechsel Ep5:** Safe Room (P6) und Ridge-Hatch (P16) in derselben Nacht — vom Review geflaggt, nicht gefixt.
11. **Milos Mutismus:** endet in Ep6 P10 unbemerkt; ab da spricht er normal, ohne dass eine Figur die zentrale Anomalie der Serie (der stumme Zeuge spricht!) je thematisiert.
12. **Yunas Motiv:** Mutter-Schulden konkret etabliert (Ep1 P12), ab Ep5-Kanon (Jobangebot/Einwanderung) nie wieder aufgegriffen — kein Widerspruch im Skript, aber ein fallengelassener Faden.

### Wiederholte Phrasen / LLM-Tics (Zählung über 8 Episoden)

- Style-Direktive „to himself/herself": **105×** (davon „muttering to himself" 11×) — fast jede Solo-Szene öffnet identisch.
- „barely audible": **41×** — auf Dauer eine TTS-Falle (durchgehend geflüsterte Passagen).
- „Not yet": **37×** als Zeilen-Schluss/Selbstermahnung — der auffälligste Dialog-Tic, bei vier verschiedenen Figuren identisch.
- „unreadable": 19×, „mask/mask back on": 14×, „practiced": 10×, „rehearsed": 9×, „a beat too (quick/fast/long)": 9× — dasselbe Misstrauens-Vokabular für Yuna UND Wei UND Chen.
- „Okay. Okay." 9×, „Come on. Come on" 4×, „Sure." als ganze Jonah-Zeile 5×.
- SFX-Tic: **„…, then silence/stillness"** als Cue-Schwanz (12 det-Findings + weitere unauffällige) — dramaturgisch gemeint, technisch halb-unrenderbar.
- Struktur-Tic: Szenen enden ~30× mit NARRATOR-Schlusssatz des Musters „He doesn't say X — not yet." (Erkenntnis benannt + vertagt).

### Thread-Bilanz

- **Signal/Halcyon (Haupt):** ~45 % der Sections, sauber eskaliert (Watermark→Waveform→Bearing→Checkpoint→Bunker→Broadcast). Gut dosiert.
- **Yuna:** ~22 %, in jeder Episode präsent, langsamste und beste Eskalation (Deflection→Beobachtung→Manifest→Zweitphone→Geständnis→Verhaftung).
- **Wei Zhou/Familie:** ~18 %, konstant; kleine Redundanz (dreimal „Jonah fragt, Wei weicht aus": Ep3 P7/P16, Ep4 P8).
- **Old Chen:** 0 % in Ep1–2 (per Konzept erst ab Ep3), danach ~15 % und ab Ep4 tragend — funktioniert, aber sein Zahlen-Kanon zerbröselt (s. o.).
- **Milo/Mei Lin:** 1–2 Sections pro Episode; Mei Lin verhungert ab Ep5 als Figur (nur noch Milo-Begleitung, kein eigener Erkenntnisfortschritt; das Implantat-Faktum aus dem Ep7-Kanon kommt in keinem Skript vor).

### REVIEW-Abgleich

7 von 8 Reviews: „Keine Auffälligkeiten." — trotz der oben gelisteten, teils gravierenden Fehler. Einziger Fund (ep5_REVIEW: Mei-Lin-Zeile in P16 falscher Sprecher/Ort) ist **korrekt und im Skript unverändert enthalten**. Fazit: Das Episoden-Review prüft offenbar nur intra-episodisch und oberflächlich; Cross-Episode-Fakten (Namen, Zahlen, Orte) prüft niemand — genau dort liegt die Hauptschwäche der Serie.

### Einordnung der 12 SFX-Befunde (Orchestrator-Frage)

Der Ausreißer ist harmloser, als die Zahl suggeriert: 10 der 12 Cues enthalten ein voll hörbares Kern-Event und scheitern nur am angehängten Stille-/Zustands-Schwanz („…, then silence", „a beat of silence, then …", „as it's held ajar"). 2–3 sind False Positives des Checkers („a fan motor winding down to silence" und „a van door hinge creaking…" sind komplett renderbar). Es ist ein einziger stilistischer Tic dieses Skript-Laufs (Stille als dramatischer Beat im Cue-Text), kein Sounddesign-Problem — Fix: Stille-Schwänze aus den Cue-Texten strippen (Regex-fähig), Rest unverändert lassen.

---

## Top-5 konkrete Korrekturen (priorisiert)

1. **Chens Enkelin vereinheitlichen (Ep6↔Ep8):** In Ep8 P1 „Grace." → „Iris.", P13 „My granddaughter. Grace. Twenty-two years back" → „Iris. Eleven years back"; in Ep6 P7 die Zufalls-Bewohnerin „Doyle, Grace" umbenennen (z. B. „Doyle, Anna"), damit keine zweite Grace existiert. Zusätzlich Ep4 P14 „Nineteen years" → „Eleven years". *(Hand-Edit, 4 Stellen; Wurzel-Fix: case-Blöcke in episodes.json über Episoden hinweg einfrieren statt neu generieren.)*
2. **Lian konsistent machen:** Entscheiden: Lian = erwachsene Cousine/Mutter (Ep4-Version, deckt sich mit Kanon). Dann Ep7 P4 „the girl between them" → „the woman between them… That's Lian" und Ep8 P4/P5 „he's right there" / „I looked him in the face" → „she/her". Plus Ep1 P13 „Two adults, two children" → „Two adults, three children" oder Ep3 P6 „Five of them" angleichen; Zhao→Zhang einmalig im Dialog erklären (eine Zeile Wei: „Zhao was her maiden name").
3. **Zeitachse glätten:** Ep2 P7 „Three weeks" → „Two days"; Ep3 P4 „Eleven days cold" → „Three days cold"; Ep5 P13 „Three weeks ago" → „That first night"; Ep1 P2 „an hour after nobody's touched it" → Dampf streichen („gone cold on the table"). Vier kleine Edits machen die Serie zeitlich hörbar konsistent.
4. **Ep8-Finale-Geographie reparieren:** P13 auf Funk umstellen (Jonah/Wei hören den Broadcast am Checkpoint-Rand, Chen spricht über den Field-Ops-Kanal) ODER P14 vor P13 ziehen und P13-Intro zu „after the agents took Yuna" ändern; zusätzlich in P6 eine Chen-Erklärzeile, warum er nicht im Schacht wartet („I went back topside to draw the patrol off").
5. **SFX-Stille-Schwänze strippen + Review härten:** Alle „…, then silence/stillness"-Cue-Schwänze automatisch kürzen (rein mechanisch, ~12 Stellen); die vom ep5-Review geflaggte Mei-Lin-Zeile in P16 endlich auf Wei Zhou umschreiben; und dem Episoden-Review einen Cross-Episode-Faktencheck (Namen, Zahlen, Orte aus Vorgänger-Skripten) mitgeben — diese Serie beweist, dass genau diese Prüfebene fehlt.
