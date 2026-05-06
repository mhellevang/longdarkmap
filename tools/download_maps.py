#!/usr/bin/env python3
"""Download region maps (Pilgrim/Voyageur/Stalker + Interloper/Misery variants)
from the Steam Community guide.

Source: https://steamcommunity.com/sharedfiles/filedetails/?id=3255435617
        "Updated Region Maps [2025]" by HokuOwl
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "maps"
REGIONS_FILE = ROOT / "data" / "regions.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/webp": ".webp",
}

# Variant labels indexed alongside `maps[i]` / `download_urls[i]` in
# data/regions.json. Index 0 is the standard Pilgrim/Voyageur/Stalker map;
# index 1, when present, is the Interloper/Misery (loper) variant.
VARIANT_LABELS = ["PVS", "Loper"]


def download(url: str, dest: Path) -> tuple[Path, bool]:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        ct = resp.headers.get_content_type()
        ext = CONTENT_TYPE_EXT.get(ct, ".jpg")
        path = dest.with_suffix(ext)
        if path.exists():
            return path, True
        path.write_bytes(resp.read())
    return path, False


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    regions = json.loads(REGIONS_FILE.read_text())
    total = sum(len(r["download_urls"]) for r in regions)
    print(f"Downloading {total} maps ({len(regions)} regions, PVS + Loper) ...\n")

    downloaded = skipped = failed = 0
    step = 0

    for region in regions:
        for i, url in enumerate(region["download_urls"]):
            step += 1
            variant = VARIANT_LABELS[i] if i < len(VARIANT_LABELS) else f"v{i}"
            # `maps[i]` already includes the canonical filename + extension;
            # strip the extension so download() can re-derive it from the
            # response Content-Type (avoids hard-coding .jpg vs .png).
            dest = (ROOT / region["maps"][i]).with_suffix("")
            print(f"[{step}/{total}] {region['name']} ({variant})")
            try:
                path, existed = download(url, dest)
                size_kb = path.stat().st_size // 1024
                if existed:
                    print(f"  Skip (exists): {path.name}")
                    skipped += 1
                else:
                    print(f"  OK -> {path.name} ({size_kb} KB)")
                    downloaded += 1
            except Exception as e:
                print(f"  Error: {e}")
                failed += 1

    print(f"\nDone. Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")
    print(f"Saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
