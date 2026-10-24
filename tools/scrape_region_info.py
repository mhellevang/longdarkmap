"""Scrape each region's difficulty and in-game description from the wiki.

The region-select screen in the game shows a short blurb per region that
opens with the intended experience level ("For advanced players. ...").
The wiki quotes it in a {{Quote2|text|In-game description}} template, and
the Infobox/Region carries a `difficulty` field. Pages may also quote an
official marketing blurb first, so only the quote attributed to the game
is used. Transition zones (Ravine, Winding River, ...) mostly have neither
and are left out.

Writes data/region_info.json as { region_id: { difficulty, description } }
and inlines it into index.html via tools/inline_regions.py.

Stdlib only.
"""
import json, re
from pathlib import Path

from scrape_connections import WIKI_TITLE, fetch_wikitext

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "region_info.json"

TITLES = dict(WIKI_TITLE, langston_mine="Langston Mine")

LEVELS = {"new": "Beginner", "beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"}
LEVEL_PREFIX = re.compile(r"^For (new|beginner|intermediate|advanced) players\.\s*", re.I)


def clean(text: str) -> str:
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"'{2,}", "", text)
    # The "Connects to ..." line repeats what the map already shows.
    text = re.sub(r"\s*Connects to [^\n]*$", "", text.strip())
    return re.sub(r"\s*\n\s*", " ", text).strip()


def in_game_quote(wikitext: str) -> str | None:
    for m in re.finditer(r"\{\{Quote2\|(.*?)\|([^|{}]*)\}\}", wikitext, re.S):
        if re.search(r"in.game", m.group(2), re.I):
            return m.group(1)
    return None


def main():
    info = {}
    for rid, title in TITLES.items():
        wikitext = fetch_wikitext(title)
        m = re.search(r"\|\s*difficulty\s*=\s*([^\n|}]*)", wikitext)
        difficulty = LEVELS.get(m.group(1).strip().lower()) if m else None
        quote = in_game_quote(wikitext)
        description = None
        if quote:
            lvl = LEVEL_PREFIX.match(quote.strip())
            if lvl and not difficulty:
                difficulty = LEVELS[lvl.group(1).lower()]
            description = clean(LEVEL_PREFIX.sub("", quote.strip()))
        if difficulty or description:
            info[rid] = {"difficulty": difficulty, "description": description}
        print(f"  {rid:<22} {difficulty or '-':<13} {'desc' if description else '-'}")
    OUT.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(info)} regions)")


if __name__ == "__main__":
    main()
