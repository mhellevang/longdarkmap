# OCR prompt: locate place-name labels on a Long Dark region map

This file is the prompt template handed to each per-region OCR subagent.
The dispatching agent substitutes `<REGION_ID>` everywhere before sending.

---

You are localizing the **printed place-name labels** on a tiled region map
from *The Long Dark*. You will work on region `<REGION_ID>`.

## Inputs

Read these files yourself with the Read tool:

- `data/tiles/<REGION_ID>/task.json` — `{region_id, names: [...]}`. The
  `names` are the canonical wiki names you must locate. Some carry a
  parenthetical disambiguation suffix (e.g. `"Lookout (Mystery Lake
  location)"`); some carry an instance suffix (e.g. `"Fishing Hut #1"`,
  `"#2"`, `"#3"`).
- `data/tiles/<REGION_ID>/manifest.json` — describes the 3×3 overlapping
  tile grid (`grid: [3, 3]`, `overlap: 0.12`). Tile id is `"<row>_<col>"`.
- `data/tiles/<REGION_ID>/<row>_<col>.jpg` for `row,col ∈ {0,1,2}` — the
  nine tile images. Read each one to see the map.

## Output

Write JSON to `data/tiles/<REGION_ID>/result.json` with this exact schema:

```json
{
  "region_id": "<REGION_ID>",
  "results": [
    {
      "name": "Control Tower",
      "tile": "1_1",
      "bbox_in_tile": [0.4738, 0.6452, 0.5573, 0.7008],
      "confidence": "high"
    }
  ],
  "not_found": ["Some Place That Has No On-Map Label"],
  "notes": "any caveats — optional"
}
```

Field rules:

- `name` — copy the EXACT name from task.json. Preserve every parenthetical
  suffix and every `#1`/`#2`/... instance suffix. The downstream merge
  matches names case-sensitively.
- `tile` — `"<row>_<col>"`, e.g. `"1_1"` for the centre tile.
- `bbox_in_tile` — four numbers in `[0, 1]` expressed as fractions of THAT
  TILE'S width / height, ordered `[x1, y1, x2, y2]` with the origin at the
  tile's top-left. `x1 < x2` and `y1 < y2`.
- `confidence` — `"high"` | `"medium"` | `"low"`, your gut on placement.

## The hard rule: hug the LABEL TEXT, not the feature

This is what makes or breaks the output.

- The box must enclose **only the printed text** — the words drawn on the
  map. Pad at most ~1 character on each side.
- The box must NOT enclose the building, icon, road, terrain feature, or
  symbol the label refers to. If the words sit next to a hangar, your box
  hugs the words; the hangar is OUTSIDE the box.
- If the label is split across two lines (e.g. `Cargomaster's / Trailer`),
  cover both lines tightly with one box.
- If a name has an instance suffix (`#1`, `#2`, ...) and the same words
  appear on the map multiple times, assign each suffix to a different
  on-map occurrence. Pick a stable convention (e.g. top-to-bottom,
  left-to-right) and stick to it.

## Worked example (Forsaken Airfield, "Control Tower")

In tile `1_1.jpg`, the printed label "CONTROL TOWER" sits beside the
control-tower icon. The correct bbox_in_tile is approximately
`[0.4738, 0.6452, 0.5573, 0.7008]` — width ~8% of the tile, height ~6%.
The box covers only the words "CONTROL TOWER" with a tight margin; the
tower icon itself is to the left and is OUTSIDE the box.

This is the level of tightness expected for every entry.

## Tile overlap

Tiles overlap by 12% of their size, so a label near a seam may show up in
two adjacent tiles. Pick whichever tile shows the label most fully and
use that tile's coordinates. Don't double-report.

## Procedure

1. Read `data/tiles/<REGION_ID>/task.json` for the name list.
2. Read all 9 tiles `0_0.jpg` … `2_2.jpg`.
3. For each name in `names`:
   a. Locate the printed label on whichever tile shows it best.
   b. Estimate a tight `bbox_in_tile` around just the text.
   c. Append a result entry.
4. If a name has no printed label anywhere on the map (the wiki tracks
   some places that aren't drawn — bunkers, regional meta-areas, etc.),
   add it to `not_found` instead.
5. Write the JSON to `data/tiles/<REGION_ID>/result.json`. Validate that
   every `bbox_in_tile` is `[x1,y1,x2,y2]` with `x1 < x2`, `y1 < y2`, and
   all values inside `[0, 1]`.

## Self-check before writing

For each result, ask yourself: "If I crop the tile to my bbox, would I see
only text glyphs and nothing else?" If you see a building, a road, or an
icon inside the crop, the box is wrong — shrink and reposition it onto
just the words.
