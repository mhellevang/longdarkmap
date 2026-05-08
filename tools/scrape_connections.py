"""Scrape the `connections` field from each region's wiki Infobox.

Each region's page on thelongdark.fandom.com carries an Infobox/Region with
a `connections` field listing neighbouring regions plus optional "via X"
transition annotations. This dumps the raw + parsed result to
data/regions_connections_raw.json. The symmetric union of those edges was
hand-merged into data/regions.json's `adjacencies` field — re-run only if
the wiki adds a region or changes a connection, then reconcile by hand and
re-run tools/inline_regions.py.

Stdlib only.
"""
import json, re, urllib.parse, urllib.request, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
regions = json.loads((ROOT / "data" / "regions.json").read_text())

API = "https://thelongdark.fandom.com/api.php"
UA = {"User-Agent": "longdarkmap-scraper/1.0"}

# Wiki page title per region (most have a "(region)" suffix to disambiguate).
# Manual map for the few ambiguous ones.
WIKI_TITLE = {
    "mystery_lake": "Mystery Lake (region)",
    "coastal_highway": "Coastal Highway",
    "pleasant_valley": "Pleasant Valley",
    "desolation_point": "Desolation Point",
    "timberwolf_mountain": "Timberwolf Mountain",
    "forlorn_muskeg": "Forlorn Muskeg",
    "broken_railroad": "Broken Railroad",
    "bleak_inlet": "Bleak Inlet",
    "hushed_river_valley": "Hushed River Valley",
    "mountain_town": "Mountain Town",
    "ash_canyon": "Ash Canyon",
    "blackrock": "Blackrock",
    "forsaken_airfield": "Forsaken Airfield",
    "sundered_pass": "Sundered Pass",
    "zone_of_contamination": "Zone of Contamination",
    "crumbling_highway": "Crumbling Highway",
    "far_range": "Far Range Branch Line",
    "transfer_pass": "Transfer Pass",
    "ravine": "The Ravine",
    "winding_river": "Winding River",
    "keepers_pass": "Keeper's Pass",
}

# Map region display names (as they appear in wiki link text) → our region id.
NAME_TO_ID = {r["name"]: r["id"] for r in regions}
# Aliases for wiki names that don't exactly match our display name.
NAME_TO_ID.update({
    "The Ravine": "ravine",
    "Ravine": "ravine",
    "Winding River": "winding_river",
    "Winding River & Carter Hydro Dam": "winding_river",
    "Carter Hydro Dam": "winding_river",
    "Mystery Lake": "mystery_lake",
    "Far Range Branch Line": "far_range",
    "Keeper's Pass": "keepers_pass",
    "Keepers Pass": "keepers_pass",
})


def fetch_wikitext(title: str) -> str:
    qs = urllib.parse.urlencode({"action": "parse", "page": title, "format": "json", "prop": "wikitext", "redirects": "1"})
    req = urllib.request.Request(f"{API}?{qs}", headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode())
    return d.get("parse", {}).get("wikitext", {}).get("*", "")


def extract_connections(wikitext: str) -> str | None:
    # Multiline-tolerant: connections runs from |connections= to next |key=
    m = re.search(r"\|connections\s*=\s*(.*?)(?:\n\|[a-z]+\s*=|\}\})", wikitext, re.S | re.I)
    return m.group(1).strip() if m else None


def parse_links(connections: str) -> list[tuple[str, str | None]]:
    # Yields (target_region_name, via_name_or_None) tuples.
    out = []
    # Strip nested italic ''(via [[X]])'' first → record via separately, then
    # scan for the lead [[Region]] of each entry.
    # Walk the string segment by segment using comma/<br /> as separators.
    # Each segment may contain one [[Region]] and an optional (via [[X]]).
    for seg in re.split(r",|<br\s*/?>|\n", connections):
        seg = seg.strip()
        if not seg:
            continue
        link = re.search(r"\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]", seg)
        if not link:
            continue
        target = link.group(1).strip()
        via_match = re.search(r"via\s*\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]", seg)
        via = via_match.group(1).strip() if via_match else None
        out.append((target, via))
    return out


def main():
    raw = {}
    print(f"{'region':<24} {'edges'}")
    for r in regions:
        rid = r["id"]
        title = WIKI_TITLE[rid]
        try:
            wt = fetch_wikitext(title)
        except Exception as e:
            print(f"  {rid:<24} HTTP error: {e}")
            continue
        conn = extract_connections(wt)
        if not conn:
            raw[rid] = {"title": title, "connections_raw": None, "parsed": []}
            print(f"  {rid:<24} no connections field")
            continue
        parsed = parse_links(conn)
        raw[rid] = {"title": title, "connections_raw": conn, "parsed": parsed}
        edges = []
        for target, via in parsed:
            tid = NAME_TO_ID.get(target, f"???{target}")
            vid = NAME_TO_ID.get(via, f"???{via}") if via else None
            edges.append(f"{tid}" + (f" via {vid}" if vid else ""))
        print(f"  {rid:<24} {' | '.join(edges)}")
        time.sleep(0.2)

    out = ROOT / "data" / "regions_connections_raw.json"
    out.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
    print(f"\nraw -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
