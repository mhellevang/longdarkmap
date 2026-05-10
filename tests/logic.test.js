'use strict';

// Run with: node --test tests/
//
// Tests for the pure helpers in src/logic.js. Fixtures are tiny so the tests
// describe the behavioral contract — adding/changing data in index.html
// should not break these.

const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/logic.js');

// ─── fixtures ────────────────────────────────────────────────────────────────

const REGIONS = [
  { id: 'mystery_lake',    name: 'Mystery Lake',    adjacencies: ['ravine', 'forlorn_muskeg', 'mountain_town'] },
  { id: 'coastal_highway', name: 'Coastal Highway', adjacencies: ['ravine', 'pleasant_valley'] },
  { id: 'ravine',          name: 'Ravine',          adjacencies: ['mystery_lake', 'coastal_highway'] },
  { id: 'forlorn_muskeg',  name: 'Forlorn Muskeg',  adjacencies: ['mystery_lake', 'broken_railroad'] },
  { id: 'mountain_town',   name: 'Mountain Town',   adjacencies: ['mystery_lake'] },
  { id: 'pleasant_valley', name: 'Pleasant Valley', adjacencies: ['coastal_highway'] },
  { id: 'broken_railroad', name: 'Broken Railroad', adjacencies: ['forlorn_muskeg'] },
  { id: 'island',          name: 'Lone Island',     adjacencies: [] },
];
const REGIONS_BY_ID = Object.fromEntries(REGIONS.map(r => [r.id, r]));

const PLACES_INDEX = [
  { name: "Angler's Den",       region: 'mystery_lake' },
  { name: 'Camp Office',        region: 'mystery_lake' },
  { name: 'Forge Shed',         region: 'forlorn_muskeg' },
  { name: 'Quonset Garage',     region: 'coastal_highway' },
  { name: 'Hibernia Processing',region: 'broken_railroad' },
  { name: 'Mountaineer\'s Hut', region: 'pleasant_valley' },
];

const PLACE_TOOLS = {
  forlorn_muskeg:  { 'Forge Shed':          ['forge', 'workbench'] },
  broken_railroad: { 'Hibernia Processing': ['forge', 'workbench'] },
  coastal_highway: { 'Quonset Garage':      ['workbench', 'bed'] },
  mystery_lake:    { 'Camp Office':         ['workbench', 'bed', 'stove'] },
};

const SEARCH_CTX = {
  placesIndex: PLACES_INDEX,
  placeTools:  PLACE_TOOLS,
  regions:     REGIONS,
  maxResults:  30,
};

// ─── matchToolKeyword ────────────────────────────────────────────────────────

test('matchToolKeyword: canonical synonyms', () => {
  assert.equal(L.matchToolKeyword('forge'), 'forge');
  assert.equal(L.matchToolKeyword('arrowheads'), 'forge');
  assert.equal(L.matchToolKeyword('wb'), 'workbench');
  assert.equal(L.matchToolKeyword('ammo'), 'ammunition_workbench');
  assert.equal(L.matchToolKeyword('mill'), 'milling_machine');
  assert.equal(L.matchToolKeyword('medkit'), 'first_aid');
});

test('matchToolKeyword: trims and lowercases', () => {
  assert.equal(L.matchToolKeyword('  Forge  '), 'forge');
  assert.equal(L.matchToolKeyword('FORGE'), 'forge');
});

test('matchToolKeyword: non-synonym returns null', () => {
  assert.equal(L.matchToolKeyword(''), null);
  assert.equal(L.matchToolKeyword('camp'), null);
  assert.equal(L.matchToolKeyword('something else'), null);
});

// ─── searchPlaces ────────────────────────────────────────────────────────────

test('searchPlaces: empty query returns []', () => {
  assert.deepEqual(L.searchPlaces('', SEARCH_CTX), []);
  assert.deepEqual(L.searchPlaces('   ', SEARCH_CTX), []);
});

test('searchPlaces: prefix match beats substring match', () => {
  // "Camp Office" starts with "camp" → score 1
  // (no other "camp" hits in fixture)
  const r = L.searchPlaces('camp', SEARCH_CTX);
  assert.equal(r[0].name, 'Camp Office');
});

test('searchPlaces: word-boundary beats arbitrary substring', () => {
  // Add a fixture where two places contain "shed": one as a word, one
  // mid-word. Verify the word-boundary one wins.
  const ctx = {
    ...SEARCH_CTX,
    placesIndex: [
      { name: 'Bunkershed Cave', region: 'ravine' },        // substring score 3
      { name: 'Forge Shed',      region: 'forlorn_muskeg' },// word-boundary score 2
    ],
  };
  const r = L.searchPlaces('shed', ctx);
  assert.equal(r[0].name, 'Forge Shed');
  assert.equal(r[1].name, 'Bunkershed Cave');
});

