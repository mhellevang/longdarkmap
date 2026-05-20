"""Detect resource pictograms on every region map via legend-template matching.

Locates icons like moose-area, bear-area, wolf-area, cattails — anything drawn
as a small recurring pictogram with a distinctive color signature — and writes
their bbox positions to `data/region_resources.json`.

Pipeline (per region):
  1. For each "class group" (resources sharing one HSV color filter), build a
     binary color mask of the map.
  2. For each template in the group, multi-scale TM_CCOEFF_NORMED on the binary
     mask → raw hits with (bbox, score, class).
  3. Cross-class NMS keeps each spatial cluster's highest-scoring class — this
     is how moose/bear/wolf get disambiguated despite sharing color.
  4. Output bboxes as 0..1 fractions of the region image, like place_boxes.

Templates in `data/legend_icons/canonical/` are shared across all 21 regions —
HokuOwl reuses the same vector icons in every map's legend, so a single
canonical set suffices. We also match against a horizontally-flipped copy of
each template, since animals on the map are drawn facing either direction.

Masked SQDIFF was tried first but disables OpenCV's DFT fast path, making the
match step minutes per region. Binary CCOEFF on a color-pre-filtered map is
~20× faster (≈10 s/region) and gives equivalent precision once cross-class
NMS resolves intra-color-family overlap.

Usage:
    .venv/bin/python tools/find_resources.py            # all regions
    .venv/bin/python tools/find_resources.py mystery_lake desolation_point
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from _inline import inline_block

ROOT = Path(__file__).parent.parent
REGIONS_FILE = ROOT / "data" / "regions.json"
TEMPLATES_DIR = ROOT / "data" / "legend_icons" / "canonical"
OUT_FILE = ROOT / "data" / "region_resources.json"
INDEX_HTML = ROOT / "index.html"

SCALES = [0.85, 0.95, 1.00, 1.05, 1.15]
# Default per-group score threshold. Looser groups (red_brown_animals,
# cattails, green_foraging) where the color filter alone gives strong
# discrimination can use the default. Stricter groups (black, gray) where
# the color filter catches a lot of map noise need a higher threshold —
# configured per-group in CLASS_GROUPS below.
SCORE_THRESHOLD_DEFAULT = 0.45
NMS_IOU = 0.30
# HokuOwl's region maps have a legend strip at the bottom ~22% of the image
# for *most* regions, but Mystery Lake / Bleak Inlet / Forlorn Muskeg put
# the legend at the top instead. Rather than maintain a per-region exclusion
# rect, we detect legend areas after matching: a tight spatial cluster
# containing very-high-score hits from multiple distinct classes (legend
# swatches reproduce the icon exactly so they peak at ~0.98) is almost
# certainly a legend. We then suppress *all* hits inside that bbox.
LEGEND_TOP_FRAC = 0.78
LEGEND_DETECT_SCORE = 0.95
# Classes trusted to seed legend-area detection. Only the four red-brown
# animals have low enough false-positive rates at >0.95 that their hits
# can be taken at face value. The black-icon and gray-icon groups pick up
# too much text/label noise to be trustworthy seeds — even after
# morphological opening — and would create runaway false clusters.
LEGEND_SEED_CLASSES = {"moose", "bear", "wolf", "timberwolf"}
LEGEND_DETECT_RADIUS = 0.07   # fraction of map; how close two class swatches
                              # must sit to be considered part of one legend.
                              # Also used to grow the cluster bbox to swallow
                              # adjacent legend entries (rows further away).
LEGEND_MAX_AREA = 0.08        # fraction of map; cap on a single legend bbox's
                              # area. Real legend strips on HokuOwl's maps
                              # sit in <6% of the image; this gives headroom.
LEGEND_EDGE_TOLERANCE = 0.08  # fraction of map; a cluster must touch (be
                              # within this distance of) at least one map
                              # edge to count as a legend. Real legends are
                              # always edge-anchored; clusters in the dead
                              # center are almost certainly real on-map
                              # multi-species hot-spots, not legend swatches.

# HSV ranges (OpenCV: H 0..179, S/V 0..255).
RED_BROWN = [
    {"h": (0, 12),    "s": (90, 255), "v": (30, 200)},
    {"h": (160, 179), "s": (90, 255), "v": (30, 200)},
]
CATTAILS_BROWN = [
    {"h": (8, 22), "s": (90, 255), "v": (30, 180)},
]
# Pure-black icons (deer silhouette, rabbit, coal cart, salt deposit). Very
# low value (dark), saturation can be anything (a flat dark color works at
# any saturation when V is low).
BLACK = [
    {"h": (0, 179), "s": (0, 255), "v": (0, 70)},
]
# Gray cougar — medium luminance, very low saturation.
GRAY = [
    {"h": (0, 179), "s": (0, 50), "v": (70, 170)},
]
# Foraging greens (saplings, herbs, mushrooms). Slightly cool greens.
GREEN = [
    {"h": (35, 85), "s": (50, 255), "v": (30, 200)},
]

# Each entry: (group_id, [resources sharing the color filter], hsv ranges,
# morph_open_k, density_min, score_threshold). Resources inside a group compete
# in NMS — the highest-scoring class wins each spatial cluster, resolving
# intra-color-family confusion.
# morph_open_k — morphological-opening kernel side length applied to BOTH the
#   map mask and the template mask. Use it on color groups that the raw mask
#   catches too much of (black text, gray ground); 0 disables it.
# density_min — fraction of the template's mask coverage that a candidate
#   bbox must contain to be kept. Filters CCOEFF-high but sparse hits (text
#   strokes that fall near the silhouette's outline). 0 disables it.
# score_threshold — minimum CCOEFF for a hit. Stricter (~0.7) for noisy
#   color groups (black, gray); default (0.45) for clean groups.
DEF_THR = SCORE_THRESHOLD_DEFAULT
CLASS_GROUPS: list[tuple[str, list[str], list[dict], int, float, float]] = [
    ("red_brown_animals", ["moose", "bear", "wolf", "timberwolf"], RED_BROWN,      0, 0.0,  DEF_THR),
    ("cattails",          ["cattails"],                            CATTAILS_BROWN, 0, 0.0,  DEF_THR),
    # Black: opening removes thin text strokes, density filter rejects sparse
    # hits, and a higher score floor avoids weak-but-color-correct false hits.
    ("black_icons",       ["deer", "salt_deposit", "rabbit", "coal"], BLACK,        2, 0.55, 0.70),
    # Gray: similar reasoning.
    ("gray_animals",      ["cougar"],                               GRAY,          2, 0.55, 0.70),
    ("green_foraging",    ["maple_sapling", "birch_sapling",
                           "rose_hips", "lichen", "reishi"],        GREEN,         0, 0.0,  DEF_THR),
]
# Disambiguator classes — found by the matcher to suppress false hits in
# their color group, but not surfaced in data/region_resources.json.
DISAMBIGUATOR_CLASSES = {"rabbit", "coal", "rose_hips", "lichen", "reishi"}

# Internal classes that get merged into a single output class. Used when
# multiple legend icons differ by a small detail (e.g. maple/birch saplings
# differ only by a tiny M/B letter — too small for reliable matchTemplate
# discrimination) but the user just wants to find "a sapling".
MERGE_INTO = {
    "maple_sapling": "sapling",
    "birch_sapling": "sapling",
}


def color_mask(bgr: np.ndarray, ranges: list[dict], open_k: int = 0) -> np.ndarray:
    """HSV-range mask. Optional morphological opening kills thin strokes (text,
    fine outlines) while preserving filled blob shapes — essential for the
    black-icon group, where the raw color mask catches every dark text label
    on the map. open_k = kernel side length; 0 = no opening."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    out = np.zeros(bgr.shape[:2], dtype=np.uint8)
    for r in ranges:
        lo = np.array([r["h"][0], r["s"][0], r["v"][0]], dtype=np.uint8)
        hi = np.array([r["h"][1], r["s"][1], r["v"][1]], dtype=np.uint8)
        out |= cv2.inRange(hsv, lo, hi)
    if open_k >= 2:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (open_k, open_k))
        out = cv2.morphologyEx(out, cv2.MORPH_OPEN, kernel)
    return out


