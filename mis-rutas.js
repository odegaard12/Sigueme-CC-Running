// Tus rutas para el reloj: el espacio del invitado. Sin librerías; los textos del usuario
// se pintan SIEMPRE con textContent (nunca innerHTML).
'use strict';
const $ = id => document.getElementById(id);
// el nombre del sitio, del dominio (odegaard12.online → odegaard12)
(() => { const h = location.hostname.replace(/^www\./, '').split('.')[0]; if (h && !/^[\d.]+$/.test(location.hostname) && location.hostname !== 'localhost') $('marca').textContent = h; })();
const km = v => String(Math.round(v * 10) / 10).replace('.', ',');
const base = '/api/invitado';
let actual = null;          // la ruta abierta

function aviso(id, texto, tipo) { const m = $(id); m.textContent = texto || ''; m.className = 'msg' + (tipo ? ' ' + tipo : ''); }
function ver(vista) {
  for (const v of ['login', 'lista', 'ruta']) $('vista-' + v).hidden = v !== vista;
  if (vista === 'login') { const g = $('btn-guia'); if (g) g.hidden = true; }
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
  $('cabecera').textContent = d.dueno ? 'Las rutas del dueño de la web, sin caducidad.' : 'Hola, ' + d.nombre + (d.caduca === '2099-12-31' ? '. Tu acceso no caduca.' : '. Tu acceso vale hasta el ' + fecha(d.caduca) + '; después se borra todo lo tuyo.');
  $('salir').hidden = !!d.dueno;
  acceso = { caduca: d.caduca, dueno: !!d.dueno, nombre: d.dueno ? '' : d.nombre };
  $('btn-guia').hidden = false;
  guiaPrimeraVez();
  const cont = $('lista'); cont.textContent = '';
  $('lista-vacia').hidden = d.rutas.length > 0;
  for (const r of d.rutas) {
    const fila = document.createElement('div'); fila.className = 'ruta-fila';
    const dato = document.createElement('div'); dato.className = 'dato';
    const nombre = document.createElement('b'); nombre.textContent = r.nombre;
    const info = document.createElement('span'); info.className = 'sub';
    info.textContent = km(r.distancia_km) + ' km · +' + r.desnivel_m + ' m' + (r.avituallamientos ? ' · ' + r.avituallamientos + ' avit.' : '') + (r.publica ? ' · pública' : '');
    dato.append(nombre, info);
    const abrir = document.createElement('button'); abrir.type = 'button'; abrir.className = 'btn chico principal'; abrir.textContent = 'Abrir';
    abrir.addEventListener('click', () => abrirRuta(r.id));
    fila.append(dato, abrir); cont.append(fila);
  }
  ver('lista');
  cargarDirectos().catch(() => {});
}

// ---- menú de saltos de una ruta (v1.59): marca el paso que se está viendo
(function () {
  const menu = document.getElementById('r-menu'); if (!menu || !('IntersectionObserver' in window)) return;
  const enlaces = [...menu.querySelectorAll('a')];
  const io = new IntersectionObserver(es => {
    for (const e of es) if (e.isIntersecting) {
      enlaces.forEach(a => a.classList.toggle('activo', a.getAttribute('href') === '#' + e.target.id));
      const a = menu.querySelector('a.activo'); if (a && menu.scrollWidth > menu.clientWidth) menu.scrollTo({ left: a.offsetLeft - (menu.clientWidth - a.offsetWidth) / 2 });
    }
  }, { rootMargin: '-30% 0px -60% 0px' });
  enlaces.forEach(a => { const t = document.querySelector(a.getAttribute('href')); if (t) io.observe(t); });
  // al llegar al final de la página, la última tarjeta es la activa aunque no cruce la franja
  addEventListener('scroll', () => { if (innerHeight + scrollY >= document.documentElement.scrollHeight - 6 && document.getElementById('vista-ruta') && !document.getElementById('vista-ruta').hidden) enlaces.forEach((a, i) => a.classList.toggle('activo', i === enlaces.length - 1)); }, { passive: true });
})();

