/**
 * Service Worker Oficial de StockAgent PWA
 * Soporte Offline-First y Resiliencia ante Microcortes de Red WiFi en Depósito.
 */

const CACHE_NAME = 'stockagent-pwa-v3';

const STATIC_ASSETS = [
  '/manifest.json',
  '/favicon.ico',
  '/favicon.png',
  '/offline.html',
  '/scanner.html',
  '/css/scanner.css',
  '/js/scanner.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-192.png',
  '/icons/icon-maskable-512.png',
];

// 1. Instalación y Precaching de la Shell de la Aplicación
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-cacheados recursos estáticos de StockAgent');
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] Aviso durante precache:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// 2. Activación y Limpieza de Cachés Previos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            console.log('[SW] Eliminando caché antiguo:', name);
            return caches.delete(name);
          }
          // Limpiar index.html y FontManifest antiguos si quedaron guardados en v1
          return caches.open(name).then((c) => {
            c.delete('/');
            c.delete('/index.html');
            c.delete('/assets/FontManifest.json');
          });
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. Estrategia de Enrutamiento y Fetch Resiliente
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Ignorar peticiones no GET, orígenes externos y tráfico WebSocket/motor de Flet (/ws, .wasm, canvaskit)
  if (
    req.method !== 'GET' ||
    url.origin !== self.location.origin ||
    url.protocol.startsWith('ws') ||
    url.pathname.startsWith('/ws') ||
    url.pathname.endsWith('.wasm') ||
    url.pathname.endsWith('.mjs') ||
    url.pathname.includes('canvaskit') ||
    url.pathname.includes('main.dart') ||
    url.pathname.includes('flutter_bootstrap') ||
    url.pathname.includes('FontManifest') ||
    url.pathname.includes('AssetManifest')
  ) {
    return;
  }

  // A. Peticiones de Navegación HTML (páginas completas)
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(async () => {
        // Si falló la red (microcorte WiFi), intentar responder con la página cacheada o contingencia offline
        const cachedPage = await caches.match(req);
        if (cachedPage) {
          return cachedPage;
        }
        const offlinePage = await caches.match('/offline.html');
        return offlinePage || new Response('Sin conexión a la red local.', {
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
      })
    );
    return;
  }

  // B. Recursos Estáticos propios (iconos, scanner offline, css, manifest)
  event.respondWith(
    caches.match(req).then((cachedResponse) => {
      if (cachedResponse) {
        fetch(req).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(req, networkResponse));
          }
        }).catch(() => {});
        return cachedResponse;
      }

      return fetch(req).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }
        const responseToCache = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(req, responseToCache);
        });
        return networkResponse;
      }).catch(async () => {
        if (req.headers.get('accept')?.includes('text/html')) {
          return caches.match('/offline.html');
        }
        return new Response('', { status: 408, statusText: 'Offline' });
      });
    })
  );
});