def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    if inter == 0:
        return 0.0
    a_area = (ax2 - ax1) * (ay2 - ay1)
    b_area = (bx2 - bx1) * (by2 - by1)
    return inter / (a_area + b_area - inter)


def _nms(boxes, iou_thresh):
    boxes = sorted(boxes, key=lambda b: -b[4])
    keep = []
    for box in boxes:
        if all(_iou(box[:4], k[:4]) < iou_thresh for k in keep):
            keep.append(box)
    return keep


def _match_template(map_mask_f: np.ndarray, tpl_mask: np.ndarray, cls: str,
                    H: int, W: int, density_min: float = 0.0,
                    score_threshold: float = SCORE_THRESHOLD_DEFAULT):
    """Multi-scale match. Also tries the horizontally-flipped template so
    animal silhouettes drawn facing the opposite way to the legend swatch
    still get picked up (NMS later collapses overlapping orig/flipped hits).

    density_min — fraction in [0, 1]. After a candidate scores above the
    threshold, also require the candidate bbox's mask coverage to be at
    least this fraction of the template's mask coverage. CCOEFF can score
    high on bboxes with very *few* matching pixels in the right positions
    (e.g. text strokes that happen to land near the deer's outline), so
    this density check filters those — sparse-but-correctly-positioned
    matches don't have enough filled area to be a real silhouette."""
    raw = []
    tpl_h0, tpl_w0 = tpl_mask.shape
    variants = [tpl_mask, cv2.flip(tpl_mask, 1)]
    for scale in SCALES:
        new_w = max(8, int(round(tpl_w0 * scale)))
        new_h = max(8, int(round(tpl_h0 * scale)))
        if new_h >= H or new_w >= W:
            continue
        for variant in variants:
            tpl_s = cv2.resize(variant, (new_w, new_h), interpolation=cv2.INTER_AREA)
            tpl_sum = float(tpl_s.sum())
            if tpl_sum < 50:  # template gone after resize → skip
                continue
            result = cv2.matchTemplate(map_mask_f, tpl_s.astype(np.float32),
                                       cv2.TM_CCOEFF_NORMED)
            legend_top_y = int(H * LEGEND_TOP_FRAC) - new_h
            if 0 < legend_top_y < result.shape[0]:
                result[legend_top_y:, :] = -1
            ys, xs = np.where(result >= score_threshold)
            density_threshold = density_min * tpl_sum if density_min > 0 else 0.0
            for y, x in zip(ys, xs):
                if density_threshold > 0:
                    bbox_sum = float(map_mask_f[y:y+new_h, x:x+new_w].sum())
                    if bbox_sum < density_threshold:
                        continue
                raw.append((int(x), int(y), int(x + new_w), int(y + new_h),
                            float(result[y, x]), cls))
    return raw


