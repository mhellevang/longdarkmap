"""Scrape per-place crafting-tool tags from the Long Dark wiki.

The wiki carries two structured categories:
  - Category:Locations_with_a_forge
  - Category:Locations_with_a_workbench
Each member is a location page whose title already lines up with an entry in
data/places_index.json. We join on (name, region) and emit a per-region map of
tool tags. Manual additions for tools the wiki doesn't categorise (ammunition
workbench, milling machine, ...) live in data/crafting_tools_extra.json.

Output: data/crafting_tools.json — {region: {place: [tool, ...]}}, mirroring
the shape of place_boxes.json so the runtime can join them by (region, place).

Usage:
    python3 tools/scrape_tools.py
    python3 tools/scrape_tools.py --inline   # also bundle into index.html

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from _inline import inline_block
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLACES_FILE = ROOT / "data" / "places_index.json"
EXTRA_FILE = ROOT / "data" / "crafting_tools_extra.json"
TILES_DIR = ROOT / "data" / "tiles"
OUT = ROOT / "data" / "crafting_tools.json"
INDEX_HTML = ROOT / "index.html"

API = "https://thelongdark.fandom.com/api.php"
USER_AGENT = "longdarkmap-scraper/1.0 (https://github.com/mathiashellevang/longdarkmap)"

# Wiki category -> tool tag.
CATEGORIES: list[tuple[str, str]] = [
    ("Locations with a forge", "forge"),
    ("Locations with a workbench", "workbench"),
]

START = "// PLACE_TOOLS_START"
END = "// PLACE_TOOLS_END"


def api_get(params: dict) -> dict:
    qs = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def fetch_category(category: str) -> list[str]:
    titles: list[str] = []
    cmcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": 500,
            "cmtype": "page",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        data = api_get(params)
        for m in data.get("query", {}).get("categorymembers", []):
            if m["ns"] == 0:
                titles.append(m["title"])
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        cmcontinue = cont
    return titles


def inline_into_html(tools: dict) -> bool:
    return inline_block(INDEX_HTML, "PLACE_TOOLS", START, END, tools)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inline", action="store_true",
                   help="also inline the result into index.html between sentinels")
    args = p.parse_args(argv)

    places = json.loads(PLACES_FILE.read_text())
    # name -> [region, ...]  (a name can recur across regions, rarely)
    name_to_regions: dict[str, list[str]] = {}
    for entry in places:
        name_to_regions.setdefault(entry["name"], []).append(entry["region"])

    # {region: {place: set[tool]}}
    tools: dict[str, dict[str, set[str]]] = {}
    summary: list[tuple[str, int, int]] = []
    unmatched: list[tuple[str, str]] = []

    for category, tag in CATEGORIES:
        try:
            titles = fetch_category(category)
        except urllib.error.URLError as e:
            print(f"  {category}: {e}", file=sys.stderr)
            continue
        matched = 0
        for title in titles:
            regions = name_to_regions.get(title)
            if not regions:
                unmatched.append((tag, title))
                continue
            for region in regions:
                tools.setdefault(region, {}).setdefault(title, set()).add(tag)
            matched += 1
        summary.append((tag, len(titles), matched))
        time.sleep(0.2)

    extras_added = 0
    if EXTRA_FILE.exists():
        for entry in json.loads(EXTRA_FILE.read_text()):
            region = entry["region"]
            name = entry["name"]
            for tag in entry["tools"]:
                bucket = tools.setdefault(region, {}).setdefault(name, set())
                if tag not in bucket:
                    bucket.add(tag)
                    extras_added += 1

    # Vision-LLM amenity passes write data/tiles/<region>/amenities/result.json
    # with the same {place: [tags]} shape. Layer them on top of the wiki
    # categories — vision adds bed/stove/first_aid/ice_fishing_hut/etc. that
    # the wiki doesn't categorise. Wiki tags stay authoritative for forge and
    # workbench (vision recall on those is unreliable on distributed-icon
    # maps), and amenity passes never *remove* a wiki tag.
    vision_added = 0
    vision_regions = 0
    if TILES_DIR.exists():
        for region_dir in sorted(TILES_DIR.iterdir()):
            result = region_dir / "amenities" / "result.json"
            if not result.exists():
                continue
            doc = json.loads(result.read_text())
            region = doc.get("region_id") or region_dir.name
            counted_region = False
            for name, tags in (doc.get("places") or {}).items():
                if not tags:
                    continue
                bucket = tools.setdefault(region, {}).setdefault(name, set())
                for tag in tags:
                    if tag not in bucket:
                        bucket.add(tag)
                        vision_added += 1
                        if not counted_region:
                            vision_regions += 1
                            counted_region = True

    serialised: dict[str, dict[str, list[str]]] = {
        region: {name: sorted(tags) for name, tags in sorted(places.items())}
        for region, places in sorted(tools.items())
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(serialised, indent=2) + "\n")

    total_entries = sum(len(v) for v in serialised.values())
    print(f"Wrote {total_entries} place(s) across {len(serialised)} region(s) -> {OUT.relative_to(ROOT)}")
    for tag, fetched, matched in summary:
        marker = " " if matched == fetched else "!"
        print(f"  {marker} {tag:<12} wiki={fetched:>3}  matched={matched:>3}")
    if extras_added:
        print(f"  + {extras_added} entry/entries from {EXTRA_FILE.name}")
    if vision_added:
        print(f"  + {vision_added} tag(s) from {vision_regions} region(s) via amenities/result.json")
    if unmatched:
        print("  unmatched (no place_index entry — fix or add to crafting_tools_extra.json):",
              file=sys.stderr)
        for tag, title in unmatched:
            print(f"    {tag:<12} {title!r}", file=sys.stderr)

    if args.inline:
        if inline_into_html(serialised):
            print(f"Inlined into {INDEX_HTML.relative_to(ROOT)}")
        else:
            print(f"warn: sentinels {START}/{END} not found in index.html — not inlined",
                  file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
