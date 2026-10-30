/**
 * Service Worker Oficial de StockAgent PWA
 * Soporte Offline-First y Resiliencia ante Microcortes de Red WiFi en Depósito.
 */

const CACHE_NAME = 'stockagent-pwa-v1';

const STATIC_ASSETS = [
  '/',
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
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. Estrategia de Enrutamiento y Fetch Resiliente
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Ignorar peticiones no GET y tráfico WebSocket de Flet (/ws)
  if (req.method !== 'GET' || url.protocol.startsWith('ws') || url.pathname.startsWith('/ws')) {
    return;
  }

  // A. Peticiones de Navegación HTML (páginas completas)
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((networkResponse) => {
          // Si respondió la red, guardar copia en caché y retornar
          if (networkResponse && networkResponse.status === 200) {
            const copy = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return networkResponse;
        })
        .catch(async () => {
          // Si falló la red (microcorte WiFi), intentar responder con la página cacheada
          const cachedPage = await caches.match(req);
          if (cachedPage) {
            return cachedPage;
          }
          // Si no está la página específica, servir la pantalla de fallback offline
          const offlinePage = await caches.match('/offline.html');
          return offlinePage || new Response('Sin conexión a la red local.', {
            headers: { 'Content-Type': 'text/plain; charset=utf-8' },
          });
        })
    );
    return;
  }

  // B. Recursos Estáticos (imágenes, fuentes, css, scripts)
  event.respondWith(
    caches.match(req).then((cachedResponse) => {
      if (cachedResponse) {
        // Stale-While-Revalidate: retornar caché de inmediato y actualizar en segundo plano si hay red
        fetch(req).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(req, networkResponse));
          }
        }).catch(() => {
          // Silencioso ante falta de red
        });
        return cachedResponse;
      }

      // Si no estaba en caché, pedir a la red
      return fetch(req).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const copy = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        }
        return networkResponse;
      }).catch(async () => {
        if (req.headers.get('accept') && req.headers.get('accept').includes('text/html')) {
          return caches.match('/offline.html');
        }
        return new Response('', { status: 408, statusText: 'Offline' });
      });
    })
  );
});
