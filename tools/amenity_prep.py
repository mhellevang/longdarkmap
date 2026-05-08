"""Prepare per-region inputs for the vision-LLM amenity pass.

For each region, write into data/tiles/<region>/amenities/:
  - legend.jpg     — bottom strip of the map; the icon→label key
  - <slug>.jpg     — one padded crop per place (PLACE_BOXES bbox, expanded)
  - task.json      — region id, list of {name, slug, bbox}, canonical tag list

A subagent (one per region) reads task.json + the crops, returns
{place_name: [tags]} into result.json. tools/merge_amenities.py (TODO)
layers those into data/crafting_tools.json next to the wiki forge/workbench
tags.

The crop padding is generous — icons sit *next to* the place's printed
label, not on top of it. We expand each PLACE_BOXES bbox to a square ~3×
the label's longer edge (capped to a per-region maximum) so adjacent icons
fall inside the crop. Small enough to keep visual context tight, large
enough to catch icons that float a label-width away.

Usage:
    .venv/bin/python tools/amenity_prep.py            # all regions
    .venv/bin/python tools/amenity_prep.py coastal_highway
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent
TILES_DIR = ROOT / "data" / "tiles"
REGIONS_FILE = ROOT / "data" / "regions.json"
PLACE_BOXES_FILE = ROOT / "data" / "place_boxes.json"

# Canonical tag list. Subagents are constrained to this set so the merged
# crafting_tools.json stays consistent. Anything not in this set → ignored.
# Kept tight on purpose: rare/scarce stations the player might travel for,
# plus a few comfort markers. Animal areas, foraging, loot drops, road
# graphics, etc. are visible on the map already — re-tagging them adds noise
# without information.
CANONICAL_TAGS = [
    # Crafting (rare)
    "forge",
    "workbench",
    "ammunition_workbench",
    "milling_machine",
    # Comfort / survival
    "bed",
    "stove",
    "first_aid",
    # Fishing
    "ice_fishing_hut",
    "ice_fishing_hole",
]

# Crop sizing. The label bbox itself is small (a few percent of the map);
# icons sit a label-width or two away. Expand to a square that's max(W,H) * 4
# centred on the label, then clamp to the image bounds.
EXPAND_FACTOR = 4.0
# Lower bound so very tiny labels still get a crop with usable context.
MIN_CROP_PX = 320
# Upper bound so dense city centres don't produce a huge crop that drags in
# unrelated icons. 720px keeps the resolution under Anthropic's 1568px clamp
# without losing icon legibility.
MAX_CROP_PX = 720

# Legend strip — the bottom ~22% of HokuOwl's region maps holds the icon key.
# Tuned by eye on coastal_highway/ash_canyon/forsaken_airfield; adjust if a
# specific map needs a different fraction.
LEGEND_TOP_FRAC = 0.78


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s or "place"


def crop_box_for(bbox: list[float], W: int, H: int) -> tuple[int, int, int, int]:
    """Compute a (left, top, right, bottom) crop in pixel coords."""
    x1, y1, x2, y2 = bbox
    px1, py1, px2, py2 = x1 * W, y1 * H, x2 * W, y2 * H
    cx, cy = (px1 + px2) / 2, (py1 + py2) / 2
    edge = max(px2 - px1, py2 - py1, 1.0) * EXPAND_FACTOR
    edge = max(MIN_CROP_PX, min(MAX_CROP_PX, edge))
    half = edge / 2
    L = max(0, int(round(cx - half)))
    T = max(0, int(round(cy - half)))
    R = min(W, int(round(cx + half)))
    B = min(H, int(round(cy + half)))
    return (L, T, R, B)


def prep_region(region_id: str, map_path: Path, boxes: dict, out_dir: Path) -> dict:
    img = Image.open(map_path)
    W, H = img.size
    out_dir.mkdir(parents=True, exist_ok=True)

    # Legend strip: full-width crop of the bottom of the map.
    legend = img.crop((0, int(H * LEGEND_TOP_FRAC), W, H))
    legend.save(out_dir / "legend.jpg", quality=88)

    # Dedupe alias names that share a bbox (merge_boxes.py emits both forms).
    seen: dict[str, str] = {}
    for name, bbox in boxes.items():
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        key = ",".join(f"{v:.5f}" for v in bbox)
        if key not in seen or len(name) > len(seen[key]):
            seen[key] = name

    places = []
    for key, name in seen.items():
        bbox = boxes[name]
        slug = slugify(name)
        L, T, R, B = crop_box_for(bbox, W, H)
        crop = img.crop((L, T, R, B))
        crop.save(out_dir / f"{slug}.jpg", quality=88)
        places.append({
            "name": name,
            "slug": slug,
            "bbox": [round(v, 5) for v in bbox],
            "crop_px": [L, T, R, B],
        })

    places.sort(key=lambda p: p["name"].lower())
    task = {
        "region_id": region_id,
        "source_map": str(map_path.relative_to(ROOT)),
        "image_size": [W, H],
        "legend_image": "legend.jpg",
        "canonical_tags": CANONICAL_TAGS,
        "places": places,
    }
    (out_dir / "task.json").write_text(json.dumps(task, indent=2) + "\n")
    return task


def main(argv: list[str]) -> int:
    regions = {r["id"]: r for r in json.loads(REGIONS_FILE.read_text())}
    boxes_all = json.loads(PLACE_BOXES_FILE.read_text())
    targets = argv or list(regions.keys())

    for region_id in targets:
        if region_id not in regions:
            print(f"unknown region: {region_id}", file=sys.stderr)
            continue
        region = regions[region_id]
        boxes = boxes_all.get(region_id, {})
        if not boxes:
            print(f"  · {region_id:<24} no place boxes, skip")
            continue
        map_path = ROOT / region["maps"][0]
        if not map_path.exists():
            print(f"  · {region_id:<24} missing {map_path}, skip")
            continue
        out_dir = TILES_DIR / region_id / "amenities"
        task = prep_region(region_id, map_path, boxes, out_dir)
        print(f"    {region_id:<24} {len(task['places']):>3} crops -> {out_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