// ---- carreras en directo (v1.54): las tuyas y en las que corres; «Tu móvil» se configura de un toque
async function cargarDirectos(abierta) {
  const d = await api('/directos');
  const cont = $('directos'); cont.textContent = '';
  $('card-directos').hidden = false;
  if (!d.directos.length) {
    const p = document.createElement('p'); p.className = 'sub';
    p.textContent = 'Aún no tienes ninguna carrera en directo. Abre una ruta y, en el paso 6, pon el día y la hora: ahí es donde se configura tu móvil (app o Traccar) y se invita a quien corra contigo. Una carrera que ya pasó no se repite: crea otra con la fecha nueva.';
    cont.append(p);
  }
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt) e.textContent = txt; return e; };
  for (const c of d.directos) {
    if (c.ident) { try { localStorage.setItem('directo.' + c.id, c.ident); } catch (e) { /* da igual */ } }
    const item = el('div', 'dir-item');
    if (c.id === abierta) item.append(el('p', 'listo-cab', '✓ Tu carrera está lista'));
    item.append(el('b', '', c.nombre), el('span', 'sub', fecha(c.fecha) + ' · salida ' + c.hora_salida + ' · ' + c.corredores.join(', ')));
    const ver = el('a', 'btn principal', 'Ver el directo'); ver.href = '/d/' + c.id; item.append(ver);
    const movil = el('div');
    if (c.ident) {
      const conf = el('button', 'btn', 'Configurar mi móvil'); conf.type = 'button';
      conf.addEventListener('click', () => { movil.hidden = !movil.hidden; if (!movil.hidden) window.pintarMovil(movil, c.ident); });
      movil.hidden = c.id !== abierta; if (!movil.hidden) window.pintarMovil(movil, c.ident);
      const ret = el('button', 'btn', 'Retirarme de esta carrera'); ret.type = 'button';
      const rmsg = el('div', 'msg');
      ret.addEventListener('click', async () => {
        if (!confirm('¿Retirarte de «' + c.nombre + '»? Dejarás de salir en el mapa y tu móvil ya no contará.')) return;
        try { await post('/retirarme', { ident: c.ident }); rmsg.textContent = 'Te has retirado. Desactiva el seguimiento en tu móvil.'; rmsg.className = 'msg ok'; ret.hidden = true; }
        catch (err) { rmsg.textContent = err.message; rmsg.className = 'msg err'; }
      });
      item.append(conf, movil, ret, rmsg);
    }
    if (c.invitacion) {
      const inv = el('button', 'btn', 'Invitar a quien corra contigo'); inv.type = 'button';
      const msg = el('div', 'msg');
      inv.addEventListener('click', async () => {
        const url = location.origin + '/d/' + c.id + '#unirse=' + c.invitacion;
        try { if (navigator.share) await navigator.share({ title: c.nombre + ' · apúntate', url }); else { await navigator.clipboard.writeText(url); msg.textContent = 'Invitación copiada: mándala por WhatsApp.'; msg.className = 'msg ok'; } }
        catch (e) { msg.textContent = url; }
      });
      const borrar = el('button', 'btn peligro', 'Borrar esta carrera'); borrar.type = 'button';
      borrar.addEventListener('click', async () => {
        if (!confirm('¿Borrar «' + c.nombre + '» del ' + fecha(c.fecha) + '? Se borra para todos los apuntados.')) return;
        try { await post('/directo', { accion: 'borrar', id: c.id }); await cargarDirectos(); } catch (err) { msg.textContent = err.message; msg.className = 'msg err'; }
      });
      item.append(inv, msg, borrar);
    }
    cont.append(item);
  }
  if (abierta) $('card-directos').scrollIntoView({ block: 'start' });
  cargarAbiertas().catch(() => {});
}

