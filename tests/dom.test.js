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

test('world view: clicking a region label updates the hash and opens detail', async () => {
  const { window, document, close } = await loadPage();
  try {
    // Region buttons live in the label-layer.
    const labelLayer = document.getElementById('label-layer');
    const buttons = labelLayer.querySelectorAll('button');
    assert.ok(buttons.length > 0, 'expected region buttons in label-layer');

    const first = buttons[0];
    fire(window, first, 'click');

    assert.equal(document.getElementById('detail-view').style.display, 'flex');
    assert.ok(window.location.hash.length > 1);
  } finally { close(); }
});

// ─── resources panel (legend-icon cycle) ────────────────────────────────────

test('resources panel: opening a region populates pills for present resources', async () => {
  const { window, document, close } = await loadPage();
  try {
    // Mystery Lake has hits in all 5 resource classes.
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');

    const pills = document.querySelectorAll('#resources-panel .resource-pill');
    assert.ok(pills.length >= 1, 'expected at least one resource pill');
  } finally { close(); }
});

test('resources panel: clicking a pill activates it and updates the hash to $resource:', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake';
    fire(window, window, 'hashchange');

    const moosePill = document.querySelector('#resources-panel .resource-pill[data-tag="moose"]');
    assert.ok(moosePill, 'expected a moose pill on Mystery Lake');
    fire(window, moosePill, 'click');

    assert.ok(moosePill.classList.contains('active'), 'pill should be active after click');
    // $ encodes to %24, : encodes to %3A in the URL fragment.
    assert.match(window.location.hash, /(?:\$|%24)resource(?:%3A|:)moose/);
  } finally { close(); }
});

test('resources panel: re-clicking the same pill cycles to the next hit (index shown)', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');

    // Coastal Highway has many cattail hits, so cycling is observable.
    const cattPill = document.querySelector('#resources-panel .resource-pill[data-tag="cattails"]');
    assert.ok(cattPill, 'expected a cattails pill on Coastal Highway');

    fire(window, cattPill, 'click');
    const firstIdx = cattPill.querySelector('.resource-pill-index').textContent;
    assert.match(firstIdx, /^1 \/ \d+$/, `first click should show "1 / N", got "${firstIdx}"`);

    fire(window, cattPill, 'click');
    const secondIdx = cattPill.querySelector('.resource-pill-index').textContent;
    assert.match(secondIdx, /^2 \/ \d+$/, `second click should show "2 / N", got "${secondIdx}"`);
  } finally { close(); }
});

test('resources panel: hash deep-link to a resource hit activates the pill', async () => {
  const { window, document, close } = await loadPage();
  try {
    // Direct URL hit: open Coastal Highway at cattails hit #2.
    window.location.hash = '#coastal_highway/' + encodeURIComponent('$resource:cattails') + '/2';
    fire(window, window, 'hashchange');

    const cattPill = document.querySelector('#resources-panel .resource-pill[data-tag="cattails"]');
    assert.ok(cattPill, 'expected a cattails pill after deep-link');
    assert.ok(cattPill.classList.contains('active'), 'deep-linked pill should be active');
    assert.equal(cattPill.querySelector('.resource-pill-index').textContent.startsWith('2 / '), true);
  } finally { close(); }
});

test('tool pill: clicking "Workbench here" cycles through instances', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');

    let pill = document.querySelector('#tools-nearby .tool-pill[data-tool="workbench"].here');
    assert.ok(pill, 'expected "Workbench here" pill on CH');

    // First click: cycle activates, index shows "1 / N", pill goes .cycling.
    fire(window, pill, 'click');
    pill = document.querySelector('#tools-nearby .tool-pill[data-tool="workbench"]');
    assert.ok(pill.classList.contains('cycling'), 'pill should be cycling after first click');
    const idx1 = pill.querySelector('.tool-pill-cycle-index').textContent;
    assert.match(idx1, /^1 \/ \d+$/, `first click should show "1 / N", got "${idx1}"`);
    const hashAfter1 = decodeURIComponent(window.location.hash);
    assert.match(hashAfter1, /\/.+\/workbench$/, 'hash should carry place + workbench filter');

    // Second click: advances to "2 / N", hash points at a different place.
    fire(window, pill, 'click');
    pill = document.querySelector('#tools-nearby .tool-pill[data-tool="workbench"]');
    const idx2 = pill.querySelector('.tool-pill-cycle-index').textContent;
    assert.match(idx2, /^2 \/ \d+$/, `second click should show "2 / N", got "${idx2}"`);
    const hashAfter2 = decodeURIComponent(window.location.hash);
    assert.notEqual(hashAfter1, hashAfter2,
      'second click should navigate to a different place');
  } finally { close(); }
});

