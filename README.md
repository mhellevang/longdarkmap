# The Long Dark — Interactive Map

A single-file, offline-friendly interactive map for *The Long Dark*. The world view shows Great Bear Island with clickable region labels; clicking a region opens a zoomable, pannable detail map.

**▶ Live demo: https://mhellevang.github.io/longdarkmap/**

## Usage

Open the [live demo](https://mhellevang.github.io/longdarkmap/), or clone the repo and open `index.html` in any modern browser. No build step, no server required.

- **Click** a region label to open its detail map
- **Scroll** to zoom, **drag** to pan, **double-click** to reset
- **+ / − / ⊡** zoom controls in the bottom-right of the detail view
- **D** toggles a coordinate overlay — `[x%, y%]` of the world map on the world view; `[x, y]` as 0..1 of the region map on the detail view. In the detail view with D on:
  - **All bounding boxes for the region are drawn** as labelled blue rectangles, so misplaced ones can be spotted at a glance.
  - **Click any box** (including the search highlight) to grab it — immediately editable, drag-to-move.
  - **Shift-drag** to draw a fresh bounding box.
  - In editing mode, **drag the body** to translate, **drag the corner handles** to resize. Click **Save** to persist (requires the dev server, see below) or **Cancel** to dismiss.

## Place search

The world view has a search box for finding any named location across all regions.

- Type to filter — e.g. `carter` matches *Carter Hydro Dam* in Mystery Lake
- Press **/** anywhere on the world view to focus the search
- **↑ / ↓** to navigate results, **Enter** to open, **Esc** to clear / blur
- Each result shows the location name and the region it belongs to; clicking opens that region's detail map and **highlights** the matching label — the view zooms in on the box, briefly dims the rest of the map, and leaves a glowing outline around the label

The index (~355 named locations) plus per-label bounding boxes are bundled into `index.html` so search and highlighting work fully offline, including from a static deploy.

## Refreshing the region maps

The map images live in `maps/` and are committed to the repo so the site works as a static deploy (e.g. GitHub Pages). To pull the latest versions from the source guide, run:

```sh
python3 download_maps.py
```

The script fetches both difficulty variants for each region into `maps/` and skips files that already exist. No third-party dependencies, just the Python standard library.

## Refreshing the place index

To re-scrape the location list from the Long Dark wiki:

```sh
python3 scrape_places.py            # writes data/places_index.json
python3 scrape_places.py --inline   # also bundles the result into index.html
```

The scraper hits the Fandom MediaWiki API for each region's `Category:Locations_in_<Region>` page. Use `--inline` after the scrape to bake the new index into `index.html` between the `PLACES_INDEX_START` / `PLACES_INDEX_END` sentinels — that's what the runtime search reads. Stdlib only.

## Refreshing the place boxes

Each named location has a bounding box on its region map so search-result clicks can frame the right label. The boxes are produced by reading each map with a vision-capable subagent.

```sh
python3 build_tiles.py        # split each map into a 3×3 overlapping tile grid
python3 build_task_files.py   # write per-region task.json (names to locate)
# then, in Claude Code, dispatch one OCR subagent per region pointed at
# data/tiles/<region>/ — see the inline prompt template in the chat history
python3 merge_boxes.py --inline   # merge results, write data/place_boxes.json,
                                  # and inline into index.html
```

The merge script writes both `data/place_boxes.json` and refreshes the `PLACE_BOXES_START` / `PLACE_BOXES_END` block in `index.html`. Coordinates are stored as `[x1, y1, x2, y2]` fractions (0..1) of the region's full map image.

### Fixing misplaced boxes from the browser

```sh
node dev-server.js   # http://127.0.0.1:8765/  (no npm install — stdlib only)
```

Press **D** in any region to overlay every stored bounding box at once — labelled with its place name — so misplaced boxes are easy to find without opening each one via search. Then either:
- **Click any box** (or the brighter search highlight) to grab it — drag the body to move, drag corner handles to resize.
- **Shift-drag** anywhere to draw a fresh bounding box from scratch.

Click **Save** when the box looks right. The server writes the new bbox into `data/place_boxes_overrides.json` and re-runs `merge_boxes.py --inline` so `data/place_boxes.json` and the inlined `PLACE_BOXES` in `index.html` both reflect the change immediately. The page also updates its in-memory `PLACE_BOXES` so the highlight snaps to the new position without a reload.

The overrides file is the source of manual fixes; running `merge_boxes.py` on its own re-derives `data/place_boxes.json` from the OCR results in `data/tiles/` and layers overrides on top, so re-running the OCR pipeline never destroys hand-tuned boxes.

## Map sources & credits

All map artwork is community-made and hosted on Steam. The images bundled here are mirrored only so the static site is usable; full credit and ownership belong to the creators below. Please visit, rate, and follow their work on Steam. If either creator would prefer the images not be re-hosted, open an issue and they'll be removed.

- **World map** (`maps/2899955301_preview_GREAT_BEAR_ISLAND_MAP_v12.jpg`) — preview image from [*[spoilers] Tales from the Far Territory map locations*](https://steamcommunity.com/sharedfiles/filedetails/?id=2899955301) by **Krueger**.
- **Region maps** — from [*Updated Region Maps [2025]*](https://steamcommunity.com/sharedfiles/filedetails/?id=3255435617) by **HokuOwl**. Each region has two difficulty variants: Pilgrim/Voyageur/Stalker (saved as `<region>.jpg`) and Interloper/Misery (saved as `<region>_loper.jpg`). Exact image URLs are listed in `download_maps.py`.
- **Region label positions** — adapted from [*TLD-Interactive-Map*](https://github.com/Elektronixx/TLD-Interactive-Map) by **Elektronixx**, whose image-map hotspot coordinates were converted to percentages and used as the `pos` values in `index.html`.
- **Place names** — scraped from the per-region `Category:Locations_in_*` pages on the [Long Dark Fandom wiki](https://thelongdark.fandom.com/wiki/Locations). Wiki text is licensed CC-BY-SA 3.0.

*The Long Dark* is © Hinterland Studio Inc.

## Project structure

```
index.html              # The entire app — HTML, CSS, region data, place index, place boxes, and JS
download_maps.py        # Fetches region maps into maps/
scrape_places.py        # Scrapes the place index from the Long Dark Fandom wiki
build_tiles.py          # Splits each region map into a 3×3 overlapping tile grid for OCR
build_task_files.py     # Writes per-region task.json (names a vision agent should locate)
merge_boxes.py          # Merges per-region OCR results + overrides into data/place_boxes.json + index.html
dev-server.js           # Optional Node dev server: serves the site + persists in-browser bbox edits
maps/                   # Map images: per-region detail maps + the world map (committed; refresh via the script)
data/places_index.json  # Flat [{name, region}] index powering the world-view search (committed)
data/place_boxes.json   # {region: {name: [x1,y1,x2,y2]}} bounding boxes (committed; merge of OCR results + overrides)
data/place_boxes_overrides.json  # Manual edits from the dev server's Save button (committed)
data/tiles/             # Per-region tiled maps + OCR results (intermediate; gitignored)
```

Region positions on the world map are defined in the `REGIONS` array inside `index.html` as `[x%, y%]` coordinates. Press **D** in the browser to overlay live coordinates while hovering, so you can read off the right `[x%, y%]` for a misplaced label and update its entry in `REGIONS`.
