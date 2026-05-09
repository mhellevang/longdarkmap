"""Extract clickable "To <region>" link bboxes from OCR data.

Each region map has red perimeter labels that point at neighbouring regions
("To Mystery Lake", "TO ASH CANYON", ...). The OCR pass already detects
those fragments; this script:

  1. Walks each region's `data/tiles/<id>/ocr_detections.json`.
  2. Filters fragments whose text begins with "to " and whose suffix
     resolves to a known region id.
  3. Converts tile-local bboxes to whole-image 0..1 coords using the
     tile manifest's `bbox_norm`.
  4. Dedupes labels that appear in two overlapping tiles.
  5. Writes `data/region_links.json` —
     `{ region_id: [{ "target": region_id, "bbox": [x1,y1,x2,y2], "text": "..." }, ...] }`.

Run after `ocr_run.py`. The frontend inlines the result via
`inline_regions.py` (extended in the same commit).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TILES_DIR = ROOT / "data" / "tiles"
OUT_FILE = ROOT / "data" / "region_links.json"
REGIONS_FILE = ROOT / "data" / "regions.json"

# Map the *first one or two words* after "to" to a target region id. The
# OCR labels are often split across two visual lines ("To Forlorn /
# Muskeg"), so the first word alone is usually enough — we only need the
# disambiguators where two regions share a leading word ("Keeper's Pass"
# vs "Keepers ..."). Lowercase keys; longest match wins.
TARGETS: dict[str, str] = {
    "mystery": "mystery_lake",
    "mystery lake": "mystery_lake",
    "coastal": "coastal_highway",
    "coastal highway": "coastal_highway",
    "pleasant": "pleasant_valley",
    "pleasant valley": "pleasant_valley",
    "timberwolf": "timberwolf_mountain",
    "ash": "ash_canyon",
    "ash canyon": "ash_canyon",
    "bleak": "bleak_inlet",
    "bleak inlet": "bleak_inlet",
    "mountain": "mountain_town",
    "mountain town": "mountain_town",
    "hushed": "hushed_river_valley",
    "hushed river": "hushed_river_valley",
    "hushed river valley": "hushed_river_valley",
    "forlorn": "forlorn_muskeg",
    "forlorn muskeg": "forlorn_muskeg",
    "broken": "broken_railroad",
    "broken railroad": "broken_railroad",
    "far range": "far_range",
    "transfer": "transfer_pass",
    "transf": "transfer_pass",  # truncated OCR fragment
    "transfer pass": "transfer_pass",
    "forsaken": "forsaken_airfield",
    "forsaken airfield": "forsaken_airfield",
    "sundered": "sundered_pass",
    "sundered pass": "sundered_pass",
    "zone of": "zone_of_contamination",
    "zone of contamination": "zone_of_contamination",
    "ravine": "ravine",
    "the ravine": "ravine",
    "crumbling": "crumbling_highway",
    "crumbling highway": "crumbling_highway",
    "desolation": "desolation_point",
    "desolation point": "desolation_point",
    "winding": "winding_river",
    "winding river": "winding_river",
    "lower dam": "winding_river",  # "TO LOWER DAM & WINDING RIVER"
    "keeper's pass": "keepers_pass",
    "keepers pass": "keepers_pass",
    "keeper's": "keepers_pass",
    "blackrock": "blackrock",
}

# Strip leading "to " (case-insensitive) and any decorative ampersand junk
# OCR sometimes attaches at the end ("TO LOWER DAM &").
_TO_RE = re.compile(r"^\s*to\s+", re.IGNORECASE)


def normalise(text: str) -> str:
    """Return the lower-case content following the leading 'to '."""
    text = _TO_RE.sub("", text).strip()
    text = text.rstrip("&").strip()
    return text.lower()


def resolve_target(text: str) -> str | None:
    """Match the OCR text's content to a region id, longest-prefix wins."""
    body = normalise(text)
    if not body:
        return None
    best = None
    for key, region_id in TARGETS.items():
        if body == key or body.startswith(key + " ") or body.startswith(key):
            if best is None or len(key) > len(best[0]):
                best = (key, region_id)
    return best[1] if best else None


def to_global(tile_bbox_norm, frag_bbox):
    """Map a tile-local 0..1 bbox to whole-image 0..1 coords."""
    tx1, ty1, tx2, ty2 = tile_bbox_norm
    fx1, fy1, fx2, fy2 = frag_bbox
    tw, th = tx2 - tx1, ty2 - ty1
    return [
        round(tx1 + fx1 * tw, 5),
        round(ty1 + fy1 * th, 5),
        round(tx1 + fx2 * tw, 5),
        round(ty1 + fy2 * th, 5),
    ]


