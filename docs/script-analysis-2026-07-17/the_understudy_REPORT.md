# the_understudy — Tiefenanalyse

## Serien-Überblick

**Prämisse:** Detective Elias Vance wird von einem Serienmörder (Simon Boru, antiquarischer Buchhändler) über kryptische Postkarten in ein privates Spiel gezogen. Borus eigentliches "Masterwork": Elias Schritt für Schritt zu genau der Sorte Detective umzubauen, die einst Borus Bruder zerstörte — bis Elias ihn am Ende selbst, ohne Zeugen, tötet. Threads: **The Puppeteer's Game** (Killer-Spiel), **The Vance Marriage** (Mira liest Elias' Geheimnisse als Affäre), **The Frame** (der unschuldige Lebensmittelhändler Han Mei), **Institutional Doubt / The Captain's Doubt** (Lin und Zhou beobachten Elias' Regelbrüche, jeder für sich).

**Gesamturteil: 5/10.** Auf Szenenebene ist das die handwerklich stärkste Serie im Vergleichsfeld: Dialog trägt Subtext statt Exposition, Figuren klingen unterscheidbar, die Dramaturgie der Selbstrechtfertigung ("It's not a lie if it's just… incomplete") ist konsequent und thematisch dicht. Aber auf Makro-Ebene bricht die Serie zusammen: **Das Staffelfinale passiert zweimal mit entgegengesetztem Ausgang** (Ep9: Boru verhaftet, kein Schuss — Ep10: Boru frei, wird erschossen), Borus Motiv wird im Laufe der Staffel dreimal umgeschrieben (Sohn Daniel → diskreditierter Kriminologe → Bruder Aldous), Hans Ehefrau trägt vier verschiedene Namen, seine Tochter ist 9, 12 und 14 Jahre alt, und Captain Zhou wechselt zwischen Ep1–4 mehrfach das Geschlecht — bei männlicher TTS-Stimme (Eric). Wurzelursache ist bereits die episodes.json: create_series hat die `solution`-Texte pro Episode neu generiert statt kanonisch festzuschreiben, und der Skript-Writer hat die Drift ungefiltert übernommen und verstärkt.

## Episode 1: The First Postcard

- **Stärken:** Starker Cold Open (Postkarte "placed, not dropped"); Elias' erster Vertrauensbruch (Name auf der Karte verschweigen) entsteht organisch in P3; Boru-Einführung in P7/P8 exzellent ("A dropped card wouldn't send a detective hunting down its footnotes" — er verrät sich fast, und die Szene faltet es glaubwürdig weg); Mira-Szenen zeigen statt erklären (P4 "Three mornings.").
- **Schwächen:** P15 (Borus Ritual mit Daniels Foto) legt Täter, Methode UND Motiv in Ep1 offen — nimmt der Staffel jede Wer-war's-Spannung; die Drama-Ironie-Entscheidung wäre vertretbar, widerspricht aber der Case-Regel und wurde vom Review geflaggt.
- **Fehler (korrigierbar):**
  - PART 2: Zhou als Frau eingeführt ("worked her way up … trained Elias herself"), aber voices.json beschreibt Zhou männlich ("his protégé") und castet die Männerstimme **Eric** → hörbarer Widerspruch Stimme vs. Erzähltext.
  - PART 6 vs. 7 vs. 17: Der Vers der EINEN Postkarte wird dreimal verschieden zitiert: "Where the tide forgets its name" (P6), "The garden keeps what the gardener buries. That's the whole thing." (P7), "The water remembers what the shore forgets" (P17) — obwohl objective_fact "a single line of verse" festlegt.
  - PART 9: Han Mei mit weiblichen Style-Tags ("half to herself", "quiet, almost to herself"), ab Ep3 durchgehend männlich (Frau, Tochter).
  - PART 15: Spoiler-Leak (siehe REVIEW) unbehoben.

## Episode 2: Reading Between the Lines

