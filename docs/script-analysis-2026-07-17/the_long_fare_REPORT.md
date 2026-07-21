# the_long_fare — Tiefenanalyse

## Serien-Überblick

**Prämisse:** Real-Time-Abduction-Thriller als Soap: Eine Hackerin ("Cipher")
kapert die Limousine, in der Chauffeur Marcus Kane den verletzten CEO Elias
Vance fährt. Beide Männer verbindet — ohne dass sie es voneinander wissen —
der Einsturz des Harrow Warehouse vor zehn Jahren. Parallel jagen
Dispatcherin Delia Reyes und Cyber-Detective Leo Chen das Signal; Nachtwächter
Wei Su hält am Ruinen-Zaun Totenwache für seinen Sohn Danny.

**Threads:** "The Hijacking" (Motor), "The Chase" (Delia/Chen), "The Harrow
Reckoning" (ab Ep3; wird ab Ep6 zum Hauptthread). Auflösung Ep10: Cipher =
Mei Su, Wei Sus Tochter; die Bombe war Druckmittel, sie wählt Veröffentlichung
statt Detonation.

**Gesamturteil: 6/10.** Die Serie ist handwerklich die bisher stärkste im
Dialog (unterscheidbare Figuren, konsequente Parallelmontage, echte
Eskalationslogik, Cipher als herausragende Antagonistin) und hält die
soap_opera-Wissens-Slices szenenweise erstaunlich präzise ein. Was sie
herunterzieht, ist **Konzept-Drift**: Die `case`-Blöcke in episodes.json
wurden pro Episode neu erfunden (Harrow-Solution existiert in 4 Varianten,
Wagen-Nummer in 3, Totenzahl in 2) — und ein Teil dieser Drift ist hörbar
in die Skripte durchgeschlagen, inkl. eines massiven Ep9→Ep10-Bruchs, bei dem
Chen und Delia, die in Ep9 bereits am Zaun stehen, in Ep10 wieder in ihren
Büros sitzen und ein zweites Mal anreisen.

---

## Episode 1: Loss of Control

- **Stärken:** Sauberer Slow-Burn-Einstieg; Marcus' Alltag (Trinkgeld-Witz,
  "Both shoes, Delia") etabliert Figur & Freundschaft ökonomisch. Cipher-Debüt
  (PART 5) ist die beste Szene der Episode: "I have every authorization I
  need, Marcus." Delias Zögern (P6/P11) exakt auf ihrem knows/hides-Slice.
- **Schwächen:** P4 ("The Screens Flicker") ist mit 73 Wörtern ein reiner
  Event-Beat — der Plan gab 130–190 vor, die Szene hat aber inhaltlich nur
  einen Moment (Locks klicken); dünn geplant, nicht nur dünn geschrieben.
  P12 (210 W.) füllt sein Budget nicht, weil der Beat "Annäherung + sofortiger
  Rückzug" nach einer Minute erschöpft ist.
