'use strict';

// Pure helpers extracted from index.html so they can be unit-tested.
// Loaded in the browser as a classic <script> (attaches to window.LDLogic);
// imported in tests via Node's CJS require/import (module.exports = LDLogic).
//
// Functions take all the data they need as arguments — no closures over the
// big PLACES_INDEX / PLACE_TOOLS / REGIONS tables — so tests can pass small
// fixtures.

// Single source of truth for crafting-tool tags. Each entry carries:
//   glyph    — one-char badge text shown on map overlays + search rows
//   label    — human-readable name for tooltips / pill text
//   synonyms — words the user might type to surface this tool in search
//              (include the canonical tag itself so identity matches work)
//   nearby   — true if the detail-view "nearest tool" strip should surface
//              this tool. Rare crafting stations only; common amenities
//              (bed, stove, first_aid) aren't worth a nearest pill.
//
// TOOL_SYNONYMS, TOOL_GLYPHS, NEARBY_TOOLS, toolLabel are all derived from
// this. Adding a tool means adding one entry here.
const TOOLS_META = {
  forge:                { glyph: 'F', label: 'Forge',                synonyms: ['forge', 'forges', 'arrowhead', 'arrowheads', 'smithing'], nearby: true },
  workbench:            { glyph: 'W', label: 'Workbench',            synonyms: ['workbench', 'workbenches', 'wb', 'craft', 'crafting'],    nearby: true },
  ammunition_workbench: { glyph: 'A', label: 'Ammunition Workbench', synonyms: ['ammo', 'ammunition', 'reload', 'reloading'],              nearby: true },
  milling_machine:      { glyph: 'M', label: 'Milling Machine',      synonyms: ['milling', 'mill'],                                        nearby: true },
  bed:                  { glyph: 'B', label: 'Bed',                  synonyms: ['bed', 'beds', 'sleep', 'bedroll'],                        nearby: false },
  stove:                { glyph: 'S', label: 'Stove',                synonyms: ['stove', 'fireplace', 'fire', 'barrel'],                   nearby: false },
  first_aid:            { glyph: '+', label: 'First Aid',            synonyms: ['firstaid', 'first-aid', 'first_aid', 'medkit', 'medical'], nearby: false },
  ice_fishing_hut:      { glyph: 'I', label: 'Ice Fishing Hut',      synonyms: ['icefishing', 'ice-fishing'],                              nearby: false },
  ice_fishing_hole:     { glyph: 'i', label: 'Ice Fishing Hole',     synonyms: [],                                                         nearby: false },
};

const TOOL_SYNONYMS = {};
for (const [tag, meta] of Object.entries(TOOLS_META)) {
  for (const syn of meta.synonyms) TOOL_SYNONYMS[syn] = tag;
}

// Single source of truth for legend-icon resources surfaced in the detail
// view's "Resources" pill row. Each entry carries:
//   label    — display name shown on the pill and used in the search-result
//              "highlighted name" (e.g. "Moose area #2")
//   color    — CSS colour for the pill border + swatch when the pill is
//              active. Picked roughly to match the legend pictogram's
//              palette so the active pill reads as "this kind of icon".
//   synonyms — words the user might type to surface this resource in the
//              world-view search (consumed by matchResourceKeyword /
//              searchResources). Include the canonical tag itself so
//              identity matches work.
//
// Source of detections is tools/find_resources.py → REGION_RESOURCES inlined
// in index.html as `REGION_RESOURCES[region_id][tag] = [{bbox, score}]`.
// Iteration order here is the visual order of the pills (regions don't
// reorder them per-region — common resources first, rarer ones last).
//
// To add a resource: (1) add a canonical PNG to
// data/legend_icons/canonical/<tag>.png, (2) extend CLASS_GROUPS in
// tools/find_resources.py with the colour filter that captures it,
// (3) add an entry here, (4) re-run find_resources.py --inline.
const RESOURCES_META = {
  moose:          { label: 'Moose area',      color: '#1f7a3a', synonyms: ['moose'] },
  bear:           { label: 'Bear area',       color: '#b85a1a', synonyms: ['bear'] },
  wolf:           { label: 'Wolf area',       color: '#1a7fb8', synonyms: ['wolf'] },
  timberwolf:     { label: 'Timberwolf pack', color: '#947010', synonyms: ['timberwolf', 'timberwolves'] },
  cougar:         { label: 'Cougar territory', color: '#777a85', synonyms: ['cougar'] },
  deer:           { label: 'Deer area',       color: '#2f3540', synonyms: ['deer'] },
  cattails:       { label: 'Cattails',        color: '#a14fb0', synonyms: ['cattails', 'cattail'] },
  sapling:        { label: 'Sapling',         color: '#3a8a3a', synonyms: ['sapling', 'saplings', 'maple', 'birch'] },
  salt_deposit:   { label: 'Salt deposit',    color: '#444b58', synonyms: ['salt'] },
};