def near_duplicate(a, b, tol=0.01):
    """True if two global bboxes overlap nearly the same patch of map.

    Tile overlap means the same red label can be detected twice; the
    fragments are pixel-identical except for the global shift, so a small
    centre-distance tolerance is enough."""
    ax = (a[0] + a[2]) / 2
    ay = (a[1] + a[3]) / 2
    bx = (b[0] + b[2]) / 2
    by = (b[1] + b[3]) / 2
    return abs(ax - bx) < tol and abs(ay - by) < tol


def merge_continuations(base_frag: dict, frags: list[dict], target: str) -> tuple[list, str]:
    """Greedily extend a 'To <X>' bbox downward to swallow wrapped lines.

    The wiki maps render multi-word labels on two visual lines ("To
    Crumbling" / "Highway"), and Apple Vision OCR splits each line into a
    separate fragment. We match continuations by:
      - vertical proximity (gap below the running bbox under one line height),
      - horizontal overlap with the running bbox.

    Other 'To <Y>' fragments are only swallowed if they resolve to the same
    target (handles "TO LOWER DAM & / WINDING RIVER" — both line 1 and
    line 2 point at winding_river).
    """
    bbox = list(base_frag["bbox"])
    base_h = bbox[3] - bbox[1]
    pieces = [base_frag["text"].strip()]
    used = {id(base_frag)}
    changed = True
    while changed:
        changed = False
        for other in frags:
            if id(other) in used:
                continue
            ob = other["bbox"]
            gap = ob[1] - bbox[3]
            # Allow a slight upward overlap (-0.3h) for tightly stacked
            # baselines but cap downward search at ~1.2 line heights so we
            # don't start swallowing the next paragraph.
            if not (-0.3 * base_h <= gap <= 1.2 * base_h):
                continue
            ox_overlap = min(ob[2], bbox[2]) - max(ob[0], bbox[0])
            if ox_overlap <= 0:
                continue
            ot = other["text"].strip()
            if _TO_RE.match(ot):
                other_target = resolve_target(ot)
                if other_target != target:
                    continue
            bbox[0] = min(bbox[0], ob[0])
            bbox[1] = min(bbox[1], ob[1])
            bbox[2] = max(bbox[2], ob[2])
            bbox[3] = max(bbox[3], ob[3])
            pieces.append(ot)
            used.add(id(other))
            changed = True
    return bbox, " ".join(pieces)


def extract_region(region_id: str) -> list[dict]:
    region_dir = TILES_DIR / region_id
    manifest_path = region_dir / "manifest.json"
    ocr_path = region_dir / "ocr_detections.json"
    if not manifest_path.exists() or not ocr_path.exists():
        return []

    manifest = json.loads(manifest_path.read_text())
    tiles_by_id = {f"{t['row']}_{t['col']}": t for t in manifest["tiles"]}
    ocr = json.loads(ocr_path.read_text())

    candidates: list[dict] = []
    for tile_id, frags in ocr["tiles"].items():
        tile = tiles_by_id.get(tile_id)
        if not tile:
            continue
        for frag in frags:
            text = frag["text"].strip()
            if not _TO_RE.match(text):
                continue
            target = resolve_target(text)
            if not target or target == region_id:
                # No match (e.g. "To 1st floor", "to sleep") — or self-loop
                # (a label inside a region that points back to itself).
                continue
            merged_bbox, merged_text = merge_continuations(frag, frags, target)
            global_bbox = to_global(tile["bbox_norm"], merged_bbox)
            candidates.append({
                "target": target,
                "bbox": global_bbox,
                "text": merged_text,
            })

    # Dedupe: collapse near-duplicate detections (tile overlap) by target.
    candidates.sort(key=lambda c: (c["target"], c["bbox"][1], c["bbox"][0]))
    merged: list[dict] = []
    for c in candidates:
        dup = next(
            (m for m in merged
             if m["target"] == c["target"] and near_duplicate(m["bbox"], c["bbox"])),
            None,
        )
        if dup:
            # Keep the longer text — usually the more complete OCR read.
            if len(c["text"]) > len(dup["text"]):
                dup["text"] = c["text"]
                dup["bbox"] = c["bbox"]
            continue
        merged.append(c)
    return merged


def main(argv: list[str]) -> int:
    region_ids = [r["id"] for r in json.loads(REGIONS_FILE.read_text())]
    out: dict[str, list[dict]] = {}
    total = 0
    for region_id in region_ids:
        links = extract_region(region_id)
        out[region_id] = links
        total += len(links)
        targets = ", ".join(sorted({l["target"] for l in links})) or "(none)"
        print(f"  {region_id:<24} {len(links):>2} link(s)  → {targets}")

    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {total} links across {len(out)} regions → {OUT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
