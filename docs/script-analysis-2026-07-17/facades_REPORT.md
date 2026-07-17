# facades — Tiefenanalyse

## Serien-Überblick

**Prämisse:** Familiendynastie-Soap (Succession-Ton): Beim Centennial-Gala der Vanderburgs wird nach einem Jahr die Leiche von Elena Marsh (Julians Verlobte) aus dem See geborgen; noch in derselben Nacht erhalten alle vier Vanderburgs anonyme Briefe. Vier Threads: **The Death of Elena Marsh** (Konrad tötete sie im Streit; sie war von ihm schwanger), **The Blackmailer** (Anwältin Isabelle Liu), **Chloe & Marcus** (Affäre mit dem Chauffeur), **Konrad's Debts** ($2,4M an Anson Fong).

**Gesamturteil: 4/10.** Szenenweise ist das die stärkste Dialogarbeit, die man von der ältesten Pipeline-Generation (10.07, kein Review, keine Beats) erwarten kann — Subtext, unterscheidbare Figuren, echte Cliffhanger, exzellente dramatische Ironie um Isabelle. Aber die serienübergreifende Faktenlage kollabiert: Der Fundort der Leiche, der Inhalt der Erpresserbriefe, Marcus' Zeugenaussage, Konrads Alibi, die gefälschte Abhebungssumme und die Zahlungshistorie ändern sich von Episode zu Episode. Ohne Recap-Mechanismus/Review hat das Modell jede Episode Details "neu erfunden" statt nachgeschlagen. Als Einzelepisoden 7/10, als Serie hörbar inkonsistent.

**Sonderauftrag-Verifikation (Ep2-Recap):** Der deterministische Befund "Ep2: kein previously-on-Recap" ist ein **False Positive**. Ep2 PART 1 beginnt mit einem vollwertigen Recap-NARRATOR-Block: „Elena Marsh disappeared from her own engagement dinner one year ago and was never found — until this week… By nightfall, four members of the family were each holding an identical, unsigned letter. None of them have said a word about it to each other." Es fehlt nur die wörtliche Floskel „Previously on", auf die die Regex offenbar matcht (Ep3–10 benutzen sie alle).

---

## Episode 1: The Centennial Toast

- **Stärken:** Bestes Kaltstart-Setup der Serie: Gala-Fassade gegen Floodlights am See; Victoria/Konrad-Reibung etabliert beide in 10 Zeilen; die vier Umschläge mit je EINER Zeile („The lake remembers everything, Konrad." / „Driver.") sind kleine Detonationen exakt im Sinne der style_guidelines. Konrads Solo-Telefonate (PART 7/8) verkaufen die Schulden ohne Exposition-Dump.
- **Schwächen:** PART 7/8 sind zwei aufeinanderfolgende Quasi-Monologe Konrads am Telefon — 1.000 Wörter einseitiges Telefonat strapazieren das Audio-Format. Die 44 SFX-Cues sind Rohware (8 nicht hörbar laut det-Check), typisch für den Pipeline-Stand.
- **Fehler (korrigierbar):**
  1. PART 11: Victoria findet den Brief „no stamp… No postmark I can see" auf dem Kopfkissen — episodes.json objective_fact sagt „postmarked from a mailbox forty minutes from the estate, dropped days before the body was even discovered". Skript widerspricht der Case-Faktenlage (handplatziert statt gepostet); Ep5 PART 7 zementiert es („delivered by hand, not post").
  2. PART 11/12: Die vier Briefe haben vier VERSCHIEDENE Texte — Case sagt „identical, unsigned typed note" (Outro-Note „one line each" stützt allerdings das Skript; die Planung widerspricht sich hier selbst).

## Episode 2: Cracks in the Marble