const RESOURCE_SYNONYMS = {};
for (const [tag, meta] of Object.entries(RESOURCES_META)) {
  for (const syn of meta.synonyms) RESOURCE_SYNONYMS[syn] = tag;
}

function matchResourceKeyword(q) {
  // Returns a canonical resource tag if the trimmed query matches a synonym
  // (full word, case-insensitive) — same contract as matchToolKeyword.
  const ql = q.trim().toLowerCase();
  return RESOURCE_SYNONYMS[ql] || null;
}

function searchResources(q, ctx) {
  // Region-scoped resource results for the world-view search: typing "moose"
  // lists the regions with detected moose areas, biggest count first, so the
  // user can jump straight into a #region/$resource:moose cycle.
  //   ctx: { regionResources, regions, maxResults? }
  // Returns [{ tag, region, count }].
  const tag = matchResourceKeyword(q);
  if (!tag) return [];
  const maxResults = ctx.maxResults != null ? ctx.maxResults : 6;
  const rows = [];
  for (const r of ctx.regions) {
    const hits = (ctx.regionResources[r.id] || {})[tag];
    if (Array.isArray(hits) && hits.length) {
      rows.push({ tag, region: r.id, count: hits.length });
    }
  }
  rows.sort((a, b) => b.count - a.count);
  return rows.slice(0, maxResults);
}

// Heuristic: does this bbox look like it landed inside the map's legend
// strip rather than on real on-map content? HokuOwl's region maps put the
// legend at the very top or very bottom of the image (depending on region).
// Bands are intentionally narrow: real on-map labels can sit close to the
// edge (e.g. a region-transition label at the top of CH), and being too
// aggressive here would silently skip legitimate places. The original bug
// we're guarding against had cy ≈ 0.925; thresholds set to comfortably
// catch that while leaving room for real edge labels to pass.
function looksLikeLegendBbox(bbox) {
  if (!Array.isArray(bbox) || bbox.length !== 4) return false;
  const cy = (bbox[1] + bbox[3]) / 2;
  return cy < 0.025 || cy > 0.92;
}

// Pure cycle-step helper for the resources panel: given the currently active
// resource state and a click on some pill, return the next state.
//   currentTag    — resource tag the user is currently cycling through, or null
//   currentIndex  — 0-indexed hit within that resource (ignored if tag changes)
//   clickedTag    — the pill the user just clicked
//   hitCount      — how many hits the clicked resource has on this region (>= 1)
//
// Clicking a different pill resets the cycle to hit 0 of the new resource;
// clicking the same pill again advances and wraps. Returns { tag, index }.
function nextResourceCycle(currentTag, currentIndex, clickedTag, hitCount) {
  if (hitCount <= 0) return { tag: clickedTag, index: 0 };
  if (currentTag !== clickedTag) return { tag: clickedTag, index: 0 };
  return { tag: clickedTag, index: (currentIndex + 1) % hitCount };
}

function matchToolKeyword(q) {
  // Returns a canonical tool tag if the trimmed query matches a synonym
  // (full word, case-insensitive). Used by search to surface tool-bearing
  // places that don't share their name with the tool.
  const ql = q.trim().toLowerCase();
  return TOOL_SYNONYMS[ql] || null;
}

function searchPlaces(q, ctx) {
  const placesIndex = ctx.placesIndex;
  const placeTools  = ctx.placeTools;
  const regions     = ctx.regions;
  const maxResults  = ctx.maxResults != null ? ctx.maxResults : 30;

  const ql = q.trim().toLowerCase();
  if (!ql) return [];
  const regionOrder = new Map(regions.map((r, i) => [r.id, i]));
  const matches = [];
  // Score: exact prefix > word-boundary > substring; ties broken by region order.
  for (const p of placesIndex) {
    const nl = p.name.toLowerCase();
    let score;
    if (nl === ql) score = 0;
    else if (nl.startsWith(ql)) score = 1;
    else if (nl.includes(' ' + ql)) score = 2;
    else if (nl.includes(ql)) score = 3;
    else continue;
    matches.push({ p, score, matchedTool: null });
  }
  // Tool-keyword expansion: any place tagged with the matched tool joins the
  // results, even if its name doesn't contain the query. Score 1.5 keeps tool
  // matches above generic substring hits but below name-prefix hits.
  const tool = matchToolKeyword(q);
  if (tool) {
    const seen = new Set(matches.map(m => m.p.region + '|' + m.p.name));
    for (const [region, places] of Object.entries(placeTools)) {
      for (const [name, tags] of Object.entries(places)) {
        if (!tags.includes(tool)) continue;
        const key = region + '|' + name;
        if (seen.has(key)) {
          const existing = matches.find(m => m.p.region === region && m.p.name === name);
          if (existing) existing.matchedTool = tool;
          continue;
        }
        seen.add(key);
        matches.push({ p: { name, region }, score: 1.5, matchedTool: tool });
      }
    }
  }
  matches.sort((a, b) =>
    a.score - b.score
    || regionOrder.get(a.p.region) - regionOrder.get(b.p.region)
    || a.p.name.localeCompare(b.p.name));
  return matches.slice(0, maxResults).map(m => ({ ...m.p, matchedTool: m.matchedTool }));
}

