# The Long Dark — Interactive Map

A no-build, offline-friendly interactive map for *The Long Dark*. The world view shows Great Bear Island with clickable region labels; clicking a region opens a zoomable, pannable detail map. Static files only — `index.html` + `styles.css` + `src/logic.js` + the bundled map images, no toolchain, no runtime server.

**▶ Live demo: https://mhellevang.github.io/longdarkmap/**

## Usage

Open the [live demo](https://mhellevang.github.io/longdarkmap/), or clone the repo and open `index.html` in any modern browser. No build step, no server required.

- **Click** a region label to open its detail map
- **Scroll** to zoom, **drag** to pan, **double-click** to reset
- **+ / − / ⊡** zoom controls in the bottom-right of the detail view
- **D** (dev server only) toggles a coordinate overlay: `[x%, y%]` of the world map on the world view, `[x, y]` as 0..1 of the region map on the detail view. The key is a no-op when the page is opened directly or from the public deploy. In the detail view with D on:
  - Every stored bounding box for the region is drawn as a labelled blue rectangle, so misplaced ones jump out.
  - **Click any box** (including the search highlight) to grab it for editing.
  - **Shift-drag** to draw a fresh bounding box.
  - In editing mode, **drag the body** to move and **drag the corner handles** to resize. Click **Save** to persist (requires the dev server, see below) or **Cancel** to dismiss.

## Place search

The world view has a search box for finding any named location across all regions.

- Type to filter — e.g. `carter` matches *Carter Hydro Dam* in Mystery Lake
- Press **/** anywhere on the world view to focus the search
- **↑ / ↓** to navigate results, **Enter** to open, **Esc** to clear / blur
- Each result shows the location name and the region it belongs to; clicking opens that region's detail map and **highlights** the matching label: the view zooms in on the box, briefly dims the rest of the map, and leaves a glowing outline around the label

The index (~355 named locations) plus per-label bounding boxes are bundled into `index.html` so search and highlighting work fully offline, including from a static deploy.

### Crafting-tool keywords

The search also recognises crafting-tool keywords:

- `forge`, `arrowheads`, `smithing` → the 6 in-game forges
- `workbench`, `wb`, `crafting` → the 42 wiki-tagged workbenches
- `ammo`, `ammunition`, `reloading` → the ammunition workbench at Last Resort Cannery

Each result row shows a small badge for the tools at that place (F/W/A). Opening a tool result accents the matching badges in the detail view and dims the rest, so you can see at a glance "I'm at Field 31, and there are two more forges (Hangar Basement, Main Hangar) here too." Deep links carry the filter — share a URL like `index.html#forsaken_airfield/Field%2031/forge` and the filter activates on load.

The tool data is scraped from the Long Dark wiki's structured categories ([Locations with a forge](https://thelongdark.fandom.com/wiki/Category:Locations_with_a_forge), [Locations with a workbench](https://thelongdark.fandom.com/wiki/Category:Locations_with_a_workbench)) by `tools/scrape_tools.py`, layered with:

- manual entries from `data/crafting_tools_extra.json` for tools the wiki doesn't categorise (e.g. the ammunition workbench at Last Resort Cannery), and
- vision-LLM amenity passes (per region, optional) that pick up amenities printed only as map pictograms — bed, stove, first-aid kit, ice fishing hut. These layer on top of the wiki tags and never remove them.

Output: `data/crafting_tools.json` plus an inlined `PLACE_TOOLS` block in `index.html`.

### Vision-LLM amenity pass (per region)

```sh
.venv/bin/python tools/amenity_prep.py coastal_highway   # crops + task.json + legend.jpg
# Then in Claude Code, dispatch one vision subagent per region using
# tools/amenity_prompt.md as the prompt template. Each subagent reads
# data/tiles/<region>/amenities/ and writes result.json there.
python3 tools/scrape_tools.py --inline                   # merges all result.json files
```

The prep step (`amenity_prep.py`) crops each `PLACE_BOXES` entry from the region's standard map with generous padding (the icons sit *next to* the place's label, not on top), saves them under `data/tiles/<region>/amenities/<slug>.jpg`, plus a `legend.jpg` strip from the bottom of the map and a `task.json` listing the canonical tag set the subagent is allowed to emit.

The subagent prompt (`amenity_prompt.md`) constrains the output to a fixed canonical-tag set — `forge`, `workbench`, `ammunition_workbench`, `milling_machine`, `bed`, `stove`, `first_aid`, `ice_fishing_hut`, `ice_fishing_hole` — and instructs the agent to ignore loot icons, animal areas, foraging markers, and DLC trinkets, since those are visible on the map already. False positives are worse than false negatives: the wiki layer authoritatively covers `forge` and `workbench`.

Recall is uneven by map style: regions where amenities cluster in styled "info chips" next to each label (e.g. Quonset Garage in Coastal Highway) come back well-tagged; regions where amenity icons are drawn at their actual workshop building inside a building cluster (e.g. Coastal Townsite) often produce empty crops because the icon is outside the label-centred crop window. The wiki layer is what catches those.

### Nearest-tool lookup

Every region in `data/regions.json` carries an `adjacencies` field — a list of region IDs reachable via in-game transition zones, seeded from the Long Dark wiki's `connections` infobox field. The detail view shows a small pill row in its header for each rare crafting tool (forge, workbench, ammunition workbench, milling machine):

- If the open region has the tool, the pill shows the count and a `here` accent. Click it to jump to the first instance with the tool filter active.
- If not, the pill shows the closest place that does, with the hop count via BFS over the adjacency graph (e.g. *"Forge → The Riken (Desolation Point) · 1 hop"* from Coastal Highway). Click to navigate.

The graph is undirected and seeded once. To regenerate after wiki changes, run `python3 tools/scrape_connections.py` to dump each region's parsed connections to `data/regions_connections_raw.json`; the symmetric union is hand-merged into `data/regions.json` and re-inlined via `python3 tools/inline_regions.py`.

## Refreshing the region maps

The map images live in `maps/` and are committed to the repo so the site works as a static deploy (e.g. GitHub Pages). To pull the latest versions from the source guide, run:

```sh
python3 tools/download_maps.py
```

The script fetches both difficulty variants for each region into `maps/` and skips files that already exist. No third-party dependencies, just the Python standard library.

## Refreshing the place index

To re-scrape the location list from the Long Dark wiki:

```sh
python3 tools/scrape_places.py            # writes data/places_index.json
python3 tools/scrape_places.py --inline   # also bundles the result into index.html
```

The scraper hits the Fandom MediaWiki API for each region's `Category:Locations_in_<Region>` page. Use `--inline` after the scrape to bake the new index into `index.html` between the `PLACES_INDEX_START` / `PLACES_INDEX_END` sentinels — that's what the runtime search reads. Stdlib only.

## Refreshing the place boxes

Each named location has a bounding box on its region map so search-result clicks can frame the right label. The boxes come from a two-stage pipeline:

1. **OCR**: Apple Vision (`ocrmac`) reads each tile locally and emits pixel-precise bboxes for every text fragment it detects.
2. **Matcher**: one Claude Haiku subagent per region maps the OCR text to canonical wiki names — handling parenthetical suffixes, `#1`/`#2` instance suffixes, multi-line label merging, and ambiguous shorthand.

```sh
python3 tools/build_tiles.py            # split each map into a 3×3 overlapping tile grid
python3 tools/scrape_places.py          # writes places_index.json AND task.json per region
.venv/bin/python tools/ocr_run.py       # Stage 1: ocrmac → data/tiles/<region>/ocr_detections.json
# Stage 2: in Claude Code, dispatch one Haiku matcher subagent per region
# pointed at data/tiles/<region>/, using the prompt template at tools/match_prompt.md
python3 tools/merge_boxes.py --inline   # merge results + overrides, write data/place_boxes.json,
                                        # and inline into index.html
```

Stage 1 is deterministic and free (Apple Vision runs on-device). Stage 2 is pure text-to-text matching with no image reads, so Haiku is plenty and the cost is negligible. (An earlier vision-LLM-only flow couldn't produce pixel-tight bboxes; switching to real OCR fixed that fundamentally — git history has the deprecated prompt template if you ever want to compare.)

The merge script writes both `data/place_boxes.json` and refreshes the `PLACE_BOXES_START` / `PLACE_BOXES_END` block in `index.html`. Coordinates are stored as `[x1, y1, x2, y2]` fractions (0..1) of the region's full map image.

### Fixing misplaced boxes from the browser

```sh
node dev-server.js   # http://127.0.0.1:8765/  (no npm install — stdlib only)
```

Press **D** in any region to overlay every stored bounding box at once, each labelled with its place name, so the wrong ones are obvious without searching them up one by one. Then either:
- **Click any box** (or the brighter search highlight) to grab it. Drag the body to move, drag corner handles to resize.
- **Shift-drag** anywhere to draw a fresh bounding box from scratch.

Click **Save** when the box looks right. The server writes the new bbox into `data/place_boxes_overrides.json` and re-runs `merge_boxes.py --inline` so `data/place_boxes.json` and the inlined `PLACE_BOXES` in `index.html` both reflect the change immediately. The page also updates its in-memory `PLACE_BOXES` so the highlight snaps to the new position without a reload.

The overrides file is the source of manual fixes; running `merge_boxes.py` on its own re-derives `data/place_boxes.json` from the OCR results in `data/tiles/` and layers overrides on top, so re-running the OCR pipeline never destroys hand-tuned boxes.

## Tests

```sh
npm install   # one-time; installs jsdom (the only dev dep)
npm test      # runs the full suite (~1s, ~50 tests)
```

Two layers, both running on Node's built-in `node:test`:

- **Unit tests** (`tests/logic.test.js`) cover the pure helpers extracted into `src/logic.js`: search ranking, tool-keyword synonym expansion, BFS region pathfinding (`findNearestTool` + tie-breaks), and the hash-routing format.
- **DOM tests** (`tests/dom.test.js`) boot `index.html` into jsdom via `tests/harness.js` and drive it: typing into the search box, ↑/↓/Enter/Esc keyboard nav, tool-badge accents, hash deep-links opening the right region, and region-button clicks.

`src/logic.js` dual-exports — it attaches `window.LDLogic` in the browser and `module.exports = LDLogic` in Node — so the same code is exercised in both environments. The inline `<script>` in `index.html` uses thin wrappers that pass the bundled data tables (`PLACES_INDEX`, `PLACE_TOOLS`, `REGIONS`, `REGIONS_BY_ID`) into those helpers.

The DOM harness stubs all subresources except `src/logic.js` (served from disk), so tests don't depend on map images or CSS being fetchable. Pan/zoom transforms and pinch-zoom are out of scope — jsdom doesn't model real layout — and would need a headless browser (e.g. Playwright) if those regress.

## Map sources & credits

All map artwork is community-made and hosted on Steam. The images bundled here are mirrored only so the static site is usable; full credit and ownership belong to the creators below. Please visit, rate, and follow their work on Steam. If either creator would prefer the images not be re-hosted, open an issue and they'll be removed.

- **World map** (`maps/2899955301_preview_GREAT_BEAR_ISLAND_MAP_v12.jpg`) — preview image from [*[spoilers] Tales from the Far Territory map locations*](https://steamcommunity.com/sharedfiles/filedetails/?id=2899955301) by **Krueger**.
- **Region maps** — from [*Updated Region Maps [2025]*](https://steamcommunity.com/sharedfiles/filedetails/?id=3255435617) by **HokuOwl**. Each region has two difficulty variants: Pilgrim/Voyageur/Stalker (saved as `<region>.jpg`) and Interloper/Misery (saved as `<region>_loper.jpg`). Exact image URLs are listed in `data/regions.json`.
- **Region label positions** — adapted from [*TLD-Interactive-Map*](https://github.com/Elektronixx/TLD-Interactive-Map) by **Elektronixx**, whose image-map hotspot coordinates were converted to percentages and used as the `pos` values in `data/regions.json`.
- **Place names** — most are scraped from the per-region `Category:Locations_in_*` pages on the [Long Dark Fandom wiki](https://thelongdark.fandom.com/wiki/Locations) (CC-BY-SA 3.0). A handful in `data/places_extra.json` were read off the printed labels on HokuOwl's maps where the wiki had no matching entry.
- **Per-place bounding boxes** (`data/place_boxes.json`) — derived locally from Apple Vision OCR run over HokuOwl's region maps via `tools/ocr_run.py`, then matched to the wiki names by a Haiku subagent (`tools/match_prompt.md`). Manual fixes from the in-browser editor live in `data/place_boxes_overrides.json`. No external attribution is needed for the box coordinates themselves; the underlying labels they frame are the map artists' work.

*The Long Dark* is © Hinterland Studio Inc.

## Project structure

```
index.html              # App shell, HTML markup, JS, and inlined data (place index + place boxes + regions)
styles.css              # All app styling, loaded by index.html
src/logic.js            # Pure helpers (search ranking, BFS, hash routing). Loaded by index.html and unit-tested
tests/                  # node:test suites (run via `npm test`)
  harness.js            #   Boots index.html into jsdom for DOM-level tests
  logic.test.js         #   Unit tests for src/logic.js
  dom.test.js           #   Search dropdown, keyboard nav, hash routing
package.json            # `npm test` script + jsdom dev-dep (the only npm dep in the project)
tools/                  # Build-time scripts — only needed when refreshing the data:
  download_maps.py      #   Fetches region maps into maps/
  scrape_places.py      #   Scrapes the place index from the Long Dark Fandom wiki
  build_tiles.py        #   Splits each region map into a 3×3 overlapping tile grid for OCR
  ocr_run.py            #   Stage 1: macOS Vision OCR (ocrmac) → data/tiles/<region>/ocr_detections.json
  match_prompt.md       #   Stage 2 prompt: matches OCR text fragments to canonical wiki names
  merge_boxes.py        #   Merges per-region matcher results + overrides into data/place_boxes.json + index.html
  find_unclaimed.py     #   Discovery tool: surfaces OCR labels not claimed by the wiki for review
  inline_regions.py     #   Inlines data/regions.json into index.html between REGIONS_START/END sentinels
  scrape_tools.py       #   Scrapes Locations_with_a_forge / _workbench wiki categories + extras → crafting_tools.json
  scrape_connections.py #   Scrapes per-region `connections` infobox → regions_connections_raw.json (audit trail)
  amenity_prep.py       #   Crops each PLACE_BOXES entry into per-place .jpg + legend.jpg for vision-LLM amenity tagging
  amenity_prompt.md     #   Subagent prompt template for the vision-LLM amenity pass
dev-server.js           # Optional Node dev server: serves the site + persists in-browser bbox edits
maps/                   # Map images: per-region detail maps + the world map (committed; refresh via the script)
data/regions.json       # Canonical region list (id, display name, world-map pos, map paths, wiki + Steam URLs, adjacencies)
data/places_index.json  # Flat [{name, region}] index powering the world-view search (committed)
data/place_boxes.json   # {region: {name: [x1,y1,x2,y2]}} bounding boxes (committed; merge of OCR results + overrides)
data/place_boxes_overrides.json  # Manual edits from the dev server's Save button (committed)
data/crafting_tools.json         # {region: {name: [tool, ...]}} merge of wiki + extras + vision-LLM amenities (committed)
data/crafting_tools_extra.json   # Manual seed for tools the wiki doesn't categorise — ammo workbench, milling machine (committed)
data/regions_connections_raw.json # Wiki connections audit trail from scrape_connections.py (committed; small)
data/tiles/             # Per-region tiled maps + OCR/amenity intermediates (intermediate; gitignored)
```

Region positions on the world map live in `data/regions.json` as `pos: [x%, y%]`, consumed by every Python tool and inlined into `index.html` by `tools/inline_regions.py`. Press **D** in the browser to overlay live coordinates while hovering, then update the matching entry in `data/regions.json` and re-run the inliner.