- **Stärken:** Lins Misstrauen wächst in glaubwürdigen Mikro-Schritten (P10 Timeline-Diskrepanz, "He trained me to double-check everything… Guess that cuts both ways now"); P16 "Buch fällt an der richtigen Stelle auf" ist ein schönes unheimliches Bild, das das Outro-Note exakt trifft.
- **Schwächen:** Der Noten-Fund (P8) nimmt den Concept-Beat von Ep5 vorweg — Beginn der "Mira findet die Notiz zum ersten Mal"-Endlosschleife (Ep2, Ep3, Ep5).
- **Fehler (korrigierbar):**
  - PART 1: Recap sagt, Elias knackte die Referenz "alone at his kitchen table" — in Ep1 P17 war es der Precinct-Schreibtisch.
  - PART 1/P6: Wieder zwei NEUE Verszeilen ("Where the ferryman's coin buys no passage home"; "The tide keeps what the city forgets…") — der Postkartentext stabilisiert sich nie.
  - PART 12/13: Zeitachse bricht: Elias besucht das Tableau "past midnight" (Folgenacht), aber Zhou konfrontiert ihn mit Fundzeit 06:40 und seinem Anruf 08:15 desselben Morgens — die gezeigte Mitternachtsszene passt in keine der beiden Versionen.

## Episode 3: A Little Circumstantial

- **Stärken:** Han-Mei-Alltag (P3) mit warmen Details (Mrs. Okafor, Pfirsiche) macht die spätere Zerstörung wirksam; die verschlossene Schublade ("Still here.") pflanzt sein Geheimnis sauber; P8-Diner-Streit Elias/Lin ist der beste Argument-Dialog der Staffel ("You decided he's right before the evidence caught up").
- **Schwächen:** P15 (Borus Box-Ritual) wiederholt Ep1-P15 nahezu strukturell identisch; erneut vom Review geflaggter Frame-Spoiler.
- **Fehler (korrigierbar):**
  - PART 2: Genderkollision in EINEM Satz: "Captain Zhou — … **the man** who trained Elias **himself** years ago — calls … into **her** office."
  - PART 1 vs. 2 vs. 4: Falldauer widerspricht sich: "three days after the body was found" (P1) vs. "more than this case has produced in **three weeks**" (P2) vs. "**Six weeks** of a case" (P4).
  - PART 6 vs. 11: Mira legt die Notiz in P6 zurück in die Manteltasche, sitzt in P11 wieder mit ihr am Tisch und versteckt sie in einer Box — und der Text der Notiz hat sich geändert: "The second key isn't where you think" statt "Third shelf, second from the left. It's waiting for you" (Ep2 P8).
  - PART 15: Spoiler-Monolog (REVIEW-Fund) unbehoben.

## Episode 4: Rules Are for Other Cases

- **Stärken:** Zhous "Provisional"-Litanei und ihr/sein leises Nachgeben zeichnen die institutionelle Erosion stark; P10 Lin zählt Verstöße ("It's four. I checked the mileage log before I checked myself"); P17-Cliffhanger (Postkarte kennt das Warrant-Formular und die Uhrzeit) ist exzellent.
- **Schwächen:** "Twine/packaging" taucht als etabliertes Beweisstück auf, wurde aber on-screen nie eingeführt (Concept-Drift ep3→ep4: Matchbook/Receipt → Packaging/Twine).
- **Fehler (korrigierbar):**
  - Zhou-Gender-Chaos auf dem Höhepunkt: P1 "to **himself**… **He** says the word again", P3/P9/P14 "**her** office / **she** opens the folder", P11 "**his** office door… to **himself**".
  - PART 12 vs. 13: P12 "This one's ten days later" (zweite Leiche), P13 "**Eleven days** between the first two. **Six** between the second and this" — impliziert eine dritte Leiche, die es nicht gibt; P14 bestätigt "Two bodies now… in eleven days".
  - PART 17: nicht-hörbarer SFX-Cue (det. Befund) — "three tones of a phone number half-dialed" beschreibt eine abgebrochene Handlung, kein klares Geräusch-Event.
  - Vier Unterlängen-Parts (det. Befund P2/P4/P10/P11): jeweils Solo-Grübelszenen, deren Beat-Substanz für 250+ Wörter zu dünn geplant war.

## Episode 5: What Mira Found

