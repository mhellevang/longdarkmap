# Amenity-tagging subagent prompt

You're tagging crafting/comfort amenities for one Long Dark region. The map is a
community-made guide that uses pictogram icons to mark what's at each place. A
prep step has cropped one image per place (centred on its label, with the
surrounding area where icons sit) plus the map's legend strip. Your job is to
look at each crop, compare the icons it contains to the legend, and return a
canonical tag list per place.

## Inputs

`data/tiles/{REGION_ID}/amenities/` contains:

- `task.json` — region id, the canonical tag list you may use (and only those),
  the list of places with `name`, `slug`, and the pixel crop coords for context.
- `legend.jpg` — the map's legend strip; pairs each pictogram with its label.
- `<slug>.jpg` — one crop per place, centred on the label.

## Method

1. **Read the legend first** so you know which legend label corresponds to each
   icon shape on this map specifically. Different regions sometimes draw the
   same amenity slightly differently, so don't lean on memory of other maps.
2. For each `<slug>.jpg`:
   - Find the place's printed label inside the crop (the prep step centred it).
   - Look at the icons clustered next to the label — they're the amenities for
     this place. Don't tag icons that belong to a *neighbouring* place's label.
   - Map each icon to the matching legend label, then to the canonical tag set
     in `task.json` using the rules below.

## Canonical tag mapping (only emit these tags)

| Legend label                          | Canonical tag             |
|---------------------------------------|---------------------------|
| Workbench                             | `workbench`               |
| Forge                                 | `forge`                   |
| Ammunition workbench / Reloading bench| `ammunition_workbench`    |
| Milling machine                       | `milling_machine`         |
| Place to sleep / Bedroll / Bed        | `bed`                     |
| Fireplace, barrel or stove            | `stove`                   |
| First aid kit                         | `first_aid`               |
| Ice fishing hut                       | `ice_fishing_hut`         |
| Ice fishing hole                      | `ice_fishing_hole`        |

If a legend on this map doesn't include one of these, that's normal — only emit
tags whose legend equivalent actually appears in the crop.

**Don't emit anything else.** Loot icons (rifle, knife, hatchet, hammer,
"possible X"), animal-area icons (bear/wolf/deer/moose), foraging icons
(saplings, mushrooms, herbs), DLC trinket icons (cairn, salt deposit, polaroid,
shortwave cache, traders radio, film box), and travel-graphics (rail tracks,
roads, bridges, vehicles, mine entrance) all get ignored.

## Edge cases

- **No icons next to the label**: emit `[]`. Don't guess based on the place name.
- **Icons partly inside the crop**: only count them if at least half the icon is
  inside, AND it visually clusters with this place's label rather than the next
  place's label.
- **Place label appears twice in the crop** (rare — happens when two nearby
  places end up in the same crop): the prep step centred the crop on this
  place's label specifically, so prefer the icons closest to the centre.
- **Legend itself in the crop**: if the place sits near the bottom of the map,
  the crop may include legend rows. Ignore icons that are part of a labelled
  legend row — those aren't this place's amenities.

## Output

Write `data/tiles/{REGION_ID}/amenities/result.json`:

```json
{
  "region_id": "{REGION_ID}",
  "places": {
    "Quonset Garage": ["workbench", "bed", "stove", "first_aid"],
    "Fishing Camp":   ["workbench", "bed", "stove"],
    "Abandoned Lookout": []
  }
}
```

Use the exact `name` strings from `task.json` as keys. Include every place,
even if its tag list is empty — it makes the merge step's diff cleaner.

Confidence threshold: when in doubt about an icon, leave it out. False
negatives are recoverable (the wiki scrape catches forge/workbench
authoritatively); false positives propagate to the UI.
