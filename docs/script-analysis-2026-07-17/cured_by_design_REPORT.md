# cured_by_design — Tiefenanalyse

**Serie:** Cured by Design (soap_opera, drama, 8 Episoden, erstellt 16.07 — 8-Folgen-Format, Editier-Vertrag, Beat-Layer, LLM-Review aktiv)
**Gelesen:** episodes.json vollständig, ep1–ep8 vollständig, alle 8 `_REVIEW.txt`, det_findings.json

## Serien-Überblick

**Prämisse:** Eine Abrisskolonne findet in einer 70er-Jahre-Anstalt eine eingemauerte Zeitkapsel — Tagebücher der Nachtschwester Eleanor Voss plus Polaroids von Patienten, die als "cured" entlassen wurden und spurlos verschwanden. Ein True-Crime-Podcast (Mira Kwon + Ethan Cole) zieht die Fäden; jeder führt zu heutiger Macht. Vier Threads: **The Time Capsule** (das Programm), **The Inside Plant** (Ethan ist der Enkel des Anstaltsdirektors), **The Senator's Bloodline** (Marshs Großmutter war Patientin), **The Silencing Campaign** (Fixer Victor Lane).

**Gesamturteil: 4/10.** Das ist die frustrierendste Serie, die man sich vorstellen kann: **Szenenhandwerk auf 8/10-Niveau, seriale Kohärenz auf 1/10-Niveau.** Dialog, Subtext, Figurenstimmen, Cliffhanger und die Marsh/Pike-Arcs gehören zum Besten, was die Pipeline produziert hat. Aber die episodes.json mutiert den **Kern-Kanon der Mystery pro Episode** — Name des Direktors (4 verschiedene!), Programmname, Anstaltsname, Patientenzahl, alle Schlüsseldaten, sogar Ethans Abstammungslinie — und die Skripte übernehmen diese Drift ungefiltert **auf Sendung**. Bei einem Rätsel-Podcast, dessen Payload aus Namen und Daten besteht, ist das für Durchhörer fatal. Dazu kommt ein in sich widersprüchliches Finale (Ethan konfrontiert live on air, ist aber laut Log vor Beginn der Sendung gegangen) und zwei Sprecher-Fehlbesetzungen, die Hörer direkt verwirren.

### Die Kanon-Drift auf einen Blick (alles ON AIR, nicht nur im Konzept)

| Fakt | Ep1–2 | Ep3–4 | Ep5–6 | Ep7–8 |
|---|---|---|---|---|
| Direktor | **Ambrose Faulkner** (ep1 P7: "Ambrose Faulkner. My grandfather ran this hospital."; ep2 P13 "Dr. Faulkner signed off") | **Warren Ashcroft** (ep3 P15 Eleanor: "Warren Ashcroft ordered it."; ep4 P10 "Ashcroft's estate") | **Reginald Ashford** (ep6 P15 "Directing physician. Dr. Reginald Ashford."; ep6 P17 "Ashford's name, out loud, on record") | **Julian Wexford** (ep7/8 durchgehend) |
| Monogramm/Initialen | A.F. ("that slant on the F") | W.A. ("monogram on the cufflinks in my mother's cedar box") | R.A. / Warren Ashford = Vater | — |
| Programmname | — | — | **The Continuity Program** (ep6 P10 on air!) | **Project Threshold** (ep7 Recap, ep8 Broadcast) |
| Anstaltsname | **Ridgeline Asylum** (ep1 P5 on air) | namenlos | namenlos | **Ashgrove Sanatorium** |
| Patientenzahl | **14 Polaroids** (Staffel-Ikone, on air ep1+2) | 14 | 14→? | **41 Namen** (ep7 P4, ep8 P6; Pike: "I logged forty-two") |
| Marshs Großmutter | **Mei-Ling Chow**, Aufnahme März **1975** (ep2 P5), Entlassung **1977**, Trust **sechs Wochen später** (ep2 on air) | Diane Marsh, Heirat April **1974**, Zahlungen 1974–1985 (ep4 P10) | **Mei-Lin Chao**, Aufnahme **1971** (ep6 P2 "admission date … seventy-one"), Resettlement 1974 | Aufnahme "in the sixties", Entlassung **1981**, Heirat 6 Wochen später (ep8 P8 — Marshs Live-Testimony!) |
| Namensänderung Cole | — | — | **1979**, Ashford→Cole, Petent = Ethans **Vater** Warren (ep5 P9, ep6 P15) | **1981**, Wexford→Cole, "mother's maiden name" (ep7 P2) |
| Ethans Linie | **mütterlich** (ep1 P12: Anruf bei Mom, "daughter of the asylum's former director"; ep3 "meine Mutter") | mütterlich | **väterlich** (ep5 P6 Victor: "what your father built after 1979"; ep6 "Warren Cole, formerly Warren Ashford. Father of one. Ethan") | väterlich (aber Cole = Muttername!) |
| Ethans Wissen | entdeckt A.F.-Polaroid geschockt (ep1 P7); Erstkontakt Netzwerk erst ep4 P17 ("Don't call this number again") | wird erstmals kontaktiert | voller Kollaborateur, Garagen-Meetings | "recruited **four months before** episode one", wusste alles von Anfang an (ep8 P12 on air) |
| Eleanor-Flashbacks | 1975–1977, verschwindet Dez. 1977, Kapsel 1977 versiegelt | 1976 | — | Oktober **1979**, "a diary sealed in 1979" (ep8 P13) |
| Anstalts-Schließung | 1977 (ep1 P8) | — | **1976** (ep6 P10 on air: "doors closed in nineteen seventy-six") | 1978/79 impliziert |