def _detect_legend_bboxes(per_resource: dict[str, list[dict]]) -> list[tuple[float, float, float, float]]:
    """Identify legend areas. Two-step:
      1. Seed: find co-located very-high-score (>0.95) hits in multiple
         distinct classes. Legend swatches reproduce the icon exactly so they
         peak high; on-map clusters of different animals at >0.95 are rare.
      2. Grow: extend the cluster bbox to absorb *any* nearby hit (any class,
         any score). Legend entries on different rows but within the same
         bordered rectangle get pulled in this way."""
    # Seed candidates: only very-high-score hits from trusted classes.
    seeds = []
    for cls, items in per_resource.items():
        if cls not in LEGEND_SEED_CLASSES:
            continue
        for h in items:
            if h["score"] < LEGEND_DETECT_SCORE:
                continue
            x1, y1, x2, y2 = h["bbox"]
            seeds.append(((x1 + x2) / 2, (y1 + y2) / 2, cls))

    if len(seeds) < 2:
        return []

    # Build seed clusters by mutual proximity.
    used = [False] * len(seeds)
    seed_groups: list[list[tuple[float, float, str]]] = []
    for i, (cx, cy, cls) in enumerate(seeds):
        if used[i]:
            continue
        members = [(cx, cy, cls)]
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j, (cx2, cy2, cls2) in enumerate(seeds):
                if used[j]:
                    continue
                if any(abs(cx2 - mx) < LEGEND_DETECT_RADIUS
                       and abs(cy2 - my) < LEGEND_DETECT_RADIUS
                       for mx, my, _ in members):
                    members.append((cx2, cy2, cls2))
                    used[j] = True
                    changed = True
        if len({m[2] for m in members}) >= 2:
            seed_groups.append(members)

    if not seed_groups:
        return []

    # All hits (any score) to feed the grow step.
    all_pts: list[tuple[float, float]] = []
    for items in per_resource.values():
        for h in items:
            x1, y1, x2, y2 = h["bbox"]
            all_pts.append(((x1 + x2) / 2, (y1 + y2) / 2))

    clusters = []
    for members in seed_groups:
        xs = [m[0] for m in members]
        ys = [m[1] for m in members]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        # Iteratively absorb nearby hits, but stop growing if the bbox area
        # exceeds LEGEND_MAX_AREA — that's a sign the grow has chained through
        # on-map hits rather than tracing a real legend strip.
        changed = True
        while changed:
            changed = False
            grow = LEGEND_DETECT_RADIUS
            for cx, cy in all_pts:
                if x1 - grow <= cx <= x2 + grow and y1 - grow <= cy <= y2 + grow:
                    nx1, ny1, nx2, ny2 = min(x1, cx), min(y1, cy), max(x2, cx), max(y2, cy)
                    if (nx1, ny1, nx2, ny2) != (x1, y1, x2, y2):
                        if (nx2 - nx1) * (ny2 - ny1) > LEGEND_MAX_AREA:
                            continue
                        x1, y1, x2, y2 = nx1, ny1, nx2, ny2
                        changed = True
        # Reject clusters that don't touch a map edge — real legends are
        # always edge-anchored; a centered cluster is a real animal hotspot.
        touches_edge = (
            x1 <= LEGEND_EDGE_TOLERANCE
            or y1 <= LEGEND_EDGE_TOLERANCE
            or x2 >= 1.0 - LEGEND_EDGE_TOLERANCE
            or y2 >= 1.0 - LEGEND_EDGE_TOLERANCE
        )
        if not touches_edge:
            continue
        pad = 0.015
        clusters.append((x1 - pad, y1 - pad, x2 + pad, y2 + pad))
    return clusters


