const CACHE_NAME = 'elide-pwa-v12';
const ASSETS_TO_CACHE = [
  '/',
  '/soutenir',
  '/partenariat',
  '/elide-track',
  '/static/css/style.css?v=9',
  '/static/js/app.js?v=12',
  '/static/js/lucide.min.js',
  '/static/assets/logo-vert.png',
  '/static/assets/logo-noir.png',
  '/static/assets/icon-192.png',
  '/static/assets/icon-512.png',
  '/static/assets/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.allSettled(ASSETS_TO_CACHE.map((url) => cache.add(url)))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/lang/')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then((cached) => cached || caches.match('/'))
      )
  );
});