function bfsPaths(fromId, regionsById) {
  const visited = { [fromId]: { hops: 0, path: [fromId] } };
  const queue = [fromId];
  while (queue.length) {
    const cur = queue.shift();
    const region = regionsById[cur];
    if (!region) continue;
    for (const neighbour of (region.adjacencies || [])) {
      if (neighbour in visited) continue;
      visited[neighbour] = {
        hops: visited[cur].hops + 1,
        path: [...visited[cur].path, neighbour],
      };
      queue.push(neighbour);
    }
  }
  return visited;
}

function findNearestTool(fromRegionId, tool, ctx) {
  // Returns { regionId, placeName, hops, path } or null. Ties broken by
  // lexical region order so results are deterministic.
  const placeTools  = ctx.placeTools;
  const regionsById = ctx.regionsById;
  const reachable = bfsPaths(fromRegionId, regionsById);
  let best = null;
  for (const [regionId, places] of Object.entries(placeTools)) {
    if (!(regionId in reachable)) continue;
    const { hops, path } = reachable[regionId];
    for (const [placeName, tags] of Object.entries(places)) {
      if (!tags.includes(tool)) continue;
      if (!best
          || hops < best.hops
          || (hops === best.hops && regionId < best.regionId)) {
        best = { regionId, placeName, hops, path };
      }
    }
  }
  return best;
}

function pathSummary(path, regionsById) {
  // "via Ravine, Mystery Lake" for an intermediate-only summary; "" if direct.
  if (path.length <= 2) return '';
  const middle = path.slice(1, -1).map(id => (regionsById[id] || {}).name || id);
  return 'via ' + middle.join(', ');
}

// Sentinel prefix that distinguishes a resource-cycle segment from a normal
// place name. Real place names never start with '$', so collisions are out.
const RESOURCE_HASH_PREFIX = '$resource:';

function parseHash(hashStr) {
  // Format variants:
  //   #region                         — open region only
  //   #region/place                   — open + highlight a named place
  //   #region/place/tool              — same + carry a tool filter
  //   #region/$resource:moose         — open + cycle 1st moose hit
  //   #region/$resource:moose/3       — same + cycle 3rd hit (1-indexed)
  const raw = (hashStr || '').replace(/^#/, '');
  if (!raw) return null;
  const parts = raw.split('/').map(decodeURIComponent);
  const regionId = parts[0] || null;
  if (!regionId) return null;
  if (parts[1] && parts[1].startsWith(RESOURCE_HASH_PREFIX)) {
    const resource = parts[1].slice(RESOURCE_HASH_PREFIX.length) || null;
    const idxRaw = parts[2] ? parseInt(parts[2], 10) : 1;
    const resourceIndex = Number.isFinite(idxRaw) && idxRaw >= 1 ? idxRaw : 1;
    return {
      regionId, placeName: null, tool: null,
      resource, resourceIndex,
    };
  }
  return {
    regionId,
    placeName: parts[1] || null,
    tool: parts[2] || null,
    resource: null,
    resourceIndex: null,
  };
}

function makeHash(opts) {
  // opts: { regionId, placeName, tool, resource, resourceIndex } — same shape
  // parseHash returns, so the round-trip is symmetric. All keys optional.
  const { regionId, placeName, tool, resource, resourceIndex } = opts || {};
  if (!regionId) return '';
  let h = '#' + encodeURIComponent(regionId);
  if (resource) {
    h += '/' + encodeURIComponent(RESOURCE_HASH_PREFIX + resource);
    // Omit index suffix when it's 1 to keep shareable URLs short.
    if (resourceIndex && resourceIndex > 1) {
      h += '/' + encodeURIComponent(String(resourceIndex));
    }
    return h;
  }
  if (placeName) h += '/' + encodeURIComponent(placeName);
  if (placeName && tool) h += '/' + encodeURIComponent(tool);
  return h;
}

const LDLogic = {
  TOOLS_META,
  TOOL_SYNONYMS,
  RESOURCES_META,
  RESOURCE_HASH_PREFIX,
  looksLikeLegendBbox,
  nextResourceCycle,
  matchToolKeyword,
  matchResourceKeyword,
  searchPlaces,
  searchResources,
  bfsPaths,
  findNearestTool,
  pathSummary,
  parseHash,
  makeHash,
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = LDLogic;
}
if (typeof window !== 'undefined') {
  window.LDLogic = LDLogic;
}
