// Tus rutas para el reloj: el espacio del invitado. Sin librerías; los textos del usuario
// se pintan SIEMPRE con textContent (nunca innerHTML).
'use strict';
const $ = id => document.getElementById(id);
const km = v => String(Math.round(v * 10) / 10).replace('.', ',');
const base = '/api/invitado';
let actual = null;          // la ruta abierta

function aviso(id, texto, tipo) { const m = $(id); m.textContent = texto || ''; m.className = 'msg' + (tipo ? ' ' + tipo : ''); }
function ver(vista) {
  for (const v of ['login', 'lista', 'ruta']) $('vista-' + v).hidden = v !== vista;
  window.scrollTo(0, 0);
}
function fecha(iso) { const [a, m, d] = iso.split('-'); return d + '/' + m + '/' + a; }

async function api(ruta, opciones = {}) {
  const res = await fetch(base + ruta, Object.assign({ credentials: 'same-origin', signal: AbortSignal.timeout ? AbortSignal.timeout(60000) : undefined }, opciones));
  let datos = null;
  try { datos = await res.json(); } catch (e) { /* GPX u otra cosa */ }
  if (res.status === 403 && ruta !== '/login') { ver('login'); aviso('msg-login', 'La sesión ha caducado: entra otra vez.', 'err'); throw new Error('sesion'); }
  if (!res.ok) throw new Error((datos && datos.error) || 'No se pudo completar. Prueba otra vez.');
  return datos;
}
const post = (ruta, cuerpo) => api(ruta, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) });

// ---- entrar / salir
$('form-login').addEventListener('submit', async e => {
  e.preventDefault();
  const b = $('entrar'); b.disabled = true; aviso('msg-login', 'Entrando…');
  try {
    await post('/login', { usuario: $('usuario').value.trim(), codigo: $('codigo').value });
    $('codigo').value = '';
    aviso('msg-login', '');
    await lista();
  } catch (err) { aviso('msg-login', err.message === 'sesion' ? '' : err.message, 'err'); }
  finally { b.disabled = false; }
});
$('salir').addEventListener('click', async () => { try { await post('/logout', {}); } catch (e) { /* da igual */ } ver('login'); aviso('msg-login', 'Hasta la próxima.', 'ok'); });

// ---- lista de rutas
async function lista() {
  const d = await api('/rutas');
  $('cabecera').textContent = 'Hola, ' + d.nombre + '. Tu acceso vale hasta el ' + fecha(d.caduca) + '.';
  const cont = $('lista'); cont.textContent = '';
  $('lista-vacia').hidden = d.rutas.length > 0;
  for (const r of d.rutas) {
    const fila = document.createElement('div'); fila.className = 'ruta-fila';
    const dato = document.createElement('div'); dato.className = 'dato';
    const nombre = document.createElement('b'); nombre.textContent = r.nombre;
    const info = document.createElement('span'); info.className = 'sub';
    info.textContent = km(r.distancia_km) + ' km · +' + r.desnivel_m + ' m' + (r.avituallamientos ? ' · ' + r.avituallamientos + ' avit.' : '');
    dato.append(nombre, info);
    const abrir = document.createElement('button'); abrir.type = 'button'; abrir.className = 'btn chico principal'; abrir.textContent = 'Abrir';
    abrir.addEventListener('click', () => abrirRuta(r.id));
    fila.append(dato, abrir); cont.append(fila);
  }
  ver('lista');
}

$('subir').addEventListener('click', async () => {
  const f = $('gpx').files[0];
  if (!f) { aviso('msg-lista', 'Elige primero un fichero GPX.', 'err'); return; }
  if (f.size > 8000000) { aviso('msg-lista', 'El GPX pesa demasiado (máximo 8 MB).', 'err'); return; }
  const b = $('subir'); b.disabled = true; aviso('msg-lista', 'Subiendo y preparando la ruta…');
  try {
    const nombre = $('nombre-nueva').value.trim() || f.name.replace(/\.gpx$/i, '');
    const r = await api('/gpx?nombre=' + encodeURIComponent(nombre), { method: 'POST', headers: { 'Content-Type': 'application/gpx+xml' }, body: f });
    $('gpx').value = ''; $('nombre-nueva').value = ''; aviso('msg-lista', '');
    pintarRuta(r.ruta);
  } catch (err) { if (err.message !== 'sesion') aviso('msg-lista', err.message, 'err'); }
  finally { b.disabled = false; }
});

// ---- una ruta
async function abrirRuta(id) {
  try { pintarRuta((await api('/ruta?id=' + id)).ruta); } catch (err) { if (err.message !== 'sesion') aviso('msg-lista', err.message, 'err'); }
}