// carreras de otros a las que apuntarse sin enlace (v1.57)
async function cargarAbiertas() {
  const d = await api('/abiertas');
  const cont = $('abiertas'); cont.textContent = '';
  $('card-abiertas').hidden = !d.abiertas.length;
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt) e.textContent = txt; return e; };
  let nombreGuardado = ''; try { nombreGuardado = localStorage.getItem('nombre_carrera') || ''; } catch (e) { /* da igual */ }
  for (const c of d.abiertas) {
    const item = el('div', 'dir-item');
    item.append(el('b', '', c.nombre), el('span', 'sub', fecha(c.fecha) + ' · salida ' + c.hora_salida + (c.corredores.length ? ' · ' + c.corredores.join(', ') : '')));
    const nom = el('input'); nom.type = 'text'; nom.maxLength = 30; nom.placeholder = 'Tu nombre en el mapa'; nom.value = nombreGuardado; nom.setAttribute('aria-label', 'Tu nombre en el mapa');
    const ap = el('button', 'btn principal', 'Apuntarme'); ap.type = 'button';
    const msg = el('div', 'msg');
    ap.addEventListener('click', async () => {
      const nombre = nom.value.trim();
      if (!nombre) { msg.textContent = 'Pon tu nombre: es el que verán en el mapa.'; msg.className = 'msg err'; nom.focus(); return; }
      ap.disabled = true;
      try { try { localStorage.setItem('nombre_carrera', nombre); } catch (e) { /* da igual */ } await post('/apuntarme', { id: c.id, nombre }); await cargarDirectos(c.id); }
      catch (err) { msg.textContent = err.message; msg.className = 'msg err'; ap.disabled = false; }
    });
    const ver = el('a', 'btn', 'Ver el directo'); ver.href = '/d/' + c.id;
    item.append(nom, ap, ver, msg); cont.append(item);
  }
}

$('d-crear').addEventListener('click', async () => {
  const fechaD = $('d-fecha').value, hora = $('d-hora').value, nombre = $('d-nombre').value.trim();
  if (!fechaD) { aviso('msg-directo', 'Pon el día de la carrera.', 'err'); return; }
  if (!hora) { aviso('msg-directo', 'Pon la hora de salida.', 'err'); return; }
  if (!nombre) { aviso('msg-directo', 'Pon tu nombre: es el que verán en el mapa.', 'err'); $('d-nombre').focus(); return; }
  const b = $('d-crear'); b.disabled = true; aviso('msg-directo', 'Creando la carrera…');
  try {
    const d = await post('/directo', { ruta: actual.id, fecha: fechaD, hora, nombre });
    await lista();
    await cargarDirectos(d.id);
  } catch (err) { if (err.message !== 'sesion') aviso('msg-directo', err.message, 'err'); }
  finally { b.disabled = false; }
});

