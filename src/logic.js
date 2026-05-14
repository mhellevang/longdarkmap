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

function parseHash(hashStr) {
  // Format: region[/place[/tool]]. Tool segment activates setToolFilter so
  // tool-keyword search results stay tool-filtered across deep links.
  const raw = (hashStr || '').replace(/^#/, '');
  if (!raw) return null;
  const parts = raw.split('/').map(decodeURIComponent);
  return {
    regionId: parts[0] || null,
    placeName: parts[1] || null,
    tool: parts[2] || null,
  };
}

function makeHash(regionId, placeName, tool) {
  if (!regionId) return '';
  let h = '#' + encodeURIComponent(regionId);
  if (placeName) h += '/' + encodeURIComponent(placeName);
  if (placeName && tool) h += '/' + encodeURIComponent(tool);
  return h;
}

const LDLogic = {
  TOOLS_META,
  TOOL_SYNONYMS,
  matchToolKeyword,
  searchPlaces,
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