Dazu die rechnerische Unmöglichkeit: ep6 P15 nennt on air "Ethan Warren Cole. **Born 1988**", ep7/8 behaupten, der 7–8-jährige Junge auf dem 1979er Ward-Foto sei "feature for feature … **the same boy**" wie Ethan (ep7 P14, ep8 P11). Ein 1988 Geborener kann 1979 nicht fotografiert worden sein.

**Ursache:** Die `case`-Blöcke in episodes.json wurden pro Episode neu generiert statt einmal fixiert — Solution, objective_facts und sogar Eigennamen driften ab Episode 3 frei. Die Skript-Stufe hat der jeweiligen Episoden-Wahrheit treu gedient und die Drift damit hörbar gemacht. Der Beat-/Review-Layer prüft offenbar nur intra-episodisch — und selbst da nicht zuverlässig (s. REVIEW-Abgleich).

---

## Episode 1: What the Capsule Kept

- **Stärken:** Starker Cold Open (Brecheisen findet den Hohlraum, kein Dialog nötig). Ethans Verbergen ist mustergültig "um das Geheimnis herumgeschrieben": Foto halten (P3), "Just the case number. Nothing else." (P6, seine erste Lüge), private Erkennung erst allein (P7). Mira/Ethan-Dynamik sofort unterscheidbar. Eleanor-Diary-Register sitzt. Cliffhanger (das eine Gesicht am Corkboard) zieht sauber in Ep2.
- **Schwächen:** P12 (129 W.) und P13 (212 W.) unter Budget, weil die Szenen inhaltlich einzeilig geplant sind (ein Telefonat, ein Wiedererkennen) — deckt sich mit den det_findings. Discharge-Fenster wackelt intern: P6 "March to September, '77" vs. P14 "between April and October".
- **Fehler (korrigierbar):**
  1. **P8: Sprecher-Fehlbesetzung.** Der pensionierte Lokalreporter im Diner spricht mit dem Tag `[DR_HAROLD_PIKE]` ("Wasn't strange to me. I've been waiting for someone to ask…"). Pike wird aber erst in Ep2 als Records-Orderly eingeführt und knallt Mira die Tür vor der Nase zu ("I don't talk about that job. Not to strangers"). Hörer hören dieselbe TTS-Stimme als zwei verschiedene Figuren mit widersprüchlichem Verhalten. Fix: Szene als einseitigen Dialog umschreiben (wie ep2 P7 mit dem Union-Kontakt) oder Kontakt durch NARRATOR paraphrasieren.
  2. **P7: "Ambrose Faulkner"** — muss auf den Serien-Kanon (Wexford, s. Top-Korrekturen) umgestellt werden, inkl. "slant on the F".
  3. P4: Eleanor erwägt "asking someone above me. **Doctor Pike**, maybe" — Pike ist Orderly unter ihr, kein Vorgesetzter und kein Arzt.
  4. P5 nennt die Anstalt "**Ridgeline** Asylum" — kollidiert mit "Ashgrove Sanatorium" ab Ep7.

## Episode 2: Names on Film