test('searchPlaces: ties broken by region order in REGIONS', () => {
  // Two places named "Cave" — the one whose region appears first in REGIONS
  // should rank first.
  const ctx = {
    ...SEARCH_CTX,
    placesIndex: [
      { name: 'Cave', region: 'coastal_highway' },  // index 1 in REGIONS
      { name: 'Cave', region: 'mystery_lake' },     // index 0 in REGIONS
    ],
  };
  const r = L.searchPlaces('cave', ctx);
  assert.equal(r[0].region, 'mystery_lake');
  assert.equal(r[1].region, 'coastal_highway');
});

test('searchPlaces: tool-keyword expansion surfaces tool-tagged places', () => {
  // "forge" matches no place name in the fixture, but Forge Shed and
  // Hibernia Processing are tagged with forge → both should appear.
  const r = L.searchPlaces('forge', SEARCH_CTX);
  const names = r.map(x => x.name);
  assert.ok(names.includes('Forge Shed'));
  assert.ok(names.includes('Hibernia Processing'));
});

test('searchPlaces: tool-matched results are annotated with matchedTool', () => {
  const r = L.searchPlaces('forge', SEARCH_CTX);
  const hibernia = r.find(x => x.name === 'Hibernia Processing');
  assert.equal(hibernia.matchedTool, 'forge');
});

test('searchPlaces: name-prefix beats tool-keyword expansion', () => {
  // "forge" prefix-matches "Forge Shed" (score 1) AND tool-expansion
  // surfaces it (score 1.5). Prefix should win, so it appears once.
  const r = L.searchPlaces('forge', SEARCH_CTX);
  const forgeSheds = r.filter(x => x.name === 'Forge Shed' && x.region === 'forlorn_muskeg');
  assert.equal(forgeSheds.length, 1, 'no duplicate row for the same place');
  // And the prefix-matched row still gets the tool annotation.
  assert.equal(forgeSheds[0].matchedTool, 'forge');
});

test('searchPlaces: maxResults caps the output', () => {
  const ctx = { ...SEARCH_CTX, maxResults: 2 };
  const r = L.searchPlaces('e', ctx);  // matches a lot
  assert.equal(r.length, 2);
});

// ─── bfsPaths ────────────────────────────────────────────────────────────────

test('bfsPaths: starting region is reachable in 0 hops', () => {
  const v = L.bfsPaths('mystery_lake', REGIONS_BY_ID);
  assert.equal(v.mystery_lake.hops, 0);
  assert.deepEqual(v.mystery_lake.path, ['mystery_lake']);
});

test('bfsPaths: direct neighbours are 1 hop', () => {
  const v = L.bfsPaths('mystery_lake', REGIONS_BY_ID);
  assert.equal(v.ravine.hops, 1);
  assert.deepEqual(v.ravine.path, ['mystery_lake', 'ravine']);
});

test('bfsPaths: multi-hop paths are shortest', () => {
  // mystery_lake → forlorn_muskeg → broken_railroad (2 hops)
  const v = L.bfsPaths('mystery_lake', REGIONS_BY_ID);
  assert.equal(v.broken_railroad.hops, 2);
  assert.deepEqual(v.broken_railroad.path, ['mystery_lake', 'forlorn_muskeg', 'broken_railroad']);
});

test('bfsPaths: disconnected region not in result', () => {
  const v = L.bfsPaths('mystery_lake', REGIONS_BY_ID);
  assert.ok(!('island' in v));
});

test('bfsPaths: unknown start id returns just itself', () => {
  const v = L.bfsPaths('nowhere', REGIONS_BY_ID);
  assert.deepEqual(Object.keys(v), ['nowhere']);
});

// ─── findNearestTool ─────────────────────────────────────────────────────────

test('findNearestTool: prefers fewer hops', () => {
  // Forges live in forlorn_muskeg (1 hop from mystery_lake) and
  // broken_railroad (2 hops). Closest should win.
  const r = L.findNearestTool('mystery_lake', 'forge', {
    placeTools:  PLACE_TOOLS,
    regionsById: REGIONS_BY_ID,
  });
  assert.equal(r.regionId, 'forlorn_muskeg');
  assert.equal(r.placeName, 'Forge Shed');
  assert.equal(r.hops, 1);
});

