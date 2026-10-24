'use strict';

// DOM-level tests: drive the real index.html in jsdom.
// Each test gets a fresh page so state doesn't leak.

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadPage, fire } = require('./harness');

// ─── search dropdown ─────────────────────────────────────────────────────────

test('search: empty input keeps dropdown hidden', async () => {
  const { document, close } = await loadPage();
  try {
    const results = document.getElementById('search-results');
    assert.notEqual(results.style.display, 'block');
    assert.equal(results.querySelectorAll('.search-result').length, 0);
  } finally { close(); }
});

test('search: typing a query renders matching results', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'camp';
    fire(window, input, 'input');

    const results = document.getElementById('search-results');
    assert.equal(results.style.display, 'block');
    const rows = results.querySelectorAll('.search-result');
    assert.ok(rows.length > 0, 'at least one result row');
    // "Camp Office" is in mystery_lake — it should show up.
    const names = [...rows].map(r => r.querySelector('.result-name').textContent);
    assert.ok(names.some(n => n.toLowerCase().includes('camp')),
      `expected a "camp" result, got: ${names.slice(0, 5).join(', ')}`);
  } finally { close(); }
});

test('search: nonsense query renders the "No results" empty state', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'zzzzz_no_match_zzzzz';
    fire(window, input, 'input');

    const results = document.getElementById('search-results');
    assert.equal(results.style.display, 'block');
    assert.equal(results.querySelectorAll('.search-result').length, 0);
    const empty = document.getElementById('search-empty');
    assert.ok(empty, 'empty state element exists');
    assert.equal(empty.textContent, 'No results');
  } finally { close(); }
});

test('search: ArrowDown highlights the first result with .active', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'camp';
    fire(window, input, 'input');
    fire(window, input, 'keydown', { key: 'ArrowDown' });

    const rows = document.querySelectorAll('#search-results .search-result');
    assert.ok(rows.length > 0);
    assert.ok(rows[0].classList.contains('active'),
      'first row should be active after ArrowDown');
  } finally { close(); }
});

test('search: ArrowDown then Enter opens the selected region (updates hash)', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'camp';
    fire(window, input, 'input');
    fire(window, input, 'keydown', { key: 'ArrowDown' });
    fire(window, input, 'keydown', { key: 'Enter' });

    // Enter should have triggered openSearchResult → openRegion → pushHash.
    assert.ok(window.location.hash.length > 1, 'hash should be set');
    assert.ok(window.location.hash.startsWith('#'), 'hash should start with #');
    // The detail view should be open.
    assert.equal(document.getElementById('detail-view').style.display, 'flex');
  } finally { close(); }
});

test('search: Enter without ArrowDown opens the first result', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'camp';
    fire(window, input, 'input');
    // No ArrowDown — Enter should still pick items[0] per the keydown handler.
    fire(window, input, 'keydown', { key: 'Enter' });

    assert.equal(document.getElementById('detail-view').style.display, 'flex');
    assert.ok(window.location.hash.length > 1);
  } finally { close(); }
});

test('search: Escape with text clears the input and hides results', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'camp';
    fire(window, input, 'input');

    fire(window, input, 'keydown', { key: 'Escape' });
    assert.equal(input.value, '');
    assert.equal(document.getElementById('search-results').style.display, 'none');
  } finally { close(); }
});

test('search: tool keyword surfaces tool-tagged places with .match badge', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'forge';
    fire(window, input, 'input');

    const rows = document.querySelectorAll('#search-results .search-result');
    assert.ok(rows.length > 0, 'should have forge results');
    // At least one result should carry a forge badge with the .match accent.
    const matchBadges = document.querySelectorAll(
      '#search-results .tool-badge.tool-forge.match');
    assert.ok(matchBadges.length > 0,
      'expected at least one tool-forge.match badge on a result row');
  } finally { close(); }
});