- **Stärken:** Der einseitige Diner-Dialog (P7, stummer Union-Kontakt) ist eine elegante Lösung gegen Stimmen-Inflation. Marsh-Einführung über einen banalen Bürotag mit dem Porträt ("Morning, Grandma.") — beste Art von Soap-Ökonomie. Ethans "God, listen to you. Relieved a stranger's family gets dragged through this instead of yours." (P10) ist der beste Selbst-Moment der Staffel. Pikes Tür-Szenen (P8/P11, "You want the shape of it, I'll draw the shape") etablieren die stärkste Figurenstimme der Serie.
- **Schwächen:** P17 (98 W.) zu dünn für einen Staffel-relevanten Cliffhanger; das idle Auto wird in Ep3 nie wieder aufgegriffen (fallengelassener Outro-Beat). P8/P10 unter Budget.
- **Fehler (korrigierbar):**
  1. **P2 vs. P12: Trust-Datum widerspricht sich in derselben Episode.** P2: "Trust filing, opened **January** nineteen seventy-eight … barely two months after the discharge window closes." P12: "**March fourteenth. April twenty-fifth.** That's — six weeks, Ethan." Zwei unvereinbare Datumspaare für denselben Anker-Fakt, auf dem laut P12 "the whole reveal" aufbaut.
  2. P16: "Mei-Ling's face, **sixty years old**" — das Foto ist auf 1975 datiert, also ~50 Jahre alt.
  3. P5: Aufnahme Mei-Lings "March the fourth" **1975** — kollidiert mit ep6 ("seventy-one") und ep8 ("the sixties"); Kanon-Fix nötig.

## Episode 3: The Face That Wasn't There

- **Stärken:** Deepfake-Thread kommt mit Wucht (P1, Miras "That's not my voice"). Victors "Nine days early and they still don't know why. That's the whole game, right there." (P7) ist ein exzellent gepflanzter Mystery-Haken. P15 (Eleanor schreibt den Namen einmal aus, dann nur noch Code) ist die beste Flashback-Szene der Staffel. Ethans Seite-Umschalten (P5: entschlüsselt W.A. allein, taggt die Seite um) dramatisiert "hides" statt es zu erzählen.
- **Schwächen:** Victors einseitige Telefon-/Meeting-Monologe (P7, P13) etablieren ein Muster, das die Serie bis Ep8 ~8× wiederholt — ab Ep5 spürbar formelhaft. Der Deepfake-Thread (Sponsoren, Forensik, "nine days") wird nach Ep4 kommentarlos fallengelassen; das "Wer verriet das Timing?"-Rätsel wird nie on air aufgelöst.
- **Fehler (korrigierbar):**
  1. **P15/P5: "Warren Ashcroft" / "W.A."** — zweiter Direktorname; kollidiert frontal mit ep1 P7 ("Ambrose Faulkner", A.F.). Ein Hörer hat an diesem Punkt zwei verschiedene Großväter für Ethan gehört.
  2. **P10: Regieanweisung als Sprechtext.** `[ETHAN_COLE | style: flat, private]` gefolgt von der Zeile `(quietly, to himself)` — TTS liest die Klammer vor.
  3. P11: Pike bricht bei "Ash—" ab — passt zu Ashcroft/Ashford, ist aber mit dem Faulkner-Kanon von Ep1/2 unvereinbar (gleicher Kanon-Fix).

## Episode 4: Locks and Ledgers

