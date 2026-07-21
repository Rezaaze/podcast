# negative_space — Tiefenanalyse

**Serie:** Negative Space (soap_opera, drama, 8 Episoden, erstellt 16.07 — 8-Folgen-Format, Editier-Vertrag aktiv, Beats + LLM-Review vorhanden)
**Gelesen:** episodes.json (vollständig), ep1–ep8.txt (vollständig), alle `_REVIEW.txt`, det_findings.json.

## Serien-Überblick

**Prämisse:** Forensik-Analyst Ethan Voss erhält eine anonyme Festplatte mit Familienfotos — in jedem Bild derselbe Schatten am Bildrand, jede Familie tot durch "Unfälle". Der Absender ist Ethans alter Fotografie-Mentor Mr. Han, ein Serienmörder, der Ethan als Nachfolger auditioniert.

**Threads:** (1) *Trophy Rooms* (Haupt-Krimi, Han), (2) *The Second Byline* (Linas Geheim-Recherche + anonyme Quelle), (3) *Trust at the Lab* (Marcus' Leaks aus Kränkung), (4) *The Shop's Ledger* (Schulden des Cho-Familienladens, ab Ep2).

**Gesamturteil: 5/10.** Auf Episoden-Ebene ist das Handwerk stark — atmosphärische Prosa, unterscheidbare Figurenstimmen, exzellente dramatische Ironie um Han, taktile Forensik-Details genau wie die style_guidelines es verlangen. Auf Staffel-Ebene kollabiert aber die Kontinuität: Die case-Threads in episodes.json wurden zwischen den Episoden mehrfach **retconned** (Linas Quelle hat 4 verschiedene Identitäten, Marcus' Kontakt ebenso, Yukis alter Fall hat 6+ widersprüchliche Versionen), und die Skripte folgen jeweils dem lokalen JSON statt den bereits geschriebenen Vorgänger-Skripten. Ein Binge-Hörer bemerkt spätestens in Ep7, dass die Serie ihr eigenes Mid-Season-Reveal (Ep5: "Meine Quelle ist Marcus") vergessen hat. Das ist der eine strukturelle Fehler, der eine 8/10-Staffel auf 5/10 drückt.

---

## Episode 1: The Anonymous Drive

**Stärken:**
- Kalt-öffnender Narrator-Monolog (P1) etabliert das Voyeurismus-Thema elegant ("everyone believes they are the one doing the watching").
- P8 (Han allein im Darkroom) ist Muster-Subtext: Ledger, Messingmarke "Arthur", "Someone's finally paying the right kind of attention" — zeigt, plaudert nicht aus.
- P14: Yukis Mikro-Verhalten ("half a beat after the others have looked away") verkauft ihr `hides` perfekt.
- Marcus' Kränkung (P5) wird über konkrete Details aufgebaut ("Lead analyst, E. Voss. Secondary, M. Tang."), nicht über Exposition.

**Schwächen:**
- P17 eskaliert zu weit und frisst Ep2 das Material weg: Die Wand voller Reports mit Sato+Mei nimmt Ep2s "Woche der stillen Bestätigungen" vorweg (Ep2 spielt die 11-Jahre-Entdeckung erneut als neu, siehe unten).
- P2: Der allwissende Narrator verrät das geloopte Kamera-Feed-Detail ("its feed was looped six minutes before") — suggeriert High-Tech-Täter, was der späteren Low-Tech-Lösung (Schlüssel) widerspricht und dem Hörer Wissen gibt, das kein Ermittler je erlangt.

**Fehler (korrigierbar):**
1. **P17 vs. P9/Ep2:** Mei: "Nine families. Nine rulings" und Marcus: "Report on the Alvarez file, ninety-four … Ninety-four to now. That's not a case. That's a career." — Widerspruch zu P9 ("this is every single photograph. All twelve. Twelve different families") und zur gesamten Ep2, die den Zeitraum auf **elf Jahre** festlegt ("dated eleven years before the first"). '94 = 20+ Jahre. Fix: P17 auf "zwölf Familien, Zeitraum noch unklar" zurückschneiden.

## Episode 2: Dead Ends

**Stärken:**
- P1-Narrator über "Bestätigung als Akkumulation, nicht Entdeckung" — ungewöhnlich ehrliche, ruhige Procedural-Dramaturgie.
- P4 (Ethan findet "Arthur Voss" auf dem Storage-Mietvertrag und redet es sich klein) ist der beste Grusel-Beat der Frühstaffel — der eigene Nachname als Alias.
- P12: Hans Unterrichtsszene, in der er beiläufig Urlaubsroutinen der Familie abfragt ("Every other weekend, then. That's a good rhythm") — Auswahlprozess als Smalltalk, vorbildliches Show-don't-tell.

**Schwächen:**
- Die Episode wiederholt Ep1 P15–17: Die 11-Jahre-Spanne wird in P6 (Mei: "Call it a decade") UND P15 (Team: "Eleven years. Give or take a season") jeweils als frische Erkenntnis inszeniert, obwohl Ep1 P17 schon "ninety-four to now" an der Wand hatte.
- Drei Parts unter Wortbudget (det_findings P3/P4/P5) — P3 und P4 sind inhaltlich Ein-Beat-Szenen (Case anlegen; Arthur Voss finden), die Planung gab ihnen zu wenig Material.

**Fehler (korrigierbar):**
1. **P5, Wissens-Leck Han:** "Marcus heard something about a reporter, poking around the old cases." — Han kann zu diesem Zeitpunkt weder Marcus kennen noch wissen, was Marcus hört; kein Kanal existiert (die Clerk-Kette wird erst in Ep7/8 erfunden). Fix: "Marcus" durch "One of my regulars" ersetzen.
2. **P8 vs. Ep1 P10, Corkboard-Zählung rückwärts:** Ep1: "That's four now. Four families." → Ep2: "Three. That's three now that don't sit right." Fix: Ep2 auf "five" heben.
3. **P9 Wohnsituation:** "Ethan and Lina's apartment" (gemeinsame Wohnung) vs. Ep1 P10 (Linas Zimmer, "not her roommate") und getrennte Locations laut JSON. Zieht sich weiter (Ep4 P13, s. u.).
4. **P2 vs. Ep1 P15:** "Eight through twelve are Han's students" (= 5 Familien) vs. Ep1: "Four of the twelve families have a payment record there."

## Episode 3: Coordinates

**Stärken:**
- P8/P9 (Storage-Unit-Entdeckung) — der abgestoppte Rollladen, das Licht, das "keine Wand zurückgibt", Schuh und Ring als kuratierte Objekte: stärkste Horror-Szene der Staffel.
- P15: Ethan plaudert Han gegenüber arglos den Koordinaten-Durchbruch aus — doppelbödig, weil Han der Adressat des Fortschritts ist ("Then I suppose the hard part starts now").
- P10: Der Weitergabe-Ketten-Narrator ("No one asks permission first. No one tells him at all.") macht Marcus' Kontrollillusion hörbar.
- P2: Mei referenziert Ethans nicht geloggten Storage-Lead aus Ep2 — seltener, gelungener Rück-Anschluss.

**Schwächen:**
- Linas Quelle wechselt die Erscheinungsform: Ep2 stummer Mann im Windbreaker, hier spricht sie durch einen Stimmmodulator persönlich (P4) — Ep4 behauptet dann, man habe sich nie getroffen.
- P6 (Landlord-Szene) ist reine Narration ohne Dialog — verständliche Voice-Workaround (Vater/Landlord haben keine Stimmen), aber hörbar flacher als der Rest.

**Fehler (korrigierbar):**
1. **P9 vs. Ep1 P17:** "That's the Alvarez family… closed as a house fire, eleven years ago" vs. Ep1 "Alvarez file, ninety-four" (und Ep8: Alvarez-Todesdatum "March the fourteenth, two thousand nine"). Drei Versionen desselben Familiennamens.
2. **P9 vs. Ep2 P2:** Mei: "Eight families, at least, and we've only confirmed five off the drive so far" — Ep2 hatte bereits "Twelve confirmed, zero flagged elsewhere".
3. **P7:** Yukis alter Fall heißt jetzt "Delgado" (6 Jahre alt, fehlende Objekte Kamera/Ring/Kinderschuh) — kollidiert mit Ep1 P14 (CO-Vergiftung, Boiler, "six, seven years back") und Ep2 P16 (Treppensturz, Prellungen). Siehe Serienmuster.
4. **P16, fallengelassener Cliffhanger:** "No. Not this time. I have to call him. Tonight, before I lose the nerve." — Ep4 ignoriert diesen Entschluss komplett (Lina verheimlicht weiter, P16 tippt und löscht stattdessen eine Nachricht).

## Episode 4: Closer Than He Thinks

**Stärken:**
- P14 (Darkroom-Lektion als Grooming-Metapher: "You wait until the subject tells you… A print taken too early is just a guess") — die beste Han-Szene, Doppelcodierung ohne ein einziges explizites Wort.
- P5/P6: Die Quelle fragt nach Ethans Alltag; Linas verzögertes Begreifen ("She types it before the question fully lands") ist psychologisch präzise.
- P8: Yukis Selbstverhör ("I'm not rereading this to check my work. I'm rereading it hoping it clears me.") — bester Einzelsatz der Staffel für ihre Figur.

**Schwächen:**
- Zweimal dieselbe Pointe in Folge: P1 "One unit is a fluke. Two is a pattern." und P2 "Two is a pattern. One's just a story." — im Abstand von zwei Minuten Hörzeit.
- P16 (219 W.) und P15 (174 W., det_findings) sind dünn geplant — P15 ("Mei almost tells Ethan") ist als Ein-Beat-Szene angelegt und kann das Budget nicht füllen.

**Fehler (korrigierbar):**
1. **P2 vs. P3, Objekt-Switch:** In der Unit stoppt Ethan bei "Small tin. Rooster painted on the lid" (loggt es als "miscellaneous kitchenware") — in P3 grübelt er zu Hause über ein völlig anderes Objekt: "Tortoiseshell. Chipped along one edge. Nothing special about a comb like that." Der Kamm kommt in P2 nie vor. Fix: P3 auf die Blechdose umschreiben (oder P2 auf den Kamm).
2. **P13, kaputter Narrator-Satz:** "The Second Byline thread returns: Lina's editor girlfriend, guarding a source Ethan doesn't know exists." — Lina ist Reporterin, nicht Editorin, und die Syntax ist Kauderwelsch. Zudem erneut "in the apartment Ethan shares with Lina" (Kohabitations-Drift).
3. **P5:** Quelle: "Appreciate the years, Lina." — Die Beziehung besteht laut JSON und Ep2 seit ~4 Monaten. (Als Han-Hinweis lesbar, aber faktisch falsch.)
4. **P8:** Yukis Fall jetzt "faulty wiring", "four years ago", Familie zu dritt — vierte Version in vier Episoden.
5. **P1-Recap:** "a faded supplier stamp … led Ethan to a room full of belongings" — falsch, die GPS-Koordinaten führten zur Unit, der Stempel wurde dort erst gefunden.

## Episode 5: The Photo in His Own Apartment

**Stärken:**
- Dichteste Episode: Foto-Reveal, Byline-Kollision, Schulden-Eskalation und Marcus-Konfrontation greifen sauber ineinander; jede Szene bedient genau einen Thread (style_guideline eingehalten).
- P14 (Ethan/Marcus im Labor): "I can hear which one you're not saying." — Konfrontation über Subtext, nicht Geschrei; Marcus' "I wanted to matter to somebody's story for once" begründet den Verrat aus der etablierten Kränkung.
- P10: Linas erzwungene Beichte vor den Eltern in einem einzigen ununterbrochenen Redefluss — formal riskant, funktioniert als Panikmoment.
- P16: Han-Soliloquy ("It was never the room.") — literarisch stark, ABER siehe REVIEW-Abgleich.

**Schwächen:**
- P13/P14: Lina nennt Marcus als Quelle "this whole time" — das JSON-Retcon bricht hier offen mit Ep1–4 (stummer Fremder am Geländer, Modulatorstimme, Umschläge mit zittriger Handschrift, Burner-Fragen nach Ethans Wohnort: alles Dinge, die der persönlich bekannte Kollege Marcus nie tun würde/müsste). Das Skript versucht keinerlei Brücke.
- P9 (133 W.): Die Promenaden-Konfrontation — der emotionale Wendepunkt der Beziehung — ist die kürzeste Szene der Episode; das "unit not locker"-Detail ist klug, aber der Bruch verdient doppelte Länge.

**Fehler (korrigierbar):**
1. **P10, Namens-Kollision:** Der Eintreiber heißt "Mr. Alvarez" — Alvarez ist bereits eine Opferfamilie (Ep1/Ep3/Ep8) und wird in Ep7 auch noch die überwachte Zielfamilie. Fix: umbenennen.
2. **P5 vs. Ep3 P9:** "Whitfield file. Nine years back… Gas leak, they said." — Ep3: "the Whitfields. Boating accident, upstate."
3. **P3 vs. Ep2 P10/P11:** Lina: "Last year it was papers in Appa's desk drawer… A year of me sending half of every freelance check" — in Ep2 war sie noch vollständig ahnungslos ("Lease stuff, probably… He'd tell me if it were anything."). JSON-Retcon (Shop's Ledger) ungebrückt ins Skript übernommen.
4. **P16, REVIEW-Befund nicht behoben:** Das LLM-Review flaggte Hans Monolog korrekt als Lösung-Spoiler ("unambiguously reveals that he is grooming Ethan as a serial killer successor") — der Text steht unverändert im finalen Skript.

## Episode 6: Reflections

**Stärken:**
- P12: Yukis Fund (Spieluhr, "Chip, left shoulder" in beiden Inventarlisten) — Beweis über Objektbeschreibung statt Behauptung; ihr Diktiergerät-Monolog ("I closed it anyway.") trägt den Part allein.
- P5: Mei konfrontiert Marcus vor der Eskalation — die Beziehungslogik (Loyalität als Komplizenschaft) wird konsequent weitergedreht.
- P3: Das Telefonat, in dem Yuki den Terminal-Namen erfährt, ohne dass der Hörer die Gegenseite hört — gutes Audio-Handwerk.

**Schwächen:**
- P10: Ethan reagiert auf Satos Marcus-Enthüllung wie auf eine Neuigkeit ("Say that again. Slower.") — er weiß es seit Ep5 aus Linas Mund UND aus Marcus' eigenem Geständnis. Nur ein Halbsatz ("what I already know") rettet notdürftig.
- Die Reflexions-Auflösung auf einen Storefront ("Ashgrove and Third", drei Blocks von Ethans Wohnung) wird von Ep7 komplett überschrieben (s. Serienmuster).

**Fehler (korrigierbar):**
1. **P13 vs. P15, Fragment-Mismatch:** P13: Buchstabenfragment "—ARBOR" ("Could be a street name") → P15: "Corner of Ashgrove and Third. The sign fragment matched a storefront awning." "ARBOR" passt nicht zu "Ashgrove" (kein A-R-B-O-R enthalten). Innerhalb derselben Episode.
2. **P11, falscher Szenen-Rückbezug:** Ethan zu Marcus: "That's not what you said to me on the promenade." — Die Ethan/Marcus-Konfrontation in Ep5 P14 war im Labor; auf der Promenade sprach Ethan mit Lina.
3. **P9:** "the Delgado file — the one I closed out three years ago" — fünfte Datierung (3 J.), und P12 behandelt parallel "Whitfield" als ihren Fall. Zwei Fallnamen für denselben Arc in einer Episode.
4. **P4 (124 W.):** Marcus' Log-Löschung als Mini-Szene — inhaltlich wichtig (Backup-Audit-Setup), aber unter Budget, weil als reiner Funktions-Beat geplant.

## Episode 7: The Stakeout

**Stärken:**
- Operations-Handwerk: Tarp-Fehlalarm (P12), Funkloch am Storage-Perimeter (P13), Nebel als Gegner — echte Stakeout-Textur statt Abkürzung zur Action.
- P10: Han verabschiedet Ethan vor der Operation ("Be careful out there tonight, Ethan. Whatever it is.") — wissend, dass er selbst das Ziel ist; die Szene hält die Ironie mühelos.
- P17: Taschenlampen-Reveal als Cliffhanger exakt auf outro_note ("It turns.") — der Staffelhöhepunkt sitzt.
- P6: Lina findet die Zielfamilie an der eigenen Laden-Wand — verbindet Byline- und Shop-Thread physisch.

**Schwächen:**
- Die Episode tut durchgehend so, als sei Linas Quelle nie enthüllt worden — das Mid-Season-Reveal von Ep5 ist ausradiert.
- P14: Lina hat plötzlich Funkgerät und "assigned position" im Polizei-Perimeter — als Reporterin unplausibel, dient nur dem Protokollbruch-Beat.

**Fehler (korrigierbar):**
1. **P7, größter Einzel-Kontinuitätsbruch der Staffel:** Ethan: "Then tell me who's feeding you this. Just a name, Lina. That's all I'm asking." / Lina: "I've told you I can't do that." — In Ep5 P13 hat Lina ihm den Namen gegeben ("Marcus. It's been Marcus this whole time."), Ethan hat Marcus daraufhin zweimal konfrontiert. Fix: Dialog auf die *zweite*, anonyme Burner-Quelle umschreiben ("Marcus war nie der Einzige — wer ist der andere?").
2. **P1-Recap überschreibt Ep6:** "the reflection … led Mei to a fragment of rusted metal too small to name" — Ep6 P15 hatte die Reflexion bereits als Storefront-Markise bei "Ashgrove and Third" aufgelöst. Ep7 P1 ersetzt das Ergebnis durch den Gantry-Kran, ohne Übergang.
3. **P2:** Die überwachte Familie heißt "Alvarez" — dritter, diesmal lebender Träger des Namens (vgl. Ep5 Fehler 1).
4. **P5:** Mei erinnert "die zwei Nächte, in denen die Storage-Units schnell geleert wurden" — on-screen wurden beide Units **voll** vorgefunden (Ep3 P9, Ep4 P2); eine Räumung wurde nie gezeigt oder erwähnt. Ep7/8 behandeln sie als bekannte Fakten.
5. **P3:** Yukis Fall: "Riverside families, first one, three years back" — nächste Variante.

## Episode 8: The Successor

**Stärken:**
- P8 (Verhör): Hans Confessio als Ästhetik-Vortrag ("Every one of them, I photographed first… waited for the moment they trusted the lens") und der Schulden-Reveal ("You didn't save them. You bought us.") — der Twist, dass selbst die Rettung des Ladens ein Zug war, ist der beste Payoff der Staffel.
- P13: Han verweigert Yuki die eine Antwort ("Some things are better left where they are, Detective.") — die Serie hält die Disziplin, nicht alles aufzulösen; deckt sich exakt mit series_outro.
- P12: Ethan findet im Darkroom den Print von sich selbst "from the overlook. Tonight." — letzter Beweis von Hans Kontrolle, still inszeniert.
- P16: Kein Action-Finale, sondern Ethan allein mit der Frage, wie viel er "verstanden" hat — mutiger, thementreuer Schluss.

**Schwächen:**
- Der Shop's-Ledger-Thread wird als bereits gelöst behandelt (Mutter weinte über das "Wunder"), obwohl die Rettung **nie eine Szene bekam** — zwischen Ep5 ("Thirty days. I don't know how. But fine.") und Ep8 passiert der Payoff unsichtbar.
- Die Doppel-Quellen-Logik (Marcus UND Clerk als Linas Quellen) wird behauptet (P6), aber nie mit Ep5 versöhnt; Marcus und Lina haben keine einzige gemeinsame Szene zur Aufarbeitung.

**Fehler (korrigierbar):**
1. **P3 vs. Ep1 P15, Laden-Adresse:** "That's Han. From the camera shop on Blessing Street." — Ep1: "Han's Camera Shop. Corner of Delmar and Ninth."
2. **P13:** "March the fourteenth, two thousand nine. The Alvarez family." — dritte Alvarez-Datierung (’94 / vor 11 Jahren / 2009); zudem Foto-Exponat "Nineteen ninety-eight" als Yukis Fall — sechste Datierung ihres Falls.
3. **P8/P11, Reveal eines nie gezeigten Ereignisses:** Die Schulden-Tilgung ("A gift, before you understood the rules") braucht eine gepflanzte Szene in Ep6/Ep7 (z. B. Linas Vater erhält die Bestätigung des Zahlungseingangs), sonst wirkt der Twist behauptet statt verdient. Ebenso weiß Lina in P10 vom Kassierscheck ("Same block the cashier's check came from"), ohne dass sie je davon erfahren hat.
4. **Fallengelassene Pflanzung:** Der Alias "Arthur Voss" (Ep2 P4 — Hans gruseligste Signatur: Ethans eigener Nachname) wird nie wieder erwähnt; Ep8 nennt stattdessen "the Alderman name". Ein Satz im Verhör ("You noticed the name on the Riverside lease, I hoped you would") würde den besten Plant der Staffel einlösen.

---

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)

1. **Linas Quelle — 4 Identitäten:** stiller Ex-Detective mit Umschlägen/zittriger Handschrift (Ep1–2, persönliche Übergaben) → persönlich anwesend mit Stimmmodulator (Ep3 P4) → "nie getroffen, nur Burner-Messages" (Ep4 P5, Narrator explizit) → "Marcus. It's been Marcus this whole time." (Ep5 P13) → wieder anonymer Burner-Clerk (Ep7 P7, Ep8 P6/P10). Ep7 P7 negiert das Ep5-Reveal wörtlich.
2. **Marcus' Außenkontakt — 4 Identitäten:** True-Crime-Podcast-Host "LabRat_MT" (Ep1 P12) → Freelance-Decoder aus PD-Vorzeit (Ep3 P3/P10, Ep4 P9) → Lina (Ep5–6) → Storage-Facility-Clerk (Ep7 P9, Ep8 P6). Podcast-Host und Decoder verschwinden ersatzlos.
3. **Yukis alter Fall — 6+ Versionen:** CO/Boiler, Familie zu viert, "six, seven years back" (Ep1 P14) → Treppensturz/Prellungen (Ep2 P16) → "Delgado", 6 J., fehlende Objekte (Ep3 P7) → Kabelbrand, 4 J., Familie zu dritt (Ep4 P8) → "Whitfield", Gasleck, 9 J. (Ep5 P5) → "Delgado, three years back" + Whitfield-Spieluhr als ihr Fall (Ep6 P9/P12) → "first one, three years back" (Ep7 P3) → Foto von 1998 (Ep8 P13).
4. **Whitfield-Todesursache:** Bootsunfall upstate (Ep3 P9) vs. Gasleck (Ep5 P5).
5. **Alvarez-Name dreifach verbraucht:** Opferfamilie mit drei Datierungen ('94 / vor 11 J. / 14.03.2009) + Eintreiber "Mr. Alvarez" (Ep5 P10) + lebende Zielfamilie (Ep7 P2).
6. **Tatzeitraum:** "ninety-four to now… twenty-some years" (Ep1 P17) vs. 11-Jahre-Spanne als Neuentdeckung (Ep2 P2/P6/P15) vs. "Twenty years" (Ep5 P7).
7. **Zähl-Chaos:** 12 Tode bestätigt (Ep2 P2) → "only confirmed five off the drive" (Ep3 P9); Linas Corkboard 4 → 3 → 5 (Ep1 P10 / Ep2 P8 / Ep3 P5).
8. **Reflexions-Clue-Reset:** Ep6 löst auf Storefront "Ashgrove and Third", 3 Blocks von Ethans Wohnung ("—ARBOR"-Fragment passt nicht mal intern); Ep7 P1 ersetzt durch Gantry-Kran am Riverside Overlook, ~"four blocks from my building".
9. **Falscher Szenen-Rückbezug:** Ep6 P11 "you said to me on the promenade" (Konfrontation war im Labor, Ep5 P14).
10. **Shop-Schulden-Arc:** Lina ahnungslos (Ep2) vs. "wusste es seit einem Jahr, zahlt seit einem Jahr" (Ep5 P3); Auflösung (Han zahlt) findet nur off-screen statt.
11. **Wohnsituation:** Linas Mitbewohnerin (Ep1 P10) / Ethan hinter ihrer Schlafzimmertür (Ep2 P8) / "Ethan and Lina's apartment" (Ep2 P9), "apartment Ethan shares with Lina" (Ep4 P13) vs. durchgehend getrennte Wohnungen in Ep5–8.
12. **Han-Wissens-Leck:** Ep2 P5 nennt Han "Marcus" namentlich, bevor irgendein Kanal existiert.
13. **Nie gezeigte Unit-Räumungen:** Ep7 P5/Ep8 P6–P7 referenzieren zwei "Clear-outs" (Unit 14 nach 9 h, Unit 22 nach 31 h) — beide gefundenen Units waren on-screen voll.
14. **Laden-Adresse Han:** "Delmar and Ninth" (Ep1 P15) vs. "Blessing Street" (Ep8 P3).
15. **Storage-Alias-Drift:** "Arthur Voss" (Ep2) → "Bright Frame Imaging Solutions LLC" (Ep3 P12) → "Alderman" (Ep8 P13); der Voss-Alias wird nie eingelöst.

### Wiederholte Phrasen / LLM-Tics (Zählung)

- **"That's not a coincidence, that's a …(habit/shape/pattern)"** — ≥7× (Ep1 P9, Ep2 P2, Ep4 P1, Ep4 P2 [doppelt in Folge!], Ep6 P12, Ep7 P5, Var. Ep3 P7 "That's a specific list to repeat by accident").
- **Ungesendete-Nachricht-Szene (tippen → vorlesen → löschen):** 4× fast identisch: Lina Ep4 P16, Marcus Ep5 P4, Ethan Ep6 P14, Lina Ep8 P10 (E-Mail). Plus Ep3 P16 als Vorstufe. Als Motiv lesbar, als Szenen-Template ermüdend.
- **"Not yet." als Szenenschluss-Beat:** ≥8× (Yuki Ep3 P7, Ep4 P8, Ep5 P5, Ep7 P13; Lina Ep2 P8; Han Ep5 P16; Ethan Ep1 P3 …).
- **"That's all it is / That's all this is":** ≥5× (Ep3 P17, Ep4 P13, Ep5 P1, Ep5 P10, Ep7 P11).
- **Narrator-Formel "Neither of them says …":** in praktisch jeder Episode 1–3× als Szenen-Ausleitung.
- **"a beat too long/too fast/too casual":** ≥8× über die Staffel.
- **SFX-Muster "a glass/mug/folder set down hard":** ≥9 Cues; die det_findings-"nicht hörbaren" Cues sind fast alle vom Typ "X, then silence/stillness" (Ep2 P3, Ep3 P11, Ep5 P10, Ep8 P10/P13) — derselbe Formulierungs-Tic erzeugt systematisch unbrauchbare Cues.
- **Rooftop-Bar-Szene mit erzwungenem Toast/dünnem Lachen:** 6× (Ep1 P13, Ep2 P14, Ep3 P13, Ep4 P12, Ep5 P15*, Ep8 P14) — dramaturgisch gewollt als Ensemble-Anker, aber die Beat-Struktur (Marcus-Witz → Mei lacht nicht → Themawechsel) ist 4× identisch.

### Thread-Bilanz

- **Trophy Rooms:** ~55 % der Parts — angemessen dominant, sauber eskaliert (Drive → Zertifikate → Koordinaten → Units → Apartment-Foto → Reflexion → Stakeout → Verhör).
- **The Second Byline:** ~20 % — gut versorgt, aber durch die Quellen-Retcons inhaltlich beschädigt; der Ep5-Payoff (Marcus) und der Ep8-Payoff (Clerk/Han-Orbit) konkurrieren, statt aufeinander aufzubauen.
- **Trust at the Lab:** ~18 % — kontinuierlichster Neben-Arc (Kränkung → Leak → Vertuschung → Überführung → Ächtung); Marcus fehlt in Ep8 nach P7 spürbar/gewollt (leerer Stuhl).
- **The Shop's Ledger:** ~7 % — klar unterversorgt: 6 Szenen über 7 Episoden, und die Auflösung (Hans Zahlung) findet **nicht statt**, sondern wird in Ep8 nur berichtet. Der Thread existiert praktisch nur, damit Ep8 den "You bought us"-Twist hat — dieser Twist ist stark, aber sein Fundament wurde nie gebaut.
- *Han's World* (Ep1/2-Sections) geht folgerichtig in Trophy Rooms auf.

### REVIEW-Abgleich-Ergebnis

- 7 von 8 Reviews: "Keine Auffälligkeiten." — Angesichts der oben dokumentierten Brüche zu milde; die Reviews prüfen offenbar nur episodenintern und übersehen selbst dort Dinge (Ep4 Tin/Kamm-Switch, Ep6 ARBOR/Ashgrove).
- **Ep5-Review flaggte korrekt** den Han-Monolog (P16) als Lösungs-Spoiler — **der Befund wurde nicht behoben**, der Monolog steht unverändert im Skript. Der Review→Fix-Loop hat hier nicht gegriffen.
- Kein Review bemängelt Cross-Episoden-Kontinuität — erwartbar, da dem Reviewer die Vorgänger-Skripte offenbar nicht vorliegen. Genau dort entsteht aber der Hauptschaden dieser Serie.

---

## Top-5 konkrete Korrekturen (priorisiert)

1. **Ep7 P7 umschreiben (Quellen-Amnesie):** Ethans Forderung "Just a name" muss anerkennen, dass Marcus seit Ep5 enttarnt ist. Fix-Weg: Dialog auf eine explizit *zweite* Quelle drehen — "Marcus war der Anfang. Wer ist der andere, der mit dem Burner schreibt?" Damit werden Ep1–4 (anonyme Quelle) und Ep5 (Marcus) rückwirkend kompatibel und Ep8 P6 ("Your harmless guy … is Lina's anonymous source") schließt sauber an. Aufwand: 1 Szene + 2 Sätze im Ep7-P1-Recap.
2. **Reflexions-Clue Ep6↔Ep7 versöhnen:** Entweder Ep6 P13–15 auf das Kran-Fragment umschreiben (statt "Ashgrove"-Storefront), oder Ep7 P1/P2 als Verfeinerung framen ("die Markise war der Spiegel — die Quelle des Winkels ist der Kran"). Zusätzlich intern Ep6 P13 "—ARBOR" an den finalen Straßennamen angleichen. Aufwand: 2 Parts.
3. **Yukis Cold Case in einem Pass vereinheitlichen:** Ein Name (Empfehlung: Whitfield), eine Ursache (Empfehlung: Gasleck), ein Jahr (Empfehlung: 9 Jahre), ein fehlendes Objekt (Spieluhr) — konsistent einsetzen in Ep1 P14, Ep2 P16, Ep3 P7, Ep4 P8, Ep5 P5, Ep6 P9/P12, Ep7 P3, Ep8 P13; Alvarez-Datierungen dabei mitziehen und Eintreiber (Ep5 P10) + Zielfamilie (Ep7 P2) umbenennen. Aufwand: reine Suchen-und-Ersetzen-nahe Edits mit einer Referenztabelle.
4. **Shop's-Ledger-Payoff dramatisieren:** Eine kurze Szene in Ep6 oder Ep7 (Linas Mutter ruft an: "Es ist bezahlt. Alles.") plus ein Halbsatz, wie Lina vom Kassierscheck erfährt (Ep8 P10). Macht Ep8 P8/P11 ("You bought us") vom behaupteten zum verdienten Twist. Aufwand: 1 neue Kurzszene + 1 Satz.
5. **Ep5 P16 entschärfen (offener REVIEW-Befund):** Hans Monolog auf die vom Review vorgeschlagene Ambivalenz zurückschneiden — "It was never the room" darf bleiben, "Someone showed me… I never forgot the debt of it" und "before he understands what he's being given" streichen/abschwächen. Bonus in derselben Runde: Ep4 P2/P3 Objekt angleichen (Tin vs. Kamm), Ep4 P13 Narrator-Satz reparieren, "Arthur Voss"-Alias in Ep8 P8 mit einem Satz einlösen.

**Pipeline-Lehren:** (a) Der Stage-01-Generator schreibt die Thread-`solution`s pro Episode neu, statt sie zu vererben — genau daraus entstehen die Identitäts-Retcons; solutions sollten nach Ep1 eingefroren oder nur additiv erweitert werden. (b) Der Skript-Writer braucht die Vorgänger-Skripte (oder ein kanonisches Fakten-Sheet: Namen, Daten, Adressen, Aliase, Wer-weiß-was-Stand) im Kontext. (c) Der Review-Loop muss Befunde erzwingen (Ep5) und Cross-Episoden-Fakten prüfen. (d) SFX-Cues vom Typ "…, then silence" systematisch verbieten — das ist die Quelle fast aller nicht hörbaren Cues dieser Serie.
