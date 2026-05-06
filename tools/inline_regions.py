"""Inline data/regions.json into index.html between REGIONS_START/END sentinels.

The frontend, build_tiles.py, scrape_places.py, and download_maps.py all read
regions.json directly. The inlined copy in index.html exists so the page stays
single-file and works offline / on file://.

Usage:
    python3 tools/inline_regions.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REGIONS_FILE = ROOT / "data" / "regions.json"
INDEX_HTML = ROOT / "index.html"
START = "// REGIONS_START"
END = "// REGIONS_END"


def main() -> int:
    regions = json.loads(REGIONS_FILE.read_text())
    html = INDEX_HTML.read_text()
    pattern = re.compile(rf"({re.escape(START)}\n).*?(\n\s*{re.escape(END)})", re.S)
    if not pattern.search(html):
        print(f"sentinels {START}/{END} not found in {INDEX_HTML.name}", file=sys.stderr)
        return 1
    payload = f"const REGIONS = {json.dumps(regions, indent=2)};"
    INDEX_HTML.write_text(pattern.sub(lambda m: m.group(1) + payload + m.group(2), html))
    print(f"Inlined {len(regions)} regions into {INDEX_HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
