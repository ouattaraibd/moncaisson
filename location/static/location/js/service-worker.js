const CACHE_NAME = 'moncaisson-v1';
const ASSETS = [
  '/static/location/css/styles.css',
  '/static/location/js/scripts.js',
  '/static/location/images/logo.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => response || fetch(event.request))
  );
});