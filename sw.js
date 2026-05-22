// Service worker for The Long Dark Interactive Map.
//
// Strategy: pre-cache the entire app on install (app shell + every region
// map image, ~72 MB). Once installed the site works fully offline — useful
// on a plane, in the woods, or anywhere without signal.
//
// To force clients to refetch after changing any bundled asset, bump
// CACHE_VERSION. The old cache is dropped on activate.

const CACHE_VERSION = 'v3';
const CACHE_NAME = `longdarkmap-${CACHE_VERSION}`;

// Runtime assets. data/*.json, data/tiles/, and data/legend_icons/ are
// build-time only — their contents are inlined into index.html by the
// Python tools — so they don't need to be cached.
const PRECACHE_URLS = [
  './',
  './index.html',
  './styles.css',
  './src/logic.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-180.png',
  './icons/icon-maskable-512.png',
  './maps/2899955301_preview_GREAT_BEAR_ISLAND_MAP_v12.jpg',
  './maps/ash_canyon.jpg',
  './maps/ash_canyon_loper.jpg',
  './maps/blackrock.jpg',
  './maps/blackrock_loper.jpg',
  './maps/bleak_inlet.jpg',
  './maps/bleak_inlet_loper.jpg',
  './maps/broken_railroad.jpg',
  './maps/broken_railroad_loper.jpg',
  './maps/coastal_highway.jpg',
  './maps/coastal_highway_loper.jpg',
  './maps/crumbling_highway.jpg',
  './maps/desolation_point.jpg',
  './maps/desolation_point_loper.jpg',
  './maps/far_range_branch_line.jpg',
  './maps/far_range_branch_line_loper.jpg',
  './maps/forlorn_muskeg.jpg',
  './maps/forlorn_muskeg_loper.jpg',
  './maps/forsaken_airfield.jpg',
  './maps/forsaken_airfield_loper.jpg',
  './maps/hushed_river_valley.jpg',
  './maps/hushed_river_valley_loper.jpg',
  './maps/keepers_pass.jpg',
  './maps/keepers_pass_loper.jpg',
  './maps/mountain_town.jpg',
  './maps/mountain_town_loper.jpg',
  './maps/mystery_lake.jpg',
  './maps/mystery_lake_loper.jpg',
  './maps/pleasant_valley.jpg',
  './maps/pleasant_valley_loper.jpg',
  './maps/ravine.jpg',
  './maps/ravine_loper.jpg',
  './maps/sundered_pass.jpg',
  './maps/sundered_pass_loper.jpg',
  './maps/timberwolf_mountain.jpg',
  './maps/timberwolf_mountain_loper.jpg',
  './maps/transfer_pass.jpg',
  './maps/transfer_pass_loper.jpg',
  './maps/winding_river_and_carter_hydro_dam.jpg',
  './maps/winding_river_and_carter_hydro_dam_loper.jpg',
  './maps/zone_of_contamination.jpg',
  './maps/zone_of_contamination_loper.jpg',
];

// Install: open the cache and add every URL. cache.addAll is atomic — if
// any single fetch fails the install fails and the SW retries on the
// next page load. That's the behaviour we want: we don't want a partial
// cache that silently misses a region map when offline.
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// Activate: drop any old caches from previous versions, then take control
// of all open tabs so they start using this SW immediately (no reload).
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Fetch: cache-first. If the request is in the cache, serve it. Otherwise
// try the network and stash a copy on the way back. Only GETs are cached;
// everything else (e.g. the dev server's POST /api/place-box) goes
// straight to the network so editing tooling still works locally.
self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  // Skip cross-origin requests — we only own same-origin assets, and
  // caching opaque responses can quietly waste storage.
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).then(response => {
        // Only cache successful, basic (same-origin) responses.
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
        return response;
      }).catch(() => {
        // Offline and not cached. For navigations, fall back to the cached
        // shell so the user still lands in the app instead of a browser
        // error page.
        if (request.mode === 'navigate') {
          return caches.match('./index.html');
        }
        return Response.error();
      });
    })
  );
});
