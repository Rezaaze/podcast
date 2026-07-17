# Stage 04 — Visuals

## Inputs
- Layer 4: `../01_concept/output/episodes.json` (Rollen-Biografien,
  `locations`-Mapping)
- Layer 4: `../02_scripts/output/ep*.txt` (welche Emotionen tatsächlich
  vorkommen → Porträt-Varianten)
- Extern: `OPENAI_API_KEY` (optional — ohne Key nur Prompt-Texte)

## Process
Claude formuliert pro Rolle/Ort einen Bild-Prompt; mit API-Key werden die
PNGs direkt via gpt-image-1-mini erzeugt (Porträts hochkant + eine Variante
pro Emotion; Orte 1536x1024 Landscape). Vorhandene PROMPTS.txt wird
wiederverwendet, nur fehlende Bilder werden erzeugt.
Ausgeführt von: `python3 -m fabrik.cli.character_prompts` /
`location_prompts` [--force]

## Outputs
- `output/characters/PROMPTS.txt` + `<ROLE>.png` + `<ROLE>_<emotion>.png`
- `output/locations/PROMPTS.txt` + `<ORT_KEY>.png`

## Review-Gate danach
Bilder sichten; missratene PNGs löschen und Stage erneut laufen lassen
(nur Fehlendes wird regeneriert). Konsumiert von Lolfi beim Video-Rendern
(Porträt-Overlays, Szenen-Hintergründe).
