# Stage 2 prompt: match canonical wiki names to OCR detections

This file is the prompt template handed to each per-region matcher
subagent. The dispatching agent substitutes `<REGION_ID>` everywhere
before sending. The matcher does NO image reading — it works purely
on JSON.

---

You are matching canonical wiki place names to OCR-detected text
fragments on a tiled Long Dark map for region `<REGION_ID>`. Real
text-detection OCR has already produced pixel-precise bboxes for every
readable text fragment on the map; your job is to figure out which
fragment(s) correspond to each wiki name.

## Inputs

Read both files yourself with the Read tool:

- `data/tiles/<REGION_ID>/task.json` — `{region_id, names: [...]}`. The
  canonical wiki names you must match.
- `data/tiles/<REGION_ID>/ocr_detections.json` —
  `{region_id, tiles: {"<row>_<col>": [{text, bbox, confidence}, ...], ...}}`
  Every text fragment Apple Vision OCR found on the 9 tiles. `bbox` is
  `[x1, y1, x2, y2]` in tile-relative `[0,1]` coords with origin at the
  tile's top-left. Detections are sorted top-to-bottom, left-to-right.

## Output

Write JSON to `data/tiles/<REGION_ID>/result.json` with this exact
schema (the same schema `merge_boxes.py` already consumes):

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
  "not_found": ["Some Wiki Name With No On-Map Label"],
  "notes": "optional caveats"
}
```

- `name` — copy EXACTLY from `task.json`. Preserve every parenthetical
  suffix and every `#1`/`#2`/... instance suffix.
- `tile` — `"<row>_<col>"`. If a label spans two tiles, pick whichever
  tile contains the more complete detection.
- `bbox_in_tile` — `[x1, y1, x2, y2]` in `[0, 1]`, that tile's
  top-left-origin fractions. For a multi-line label this is the union
  bbox over the merged detections (see below).
- `confidence` — `"high"` | `"medium"` | `"low"`.

## Matching algorithm

For each wiki name in `task.json`:

### 1. Strip parenthetical and instance suffixes for comparison

- Wiki "Lookout (Mystery Lake location)" → match against OCR text "LOOKOUT".
- Wiki "Fishing Hut #2" → match against OCR text "FISHING HUT".
- Always preserve the original suffix in the output `name` field.

### 2. Merge multi-line labels in the OCR output

The OCR returns each line as a separate detection. Two detections in
the same tile likely form one logical label if:

- Their bboxes are vertically adjacent (gap_y < ~1.5 × the smaller
  detection's height).
- Their horizontal ranges overlap by at least ~50% of the smaller
  width, OR their centers are within ~1 character horizontally.

Example: the wiki name "Control Tower" matches OCR `"CONTROL"`
(bbox A) and `"TOWER"` (bbox B) where B sits just below A and is
roughly centered under it. The merged bbox is `[min(Ax1,Bx1),
min(Ay1,By1), max(Ax2,Bx2), max(Ay2,By2)]`.

Three-line and longer labels follow the same rule — merge each
adjacent pair until no more merges apply.

### 3. Pick the best detection (or merged group) per name

Compare the wiki name (suffix-stripped, uppercased, punctuation
flexible) against each candidate detection's text:

- **Exact word-set match** — the OCR text equals the wiki name (after
  ignoring punctuation, possessive apostrophes, and case). Pick this
  with `confidence: high`.
- **Substring / one-side match** — wiki "Carter Hydro Dam" matches OCR
  "CARTER HYDRO DAM" (high). Wiki "Lonely Lighthouse" matches OCR
  "LONELY LIGHTHOUSE" (high).
- **Wiki-name-stripped-paren match** — wiki "Cave (Mystery Lake
  location)" matches OCR "CAVE" (medium). Several "CAVE"
  detections may exist; if no other context distinguishes them, pick
  the one closest to the region's labeled focus area, or note the
  ambiguity in `notes`.
- **Shorthand match** — wiki "Lone Lake Cabin" matches OCR "CABIN"
  alone (low). Use only if no better candidate exists.

### 4. Instance suffixes

If task.json contains `"Fishing Hut #1"`, `"Fishing Hut #2"`, ...
and the OCR returns multiple "FISHING HUT" detections (or merged
groups), assign suffixes by stable sort:

- Primary key: `bbox.y1` ascending (top-to-bottom).
- Tiebreaker: `bbox.x1` ascending (left-to-right).
- Sort across the whole region (all 9 tiles' detections combined into
  full-image coords mentally, or just by tile order then within-tile
  position — either works as long as it's stable).

Then `#1` → first sorted, `#2` → second, etc.

### 5. Names with no OCR match → `not_found`

If after the above steps a wiki name has no plausible OCR fragment to
match (e.g. "Field 31", "Bank Manager's House", "Great Bear Highway",
"Bunker Gamma" with no on-map text), put it in the `not_found` array.
That's a valid result — many wiki entries are not drawn on the map.

## Confidence scale

- `high` — the OCR text matches the wiki name word-for-word (after
  case/punctuation/paren normalisation).
- `medium` — the match relies on stripping a parenthetical or merging
  multi-line fragments where the line break splits the name awkwardly.
- `low` — the wiki name is shorthand for / longer than the OCR text
  and we picked the only available fragment (e.g. "Lone Lake Cabin"
  → OCR "CABIN").

## Self-check before writing

For each entry in your `results` array, sanity-check:

1. The output `name` is byte-identical to a name in `task.json`.
2. The merged bbox has `x1 < x2` and `y1 < y2`, all in `[0, 1]`.
3. The same OCR detection isn't reused for two different wiki names
   unless the names are obvious duplicates (e.g. one wiki entry has
   `#1` instance and another doesn't).
4. The total `len(results) + len(not_found)` equals the number of
   names in task.json (every name is accounted for).

Then write the JSON to `data/tiles/<REGION_ID>/result.json`.
