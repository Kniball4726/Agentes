// @ts-check
/// <reference no-default-lib="true" />
/// <reference lib="es2022" />
/// <reference lib="webworker" />
/**
 * Service Worker Oficial de StockAgent PWA
 * Soporte Offline-First y Resiliencia ante Microcortes de Red WiFi en Depósito.
 */

const sw = /** @type {ServiceWorkerGlobalScope} */ (/** @type {unknown} */ (self));

const CACHE_NAME = 'stockagent-pwa-v4';

const STATIC_ASSETS = [
  '/manifest.json',
  '/favicon.ico',
  '/favicon.png',
  '/offline.html',
  '/scanner.html',
  '/css/scanner.css',
  '/js/scanner.js',
  '/fonts/Inter-Regular.ttf',
  '/fonts/Inter-Medium.ttf',
  '/fonts/Inter-SemiBold.ttf',
  '/fonts/Inter-Bold.ttf',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-192.png',
  '/icons/icon-maskable-512.png',
];

const STATIC_PREFIXES = ['/css/', '/js/', '/icons/', '/fonts/'];
const SENSITIVE_PREFIXES = [
  '/api/',
  '/documentos/',
  '/documentacion/',
  '/docs/',
  '/descargas/',
  '/actualizaciones/',
];

/**
 * Determina si una ruta corresponde exclusivamente a un activo estático público cacheable.
 * @param {string} pathname
 * @returns {boolean}
 */
function esRecursoEstaticoPermitido(pathname) {
  if (STATIC_ASSETS.includes(pathname)) {
    return true;
  }
  return STATIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

/**
 * Determina si una solicitud debe omitir completamente el caché del Service Worker.
 * @param {Request} req
 * @param {URL} url
 * @returns {boolean}
 */
function debeOmitirCache(req, url) {
  if (
    req.method !== 'GET' ||
    url.origin !== sw.location.origin ||
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
    return true;
  }
  // En el propio servidor local (localhost / 127.0.0.1), la navegación principal '/' va directo a Flet
  if (
    req.mode === 'navigate' &&
    (url.hostname === 'localhost' || url.hostname === '127.0.0.1') &&
    url.pathname !== '/scanner.html'
  ) {
    return true;
  }
  if (SENSITIVE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return true;
  }
  if (req.headers.has('Authorization') || url.searchParams.has('dt')) {
    return true;
  }
  return false;
}

/**
 * Comprueba si las cabeceras de respuesta permiten almacenamiento en CacheStorage.
 * @param {Response} response
 * @returns {boolean}
 */
function respuestaEsCacheable(response) {
  if (!response || response.status !== 200 || response.type !== 'basic') {
    return false;
  }
  const cacheControl = (response.headers.get('Cache-Control') || '').toLowerCase();
  if (cacheControl.includes('no-store') || cacheControl.includes('private')) {
    return false;
  }
  return true;
}

// 1. Instalación y Precaching de la Shell de la Aplicación
sw.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-cacheados recursos estáticos de StockAgent');
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] Aviso durante precache:', err);
      });
    }).then(() => sw.skipWaiting())
  );
});

// 2. Activación y Limpieza de Cachés Previos
sw.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            console.log('[SW] Eliminando caché antiguo:', name);
            return caches.delete(name);
          }
          // Limpiar restos antiguos y refrescar offline.html para evitar bloqueos tras actualizar
          return caches.open(name).then((c) => Promise.all([
            c.delete('/'),
            c.delete('/index.html'),
            c.delete('/offline.html'),
            c.delete('/assets/FontManifest.json'),
          ]).then(() => c.add(new Request('/offline.html', { cache: 'reload' })).catch(() => {})));
        })
      );
    }).then(() => sw.clients.claim())
  );
});

// 3. Estrategia de Enrutamiento y Fetch Resiliente (Allowlist estricta de estáticos)
sw.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Nunca interceptar ni cachear APIs, documentos con token, autenticación o motor WebSocket/Flet
  if (debeOmitirCache(req, url)) {
    return;
  }

  // A. Peticiones de Navegación HTML (network-first con respaldo únicamente a páginas offline/scanner)
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(async () => {
        if (url.pathname === '/scanner.html') {
          const cachedScanner = await caches.match('/scanner.html');
          if (cachedScanner) {
            return cachedScanner;
          }
        }
        const offlinePage = await caches.match('/offline.html');
        return offlinePage || new Response('Sin conexión a la red local.', {
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
      })
    );
    return;
  }

  // B. Solo cachear recursos incluidos en la allowlist explícita de activos estáticos públicos
  if (!esRecursoEstaticoPermitido(url.pathname)) {
    return;
  }

  event.respondWith(
    caches.match(req).then((cachedResponse) => {
      if (cachedResponse) {
        fetch(req).then((networkResponse) => {
          if (respuestaEsCacheable(networkResponse)) {
            caches.open(CACHE_NAME).then((cache) => cache.put(req, networkResponse));
          }
        }).catch(() => {});
        return cachedResponse;
      }

      return fetch(req).then((networkResponse) => {
        if (!respuestaEsCacheable(networkResponse)) {
          return networkResponse;
        }
        const responseToCache = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(req, responseToCache);
        });
        return networkResponse;
      }).catch(async () => {
        if (req.headers.get('accept')?.includes('text/html')) {
          const offlinePage = await caches.match('/offline.html');
          if (offlinePage) {
            return offlinePage;
          }
        }
        return new Response('', { status: 408, statusText: 'Offline' });
      });
    })
  );
});