- **Fehler (korrigierbar):**
  1. P12: Marcus erwähnt "I got a kid I don't see enough. … Nine now." —
     Das Kind existiert in keiner Konzept-Figur und wird in Ep2–10 nie wieder
     erwähnt (auch nicht im Aftermath Ep10 P13). Verwaistes Detail → streichen
     oder in Ep10 aufgreifen.
  2. P13: Koordinaten "Forty-one point two-two-eight north, seventy-one point
     four-oh-three west" — Ep2 P1 nimmt denselben Auftrag mit **anderen**
     Koordinaten wieder auf ("Thirty-one point two two four north,
     ninety-four point five seven one west"). Eine der beiden Angaben angleichen.

## Episode 2: The First Delivery

- **Stärken:** Bestechungsszene P6 ("Put your wallet away, Mr. Vance. It's the
  one thing in this car I don't want.") — Case-treu und charakterisierend.
  Chen-Einführung P8/9 inkl. seiner falschen Espionage-Theorie exakt auf
  believes_falsely. Starker Episoden-Schluss (P13: Cipher registriert die
  Beobachter fast anerkennend).
- **Schwächen:** P3 (129 W.) und die Drop-Szenen bleiben abstrakt — "package",
  "note with one word" — die Drops sind als Hörereignisse zu unsinnlich.
- **Fehler (korrigierbar):**
  1. Box-Standort-Flip: P3 Marcus legt das Paket **ins Auto** ("box set down
     inside"), P6-Narrator: "The box from the trunk now rides in the back
     seat", P7-Narrator: "The box now rides in the trunk." — innerhalb einer
     Episode widersprüchlich (und Cipher sagt in P3 "Bring it to me", obwohl
     niemand da ist, dem man es bringen könnte).
  2. Zeit läuft rückwärts: P4 endet bei "Ten minutes" Standzeit, P5 ("a few
     minutes later") beginnt wieder bei "four minutes is not a bathroom break".
  3. P5 nennt die Floor-Managerin "Renata", P11 sagt "floor manager's not
     answering **his** cell" — Genus-/Personenwechsel in derselben Episode.

## Episode 3: What the Trunk Won't Say

- **Stärken:** Wei-Su-Einführung (P2/P3) ist das emotionale Highlight der
  ersten Serienhälfte — Ritual, Memorial, "You didn't fail. Something failed
  you." Sein falscher Verdächtiger Dobrescu (P8) sitzt exakt auf
  believes_falsely. Die Namens-Task (P6) ist als Grausamkeits-Eskalation
  ("nothing but a name") konzeptgetreu und stark.
- **Schwächen:** Ab P4 wiederholen sich die Kabinen-Beats (Elias fragt, Marcus
  blockt) dreimal fast identisch (P4, P10, P12).
- **Fehler (korrigierbar):**
  1. **P6: "Danny. Danny Tran."** — Der tote Lehrling heißt ab Ep4/6/7
     durchgehend Daniel/Danny **Su** (Wei Sus Sohn, Kern der Auflösung!).
     "Tran" macht die spätere Familienlogik (Cipher = Mei Su, Dannys
     Schwester) unmöglich. → "Danny Su" (zwei Stellen: P6 Marcus, P6 Elias).
  2. P3: Wei Su: "Six weeks, for **three men**" — Ep6 sagt dreimal "four"
     (P2 "Four names on the casualty line", P5/P8 "Four men died").
     Eine Zahl festlegen.

## Episode 4: Recognition

- **Stärken:** Die Vorbeifahrt am Harrow-Zaun ist als reine Verhaltens-Szene
  (weiße Knöchel, zu schnelle Antworten) genau die "small tells"-Vorgabe der
  style_guidelines. Wei Sus Kennzeichen-Notiz (P8, "Six-Papa-Three-Five-Nine-
  Charlie") gutes prozedurales Detail; "Daniel would tell me I see ghosts in
  every set of headlights" — beste Zeile der Episode.
- **Schwächen:** P12 lässt den Failsafe-Cliffhanger vom Narrator
  **referieren** statt Cipher ihn sprechen zu lassen — schwächster möglicher
  Akt-Schluss für ein Audio-Format.
- **Fehler (korrigierbar):**
  1. **P9: Elias: "You've been driving me for three years, Marcus."** —
     Direkter Widerspruch zur Ep1-Prämisse (Erstbegegnung: "First time in car
     twelve?", Elias kennt Fahrer-Zuteilung nicht, Cipher hat Marcus namentlich
     angefordert, weil die Paarung konstruiert ist). → z. B. "I've watched
     drivers for thirty years" o. ä.
  2. P3: Elias plaudert unaufgefordert "That's Harrow… We shelved the east
     wing after the accident. I haven't looked at it since the settlement
     closed the file." — Er legt Settlement + Firmenbezug offen, die er laut
     hides-Slice (Angst vor Exposure, Framing als "generic sabotage")
     gerade nicht preisgeben würde; halbe Solution-Leckage an Marcus.

## Episode 5: Uneasy Alliance

- **Stärken:** Die Kooperations-Task (P6, Countdown + Gate) ist die beste
  Thriller-Mechanik der Staffel; "Let's see if hired help and money know how
  to move as one." Ciphers irritierte Reaktion auf die entstehende Allianz
  (P12/P13, "I don't go quiet. I recalculate.") setzt ihr believes_falsely
  ("ein Task zerschlägt die Allianz") hörbar um.
- **Schwächen:** P3 (120 W.) erfüllt zwar den Override, aber Elias' Einlenken
  ("Fine. Your way.") kommt für seinen Stolz eine Spur zu billig.
- **Fehler (korrigierbar):**
  1. P4/P5: **"Vehicle four-one-two"** (zweimal) — die Serie fährt bis Ep3
     "car twelve" und ab Ep7 "car one-fourteen". Drei IDs für dasselbe Auto.
  2. P9: Chen: "Whoever's steering that car built the same tool **I picked up
     last month**." — widerspricht dem objective_fact ("signature never seen
     in prior citywide cases") und Ep6 P1, wo derselbe Fingerprint erst über
     ein **Archiv** von Signaturen gefunden wird, die "predates anything this
     guy's ever done".
  3. P13 (REVIEW-Flag, NICHT behoben): Narrator: "the woman steering them
     toward Harrow" — nimmt das Ziel der Nacht vorweg; zusätzlich verrät die
     Zeile beiläufig Ciphers Geschlecht als Fakt des Erzählers. (Abmildernd:
     Cipher hat Harrow in Ep3 P13 selbst als "next stop" genannt — der
     eigentliche Schaden ist die Erzähler-Autorität "steering all along".)

## Episode 6: The Name Behind the Voice

- **Stärken:** Bester Einzelakt der Staffel: Wei Su vs. Delia (P3–P6) hat
  echte Szenen-Spannung ("I know exactly who you are, Delia Reyes."), und
  Elias' Geständnis (P9, "That was a decision to not know.") ist der
  dramatische Höhepunkt der Serie. Ciphers "There's always more than one
  signature on a bad piece of paper, Marcus" (P12) dreht die Episode im
  letzten Moment perfekt auf den Cliffhanger.
- **Schwächen:** Die zwei einzigen Szenen mit erhöhtem Budget (P5: 304<380,
  P9: 283<380 — Wei Sus Erzählung, Elias' Zusammenbruch) sind just die, die
  der Plan als Set-Pieces auswies. Sie funktionieren, aber sind gegen die
  Planung unterentwickelt — die Wortbudget-Unterschreitung spiegelt hier kein
  dünnes Konzept, sondern zu frühes Abblenden der Kernszenen.
- **Fehler (korrigierbar):**
  1. Staging P5→P6: Wei Su sagt in P5 bereits "**Marcus** called in a favor"
     — Delia reagiert nicht; erst in P6 der Schock "That's Marcus. … That's
     my Marcus." Die Enthüllung ist dadurch entwertet; in P5 den Namen
     vermeiden ("the foreman", "someone on the crew").
  2. P5: "Marcus called in a favor, someone needed to cover" (Schicht-Tausch
     als Todesursache) wird in Marcus' Geständnissen (Ep7 P8, Ep9 P12,
     Ep10 P7) nie wieder erwähnt — hängender Vorwurf, der unaufgelöst bleibt.

## Episode 7: The Confession Nobody Asked For

- **Stärken:** Marcus' Teilgeständnis (P8) ist präzise gebaut — Report +
  Schweigegeld ja, Unterschrift nein — und Ciphers Solo-Szene (P11, erstmals
  außerhalb des Autos: "half a confession dressed up as the whole one")
  liefert die eleganteste Perspektiv-Erweiterung der Staffel inkl. Motiv-Check
  ("mercy, or the other thing"). Wei Sus Telefonszene (P12) hält seine
  Fehldeutung (Reporter/Anwalt) sauber auf believes_falsely.
- **Schwächen:** P4: Chen "sets the phone down without ending the call,
  forgetting it's still connected" — Detail ohne jede Konsequenz. Doppelte
  "Marcus wird auf der Fahrt gefragt und blockt"-Szenen (P5, P7) recyceln
  Ep3/4-Beats wörtlich ("I know every area. It's the job." — 4. Variante
  dieser Zeile in der Serie).
- **Fehler (korrigierbar):**
  1. P1/P10: "car number one one four" / "car one-fourteen" — dritte
     Wagen-ID (s. Ep5). Eine ID serienweit wählen (Empfehlung: 12, da in
     Ep1–3 gesprochen und in Delias Dialog verankert).

## Episode 8: Countdown to Harrow

- **Stärken:** Trunk-Reveal (P2) als reines Audio-Ereignis stark gelöst
  (Verkabelung statt Anblick). Elias' Truce-Bruch (P3/P8: der versteckte
  Panik-Knopf, "Full mobilization") setzt sein hides um und Ciphers trockenes
  "Outbound transmission detected. Noted." ist die beste Machtdemonstration
  der Episode. Wei Sus "Kane."-Moment (P10) baut den Badge-Fakt exakt um.
- **Schwächen:** Chen/Delia-Zusammenführung (P9) geht auffällig glatt — keine
  Reibung zwischen Cop und Zivilistin, sie folgt ihm einfach ("Stay behind
  me"). Das rächt sich in Ep10 (s. u.).
- **Fehler (korrigierbar):**
  1. P4: Chen liest "Leased under 'M. Sutton'" vom Mietvertrag der Unit ab,
     nachdem er das Kennzeichen eines davorstehenden Sedans "runnen" wollte —
     die Beweiskette (Plate → Leasing-Alias) ist logisch verrutscht;
     eine Zeile Aufräumarbeit.

## Episode 9: The Warehouse Floor

- **Stärken:** Der Osei-Twist (P5: eine **zweite** begrabene Warnung) ist
  der beste Reveal der Staffel, weil er Marcus' Schuld-Arithmetik live
  umrechnet ("There was another man standing where I was standing."). Die
  Brief-Verbrennungs-Szene (P6/P7) verzahnt Konzept-Fakten (anonymes Geld,
  ungeöffnet verbrannt) mit Wei Sus Erkenntnis fehlerfrei über drei Figuren.
  Marcus' Geständnis an Wei Su (P12) ist das emotionale Ziel der Serie und
  trägt.
- **Schwächen:** Sehr viel Stehen-und-Reden bei laufendem Countdown — die
  Bombe verliert über 13 Parts an Glaubwürdigkeit als Bedrohung. P8 (94 W.)
  ist ein Übergangs-Beat, dessen Budget-Unterschreitung folgerichtig ist
  (Override 110 verlangt, Szene hat einen einzigen Beat: niemand weicht zurück).
- **Fehler (korrigierbar):**
  1. **P1 Recap: "the man on the dashboard"** — Cipher ist seit Ep1 hörbar
     eine Frau und wird überall "she" genannt. → "the voice on the dashboard".
  2. **P4: Regieanweisungen als Sprechertext** — drei Zeilen, die der
     TTS-Sprecher als Dialog vorlesen würde:
     `[MARCUS_KANE | …] Marcus watches the way she settles her weight…`,
     `[MARCUS_KANE | …] Marcus looks at Elias.`,
     `[ELIAS_VANCE | …] Elias looks back.` → in NARRATOR-Zeilen umwandeln.
  3. P13: `[WEI_SU | style: quiet, unreadable] ...` — Sprecherzeile, deren
     Text nur "..." ist (TTS-Artefakt); ebenso Ep10 P7 (WEI_SU "…") und
     Ep10 P8 (CIPHER "…"). → streichen, Stille dem Narrator/SFX überlassen.

## Episode 10: The Last Fare

- **Stärken:** Die Auflösung selbst ist sauber und bewegend: Wei Sus
  Stimm-Erkennung über die Geburtstagsaufnahme (P3), "Ba— / Don't. Not yet."
  (P8), "You hoped. / I raised you." (P11). Der Verzicht auf Detonation ist
  konzeptgetreu motiviert (Vaterfrage als Wendepunkt). Aftermath P13 (435 W.,
  im Override-Budget) beantwortet bewusst nichts — genau die series_outro-
  Vorgabe.
- **Schwächen:** Marcus' drittes Geständnis (P4/P7: gefälschte Zertifizierung
  Nr. 4417, Schwester-Motiv) übertrumpft die "whole truth" aus Ep9 P12 —
  als geplante letzte Schale funktioniert es, aber dass Marcus in Ep9 vor
  Wei Su ausdrücklich "That's the whole truth" sagt, macht ihn rückwirkend
  zum Lügner in seiner Läuterungsszene. Eine Zeile in Ep9 relativieren.
- **Fehler (korrigierbar):**
  1. **P5/P6/P10: Chase-Reset.** In Ep8 P9 fahren Chen und Delia gemeinsam
     Richtung Harrow, in Ep9 P10/P13 stehen sie bereits am Zaun und
     beobachten die Gruppe. Ep10 P5 setzt Chen zurück ins Bureau ("Eleven
     minutes. Let's make it eight." + Konvoi-Mobilisierung), Ep10 P6 setzt
     Delia zurück an ihren Dispatch-Platz ("I can be there in twelve"), und
     P10 lässt beide ein **zweites Mal** eintreffen. Größter hörbarer
     Kontinuitätsbruch der Serie — Ursache: die Ep10-Sections im Konzept
     ("Trace Complete", "Breaking Protocol") wurden geschrieben, als wäre
     der Chase-Stand von Ep8/9 nicht passiert, und das Skript folgte dem
     Konzept statt den Vorgänger-Skripten.
  2. P12: Delia reagiert auf "foreman… signed something. Harrow." als
     Neuigkeit — sie kennt Marcus' Namen auf dem Sign-off seit Ep6 P6
     (Wei Sus Ordner) und das versiegelte Settlement seit Ep7 P3 (Personnel
     File). Ihr Schock müsste "Bestätigung", nicht "Entdeckung" spielen.

---

## Serienweite Muster

### Kontinuitätsfehler-Liste (episodenübergreifend)

1. **Chase-Reset Ep9→Ep10** (Chen & Delia am Zaun → wieder in Büros → zweite
   Anreise). Schwerster Fehler der Serie.
2. **Wagen-ID:** "car twelve" (Ep1–3) → "vehicle four-one-two" (Ep5, 2×) →
   "car one-fourteen" (Ep7 2×, Ep8, Ep9).
3. **Opfername:** "Danny Tran" (Ep3 P6, 2×) vs. "Daniel/Danny Su" (Ep4, Ep6,
   Ep7, Auflösungs-relevant).
4. **Totenzahl:** "three men" (Ep3) vs. "four names/four men" (Ep6, 3×).
5. **"Driving me for three years"** (Ep4 P9) vs. Erstbegegnungs-Prämisse (Ep1).
6. **Koordinaten** des ersten Fernziels wechseln zwischen Ep1 P13 und Ep2 P1.
7. **Chens Vorwissen:** Ep5 "same tool I picked up last month" vs. Ep6
   "Archiv-Fund, predates anything".
8. **Delias Wissensstand** in Ep10 P12 ignoriert Ep6/Ep7 (Ordner, sealed file).
9. Klein: Floor-Manager "Renata"/„his cell" (Ep2 intern); Marcus' Kind
   (Ep1) verwaist; Wei Sus Kontakt "You worked that inspection with me"
   (Ep7 P12) passt nur halb zum Wächter-Profil.

*Wurzelursache:* Die `case`-Blöcke in episodes.json ändern Solution und
objective_facts pro Episode (Harrow-Backstory in 4 Varianten: Memo/Schicht-
Tausch → Payoff/Falsch-Signatur → Report/NDA → Falsch-Zertifikat/Schwester;
Hijack-Backdoor: "3 Tage alt" → "am selben Abend" → "4 Monate" → "Monate,
als Contractor"). Die Skripte haben das meiste erstaunlich gut zu einer
Schichten-Wahrheit verschmolzen (Report UND Unterschrift), aber Zahl-, Namen-
und Positions-Drift ging durch.

### Wiederholte Phrasen / LLM-Tics (Zählung über 10 Episoden)

- **"ten years"**: 75 Vorkommen (Spitzen: Ep9 19×, Ep6/Ep10 je 12×) — als
  Motiv gewollt, als Frequenz betäubend; in Ep9 fällt es teils dreimal pro Part.
- **"That's not an answer"**: 10× über 8 Episoden, oft gefolgt von der
  Zwillingsfloskel **"It's the only one you get/I've got"** (5×).
- **"I know every street/area/stretch of road … it's the job / comes with
  the job"**: 4× nahezu wortgleich (Ep1, Ep3, Ep4, Ep7) als Marcus-Deflection.
- **Style-Tag "barely audible"**: 57× — jede zweite Szene endet mit einer
  kaum hörbaren Selbst-Murmel-Zeile; als TTS-Anweisung zudem riskant leise.
- **"like a third passenger"** (Metapher): 2× (Ep4, Ep7).
- Konfessions-Formel **"I've never said that/this out loud (to another living
  person)"**: 6× über Elias und Marcus verteilt — nutzt sich bis Ep10 ab.
- Szenen-Schablone "Beide Männer schweigen / filen es weg / fragen nicht":
  in Ep2–4 mindestens 6 nahezu identische Part-Enden.

### Thread-Bilanz

- **The Hijacking:** dominiert Ep1–5 (gut so), löst in Ep10 sauber auf.
  Kleine Schwäche: Die Drops (Paket, Notiz "Foundation", Cross & Tull) werden
  nie rückwirkend erklärt — das "jeder Stopp = Vance-Subunternehmer"-Muster
  bleibt Behauptung.
- **The Chase:** konstant bedient (Delia in jeder Episode, Chen ab Ep2), gute
  Eigenmotivation (Delias Loyalität vs. Protokoll ist die heimliche zweite
  Soap-Beziehung). Endet wegen des Ep10-Resets unter Wert.
- **The Harrow Reckoning:** ab Ep3 eingeführt, trägt Ep6–10; Wei Su bekommt
  überdurchschnittlich viel und verdiente Sendezeit. Kein Thread verhungert;
  eher übersättigt: die immergleiche Kabinen-Verhör-Szene (Elias sondiert,
  Marcus blockt) frisst in Ep2–4 Sendezeit, die den Drops/der Außenwelt fehlt.

### REVIEW-Abgleich

9 von 10 Reviews melden "Keine Auffälligkeiten" — angesichts der oben
gelisteten Fehler (Danny Tran, three years, Chase-Reset, Narration-in-
Speaker-Zeilen) ist das Review-Gate für **episodenübergreifende** Kontinuität
blind (es prüft offenbar nur die Einzel-Episode gegen ihr eigenes Konzept).
Der einzige Flag (Ep5 P13, Harrow-Vorwegnahme durch den Narrator) ist im
ausgelieferten Skript **unverändert enthalten** → Review-Befunde wurden
nicht in einen Fix-Loop zurückgespielt.

### Einordnung der deterministischen Befunde

- **66 SFX-Befunde:** Fast alle sind "…, then silence" / "a held breath" /
  "tension held"-Cues — Ciphers Pausen-Dramaturgie als Sound-Cue notiert.
  Serie entstand vor der Template-Regel "nur physisch Hörbares" (14./15.07.);
  ein Re-Run würde die Klasse komplett beseitigen. Inhaltlich sind die Cues
  nicht falsch gedacht, nur nicht renderbar.
- **25 Wortbudget-Befunde:** Drei Muster. (a) Event-Beats, deren Plan-Budget
  zu hoch war (Ep1 P4: Locks-Klick als 130-Wort-Szene angelegt; Ep9 P8:
  "niemand weicht" als Einzel-Beat). (b) Zwei-Männer-Kabinen-Szenen, deren
  einziger Inhalt "Frage → Deflection" ist und die deshalb bei ~210–225
  Wörtern natürlich enden (Mehrzahl der Fälle, Ep2/4/7/8) — hier ist die
  Szenen-Planung dünn, nicht die Prosa faul. (c) Am gravierendsten Ep6 P5/P9:
  die beiden einzigen bewusst groß budgetierten Set-Pieces (380–580) wurden
  um 20–25 % unterschrieben — genau dort hätte Material existiert.

---

## Top-5 konkrete Korrekturen (priorisiert)

1. **Ep10 Chase-Reset beheben** (P5, P6, P10): Chen-Szene von "Bureau
   mobilisiert Konvoi" auf "Chen am Zaun ruft Verstärkung, die eintrifft"
   umschreiben; Delia-Szene P6 streichen oder als Rückblende/Funkspruch an
   ihren Supervisor rahmen; P10 als Eintreffen der **Verstärkung** statt der
   beiden spielen. (Hand-Edit der drei Parts; Rest der Episode bleibt intakt.)
2. **Ep3 P6: "Danny Tran" → "Danny Su"** (2 Zeilen) und Totenzahl
   vereinheitlichen (Ep3 P3 "three" vs. Ep6 "four" — Empfehlung: vier, da
   dreifach in Ep6 verankert). Minuten-Fix, rettet die zentrale
   Familien-Auflösung.
3. **Ep9 TTS-Bugs:** P1 "the man on the dashboard" → "the voice"; P4 drei
   Narrations-Zeilen aus MARCUS/ELIAS-Tags in NARRATOR umhängen; "..."- 
   Sprecherzeilen (Ep9 P13, Ep10 P7/P8) entfernen. Direkt hörbare Fehler,
   trivial zu fixen.
4. **Wagen-ID vereinheitlichen** auf "car twelve" (Ep5 P4/P5 2×, Ep7 P1/P10,
   Ep8 P1, Ep9 P10 ersetzen) und **Ep4 P9 "three years"** auf eine Formulierung
   ohne gemeinsame Vorgeschichte ändern.
5. **Pipeline-Lehre:** (a) `case`-Blöcke beim create_series einfrieren oder
   per Diff-Check gegen Vorepisoden validieren (Solution-Drift war hier die
   Wurzel fast aller Kontinuitätsfehler); (b) Review-Gate um einen
   Cross-Episoden-Pass ergänzen (Recap/Skript N gegen Skript N-1) und Flags
   in einen Fix-Loop zurückspielen — der einzige echte Ep5-Flag blieb unbehoben.