test('tool pill: ✕ exits the cycle and drops the place from the hash', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');

    let pill = document.querySelector('#tools-nearby .tool-pill[data-tool="workbench"].here');
    fire(window, pill, 'click');
    pill = document.querySelector('#tools-nearby .tool-pill[data-tool="workbench"]');
    assert.ok(pill.classList.contains('cycling'), 'sanity: cycling after click');

    const xBtn = pill.querySelector('.tool-pill-cycle-close');
    assert.ok(xBtn, 'expected ✕ on cycling tool pill');
    fire(window, xBtn, 'click');

    pill = document.querySelector('#tools-nearby .tool-pill[data-tool="workbench"]');
    assert.ok(!pill.classList.contains('cycling'), '✕ should exit cycling');
    assert.equal(window.location.hash, '#coastal_highway',
      'hash should drop the place segment after ✕');
    assert.equal(document.getElementById('detail-view').style.display, 'flex',
      'modal should stay open after ✕');
  } finally { close(); }
});

test('resources panel: pill ✕ deselects the active resource (keeps modal open)', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#coastal_highway/' + encodeURIComponent('$resource:cattails') + '/2';
    fire(window, window, 'hashchange');

    const cattPill = document.querySelector('#resources-panel .resource-pill[data-tag="cattails"]');
    assert.ok(cattPill && cattPill.classList.contains('active'),
      'sanity: cattails pill should be active before exit');

    const closeBtn = cattPill.querySelector('.resource-pill-close');
    assert.ok(closeBtn, 'expected a ✕ inside the active pill');
    fire(window, closeBtn, 'click');

    assert.ok(!cattPill.classList.contains('active'),
      'pill should no longer be active after ✕ click');
    // Modal stays open — only the cycle is cleared.
    assert.equal(document.getElementById('detail-view').style.display, 'flex',
      'modal should remain open after pill ✕');
    // Hash drops the resource segment but keeps the region.
    assert.equal(window.location.hash, '#coastal_highway');
  } finally { close(); }
});

test('resources panel: ESC clears the active resource before closing the modal', async () => {
  const { window, document, close } = await loadPage();
  try {
    window.location.hash = '#mystery_lake/' + encodeURIComponent('$resource:moose') + '/2';
    fire(window, window, 'hashchange');

    const moosePill = document.querySelector('#resources-panel .resource-pill[data-tag="moose"]');
    assert.ok(moosePill && moosePill.classList.contains('active'),
      'sanity: moose pill should be active before ESC');

    // First ESC: clears the cycle, modal stays open.
    fire(window, document, 'keydown', { key: 'Escape' });
    assert.ok(!moosePill.classList.contains('active'),
      'first ESC should clear the active pill');
    assert.equal(document.getElementById('detail-view').style.display, 'flex',
      'first ESC should leave the modal open');
    assert.equal(window.location.hash, '#mystery_lake');

    // Second ESC: closes the modal as before.
    fire(window, document, 'keydown', { key: 'Escape' });
    assert.notEqual(document.getElementById('detail-view').style.display, 'flex',
      'second ESC should close the modal');
  } finally { close(); }
});

test('resources panel: switching region clears the previous active pill', async () => {
  const { window, document, close } = await loadPage();
  try {
    // Open Mystery Lake on moose hit #2.
    window.location.hash = '#mystery_lake/' + encodeURIComponent('$resource:moose') + '/2';
    fire(window, window, 'hashchange');
    const mooseBefore = document.querySelector('#resources-panel .resource-pill[data-tag="moose"]');
    assert.ok(mooseBefore && mooseBefore.classList.contains('active'),
      'sanity: moose pill should be active before switching region');

    // Switch to Coastal Highway with no resource hash — moose pill should
    // no longer exist (different region's pill set) and no pill should be
    // marked active.
    window.location.hash = '#coastal_highway';
    fire(window, window, 'hashchange');

    const activePills = document.querySelectorAll('#resources-panel .resource-pill.active');
    assert.equal(activePills.length, 0,
      'no pill should remain active after switching to a non-resource hash');
  } finally { close(); }
});
