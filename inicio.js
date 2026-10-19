// Portada: las rutas publicadas y las carreras. Los textos se pintan siempre con textContent.
'use strict';
const $ = id => document.getElementById(id);
const km = v => String(Math.round(v * 10) / 10).replace('.', ',');
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const fecha = iso => { const [a, m, d] = String(iso || '').split('-'); return a && m && d ? Number(d) + ' ' + MESES[Number(m) - 1] + ' ' + a : ''; };
const tiempo = s => { if (!s) return ''; const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = Math.round(s % 60); return h + ':' + String(m).padStart(2, '0') + ':' + String(x).padStart(2, '0'); };
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

function fila(href, nombre, sub, puntos, c1, c2, i) {
  const a = document.createElement('a'); a.className = 'fila entra'; a.href = href; a.style.setProperty('--i', Math.min(i, 12));
  const n = document.createElement('div'); n.className = 'nombre'; n.textContent = nombre;
  if (sub) { const s = document.createElement('small'); s.textContent = sub; n.append(s); }
  const t = document.createElement('div'); t.className = 'traza'; t.append(traza(puntos));
  a.append(n, t, cifra(...c1), cifra(...c2));
  return a;
}

async function json(url) { try { const r = await fetch(url); return r.ok ? await r.json() : null; } catch (e) { return null; } }

(async () => {
  const [rutas, carreras] = await Promise.all([json('/api/rutas-publicas'), json('/api/carreras')]);
  const lista = $('rutas');
  const rs = (rutas && rutas.rutas) || [];
  rs.forEach((r, i) => lista.append(fila('/r/' + r.id, r.nombre, r.autor ? 'de ' + r.autor : '', r.traza, [km(r.distancia_km), 'KM'], [String(r.desnivel_m), 'D+'], i)));
  $('sin-rutas').hidden = rs.length > 0;
  if (carreras) {
    if (carreras.en_marcha) $('directo').hidden = false;
    const p = carreras.proxima;
    if (p) {
      const a = $('proxima'); a.hidden = false;
      a.textContent = 'Próxima carrera · ' + p.nombre;
      const s = document.createElement('small'); s.textContent = [fecha(p.fecha), p.hora_salida, p.lugar, p.distancia_km ? km(p.distancia_km) + ' km' : ''].filter(Boolean).join(' · ');
      a.append(s);
    }
    const hechas = carreras.carreras || [];
    if (hechas.length) {
      $('carreras-sec').hidden = false;
      hechas.forEach((c, i) => $('carreras').append(fila('/' + c.slug + '/', c.nombre || c.slug, [fecha(c.fecha), c.lugar].filter(Boolean).join(' · '), null,
        [c.distancia_km ? km(c.distancia_km) : '–', 'KM'], [tiempo(c.tiempo_s) || '–', tiempo(c.tiempo_s) ? 'TIEMPO' : ''], i)));
    }
  }
})();

// «Admin»: al dueño lo lleva al panel; al invitado, a su espacio de rutas
fetch('/api/invitado/yo', {credentials: 'same-origin'}).then(r => r.ok ? r.json() : {}).then(d => {
  const a = document.getElementById('nav-admin');
  if (a && d && d.dueno) a.href = '/admin.html';
}).catch(() => {});
