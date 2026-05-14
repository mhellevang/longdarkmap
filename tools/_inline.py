"""Shared inline-block helper for the tools/ pipeline.

Several scrapers and the merge script all replace a sentinel-delimited
JSON block in index.html with `const <VAR> = <json>;`. This collapses that
pattern into one place so the implementations don't drift on edge cases
(indent, escaping, trailing newlines).

Usage:
    from _inline import inline_block
    inline_block(INDEX_HTML, "PLACES_INDEX", "// PLACES_INDEX_START",
                 "// PLACES_INDEX_END", places)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def inline_block(
    html_path: Path,
    var_name: str,
    start_sentinel: str,
    end_sentinel: str,
    payload: Any,
    *,
    ensure_ascii: bool = True,
) -> bool:
    """Replace the block between sentinels in html_path with `const var = payload;`.

    Returns False (and does not write) if the sentinels aren't present.
    """
    html = html_path.read_text()
    pattern = re.compile(
        rf"({re.escape(start_sentinel)}\n).*?(\n\s*{re.escape(end_sentinel)})",
        re.S,
    )
    if not pattern.search(html):
        return False
    body = f"const {var_name} = {json.dumps(payload, indent=2, ensure_ascii=ensure_ascii)};"
    html_path.write_text(pattern.sub(lambda m: m.group(1) + body + m.group(2), html))
    return True
