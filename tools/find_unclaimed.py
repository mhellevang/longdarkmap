"""Find OCR detections that look like place labels but aren't claimed by any
wiki entry — i.e. labels printed on the map that the wiki doesn't list.

For each region:
  1. Drop detections whose text matches a known wiki name (or one of our
     manual additions in places_extra.json), regardless of tile.
  2. Drop legend / credits / quest-line text via a hard-coded stoplist.
  3. Merge vertically-adjacent same-tile detections so multi-line labels
     surface as one candidate (e.g. SHOULDER + LAKE → SHOULDER LAKE).
  4. Compute the full-image-norm bbox for each remaining candidate so it
     can be appended to data/place_boxes_overrides.json directly.

Writes data/unclaimed_candidates.json for review.

Usage:
    .venv/bin/python find_unclaimed.py                # all regions
    .venv/bin/python find_unclaimed.py mystery_lake   # one region
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TILES_DIR = ROOT / "data" / "tiles"
PLACES_INDEX = ROOT / "data" / "places_index.json"
EXTRAS = ROOT / "data" / "places_extra.json"
OVERRIDES = ROOT / "data" / "place_boxes_overrides.json"
OUT = ROOT / "data" / "unclaimed_candidates.json"

DIGIT_RE = re.compile(r"^[\d\s,.\-#]+$")
PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")
APOS_S_RE = re.compile(r"'([A-Z])")
TO_PREFIX_RE = re.compile(r"^to\s+", re.I)  # "TO MOUNTAIN TOWN" etc.
QUEST_HINT_RE = re.compile(r"\bquest\b|\blog\b|\bpolaroid\b|\bbadge\b|\btool belt\b", re.I)

# Region display names ("FORSAKEN AIRFIELD" prints as a title on the map; not
# a place within the region). From the REGIONS array in index.html.
REGION_TITLES = {
    "MYSTERY LAKE", "COASTAL HIGHWAY", "PLEASANT VALLEY", "DESOLATION POINT",
    "TIMBERWOLF MOUNTAIN", "FORLORN MUSKEG", "BROKEN RAILROAD", "BLEAK INLET",
    "HUSHED RIVER VALLEY", "MOUNTAIN TOWN", "ASH CANYON", "BLACKROCK",
    "FORSAKEN AIRFIELD", "SUNDERED PASS", "ZONE OF CONTAMINATION",
    "CRUMBLING HIGHWAY", "FAR RANGE BRANCH LINE", "TRANSFER PASS", "RAVINE",
    "WINDING RIVER", "KEEPER'S PASS", "OLD ISLAND CONNECTOR",
}

# Legend-block text (bottom-left tile on most maps). All entries normalized
# (uppercase, no punctuation, no parens) for matching.
LEGEND_TERMS = {
    # Credits / metadata block
    "THE LONG DARK", "FAR TERRITORY", "ORIGINAL MAP DESIGN BY",
    "MADE IN COOPERATION WITH", "CREATED BY", "STM SANTANA",
    "THE RIDDLER", "JAH HAT",
    # Legend column headers
    "NAME", "LOCATIONS", "OFFICIAL NAME", "UNMARKED NAME",
    "INACCESSIBLE LOCATIONS",
    # Legend swatches
    "OFFICIAL", "UNMARKED", "INACCESSIBLE", "WORKBENCH", "FORGE",
    "COLLECTIBLE", "VEHICLE", "TRANSMITTER", "MILLING", "AMMUNITION",
    "CONTAINER", "WOODWORKING", "POSSIBLE", "POSSIBLE HUNTERS",
    "POSSIBLE SPELUNKERS", "PATH", "SHORTCUT", "BRIDGE", "TUNNEL",
    "VISTA", "LEDGES", "CRAMPONS", "POLAR BEAR", "LICHEN", "COAL",
    "AIRCRAFT", "BASEMENT", "TRAILER", "CABIN", "BARN", "CRASH SITE",
    "DESTROYED", "SHELTER", "SHED", "VALLEY", "MOUNTAIN", "FOREST",
    "FOREST CAVE", "ROAD COLLAPSE", "HIGHER", "LOWER", "HEIGHT LEVEL",
    "BUILDINGS", "BANK", "CHURCH", "STORE", "GARAGE", "FARM",
    "ABANDONED MINE", "POWER PLANT", "SUPPLY", "LAST PROSPECT",
    "PREPPER", "CACHE", "HUNTERS", "ICE FISHING HUT", "FISHING HUT",
    "FISHING CAMP",
    # Quest-line annotations (Forsaken Airfield etc.)
    "SIGNAL VOID", "SIGNAL VOID QUEST", "SIGNAL VOID QUEST LINE",
    "SECURITY CHIEFS", "SECURITY CHIEFS LOG", "LAST HORIZON",
    "ID BADGE", "HANDHELD",
    # Common OCR fragments / typos that we know aren't places
    "BRIDGI", "FOOTRES", "ABAND", "FORE", "CLEA", "CUTT", "POLA",
    "WOODWO", "PILLARS", "CONTAIN", "SCRA", "LOCA", "REC", "CEN",
    # Building-component descriptors that get confused with labels
    "WATCHTOWER", "INFIRMARY", "WORKSHOP", "GUARDHOUSE", "CAFETERIA",
    "LIBRARY", "DESTROYED SHED", "DESTROYED CAR",
    # Single-word generics that are real on-map descriptors but never the
    # canonical name of a place by themselves (the named place would carry
    # a multi-word label)
    "PASS", "GATE", "TRACK", "SUMMIT", "CAVE", "FALLS", "HUT", "DEN",
    "CAR", "FALLEN",
}


def normalize(s: str) -> str:
    """Normalize text for name comparison: uppercase, strip punctuation."""
    return re.sub(r"[^A-Z0-9 ]", "", s.upper()).strip()


def smart_title(s: str) -> str:
    """Title-case OCR text, keeping apostrophe-S lowercase ("Angler's", not "Angler'S")."""
    return APOS_S_RE.sub(lambda m: "'" + m.group(1).lower(), s.title())


def load_known_names(region_id: str) -> list[str]:
    """All names already known for the region (wiki + manual extras), normalized."""
    names: list[str] = []
    for path in (PLACES_INDEX, EXTRAS):
        if not path.exists():
            continue
        for p in json.loads(path.read_text()):
            if p.get("region") != region_id:
                continue
            stripped = PAREN_RE.sub("", p["name"])
            n = normalize(stripped)
            if n:
                names.append(n)
    return names


def is_claimed_by_known(text_norm: str, known: list[str]) -> bool:
    """A candidate is 'claimed' if its normalized text appears as a substring
    in any known name OR vice versa (handles "POST OFFICE" vs "MILTON POST
    OFFICE" both ways)."""
    if not text_norm:
        return False
    for n in known:
        if text_norm == n:
            return True
        if text_norm in n:
            return True
        if n in text_norm:
            return True
    return False


def is_metadata(text: str) -> bool:
    if TO_PREFIX_RE.match(text):  # "TO MOUNTAIN TOWN" — direction connector
        return True
    if QUEST_HINT_RE.search(text):  # quest-line text
        return True
    n = normalize(text)
    if not n:
        return True
    if n in LEGEND_TERMS or n in REGION_TITLES:
        return True
    # Prefix / suffix substring against the legend stoplist
    for term in LEGEND_TERMS:
        if n.startswith(term + " ") or n.endswith(" " + term):
            return True
    return False


def looks_like_label(text: str, confidence: float) -> bool:
    if confidence < 0.6:
        return False
    t = text.strip()
    if len(t) < 3:
        return False
    if DIGIT_RE.match(t):
        return False
    words = t.split()
    if len(words) > 5:  # paragraphs aren't labels
        return False
    capitalized = sum(1 for w in words if w and w[0].isupper())
    if capitalized / len(words) < 0.7:
        return False
    return True


def merge_adjacent(detections: list[dict]) -> list[dict]:
    """Merge vertically-adjacent same-tile detections that look like one label."""
    items = sorted(detections, key=lambda d: (d["bbox"][1], d["bbox"][0]))
    used = [False] * len(items)
    merged: list[dict] = []
    for i, d in enumerate(items):
        if used[i]:
            continue
        group = [d]
        used[i] = True
        cur_bottom = d["bbox"][3]
        cur_h = d["bbox"][3] - d["bbox"][1]
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            e = items[j]
            x1, y1, x2, y2 = e["bbox"]
            h = y2 - y1
            # Vertical gap small enough to be a line break
            if y1 - cur_bottom > 1.5 * min(cur_h, h):
                continue
            # Horizontal overlap with the group's combined x-range
            gx1 = min(g["bbox"][0] for g in group)
            gx2 = max(g["bbox"][2] for g in group)
            ow = max(0.0, min(x2, gx2) - max(x1, gx1))
            if ow < 0.5 * min(x2 - x1, gx2 - gx1):
                continue
            group.append(e)
            used[j] = True
            cur_bottom = max(cur_bottom, y2)
            cur_h = h
        if len(group) > 1:
            merged.append({
                "tile": d["tile"],
                "text": " ".join(g["text"] for g in group),
                "bbox": [
                    min(g["bbox"][0] for g in group),
                    min(g["bbox"][1] for g in group),
                    max(g["bbox"][2] for g in group),
                    max(g["bbox"][3] for g in group),
                ],
                "confidence": round(min(g["confidence"] for g in group), 3),
            })
        else:
            merged.append(d)
    return merged


def tile_to_full(tile_bbox_norm: list[float], bbox_in_tile: list[float]) -> list[float]:
    tx0, ty0, tx1, ty1 = tile_bbox_norm
    tw, th = tx1 - tx0, ty1 - ty0
    return [
        round(tx0 + bbox_in_tile[0] * tw, 5),
        round(ty0 + bbox_in_tile[1] * th, 5),
        round(tx0 + bbox_in_tile[2] * tw, 5),
        round(ty0 + bbox_in_tile[3] * th, 5),
    ]


def load_matched_full_bboxes(region_id: str, tiles_meta: dict) -> list[list[float]]:
    """Every place's bbox in full-image norm coords — from result.json (matcher
    output) plus user overrides. Used for spatial-claim of candidates whose
    text didn't fuzzy-match a known name."""
    bboxes: list[list[float]] = []
    result_path = TILES_DIR / region_id / "result.json"
    if result_path.exists():
        for r in json.loads(result_path.read_text()).get("results", []):
            tbb = tiles_meta.get(r["tile"], {}).get("bbox_norm")
            if tbb:
                bboxes.append(tile_to_full(tbb, r["bbox_in_tile"]))
    if OVERRIDES.exists():
        for name, bbox in json.loads(OVERRIDES.read_text()).get(region_id, {}).items():
            bboxes.append(list(bbox))
    return bboxes


def claimed_by_overlap(cand_full: list[float], matched: list[list[float]]) -> bool:
    cx = (cand_full[0] + cand_full[2]) / 2
    cy = (cand_full[1] + cand_full[3]) / 2
    for mb in matched:
        if mb[0] <= cx <= mb[2] and mb[1] <= cy <= mb[3]:
            return True
    return False


def find_for_region(region_id: str) -> list[dict]:
    region_dir = TILES_DIR / region_id
    ocr_path = region_dir / "ocr_detections.json"
    manifest_path = region_dir / "manifest.json"
    if not ocr_path.exists() or not manifest_path.exists():
        return []
    ocr = json.loads(ocr_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    tiles_meta = {f"{t['row']}_{t['col']}": t for t in manifest["tiles"]}
    known = load_known_names(region_id)
    matched_full = load_matched_full_bboxes(region_id, tiles_meta)

    # 1. Generic noise filter only. Don't apply known-names or stoplist
    #    yet — multi-line labels often have one line that looks generic
    #    on its own (e.g. "CHURCH" is in the stoplist but
    #    "ST. CHRISTOPHER'S CHURCH" is a legitimate label).
    raw: list[dict] = []
    for tile_id, items in ocr.get("tiles", {}).items():
        for d in items:
            if not looks_like_label(d["text"], d["confidence"]):
                continue
            raw.append({
                "tile": tile_id,
                "text": d["text"],
                "bbox": d["bbox"],
                "confidence": d["confidence"],
            })

    # 2. Multi-line merge per tile.
    by_tile: dict[str, list[dict]] = {}
    for c in raw:
        by_tile.setdefault(c["tile"], []).append(c)
    merged: list[dict] = []
    for tile_id, items in by_tile.items():
        merged.extend(merge_adjacent(items))

    # 3. NOW apply the stoplist + known-name filter to the merged labels.
    final: list[dict] = []
    for c in merged:
        n = normalize(PAREN_RE.sub("", c["text"]))
        if is_claimed_by_known(n, known):
            continue
        if is_metadata(c["text"]):
            continue
        # Drop word fragments / single short words (OCR clipping at tile edges
        # or random partial detections in the legend block).
        chars_no_space = c["text"].replace(" ", "")
        words = c["text"].split()
        if len(chars_no_space) < 6 and len(words) < 2:
            continue
        c["bbox_full"] = tile_to_full(tiles_meta[c["tile"]]["bbox_norm"], c["bbox"])
        # Spatial claim: candidate's full-image center sits inside an already-
        # matched bbox → the matcher already covers this label (under a
        # different OCR spelling).
        if claimed_by_overlap(c["bbox_full"], matched_full):
            continue
        c["suggested_name"] = smart_title(c["text"])
        final.append(c)

    # 4. Stable cross-tile dedupe by suggested_name (overlap tiles can show
    #    the same merged label twice).
    by_name: dict[str, dict] = {}
    for c in final:
        key = normalize(c["text"])
        if key in by_name:
            # Keep the one whose bbox is more central inside its tile (i.e.
            # less likely to be a tile-edge clip).
            old = by_name[key]
            old_dist = abs((old["bbox"][0] + old["bbox"][2]) / 2 - 0.5)
            new_dist = abs((c["bbox"][0] + c["bbox"][2]) / 2 - 0.5)
            if new_dist < old_dist:
                by_name[key] = c
        else:
            by_name[key] = c
    deduped = sorted(by_name.values(), key=lambda c: (c["tile"], c["bbox"][1], c["bbox"][0]))
    return deduped


def main(argv: list[str]) -> int:
    if argv:
        regions = argv
    else:
        regions = sorted(d.name for d in TILES_DIR.iterdir() if d.is_dir())

    out: dict[str, list[dict]] = {}
    total = 0
    for r in regions:
        candidates = find_for_region(r)
        if not candidates:
            continue
        out[r] = candidates
        total += len(candidates)
        print(f"\n## {r} ({len(candidates)} candidate(s))")
        for c in candidates:
            conf = c["confidence"]
            print(f"  {c['tile']}  {c['suggested_name']!r:<32}  "
                  f"(OCR: {c['text']!r}, conf={conf})")

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"\n--- {total} total candidate(s) across {len(out)} region(s) "
          f"-> wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