- **Stärken:** Pikes Break-in-Monolog (P1: "A thief doesn't leave the silver candlesticks sitting right there") und die Notizbuch-Übergabe (P7: "I told myself silence was mercy. Tonight I'm not so sure it wasn't cowardice.") sind herausragend. Victor/Marsh-Konfrontation (P5: "I didn't say I had anything on you, Senator. … I said your family.") beste Antagonisten-Szene der Serie. Marsh allein mit den Porträts (P6) veredelt den Bloodline-Thread.
- **Schwächen:** P13/P15 unter Budget (Victor-Handoff und Marsh im Diner sind je ein einziger Beat). Victor sagt "Forty-some years. Your grandmother's years" — die Anstalt liegt ~50 Jahre zurück; Marshs "forty years before I was born" macht die Rechnung noch schiefer.
- **Fehler (korrigierbar):**
  1. **P8 + P9 erzählen denselben Beat doppelt mit zwei verschiedenen Statement-Texten.** P8 (Podcast Studio, mid-broadcast): "…whose sourcing and motives have not been transparently disclosed…". P9 (War Room, "still mid-broadcast"): "The office of Senator Delia Marsh questions the credibility and motivations…". Das Statement trifft zweimal "gerade eben live" ein, unterschiedlich formuliert. Konzept sah P8 als Statement-Drafting bei Marsh vor; die Skript-Stufe hat beide Sections zur Empfangsszene gemacht.
  2. **P10: Pike spricht im Archive Vault** ("Ashcroft's estate paying a private family… That's an obligation.") — Pike ist seit P3 im Safe House und gehört laut Konzept nicht in diese Szene; in P11 sitzt er wieder im Safe House.
  3. **P11: Pike wird als "the borrowed nurse who once worked the asylum's back office" bezeichnet** — er ist Records-Orderly, keine Krankenschwester.
  4. **P15: "(internal, murmured)" und "(to herself)" als eigene Sprechzeilen** — TTS liest die Klammern.
  5. P3 (Z. "He sits, finally, the bag still in his lap.") und P7 ("He slides the notebook across.") — **untagged Prosa ohne [NARRATOR]**, wird dem vorherigen Sprecher zugeschlagen.
  6. P5: Victor nennt die Funde "a stolen film reel" — die Kapsel enthielt Tagebücher + Polaroids, kein Filmmaterial.

## Episode 5: Noise in the Files

- **Stärken:** Die Lockout-Eskalation ist prozedural glaubwürdig erzählt (Recovery-Mails getauscht statt Passwort-Gerate). Victors Doktrin-Monolog (P5: "Fear isn't a thing you repeat to make it hold. It's a thing you pace." / "every hour they spend proving they're still standing is an hour they aren't spending publishing") ist das beste Antagonisten-Writing der Staffel. Pikes Fast-Flucht (P13, Feuerzeug auf/zu; P16 "I'm agreeing because you didn't pretend I shouldn't be.") = Serien-Highlight. Miras stiller Verdachts-Aufbau (P7 Notiz-App unter der Tischkante) ist sauber eskaliert.
- **Schwächen:** Ethans Sprung vom erstmals Kontaktierten (ep4 P17: "Don't call this number again") zum eingespielten Kollaborateur mit Sabotage-Bilanz ("I locked her out of the registry contact twice already", P6) passiert **zwischen** den Episoden, ohne eine einzige Szene der Rekrutierung — der größte Charakter-Arc-Bruch der Staffel neben dem Finale.
- **Fehler (korrigierbar):**
  1. **P9: Mira erfährt, dass der 1979er-Namenswechsel auf "Cole" lautet — und es klingelt nicht.** "C-O-L-E. Cole. … Doesn't ring anything. Not a senator, not a name from the board minutes. Nobody I've flagged." Ihr Co-Host, mit dem sie täglich am Mikro sitzt, heißt Cole; zwei Zeilen später sagt sie sogar "Loop in Ethan. He's better at genealogy." Als dramatische Ironie gedacht, als Ermittlerin disqualifizierend. Fix: Nachname im Record maskiert/abweichend geschrieben, oder Mira registriert den Namen und wiegelt aktiv ab ("Half this county is named Cole").
  2. **P8: `(no line — listening)` als Sprechtext** unter `[ETHAN_COLE | style: still, watching]` — TTS liest es vor.
  3. P6/P15: "what your **father** built after 1979" — Linien-Widerspruch zu ep1–3 (Mutter-Linie); Kanon-Fix.
  4. P6: SFX "a car alarm chirping once, distant, then silence" (det-Flag) — Cue endet auf Nicht-Ereignis; kürzen auf das Chirpen.

## Episode 6: The Director's Blood