- **Stärken:** P2 Mira-als-Therapeutin-Monolog ist die beste Mira-Szene der Staffel ("I give that advice for a living"); P12/13-Konfrontation mit der Notiz hat echte Spannung; P17 "Three car lengths" löst das Concept-Outro präzise ein.
- **Schwächen:** P6 führt einen namenlosen nächtlichen Besucher bei Boru ein ("You always want it faster than it can go") — ein Komplize/Klient, der in keinem Case-Datensatz existiert und nie wieder auftaucht: toter Plotfaden im Finale.
- **Fehler (korrigierbar):**
  - PART 1: Der Noten-Fund wird als Erstes-Mal inszeniert ("the first secret she's ever kept from him in **nine years of marriage**") — Ep2/Ep3 hatten den Fund bereits zweimal; zudem NEUER Notiztext ("The second shelf remembers what the first one forgot… Twelve Aldermoor"), in P2 ein VIERTER ("Second Tuesday. Same as before").
  - PART 8: Han-Zeilen enthalten Erzählprosa in Anführungszeichen, die die TTS als Han sprechen wird: `"Notice of expanded financial disclosure…" He set it down like it might bite him twice.` — Er-Erzählung im eigenen Mund; Part müsste auf NARRATOR/HAN aufgeteilt werden.
  - PART 15: "**Twenty-two years** I've had that door open" vs. Ep4 P15 "worked for **eleven years**" vs. Ep6 "twelve years".
  - Ehedauer "nine years" (P1) kollidiert mit Ep8 P13 "Twelve years".

## Episode 6: The Almost-Confession

- **Stärken:** P3 Boru kalibriert die Risiko-Nähe des Clues ("Too near, and it reads as planted. Too far, and he settles for Han") — bestes Killer-Writing der Staffel; P13/14 Lin im Buchladen, Boru neutralisiert sie mit Hilfsbereitschaft ("I'd rather be useful than mysterious"): großartige Doppelbödigkeit; P4/P5 "keeper miscounts his flock"-Lesartenstreit ist klug gebaut.
- **Schwächen:** Zhous Entscheidungsbogen ist in sich verdreht (s. Fehler); Han-Familienszenen wiederholen zum vierten Mal das Graffiti-Schrubben.
- **Fehler (korrigierbar):**
  - PART 11 vs. 15 vs. 17: Zhou **unterschreibt** den Arrest in P11 ("Tell them the order's signed — it's moving"), verlangt in P15 erst die Entwurfsfassung ("Get me the arrest paperwork drafted"), autorisiert in P17 erneut ("Authorized. Bring him in tonight") — dreifache Unterzeichnung derselben Anordnung.
  - PART 10 & 16 vs. section_locations: Concept-Section 10 = "The Rift at Ruby's" (DINER), Skript P10 = Zhou-Büro; Section 16 = "Alone With the Folded Page" (PRECINCT), Skript P16 = Vance-Küche → SFX-Plan legt Diner- bzw. Precinct-Ambience unter falsche Szenen.
  - PART 9: Tochter "She's **twelve**" (vs. Ep5 "nine-year-old", Ep7 "fourteen"); "**twelve years** on this street" (vs. 11/22 anderswo).
  - PART 1: "six weeks in" setzt die widersprüchliche Zeitachse fort.

## Episode 7: The Night They Took Han

- **Stärken:** Beste Episode der Staffel. Raid-Kaltstart, P4-Ziegel-durch-Scheibe komplett narratorisch erzählt (starke Form); P6 Borus Editor-Metapher ("He hasn't noticed yet whose hand is actually on the pen"); P17-Fünf-Räume-Montage als Midpoint-Schlussbild ist genau das richtige Soap-Finale.
- **Schwächen:** P2 "Second shelf, behind the rice sacks. That's where the file says to look" — woher weiß die Akte das Versteck? Der (offenbar von Boru lancierte) Hinweis wird nie erklärt oder hinterfragt; P11-Telefon-SFX (det. Befund) nicht sauber hörbar formuliert.
- **Fehler (korrigierbar):**
  - PART 3: Tochter "She's **fourteen**" — dritte Altersangabe in drei Episoden.
  - PART 4: Hans Frau heißt "**Yuan**" — in Ep3 P10 hieß sie "**Mei-Ling**".
  - PART 5: Elias sagt "Mr. **Mei**" (falsche Namensreihenfolge; Han ist der Familienname, dieselbe Episode nutzt korrekt "Mr. Han").
  - PART 12: "Months of work" — Zeitachse erneut inkonsistent zu "three days/three weeks/six weeks".

## Episode 8: Whose Hands Are Clean

