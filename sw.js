// Service worker de la web en directo. Con la cobertura cortada (un túnel, el monte, el avión) la página se abre
// igual: el esqueleto, la ruta, el perfil y las teselas del mapa que ya se vieron salen de la caché, y app.js pinta el
// último estado guardado en el móvil. NUNCA se toca /live.json ni /api/: lo vivo siempre va a la red.
const V = 'sigueme-v1';
const DATOS = V + '-datos', TESELAS = V + '-teselas';
const MAX_TESELAS = 700;          // unas decenas de MB como mucho
const SIN_RED = '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<title>Sin conexión</title><body style="margin:0;background:#0c0f0e;color:#f4f7e6;font:18px system-ui;padding:32px">' +
  '<h1 style="font:400 3rem/1 Impact,sans-serif;color:#d9f24a;text-transform:uppercase">Sin conexión</h1>' +
  '<p>No hay cobertura y esta página aún no estaba guardada en tu móvil. Vuelve a intentarlo cuando tengas red.</p></body></html>';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => !k.startsWith(V)).map(k => caches.delete(k)))).then(() => self.clients.claim())));

const guardar = (c, k, resp) => c.put(k, resp).catch(err => console.log('no se guardó', k.url || k, err.message));
const conTope = (p, ms) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error('tiempo')), ms))]);
const sinConsulta = u => new Request(u.origin + u.pathname);       // los .json llevan ?_=hora: una sola copia por fichero

// la página en directo: red primero (5 s); si no, la última guardada. Solo se guarda si de verdad es la página en directo
async function pagina(r) {
  const c = await caches.open(DATOS), clave = new Request('/__directo');
  const red = fetch(r);
  try {
    const resp = await conTope(red, 5000);
    if (!resp.ok) {                    // el túnel o la Pi caídos contestan rápido con un 5xx: mejor la última copia
      const g = await c.match(clave);
      return g || resp;
    }
    if (resp.type === 'basic' && !resp.redirected) {
      const copia = resp.clone();
      if ((await resp.clone().text()).includes('cd-cab')) guardar(c, clave, copia);
    }
    return resp;
  } catch (err) {
    const g = await c.match(clave);
    if (g) return g;
    return red.catch(() => new Response(SIN_RED, { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }));
  }
}

// datos de la carrera (ruta, perfil, avituallamientos…): red primero (4 s) y, si no, la copia
async function datos(r, u) {
  const c = await caches.open(DATOS), clave = sinConsulta(u);
  try {
    const resp = await conTope(fetch(r), 4000);
    if (!resp.ok) {                    // un 5xx no debe tapar la copia guardada
      const g = await c.match(clave);
      return g || resp;
    }
    if (resp.type === 'basic') guardar(c, clave, resp.clone());
    return resp;
  } catch (err) {
    const g = await c.match(clave);
    if (g) return g;
    throw err;
  }
}

// ficheros con versión (app.js?v=84), la librería del mapa, las fuentes y las imágenes: de la caché y se renuevan detrás
async function viejoYNuevo(r) {
  const c = await caches.open(DATOS), g = await c.match(r);
  const red = fetch(r).then(resp => { if (resp.ok && resp.type === 'basic') guardar(c, r, resp.clone()); return resp; });
  if (g) { red.catch(() => {}); return g; }
  return red;
}

// teselas del mapa (Esri, relieve de AWS): las ya vistas salen sin red
let puestas = 0;
async function tesela(r) {
  const c = await caches.open(TESELAS), g = await c.match(r);
  if (g) return g;
  const resp = await fetch(r);
  if (resp.ok || resp.type === 'opaque') {
    guardar(c, r, resp.clone());
    if (++puestas % 40 === 0) c.keys().then(ks => ks.slice(0, Math.max(0, ks.length - MAX_TESELAS)).forEach(k => c.delete(k)));
  }
  return resp;
}

self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  const u = new URL(r.url), p = u.pathname;
  if (u.origin !== location.origin) {
    if (/^(server\.arcgisonline\.com|s3\.amazonaws\.com)$/.test(u.hostname)) e.respondWith(tesela(r));
    return;
  }
  if (p.startsWith('/api/') || p === '/live.json' || p.startsWith('/admin') || p === '/sw.js') return;
  if (r.mode === 'navigate') {
    if (p === '/' || p === '/index.html') e.respondWith(pagina(r));
    return;
  }
  if (/\.(json|geojson)$/.test(p)) e.respondWith(datos(r, u));
  else if (u.search.startsWith('?v=') || p.startsWith('/lib/') || p.startsWith('/fonts/') || /\.(png|jpg|jpeg|svg|woff2)$/.test(p)) e.respondWith(viejoYNuevo(r));
});
