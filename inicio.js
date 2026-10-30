// Portada: la carrera primero (en directo, la próxima o la última) con sus cifras y su trazado, al lado los accesos
// con lo que hay en cada sección, y debajo más carreras y las últimas rutas. Los textos se pintan siempre con textContent.
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

function fila(href, nombre, sub, puntos, c1, c2, i) {
  const a = document.createElement('a'); a.className = 'fila entra'; a.href = href; a.style.setProperty('--i', Math.min(i, 12));
  const n = document.createElement('div'); n.className = 'nombre'; n.textContent = nombre;
  if (sub) { const s = document.createElement('small'); s.textContent = sub; n.append(s); }
  const t = document.createElement('div'); t.className = 'traza'; t.append(traza(puntos));
  a.append(n, t, cifra(...c1), cifra(...c2));
  return a;
}

const cuenta = (n, uno, varios) => n + ' ' + (n === 1 ? uno : varios);

async function json(url) { try { const r = await fetch(url); return r.ok ? await r.json() : null; } catch (e) { return null; } }

// «Entrar»: al dueño lo lleva al panel; al invitado, a su espacio de rutas
fetch('/api/invitado/yo', {credentials: 'same-origin'}).then(r => r.ok ? r.json() : {}).then(d => {
  const a = document.getElementById('nav-admin');
  if (a && d && d.dueno) a.href = '/admin.html';
}).catch(() => {});

(async () => {
  const [datos, pub] = await Promise.all([json('/api/carreras'), json('/api/rutas-publicas')]);
  const lista = ((datos && datos.carreras) || []).slice().sort((a, b) => String(b.fecha || '').localeCompare(String(a.fecha || '')));
  const rutas = (pub && pub.rutas) || [];
  const pill = $('hero-pill'), titulo = $('hero-titulo'), linea = $('hero-linea'), boton = $('hero-boton');
  let estado = '', nombre = 'Sígueme CC', partes = [], cifras = [], puntos = null, texto = '', href = '/', ultima = null;
  if (datos && datos.en_marcha) {
    const c = (await json('/carrera.json')) || {};
    estado = 'En directo'; nombre = c.nombre || 'Carrera en directo';
    partes = [c.lugar];
    cifras = [[c.distancia_km ? km(c.distancia_km) : '', 'KM']];
    texto = 'Ver en directo ▶';
    pill.classList.add('vivo');
  } else if (datos && datos.proxima) {
    const p = datos.proxima;
    estado = 'Próxima carrera'; nombre = p.nombre || 'Próxima carrera';
    partes = [fecha(p.fecha), p.lugar];
    cifras = [[p.distancia_km ? km(p.distancia_km) : '', 'KM'], [p.desnivel_m ? miles(p.desnivel_m) : '', 'M D+'], [p.hora_salida || '', 'SALIDA']];
    puntos = p.traza;
    texto = 'Ver la carrera ▶';
  } else if (lista.length) {
    ultima = lista[0];
    estado = 'Última carrera'; nombre = ultima.nombre || ultima.slug;
    partes = [fecha(ultima.fecha), ultima.lugar];
    cifras = [[ultima.distancia_km ? km(ultima.distancia_km) : '', 'KM'], [ultima.desnivel_m ? miles(ultima.desnivel_m) : '', 'M D+'], [tiempo(ultima.tiempo_s), 'TIEMPO']];
    puntos = ultima.traza;
    texto = 'Ver el resultado ▶'; href = '/' + ultima.slug + '/';
  } else {
    partes = ['Todavía no hay carreras'];
  }
  pill.textContent = estado; pill.hidden = !estado;
  titulo.textContent = nombre;
  linea.textContent = partes.filter(Boolean).join(' · ');
  cifras = cifras.filter(c => c[0]);
  if (cifras.length) { $('hero-cifras').append(...cifras.map(c => cifra(...c))); $('hero-cifras').hidden = false; }
  if (puntos && puntos.length > 1) { $('hero-traza').append(traza(puntos)); $('hero-traza').hidden = false; }
  if (texto) { boton.textContent = texto; boton.href = href; boton.hidden = false; }
  $('n-carreras').textContent = cuenta(lista.length, 'carrera', 'carreras');
  $('n-rutas').textContent = cuenta(rutas.length, 'ruta', 'rutas');

  const resto = lista.filter(c => c !== ultima);
  if (resto.length) {
    $('carreras-sec').hidden = false;
    resto.slice(0, 3).forEach((c, i) => {
      const f = fila('/' + c.slug + '/', c.nombre || c.slug, [fecha(c.fecha), c.lugar].filter(Boolean).join(' · '), c.traza,
        [c.distancia_km ? km(c.distancia_km) : '–', 'KM'], [tiempo(c.tiempo_s) || '–', tiempo(c.tiempo_s) ? 'TIEMPO' : ''], i);
      f.classList.add('carrera'); f.children[2].classList.add('km'); f.children[3].classList.add('t');
      $('carreras').append(f);
    });
  }
  if (rutas.length) {
    $('rutas-sec').hidden = false;
    rutas.slice(0, 3).forEach((r, i) => $('rutas').append(fila('/r/' + r.id, r.nombre, r.autor ? 'de ' + r.autor : '', r.traza,
      [km(r.distancia_km), 'KM'], [miles(r.desnivel_m || 0), 'D+'], i)));
  }
})();