def _inside(bbox, rects):
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return any(rx1 <= cx <= rx2 and ry1 <= cy <= ry2 for rx1, ry1, rx2, ry2 in rects)


def process_region(region_id: str, map_path: Path) -> dict[str, list[dict]]:
    """Returns {resource: [{bbox, score}]} with bbox as [x1,y1,x2,y2] in 0..1."""
    map_bgr = cv2.imread(str(map_path))
    if map_bgr is None:
        raise RuntimeError(f"could not read {map_path}")
    H, W = map_bgr.shape[:2]

    per_resource: dict[str, list[dict]] = {}
    for group_id, classes, ranges, open_k, density_min, score_thr in CLASS_GROUPS:
        map_mask_f = color_mask(map_bgr, ranges, open_k=open_k).astype(np.float32)
        raw_all = []
        for cls in classes:
            tpl_path = TEMPLATES_DIR / f"{cls}.png"
            if not tpl_path.exists():
                continue
            tpl_bgr = cv2.imread(str(tpl_path))
            tpl_mask = color_mask(tpl_bgr, ranges, open_k=open_k)
            raw_all.extend(_match_template(map_mask_f, tpl_mask, cls, H, W,
                                           density_min=density_min,
                                           score_threshold=score_thr))

        for x1, y1, x2, y2, score, cls in _nms(raw_all, NMS_IOU):
            # Re-tag internal classes onto their merged output class
            # (e.g. maple_sapling + birch_sapling → "sapling").
            out_cls = MERGE_INTO.get(cls, cls)
            per_resource.setdefault(out_cls, []).append({
                "bbox": [round(x1 / W, 5), round(y1 / H, 5),
                         round(x2 / W, 5), round(y2 / H, 5)],
                "score": round(score, 4),
            })

    # Detect and suppress legend areas (auto, no per-region config).
    legend_rects = _detect_legend_bboxes(per_resource)
    if legend_rects:
        filtered = {}
        for cls, items in per_resource.items():
            kept = [h for h in items if not _inside(h["bbox"], legend_rects)]
            if kept:
                filtered[cls] = kept
        per_resource = filtered

    # Drop disambiguator classes (they served their purpose in NMS — winning
    # their spatial regions so target classes don't false-positive there —
    # but the user doesn't care to see them as a navigable category).
    for cls in list(per_resource.keys()):
        if cls in DISAMBIGUATOR_CLASSES:
            del per_resource[cls]

    # Sort each resource's hits by descending score for stable output.
    for cls in per_resource:
        per_resource[cls].sort(key=lambda h: -h["score"])
    return per_resource


