# The Long Dark — Interactive Map

A single-file, offline-friendly interactive map for *The Long Dark*. The world view shows Great Bear Island with clickable region labels; clicking a region opens a zoomable, pannable detail map.

**▶ Live demo: https://mhellevang.github.io/longdarkmap/**

## Usage

Open the [live demo](https://mhellevang.github.io/longdarkmap/) — or clone the repo and open `index.html` in any modern browser. No build step, no server required.

- **Click** a region label to open its detail map
- **Scroll** to zoom, **drag** to pan, **double-click** to reset
- **+ / − / ⊡** zoom controls in the bottom-right of the detail view
- **D** toggles a coordinate overlay (handy when repositioning labels in the source)

## Place search

The world view has a search box for finding any named location across all regions.

- Type to filter — e.g. `carter` matches *Carter Hydro Dam* in Mystery Lake
- Press **/** anywhere on the world view to focus the search
- **↑ / ↓** to navigate results, **Enter** to open, **Esc** to clear / blur
- Each result shows the location name and the region it belongs to; clicking opens that region's detail map

The index (~355 named locations) is bundled into `index.html` so search works fully offline, including from a static deploy.

## Refreshing the region maps

The map images live in `maps/` and are committed to the repo so the site works as a static deploy (e.g. GitHub Pages). To pull the latest versions from the source guide, run:

```sh
python3 download_maps.py
```

The script fetches both difficulty variants for each region into `maps/` and skips files that already exist. No third-party dependencies — only the Python standard library.

## Refreshing the place index

To re-scrape the location list from the Long Dark wiki:

```sh
python3 scrape_places.py            # writes data/places_index.json
python3 scrape_places.py --inline   # also bundles the result into index.html
```

The scraper hits the Fandom MediaWiki API for each region's `Category:Locations_in_<Region>` page. Use `--inline` after the scrape to bake the new index into `index.html` between the `PLACES_INDEX_START` / `PLACES_INDEX_END` sentinels — that's what the runtime search reads. Stdlib only.

## Map sources & credits

All map artwork is community-made and hosted on Steam. The images bundled here are mirrored solely so the static site is usable; full credit and ownership belong to the creators below. Please visit, rate, and follow their work on Steam — and if either creator would prefer the images not be re-hosted, open an issue and they'll be removed.

- **World map** (`maps/2899955301_preview_GREAT_BEAR_ISLAND_MAP_v12.jpg`) — preview image from [*[spoilers] Tales from the Far Territory map locations*](https://steamcommunity.com/sharedfiles/filedetails/?id=2899955301) by **Krueger**.
- **Region maps** — from [*Updated Region Maps [2025]*](https://steamcommunity.com/sharedfiles/filedetails/?id=3255435617) by **HokuOwl**. Each region has two difficulty variants: Pilgrim/Voyageur/Stalker (saved as `<region>.jpg`) and Interloper/Misery (saved as `<region>_loper.jpg`). Exact image URLs are listed in `download_maps.py`.
- **Region label positions** — adapted from [*TLD-Interactive-Map*](https://github.com/Elektronixx/TLD-Interactive-Map) by **Elektronixx**, whose image-map hotspot coordinates were converted to percentages and used as the `pos` values in `index.html`.
- **Place names** — scraped from the per-region `Category:Locations_in_*` pages on the [Long Dark Fandom wiki](https://thelongdark.fandom.com/wiki/Locations). Wiki text is licensed CC-BY-SA 3.0.

*The Long Dark* is © Hinterland Studio Inc.

## Project structure

```
index.html              # The entire app — HTML, CSS, region data, place index, and JS
download_maps.py        # Fetches region maps into maps/
scrape_places.py        # Scrapes the place index from the Long Dark Fandom wiki
maps/                   # Map images: per-region detail maps + the world map (committed; refresh via the script)
data/places_index.json  # Flat [{name, region}] index powering the world-view search (committed)
```

Region positions on the world map are defined in the `REGIONS` array inside `index.html` as `[x%, y%]` coordinates. Press **D** in the browser to display live coordinates while hovering, which makes adjusting label positions straightforward.