test('search: resource keyword lists region-scoped resource rows first', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'moose';
    fire(window, input, 'input');

    const rows = document.querySelectorAll('#search-results .resource-result');
    assert.ok(rows.length > 0, 'expected resource rows for "moose"');
    const first = document.querySelector('#search-results .search-result');
    assert.ok(first.classList.contains('resource-result'),
      'resource rows should come before place-name matches');
    assert.equal(first.querySelector('.result-name').textContent, 'Moose');
    assert.ok(first.querySelector('.result-count').textContent.match(/^\d+$/),
      'row should show the hit count');
  } finally { close(); }
});

test('search: clicking a resource row opens the region with that layer on', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    input.value = 'moose';
    fire(window, input, 'input');

    const row = document.querySelector('#search-results .resource-result');
    fire(window, row, 'click');

    assert.equal(document.getElementById('detail-view').style.display, 'flex');
    assert.match(window.location.hash, /(?:\$|%24)resource(?:%3A|:)moose/);
    const layer = document.querySelector('#layers-list .layer-row[data-tag="moose"]');
    assert.equal(layer.getAttribute('aria-pressed'), 'true', 'moose layer should be on after opening a resource result');
  } finally { close(); }
});

test('search: combobox ARIA state tracks the dropdown', async () => {
  const { window, document, close } = await loadPage();
  try {
    const input = document.getElementById('place-search');
    assert.equal(input.getAttribute('aria-expanded'), 'false');

    input.value = 'camp';
    fire(window, input, 'input');
    assert.equal(input.getAttribute('aria-expanded'), 'true');

    fire(window, input, 'keydown', { key: 'ArrowDown' });
    const rows = document.querySelectorAll('#search-results .search-result');
    assert.equal(rows[0].getAttribute('aria-selected'), 'true');
    assert.equal(input.getAttribute('aria-activedescendant'), rows[0].id);

    fire(window, input, 'keydown', { key: 'Escape' });
    assert.equal(input.getAttribute('aria-expanded'), 'false');
    assert.equal(input.hasAttribute('aria-activedescendant'), false);
  } finally { close(); }
});

// ─── hash routing ────────────────────────────────────────────────────────────

test('hash: deep link to #region opens the detail view', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');

    assert.equal(document.getElementById('detail-view').style.display, 'flex');
    assert.equal(document.getElementById('region-title').textContent, 'Mystery Lake');
  } finally { close(); }
});

test('hash: deep link to #region/place opens with that place targeted', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#forlorn_muskeg/Forge%20Shed';
    fire(window, window, 'hashchange');

    assert.equal(document.getElementById('region-title').textContent, 'Forlorn Muskeg');
    // The detail view is up.
    assert.equal(document.getElementById('detail-view').style.display, 'flex');
  } finally { close(); }
});

test('hash: clearing the hash closes the detail view', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    assert.equal(document.getElementById('detail-view').style.display, 'flex');

    window.location.hash = '';
    fire(window, window, 'hashchange');
    assert.notEqual(document.getElementById('detail-view').style.display, 'flex');
  } finally { close(); }
});

test('hash: unknown region in hash leaves world view up', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#totally_made_up_region';
    fire(window, window, 'hashchange');

    // Detail view should NOT have opened.
    assert.notEqual(document.getElementById('detail-view').style.display, 'flex');
  } finally { close(); }
});

test('hash: navigating between regions updates the title', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    assert.equal(document.getElementById('region-title').textContent, 'Mystery Lake');

    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');
    assert.equal(document.getElementById('region-title').textContent, 'Coastal Highway');
  } finally { close(); }
});

// ─── world-view → region-button click → hash ─────────────────────────────────

test('world view: keyboard-activating a region label (click detail 0) opens detail', async () => {
  const { window, document, close } = await loadPage();
  try {
    // Region buttons live in the label-layer. A keyboard Enter/Space on a
    // focused button dispatches a click with detail 0 and clientX/Y 0 —
    // the handler must not rely on coordinates for this path.
    const labelLayer = document.getElementById('label-layer');
    const buttons = labelLayer.querySelectorAll('button');
    assert.ok(buttons.length > 0, 'expected region buttons in label-layer');

    const first = buttons[0];
    fire(window, first, 'click', { detail: 0 });

    assert.equal(document.getElementById('detail-view').style.display, 'flex');
    assert.ok(window.location.hash.length > 1);
    assert.ok(window.location.hash.includes(first.dataset.regionId),
      'the focused button\'s own region should open, not a hit-test neighbour');
  } finally { close(); }
});

