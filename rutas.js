// Rutas y relojes: las rutas publicadas. Los textos se pintan siempre con textContent.
'use strict';
const $ = id => document.getElementById(id);
const km = v => String(Math.round(v * 10) / 10).replace('.', ',');
const miles = v => String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const fecha = iso => { const [a, m, d] = String(iso || '').split('-'); return a && m && d ? Number(d) + ' ' + MESES[Number(m) - 1] + ' ' + a : ''; };
const tiempo = s => { if (!s) return ''; const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return h + 'h ' + String(m).padStart(2, '0') + 'm'; };
const ns = 'http://www.w3.org/2000/svg';

function traza(puntos) {
  const svg = document.createElementNS(ns, 'svg'); svg.setAttribute('viewBox', '0 0 100 70'); svg.setAttribute('aria-hidden', 'true');
  if (!puntos || puntos.length < 2) return svg;
  const k = Math.cos(puntos[0][1] * Math.PI / 180);
  const xs = puntos.map(p => p[0] * k), ys = puntos.map(p => -p[1]);
  const x0 = Math.min(...xs), y0 = Math.min(...ys), lado = Math.max(Math.max(...xs) - x0, Math.max(...ys) - y0) || 1, esc = 62 / lado;
  const ox = (100 - (Math.max(...xs) - x0) * esc) / 2, oy = (70 - (Math.max(...ys) - y0) * esc) / 2;
  const path = document.createElementNS(ns, 'path');
  path.setAttribute('d', 'M' + puntos.map((p, i) => ((xs[i] - x0) * esc + ox).toFixed(1) + ',' + ((ys[i] - y0) * esc + oy).toFixed(1)).join(' L'));
  path.setAttribute('fill', 'none'); path.setAttribute('stroke', 'currentColor'); path.setAttribute('stroke-width', '3');
  path.setAttribute('stroke-linejoin', 'round'); path.setAttribute('stroke-linecap', 'round');
  svg.append(path);
  return svg;
}

function cifra(valor, unidad) {
  const d = document.createElement('div'); d.className = 'cifra';
  const b = document.createElement('b'); b.textContent = valor; const s = document.createElement('span'); s.textContent = unidad;
  d.append(b, s); return d;
}

function perfil(p) {
  const svg = document.createElementNS(ns, 'svg'); svg.setAttribute('viewBox', '0 0 100 24'); svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('class', 'mini-perfil'); svg.setAttribute('aria-hidden', 'true');
  if (!p || p.length < 2) return svg;
  const d0 = p[0][0], d1 = p[p.length - 1][0], es = p.map(x => x[1]), e0 = Math.min(...es), e1 = Math.max(...es);
  const pts = p.map(x => ((x[0] - d0) / ((d1 - d0) || 1) * 100).toFixed(1) + ',' + (24 - (x[1] - e0) / ((e1 - e0) || 1) * 22).toFixed(1));
  const pol = document.createElementNS(ns, 'polygon'); pol.setAttribute('points', '0,24 ' + pts.join(' ') + ' 100,24'); pol.setAttribute('fill', 'currentColor');
  svg.append(pol);
  return svg;
}

// una ficha grande por ruta, como la tarjeta de la portada
function ficha(r, i) {
  const href = '/r/' + r.id, el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt) e.textContent = txt; return e; };
  const art = el('article', 'hero-tarj ficha-grande entra'); art.style.setProperty('--i', Math.min(i, 12));
  const txt = el('div', 'hero-txt'), h = el('h2', 'hero-titulo'), a = el('a', '', r.nombre); a.href = href; h.append(a);
  const cif = el('div', 'hero-cifras');
  cif.append(cifra(km(r.distancia_km), 'KM'), cifra(miles(r.desnivel_m || 0), 'D+'));
  if (r.avituallamientos) cif.append(cifra(String(r.avituallamientos), r.avituallamientos === 1 ? 'AVITUALLAMIENTO' : 'AVITUALLAMIENTOS'));
  const acc = el('div', 'acciones'), ver = el('a', 'boton', 'Ver la ruta ▶'), gpx = el('a', 'boton claro', 'GPX para el reloj');
  ver.href = href; gpx.href = '/api/ruta-publica/reloj.gpx?id=' + encodeURIComponent(r.id); gpx.setAttribute('download', '');
  acc.append(ver, gpx);
  txt.append(el('span', 'pill-hero', r.autor ? 'Ruta de ' + r.autor : 'Ruta'), h, cif, perfil(r.perfil), acc);
  const t = el('a', 'hero-traza'); t.href = href; t.tabIndex = -1; t.setAttribute('aria-hidden', 'true'); t.append(traza(r.traza));
  art.append(txt, t);
  return art;
}

async function json(url) { try { const r = await fetch(url); return r.ok ? await r.json() : null; } catch (e) { return null; } }

// «Entrar»: al dueño lo lleva al panel; al invitado, a su espacio de rutas
fetch('/api/invitado/yo', {credentials: 'same-origin'}).then(r => r.ok ? r.json() : {}).then(d => {
  const a = document.getElementById('nav-admin');
  if (a && d && d.dueno) a.href = '/admin.html';
}).catch(() => {});

(async () => {
  const rutas = await json('/api/rutas-publicas');
  const rs = (rutas && rutas.rutas) || [];
  const lista = $('rutas');
  rs.forEach((r, i) => lista.append(ficha(r, i)));
  $('sin-rutas').hidden = rs.length > 0;
  if (rutas === null) {
    $('sin-rutas').hidden = false;
    $('sin-rutas').textContent = 'No se han podido cargar las rutas. Comprueba la conexión y recarga la página.';
  }
})();
