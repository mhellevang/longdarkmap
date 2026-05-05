"""Write a task.json into each region's tile directory listing the place
names that the vision agent should locate. Keeps agent prompts compact and
uniform — the agent reads its own region's task file."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
TILES_DIR = ROOT / "data" / "tiles"


def main() -> int:
    places = json.loads((ROOT / "data" / "places_index.json").read_text())
    extras_path = ROOT / "data" / "places_extra.json"
    if extras_path.exists():
        places = places + json.loads(extras_path.read_text())
    by_region: dict[str, list[str]] = {}
    for p in places:
        by_region.setdefault(p["region"], []).append(p["name"])

    for region_id, names in by_region.items():
        out = TILES_DIR / region_id
        if not out.exists():
            print(f"  skip {region_id} (no tiles)")
            continue
        names_sorted = sorted(set(names))
        (out / "task.json").write_text(json.dumps({
            "region_id": region_id,
            "names": names_sorted,
        }, indent=2) + "\n")
        print(f"  {region_id}: {len(names_sorted)} names")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