- **Stärken:** Dichteste Episode der Staffel. Pikes Solo-Decode (P4: "She wasn't hiding a place. She was hiding a name.") und die zurückgehaltene Danksagung ("She thanks someone here… Just initials.", P9) sind erstklassige Mystery-Beats. Marshs Selbstermächtigung (P12: "It was done to her. I'm not letting anyone smooth that into the wrong shape.") und Victors fassungsloses "Nobody chooses the truth over the seat." — stark. Mira/Marsh im Diner (P11: "Would that have worked?" — "No." — "Then let's not waste the time") ist das beste Zwei-Frauen-Duell der Serie. Foto-Test bei Pike (P16) löst den Cliffhanger körperlich statt expositorisch.
- **Schwächen:** P2 und P8 bestätigen den Chao-Match doppelt (Facial-Rec, dann Papiere) mit nahezu identischem Erkenntnisgewinn. P10: Pike will das Notizbuch "tonight" persönlich bringen, P10 sagt dann "Pike's fax arrived an hour ago". Intern wackelt "Three weeks he's been sitting across from me" (P15) vs. "Six weeks of this" (P17).
- **Fehler (korrigierbar):**
  1. **P5: Wissens-Leak.** Mira sucht "Ashford. Ashford, Ashford" **bevor** Pike den Namen decodiert und ihr durchgibt (Anruf erst P9). Ihr letzter Stand war "Ash—" (ep3) und Surname "Cole" (ep5). Fix: Suchbegriff auf "Ash-" -Fragment + Staff-Roster umstellen.
  2. **P10 on air: "doors closed in nineteen seventy-six"** — kollidiert mit ep1 (Entlassungen bis Okt. 1977, Kapsel 1977, Eleanor vermisst Dez. 1977) und ep7/8 (Ward-Betrieb Okt. 1979).
  3. **P15: "Ethan Warren Cole. Born 1988."** — macht die Ep7/8-Fotobeweis-Logik (Junge 1979 = Ethan) unmöglich; eine der beiden Angaben muss weichen.
  4. P2 "She stops. Rereads." und P4 mehrfach ("He tests the same substitution…", "A long pause. He sits back…", "He says it like a man convincing himself…", "He opens the notebook back…") — **untagged Prosa ohne [NARRATOR]**.
  5. P2 vs. ep2: Aufnahme "March seventh, nineteen seventy-one" vs. ep2 P5 "March the fourth" 1975 — gleiches Datum, anderes Jahr, on air widersprüchlich (Kanon-Fix).

## Episode 7: Digging Ethan

- **Stärken:** Pikes Kassettenrekorder-Monolog (P7: "the kind of quiet you teach a child, not the kind they're born with" / "Erasing this one too.") ist die beste Einzelszene der Staffel. Der 1979-Flashback (P8, Eleanor + junger Pike + der Junge auf der Station) verzahnt drei Threads elegant. Mira als aktive Gegenspielerin (P4/P12: Wexford-Köder auslegen, Pausen "marken") hebt die Staffel-Endphase. Marsh/Mira-Spiegelung (P10: "Different room. Same tone.") stark.
- **Schwächen:** Victors Telefon-Monolog-Format zum x-ten Mal (P11); Pikes einseitige Szene P15 spricht mit unsichtbaren Handlern, die nie etabliert wurden ("You people keep moving me" — wer genau bewegt ihn? Das Team? Dann wäre "the team's handlers" neu). P5/P13 unter Budget.
- **Fehler (korrigierbar):**
  1. **P1-Recap widerspricht dem Ep6-Cliffhanger:** "a **1981** court filing" — Ep6 endete auf dem **1979er** Filing (Ashford→Cole). Programmname im Recap "Project Threshold" vs. Ep6 on air "the Continuity Program".
  2. **P2: "surname … changed from Wexford to Cole, mother's maiden name"** — dritter Direktorname + Cole plötzlich Muttername (ep1: "father's surname, Cole"; ep6: Vater Warren Cole). 
  3. **P14: Payoff ohne Setup.** Mira zählt als bekannt auf: "The burner phone near my building. Calls, always to the same number. And that number called Ethan's phone that same week." — Ein Burner-Fund bei ihrem Gebäude wurde in keiner vorherigen Episode erzählt (nur als objective_fact im Konzept). Fix: Mini-Szene/NARRATOR-Zeile in Ep5/6 nachrüsten oder Zeile streichen.
  4. **P11: "He answers a scheduled call within the hour, every time, for four months"** — vier Monate Kollaboration kollidiert mit dem Erstkontakt in ep4 P17.
  5. P16: `(She holds his eyes a beat too long, weighing…)` und `(Not yet. Not until I know exactly how this plays out…)` als MIRA-Sprechzeilen — **Klammer-Regieanweisungen, die TTS vorliest.**
  6. P2: "what **Danny** flagged this morning" — nie etabliertes Teammitglied (Team besteht hörbar aus Mira, Ethan, Producer/Engineer).

## Episode 8: Live From the Bunker

