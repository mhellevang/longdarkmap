"""Scrape per-region location lists from the Long Dark wiki on Fandom.

For each region, hits the MediaWiki API for `Category:Locations_in_<Region>`
and collects the page titles. Output: data/places_index.json — a flat list of
{name, region} that powers the world-view global search.

The wiki text is CC-BY-SA 3.0; place names are factual references.

Usage:
    .venv/bin/python scrape_places.py
    .venv/bin/python scrape_places.py --inline   # also bundle into index.html

No third-party dependencies — only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "places_index.json"
INDEX_HTML = ROOT / "index.html"

API = "https://thelongdark.fandom.com/api.php"
USER_AGENT = "longdarkmap-scraper/1.0 (https://github.com/mathiashellevang/longdarkmap)"

# (id, display name, wiki category titles). One region can pull from multiple
# categories (e.g. Keeper's Pass North + South). Empty list means no wiki
# coverage — fine; the region just won't contribute to the search index.
REGIONS: list[tuple[str, str, list[str]]] = [
    ("mystery_lake",          "Mystery Lake",           ["Locations in Mystery Lake"]),
    ("coastal_highway",       "Coastal Highway",        ["Locations in Coastal Highway"]),
    ("pleasant_valley",       "Pleasant Valley",        ["Locations in Pleasant Valley"]),
    ("desolation_point",      "Desolation Point",       ["Locations in Desolation Point"]),
    ("timberwolf_mountain",   "Timberwolf Mountain",    ["Locations in Timberwolf Mountain"]),
    ("forlorn_muskeg",        "Forlorn Muskeg",         ["Locations in Forlorn Muskeg"]),
    ("broken_railroad",       "Broken Railroad",        ["Locations in Broken Railroad"]),
    ("bleak_inlet",           "Bleak Inlet",            ["Locations in Bleak Inlet"]),
    ("hushed_river_valley",   "Hushed River Valley",    ["Locations in Hushed River Valley"]),
    ("mountain_town",         "Mountain Town",          ["Locations in Mountain Town"]),
    ("ash_canyon",            "Ash Canyon",             ["Locations in Ash Canyon"]),
    ("blackrock",             "Blackrock",              ["Locations in Blackrock"]),
    ("forsaken_airfield",     "Forsaken Airfield",      ["Locations in Forsaken Airfield"]),
    ("sundered_pass",         "Sundered Pass",          ["Locations in Sundered Pass"]),
    ("zone_of_contamination", "Zone of Contamination",  ["Locations in Zone of Contamination"]),
    ("crumbling_highway",     "Crumbling Highway",      ["Locations in Crumbling Highway"]),
    ("far_range",             "Far Range Branch Line",  ["Locations in Far Range Branch Line"]),
    ("transfer_pass",         "Transfer Pass",          ["Locations in Transfer Pass"]),
    ("ravine",                "Ravine",                 ["Locations in The Ravine"]),
    ("winding_river",         "Winding River & Carter Hydro Dam", []),
    ("keepers_pass",          "Keeper's Pass",          ["Locations in Keeper's Pass North",
                                                         "Locations in Keeper's Pass South"]),
]

# Wiki pages that aren't real in-game locations (collection / index pages).
EXCLUDE_TITLES = {
    "Locations",
    "List of Locations",
    "Sandbox Mode",
}


def api_get(params: dict) -> dict:
    qs = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def fetch_category(category: str) -> list[str]:
    """Page titles in a category (ns=0 only — articles, not subcategories)."""
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
            if m["ns"] == 0 and m["title"] not in EXCLUDE_TITLES:
                titles.append(m["title"])
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        cmcontinue = cont
    return titles


# Inline-bundle helpers ────────────────────────────────────────────────────
START = "// PLACES_INDEX_START"
END = "// PLACES_INDEX_END"


def inline_into_html(places: list[dict]) -> bool:
    html = INDEX_HTML.read_text()
    pattern = re.compile(rf"({re.escape(START)}\n).*?(\n\s*{re.escape(END)})", re.S)
    if not pattern.search(html):
        return False
    payload = f"const PLACES_INDEX = {json.dumps(places, indent=2)};"
    INDEX_HTML.write_text(pattern.sub(lambda m: m.group(1) + payload + m.group(2), html))
    return True


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inline", action="store_true",
                   help="also inline the result into index.html between sentinels")
    args = p.parse_args(argv)

    all_places: list[dict] = []
    summary: list[tuple[str, int]] = []

    for region_id, _, categories in REGIONS:
        seen: set[str] = set()
        for category in categories:
            try:
                titles = fetch_category(category)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    titles = []
                else:
                    print(f"  {region_id} ({category}): HTTP {e.code}", file=sys.stderr)
                    titles = []
            except urllib.error.URLError as e:
                print(f"  {region_id} ({category}): {e.reason}", file=sys.stderr)
                titles = []
            for t in titles:
                if t in seen:
                    continue
                seen.add(t)
                all_places.append({"name": t, "region": region_id})
            time.sleep(0.2)  # gentle on the API
        summary.append((region_id, len(seen)))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_places.sort(key=lambda p: (p["region"], p["name"].lower()))
    OUT.write_text(json.dumps(all_places, indent=2) + "\n")

    total = len(all_places)
    print(f"Wrote {total} places across {len(REGIONS)} regions -> {OUT.relative_to(ROOT)}")
    for region_id, n in summary:
        marker = " " if n else "·"
        print(f"  {marker} {region_id:<24} {n:>3}")

    if args.inline:
        if inline_into_html(all_places):
            print(f"Inlined into {INDEX_HTML.relative_to(ROOT)}")
        else:
            print(f"warn: sentinels {START}/{END} not found in index.html — not inlined",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
