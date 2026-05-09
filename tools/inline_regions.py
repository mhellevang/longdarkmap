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
import re
import sys
from pathlib import Path

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


def inline(html: str, block: dict) -> tuple[str, int]:
    data = json.loads(block["file"].read_text())
    start, end, var = block["start"], block["end"], block["var"]
    pattern = re.compile(rf"({re.escape(start)}\n).*?(\n\s*{re.escape(end)})", re.S)
    if not pattern.search(html):
        print(f"sentinels {start}/{end} not found in {INDEX_HTML.name}", file=sys.stderr)
        sys.exit(1)
    payload = f"const {var} = {json.dumps(data, indent=2)};"
    new_html = pattern.sub(lambda m: m.group(1) + payload + m.group(2), html)
    count = len(data) if isinstance(data, (list, dict)) else 0
    return new_html, count


def main() -> int:
    html = INDEX_HTML.read_text()
    for block in BLOCKS:
        html, count = inline(html, block)
        print(f"  inlined {block['var']:<14} ({count} entries) from {block['file'].name}")
    INDEX_HTML.write_text(html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
