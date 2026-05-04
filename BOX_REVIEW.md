# Place-box review checklist

The OCR pipeline produced an initial bbox per place; some are misplaced and
need a manual pass. Open each region in dev mode (press **D** in the detail
view) and skim the labelled boxes — drag any that are wrong onto the right
label, then click **Save** (requires `node dev-server.js`).

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
- [ ] Sundered Pass (27)
- [ ] Zone of Contamination (24)
- [ ] Crumbling Highway (5)
- [ ] Far Range Branch Line (7)
- [ ] Transfer Pass (7)
- [ ] Ravine (2)
- [ ] Winding River & Carter Hydro Dam (0)
- [ ] Keeper's Pass (4)
