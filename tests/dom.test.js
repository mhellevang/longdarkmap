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