function filaAvit(a) {
  const f = document.createElement('div'); f.className = 'avit';
  const n = document.createElement('input'); n.type = 'text'; n.maxLength = 40; n.placeholder = 'Nombre'; n.value = a.name || ''; n.setAttribute('aria-label', 'Nombre del avituallamiento');
  const k = document.createElement('input'); k.type = 'number'; k.step = '0.1'; k.min = '0'; k.inputMode = 'decimal'; k.placeholder = 'Km'; k.value = a.km ?? ''; k.setAttribute('aria-label', 'Kilómetro');
  const x = document.createElement('button'); x.type = 'button'; x.textContent = '×'; x.setAttribute('aria-label', 'Quitar este avituallamiento');
  x.addEventListener('click', () => f.remove());
  f.append(n, k, x);
  return f;
}

function perfilSvg(perfil, avits) {
  const svg = $('r-perfil'); svg.textContent = '';
  if (!perfil || perfil.length < 2) return;
  const W = 320, H = 110, p = 8, dMax = perfil[perfil.length - 1][0] || 1;
  const eles = perfil.map(q => q[1]), eMin = Math.min(...eles), eMax = Math.max(...eles), rango = (eMax - eMin) || 1;
  const X = d => p + (W - 2 * p) * d / dMax, Y = e => H - p - (H - 2 * p) * (e - eMin) / rango;
  const ns = 'http://www.w3.org/2000/svg';
  const area = document.createElementNS(ns, 'polygon');
  area.setAttribute('points', [[0, eMin]].concat(perfil, [[dMax, eMin]]).map(q => X(q[0]).toFixed(1) + ',' + Y(q[1]).toFixed(1)).join(' '));
  area.setAttribute('fill', 'rgba(127,212,106,.25)'); area.setAttribute('stroke', '#7fd46a'); area.setAttribute('stroke-width', '1.5');
  svg.append(area);
  for (const a of avits) {
    const l = document.createElementNS(ns, 'line');
    l.setAttribute('x1', X(a.km).toFixed(1)); l.setAttribute('x2', X(a.km).toFixed(1)); l.setAttribute('y1', p); l.setAttribute('y2', H - p);
    l.setAttribute('stroke', '#f3c969'); l.setAttribute('stroke-width', '1.5'); l.setAttribute('stroke-dasharray', '3 3');
    svg.append(l);
  }
}

function pintarRuta(r) {
  actual = r;
  $('r-titulo').textContent = r.nombre;
  $('r-nombre').value = r.nombre;
  $('r-datos').textContent = km(r.distancia_km) + ' km · +' + r.desnivel_m + ' m de desnivel';
  perfilSvg(r.perfil, r.avituallamientos);
  const av = $('avits'); av.textContent = '';
  for (const a of r.avituallamientos) av.append(filaAvit(a));
  const s = $('subidas'); s.textContent = '';
  if (!r.subidas.length) { const li = document.createElement('li'); li.textContent = 'No se han detectado subidas largas (o el GPX no trae altitud).'; s.append(li); }
  for (const q of r.subidas) {
    const li = document.createElement('li');
    li.textContent = 'Sube ' + q.n + ' · km ' + km(q.inicio) + ' a ' + km(q.fin) + ' · +' + q.desnivel_m + ' m · ' + String(q.pendiente).replace('.', ',') + ' %';
    s.append(li);
  }
  $('bajar').href = base + '/reloj.gpx?id=' + r.id;
  aviso('msg-ruta', '');
  ver('ruta');
}

$('mas-avit').addEventListener('click', () => { const f = filaAvit({}); $('avits').append(f); f.querySelector('input').focus(); });
$('volver').addEventListener('click', () => lista().catch(() => {}));

$('guardar').addEventListener('click', async () => {
  const filas = [...document.querySelectorAll('#avits .avit')].map(f => { const [n, k] = f.querySelectorAll('input'); return { name: n.value.trim(), km: k.value }; })
    .filter(a => a.name || a.km !== '');
  const b = $('guardar'); b.disabled = true; aviso('msg-ruta', 'Guardando…');
  try {
    pintarRuta((await post('/ruta', { id: actual.id, nombre: $('r-nombre').value, avituallamientos: filas })).ruta);
    aviso('msg-ruta', 'Guardado. Ya puedes descargar el GPX.', 'ok');
  } catch (err) { if (err.message !== 'sesion') aviso('msg-ruta', err.message, 'err'); }
  finally { b.disabled = false; }
});

$('borrar').addEventListener('click', async () => {
  if (!confirm('¿Borrar «' + actual.nombre + '»? No se puede deshacer.')) return;
  try { await post('/borrar', { id: actual.id }); await lista(); } catch (err) { if (err.message !== 'sesion') aviso('msg-ruta', err.message, 'err'); }
});

// si ya hay sesión (cookie), se entra directo
api('/yo').then(d => d.sesion ? lista() : ver('login')).catch(() => ver('login'));