- **Stärken:** Das Live-Format trägt: Marshs Testimony (P8: "I wanted a microphone, and nobody editing me afterward." / "It was built on her. That's the whole statement.") ist der emotionale Gipfel der Staffel und löst den Bloodline-Thread exakt wie im series_outro versprochen. Die Konfrontation P11/P12 ("Say my name again, so it's on the record") und Ethans Hand am Master-Fader sind großes Soap-Finale-Handwerk. Victors Rückzug (P14: "Dark isn't gone. Dark is just a room nobody's checked yet.") lässt den Campaign-Thread planmäßig offen. Eleanor bekommt mit P5/P13 einen würdigen Abschluss ("I'm leaving this where it will outlast him.").
- **Schwächen:** P9 und P11/P12 doppeln die Konfrontations-Anbahnung; P15/P17 unter Budget. Pike hört im "safe house" Radio, obwohl er in ep7 P15 gerade in ein neues Haus verlegt wurde ("Third address this year") — kosmetisch.
- **Fehler (korrigierbar):**
  1. **P2: Producer-Stimme mit VICTOR_LANE-Tag.** "[VICTOR_LANE | style: distant, filtered through speaker] Confirming Senator Marsh, ETA twenty-two minutes." Hörer hören den Erzfeind als Producer IM Bunker — maximal verwirrend. Fix: NARRATOR-Paraphrase ("A producer's voice confirms…" existiert schon davor — Zeile einfach dem NARRATOR geben).
  2. **Finale-Logik zerrissen — drei unvereinbare Versionen in einer Episode:** (a) P11/P12: Mira konfrontiert Ethan **live on air**, er gesteht ("Yes. … I've known since before we recorded episode one."), verweigert die Sabotage. (b) P15: Security-Log "**Out at 9:52. Before Marsh even finished.**" — die Sendung ging laut P6 erst um **zehn Uhr** live; Ethan kann nicht um 9:52 gegangen sein UND nach Marshs Segment on air gestanden haben. (c) P16: Mira "enthüllt" Marsh und Pike, Ethan sei Wexfords Enkel — **obwohl beide die Live-Konfrontation gehört haben** (Marsh saß im Raum). Fix: Exit-Zeit nach die Konfrontation legen ("Out at 10:47"), P16-Zeilen auf "was ich euch nicht vorher gesagt habe" umstellen.
  3. P2: "(to herself)" / "(quiet, to herself)" als Sprechzeilen; P7 Style-String mit Tippfehler "reading ahead**)**".
  4. P8: Marsh on air: Entlassung "**1981**", Heirat sechs Wochen später — widerspricht ihrer eigenen on air etablierten Familiengeschichte aus ep2/4/6 (1974er Heirat, 1977er Entlassung, 1978er Trust). Für Hörer widerlegt die Zeugin sich selbst.
  5. P11: Ethan: "We covered that in episode two." — der "Director" lief in Episode 3.

---

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend, alle hörbar)

1. **Direktor mit 4 Namen:** Ambrose Faulkner (ep1–2) → Warren Ashcroft (ep3–4) → Reginald Ashford (ep5–6, Vater = Warren Ashford) → Julian Wexford (ep7–8). Der Podcast "nennt" on air nacheinander **Ashford** (ep6 P17) und **Wexford** (ep7–8) als denselben enttarnten Mann — ohne jede Korrektur.
2. **Programmname:** "The Continuity Program" on air enthüllt (ep6 P10) → ab ep7 heißt es kommentarlos "Project Threshold".
3. **Anstaltsname:** "Ridgeline Asylum" (ep1 P5) → "Ashgrove Sanatorium" (ep7–8).
4. **Patientenzahl:** 14 Polaroids als Staffel-Ikone (ep1–2, "Fourteen names. Fourteen photos. One word.") → 41 Namen (ep7–8; Pike: 42).
5. **Marshs Großmutter:** Name (Mei-Ling Chow → Mei-Lin Chao), Aufnahmejahr (1975 → 1971 → "the sixties"), Entlassung (1977 → 1974 → 1981), Heirat (April 1974 → 1981), Geldfluss (Trust Jan/Apr 1978 → Disbursements 1974–85 → Trust "two years later" nach 1981).
6. **Cole-Namenswechsel:** 1979/Ashford→Cole/Petent Vater (ep5–6) vs. sealed 1981/Wexford→Cole/"mother's maiden name" (ep7–8).
7. **Ethans Linie:** mütterlich (ep1 P12, ep3 P5) vs. väterlich (ep5–8).
8. **Ethans Arc:** schockierte Entdeckung + Erstkontakt ep4 vs. "wusste alles seit vor Episode 1, vier Monate vorher rekrutiert" (ep7 P11, ep8 P12 — on air gestanden).
9. **Eleanor-Zeitachse:** aktiv 1975–77, Kapsel 1977, vermisst Dez. 1977 (ep1–2) vs. Flashback 1976 (ep3) vs. Okt. 1979 + "diary sealed in 1979" (ep7–8).
10. **Schließungsjahr:** 1977 (ep1) vs. 1976 (ep6 on air) vs. Betrieb noch Okt. 1979 (ep7–8).
11. **Ethan geb. 1988 (ep6) vs. Junge von 1979 = Ethan (ep7–8)** — arithmetisch unmöglich.
12. **Ep2-intern:** Trust Januar 1978 (P2) vs. 14. März→25. April "six weeks" (P12).
13. **Ep8-intern:** On-air-Konfrontation (P11–12) vs. Exit 9:52 vor Sendebeginn (P15) vs. Mira "enthüllt" das bereits Gesendete (P16).
14. Fallengelassene Beats: idle Auto (ep2-Outro) nie aufgelöst; Deepfake-/Sponsoren-Thread endet nach ep4; "nine days early"-Rätsel (ep3 P7) nie on air beantwortet.