- **Stärken:** P10 Lin legt Zhou den Log vor ("I need you to have actually read it") — der Payoff von sechs Episoden Zögern sitzt; P14 Borus Foto-Monolog gibt dem Motiv echte Trauertiefe; P13 Mira beim Kollegen ("I used to think that was steadiness. Now I think it's practice") ist herausragend.
- **Schwächen:** Boru-Motiv hier "Mentor diskreditierte mich vor **dreißig** Jahren" — kollidiert sowohl mit Daniel (Ep1/3) als auch mit Aldous/40 Jahre (Ep9/10).
- **Fehler (korrigierbar):**
  - Chain-of-Custody-Lücke in EINER Episode dreifach beziffert: "almost **four hours**" (Ep7 P10 & Ep8 P3) → "**Eleven minutes**, unaccounted for" (P4) → "logged **three hours** after the officers cleared the scene" (P11).
  - PART 7 vs. 15: "Six of them now" (Postkarten) vs. "a **fourth** envelope" acht Parts später.
  - PART 7: Boru begrüßt Elias mit "Twice in one month. I should start charging a consulting fee" — wortgleiches Begrüßungs-Template wie Ep4 P5 ("…keeping your tea ready"), zudem absurd nach 4+ Besuchen in drei Wochen (Ep4 P10).
  - Ehedauer: P13 "Twelve years" vs. Ep5 "nine years of marriage".

## Episode 9: The Last Clue

- **Stärken:** P6/P7 Elias' Nichts-mehr-zu-verlieren-Logik ("Rules only work if you've still got something to lose") ist die beste Elias-Charakterarbeit; P15 Borus Krebs-Enthüllung mit Pillendose als Requisit; P16 "Why me, specifically" bricht Borus Performance glaubwürdig auf.
- **Schwächen:** P1 erfindet beiläufig eine "funeral for his uncle Thursday", die nie wieder vorkommt; P3: Zhou verortet die Uhr "in his **register drawer**" statt im Storeroom hinter den Reissäcken (Ep7).
- **Fehler (korrigierbar):**
  - **PART 17 zerstört das Staffelfinale:** Lin und Backup stürmen den Laden, Boru wird gefesselt ("handcuffs ratcheting shut"), kein Schuss fällt, Narrator: "Simon Boru's masterwork ends here, denied its final hand." Das Concept verlangt als Ep9-Outro einen Cliffhanger (Elias allein, die Antwort "not the one he came for"), und Ep10 setzt zwingend voraus, dass Boru frei ist und von Elias erschossen wird. Der angefügte "Next time"-Teaser verspricht sogar wörtlich die Szene, die P17 gerade gegenteilig aufgelöst hat.
  - PART 4: Hans Frau heißt jetzt "**Su**" (dritter Name).
  - PART 15: "I never touched a single one of them" widerspricht Ep10-Solution ("personally committed every murder") und Ep10 P4, wo Boru die Leichen als sein Werk einräumt.
  - PART 10: Narrator-Artefakt "how far **Lin Partner's** own suspicions…" (Rollenname als Nachname behandelt).
  - PART 10/16: Verrat "**forty years** on/ago" vs. Ep8 "Thirty years".

## Episode 10: The Masterwork