test('findNearestTool: hop ties broken by lexical region order', () => {
  // Both broken_railroad (forge) and coastal_highway (workbench) sit
  // at hop 1 from ravine. For workbench, that includes mystery_lake too.
  // Looking for workbench from ravine: candidates are
  //   coastal_highway (1 hop), mystery_lake (1 hop).
  // 'coastal_highway' < 'mystery_lake' lexically → coastal_highway wins.
  const r = L.findNearestTool('ravine', 'workbench', {
    placeTools:  PLACE_TOOLS,
    regionsById: REGIONS_BY_ID,
  });
  assert.equal(r.regionId, 'coastal_highway');
});

test('findNearestTool: returns null when tool unreachable', () => {
  const r = L.findNearestTool('island', 'forge', {
    placeTools:  PLACE_TOOLS,
    regionsById: REGIONS_BY_ID,
  });
  assert.equal(r, null);
});

test('findNearestTool: returns null for unknown tool', () => {
  const r = L.findNearestTool('mystery_lake', 'tardis', {
    placeTools:  PLACE_TOOLS,
    regionsById: REGIONS_BY_ID,
  });
  assert.equal(r, null);
});

// ─── pathSummary ─────────────────────────────────────────────────────────────

test('pathSummary: direct path returns empty string', () => {
  assert.equal(L.pathSummary(['mystery_lake', 'ravine'], REGIONS_BY_ID), '');
});

test('pathSummary: single-region path returns empty string', () => {
  assert.equal(L.pathSummary(['mystery_lake'], REGIONS_BY_ID), '');
});

test('pathSummary: multi-hop summary lists intermediate regions', () => {
  const path = ['mystery_lake', 'forlorn_muskeg', 'broken_railroad'];
  assert.equal(L.pathSummary(path, REGIONS_BY_ID), 'via Forlorn Muskeg');
});

test('pathSummary: falls back to id when region unknown', () => {
  const path = ['a', 'unknown_region', 'c'];
  assert.equal(L.pathSummary(path, REGIONS_BY_ID), 'via unknown_region');
});

// ─── parseHash ───────────────────────────────────────────────────────────────

test('parseHash: empty / null returns null', () => {
  assert.equal(L.parseHash(''), null);
  assert.equal(L.parseHash('#'), null);
  assert.equal(L.parseHash(undefined), null);
});

test('parseHash: region only', () => {
  assert.deepEqual(L.parseHash('#mystery_lake'), {
    regionId: 'mystery_lake', placeName: null, tool: null,
  });
});

test('parseHash: region + place', () => {
  assert.deepEqual(L.parseHash('#mystery_lake/Camp%20Office'), {
    regionId: 'mystery_lake', placeName: 'Camp Office', tool: null,
  });
});

test('parseHash: region + place + tool', () => {
  assert.deepEqual(L.parseHash('#forlorn_muskeg/Forge%20Shed/forge'), {
    regionId: 'forlorn_muskeg', placeName: 'Forge Shed', tool: 'forge',
  });
});

test('parseHash: handles missing leading #', () => {
  assert.deepEqual(L.parseHash('mystery_lake'), {
    regionId: 'mystery_lake', placeName: null, tool: null,
  });
});

// ─── makeHash ────────────────────────────────────────────────────────────────

test('makeHash: no region returns empty string', () => {
  assert.equal(L.makeHash(null, null, null), '');
  assert.equal(L.makeHash(null, 'place', 'tool'), '');
});

test('makeHash: region only', () => {
  assert.equal(L.makeHash('mystery_lake', null, null), '#mystery_lake');
});

test('makeHash: region + place', () => {
  assert.equal(
    L.makeHash('mystery_lake', 'Camp Office', null),
    '#mystery_lake/Camp%20Office',
  );
});

test('makeHash: region + place + tool', () => {
  assert.equal(
    L.makeHash('forlorn_muskeg', 'Forge Shed', 'forge'),
    '#forlorn_muskeg/Forge%20Shed/forge',
  );
});

test('makeHash: tool ignored without place', () => {
  // The browser-side openRegion never passes tool without place, but the
  // logic guards against it anyway.
  assert.equal(L.makeHash('mystery_lake', null, 'forge'), '#mystery_lake');
});

test('makeHash / parseHash round-trip with special characters', () => {
  const region = 'pleasant_valley';
  const place  = "Mountaineer's Hut";
  const tool   = 'workbench';
  const round  = L.parseHash(L.makeHash(region, place, tool));
  assert.deepEqual(round, { regionId: region, placeName: place, tool });
});
