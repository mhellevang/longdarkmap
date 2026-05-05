"""Stage 1 of the v3 place-box pipeline: deterministic text-detection OCR.

For each region's 9 tile images, run macOS Vision OCR (via `ocrmac`) and
collect every detected text fragment with its tile-relative bbox in
top-left-origin [0..1] coords. Write the per-region detections to
`data/tiles/<region>/ocr_detections.json`.

This replaces the vision-LLM step from v1/v2 with deterministic, pixel-
precise text detection. Stage 2 (a separate Claude Code subagent per
region) consumes these detections and matches them to the canonical
wiki names from `task.json`, writing the existing `result.json` schema.

Usage:
    python3 ocr_run.py                    # all 21 regions
    python3 ocr_run.py forsaken_airfield  # one region (pre-flight check)
    python3 ocr_run.py mystery_lake mountain_town
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ocrmac import ocrmac

ROOT = Path(__file__).parent.parent
TILES_DIR = ROOT / "data" / "tiles"

# Vision returns occasional very-low-confidence noise (random pixel artefacts
# read as text). Drop those — the matcher would just have to ignore them.
MIN_CONFIDENCE = 0.4

# `accurate` is slower but materially better on stylized fonts; we're only
# running ~9 tiles per region so the wall-clock cost is fine.
RECOGNITION_LEVEL = "accurate"


def ocr_tile(path: Path) -> list[dict]:
    """Run Apple Vision OCR on one tile, return top-left-origin bboxes."""
    annotations = ocrmac.OCR(
        str(path), recognition_level=RECOGNITION_LEVEL
    ).recognize()
    out = []
    for text, conf, (x, y, w, h) in annotations:
        if conf < MIN_CONFIDENCE:
            continue
        # Apple Vision returns origin at BOTTOM-left in normalised coords.
        # The downstream pipeline (manifest tiles, merge_boxes.py) uses
        # TOP-left origin, so flip y.
        x1 = x
        y1 = 1.0 - y - h
        x2 = x + w
        y2 = 1.0 - y
        out.append({
            "text": text,
            "bbox": [round(x1, 5), round(y1, 5), round(x2, 5), round(y2, 5)],
            "confidence": round(float(conf), 3),
        })
    # Sort top-to-bottom, left-to-right so downstream consumers get a
    # predictable order (helps the matcher with #1/#2 instance suffixes).
    out.sort(key=lambda d: (d["bbox"][1], d["bbox"][0]))
    return out


def ocr_region(region_id: str) -> dict:
    region_dir = TILES_DIR / region_id
    manifest = json.loads((region_dir / "manifest.json").read_text())
    tiles_out: dict[str, list[dict]] = {}
    for tile in manifest["tiles"]:
        tile_id = f"{tile['row']}_{tile['col']}"
        tile_path = region_dir / tile["file"]
        if not tile_path.exists():
            continue
        tiles_out[tile_id] = ocr_tile(tile_path)
    return {"region_id": region_id, "tiles": tiles_out}


def main(argv: list[str]) -> int:
    if not TILES_DIR.exists():
        print(f"missing: {TILES_DIR}", file=sys.stderr)
        return 1

    if argv:
        regions = argv
    else:
        regions = sorted(d.name for d in TILES_DIR.iterdir() if d.is_dir())

    for region_id in regions:
        region_dir = TILES_DIR / region_id
        if not (region_dir / "manifest.json").exists():
            print(f"  · {region_id:<24} no manifest, skip")
            continue
        detections = ocr_region(region_id)
        out = region_dir / "ocr_detections.json"
        out.write_text(json.dumps(detections, indent=2, ensure_ascii=False) + "\n")
        n = sum(len(v) for v in detections["tiles"].values())
        print(f"    {region_id:<24} {n:>4} text fragments across {len(detections['tiles'])} tiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
