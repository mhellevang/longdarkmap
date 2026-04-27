# The Long Dark — Interactive Map

A single-file, offline-friendly interactive map for *The Long Dark*. The world view shows Great Bear Island with clickable region labels; clicking a region opens a zoomable, pannable detail map.

## Usage

Open `index.html` in any modern browser — no build step, no server required.

- **Click** a region label to open its detail map
- **Scroll** to zoom, **drag** to pan, **double-click** to reset
- **+ / − / ⊡** zoom controls in the bottom-right of the detail view
- **D** toggles a coordinate overlay (handy when repositioning labels in the source)

## Refreshing the region maps

The map images live in `maps/` and are committed to the repo so the site works as a static deploy (e.g. GitHub Pages). To pull the latest versions from the source guide, run:

```sh
python3 download_maps.py
```

The script fetches both difficulty variants for each region into `maps/` and skips files that already exist. No third-party dependencies — only the Python standard library.

## Map sources & credits

All map artwork is community-made and hosted on Steam. The images bundled here are mirrored solely so the static site is usable; full credit and ownership belong to the creators below. Please visit, rate, and follow their work on Steam — and if either creator would prefer the images not be re-hosted, open an issue and they'll be removed.

- **World map** (`maps/2899955301_preview_GREAT_BEAR_ISLAND_MAP_v12.jpg`) — preview image from [*[spoilers] Tales from the Far Territory map locations*](https://steamcommunity.com/sharedfiles/filedetails/?id=2899955301) by **Krueger**.
- **Region maps** — from [*Updated Region Maps [2025]*](https://steamcommunity.com/sharedfiles/filedetails/?id=3255435617) by **HokuOwl**. Each region has two difficulty variants: Pilgrim/Voyageur/Stalker (saved as `<region>.jpg`) and Interloper/Misery (saved as `<region>_loper.jpg`). Exact image URLs are listed in `download_maps.py`.
- **Region label positions** — adapted from [*TLD-Interactive-Map*](https://github.com/Elektronixx/TLD-Interactive-Map) by **Elektronixx**, whose image-map hotspot coordinates were converted to percentages and used as the `pos` values in `index.html`.

*The Long Dark* is © Hinterland Studio Inc.

## Project structure

```
index.html         # The entire app — HTML, CSS, region data, and JS
download_maps.py   # Fetches region maps into maps/
maps/              # Map images: per-region detail maps + the world map (committed; refresh via the script)
```

Region positions on the world map are defined in the `REGIONS` array inside `index.html` as `[x%, y%]` coordinates. Press **D** in the browser to display live coordinates while hovering, which makes adjusting label positions straightforward.