- **Stärken:** P3–P5 Docks-Konfrontation ist das dramatische Highlight der Staffel ("Certainty is faster. Juries like fast."; "I'm not explaining a crime to you, Elias. I'm asking you to finish one."); P5-Schuss im Handgemenge hält die Schuldfrage produktiv offen; P16 Zhou/Elias im Diner ("I filed it as written. God help me…") und der offene Schluss aller Threads treffen das series_outro exakt.
- **Schwächen:** Die Episode muss Ep9s Arrest ignorieren und tut es stillschweigend — P1 biegt Boru in einen Mann um, der während einer laufenden Durchsuchung durch die Hintertür entkommt.
- **Fehler (korrigierbar):**
  - PART 1 vs. Ep9 P17: unvereinbare Ausgangslage (Boru verhaftet vs. Boru flieht) — die Klimax existiert doppelt.
  - PART 8 vs. 9: P8 rechnet die Lücke im Bericht auf "**three hours**", P9 sagt wörtlich "That's **twenty minutes** unaccounted for" über dieselben Zeitstempel.
  - PART 11: "**Forty years** he ran that shop **three doors down**. Kind to my daughter at the counter every Sunday" — Boru wird rückwirkend zu Hans Nachbarn erklärt (der Laden lag bisher "across town" bzw. an den Docks) und Han weiß plötzlich, wer ihn gerahmt hat, obwohl laut Case niemand es ihm öffentlich gesagt hat.
  - PART 12: erneut "Mr. Mei".
  - PART 10 vs. 17: Lin reißt den Umschlag auf und behält ihn ("She doesn't put it back, either"), P17: der Brief "sits where it was found".
  - PART 10-Header "The morning after the docks" liegt chronologisch VOR P8 ("Two days later") und P9 — Part-Reihenfolge widerspricht der internen Zeit.

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)
1. **Doppelte Klimax:** Ep9 P17 (Boru verhaftet, kein Schuss) vs. Ep10 (Boru frei, erschossen). Schwerster Fehler der Serie.
2. **Borus Motiv dreifach:** Sohn Daniel, gestorben vor 9 Jahren (Ep1 P15, Ep3 P15) → als Forscher vom Mentor diskreditiert, vor 30 Jahren (Ep8 P14) → Bruder Aldous, vor 40 Jahren zu Unrecht verurteilt, nach 19 Jahren in der Zelle gestorben (Ep10 P3). Daniel verschwindet ab Ep4 spurlos. (Wurzel: episodes.json schreibt die solution pro Episode um.)
3. **Hans Ehefrau: vier Namen** — Mei-Ling (Ep3), Yuan (Ep7), Su (Ep9), Jia (Ep10).
4. **Hans Tochter: drei Alter** — 9 (Ep5), 12 (Ep6), 14 (Ep7).
5. **Zhou-Geschlecht:** weiblich (Ep1–2), gemischt bis in Einzelsätze (Ep3 P2, Ep4), männlich (Ep5–10) — bei männlicher Stimme Eric.
6. **Chain-of-Custody-Lücke:** 4 h → 11 min → 3 h (Ep7/Ep8) und 3 h → 20 min (Ep10 P8/P9).
7. **Postkarten-/Notiztexte fluktuieren:** 5+ Versvarianten (Ep1–2), 4 Notizvarianten (Ep2/3/5); Postkartenzahl "six" vs. "fourth envelope" (Ep8).
8. **Zeitachse:** 3 Tage → 3 Wochen → 6 Wochen → "months" → März-Daten → Oktober-Log; Leichenzahl springt (Ep4 P13 impliziert 3, P14 sagt 2; Ep9 "four people").
9. **Laden-/Ehe-Jahreszahlen:** Han: 11/12/22 Jahre; Ehe Vance: 9/12 Jahre; Verrat an Boru: 30/40 Jahre.
10. **Uhr-Fundort:** Storeroom hinter Reissäcken (Ep7) vs. Registerschublade (Ep9 P3).
11. **Boru-Laden-Geografie:** "part of town she's never heard him mention"/"across the city" (Ep5–7) vs. an der Docks-Warehouse-Row (Ep9) vs. "three doors down" von Hans Grocery (Ep10 P11).
12. **Mira-Notiz-Reset:** Fund als Novum in Ep5 trotz Ep2/Ep3; Ablageort wandert Flurschublade → Manteltasche → Box → Küchenschublade ohne Anschluss.
13. **Ep5 P6:** Borus nächtlicher Besucher (Komplize?) wird eingeführt und nie aufgelöst.
14. **Hans Geheimnis:** Ep4 P16 Immigrations-Formular (Concept Ep3) vs. Ep7/8 nicht erklärbare Docks-Nächte (Concept Ep6: Schwarzlieferungen) — beide Versionen laufen unverbunden nebeneinander; Ep3 P7 "I've never been down there [docks]" kollidiert mit den späteren regelmäßigen Docks-Nächten.

### Wiederholte Phrasen / LLM-Tics (Zählung über 10 Episoden)
- Style-Tag-Monokultur: "quiet, …" **178×**, "measured" **97×**, "to himself/herself" **148×** (davon "half to himself/herself" 16×), "barely audible" **34×**, "deflecting" **29×**.
- "Not yet" als Szenen-Schlusspointe **33×** — das strukturelle Grundmuster der Serie: Figur entdeckt etwas, beschließt zu warten. Funktioniert als Motiv, nutzt sich aber durch schiere Frequenz ab.
- "a beat too …" (fast/quick/long/still) **14×**; "That's all this is" **12×** (Selbstberuhigungs-Formel, quer durch Elias, Lin, Zhou, Mira — nivelliert die Figurenstimmen); "It's fine" 7×, "Get some sleep" 6×.
- Wiederholte Szenen-Templates: Han schrubbt Graffiti/Fenster **5×** (Ep3/4/5/8/9); Boru-Ritual im Hinterzimmer mit Objekt/Foto **5×** (Ep1/3/5/6/8); Mira findet/versteckt/befragt Notiz **8 Szenen**; Lin "schreibt es auf, zeigt es niemandem" **7 Szenen**; wortgleiche Boru-Begrüßung "Twice in one month…" (Ep4/Ep8).

