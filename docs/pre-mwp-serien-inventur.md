# Alt-Serien-Inventur (T0.3, Stand 13.07.2026)

Grundlage für die Verschiebung nach `data/archive/pre_mwp/` in Task T6.2
des MWP-Umbaus (siehe `mwp-umbau-plan.md`). Alle Serien liegen im
**alten Layout** (`episodes.json` + `scripts/` + `output/` direkt im
Serien-Ordner) und werden nach dem harten Umbau vom Code nicht mehr
unterstützt — die Dateien bleiben aber unverändert lesbar/abspielbar.

| Serie | Template/Mode | Episoden | Skript-Dateien | MP3s | Status |
|---|---|---|---|---|---|
| chain_of_custody | soap_opera/drama | 10 | 40 | 10/10 | ✅ fertig gerendert (13.07., keine Checkpoints offen) |
| facades | soap_opera/drama | 10 | 10 | 10/10 | ✅ fertig gerendert |
| vanishing_signal | soap_opera/drama | 10 | 20 | 10/10 | ✅ fertig gerendert |
| dead_reckoning | (kein template-Feld, Altformat) | 3 | 1 | 0 | ⚠️ unfertig — nur 1 Skript, nie vertont |
| tea_house_mysteries | language_course/drama | 2 | 1 | 0 | ⚠️ unfertig — nur 1 Skript, nie vertont |
| facades_speed_test | — | — | — | — | ⚠️ keine episodes.json (Test-Rest, kann weg) |

Hinweise:

- `LATEST` zeigt auf `chain_of_custody`.
- Alle Serien haben `merge_anthology: false` (soap_opera-Standard) — es
  gibt bewusst keine ANTHOLOGY-Dateien; "fertig" = alle Episoden-MP3s
  vorhanden.
- Vor T6.2 (Verschiebung ins Archiv) prüfen: sind die fertigen MP3s
  gesichert/hochgeladen? Lolfi-Videos für chain_of_custody ggf. noch aus
  dem alten Layout rendern, BEVOR Lolfi in Phase 5 auf die neuen Pfade
  umgestellt wird.
