// Service worker for The Long Dark Interactive Map.
//
// Two caches:
//  - SHELL_CACHE (versioned): index.html, styles, logic, manifest, icons.
//    Precached on install (a few hundred KB), then served
//    stale-while-revalidate — instant offline-friendly loads, and deploys
//    reach users on their next visit without a manual version bump.
//  - MAPS_CACHE (unversioned): the region map images (~70 MB in total).
//    Filled lazily as the user opens regions, or in bulk via the page's
//    "Save all maps offline" button, which writes into this cache directly
//    (keep the name in sync with MAPS_CACHE_NAME in index.html). Survives
//    shell deploys, so updating the app never re-downloads the maps.
//
// Bump SHELL_VERSION only to force an immediate refetch of everything in
// the shell — stale-while-revalidate already picks up changes one visit
// after a deploy.

const SHELL_VERSION = 'v4';
const SHELL_CACHE = `longdarkmap-shell-${SHELL_VERSION}`;
const MAPS_CACHE = 'longdarkmap-maps-v1';

// The world map is the first thing every visitor sees; treat it as part of
// the initial precache (but into MAPS_CACHE, and non-fatally — see install).
const WORLD_MAP = './maps/2899955301_preview_GREAT_BEAR_ISLAND_MAP_v12.jpg';

const SHELL_URLS = [
  './',
  './index.html',
  './styles.css',
  './src/logic.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-180.png',
  './icons/icon-maskable-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL_CACHE);
    await shell.addAll(SHELL_URLS);
    // Best-effort world-map precache: don't fail the whole install over one
    // large image — the fetch handler lazy-caches it on first view anyway.
    try {
      const maps = await caches.open(MAPS_CACHE);
      if (!(await maps.match(WORLD_MAP))) await maps.add(WORLD_MAP);
    } catch (e) { /* lazy-cached on first view instead */ }
    await self.skipWaiting();
  })());
});

// Activate: migrate region maps out of the old single-cache layout
// (longdarkmap-v1..v3 precached everything together) so existing users
// don't re-download ~70 MB, then drop every cache we don't own anymore.
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const maps = await caches.open(MAPS_CACHE);
    for (const key of await caches.keys()) {
      if (key === SHELL_CACHE || key === MAPS_CACHE) continue;
      const old = await caches.open(key);
      for (const req of await old.keys()) {
        if (!new URL(req.url).pathname.includes('/maps/')) continue;
        if (await maps.match(req)) continue;
        const res = await old.match(req);
        if (res) await maps.put(req, res);
      }
      await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

// Fetch routing. Only same-origin GETs are handled; everything else (e.g.
// the dev server's POST /api/place-box) goes straight to the network.
self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Maps: cache-first into MAPS_CACHE. The images are immutable in practice
  // (updates come with new content anyway), so no revalidation.
  if (url.pathname.includes('/maps/')) {
    event.respondWith((async () => {
      const maps = await caches.open(MAPS_CACHE);
      const cached = await maps.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (response && response.status === 200 && response.type === 'basic') {
        maps.put(request, response.clone());
      }
      return response;
    })());
    return;
  }

  // Shell: stale-while-revalidate. Serve the cached copy immediately and
  // refresh it in the background, so a deploy is picked up on the visit
  // after it lands. Offline navigations fall back to the cached index.html.
  event.respondWith((async () => {
    const shell = await caches.open(SHELL_CACHE);
    const cached = await shell.match(request);
    const refresh = fetch(request).then(response => {
      if (response && response.status === 200 && response.type === 'basic') {
        shell.put(request, response.clone());
      }
      return response;
    }).catch(() => null);
    if (cached) {
      event.waitUntil(refresh);
      return cached;
    }
    const fresh = await refresh;
    if (fresh) return fresh;
    if (request.mode === 'navigate') {
      const fallback = await shell.match('./index.html');
      if (fallback) return fallback;
    }
    return Response.error();
  })());
});
