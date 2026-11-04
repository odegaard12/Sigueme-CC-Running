// Una carrera en directo con varios corredores (/d/<id>): el mapa con cada uno, su km y su tiempo, cada 10 s.
// Con la invitación (#unirse=…) se apunta uno desde su móvil; su identificador se queda en ESTE navegador
// (localStorage) para volver a configurar el móvil. Los textos, siempre con textContent.
'use strict';
const $ = id => document.getElementById(id);
const ID = location.pathname.split('/').filter(Boolean).pop();
const km = v => String(Math.round(v * 10) / 10).replace('.', ',');
const miles = v => String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const fecha = iso => { const [a, m, d] = String(iso || '').split('-'); return a && m && d ? Number(d) + ' ' + MESES[Number(m) - 1] + ' ' + a : ''; };
const tiempo = s => { const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = Math.floor(s % 60); return h + 'h ' + String(m).padStart(2, '0') + 'm ' + String(x).padStart(2, '0') + 's'; };
const SITUACION = { sin_empezar: 'Aún sin salir', en_la_salida: 'En la salida', corriendo: 'Corriendo', en_meta: 'En meta', retirado: 'Retirado' };
const ESTADO = { proxima: 'Próxima', en_directo: 'En directo', terminada: 'Terminada' };
const clave = 'directo.' + ID;
const token = new URLSearchParams(location.hash.slice(1)).get('unirse');
let mapa = null, marcas = {}, datos = null, elegido = null;

function guardado() { try { return localStorage.getItem(clave); } catch (e) { return null; } }
// ritmo medio desde la salida real, en min/km (hace falta 300 m para que valga algo)
function ritmo(g) { if (!(g.tiempo_s > 0 && g.km >= 0.3)) return ''; const sp = Math.round(g.tiempo_s / g.km); return Math.floor(sp / 60) + ':' + String(sp % 60).padStart(2, '0') + ' min/km'; }
function iniciales(n) { return n.split(/\s+/).filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase() || '·'; }

