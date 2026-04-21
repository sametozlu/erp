const CACHE_NAME = 'v12-map-v1';
const ASSETS = [
    '/static/css/style.css',
    '/static/js/networking/retry-helper.js',
    '/static/js/networking/routing-cache.js',
    '/static/js/ui/loading-manager.js',
    '/static/js/offline/offline-manager.js',
    '/static/js/map/vehicle-manager.js',
    '/static/js/workers/map-worker.js',
    '/static/app.js',
    '/static/bazistasyonu.png',
    '/static/netmon_logo.png'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS);
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
                if (key !== CACHE_NAME) {
                    return caches.delete(key);
                }
            }));
        })
    );
});

self.addEventListener('fetch', (event) => {
    // Only handle GET requests
    if (event.request.method !== 'GET') return;

    // Skip API requests (handled by OfflineManager) - OR cache them specifically?
    // Let's cache static assets primarily.
    const url = new URL(event.request.url);

    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(event.request).then((response) => {
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }
                    const responseToCache = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                    return response;
                });
            })
        );
    }
});