$('subir').addEventListener('click', async () => {
  const f = $('gpx').files[0];
  if (!f) { aviso('msg-lista', 'Elige primero un fichero GPX.', 'err'); return; }
  if (f.size === 0) { aviso('msg-lista', 'El fichero está vacío.', 'err'); return; }
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
  area.setAttribute('fill', 'rgba(217,242,74,.28)'); area.setAttribute('stroke', '#d9f24a'); area.setAttribute('stroke-width', '1.5');
  svg.append(area);
  for (const a of avits) {
    const l = document.createElementNS(ns, 'line');
    l.setAttribute('x1', X(a.km).toFixed(1)); l.setAttribute('x2', X(a.km).toFixed(1)); l.setAttribute('y1', p); l.setAttribute('y2', H - p);
    l.setAttribute('stroke', '#f4f7e6'); l.setAttribute('stroke-width', '1.5'); l.setAttribute('stroke-dasharray', '3 3');
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
  if (!$('d-nombre').value) $('d-nombre').value = acceso.nombre || '';
  aviso('msg-directo', '');
  aviso('msg-ruta', '');
  pintarPublicacion(r);
  ver('ruta');
}

// ---- publicar en la web
function pintarPublicacion(r) {
  $('pub-no').hidden = !!r.publica; $('pub-si').hidden = !r.publica;
  $('pub-ocultar').value = String(r.ocultar_m ?? 0); $('pub-autor').value = r.autor || '';
  $('pub-ver').href = '/r/' + r.id;
  aviso('msg-pub', '');
}
async function publicacion(publica) {
  const b = publica ? $('publicar') : $('despublicar'); b.disabled = true; aviso('msg-pub', publica ? 'Publicando…' : 'Quitando…');
  try {
    const d = await post('/ruta', { id: actual.id, publica, ocultar_m: Number($('pub-ocultar').value || 0), autor: $('pub-autor').value });
    actual = d.ruta; pintarPublicacion(actual);
    aviso('msg-pub', publica ? 'Publicada. Ya sale en la portada.' : 'Ya no es pública.', 'ok');
  } catch (err) { if (err.message !== 'sesion') aviso('msg-pub', err.message, 'err'); }
  finally { b.disabled = false; }
}
$('publicar').addEventListener('click', () => publicacion(true));
$('despublicar').addEventListener('click', () => { if (confirm('¿Dejar de publicar «' + actual.nombre + '»? Desaparece de la portada.')) publicacion(false); });
$('pub-copiar').addEventListener('click', async () => {
  const url = location.origin + '/r/' + actual.id;
  try { await navigator.clipboard.writeText(url); aviso('msg-pub', 'Enlace copiado.', 'ok'); } catch (e) { aviso('msg-pub', url, 'ok'); }
});

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

// «Admin» solo aparece si quien mira es el dueño (sesión del panel)
fetch('/api/invitado/yo', {credentials: 'same-origin'}).then(r => r.ok ? r.json() : {}).then(d => {
  const a = document.getElementById('nav-admin');
  if (a && d && d.dueno) a.hidden = false;
}).catch(() => {});

// ---------- guía de primera vez y botón «? Ayuda» ----------
let acceso = { caduca: '', dueno: false };
function textoAcceso() {
  if (acceso.dueno) return 'Eres el dueño: tus rutas no caducan. Si publicas una, sale en «Rutas y relojes»; tus carreras en directo salen en la portada.';
  if (acceso.caduca === '2099-12-31') return 'Tu acceso no caduca. Si publicas una ruta, sale en «Rutas y relojes»; tus carreras en directo, en la portada.';
  return 'Tu acceso vale hasta el ' + fecha(acceso.caduca) + '; después se borra todo lo tuyo. Si necesitas más tiempo, pídele al dueño «+30 días». Si publicas una ruta, sale en «Rutas y relojes»; tus carreras en directo, en la portada.';
}
const GUIA = [
  { t: 'Bienvenido a Mis carreras', x: 'Aquí subes tus rutas, te las llevas al reloj y, si quieres, las corres en directo para que te sigan. Te lo enseño en un minuto. Siempre podrás volver a verlo con el botón «? Ayuda».' },
  { t: 'Sube tu GPX', sel: () => $('gpx').closest('.tarjeta'), x: 'El fichero sale de Strava, Komoot, Wikiloc o de la web de la carrera. Ponle un nombre y pulsa «Subir ruta».' },
  { t: 'Ponle avituallamientos', x: 'Al abrir una ruta puedes añadir cada avituallamiento con su nombre y su kilómetro. Se llevan al reloj como puntos de control.' },
  { t: 'Llévatela al reloj', x: 'Descarga el GPX con el botón «Descargar GPX para el reloj» y súbelo con la app de tu reloj. Debajo tienes un botón por marca (Xiaomi, Huawei, Amazfit, Garmin, Coros…) que te explica cómo.' },
  { t: 'Córrela en directo', x: 'Al abrir una ruta, el paso 6: pon el día y la hora y pulsa «Crear la carrera en directo». Luego «Configurar mi móvil» deja la app Sígueme CC (Android) o Traccar (iPhone) listos de un toque, e «Invitar» manda el enlace a quien corra contigo. Sale sola en la portada; el día de la carrera solo hay que tener el móvil encendido. En iPhone, activa también «los avisos de subidas» en ese mismo apartado.' },
  { t: 'Tu acceso', sel: null, x: null },
];
let guiaPaso = -1;
const guiaId = id => document.getElementById(id);
function guiaFoco(el) {
  const f = guiaId('guia-foco');
  if (el && el.offsetParent !== null) {
    const r = el.getBoundingClientRect(), m = 6;
    Object.assign(f.style, { left: (r.left - m) + 'px', top: (r.top - m) + 'px', width: (r.width + 2 * m) + 'px', height: (r.height + 2 * m) + 'px' });
    guiaId('guia-tarjeta').classList.toggle('arriba', r.top + r.height / 2 > window.innerHeight * 0.55);
  } else {
    Object.assign(f.style, { left: '50%', top: '40%', width: '0px', height: '0px' });
  }
}
function guiaElemento(p) { try { return p.sel ? p.sel() : null; } catch (e) { return null; } }
function guiaMostrar(i) {
  guiaPaso = i;
  const p = GUIA[i];
  if (p.t === 'Sube tu GPX') ver('lista');
  const el = guiaElemento(p);
  const quieto = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (el && el.offsetParent !== null) el.scrollIntoView({ block: 'center', behavior: quieto ? 'auto' : 'smooth' });
  guiaId('guia-paso').textContent = 'Paso ' + (i + 1) + ' de ' + GUIA.length;
  guiaId('guia-titulo').textContent = p.t;
  guiaId('guia-texto').textContent = p.x === null ? textoAcceso() : p.x;
  guiaId('guia-atras').hidden = i === 0;
  guiaId('guia-saltar').hidden = i === GUIA.length - 1;
  guiaId('guia-sig').textContent = i === GUIA.length - 1 ? 'Entendido' : 'Siguiente ›';
  guiaId('guia-foco').hidden = false; guiaId('guia-tarjeta').hidden = false;
  setTimeout(() => guiaFoco(el), quieto ? 0 : 350);
  guiaId('guia-sig').focus({ preventScroll: true });
}
function guiaCerrar() {
  guiaPaso = -1;
  guiaId('guia-foco').hidden = true; guiaId('guia-tarjeta').hidden = true;
  try { localStorage.setItem('guia_mis_rutas', '1'); } catch (e) {}
  window.scrollTo({ top: 0 });
  guiaId('btn-guia').focus({ preventScroll: true });
}
// ⚠️ 1/11/2026: abierta sola al entrar, la guía tapaba justo la lista de rutas y el invitado no veía la suya.
// Ahora solo se abre con «? Ayuda».
function guiaPrimeraVez() {}
guiaId('btn-guia').addEventListener('click', () => { if (guiaPaso < 0) guiaMostrar(0); });
guiaId('guia-saltar').addEventListener('click', guiaCerrar);
guiaId('guia-atras').addEventListener('click', () => guiaMostrar(Math.max(0, guiaPaso - 1)));
guiaId('guia-sig').addEventListener('click', () => guiaPaso >= GUIA.length - 1 ? guiaCerrar() : guiaMostrar(guiaPaso + 1));
document.addEventListener('keydown', e => {
  if (guiaPaso < 0) return;
  if (e.key === 'Escape') { guiaCerrar(); return; }
  if (e.key !== 'Tab') return;
  const bs = [...guiaId('guia-tarjeta').querySelectorAll('button')].filter(b => !b.hidden);
  if (!bs.length) return;
  const i = bs.indexOf(document.activeElement);
  e.preventDefault();
  bs[e.shiftKey ? (i <= 0 ? bs.length - 1 : i - 1) : (i === bs.length - 1 ? 0 : i + 1)].focus();
});
const guiaRepintar = () => { if (guiaPaso >= 0) guiaFoco(guiaElemento(GUIA[guiaPaso])); };
window.addEventListener('scroll', guiaRepintar, { passive: true });
window.addEventListener('resize', guiaRepintar);
