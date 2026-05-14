"""Merge per-region OCR results into data/place_boxes.json + inline into HTML.

Reads each data/tiles/<region>/result.json, converts tile-relative bboxes into
normalized full-image bboxes, and writes a flat keyed structure:

    { "<region>": { "<place name>": [x1, y1, x2, y2], ... } }

Coordinates are 0..1 fractions of the full map image. We expose each box
under both the agent's reported name AND the canonical PLACES_INDEX name
(with any wiki disambiguation suffix). The frontend looks up by the
canonical name shown in search; the alternate keys are belt-and-suspenders.

For places with multiple in-map instances (e.g. several Fishing Huts), the
agent appended "#1", "#2" suffixes; the plain name maps to the first
instance so a search that doesn't disambiguate still gets a sensible result.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _inline import inline_block

ROOT = Path(__file__).parent.parent
TILES_DIR = ROOT / "data" / "tiles"
OUT = ROOT / "data" / "place_boxes.json"
# Manual overrides written by the dev server's save endpoint. Layered over
# the OCR-derived results so a user can fix misplaced boxes without those
# fixes being clobbered the next time the OCR pipeline is re-run.
OVERRIDES = ROOT / "data" / "place_boxes_overrides.json"
INDEX_HTML = ROOT / "index.html"

START = "// PLACE_BOXES_START"
END = "// PLACE_BOXES_END"

INSTANCE_SUFFIX = re.compile(r"\s*#\d+\s*$")


def tile_to_full(tile_bbox_norm: list[float], bbox_in_tile: list[float]) -> list[float]:
    """Convert [x1,y1,x2,y2] in tile-relative coords to full-image norm coords."""
    tx0, ty0, tx1, ty1 = tile_bbox_norm
    tw = tx1 - tx0
    th = ty1 - ty0
    bx0, by0, bx1, by1 = bbox_in_tile
    # Clamp tile-relative coords to [0,1] in case the agent overshot.
    bx0 = max(0.0, min(1.0, bx0))
    bx1 = max(0.0, min(1.0, bx1))
    by0 = max(0.0, min(1.0, by0))
    by1 = max(0.0, min(1.0, by1))
    return [
        round(tx0 + bx0 * tw, 5),
        round(ty0 + by0 * th, 5),
        round(tx0 + bx1 * tw, 5),
        round(ty0 + by1 * th, 5),
    ]


def strip_paren_suffix(name: str) -> str:
    """'Lookout (Mystery Lake location)' -> 'Lookout'. Used to bridge agents
    that reported the on-map name without the wiki disambiguation suffix."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def merge_region(region_dir: Path, canonical_names: list[str]) -> tuple[dict, list[str], list[str]]:
    manifest = json.loads((region_dir / "manifest.json").read_text())
    result_file = region_dir / "result.json"
    if not result_file.exists():
        return {}, [], [f"{region_dir.name}: no result.json"]

    result = json.loads(result_file.read_text())
    tiles = {f"{t['row']}_{t['col']}": t for t in manifest["tiles"]}

    boxes: dict[str, list[float]] = {}
    not_found: list[str] = list(result.get("not_found", []))
    issues: list[str] = []

    for r in result.get("results", []):
        tile_id = r.get("tile")
        if tile_id not in tiles:
            issues.append(f"{region_dir.name}: unknown tile {tile_id} for {r.get('name')}")
            continue
        bbox_in_tile = r.get("bbox_in_tile")
        if not (isinstance(bbox_in_tile, list) and len(bbox_in_tile) == 4):
            issues.append(f"{region_dir.name}: bad bbox_in_tile for {r.get('name')}")
            continue
        full = tile_to_full(tiles[tile_id]["bbox_norm"], bbox_in_tile)
        name = r["name"]
        boxes[name] = full
        # Plain (instance-suffix-stripped) form, so a query without "#1" lands
        # on the first instance.
        plain = INSTANCE_SUFFIX.sub("", name).strip()
        if plain != name and plain not in boxes:
            boxes[plain] = full

    # Bridge agent-reported on-map names ("Lookout") to the canonical wiki
    # name shown in the search index ("Lookout (Mystery Lake location)").
    for canon in canonical_names:
        if canon in boxes:
            continue
        unsuffixed = strip_paren_suffix(canon)
        if unsuffixed and unsuffixed != canon and unsuffixed in boxes:
            boxes[canon] = boxes[unsuffixed]

    return boxes, not_found, issues


def inline_into_html(payload: dict) -> bool:
    return inline_block(INDEX_HTML, "PLACE_BOXES", START, END, payload, ensure_ascii=False)


def main(argv: list[str]) -> int:
    if not TILES_DIR.exists():
        print(f"missing: {TILES_DIR}", file=sys.stderr)
        return 1

    places = json.loads((ROOT / "data" / "places_index.json").read_text())
    canonical_by_region: dict[str, list[str]] = {}
    for p in places:
        canonical_by_region.setdefault(p["region"], []).append(p["name"])

    all_boxes: dict[str, dict[str, list[float]]] = {}
    summary: list[tuple[str, int, int]] = []
    all_issues: list[str] = []

    for region_dir in sorted(TILES_DIR.iterdir()):
        if not region_dir.is_dir():
            continue
        canonical = canonical_by_region.get(region_dir.name, [])
        boxes, not_found, issues = merge_region(region_dir, canonical)
        all_boxes[region_dir.name] = boxes
        summary.append((region_dir.name, len(boxes), len(not_found)))
        all_issues.extend(issues)
        for nf in not_found:
            all_issues.append(f"  {region_dir.name}: not_found {nf}")

    # Layer manual overrides on top of the OCR-derived map. Overrides are
    # produced by the dev server's Save button; this preserves them across
    # re-runs of the pipeline.
    overrides_applied = 0
    if OVERRIDES.exists():
        overrides = json.loads(OVERRIDES.read_text())
        for region_id, names in overrides.items():
            target = all_boxes.setdefault(region_id, {})
            for name, bbox in names.items():
                target[name] = list(bbox)
                overrides_applied += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(all_boxes, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)}" +
          (f"  ({overrides_applied} override{'s' if overrides_applied != 1 else ''} applied)"
           if overrides_applied else ""))
    for region_id, n, nf in summary:
        marker = " " if n else "·"
        print(f"  {marker} {region_id:<24} {n:>3} placed, {nf} not_found")

    if "--inline" in argv:
        if inline_into_html(all_boxes):
            print(f"Inlined into {INDEX_HTML.relative_to(ROOT)}")
        else:
            print(f"warn: sentinels {START}/{END} not found in index.html — not inlined",
                  file=sys.stderr)

    if all_issues:
        print("\nIssues:")
        for it in all_issues:
            print(f"  {it}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