### Wiederholte Phrasen / LLM-Tics (gezählt)

- **"That's not X, that's Y"-Kontrastfigur: 36 Treffer** über 8 Episoden ("That's not a coincidence, that's a plan/design/pattern/decision/message…") — das dominante Rhetorik-Tic, bei fast jeder Figur, dadurch stimmen-nivellierend.
- **"a beat/fraction/shade too …" (Erzähler-Verdachtsmarker): 11×** — ab ep4 vorhersehbares Signal "Ethan lügt gerade".
- **"says/said nothing" als Szenen-Schluss: 25×** — gefühlt endet jede zweite Ethan-Szene mit schweigendem Ethan.
- **"giving nothing away": 13×**, **Style-Wort "measured": 100×**, **"controlled": 59×**, **"guarded": 49×** — die Style-Direktiven kollabieren auf 3–4 Adjektive; für TTS-Ausdruck wäre mehr Varianz nützlich.
- SFX-Monotonie: "chair creaking/scraping/rolling" 26×; Marker-Kappen, "mug set down hard" und "phone buzzing against desk" tragen ganze Episoden.
- "Okay. Okay."-Selbstberuhigung 8× über 4 Figuren (auch Victor-Sphäre), wirkt figurenunspezifisch.

### Thread-Bilanz

- **The Time Capsule (~35 % der Parts):** Gut dosiert, echte Progression (Kapsel → Fenster → Pike → Code → Programmname → Broadcast), löst planmäßig in ep8. Bester Thread — wenn man die Kanon-Drift wegdenkt.
- **The Inside Plant (~30 %):** Leicht überfüttert: der Beat "Ethan lenkt ab / schweigt / atmet auf" läuft in nahezu identischer Form ~8× (ep1 P15, ep2 P1/P10, ep3 P5/P14, ep4 P16, ep5 P7, ep6 P6/P14, ep7 P4/P12). Die Payoffs (ep6 P15, ep8 P11–12) sind stark, aber der Mittelteil tritt auf der Stelle.
- **The Senator's Bloodline (~20 %):** Beste Arc-Ökonomie der Serie: von "Morning, Grandma" (ep2) über Victors Druck (ep4/7) zu Selbst-Testimony (ep8) — jede Szene bewegt die Figur.
- **The Silencing Campaign (~15 %):** Vorne stark (Deepfake, Break-in), verliert ab ep5 seine konkreten Teil-Plots (Deepfake-Forensik, Sponsoren) und schrumpft auf Victor-Monologe; das geplante "left open"-Ende funktioniert trotzdem.
- **Eleanor (Flashback-Ebene):** 1–2 Szenen fast jeder Episode, konstant hohe Qualität; einziges Problem ist die driftende Datierung.

### REVIEW-Abgleich-Ergebnis

