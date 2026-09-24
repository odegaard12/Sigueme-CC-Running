// Service worker de la carrera.
//
// Regla de oro tras pelearse con esto: el CÓDIGO (html/js/css) nunca se
// precachea ni se sirve desde caché estando en línea. Un service worker
// cache-first servía app.js viejo después de desplegar, y eso el día de la
// carrera significa enseñar una web rota sin forma de arreglarla.
// Solo se cachean los datos pesados que no cambian: ruta, perfil e imágenes.
const VERSION = 'v4';
const CACHE = 'sigueme-' + VERSION;

const DATOS = ['./route.geojson', './elevation.json', './aid_stations.json',
               './rider.png', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(DATOS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // datos en vivo, API y todo lo externo (teselas, librerías): a la red
  if (url.origin !== self.location.origin) return;
  if (url.pathname.endsWith('/live.json') || url.pathname.startsWith('/api/')) return;

  const esDato = DATOS.some(d => url.pathname.endsWith(d.slice(1)));

  if (esDato) {
    e.respondWith(
      caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
        const copia = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copia));
        return res;
      }))
    );
    return;
  }

  // código: siempre red; el caché solo salva si no hay cobertura
  e.respondWith(
    fetch(e.request).then(res => {
      const copia = res.clone();
      caches.open(CACHE).then(c => c.put(e.request, copia));
      return res;
    }).catch(() => caches.match(e.request))
  );
});
