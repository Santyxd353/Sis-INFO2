/* Public resources only. Bump VERSION whenever this worker or offline shell changes. */
const VERSION = 'v1-20261117';
const CACHE_PREFIX = 'edugestion-hu29-static-';
const CACHE_NAME = `${CACHE_PREFIX}${VERSION}`;
const SHELL = ['/offline.html', '/manifest.webmanifest', '/pwa/icon-192.png', '/pwa/icon-512.png', '/pwa/icon-maskable-512.png'];

function publicStaticPath(path) {
  return SHELL.includes(path) || path === '/favicon.svg' || path === '/icons.svg' ||
    /^\/assets\/[A-Za-z0-9_.-]+-[A-Za-z0-9_-]{6,}\.(?:js|css|woff2?|png|svg|webp|jpe?g|gif|ico)$/.test(path);
}

function safeResponse(response, path) {
  if (!response.ok || response.status !== 200 || response.redirected ||
      !['basic', 'default'].includes(response.type) ||
      /(?:no-store|private)/i.test(response.headers.get('Cache-Control') || '') ||
      response.headers.has('Set-Cookie') || response.headers.get('Vary')?.includes('*')) return false;
  const type = (response.headers.get('Content-Type') || '').split(';')[0].trim();
  if (path.endsWith('.js')) return ['text/javascript', 'application/javascript'].includes(type);
  if (path.endsWith('.css')) return type === 'text/css';
  if (/\.woff2?$/.test(path)) return /^font\//.test(type);
  if (/\.(png|svg|webp|jpe?g|gif|ico)$/.test(path)) return /^image\//.test(type);
  if (path.endsWith('.webmanifest')) return ['application/manifest+json', 'application/json'].includes(type);
  return path === '/offline.html' && type === 'text/html';
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    for (const path of SHELL) {
      const response = await fetch(new Request(new URL(path, self.location.origin), { credentials: 'omit', cache: 'no-store' }));
      if (!safeResponse(response, path)) throw new Error('El shell público no está disponible');
      await cache.put(path, response);
    }
    // Updates wait for the user's explicit reload; do not replace an active session mid-task.
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  // Never accept lifecycle commands from another origin or persist message payloads.
  if (!event.source?.url || new URL(event.source.url).origin !== self.location.origin) return;
  if (event.data?.type === 'SKIP_WAITING') event.waitUntil(self.skipWaiting());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Strict allowlist: all other traffic, including API, auth, PDFs and query strings,
  // is network-only with HTTP-cache bypass and no offline HTML fallback.
  const excluded = request.method !== 'GET' || url.search ||
    request.headers.has('Authorization') || request.headers.has('Range') ||
    request.headers.has('Cookie') || request.cache === 'no-store';
  if (excluded || (!publicStaticPath(url.pathname) && request.mode !== 'navigate')) {
    event.respondWith(fetch(request, { cache: 'no-store' }));
    return;
  }

  if (publicStaticPath(url.pathname) && request.mode !== 'navigate') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(request);
      if (cached) return cached;
      // Static resources are fetched without cookies, even when the browser is signed in.
      const response = await fetch(new Request(request, { credentials: 'omit', cache: 'no-store' }));
      if (safeResponse(response, url.pathname)) {
        try { await cache.put(request, response.clone()); } catch { /* Storage pressure must not break online use. */ }
      }
      return response;
    })());
    return;
  }

  // Navigation responses are NEVER stored: deployments may render personalized HTML.
  // Only app routes get the generic, public offline shell; private documents never do.
  const appRoute = url.pathname === '/' || url.pathname === '/dashboard' ||
    /^\/dashboard\/[A-Za-z0-9_/-]*$/.test(url.pathname);
  event.respondWith((async () => {
    try { return await fetch(request, { cache: 'no-store' }); }
    catch (error) {
      if (!appRoute) throw error;
      const cache = await caches.open(CACHE_NAME);
      const offline = await cache.match('/offline.html');
      if (offline) return offline;
      throw error;
    }
  })());
});
