"""Tile each region map into a grid for high-resolution OCR by vision agents.

Each map is large (~4000×4500). When sent to a model in one shot it gets
downsampled to ~1500px on the long edge, which makes small labels unreadable.
Cutting each map into N×M tiles keeps text legible while still letting the
agent reason about where on the full map a label sits.

Output: data/tiles/<region>/<row>_<col>.jpg + data/tiles/<region>/manifest.json
The manifest records each tile's bounding box in normalized full-image coords
(0..1) so the agent (and downstream code) can map tile-relative finds back to
the full map.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent
TILES_DIR = ROOT / "data" / "tiles"

# Regions to tile (id -> primary map path). We OCR the standard variant only;
# loper variants share layout.
REGION_MAPS: dict[str, str] = {
    "mystery_lake":          "maps/mystery_lake.jpg",
    "coastal_highway":       "maps/coastal_highway.jpg",
    "pleasant_valley":       "maps/pleasant_valley.jpg",
    "desolation_point":      "maps/desolation_point.jpg",
    "timberwolf_mountain":   "maps/timberwolf_mountain.jpg",
    "forlorn_muskeg":        "maps/forlorn_muskeg.jpg",
    "broken_railroad":       "maps/broken_railroad.jpg",
    "bleak_inlet":           "maps/bleak_inlet.jpg",
    "hushed_river_valley":   "maps/hushed_river_valley.jpg",
    "mountain_town":         "maps/mountain_town.jpg",
    "ash_canyon":            "maps/ash_canyon.jpg",
    "blackrock":             "maps/blackrock.jpg",
    "forsaken_airfield":     "maps/forsaken_airfield.jpg",
    "sundered_pass":         "maps/sundered_pass.jpg",
    "zone_of_contamination": "maps/zone_of_contamination.jpg",
    "crumbling_highway":     "maps/crumbling_highway.jpg",
    "far_range":             "maps/far_range_branch_line.jpg",
    "transfer_pass":         "maps/transfer_pass.jpg",
    "ravine":                "maps/ravine.jpg",
    "winding_river":         "maps/winding_river_and_carter_hydro_dam.jpg",
    "keepers_pass":          "maps/keepers_pass.jpg",
}

# Grid size and overlap. Overlap helps with labels that straddle a seam.
COLS, ROWS = 3, 3
OVERLAP = 0.12  # fraction of tile size


def tile_map(region_id: str, src: Path, out_dir: Path) -> dict:
    img = Image.open(src)
    W, H = img.size
    tile_w = W / COLS
    tile_h = H / ROWS
    pad_x = int(tile_w * OVERLAP)
    pad_y = int(tile_h * OVERLAP)

    tiles = []
    for r in range(ROWS):
        for c in range(COLS):
            x0 = max(0, int(c * tile_w) - pad_x)
            y0 = max(0, int(r * tile_h) - pad_y)
            x1 = min(W, int((c + 1) * tile_w) + pad_x)
            y1 = min(H, int((r + 1) * tile_h) + pad_y)
            crop = img.crop((x0, y0, x1, y1))
            name = f"{r}_{c}.jpg"
            crop.save(out_dir / name, quality=88)
            tiles.append({
                "file": name,
                "row": r,
                "col": c,
                "bbox_pixels": [x0, y0, x1, y1],
                "bbox_norm": [x0 / W, y0 / H, x1 / W, y1 / H],
            })

    manifest = {
        "region_id": region_id,
        "source": str(src.relative_to(ROOT)),
        "image_size": [W, H],
        "grid": [COLS, ROWS],
        "overlap": OVERLAP,
        "tiles": tiles,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv: list[str]) -> int:
    targets = argv or list(REGION_MAPS.keys())
    TILES_DIR.mkdir(parents=True, exist_ok=True)
    for region_id in targets:
        if region_id not in REGION_MAPS:
            print(f"unknown region: {region_id}", file=sys.stderr)
            continue
        src = ROOT / REGION_MAPS[region_id]
        if not src.exists():
            print(f"missing: {src}", file=sys.stderr)
            continue
        out_dir = TILES_DIR / region_id
        out_dir.mkdir(parents=True, exist_ok=True)
        m = tile_map(region_id, src, out_dir)
        W, H = m["image_size"]
        print(f"{region_id:<24} {W}x{H}  -> {len(m['tiles'])} tiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