### Thread-Bilanz
- **Puppeteer's Game:** ~65 von 170 Parts — dominant, trägt die Serie; im Mittelteil (Ep4–6) leicht redundant (drei fast identische Boru-Werkstatt-Szenen).
- **The Frame (Han):** ~27 Parts — bestes Verhältnis von Sendezeit zu Wirkung; Hans Bogen ist emotional der stärkste der Staffel, endet konsequent bitter ("Seeing it isn't the same as fixing it").
- **Vance Marriage:** ~32 Parts — ausreichend Sendezeit, aber dramaturgisch auf der Stelle: Mira trifft von Ep2 bis Ep8 sieben Mal dieselbe Entscheidung (beobachten, nicht fragen). Die Concept-Vorgabe "consult a lawyer / moves out" (Ep8/9) rettet den Bogen spät.
- **Institutional Doubt:** ~28 Parts — der Lin-Zhou-Parallelismus (beide schweigen einander an) ist zweimal stark (Ep4 P11, Ep5 P10) und danach nur noch Wiederholung; Payoff in Ep8 P10 gut.
- Kein Thread verhungert; das Problem ist nicht Verteilung, sondern Stagnation innerhalb der Threads (Mira, Lin) durch das "Not yet"-Muster.

### REVIEW-Abgleich-Ergebnis
- Ep1 REVIEW flaggte P15 (Boru-Soliloquy verrät Täter+Motiv) → **unbehoben** im Skript.
- Ep3 REVIEW flaggte P15 (Boru bekennt die Han-Falle) → **unbehoben**.
- Ep2, 4–10: "Keine Auffälligkeiten" — der Episoden-Review hat sämtliche schweren Fehler übersehen (Zhou-Gender, Custody-Lücken-Zahlen, Namens-/Alterswechsel), was erwartbar ist: Er prüft episodenweise ohne Serien-Gedächtnis. Der Ep9/Ep10-Konflikt und die Motivdrift sind ohne Cross-Episode-Kontext nicht detektierbar → Lücke im Review-Design, nicht nur in dieser Serie.

## Top-5 konkrete Korrekturen (priorisiert)

1. **Ep9 PART 17 neu schreiben (Doppel-Klimax auflösen):** Verhaftung, Handschellen und "denied its final hand" streichen. Gemäß Concept-Outro endet Ep9 damit, dass Elias allein vor Boru steht und die Antwort "not the one he came for" hört — Lin/Zhou erreichen die Docks erst in Ep10-Zeit. Der "Next time"-Teaser passt dann wieder. (Ein Part, chirurgischer Eingriff, größter Qualitätsgewinn.)
2. **Borus Motiv auf Aldous kanonisieren:** Ep1 P15 + Ep3 P15: "Daniel"→"Aldous", "Nine years"→"Forty years", Sohn→Bruder (Uhr/Foto können bleiben); Ep8 P14 "Thirty years"→"Forty years". Alternativ Daniel als Deckname streichen — Hauptsache eine Version.
3. **Fakten-Suchlauf Familie/Zahlen:** Hans Frau einheitlich benennen (3 Edits: Ep3 P10, Ep9 P4, Ep10 P11 → z. B. überall "Yuan"), Tochter auf ein Alter festlegen (Ep5 P8, Ep6 P9), "Mr. Mei"→"Mr. Han" (Ep7 P5, Ep10 P12), Ep8 P4 "Eleven minutes"→"Four hours" und Ep10 P9 an P8s "three hours" angleichen, Laden-/Ehejahre vereinheitlichen.
4. **Zhou-Geschlecht in Ep1–4 auf männlich normalisieren** (per Skript-Edit aller she/her/herself-Stellen in Zhou-Kontext, ~15 Stellen) — sonst spricht die männliche Eric-Stimme unter weiblicher Narration; zusätzlich Ep6 P10/P16 gegen section_locations prüfen bzw. SFX_PLAN-Ambience für diese zwei Parts manuell korrigieren.
5. **Pipeline-Fix (für Re-Runs):** In create_series die `case[].solution`/`objective_facts` einmal erzeugen und über alle Episoden wörtlich durchreichen (Canon-Lock) statt pro Episode neu formulieren zu lassen; im Skript-Stage ein serienweites Fakten-Sheet (Namen, Alter, Orte, Clue-Texte, Zeitachse) in den Kontext geben und den Episode-Review um einen Cross-Episode-Konsistenzpass ergänzen. the_understudy zeigt, dass ohne Canon-Lock gerade die längste Serie am stärksten driftet.