test('world view: pointer-clicking a region label opens detail', async () => {
  const { window, document, close } = await loadPage();
  try {
    const labelLayer = document.getElementById('label-layer');
    const first = labelLayer.querySelectorAll('button')[0];
    // detail >= 1 marks a real pointer click; jsdom's zero-size rects make
    // the coordinate hit-test degenerate but the click must still open a
    // region rather than fall through.
    fire(window, first, 'click', { detail: 1 });

    assert.equal(document.getElementById('detail-view').style.display, 'flex');
    assert.ok(window.location.hash.length > 1);
  } finally { close(); }
});

test('world view: mobile viewport defaults to a centred cover zoom, desktop to fit', async () => {
  const { window, document, tick, close } = await loadPage();
  try {
    const scaleOf = () => {
      const m = document.getElementById('map-container').style.transform
        .match(/scale\(([\d.]+(?:e-?\d+)?)\)/);
      return m ? Number(m[1]) : NaN;
    };
    // Desktop (harness matchMedia stub matches nothing): plain contained fit.
    assert.equal(scaleOf(), 1, 'desktop keeps the whole-map fit');

    // Simulate a portrait phone: mobile breakpoint matches, viewport 390×844.
    // The contained fit of the 4017×2048 map is a ~200px strip there, so the
    // default must zoom until the map covers the viewport, centred.
    Object.defineProperty(window, 'innerWidth',  { value: 390, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 844, configurable: true });
    window.matchMedia = (query) => ({
      matches: true, media: query, onchange: null,
      addEventListener() {}, removeEventListener() {},
      addListener() {}, removeListener() {}, dispatchEvent: () => false,
    });
    fire(window, window, 'resize');
    await tick(200); // past the resize debounce

    const mc = document.getElementById('map-container');
    const scale = scaleOf();
    const scaledW = parseFloat(mc.style.width) * scale;
    const scaledH = parseFloat(mc.style.height) * scale;
    assert.ok(scale > 1, `mobile default should zoom in, got scale ${scale}`);
    assert.ok(scaledW >= 390 - 1 && scaledH >= 844 - 1,
      `map should cover the viewport, got ${scaledW}×${scaledH}`);
    const panX = Number(mc.style.transform.match(/translate\((-?[\d.]+(?:e-?\d+)?)px/)[1]);
    assert.ok(Math.abs(panX - (390 - scaledW) / 2) < 1, 'crop is horizontally centred');
  } finally { close(); }
});

// ─── layers panel ───────────────────────────────────────────────────────────

const layerRow = (document, tag) =>
  document.querySelector(`#layers-panel .layer-row[data-tag="${tag}"]`);
const markerCount = (document) =>
  document.querySelectorAll('#markers-layer .layer-marker').length;

test('layers panel: opening a region lists its resources and local tools', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');
    assert.ok(layerRow(document, 'cattails'), 'expected a cattails row on Coastal Highway');
    assert.ok(layerRow(document, 'workbench'), 'expected a workbench row on Coastal Highway');
    assert.ok(Number(layerRow(document, 'workbench').querySelector('.layer-count').textContent) > 1);
    assert.equal(layerRow(document, 'cattails').getAttribute('aria-pressed'), 'false');
    assert.equal(markerCount(document), 0);
  } finally { close(); }
});

test('layers panel: toggling a layer rings every hit and dims the map', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    const row = layerRow(document, 'bear');
    const count = Number(row.querySelector('.layer-count').textContent);

    fire(window, row, 'click');
    assert.equal(row.getAttribute('aria-pressed'), 'true');
    assert.equal(markerCount(document), count);
    assert.ok(document.getElementById('map-canvas').classList.contains('layers-on'));
    const clear = document.getElementById('layers-clear');
    assert.equal(clear.hidden, false);
    assert.equal(clear.textContent, 'Clear (1)');

    // A second layer adds its rings on top.
    const wolf = layerRow(document, 'wolf');
    fire(window, wolf, 'click');
    assert.equal(markerCount(document),
      count + Number(wolf.querySelector('.layer-count').textContent));

    fire(window, row, 'click');
    fire(window, wolf, 'click');
    assert.equal(row.getAttribute('aria-pressed'), 'false');
    assert.equal(markerCount(document), 0);
    assert.ok(!document.getElementById('map-canvas').classList.contains('layers-on'));
  } finally { close(); }
});