- **Stärken:** Julians Pressestatement (PART 9, „Her name was Elena Marsh…") ist der emotionale Höhepunkt der halben Staffel. Victorias Nevada-Anwalt-Telefonat (PART 4) macht Geldwäsche prozedural spannend — genau die „mechanics of maintaining a facade" aus dem Briefing.
- **Schwächen:** Ab hier viele Szenen mit „NARRATOR: The detective asks…" — der Gesprächspartner wird komplett wegabstrahiert; spart Sprecher, wirkt aber über 10 Parts hinweg monoton.
- **Fehler (korrigierbar):**
  1. PART 3: Victoria liest „ihren" Brief aus Ep1 neu vor — jetzt lautet er: „I know what the trust signature really cost this family. The first installment is due Friday…". In Ep1 PART 11 stand dort: „Ask Konrad where he was the night she died." Kompletter Retcon des Briefinhalts inkl. neu erfundener Zahlungsforderung.
  2. Folgefehler: Der Brief nennt „the trust signature" — Victoria entdeckt die gefälschte Signatur aber erst in Ep3 PART 5 und behandelt sie dort als völlige Neuigkeit. Dass der Erpresserbrief sie explizit nennt, wird nie verarbeitet.
  3. PART 2: Konrad erzählt dem Detective die Schnittwunden-Story als „carving the turkey… six stitches, Saint Agatha's" — in Ep1 PART 10 war die etablierte Story „some glass you'd dropped clearing plates" (von Julian erinnert, von Konrad bestätigt). Sein Alibi soll laut Victoria „the same way every time" erzählt werden; der Wechsel wird in-Story nicht bemerkt (erst Ep10 lampenschirmt „three different stories" — gegenüber der Polizei bleibt es ein Loch).

## Episode 3: Whatever It Takes

- **Stärken:** Konrads Fälschungs-Szene (PART 1, „The V drops, then climbs…") ist großartiges Show-don't-tell; Victorias Archiv-Entdeckung (PART 5, „That's not how I close my V… It is not mine.") die beste Solo-Szene der Serie; der zweite Erpresserbrief mit exakter Summe „$240.000, the exact amount you moved in March" verzahnt Blackmail- und Schulden-Thread elegant (zwei Deadlines!).
- **Schwächen:** PART 5/6 sind zusammen ~950 Wörter Victoria-Monolog — stark geschrieben, aber im Audio ermüdend. Recap behauptet „divers pulled Elena Marsh's body" und „paid a stranger, in cash" — beides falsch (Baukolonne/Bagger; Überweisung via Anwalt).
- **Fehler (korrigierbar):**
  1. PART 6: Victoria findet „Three of these now that don't sit right" — drei verdächtige Abhebungen. Laut Case existieren genau zwei Fälschungen (eine alte + die aus PART 1 dieser Nacht, die noch gar nicht im Foundation-Archiv liegen kann). Die dritte bleibt für immer unerklärt.
  2. Recap-Retcon „divers" infiziert die Episode selbst (Julian: „even before the divers found her", Marcus: „since the divers") — Ep1 hatte die Bagger-Crew etabliert.

## Episode 4: The Ledger

- **Stärken:** Isabelles Audit-Pitch (PART 1/2) ist Serien-Bestwert an dramatischer Ironie („Let someone else hold the ledger" / Victorias „You're the only person left in this house I haven't had to watch. Don't make me start."). Victorias Handschrift-Erkennung über die Kindheits-Anekdote („The K drags left before it climbs… since he was nine years old") gibt dem Plot-Beat echtes Gewicht.
- **Schwächen:** Chloe/Marcus (PART 7/8) wiederholt inhaltlich fast eins zu eins ihre Ep3-Szene (soll ich Julian sagen, was Marcus sah? → nein, wegen uns) — der Thread tritt auf der Stelle.
- **Fehler (korrigierbar):**
  1. PART 1: Victoria: „Marcus found her wedged under the old dock pilings, under six feet of water" — dritte Fundort-Version (Ep1: Bagger-Crew im Poolhaus-Fundamentgraben; Ep3: Taucher). Zusätzlich wird ausgerechnet Marcus zum Finder erklärt.
  2. Recap PART 1: „Marcus Chen finally told Chloe what he saw **the night Elena Marsh disappeared**" — laut Ep3/Case sah er den Streit „weeks before she disappeared".
  3. PART 4: Victoria erinnert Konrads Alibi als „he walked her as far as the terrace and turned back for a drink" — Ep1: „We talked for five minutes down on the dock." Alibi-Drift Nr. 2.

## Episode 5: Blood Is Not Enough

- **Stärken:** Julians ME-Anruf (PART 1) nur über seine Gesprächshälfte ist formal die eleganteste Szene der Serie; die Sapphire-Halsketten-Erinnerung und Victorias „shadow nursery" (PART 3/4) geben der Trauer Textur; Chloes Solo (PART 9, „five separate people performing the same funeral face") ist das beste Figuren-Essay der Staffel.
- **Schwächen:** Die Dinner-Szene (PART 11/12) recycelt wörtlich das „Fine is doing a great deal of work"-Spiel aus Ep3 PART 10 (dort: „You've said 'fine' three times… that's usually your tell").
- **Fehler (korrigierbar):**
  1. PART 6/10: Massiver Retcon von Marcus' Aussage. Ep3 PART 4 benannte er Konrad explizit („Konrad and her, out on the dock… I saw him grab her arm") und zitierte „I'm keeping it." Jetzt: „I said I couldn't be sure who" und Chloe bestätigt: „You were very specific about not being sure." PART 10: „I couldn't swear to you who it was… it wasn't Julian's build." Unvereinbar mit Ep3.
  2. PART 11: Victoria: „you were the last one to see her that night, **at the terrace**" und Konrad: „We said goodnight by the terrace, same as I told the police a hundred times" — Alibi-Drift Nr. 3 (Dock → Terrasse), als wäre es immer so erzählt worden.
  3. PART 5: Marcus: „I've driven this family fifteen years" — er ist 31 (Casting) und die Chens fahren laut Case „two generations"; hier zusätzlich „My grandfather drove… My father did too" (drei Generationen).

## Episode 6: Whose Child

- **Stärken:** Victoria/Julian-Eröffnung (PART 1) hat die härtesten Zeilen der Serie („I won't say it twice." / „Grieve where I can see you."); Isabelles Panik-Soliloquy (PART 6) nachdem Victoria „eighteen months" Banking-Historie anfordert, ist Thriller-Handwerk; PART 8 (Victoria über die Lügen-Tells ihrer drei Kinder) exzellent.
- **Schwächen:** Julians Verdächtigen-Liste (PART 3) bleibt folgenlos (Fotograf/Professor/Segellehrer tauchen nie wieder auf).
- **Fehler (korrigierbar):**
  1. PART 2: Julian über Konrad & Elena: „Every holiday, every summer at the lake house, you two were thick as thieves" (als Kinder!) — Elena kam laut Ep6 PART 9 erst vor zwei Jahren über Julian in die Familie. Retcon macht sie zur Jugendfreundin.
  2. PART 7/8: Der Whitfield-Landdeal heißt jetzt zweimal „the **Whitmore** land" — Namenskollision mit dem Whitmore Family Trust (Käufer ist die Whitfield Group, Ep2/Ep8).
  3. PART 1: Victoria zu Julian: „Someone in this family, or very near it, put that girl in the lake" — ihr knowledge-Slice verlangt, dass sie ihre Schlussfolgerung „from Julian entirely" verbirgt; hier serviert sie ihm die halbe Auflösung (nur ohne Namen).

## Episode 7: Open Doors, Closed Ranks

- **Stärken:** „Nobody said ledger, Konrad." (PART 4) ist der beste Verhör-Beat der Serie; die Doppel-Telefon-Szene (PART 10: Isabelle unterdrückt erst Chloes Foto, berät dann Victoria zu ihren eigenen Erpresserbriefen) ist Dramaturgie auf Soll-Niveau; Victorias „I wanted you to see me know it" (PART 6) trägt den Outro-Cliffhanger perfekt.
- **Schwächen:** „Fifteen years" fällt in dieser Episode 6-mal, fast alles Isabelle — die Figur bekommt ein Verbal-Tick-Korsett.
- **Fehler (korrigierbar):**
  1. PART 1: Der vierte Brief sagt „Four notes. **Still no payment.**" — aber Victoria hat in Ep2 gezahlt (binnen Stunde eingelöst), und Julian sagt in PART 2 dieser Episode: „We've paid three times already, Mother." Brief und Dialog widersprechen sich in derselben Episode.
  2. Folgefehler: Dass Julian und Chloe von Zahlungen wissen (PART 2/3, inkl. „the wire account… same one from the second demand"), verletzt Victorias hides-Slice („The payment itself from Julian, Chloe, and Konrad") — nie wurde gezeigt, dass sie es erfahren.
  3. PART 1: Der Brief verrät „**Elena found the entry in the trust ledger** that didn't add up. She's gone." — (a) Isabelle kann nicht wissen, dass Elena die Fälschung fand (steht nur in der solution; ihr knows-Slice deckt es nicht), (b) es leakt ein Kernstück der Elena-Auflösung an die ganze Familie — und niemand (Julian! Chloe!) reagiert je auf diese Zeile.
  4. PART 1: „The price doubles: two million" — Verdopplung von $400k (Ep5) wäre $800k; und PART 5 nennt die März-Abhebung „Four hundred thousand dollars" statt $240k (Ep3).

## Episode 8: The Weight of the Name

- **Stärken:** Victoria/Marcus am Seeufer (PART 7/8) ist die beste Zwei-Personen-Szene der Staffel („I'm asking you to stop deciding, on my behalf, what I'm strong enough to hear."); Victorias Beweis-Auslege-Monolog (PART 9/10) mit dem ausgesprochenen Wort „Murder" ist ein würdiger Mittelpunkts-Höhepunkt; Marcus' „Her silence is an answer too" (PART 6) beendet den Beziehungs-Thread-Beat sauber.
- **Schwächen:** Die Beweisliste in PART 9 erfindet gleich zwei neue Artefakte (s.u.), um „vier Lügen" aufzählen zu können.
- **Fehler (korrigierbar):**
  1. PART 2: Julian: „…the week before **my wedding**" und Konrad: „Go find **your fiancée's** seating chart" — Julian hat keine Verlobte und keine Hochzeit; Elena ist tot. Halluzinierte Realität mitten in der Episode (vermutlich Gala-Verwechslung).
  2. PART 1: Julian: „**Fong's** men were photographed outside your building in April" — Julian kennt Fong nicht; sein knowledge-Slice kennt nur den Whitfield-Vertrag. Niemand hat ihm je von Fong erzählt.
  3. PART 7: Marcus' dritte, wieder neue Aussage-Version: Jetzt war er in der **Todesnacht** am Bootshaus („the night of the engagement dinner… past eleven"), hörte „she was keeping the baby, Julian deserved to know everything", hörte sie „go quiet all at once" und sah Konrad allein am gebrochenen Geländer. Unvereinbar mit Ep3 (Wochen vorher, er unterbrach den Streit per Bootslärm) und Ep5 (konnte niemanden identifizieren). Case/objective_fact sprechen weiter nur vom „argument he witnessed".
  4. PART 9: Abhebung jetzt „**Six hundred thousand** dollars" (Ep3: 240k, Ep7: 400k) und „a paternity result, sealed, **dated three days before the engagement dinner**" — der Vaterschaftstest wurde erst nach der Bergung gemacht (Ep6); ein pränatales, verstecktes Ergebnis ist ein neues, unmögliches Artefakt (Ep9-Recap wiederholt es: „the paternity records Elena hid").
  5. PART 1: „We buried Elena's memorial **three months ago**" — kollidiert mit Ep10 („I buried the girl… **eleven days ago**") und der weiterlaufenden Friday-Deadline-Dringlichkeit aus Ep7.
  6. PART 6: Marcus: „**Two years** my father drove for this family before me" — vierte Version der Chen-Dienstzeit.

## Episode 9: The Night on the Dock

- **Stärken:** Die Beichte (PART 3/4) ist der stärkste Einzel-Part der Serie — präzise, physisch, ohne Selbstmitleid („I performed CPR on my dead pregnant almost-sister-in-law for eleven minutes by my watch"); Victorias Fixer-Telefonate (PART 6) zeigen ihre Kompetenz prozedural; „Konrad slept that night believing he had been forgiven. He had not been forgiven." ist ein perfekter Outro.
- **Schwächen:** PART 7 lässt Isabelle ihren Forderungsbrief laut diktieren — die Serie hat ihre Identität für den Hörer längst zehnfach bestätigt, hier verpufft die letzte Ambiguität ohne Not.
- **Fehler (korrigierbar):**
  1. PART 5: Konrad: „That was **Isabelle's idea**, the runaway-bride story, to keep the police from—" und Victoria: „I know whose idea it was." Das macht Isabelle zur Mitwisserin/Komplizin der ursprünglichen Vertuschung vor einem Jahr — widerspricht dem kompletten Blackmailer-Design (sie entdeckte nur die Signatur; von Konrads Tat wusste niemand).
  2. PART 5: „Detective **Reyes**" vs. Ep10 „Detective **Ruiz**" — und Konrads Tarnname in Ep10 ist ausgerechnet „Konstantin **Reyes**".
  3. PART 2/3: Affäre „started in March. Before Julian even proposed" + Elena entdeckte „my withdrawal, from the trust" vor ihrem Tod — kollidiert mit Ep2 („six-month grace period… after the trust withdrawal") und Ep3/Ep6, die die erste Fälschung als ~6 Monate alt (also NACH Elenas Tod) behandeln. Der Planungsfehler steckt schon in episodes.json (solution verlangt Fälschung vor ihrem Tod; Konrad's-Debts-objective_fact sagt „six months ago").
  4. PART 6: „cold feet"-Skript für Elenas Mutter seit einem Jahr — kollidiert mit dem etablierten öffentlichen Großaufgebot (Flyer, Belohnung, Privatermittler, Julians Suche, Ep1/2).
  5. PART 8: Victoria: „Every note has known things… What happened with the girl in Miami" — kein vorgelesener Brief erwähnte je Miami; nur Isabelles Soliloquy tat es.

## Episode 10: Legacy

- **Stärken:** Victoria/Isabelle-Showdown (PART 3/4) löst den Blackmail-Thread mit der Codicil-Formulierung („Confession is a luxury the guilty rarely afford themselves twice") intelligent auf; „I don't threaten people I've decided to keep" ist die beste Zeile der Staffel; Tarmac-Abschied („Goodbye, Konstantin.") und Chloes finales „That's the answer" schließen beide Threads exakt wie geplant; Julians „Almost Knowing" (PART 7/8) trifft den Case-Slice punktgenau.
- **Schwächen:** PART 11/12 sind zwei Victoria-Monologe hintereinander mit deutlicher Aussagen-Redundanz („I built this name out of nothing…" zum x-ten Mal).
- **Fehler (korrigierbar):**
  1. PART 3: Die Identifikations-Note „came the morning after we pulled **Elena's coat off the dock railing**" — vierte Fundort-/Auffinde-Version und eine Note, die es in keiner Episode gab (die Ep1-Briefe lagen abends in den Zimmern).
  2. PART 7: Julian: Konrad war Letzter bei Elena — „I only found out **from Chloe, weeks later**, almost by accident" — Ep1 PART 10 konfrontierte Julian Konrad selbst damit („That's all anyone ever asked you").
  3. PART 7: Victoria erfindet vierte Wunden-Story („He sliced it on a broken cabinet hinge") und behauptet, Konrad habe „three times, **under oath**" ausgesagt, er habe sie „partway to the dock" gebracht — Alibi-Drift Nr. 4.
  4. PART 8: Victoria: „we discussed it as a family in March, the whole ugly business" (Konrads Spielschulden) — die Familie wusste laut Case/Skripten nie davon; Julian widerspricht nicht.
  5. PART 11: „**Konrad** Reyes is somewhere over the Atlantic" — der Tarnname war „**Konstantin** Reyes" (PART 2/5/6).
  6. PART 2/7: „eleven days ago" (Beerdigung/Umbruch) — Timeline-Kollision mit Ep8 („three months ago").

---

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)

1. **Fundort/Auffindung der Leiche (4 Versionen):** Bagger-Crew im Fundamentgraben (Ep1) → „divers" (Ep3) → „Marcus found her wedged under the old dock pilings" (Ep4) → „Elena's coat off the dock railing" (Ep10).
2. **Marcus' Zeugenaussage (3 unvereinbare Versionen):** Ep3 benennt Konrad + „I'm keeping it", Wochen vor dem Verschwinden; Ep5 „war nie sicher, wer"; Ep8 Todesnacht mit Volltext-Ohrenzeugenschaft und gebrochenem Geländer.
3. **Konrads Alibi (4 Versionen):** 5 Min. auf dem Dock (Ep1) → Terrasse (Ep4/5) → Boothaus, zurück zum Zelt (Ep6) → „partway to the dock, under oath" (Ep10) — für eine Figur, deren Überleben an wortgleicher Konsistenz hängt.
4. **Briefinhalt-Retcon:** Victorias Ep1-Brief („Ask Konrad where he was the night she died") wird in Ep2 zu einer Trust-Signatur-Forderung mit Friday-Deadline.
5. **Zahlungs-Historie:** 1 Zahlung gezeigt (Ep2) vs. „Still no payment" (Brief, Ep7) vs. „We've paid three times" (Julian, Ep7) vs. „Four notes I paid without a word" (Victoria, Ep8).
6. **Summen-Drift der März-Fälschung:** $240k (Ep3) → $400k (Ep7) → $600k (Ep8).
7. **Timeline:** Tage/Wochen-Takt (Ep1–7, Gala „in eleven days") vs. „memorial three months ago"/„April" (Ep8) vs. „buried her eleven days ago" (Ep10).
8. **Fälschungs-Zeitpunkt:** Erste Abhebung „six months ago"/laufende grace period (Ep2/3) vs. Elena entdeckte sie vor >1 Jahr (Ep9-Beichte; von der solution verlangt) — Wurzel bereits in episodes.json (Konrad's-Debts-Fakt widerspricht der Elena-solution).
9. **Isabelle als Alt-Komplizin:** „runaway-bride story was Isabelle's idea" (Ep9) — widerspricht dem gesamten Thread-Design.
10. **Julian-Wissen:** kennt „Fong" (Ep8) und „wusste erst Wochen später von Chloe", dass Konrad Letzter war (Ep10) — beides gegen etablierten Stand.
11. **Julians Phantom-Hochzeit** (Ep8 PART 2).
12. **Elena als Kindheits-Vertraute Konrads** (Ep6) vs. 2-Jahres-Beziehung.
13. **Chen-Dienstjahre:** two generations (Case/Ep1) / 3 Generationen (Ep5) / „fifteen years" Fahrer mit 31 (Ep5) / „two years my father drove" (Ep8).
14. **Detective Reyes (Ep9) vs. Ruiz (Ep10)** + Kollision mit Alias „Konstantin Reyes"; „Konrad Reyes" (Ep10 PART 11).
15. **Brief-Logistik:** gepostet mit Poststempel (Case) vs. handzugestellt ohne Stempel (Ep1/5).
16. **Öffentliche Suche** (Flyer, Belohnung, Ermittler) vs. „cold feet"-Skript an Elenas Mutter (Ep9).

### Wiederholte Phrasen / LLM-Tics (Zählung über alle 10 Skripte)

- **„fifteen years": 30×** (Peak Ep7: 6×; auch von Marcus und Konrad benutzt — es ist Isabelles Kernattribut, das auf andere Figuren abfärbt)
- **„never once": 31×** (figurenübergreifend, Victorias Superlativ-Muster kolonisiert alle Stimmen)
- **„eight months": 20×** (Chloe/Marcus benennen ihre Affärendauer fast jede Szene)
- **„too fast/too quick"-Regieanweisungen: 13×**, **„a beat too …": 9×**, **„of all nights": 10×**, **„handled": 14×** (Ep6 lampenschirmt es immerhin: „You keep reaching for that word")
- Wiederkehrende Bausteine: „built this family/empire/name out of nothing" (5×), „X is doing a great deal of work in that sentence" (Ep3 + Ep5, fast wortgleich), das „Fine"-Tell-Spiel doppelt (Ep3/Ep5), zweimal fast identische „soll ich Julian sagen…"-Szenen (Ep3/Ep4).

### Thread-Bilanz

- **Death of Elena Marsh:** ~45 % Sendezeit, klar dominant — gerechtfertigt, da Haupt-Thread; Eps 8–10 fast monothematisch.
- **The Blackmailer:** ~20 %, in jeder Episode präsent, Auflösung Ep10 sauber — aber der am schwersten von Faktendrift beschädigte Thread (Briefinhalte, Zahlungen, Summen).
- **Chloe & Marcus:** ~20 %, konstant bedient, emotional konsistent, aber inhaltlich redundant (Ep3/4 nahezu dieselbe Szene; „choose me"-Beat dreimal: Ep1, Ep8, Ep10). Der anonyme SMS-Absender (Ep7 PART 8) bleibt unaufgelöst.
- **Konrad's Debts:** ~15 %, effizient erzählt, gute Verzahnung mit Blackmail (Doppel-Deadline Ep3); Whitfield-Deal versandet nach Ep8 kommentarlos (Ep9 zahlt Victoria einfach — ob der Deal platzte, bleibt offen).
- Kein Thread verhungert; die Balance selbst ist die größte planerische Stärke der Serie.

### REVIEW-Abgleich

Keine `_REVIEW.txt`- und keine `_BEATS.txt`-Dateien vorhanden (nur `epN.txt` + `epN_META.txt`) — konsistent mit dem Pipeline-Stand vom 10.07 (vor LLM-Review/Beat-Layer). Kein Abgleich möglich. Bemerkenswert: Genau die Fehlerklassen, die das spätere Review + der Beat-Layer adressieren (Faktendrift zwischen Episoden, Zahlen-Konsistenz, Zeugen-Aussagen), sind hier die Hauptschadensbilder — facades ist der beste Beleg dafür, warum diese Pipeline-Stufen eingeführt wurden.

---

## Top-5 konkrete Korrekturen (priorisiert, mit Fix-Weg)

1. **Marcus-Aussage vereinheitlichen (Ep5 PART 6/10, Ep8 PART 7).** Kanon auf Ep3 festlegen (Streit Wochen vorher, Konrad benannt, „I'm keeping it"). Fix: In Ep5 die Zeilen „I said I couldn't be sure who" / „You were very specific about not being sure" streichen bzw. zu „I never told you all of it" umschreiben; in Ep8 Marcus' Bericht auf den Wochen-vorher-Streit zurückschneiden (kein Todesnacht-Ohrenzeuge, kein gebrochenes Geländer aus seiner Sicht) — Victorias Beweiskette funktioniert auch ohne.
2. **Blackmail-Buchhaltung reparieren (Ep2 PART 3, Ep7 PART 1/2, Ep8 PART 11).** Ep2: Victorias Brief-Neuvorlesung durch den Ep1-Wortlaut ersetzen und die Zahlungsforderung in einen ZWEITEN, nur an sie gerichteten Brief verlegen (eine neue NARRATOR-Zeile genügt). Ep7: „Still no payment" → „Your payments bought you silence, not me"; Julians „We've paid three times" → „You've paid, haven't you" (Victoria weicht aus) — hält ihren hides-Slice intakt. Ep8: „Four notes I paid without a word" → „Four notes I answered without a word to anyone".
3. **Julians Phantom-Hochzeit tilgen (Ep8 PART 2).** „…the week before my wedding" → „…the week of Mother's gala"; „Go find your fiancée's seating chart" → „Go find Mother's seating chart". Zwei-Zeilen-Edit, beseitigt den auffälligsten Einzel-Fehler der Serie. Im selben Durchgang Ep8 PART 1 „Fong's men" → „men in gray sedans" (Julian darf den Namen nicht kennen).
4. **Zahlen & Namen normalisieren (Ep7 PART 5, Ep8 PART 9, Ep6 PART 7/8, Ep9 PART 5, Ep10).** März-Abhebung überall auf $240.000 (Ep3-Kanon); „Whitmore land" (Ep6) → „Whitfield deal"; Detective einheitlich „Ruiz" (Ep9 PART 5 ändern, wegen Alias-Kollision mit „Reyes" NICHT den Alias); Ep10 PART 11 „Konrad Reyes" → „Konstantin Reyes"; Ep8 PART 9 das pränatale Paternity-Dokument („dated three days before the engagement dinner") auf das Post-Mortem-Laborergebnis aus Ep6 umformulieren.
5. **Isabelle-Komplizenschaft entfernen (Ep9 PART 5) + Fundort fixieren (Ep3 Recap, Ep4 PART 1, Ep10 PART 3).** Ep9: „That was Isabelle's idea, the runaway-bride story" → „That was my idea, the runaway-bride story — and everyone was relieved enough to believe it" (Victorias Antwort „I know whose idea it was" streichen). Fundort überall auf Ep1-Kanon (Baukolonne, Fundamentgraben): Ep3-Recap „divers" ersetzen, Ep4 „Marcus found her…" → „They found her wedged…", Ep10 „the morning after they pulled her from the lake".

**Empfehlung fürs Re-Run-Lernen:** facades zeigt, dass Szenen-Qualität ohne Faktengedächtnis nicht trägt. Ein „Canon-Sheet" (Fundort, Alibi-Wortlaut, Brieftexte, Summen, Namen, Timeline) als Pflicht-Kontext pro Episode — heute durch Beats + Review teilweise abgedeckt — hätte ~80 % der 22 korrigierbaren Fehler verhindert.
