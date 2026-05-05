# Place-box review checklist

The v3 pipeline (Apple Vision OCR + Haiku matcher) produces pixel-tight
boxes for nearly every entry — typical placement is within ~30px of a
hand-corrected reference. A handful of entries per region still need a
manual pass: matcher slips on labels with multiple identical OCR hits
(e.g. mid-paragraph mentions of a label), and the wiki-only entries
that have no on-map text and end up in `not_found`.

Open each region in dev mode (press **D** in the detail view), skim the
labelled overlay, and drag any that look wrong onto the right label.
Click **Save** to persist (requires `node dev-server.js`).

Region order matches the in-app tab order; box counts come from
`data/place_boxes.json` at the time of writing.

- [ ] Mystery Lake (36)
- [ ] Coastal Highway (19)
- [ ] Pleasant Valley (30)
- [ ] Desolation Point (13)
- [ ] Timberwolf Mountain (21)
- [ ] Forlorn Muskeg (16)
- [ ] Broken Railroad (7)
- [ ] Bleak Inlet (25)
- [ ] Hushed River Valley (24)
- [ ] Mountain Town (29)
- [ ] Ash Canyon (19)
- [ ] Blackrock (23)
- [x] Forsaken Airfield (23)
- [x] Sundered Pass (27) — partial: 26 manual overrides
- [ ] Zone of Contamination (24) — partial: 14 manual overrides
- [ ] Crumbling Highway (5)
- [ ] Far Range Branch Line (7)
- [x] Transfer Pass (7) — partial: 7 manual overrides
- [ ] Ravine (2)
- [ ] Winding River & Carter Hydro Dam (0)
- [ ] Keeper's Pass (4)