test('layers panel: tool layer rings each place with that tool', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');
    const row = layerRow(document, 'workbench');
    fire(window, row, 'click');
    assert.equal(markerCount(document), Number(row.querySelector('.layer-count').textContent));
  } finally { close(); }
});

test('layers panel: $resource deep link turns the layer on; toggling off drops it from the hash', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway/' + encodeURIComponent('$resource:cattails');
    fire(window, window, 'hashchange');
    const row = layerRow(document, 'cattails');
    assert.equal(row.getAttribute('aria-pressed'), 'true');
    assert.ok(markerCount(document) > 0);

    fire(window, row, 'click');
    assert.equal(window.location.hash, '#coastal_highway');
    assert.equal(markerCount(document), 0);
  } finally { close(); }
});

test('layers panel: layers follow region switches and clear on close', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    fire(window, layerRow(document, 'bear'), 'click');

    window.location.hash = '#pleasant_valley';
    fire(window, window, 'hashchange');
    const pvBear = layerRow(document, 'bear');
    assert.ok(pvBear, 'expected a bear row on Pleasant Valley');
    assert.equal(pvBear.getAttribute('aria-pressed'), 'true');
    assert.equal(markerCount(document), Number(pvBear.querySelector('.layer-count').textContent));

    fire(window, document.getElementById('back-btn'), 'click');
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    assert.equal(layerRow(document, 'bear').getAttribute('aria-pressed'), 'false');
    assert.equal(markerCount(document), 0);
  } finally { close(); }
});

test('layers panel: collapse state toggles and is remembered', async () => {
  const { window, document, close } = await loadPage();
  try {
    const panel = document.getElementById('layers-panel');
    const toggle = document.getElementById('layers-toggle');
    assert.ok(!panel.classList.contains('collapsed'), 'desktop starts expanded');
    fire(window, toggle, 'click');
    assert.ok(panel.classList.contains('collapsed'));
    assert.equal(toggle.getAttribute('aria-expanded'), 'false');
    assert.equal(window.localStorage.getItem('ldm.layersCollapsed.v1'), '1');
  } finally { close(); }
});

test('region picker: choosing a region opens it with a way back', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    const select = document.getElementById('region-select');
    assert.equal(select.value, 'mystery_lake');

    select.value = 'forlorn_muskeg';
    fire(window, select, 'change');
    assert.equal(window.location.hash, '#forlorn_muskeg');
    assert.equal(document.getElementById('region-title').textContent, 'Forlorn Muskeg');
    const back = document.getElementById('back-to-origin-btn');
    assert.ok(!back.hidden);
    assert.match(back.textContent, /Mystery Lake/);
  } finally { close(); }
});

test('region info: difficulty and in-game description show when the wiki has them', async () => {
  const { window, document, close } = await loadPage();
  try {
    const info = document.getElementById('region-info');
    const badge = document.getElementById('region-difficulty');
    const desc = document.getElementById('region-description');
    window.location.hash = '#forlorn_muskeg';
    fire(window, window, 'hashchange');
    assert.equal(info.hidden, false);
    assert.equal(badge.textContent, 'Advanced');
    assert.equal(badge.dataset.level, 'advanced');
    assert.match(desc.textContent, /marshland/);

    // Click opens the bubble; Escape closes it without closing the region.
    fire(window, badge, 'click');
    assert.ok(info.classList.contains('open'));
    assert.equal(badge.getAttribute('aria-expanded'), 'true');
    fire(window, document, 'keydown', { key: 'Escape' });
    assert.ok(!info.classList.contains('open'));
    assert.equal(document.getElementById('detail-view').style.display, 'flex');

    // Difficulty without a description: badge only, nothing to open.
    window.location.hash = '#ravine';
    fire(window, window, 'hashchange');
    assert.equal(info.hidden, false);
    assert.ok(!info.classList.contains('has-description'));
    assert.equal(badge.disabled, true);

    window.location.hash = '#winding_river';
    fire(window, window, 'hashchange');
    assert.equal(info.hidden, true);
  } finally { close(); }
});

