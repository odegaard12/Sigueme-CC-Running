// Página de una ruta publicada: mapa, perfil, avituallamientos, subidas y GPX para el reloj.
'use strict';
const $ = id => document.getElementById(id);
const km = v => String(Math.round(v * 10) / 10).replace('.', ',');
const miles = v => String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const ns = 'http://www.w3.org/2000/svg';
const id = location.pathname.split('/').filter(Boolean).pop();
const rad = x => x * Math.PI / 180;

function distancia(a, b) {
  const h = Math.sin(rad(b[1] - a[1]) / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(rad(b[0] - a[0]) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}
// el punto de la ruta a tantos km (la ruta del mapa va simplificada: se reparte hasta el total real)
function acumulados(coords, total) {
  const a = [0]; for (let i = 1; i < coords.length; i++) a.push(a[i - 1] + distancia(coords[i - 1], coords[i]));
  const esc = a[a.length - 1] ? total / a[a.length - 1] : 1; return a.map(x => x * esc);
}
function puntoEn(coords, acum, k) {
  let i = acum.findIndex(x => x >= k); if (i < 1) i = k <= 0 ? 1 : coords.length - 1;
  const t = acum[i] > acum[i - 1] ? Math.min(1, Math.max(0, (k - acum[i - 1]) / (acum[i] - acum[i - 1]))) : 0;
  return [coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * t, coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * t];
}

function cifra(valor, unidad) {
  const c = document.createElement('div'); c.className = 'c';
  const b = document.createElement('b'); b.textContent = valor; const s = document.createElement('span'); s.textContent = unidad;
  c.append(b, s); return c;
}
function filaSimple(nombre, sub, c1, c2, i) {
  const f = document.createElement('div'); f.className = 'fila simple entra'; f.style.setProperty('--i', Math.min(i, 12));
  const n = document.createElement('div'); n.className = 'nombre'; n.textContent = nombre;
  if (sub) { const s = document.createElement('small'); s.textContent = sub; n.append(s); }
  const mk = ([v, u]) => { const d = document.createElement('div'); d.className = 'cifra'; const b = document.createElement('b'); b.textContent = v;
    const s = document.createElement('span'); s.textContent = u; d.append(b, s); return d; };
  f.append(n, mk(c1), mk(c2)); return f;
}
function svgEl(tag, attrs) { const e = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; }

function dibujarPerfil(r) {
  const svg = $('perfil'); svg.textContent = '';
  if (!r.perfil || r.perfil.length < 2) { svg.hidden = true; return; }
  const W = Math.max(320, Math.round(svg.getBoundingClientRect().width || 1000)), H = W < 600 ? 200 : 240, L = 48, R = 14, T = 16, B = 28, total = r.perfil[r.perfil.length - 1][0] || r.distancia_km;
  const eles = r.perfil.map(p => p[1]), e0 = Math.floor(Math.min(...eles) / 10) * 10, e1 = Math.ceil(Math.max(...eles) / 10) * 10 || e0 + 10;
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  const X = d => L + (W - L - R) * d / total, Y = e => H - B - (H - B - T) * (e - e0) / ((e1 - e0) || 1);
  for (const s of r.subidas) svg.append(svgEl('rect', { x: X(s.inicio), y: T, width: Math.max(2, X(s.fin) - X(s.inicio)), height: H - B - T, fill: 'rgba(217,242,74,.14)' }));
  const pts = r.perfil.map(p => X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1));
  svg.append(svgEl('polygon', { points: X(0) + ',' + (H - B) + ' ' + pts.join(' ') + ' ' + X(total) + ',' + (H - B), fill: '#d9f24a' }));
  // las etiquetas que se pisarían no se ponen (en el mapa y en la lista están todas)
  let ultimo = -Infinity;
  for (const a of r.avituallamientos) {
    const x = X(a.km);
    svg.append(svgEl('line', { x1: x, x2: x, y1: T, y2: H - B, stroke: '#0c0f0e', 'stroke-width': 1.5, opacity: 0.8 }));
    if (x - ultimo < 34 || x > W - R - 48) continue;
    const t = svgEl('text', { x, y: H - 10, 'text-anchor': 'middle' }); t.textContent = km(a.km); svg.append(t); ultimo = x;
  }
  for (const [e, y] of [[e1, T + 8], [e0, H - B - 2]]) { const t = svgEl('text', { x: 4, y }); t.textContent = e + ' m'; svg.append(t); }
  const t = svgEl('text', { x: W - R, y: H - 10, 'text-anchor': 'end' }); t.textContent = km(total) + ' km'; svg.append(t);
}

function dibujarMapa(r) {
  const cont = $('mapa');
  const arrancarMapa = () => {
    if (!window.maplibregl) { cont.hidden = true; return; }
    const acum = acumulados(r.coords, r.distancia_km);
    const map = new maplibregl.Map({
      container: cont, interactive: true, attributionControl: { compact: true }, cooperativeGestures: true,
      style: { version: 8, sources: { sat: { type: 'raster', tileSize: 256, maxzoom: 18, attribution: 'Esri, Maxar, Earthstar Geographics',
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'] } },
        layers: [{ id: 'sat', type: 'raster', source: 'sat' }] },
      bounds: [[r.bbox[0], r.bbox[1]], [r.bbox[2], r.bbox[3]]], fitBoundsOptions: { padding: 40 }
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      map.addSource('ruta', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: r.coords } } });
      map.addLayer({ id: 'borde', type: 'line', source: 'ruta', paint: { 'line-color': '#0c0f0e', 'line-width': 8 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
      map.addLayer({ id: 'linea', type: 'line', source: 'ruta', paint: { 'line-color': '#d9f24a', 'line-width': 4 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
      const marcas = [];
      for (const a of r.avituallamientos) {
        const el = document.createElement('button'); el.type = 'button'; el.className = 'marca-avit'; el.textContent = km(a.km); el.setAttribute('aria-label', a.name + ', km ' + km(a.km));
        const pop = new maplibregl.Popup({ offset: 18, closeButton: false }).setText(a.name + ' · km ' + km(a.km));
        marcas.push(new maplibregl.Marker({ element: el }).setLngLat(puntoEn(r.coords, acum, a.km)).setPopup(pop).addTo(map));
      }
      // con poco zoom, los avituallamientos muy juntos se pisan: sale el primero y los demás al acercar
      const despejar = () => {
        const vistos = [];
        for (const m of marcas) {
          const p = map.project(m.getLngLat()), tapa = vistos.some(q => Math.abs(q.x - p.x) < 46 && Math.abs(q.y - p.y) < 30);
          m.getElement().style.visibility = tapa ? 'hidden' : ''; if (!tapa) vistos.push(p);
        }
      };
      despejar(); map.on('zoomend', despejar);
    });
  };
  const arrancar = () => { try { arrancarMapa(); } catch (e) { cont.hidden = true; } };
  if (window.maplibregl) { arrancar(); return; }
  const s = document.createElement('script'); s.src = '/lib/maplibre-gl-4.7.1.js'; s.async = true; s.onload = arrancar; s.onerror = () => { cont.hidden = true; };
  document.head.append(s);
}

function pintar(r) {
  document.title = r.nombre + ' · Sígueme CC';
  const t = $('titulo'); t.textContent = r.nombre; if (r.nombre.length > 26) t.classList.add('largo');
  if (r.autor) { const a = $('autor'); a.textContent = 'Ruta de ' + r.autor; a.hidden = false; }
  const c = $('cifras'); c.textContent = '';
  c.append(cifra(km(r.distancia_km), 'KM'), cifra(miles(r.desnivel_m), 'D+'));
  if (r.avituallamientos.length) c.append(cifra(String(r.avituallamientos.length), r.avituallamientos.length === 1 ? 'AVITUALLAMIENTO' : 'AVITUALLAMIENTOS'));
  if (r.subidas.length) c.append(cifra(String(r.subidas.length), r.subidas.length === 1 ? 'SUBIDA' : 'SUBIDAS'));
  c.hidden = false;
  $('bajar').href = '/api/ruta-publica/reloj.gpx?id=' + id; $('acciones').hidden = false;
  $('compartir').addEventListener('click', async () => {
    const url = location.href;
    try { if (navigator.share) await navigator.share({ title: r.nombre, url }); else { await navigator.clipboard.writeText(url); $('compartir').textContent = 'Enlace copiado'; } } catch (e) { /* cancelado */ }
  });
  $('detalle').hidden = false; dibujarPerfil(r); dibujarMapa(r);
  let espera; addEventListener('resize', () => { clearTimeout(espera); espera = setTimeout(() => dibujarPerfil(r), 200); });
  const av = $('avits'); av.textContent = '';
  r.avituallamientos.forEach((a, i) => av.append(filaSimple(a.name, '', [km(a.km), 'KM'], [km(Math.max(0, r.distancia_km - a.km)), 'A META'], i)));
  $('sec-avit').hidden = !r.avituallamientos.length;
  const su = $('subidas'); su.textContent = '';
  r.subidas.forEach((s, i) => su.append(filaSimple('Sube ' + s.n, 'km ' + km(s.inicio) + ' a ' + km(s.fin) + ' · ' + String(s.pendiente).replace('.', ',') + ' %', ['+' + s.desnivel_m, 'M'], [km(s.largo_km), 'KM'], i)));
  $('sec-subidas').hidden = !r.subidas.length;
  $('como').hidden = false;
}

fetch('/api/ruta-publica?id=' + encodeURIComponent(id)).then(r => r.ok ? r.json() : null).then(r => {
  if (!r) { $('titulo').textContent = 'Ruta no disponible'; $('error').hidden = false; return; }
  pintar(r);
}).catch(() => { $('titulo').textContent = 'Sin conexión'; $('error').hidden = false; });

// «Admin»: al dueño lo lleva al panel; al invitado, a su espacio de rutas
fetch('/api/invitado/yo', {credentials: 'same-origin'}).then(r => r.ok ? r.json() : {}).then(d => {
  const a = document.getElementById('nav-admin');
  if (a && d && d.dueno) a.href = '/admin.html';
}).catch(() => {});