function pintar(d) {
  datos = d;
  if (d.estado === 'terminada') $('sec-unirse').hidden = true;      // una carrera terminada ya no admite a nadie
  const e = $('estado'); e.textContent = ESTADO[d.estado] || ''; e.hidden = false; e.classList.toggle('vivo', d.estado === 'en_directo');
  $('linea').textContent = [fecha(d.fecha) + ' · salida ' + d.hora_salida, d.distancia_km ? km(d.distancia_km) + ' km' : '',
    d.desnivel_m ? '+' + miles(d.desnivel_m) + ' m' : ''].filter(Boolean).join(' · ');
  const lista = $('gente'); lista.textContent = '';
  d.corredores.forEach((g, i) => {
    const f = document.createElement('div'); f.className = 'fila simple';
    const n = document.createElement('div'); n.className = 'nombre'; n.textContent = (g.situacion === 'en_meta' ? (i + 1) + ' · ' : '') + g.nombre;
    const s = document.createElement('small'); s.textContent = [SITUACION[g.situacion] || '', g.situacion === 'retirado' ? '' : ritmo(g)].filter(Boolean).join(' · '); n.append(s);
    const c1 = document.createElement('div'); c1.className = 'cifra'; const b1 = document.createElement('b'); b1.textContent = km(g.km); const u1 = document.createElement('span'); u1.textContent = 'KM'; c1.append(b1, u1);
    const c2 = document.createElement('div'); c2.className = 'cifra'; const b2 = document.createElement('b'); b2.textContent = g.tiempo_s != null ? tiempo(g.tiempo_s) : '–'; const u2 = document.createElement('span'); u2.textContent = g.situacion === 'en_meta' ? 'TIEMPO' : 'EN CARRERA'; c2.append(b2, u2);
    f.append(n, c1, c2); lista.append(f);
    f.tabIndex = 0; f.setAttribute('role', 'button'); f.setAttribute('aria-pressed', String(elegido === g.cid));
    f.classList.toggle('sel', elegido === g.cid);
    const elige = () => elegir(g.cid);
    f.addEventListener('click', elige);
    f.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); elige(); } });
  });
  // la tira de caras de arriba: la foto de cada uno (o su inicial), su nombre y su tiempo; al tocar, el mapa va a él
  const tira = $('tira'); tira.textContent = '';
  $('tarjeta-corr').hidden = !d.corredores.length;
  $('tira-tit').textContent = d.corredores.length > 1 ? 'Corredores' : 'Corredor';       // ficha de corredor (uno) o de corredores (varios)
  tira.classList.toggle('solo', d.corredores.length === 1);
  d.corredores.forEach(g => {
    const b = document.createElement('button'); b.type = 'button';
    b.className = 'cara' + (elegido === g.cid ? ' sel' : '') + (g.situacion === 'retirado' ? ' retirado' : '');
    b.setAttribute('aria-pressed', String(elegido === g.cid)); b.setAttribute('aria-label', g.nombre);
    const av = document.createElement('span'); av.className = 'av';
    if (g.foto) { const im = document.createElement('img'); im.alt = ''; im.src = '/d/' + ID + '/foto/' + g.cid + '.png?v=' + g.foto; av.append(im); } else av.textContent = iniciales(g.nombre);
    const n = document.createElement('b'); n.textContent = g.nombre;
    const s = document.createElement('small');
    s.textContent = d.corredores.length === 1 ? [SITUACION[g.situacion] || '', g.km ? km(g.km) + ' km' : '', g.tiempo_s != null ? tiempo(g.tiempo_s) : '', ritmo(g)].filter(Boolean).join(' · ')
      : g.situacion === 'retirado' ? 'Retirado' : (g.tiempo_s != null ? tiempo(g.tiempo_s) : (SITUACION[g.situacion] || ''));
    b.append(av, n, s); b.addEventListener('click', () => elegir(g.cid)); tira.append(b);
  });
  $('aviso-posicion').hidden = d.corredores.some(g => g.lat != null);
  if (mapa && mapa.loaded()) pintarMarcas();
}

function elegir(cid) { elegido = elegido === cid ? null : cid; pintar(datos); if (elegido) verEnMapa(cid); }

function verEnMapa(cid) {
  const m = marcas[cid];
  if (!mapa || !m) { $('aviso-posicion').hidden = false; return; }       // aún sin posición: no hay dónde ir
  mapa.flyTo({ center: m.getLngLat(), zoom: Math.max(mapa.getZoom(), 14.5) });
  Object.keys(marcas).forEach(k => { if (k !== cid && marcas[k].getPopup().isOpen()) marcas[k].togglePopup(); });   // solo el del elegido
  const p = m.getPopup(); if (p && !p.isOpen()) m.togglePopup();
  document.getElementById('mapa').scrollIntoView({ block: 'center', behavior: 'smooth' });
}

function pintarMarcas() {
  for (const g of datos.corredores) {
    if (g.lat == null) { if (marcas[g.cid]) { marcas[g.cid].remove(); delete marcas[g.cid]; } continue; }
    if (!marcas[g.cid]) {
      const el = document.createElement('div'); el.className = 'corredor-dir' + (g.situacion === 'en_meta' ? ' meta' : ''); el.textContent = iniciales(g.nombre); el.title = g.nombre;
      marcas[g.cid] = new maplibregl.Marker({ element: el }).setLngLat([g.lon, g.lat]).setPopup(new maplibregl.Popup({ offset: 16, closeButton: false }).setText(g.nombre)).addTo(mapa);
    } else marcas[g.cid].setLngLat([g.lon, g.lat]);
    marcas[g.cid].getElement().classList.toggle('elegido', elegido === g.cid);
    if (g.foto) { const e2 = marcas[g.cid].getElement(); e2.classList.add('con-foto'); e2.style.backgroundImage = 'url(/d/' + ID + '/foto/' + g.cid + '.png?v=' + g.foto + ')'; e2.textContent = ''; }
  }
}