// ─── visited places ───────────────────────────────────────────────────────────

test('visited: clicking a place toggles the mark, progress, and storage', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');
    const targets = document.querySelectorAll('#places-layer .place-target');
    assert.ok(targets.length > 0, 'sanity: coastal_highway has place targets');
    const progress = document.getElementById('visited-progress');
    assert.equal(progress.textContent, `✓ 0/${targets.length} visited`);

    fire(window, targets[0], 'click');
    assert.ok(targets[0].classList.contains('visited'));
    assert.equal(progress.textContent, `✓ 1/${targets.length} visited`);
    const stored = JSON.parse(window.localStorage.getItem('ldm.looted.v1'));
    assert.equal(stored.coastal_highway.length, 1);

    fire(window, targets[0], 'click');
    assert.ok(!targets[0].classList.contains('visited'));
    assert.equal(progress.textContent, `✓ 0/${targets.length} visited`);
  } finally { close(); }
});

test('visited: search results mark visited places with ✓', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');
    fire(window, document.querySelector('#places-layer .place-target'), 'click');
    const [name] = JSON.parse(window.localStorage.getItem('ldm.looted.v1')).coastal_highway;

    const input = document.getElementById('place-search');
    input.value = name;
    fire(window, input, 'input');
    const row = [...document.querySelectorAll('.search-result')]
      .find(r => r.querySelector('.result-name').firstChild.textContent === name);
    assert.ok(row, `expected a result row for ${name}`);
    assert.ok(row.querySelector('.result-visited'), 'visited row carries a ✓');
  } finally { close(); }
});

test('layers panel: Clear turns every layer off', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    fire(window, layerRow(document, 'bear'), 'click');
    fire(window, layerRow(document, 'wolf'), 'click');
    const clear = document.getElementById('layers-clear');
    assert.equal(clear.textContent, 'Clear (2)');
    fire(window, clear, 'click');
    assert.equal(markerCount(document), 0);
    assert.equal(clear.hidden, true);
    assert.equal(layerRow(document, 'bear').getAttribute('aria-pressed'), 'false');
  } finally { close(); }
});

test('find on map: a missing tool lights up regions that have it', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');
    // Mystery Lake has workbenches but no forge.
    assert.ok(layerRow(document, 'workbench'), 'workbench is a toggle here');
    const forge = document.querySelector('#crafting-list .find-row[data-tool="forge"]');
    assert.ok(forge, 'forge gets a Find on map row');

    fire(window, forge, 'click');
    assert.notEqual(document.getElementById('detail-view').style.display, 'flex');
    const banner = document.getElementById('find-banner');
    assert.equal(banner.hidden, false);
    assert.match(document.getElementById('find-sub').textContent, /Forlorn Muskeg/);
    const lit = [...document.querySelectorAll('.region-btn.find-has')].map(b => b.dataset.regionId);
    assert.ok(lit.includes('forlorn_muskeg'));
    assert.ok(!lit.includes('mystery_lake'));
    assert.ok(document.querySelector('.region-btn.find-here[data-region-id="mystery_lake"]'));
    assert.ok(document.querySelector('#find-route polyline'));

    // Opening a lit region turns the forge layer on there.
    fire(window, document.querySelector('.region-btn.find-has[data-region-id="forlorn_muskeg"]'), 'click');
    assert.equal(layerRow(document, 'forge').getAttribute('aria-pressed'), 'true');

    fire(window, document.getElementById('back-btn'), 'click');
    fire(window, document.getElementById('find-close'), 'click');
    assert.equal(banner.hidden, true);
    assert.equal(document.querySelectorAll('.region-btn.find-has').length, 0);
  } finally { close(); }
});