Alle 8 `_REVIEW.txt` enthalten wortgleich **"Keine Auffälligkeiten."** Der LLM-Review hat **nichts** gefunden — weder die intra-episodischen Brüche (ep2 Trust-Daten, ep4 Doppel-Statement + Pike im Vault, ep8 Finale-Logik, Sprecher-Fehlbesetzungen) noch (erwartbar, da vermutlich ohne Cross-Episoden-Kontext) die Kanon-Drift. Für diese Serie war das Review-Gate wirkungslos; es gab entsprechend auch nichts "Geflaggtes", dessen Behebung zu prüfen wäre. Empfehlung an die Pipeline: Review-Stufe (a) mit Vorgänger-Skripten oder einem Kanon-Extrakt füttern, (b) explizite Checkliste für Sprecher-Tag-Plausibilität, Klammer-Zeilen und untagged Prosa.

---

## Top-5 konkrete Korrekturen (priorisiert)

1. **Kanon vereinheitlichen (größter Hebel).** Da das Finale (ep7–8) Wexford/Threshold/Ashgrove/41 festschreibt und am schwersten umzubauen ist: ep1–6 auf diesen Kanon patchen. Konkret: ep1 P7 ("Ambrose Faulkner", "slant on the F" → "slant on the W"), ep1 P5 ("Ridgeline"→"Ashgrove"), ep2 P13/ep1 P4 ("Faulkner"→"Wexford"), ep3 P15/P5 ("Warren Ashcroft"/"W.A." → "Julian Wexford"/"J.W."), ep4 P10/P12 ("Ashcroft's estate" → "Wexford-linked trust"), ep5 P6/ep6 P4–15 ("Ashford"→"Wexford", Filing-Jahr einheitlich 1981, Linie einheitlich väterlich mit Cole = Mutter-Mädchenname), ep6 P10 ("Continuity Program" → "Threshold" ODER ep7/8-Recaps auf "Continuity Program"), Zahlen (14 Polaroids beibehalten, "41 discharge records" als Obermenge sauber einführen: "14 Polaroids von 41 Entlassenen" — eine Zeile in ep6/7 genügt), Chao-Daten auf EIN Datenset (Empfehlung: Aufnahme 1971, Entlassung 1974, Trust 1974, da ep4+6 doppelt gesendet), ep6 P15 Geburtsjahr "1988" → "1971" (macht den 1979er-Jungen möglich). Dann `case`-Blöcke in episodes.json einmalig fixieren, damit ein Re-Run nicht erneut driftet.
2. **Ep8-Finale konsistent machen:** P15 Exit-Log "Out at 9:52. Before Marsh even finished." → Zeitpunkt nach der On-Air-Konfrontation ("Out at 10:51. Two minutes after his last word on air."); P16 Miras Enthüllungs-Rede umformulieren zu "what I didn't tell you before the broadcast" (Marsh/Pike haben die Konfrontation gehört); P2 Producer-Zeile vom VICTOR_LANE-Tag auf [NARRATOR] umziehen.
3. **Sprecher-Fehlbesetzungen ep1/ep4 beheben:** ep1 P8 Reporter-Szene auf einseitigen Mira-Dialog umbauen (Muster ep2 P7) oder eigenen Nebenstimmen-Workaround; ep4 P10 die zwei Pike-Zeilen streichen/Ethan geben und P11 "the borrowed nurse" → "the retired records orderly".
4. **TTS-Artefakte bereinigen (mechanisch, risikolos):** Klammer-Zeilen als Sprechtext entfernen — ep3 P10 "(quietly, to himself)", ep4 P15 "(internal, murmured)"/"(to herself)", ep5 P8 "(no line — listening)", ep7 P16 beide Klammer-Zeilen, ep8 P2 "(to herself)"/"(quiet, to herself)" + Tippfehler "reading ahead)"; untagged Prosa mit [NARRATOR] taggen — ep4 P3/P7, ep6 P2/P4 (4 Stellen). Kandidat für einen deterministischen Check in validate_data (Zeile beginnt mit "(" oder Prosa ohne Tag zwischen Dialogzeilen).
5. **Glaubwürdigkeits-Fix ep5 P9 + Setup-Nachrüstung ep7 P14:** Mira darf den Namen "Cole" nicht kommentarlos "nobody I know" nennen — entweder Record maskieren ("C-something, half illegible") oder sie registriert und verwirft ihn aktiv; für ep7 P14 in ep6 eine NARRATOR-Zeile über den Burner-Fund bei Miras Gebäude nachrüsten (oder die Burner-Referenz in ep7 streichen).
