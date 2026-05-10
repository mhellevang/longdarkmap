'use strict';

// Loads index.html into jsdom for DOM-level tests. Stubs out all network
// resources except src/logic.js (served from disk) so tests don't depend on
// images or CSS being fetchable.
//
// Usage:
//   const { loadPage } = require('./harness');
//   const { window, document, tick, close } = await loadPage();
//   ... drive the page ...
//   close();

const path = require('path');
const fs = require('fs');
const { JSDOM, requestInterceptor } = require('jsdom');

const ROOT = path.join(__dirname, '..');

async function loadPage() {
  const interceptor = requestInterceptor(async (request) => {
    const url = request.url;
    if (url.endsWith('/src/logic.js')) {
      return new Response(fs.readFileSync(path.join(ROOT, 'src/logic.js'), 'utf8'), {
        headers: { 'Content-Type': 'application/javascript' },
      });
    }
    // Stub everything else (CSS, images) with empty bytes — tests don't need them.
    return new Response('', { headers: { 'Content-Type': 'text/plain' } });
  });

  const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
  // url must be http(s) so history.pushState works (jsdom blocks pushState
  // against file:// origins). The interceptor handles all relative URLs.
  const dom = new JSDOM(html, {
    url: 'http://localhost:8765/',
    runScripts: 'dangerously',
    resources: { interceptors: [interceptor] },
    pretendToBeVisual: true,
  });
  const { window } = dom;

  // Wait for window 'load' (after all scripts execute) plus a microtask flush.
  await new Promise(resolve => {
    if (window.document.readyState === 'complete') resolve();
    else window.addEventListener('load', resolve, { once: true });
  });
  await tick(window, 0);

  // The world-map image won't actually load (we stub it). Trigger a synthetic
  // resize so layoutWorldMap() runs and renderLabels() populates region buttons.
  window.dispatchEvent(new window.Event('resize'));
  await tick(window, 0);

  return {
    window,
    document: window.document,
    tick: (ms) => tick(window, ms),
    close: () => window.close(),
  };
}

function tick(window, ms = 0) {
  // Yield to jsdom's event loop. Most DOM-event-driven updates are synchronous
  // but listeners that schedule via rAF/setTimeout(0) need a turn.
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

// Build a real Event the page's listeners will accept. Helper around new Event().
function fire(window, target, type, init = {}) {
  let event;
  if (type === 'input' || type === 'change') {
    event = new window.Event(type, { bubbles: true, ...init });
  } else if (type.startsWith('key')) {
    event = new window.KeyboardEvent(type, { bubbles: true, ...init });
  } else if (type === 'click' || type.startsWith('mouse') || type === 'dblclick') {
    event = new window.MouseEvent(type, { bubbles: true, cancelable: true, ...init });
  } else {
    event = new window.Event(type, { bubbles: true, ...init });
  }
  target.dispatchEvent(event);
  return event;
}

module.exports = { loadPage, fire };
