"""Inline data/regions.json and data/region_links.json into index.html.

The frontend, build_tiles.py, scrape_places.py, and download_maps.py all read
regions.json directly. The inlined copy in index.html exists so the page stays
single-file and works offline / on file://.

`region_links.json` (produced by `extract_region_links.py`) maps each region
to the red "To <region>" perimeter labels that should render as clickable
exits in the detail view.

Usage:
    python3 tools/inline_regions.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from _inline import inline_block

ROOT = Path(__file__).parent.parent
INDEX_HTML = ROOT / "index.html"

BLOCKS = [
    {
        "file": ROOT / "data" / "regions.json",
        "start": "// REGIONS_START",
        "end": "// REGIONS_END",
        "var": "REGIONS",
    },
    {
        "file": ROOT / "data" / "region_links.json",
        "start": "// REGION_LINKS_START",
        "end": "// REGION_LINKS_END",
        "var": "REGION_LINKS",
    },
]


def main() -> int:
    for block in BLOCKS:
        data = json.loads(block["file"].read_text())
        if not inline_block(INDEX_HTML, block["var"], block["start"], block["end"], data):
            print(
                f"sentinels {block['start']}/{block['end']} not found in {INDEX_HTML.name}",
                file=sys.stderr,
            )
            return 1
        count = len(data) if isinstance(data, (list, dict)) else 0
        print(f"  inlined {block['var']:<14} ({count} entries) from {block['file'].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