function arrancarMapa(d) {
  const lons = d.ruta.map(p => p[0]), lats = d.ruta.map(p => p[1]);
  mapa = new maplibregl.Map({ container: 'mapa', attributionControl: { compact: true }, cooperativeGestures: true, maxPitch: 62,
    style: { version: 8, sources: { sat: { type: 'raster', tileSize: 256, maxzoom: 18, attribution: 'Esri, Maxar, Earthstar Geographics',
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'] } },
      layers: [{ id: 'sat', type: 'raster', source: 'sat' }] },
    bounds: [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], fitBoundsOptions: { padding: 40 } });
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  // «Ver en 3D»: el mismo satélite sobre el relieve real (AWS Terrain Tiles); «Ver en 2D» lo deja plano otra vez
  const b3 = document.createElement('button'); b3.type = 'button'; b3.className = 'ver3d'; b3.textContent = 'Ver en 3D'; b3.setAttribute('aria-pressed', 'false');
  let en3d = false;
  b3.addEventListener('click', () => {
    en3d = !en3d;
    if (en3d) {
      if (!mapa.getSource('terreno')) mapa.addSource('terreno', { type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], tileSize: 256, encoding: 'terrarium', maxzoom: 14 });
      mapa.setTerrain({ source: 'terreno', exaggeration: 1.4 }); mapa.easeTo({ pitch: 55, bearing: -20, duration: 900 });
    } else { mapa.setTerrain(null); mapa.easeTo({ pitch: 0, bearing: 0, duration: 700 }); }
    b3.textContent = en3d ? 'Ver en 2D' : 'Ver en 3D'; b3.setAttribute('aria-pressed', String(en3d));
  });
  $('mapa').append(b3);
  mapa.on('load', () => {
    mapa.addSource('ruta', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: d.ruta } } });
    mapa.addLayer({ id: 'borde', type: 'line', source: 'ruta', paint: { 'line-color': '#0c0f0e', 'line-width': 8 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
    mapa.addLayer({ id: 'linea', type: 'line', source: 'ruta', paint: { 'line-color': '#d9f24a', 'line-width': 4 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
    pintarMarcas();
  });
  // Safari: si el mapa termina de pintarse fuera de la pantalla, al bajar hasta él sale en negro (lo del 1/11)
  if ('IntersectionObserver' in window) new IntersectionObserver(es => { if (es.some(x => x.isIntersecting)) mapa.triggerRepaint(); }).observe($('mapa'));
}

async function cargar() {
  try {
    const r = await fetch('/api/directo?id=' + encodeURIComponent(ID), { cache: 'no-store' });
    if (!r.ok) { $('linea').textContent = 'Esta carrera ya no existe.'; return; }
    const d = await r.json();
    pintar(d);
    if (!mapa && d.ruta.length > 1) {
      if (window.maplibregl) arrancarMapa(d);
      else { const s = document.createElement('script'); s.src = '/lib/maplibre-gl-4.7.1.js'; s.onload = () => arrancarMapa(d); s.onerror = () => { $('mapa').hidden = true; }; document.head.append(s); }
    }
    setTimeout(cargar, d.estado === 'en_directo' ? 10000 : 30000);
  } catch (e) { setTimeout(cargar, 20000); }
}

function enseñarMovil(ident) {
  $('sec-movil').hidden = false; window.pintarMovil($('movil'), ident);
  if (window.fotoCorredor) window.fotoCorredor($('foto-mia'), ident, () => cargar());
  let retirado = false;
  $('retirarme').onclick = async () => {
    if (!retirado && !confirm('¿Retirarte de esta carrera? Dejarás de salir en el mapa y tu móvil ya no contará. Podrás volver mientras la carrera no termine.')) return;
    $('retirarme').disabled = true;
    try {
      const r = await fetch(retirado ? '/api/invitado/volver' : '/api/invitado/retirarme', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ident }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.error || 'No se pudo. Prueba otra vez.');
      retirado = !retirado;
      $('retirarme').textContent = retirado ? 'Volver a la carrera' : 'Retirarme de la carrera';
      $('r-msg').textContent = retirado ? 'Te has retirado. Si fue sin querer, pulsa «Volver a la carrera».' : 'Vuelves a estar en la carrera.';
      cargar();
    } catch (e) { $('r-msg').textContent = e.message; }
    $('retirarme').disabled = false;
  };
}

// quien creó la carrera (con la sesión iniciada) también invita desde aquí
fetch('/api/invitado/yo', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : {}).then(y => {
  if (!y || !y.sesion) return null;
  return fetch('/api/invitado/directos', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : null);
}).then(d => {
  const c = d && (d.directos || []).find(x => x.id === ID && x.invitacion); if (!c) return;
  const b = document.createElement('button'); b.type = 'button'; b.className = 'boton'; b.textContent = 'Invitar a quien corra contigo';
  b.addEventListener('click', async () => {
    const url = location.origin + '/d/' + ID + '#unirse=' + c.invitacion;
    try { if (navigator.share) await navigator.share({ title: document.title + ' · apúntate', url }); else { await navigator.clipboard.writeText(url); b.textContent = 'Invitación copiada'; } } catch (e) { /* cancelado */ }
  });
  $('compartir').after(b);
  const p = document.createElement('p'); p.className = 'autor'; p.textContent = '«Compartir»: para que te sigan. «Invitar»: para que corra contigo y salga en el mapa.';
  $('compartir').parentNode.after(p);
}).catch(() => {});

$('compartir').addEventListener('click', async () => {
  const url = location.origin + '/d/' + ID;
  try { if (navigator.share) await navigator.share({ title: document.title, url }); else { await navigator.clipboard.writeText(url); $('compartir').textContent = 'Enlace copiado'; } } catch (e) { /* cancelado */ }
});

if (guardado()) {
  // apuntado con cuenta: los ajustes solo salen con la sesión iniciada; apuntado con el enlace (sin cuenta): salen siempre en su móvil
  let anonimo = false; try { anonimo = !!localStorage.getItem(clave + '.anonimo'); } catch (e) { /* da igual */ }
  if (anonimo) enseñarMovil(guardado());
  else fetch('/api/invitado/yo', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : {}).then(y => {
    if (y && y.sesion) enseñarMovil(guardado());
    else { try { localStorage.removeItem(clave); localStorage.removeItem(clave + '.cuenta'); } catch (e) { /* da igual */ } }
  }).catch(() => {});
}
else if (token) {
  $('sec-unirse').hidden = false;
  $('u-boton').addEventListener('click', async () => {
    const nombre = $('u-nombre').value.trim();
    if (!nombre) { $('u-msg').textContent = 'Pon tu nombre: es el que verán en el mapa.'; $('u-nombre').focus(); return; }
    const b = $('u-boton'); b.disabled = true; $('u-msg').textContent = 'Apuntándote…';
    try {
      const r = await fetch('/api/invitado/unirse', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: ID, token, nombre }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.error || 'No se pudo apuntar. Prueba otra vez.');
      try { localStorage.setItem(clave, d.ident); } catch (e) { /* sin almacenamiento: se enseña igual */ }
      fetch('/api/invitado/yo', { credentials: 'same-origin' }).then(r => r.json()).then(y => { if (!y.sesion) { try { localStorage.setItem(clave + '.anonimo', '1'); } catch (e) { /* da igual */ } } }).catch(() => {});
      history.replaceState(null, '', location.pathname);
      $('sec-unirse').hidden = true; enseñarMovil(d.ident);
    } catch (err) { $('u-msg').textContent = err.message; b.disabled = false; }
  });
}
cargar();