def main(argv: list[str]) -> int:
    do_inline = "--inline" in argv
    inline_only = "--inline-only" in argv
    argv = [a for a in argv if a not in ("--inline", "--inline-only")]

    # --inline-only: skip the matcher entirely; just re-inline the existing
    # data/region_resources.json into index.html (useful after editing the
    # data file by hand, or to refresh the inline block without a 3-min
    # full re-run).
    if inline_only:
        if not OUT_FILE.exists():
            print(f"ERR: {OUT_FILE} does not exist; can't inline", file=sys.stderr)
            return 1
        out = json.loads(OUT_FILE.read_text())
        ok = inline_block(INDEX_HTML, "REGION_RESOURCES",
                          "// REGION_RESOURCES_START",
                          "// REGION_RESOURCES_END", out)
        if not ok:
            print("WARN: REGION_RESOURCES sentinels not found in index.html",
                  file=sys.stderr)
            return 1
        print(f"inlined into {INDEX_HTML.relative_to(ROOT)}")
        return 0

    regions = json.loads(REGIONS_FILE.read_text())
    by_id = {r["id"]: r for r in regions}
    targets = argv or [r["id"] for r in regions]

    out: dict[str, dict[str, list[dict]]] = {}
    if OUT_FILE.exists():
        out = json.loads(OUT_FILE.read_text())

    t_total = time.time()
    for region_id in targets:
        if region_id not in by_id:
            print(f"  unknown region: {region_id}", file=sys.stderr)
            continue
        map_path = ROOT / by_id[region_id]["maps"][0]
        if not map_path.exists():
            print(f"  {region_id:<24} missing {map_path}, skip")
            continue
        t0 = time.time()
        per_resource = process_region(region_id, map_path)
        elapsed = time.time() - t0
        counts = "  ".join(f"{c}:{len(h)}" for c, h in sorted(per_resource.items()))
        print(f"  {region_id:<24} {elapsed:5.1f}s  {counts}")
        out[region_id] = per_resource

    OUT_FILE.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\ntotal: {time.time()-t_total:.1f}s, wrote {OUT_FILE.relative_to(ROOT)}")

    if do_inline:
        ok = inline_block(INDEX_HTML, "REGION_RESOURCES",
                          "// REGION_RESOURCES_START",
                          "// REGION_RESOURCES_END", out)
        if ok:
            print(f"inlined into {INDEX_HTML.relative_to(ROOT)}")
        else:
            print("WARN: REGION_RESOURCES sentinels not found in index.html",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
