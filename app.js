// ---------- Estado y utilidades de la ruta ----------
let routeGeojson = null;
let routeBounds = null;      // [west, south, east, north]
let routeLatLon = [];        // [[lat,lon], ...]
let routeCumKm = [];         // km acumulados en cada punto de routeLatLon
let totalRouteKm = 0;
let aidStations = [];

// números en formato español: 102,1 km, 11,8 km/h
const num = (v, dec = 1) => (v == null || v === '' || isNaN(v)) ? '—'
  : Number(v).toLocaleString('es-ES', { minimumFractionDigits: dec, maximumFractionDigits: dec });
const numKm = v => (v == null || v === '' || isNaN(v)) ? '—'
  : Number(v).toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const entero = v => (v == null || v === '' || isNaN(v)) ? '—' : String(Math.round(v));

// Datos pedidos desde el <head> (index.html) para no esperar a la librería
// del mapa. Si no están (o fallaron), se piden aquí.
// Todo lo propio de la carrera viene de carrera.json (nombre, fecha, hora de
// salida, límite, km mínimos para meta, corredor y bici): el código vale para
// cualquier carrera. Estos son los valores si falta algo.
// quien pide menos movimiento en el sistema no ve animaciones de cámara
const QUIETO = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

let relojSondeo = null, ritmoActual = 0;
const ARCHIVADA = !!document.querySelector('meta[name="archivo"]');
function ritmoSondeo(ms) {
  if (ARCHIVADA || ms === ritmoActual) return;
  clearInterval(relojSondeo);
  relojSondeo = setInterval(pollLive, ms);
  ritmoActual = ms;
}

let CARRERA = {
  nombre: '', lugar: '', fecha: '', modalidad: '', hora_salida: '08:30', limite_h: 12,
  zona_horaria: 'Europe/Madrid', km_minimos_meta: null, corredor: { nombre: '', dorsal: '' }, bici: null,
};
const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const kmMinimosMeta = () => CARRERA.km_minimos_meta || 0.8 * (totalRouteKm || 100);
function diaCarrera() {
  if (!CARRERA.fecha) return '';
  const d = new Date(CARRERA.fecha + 'T12:00:00');
  return isNaN(d) ? '' : d.toLocaleDateString('es-ES', { weekday: 'long', day: '2-digit', month: '2-digit' }).replace(',', '');
}
function pintarCarrera() {
  const c = CARRERA, corredor = c.corredor || {};
  const sl = document.getElementById('stat-limite');
  if (sl && /^\d+ h$/.test(sl.textContent)) sl.textContent = c.limite_h + ' h';
  // el nombre de la carrera como titular y el del sitio (del dominio) en la barra
  const tcd = document.getElementById('titulo-cd');
  if (tcd && c.nombre) tcd.textContent = c.nombre;
  const hostSitio = location.hostname.replace(/^www\./, '').split('.')[0], mcd = document.getElementById('marca-sitio');
  if (mcd && hostSitio && !/^[\d.]+$/.test(location.hostname) && location.hostname !== 'localhost') mcd.textContent = hostSitio;
  // ?v= cambia al subir otra foto desde el panel: así nadie ve la vieja
  document.querySelectorAll('img[src^="rider.png"]').forEach(i => {
    i.src = 'rider.png?v=' + (Number(c.avatar_v) || 5);
    i.alt = 'Foto de ' + (corredor.nombre || 'corredor');
  });
  const nombre = document.getElementById('ficha-nombre');
  if (nombre && corredor.nombre) nombre.textContent = corredor.nombre;
  const sub = document.getElementById('ficha-sub');
  if (sub) sub.textContent = [corredor.club, corredor.categoria].filter(Boolean).join(' · ') || c.nombre || '';
  const dorsal = document.getElementById('ficha-dorsal');
  if (dorsal && corredor.dorsal) { document.getElementById('ficha-dorsal-n').textContent = corredor.dorsal; dorsal.hidden = false; }
  // la carrera, en casillas: solo las que tienen dato
  const datos = document.getElementById('ficha-carrera');
  if (datos) {
    const fecha = c.fecha ? new Date(c.fecha + 'T12:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '';
    const casillas = [['Carrera', c.nombre], ['Modalidad', c.modalidad],
      ['Distancia', c.distancia_km ? num(c.distancia_km, c.distancia_km % 1 ? 1 : 0) + ' km' : ''],
      ['Desnivel', c.desnivel_m ? '+' + Math.round(c.desnivel_m).toLocaleString('es-ES') + ' m' : ''],
      ['Salida', [fecha, c.hora_salida].filter(Boolean).join(' · ')], ['Límite', c.limite_h ? c.limite_h + ' h' : '']];
    datos.textContent = '';
    casillas.filter(([, v]) => v).forEach(([k, v]) => {
      const fila = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = k; dd.textContent = v; fila.append(dt, dd); datos.append(fila);
    });
  }
  const bici = document.getElementById('ficha-bici');
  if (bici && c.bici && c.bici.modelo) {
    document.getElementById('ficha-bici-modelo').textContent = c.bici.modelo;
    const dl = document.getElementById('ficha-specs');
    dl.textContent = '';
    Object.entries(c.bici.piezas || {}).forEach(([k, v]) => {
      const fila = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = k; dd.textContent = v; fila.append(dt, dd); dl.append(fila);
    });
    bici.hidden = false;
  }
  const pie = document.getElementById('pie-carrera');
  if (pie) pie.textContent = [c.nombre, c.lugar].filter(Boolean).join(' · ');
}

function precargado(nombre, respaldo) {
  const p = window.__datos && window.__datos[nombre];
  if (p) {
    delete window.__datos[nombre];
    // ⚠️ esa petición no tiene tiempo límite: si al abrir la web la conexión
    // se quedaba colgada, el primer poll no acababa nunca y, con el cerrojo
    // puesto, ya no se pedía nada más (web congelada y sin aviso)
    const tope = new Promise(r => setTimeout(() => r(null), 10000));
    return Promise.race([p, tope]).then(v => v || respaldo());
  }
  return respaldo();
}

function haversineKm(a, b) {
  const R = 6371;
  const toRad = x => x * Math.PI / 180;
  const dLat = toRad(b[0] - a[0]);
  const dLon = toRad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// ⚠️ La ruta es CIRCULAR: salida y meta son el mismo sitio, y hay tramos que
// se repiten. Quedarse con el punto más cercano a secas hacía que al llegar a
// meta el recorrido se leyera como "km 0" (el trazado de ida pasa por ahí),
// así que no se detectaba la llegada. Solución: entre todos los candidatos
// igual de cerca (±50 m), se elige el que esté más pegado a lo que ya llevaba
// recorrido. Con eso el progreso avanza siempre hacia delante.
let ultimoKmConocido = 0;
let anclaDelGps = false;   // ultimoKmConocido viene del ciclocomputador, no de la ruta
let largoLinea = 0;
let factorKm = 1;

function projectOntoRoute(lat, lon) {
  if (routeLatLon.length < 2) return { distKm: Infinity, alongKm: 0 };
  const candidatos = [];
  let mejorDist = Infinity;
  for (let i = 0; i < routeLatLon.length - 1; i++) {
    const a = routeLatLon[i], b = routeLatLon[i + 1];
    const segKm = haversineKm(a, b) || 1e-9;
    const abx = b[1] - a[1], aby = b[0] - a[0];
    const apx = lon - a[1], apy = lat - a[0];
    const t = Math.max(0, Math.min(1, (apx * abx + apy * aby) / (abx * abx + aby * aby || 1e-12)));
    const projLat = a[0] + t * aby, projLon = a[1] + t * abx;
    const distKm = haversineKm([lat, lon], [projLat, projLon]);
    if (distKm < mejorDist) mejorDist = distKm;
    candidatos.push({ distKm, alongKm: routeCumKm[i] + t * segKm });
  }
  // ultimoKmConocido va en km oficiales; aquí se compara en km de la línea
  const ancla = ultimoKmConocido / (factorKm || 1);
  const cerca = candidatos.filter(c => c.distKm <= mejorDist + 0.05);
  // ida y vuelta: en la vuelta el tramo de la ida está igual de cerca (y ganaba por ir antes). Como
  // en la app: de lo que no va hacia atrás, la PRIMERA pasada (menor km, así tampoco salta a una
  // pasada posterior por el mismo sitio); si no hay nada por delante, el más cercano al último km
  const adelante = cerca.filter(c => c.alongKm >= ancla - 0.02);
  if (adelante.length) return adelante.reduce((a, b) => (b.alongKm < a.alongKm ? b : a));
  let best = cerca[0];
  for (const c of cerca) {
    if (Math.abs(c.alongKm - ancla) < Math.abs(best.alongKm - ancla)) best = c;
  }
  return best;
}

// Dado un km sobre la ruta, interpola su posición [lat, lon].
function pointAtKm(km) {
  if (!routeLatLon.length) return null;
  let i = 0;
  while (i < routeCumKm.length - 1 && routeCumKm[i + 1] < km) i++;
  const a = routeLatLon[i], b = routeLatLon[Math.min(i + 1, routeLatLon.length - 1)];
  const segKm = routeCumKm[Math.min(i + 1, routeCumKm.length - 1)] - routeCumKm[i] || 1e-9;
  const t = Math.max(0, Math.min(1, (km - routeCumKm[i]) / segKm));
  return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])];
}

// ⚠️ Por qué los popups no se abrían (dos trampas encadenadas):
//  1. MapLibre v4 se niega a abrir el popup de un marcador si
//     elemento.style.opacity === opacityWhenCovered. Como los marcadores
//     llevan opacityWhenCovered para que no se desvanezcan sobre el terreno,
//     poner '1' los dejaba mudos: '1' === '1'. Por eso va '0.99', que se ve
//     igual pero nunca coincide.
//  2. El clic también llega al mapa y, con closeOnClick (por defecto), cierra
//     el popup en el mismo gesto -> closeOnClick:false.
const marcadoresConPopup = [];

function nuevoPopup(offset) {
  return new maplibregl.Popup({ offset, closeOnClick: false });
}

function pulsarAbrePopup(marcador, elemento) {
  elemento.style.cursor = 'pointer';
  // Se abre en un setTimeout(0) a propósito: así corre DESPUÉS de todos los
  // manejadores del clic (el propio de MapLibre incluido) y el estado final es
  // siempre "abierto", sin depender de si MapLibre lo abrió, lo cerró o las
  // dos cosas.
  // Hay que usar togglePopup() y no popup.addTo(mapa): el popup de un marcador
  // no tiene coordenadas propias, se las pone el marcador al abrirlo. Con
  // addTo() directo, isOpen() decía "true" pero no se pintaba nada.
  // isOpen() no sirve de guarda: los popups nacen con _map puesto (isOpen
  // true) pero sin coordenadas, así que "están abiertos" sin pintarse nada.
  // Lo que vale es mirar si su nodo está de verdad en la página; si no lo
  // está, se limpia el estado fantasma y se abre con togglePopup(), que es
  // quien le pasa las coordenadas del marcador.
  const abrir = () => setTimeout(() => {
    const popup = marcador.getPopup();
    if (!popup) return;
    // cerrar los demás SIEMPRE y primero: si se comprueba antes si este ya
    // está abierto, se salía por ahí y el anterior se quedaba abierto
    marcadoresConPopup.forEach(m => {
      if (m === marcador) return;
      const p = m.getPopup();
      if (p) p.remove();
    });
    const visible = popup._container && popup._container.parentNode;
    if (!visible) marcador.togglePopup();
  }, 0);
  marcadoresConPopup.push(marcador);
  elemento.addEventListener('click', abrir);
  elemento.addEventListener('touchend', abrir, { passive: true });
  return marcador;
}

// Chincheta de color macizo: probada la versión oscura y sobre el satélite se
// leía mucho peor, así que el color manda y el número va calado en negro.
function aidPinSVG(color, label) {
  const size = /^\d+$/.test(label) ? 10 : 9;
  return `
    <svg width="26" height="34" viewBox="0 0 26 34" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 0C5.8 0 0 5.8 0 13c0 9.5 13 21 13 21s13-11.5 13-21C26 5.8 20.2 0 13 0z"
            fill="${color}" stroke="#0b1210" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="8.5" fill="#0b1210"/>
      <text x="13" y="${13 + size / 2 - 1}" text-anchor="middle" font-size="${size}" font-weight="700" fill="${color}">${label}</text>
    </svg>`;
}

// Mezcla un color con el gris del panel: sirve para pintar lo que aún no se ha
// recorrido "apagado" pero sin perder de qué color es esa rampa.
function colorApagado(hex) {
  const n = parseInt(hex.slice(1), 16);
  // solo un 15 % del color: con más, lo que falta parecía ya recorrido
  const mezcla = (c, gris) => Math.round(c * 0.22 + gris * 0.78);
  const r = mezcla((n >> 16) & 255, 0x2b);
  const g = mezcla((n >> 8) & 255, 0x32);
  const b = mezcla(n & 255, 0x2e);
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}

function traveledIndex(alongKm) {
  let idx = 0;
  while (idx < routeCumKm.length - 1 && routeCumKm[idx + 1] <= alongKm) idx++;
  return idx;
}

// ---------- Mapa 3D (MapLibre + satélite + terreno) ----------
let map3d = null;
let mapReady = false;
let riderMarkerEl = null;
let riderMarkerPos = null;
let tamanoCorredorActual = 0;
const map3dDiv = document.getElementById('map3d');
const btnRecenter = document.getElementById('btn-recenter');
if (btnRecenter) {
  btnRecenter.innerHTML = '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="12" cy="7.5" r="3.2"/><path d="M5.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/></svg><span class="t">Seguir</span>';
}
const geoHint = document.getElementById('geo-hint');

// Compartir: en el móvil abre el menú de compartir (WhatsApp, etc.); en el PC
// copia el enlace. La vista previa sale de las etiquetas og: del <head>.
const botonCompartir = document.getElementById('compartir');
if (botonCompartir) {
  botonCompartir.addEventListener('click', async () => {
    const datos = { title: document.title, text: ARCHIVADA ? 'Mira mi carrera' : 'Sígueme en directo', url: location.href.split('#')[0] };
    try {
      if (navigator.share) { await navigator.share(datos); return; }
      await navigator.clipboard.writeText(datos.url);
      botonCompartir.classList.add('hecho');
      botonCompartir.title = 'Enlace copiado';
      setTimeout(() => { botonCompartir.classList.remove('hecho'); botonCompartir.title = 'Compartir el enlace'; }, 1800);
    } catch (e) { /* cancelado por el usuario */ }
  });
}

const botonFicha = document.getElementById('ver-ficha');
if (botonFicha) {
  botonFicha.addEventListener('click', () => {
    const ficha = document.getElementById('ficha');
    ficha.hidden = !ficha.hidden;
    botonFicha.setAttribute('aria-expanded', ficha.hidden ? 'false' : 'true');
    // OJO: cambiar textContent del botón borraba la foto que lleva dentro.
    // Solo se toca el <span> del texto.
    document.getElementById('ver-ficha-txt').textContent = ficha.hidden ? 'Mi ficha' : 'Cerrar';
    if (!ficha.hidden) ficha.scrollIntoView({ behavior: QUIETO ? 'auto' : 'smooth', block: 'nearest' });
  });
}

function quitarPantallaDeCarga() {
  const tapa = document.getElementById('cargando');
  if (!tapa || tapa.classList.contains('fuera')) return;
  tapa.classList.add('fuera');      // se queda oculta: el aviso de mapa roto la reutiliza
  // tras un minuto funcionando, una pérdida de WebGL dentro de horas vuelve a tener sus reintentos
  setTimeout(() => { if (mapReady) intentosDeMapa = 0; }, 60000);
}

// Posición del sol (aproximada, sin ecuación del tiempo): sirve para que las sombras del relieve vayan con la hora real.
function posicionSol(lat, lon, fecha) {
  const rad = Math.PI / 180;
  const dia = (fecha - Date.UTC(fecha.getUTCFullYear(), 0, 0)) / 864e5;
  const decl = -23.44 * rad * Math.cos(2 * Math.PI / 365 * (dia + 10));
  const hSolar = fecha.getUTCHours() + fecha.getUTCMinutes() / 60 + lon / 15;
  const h = (hSolar - 12) * 15 * rad, la = lat * rad;
  const alt = Math.asin(Math.sin(la) * Math.sin(decl) + Math.cos(la) * Math.cos(decl) * Math.cos(h));
  const az = Math.atan2(Math.sin(h), Math.cos(h) * Math.sin(la) - Math.tan(decl) * Math.cos(la)) + Math.PI;
  return { az: ((az / rad) % 360 + 360) % 360, alt: alt / rad };
}

function ponerSombras() {
  if (!map3d || !map3d.getSource('terrain')) return;
  const c = routeBounds ? [(routeBounds[1] + routeBounds[3]) / 2, (routeBounds[0] + routeBounds[2]) / 2] : [map3d.getCenter().lat, map3d.getCenter().lng];
  const sol = posicionSol(c[0], c[1], new Date());
  const fuerza = sol.alt > 0 ? Math.min(0.55, 0.15 + sol.alt / 120) : 0.1;      // de noche, casi sin sombras
  const paint = { 'hillshade-illumination-direction': Math.round(sol.az), 'hillshade-exaggeration': fuerza };
  if (map3d.getLayer('sombras')) {
    for (const k in paint) map3d.setPaintProperty('sombras', k, paint[k]);
  } else {
    map3d.addLayer({ id: 'sombras', type: 'hillshade', source: 'terrain',
      paint: Object.assign({ 'hillshade-illumination-anchor': 'map', 'hillshade-shadow-color': 'rgba(0,0,0,0.9)',
        'hillshade-highlight-color': 'rgba(255,255,255,0.3)', 'hillshade-accent-color': 'rgba(0,0,0,0.25)' }, paint) },
      map3d.getLayer('route-line') ? 'route-line' : undefined);
  }
}

function relieveVivo() {
  const meta = 1.4;
  if (QUIETO) { map3d.setTerrain({ source: 'terrain', exaggeration: meta }); ponerSombras(); return; }
  map3d.setTerrain({ source: 'terrain', exaggeration: 0.1 });
  const t0 = performance.now();
  const paso = ahora => {
    const t = Math.min(1, (ahora - t0) / 1600);
    map3d.setTerrain({ source: 'terrain', exaggeration: 0.1 + (meta - 0.1) * (1 - Math.pow(1 - t, 3)) });
    if (t < 1) requestAnimationFrame(paso);
  };
  requestAnimationFrame(paso);
  ponerSombras();
  setInterval(ponerSombras, 10 * 60 * 1000);       // el sol se mueve
}

function buildMap3D() {
  map3d = new maplibregl.Map({
    container: 'map3d',
    // Satélite (Esri World Imagery, gratis, sin API key) drapeado sobre el
    // terreno real (AWS terrain-rgb) -> esto se ve como 3D real, no un mapa
    // de calles inclinado.
    style: {
      version: 8,
      sources: {
        satellite: {
          type: 'raster',
          tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
          tileSize: 256,
          attribution: 'Imágenes © Esri, Maxar, Earthstar Geographics y la comunidad de usuarios GIS'
        },
        terrain: {
          type: 'raster-dem',
          tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
          tileSize: 256,
          encoding: 'terrarium',
          maxzoom: 14
        }
      },
      layers: [{ id: 'satellite', type: 'raster', source: 'satellite' }],
      sky: { 'sky-color': '#0f1b2a', 'horizon-color': '#28455c', 'fog-color': '#0c0f0e', 'sky-horizon-blend': 0.8, 'horizon-fog-blend': 0.6 }
    },
    // el terreno NO va en el estilo inicial: se enciende cuando ya se ve el
    // mapa (abajo, en 'idle'). Pedir a la vez satélite + modelo de elevación
    // era lo que hacía la primera carga tan lenta.
    pitch: 50,
    bearing: -20,
    maxPitch: 62,
    // El satélite de Esri se queda sin fotos a partir de cierto acercamiento y
    // salía el cartel de "mapa no disponible". Con este tope nunca se pasa de
    // donde hay imagen.
    maxZoom: 17.5,
    center: [-3.7, 40.4],          // la península; enseguida encuadra la ruta
    zoom: 11,
    // con un dedo se desliza la página y con dos se mueve el mapa: si no, en
    // el móvil es imposible bajar a ver las métricas sin arrastrar el mapa
    cooperativeGestures: window.matchMedia('(pointer: coarse)').matches,
    // los avisos de MapLibre vienen en inglés ("Use two fingers…")
    locale: {
      'CooperativeGesturesHandler.WindowsHelpText': 'Usa Ctrl + rueda para hacer zoom',
      'CooperativeGesturesHandler.MacHelpText': 'Usa ⌘ + rueda para hacer zoom',
      'CooperativeGesturesHandler.MobileHelpText': 'Mueve el mapa con dos dedos',
      'NavigationControl.ZoomIn': 'Acercar',
      'NavigationControl.ZoomOut': 'Alejar',
      'NavigationControl.ResetBearing': 'Volver al norte'
    },
    fadeDuration: 0,
    maxTileCacheSize: 60,
    refreshExpiredTiles: false,
    // la atribución de Esri se quita del mapa (tapaba el perfil) y se pone
    // como texto en el pie de página, que cumple igual
    attributionControl: false
  });

  map3d.on('error', e => console.error('map3d error:', e && e.error));

  // el relieve entra cuando el mapa plano ya está pintado
  map3d.once('idle', () => {
    if (!map3d.getTerrain()) relieveVivo();
    quitarPantallaDeCarga();
  });

  // Red de seguridad: si el mapa no llega nunca a estar del todo quieto
  // (teselas que tardan, cobertura mala), 'idle' no salta y la pantalla de
  // carga se quedaba puesta tapando el mapa. A los 8 s se quita igual.
  setTimeout(quitarPantallaDeCarga, 8000);
  // ⚠️ Antes se quitaba 1,5 s después de 'load' y se veía el mapa pintándose:
  // primero el color plano, luego las teselas a trozos (parecía que la pantalla
  // se ponía verde y de golpe azul). Ahora se espera a que las teselas estén
  // DE VERDAD cargadas, comprobándolo cada cuarto de segundo.
  map3d.on('load', () => {
    const esperar = setInterval(() => {
      if (map3d.areTilesLoaded()) {
        clearInterval(esperar);
        quitarPantallaDeCarga();
      }
    }, 250);
    setTimeout(() => clearInterval(esperar), 8000);
  });

  map3d.on('load', () => {
    map3d.addSource('route', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
    map3d.addLayer({
      id: 'route-line', type: 'line', source: 'route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#d9f24a', 'line-width': 5, 'line-opacity': 0.95 }
    });

    map3d.addSource('traveled', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
    map3d.addLayer({
      id: 'traveled-line', type: 'line', source: 'traveled',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#5cc2e8', 'line-width': 6 }
    });

    // cometa: el último kilómetro, claro en la cabeza y apagándose hacia atrás (degradado fijo, no se anima: no cuesta nada)
    map3d.addSource('cometa', { type: 'geojson', lineMetrics: true, data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
    map3d.addLayer({
      id: 'cometa-line', type: 'line', source: 'cometa',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-width': 10, 'line-blur': 3,
        'line-gradient': ['interpolate', ['linear'], ['line-progress'], 0, 'rgba(244,247,230,0)', 1, 'rgba(244,247,230,0.95)'] }
    });

    mapReady = true;
    ajustarTamanoCorredor();
    onMapReady();
  });

  // la foto del corredor crece al acercar y encoge al alejar: a zoom de toda
  // la ruta tapaba media provincia
  map3d.on('zoom', ajustarTamanoCorredor);
  // arrastrar el mapa = quiere mirar otra cosa: se deja de seguir
  map3d.on('dragstart', () => marcarSiguiendo(false));
}

let chinchetasPuestas = false;

// ⚠️ Visto en pruebas: a veces el mapa se queda a medias (el estilo nunca
// termina de montarse) y, como la pantalla de carga se quita a los 8 s, el
// resultado es un recuadro negro sin chinchetas y sin ningún aviso. También
// puede pasar en el móvil si el navegador se lleva por delante el contexto
// gráfico al cambiar de app. Este vigilante lo detecta y rehace el mapa.
let intentosDeMapa = 0, temporizadorRevisar = null;
let lienzoActual = null;
let revisarActual = null;
const alPerderContexto = () => rehacerMapa('contexto gráfico perdido');

function montarMapa() {
  try {
    buildMap3D();
  } catch (e) {
    map3dDiv.innerHTML = '<p style="color:#eef2ee;text-align:center;padding:40px 16px">No se pudo cargar el mapa 3D: ' + esc(e.message) + '</p>';
    return;
  }
  // si el contexto gráfico se pierde (cambiar de app, memoria baja), rehacer.
  // ⚠️ map3d.remove() también lo pierde (y el aviso llega un instante
  // después): sin desengancharlo antes, cada rehacer contaba como DOS fallos
  // y a la segunda salía "no se pudo cargar el mapa".
  lienzoActual = map3d.getCanvas();
  if (lienzoActual) lienzoActual.addEventListener('webglcontextlost', alPerderContexto);
  // ⚠️ Con la pestaña en segundo plano el navegador congela el dibujado y el
  // mapa NO se monta hasta que se mira: eso no es un fallo y no hay que
  // rehacer nada. Se comprueba solo con la página a la vista.
  // ⚠️ Solo cuenta si el mapa NO llegó a arrancar ('load'). Antes también
  // miraba isStyleLoaded(), que da falso mientras quedan teselas por bajar:
  // con cobertura lenta (medido a 400 kbit/s) destruía a los 12 s un mapa que
  // ya funcionaba, y lo volvía a descargar dos veces.
  const revisar = () => {
    if (document.hidden) return;
    if (!mapReady) rehacerMapa('el mapa no terminó de cargar');
  };
  clearTimeout(temporizadorRevisar);
  temporizadorRevisar = setTimeout(revisar, 20000);
  revisarActual = revisar;
}

// UNA sola escucha: si se ponía dentro de montarMapa, cada mapa rehecho añadía
// otra, y al volver a la pestaña saltaban todas y gastaban los reintentos
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !mapReady && revisarActual) {
    clearTimeout(temporizadorRevisar);
    temporizadorRevisar = setTimeout(revisarActual, 20000);
  }
});

function avisoMapaRoto() {
  // Si ni rehaciéndolo arranca (móvil sin memoria, WebGL agotado), mejor
  // decirlo claro que dejar un recuadro negro para siempre.
  const tapa = document.getElementById('cargando');
  if (!tapa) return;
  tapa.classList.remove('fuera');
  tapa.innerHTML = '<p style="text-align:center;padding:0 20px;line-height:1.5">' +
    'No se pudo cargar el mapa en este móvil.<br>Los datos de abajo siguen en directo.</p>' +
    '<button class="btn-recargar">Volver a intentarlo</button>';
  tapa.querySelector('.btn-recargar').addEventListener('click', () => location.reload());
}

function rehacerMapa(motivo) {
  if (intentosDeMapa >= 2) { avisoMapaRoto(); return; }   // no entrar en bucle
  intentosDeMapa++;
  console.warn('Rehaciendo el mapa:', motivo);
  const tapa = document.getElementById('cargando');
  if (tapa) tapa.classList.remove('fuera');
  if (lienzoActual) lienzoActual.removeEventListener('webglcontextlost', alPerderContexto);
  try { map3d.remove(); } catch (e) {}
  mapReady = false;
  chinchetasPuestas = false;
  marcadoresConPopup.length = 0;
  riderMarkerEl = null;
  fantasmaEl = null;
  tamanoCorredorActual = 0;
  kmPintado = null;
  objetivo = null;      // si no, el siguiente poll no repinta la línea azul
  idxRecorridoPintado = -1;
  montarMapa();
}

// La librería del mapa (800 KB) llega aparte (async): las cifras, el perfil y
// los avituallamientos se pintan sin esperarla. Medido en un móvil lento:
// antes los datos salían a los 7-9 s, detrás de la librería.
if (window.__libMapa) window.__libMapa.then(montarMapa, avisoMapaRoto);
else montarMapa();


// Se llama cuando el mapa Y la ruta están listos (llegan async, en cualquier orden).
function onMapReady() {
  if (!mapReady || !routeGeojson) return;

  map3d.getSource('route').setData(routeGeojson);

  // esta función entra varias veces (mapa listo, ruta cargada, avituallamientos
  // cargados). Sin esta guarda se duplicaban las chinchetas.
  if (chinchetasPuestas) {
    if (riderMarkerPos) placeRiderMarker(riderMarkerPos[0], riderMarkerPos[1]);
    return;
  }
  if (!avitusCargados) return;      // hasta saber si hay avituallamientos
  chinchetasPuestas = true;

  map3d.fitBounds(
    [[routeBounds[0], routeBounds[1]], [routeBounds[2], routeBounds[3]]],
    { padding: 30, pitch: 50, bearing: -20, duration: 0 }
  );

  // salida y meta: una bandera si es un recorrido circular, dos si no
  const startPos = routeLatLon[0], endPos = routeLatLon[routeLatLon.length - 1];
  const circular = startPos && endPos && haversineKm(startPos, endPos) < 0.3;
  const bandera = (pos, tipo, km) => {
    const el = document.createElement('div');
    el.className = 'aid-pin';
    el.innerHTML = aidPinSVG('#f3f6f2', 'M');
    pulsarAbrePopup(
      new maplibregl.Marker({ element: el, anchor: 'bottom', opacityWhenCovered: '0.99' })
        .setLngLat([pos[1], pos[0]])
        .setPopup(nuevoPopup(30).setHTML(
          '<div class="globo"><span class="globo-tipo">' + tipo + '</span>' +
          '<b>' + esc(CARRERA.lugar || CARRERA.nombre || tipo) + '</b>' +
          '<span class="globo-km">' + km + '</span></div>'))
        .addTo(map3d),
      el);
  };
  if (startPos) bandera(startPos, circular ? 'Salida y meta' : 'Salida', circular ? 'km 0 · km ' + num(totalRouteKm) : 'km 0');
  if (endPos && !circular) bandera(endPos, 'Meta', 'km ' + num(totalRouteKm));

  // avituallamientos como chinchetas numeradas: verde normal, naranja el
  // principal (comida caliente), azul los talleres MTB, igual que la guía
  aidStations.forEach((s, i) => {
    const pos = pointAtKm(s.km / (factorKm || 1));
    if (!pos) return;
    const color = s.principal ? '#e08a3a' : s.taller ? '#5cc2e8' : '#d9f24a';
    const tipo = s.principal ? 'Avituallamiento principal'
      : s.taller ? 'Avituallamiento + asistencia mecánica'
      : 'Avituallamiento';
    const el = document.createElement('div');
    el.className = 'aid-pin';
    el.innerHTML = aidPinSVG(color, s.taller ? 'T' : String(i + 1));
    pulsarAbrePopup(
      new maplibregl.Marker({ element: el, anchor: 'bottom', opacityWhenCovered: '0.99' })
        .setLngLat([pos[1], pos[0]])
        .setPopup(nuevoPopup(30).setHTML(
          '<div class="globo"><span class="globo-tipo" style="color:' + color + '">' + tipo + '</span>' +
          '<b>' + (i + 1) + '. ' + esc(s.name) + '</b>' +
          '<span class="globo-km">km ' + num(s.km) + ' · faltan ' +
          num(totalRouteKm - s.km) + ' km para meta</span></div>'))
        .addTo(map3d),
      el);
  });

  if (riderMarkerPos) placeRiderMarker(riderMarkerPos[0], riderMarkerPos[1]);
  idxRecorridoPintado = -1;
  drawTraveledLine(currentKm || 0);
}

precargado('carrera.json', () => fetch('carrera.json').then(r => r.ok ? r.json() : null).catch(() => null))
  .then(c => { if (c) { CARRERA = Object.assign(CARRERA, c); gestionarSW(); } pintarCarrera(); });

// la ruta y el perfil son imprescindibles: si fallan (404/5xx, sin red) se reintentan solos, cada vez más espaciados
function jsonConReintento(url, intento = 0) {
  return fetch(url).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .catch(() => new Promise(ok => setTimeout(ok, Math.min(30000, 2000 * 2 ** intento))).then(() => jsonConReintento(url, intento + 1)));
}

precargado('route.geojson', () => jsonConReintento('route.geojson'))
  .then(geojson => {
    routeGeojson = geojson;
    const props = geojson.features[0].properties;
    if (!document.getElementById('stat-dist').dataset.real) document.getElementById('stat-dist').textContent = numKm(props.distance_km);
    if (!document.getElementById('stat-gain').dataset.real) document.getElementById('stat-gain').textContent = Number(props.elevation_gain_m).toLocaleString('es-ES');
    totalRouteKm = props.distance_km;

    const coords = geojson.features[0].geometry.coordinates;
    routeLatLon = coords.map(c => [c[1], c[0]]);
    routeCumKm = [0];
    let west = coords[0][0], east = coords[0][0], south = coords[0][1], north = coords[0][1];
    for (let i = 1; i < routeLatLon.length; i++) {
      routeCumKm.push(routeCumKm[i - 1] + haversineKm(routeLatLon[i - 1], routeLatLon[i]));
    }
    for (const [lon, lat] of coords) {
      if (lon < west) west = lon;
      if (lon > east) east = lon;
      if (lat < south) south = lat;
      if (lat > north) north = lat;
    }
    routeBounds = [west, south, east, north];
    // El trazado simplificado suma algo menos que el GPX entero (102,5 vs
    // 103,36). Para que "km restan" llegue a 0 y la meta se detecte, los km
    // medidos sobre la línea se escalan al total oficial de la cabecera.
    largoLinea = routeCumKm[routeCumKm.length - 1];
    factorKm = largoLinea ? totalRouteKm / largoLinea : 1;

    loadAidStations();
    onMapReady();
    // la ruta tarda en llegar y el primer poll suele adelantarse: sin esto,
    // los km y el trazado se quedaban en blanco hasta el siguiente (15 s)
    pollLive();
  });

// Se editan a mano en aid_stations.json ([{ "name": "...", "km": 0 }, ...]) —
// no hay forma de sacarlos del GPX, así que se rellenan antes de la carrera.
let avitusCargados = false;
function loadAidStations() {
  precargado('aid_stations.json', () => fetch('aid_stations.json').then(r => r.ok ? r.json() : []))
    .then(stations => {
      aidStations = stations || [];
      avitusCargados = true;
      document.querySelector('.leyenda').hidden = !aidStations.length;
      const hay = { normal: aidStations.some(s => !s.principal && !s.taller), principal: aidStations.some(s => s.principal),
                    taller: aidStations.some(s => s.taller) };
      document.querySelectorAll('.leyenda [data-tipo]').forEach(el => { el.hidden = !hay[el.dataset.tipo]; });
      drawElevationMarkers();
      onMapReady();
    })
    .catch(() => { avitusCargados = true; onMapReady(); });
}

// ---------- Perfil de altimetría ----------
// El rojo es para las SUBIDAS duras. Antes se usaba el valor absoluto y las
// bajadas fuertes salían igual de rojas, que no tiene sentido: ahora las
// bajadas van en azul, más claro cuanto más se despeñan.
function gradColor(g) {
  if (g < 0) {
    // azules apagados a propósito: las bajadas no tienen que competir con las
    // subidas, que son las que hay que sufrir
    const a = -g;
    if (a < 5) return '#2f4f5e';
    if (a < 10) return '#3a6d82';
    return '#4a92ae';
  }
  if (g < 4) return '#4fb350';
  if (g < 7) return '#e0c341';
  if (g < 10) return '#e08a3a';
  return '#e0473a';
}

let lastEleData = null;
let currentKm = 0; // hasta dónde ha avanzado el corredor, para completar el perfil

precargado('elevation.json', () => jsonConReintento('elevation.json'))
  .then(data => {
    lastEleData = data;
    drawElevationChart(data.profile, data.min_ele_m, data.max_ele_m);
  });

// Pendiente del tramo en el que va ahora mismo, sacada del propio perfil.
function pendienteEn(km) {
  if (!lastEleData || !lastEleData.profile || lastEleData.profile.length < 2) return '—';
  const perfil = lastEleData.profile;
  const maxD = perfil[perfil.length - 1].d;
  const i = Math.min(perfil.length - 1, Math.max(1, Math.round(km / maxD * (perfil.length - 1))));
  const g = perfil[i].grad;
  return (g > 0 ? '+' : '') + num(g) + '%';
}

function drawElevationMarkers() {
  if (lastEleData) drawElevationChart(lastEleData.profile, lastEleData.min_ele_m, lastEleData.max_ele_m);
}

// en un perfil de ~380 px, un píxel son ~270 m: repintarlo 5 veces por
// segundo no se veía, solo gastaba
let pixelPerfilPintado = null;
function perfilSiCambia(km) {
  const canvas = document.getElementById('elevation-chart');
  const px = Math.round((km / (totalRouteKm || 1)) * (canvas.clientWidth || 1));
  if (px === pixelPerfilPintado) return;
  pixelPerfilPintado = px;
  drawElevationMarkers();
}

function drawElevationChart(profile, minEle, maxEle) {
  if (!profile || profile.length < 2) return;      // GPX sin altura: no hay perfil que dibujar
  const canvas = document.getElementById('elevation-chart');
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth || canvas.parentElement.clientWidth;
  const cssH = canvas.clientHeight || 64;
  if (!cssW) return;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const padL = 4, padR = 4, padT = 18, padB = 2;
  const w = cssW - padL - padR;
  const h = cssH - padT - padB;
  const maxD = profile[profile.length - 1].d;
  const range = Math.max(1, maxEle - minEle);

  const x = d => padL + (d / maxD) * w;
  const y = ele => padT + h - ((ele - minEle) / range) * h;

  ctx.clearRect(0, 0, cssW, cssH);

  // Con 1293 puntos en 66 px de alto salían rayas finísimas de colores que
  // parecían un estampado de rombos. Se agrupan en tiras de ~3 px de ancho,
  // con la pendiente media del tramo: se lee de un vistazo y se ve limpio.
  const porTira = Math.max(1, Math.round(profile.length / (w / 3)));
  const tiras = [];
  for (let i = 1; i < profile.length; i += porTira) {
    const trozo = profile.slice(i, i + porTira);
    if (!trozo.length) break;
    // ⚠️ Antes la tira se dibujaba solo con su primer y último punto: los
    // picos que caían EN MEDIO quedaban por encima del relleno y se veían
    // "enterrados", con la punta gris. Ahora se guarda el trozo entero y el
    // relleno sigue la línea punto por punto.
    tiras.push({
      d0: profile[i - 1].d,
      ele0: profile[i - 1].ele,
      puntos: trozo,
      grad: trozo.reduce((m, p) => Math.abs(p.grad) > Math.abs(m) ? p.grad : m, 0)
    });
  }

  // el perfil entero se pinta apagado y luego se repinta a color sólo hasta
  // currentKm: así se va "rellenando" según avanza, en vez de oscurecerse
  function paintProfile(colorFn) {
    for (const t of tiras) {
      const ultimo = t.puntos[t.puntos.length - 1];
      ctx.beginPath();
      ctx.moveTo(x(t.d0), padT + h);
      ctx.lineTo(x(t.d0), y(t.ele0));
      for (const p of t.puntos) ctx.lineTo(x(p.d), y(p.ele));
      // +0.6 px: sin solape se veían rayitas finas entre tira y tira
      ctx.lineTo(x(ultimo.d) + 0.6, y(ultimo.ele));
      ctx.lineTo(x(ultimo.d) + 0.6, padT + h);
      ctx.closePath();
      ctx.fillStyle = colorFn(t);
      ctx.fill();
    }
  }

  // lo que falta va a color pero atenuado, y lo recorrido a color pleno: así
  // se ven las rampas duras desde el principio y aun así se nota el avance
  const doneX = currentKm > 0 ? x(Math.min(currentKm, maxD)) : 0;
  // SIEMPRE apagado lo que no se ha recorrido, también antes de salir: con la
  // web a cero y el perfil a todo color parecía que ya estaba completado.
  paintProfile(t => colorApagado(gradColor(t.grad)));
  if (doneX > 0) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(padL, padT, doneX - padL, h);
    ctx.clip();
    paintProfile(p => gradColor(p.grad));
    ctx.restore();
  }

  ctx.beginPath();
  ctx.moveTo(x(profile[0].d), y(profile[0].ele));
  for (const p of profile) ctx.lineTo(x(p.d), y(p.ele));
  ctx.strokeStyle = '#eef2ee';
  ctx.globalAlpha = 0.35;
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.globalAlpha = 1;

  // los avituallamientos van sobre la propia línea de elevación, como en la
  // guía oficial, no colgando del techo del gráfico
  const eleAtKm = km => {
    const i = Math.min(profile.length - 1, Math.max(0, Math.round(km / maxD * (profile.length - 1))));
    return profile[i].ele;
  };
  aidStations.forEach(s => {
    if (s.km > maxD) return;
    const px = x(s.km);
    const py = y(eleAtKm(s.km));
    const color = s.principal ? '#e08a3a' : s.taller ? '#5cc2e8' : '#d9f24a';
    ctx.beginPath();
    ctx.arc(px, py, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#0b1210';
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  if (doneX > 0) {
    ctx.beginPath();
    ctx.moveTo(doneX, padT);
    ctx.lineTo(doneX, padT + h);
    ctx.strokeStyle = '#f3f6f2';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // la escala, en el hueco de arriba: de qué altura a qué altura, y cuántos km
  ctx.save();
  ctx.font = '700 11px system-ui, sans-serif';
  ctx.fillStyle = '#f4f7e6';
  ctx.shadowColor = 'rgba(0,0,0,0.85)';
  ctx.shadowBlur = 3;
  ctx.textBaseline = 'top';
  ctx.textAlign = 'right';        // a la derecha: a la izquierda, sobre el gráfico, van los botones del mapa
  ctx.fillText('Altura ' + Math.round(minEle) + '–' + Math.round(maxEle) + ' m · ruta ' + numKm(maxD) + ' km', cssW - padR - 4, 2);
  ctx.restore();
}

let anchoPerfil = 0;
window.addEventListener('resize', () => {
  const c = document.getElementById('elevation-chart');
  if (!c || c.clientWidth === anchoPerfil) return;      // solo si cambia el ancho
  anchoPerfil = c.clientWidth;
  drawElevationMarkers();
});

// ⚠️ Cada setData obliga a redibujar el mapa 3D entero. Se hacía 5 veces por
// segundo aunque la línea no cambiara: medido, la página trabajaba el 100 %
// del tiempo (batería y calor en el móvil de quien mira durante horas). La
// línea solo crece al pasar un vértice del trazado (cada ~57 m).
let idxRecorridoPintado = -1;
function drawTraveledLine(doneKm) {
  const idx = traveledIndex(doneKm / (factorKm || 1));
  if (idx === idxRecorridoPintado) return;
  const traveledPts = routeLatLon.slice(0, idx + 1);
  if (mapReady) {
    const src = map3d.getSource('traveled');
    if (src) {
      idxRecorridoPintado = idx;
      src.setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: traveledPts.map(p => [p[1], p[0]]) }
      });
      const cometa = map3d.getSource('cometa');
      if (cometa) {
        const desde = traveledIndex(Math.max(0, doneKm - 1) / (factorKm || 1));
        const cola = routeLatLon.slice(desde, idx + 1).map(p => [p[1], p[0]]);
        cometa.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: cola.length > 1 ? cola : [] } });
      }
    }
  }
}

// ---------- Corredor: posición extraída del enlace de iGPSPORT vía admin ----------
// (riderMarkerEl / riderMarkerPos se declaran arriba: rehacerMapa las usa)
riderMarkerPos = null;

function placeRiderMarker(lat, lon) {
  riderMarkerPos = [lat, lon];
  if (!mapReady) return;
  if (!riderMarkerEl) {
    const el = document.createElement('div');
    el.className = 'map3d-rider';
    // por encima de las chinchetas: si coincide con un avituallamiento, la
    // chincheta le tapaba la cara
    el.style.zIndex = '6';
    // ?v= para que el móvil no siga enseñando la foto cacheada
    const corredor = CARRERA.corredor || {};
    el.innerHTML = '<span><img src="rider.png?v=' + (Number(CARRERA.avatar_v) || 5) + '" alt="' + esc(corredor.nombre || 'Corredor') + '"></span>';
    // opacityWhenCovered: con terreno 3D MapLibre da por "tapado" todo lo que
    // está pegado al suelo y lo deja casi invisible al acercar. Aquí no
    // interesa: el corredor tiene que verse siempre.
    riderMarkerEl = new maplibregl.Marker({ element: el, opacityWhenCovered: '0.99' })
      .setLngLat([lon, lat])
      .setPopup(nuevoPopup(18).setHTML(
        '<div class="globo"><span class="globo-tipo">' + (corredor.dorsal ? 'Dorsal ' + esc(corredor.dorsal) : 'Corredor') + '</span>' +
        '<b>' + esc(corredor.nombre || '') + '</b><span class="globo-km">' + esc((CARRERA.bici || {}).modelo || '') + '</span></div>'))
      .addTo(map3d);
    pulsarAbrePopup(riderMarkerEl, el);
  } else {
    riderMarkerEl.setLngLat([lon, lat]);
  }
}


function ajustarTamanoCorredor() {
  if (!map3d) return;
  const z = map3d.getZoom();               // ~9 toda la ruta, ~16 pegado
  // mínimo 38 px: por debajo de eso la foto se pierde entre las chinchetas de
  // los avituallamientos y con el mapa entero en pantalla no se veía
  const px = Math.round(Math.max(38, Math.min(60, 38 + (z - 9) * 4)) / 4) * 4;
  // solo tocamos el DOM cuando cambia de verdad: escribir en cada fotograma
  // del zoom obligaba a recalcular estilos y se notaba el tirón en el móvil
  if (px === tamanoCorredorActual) return;
  tamanoCorredorActual = px;
  document.documentElement.style.setProperty('--corredor', px + 'px');
}

// Con 🎯 la cámara se queda siguiendo al corredor mientras avanza (antes
// centraba una vez y a los pocos minutos ya estaba fuera de la pantalla).
// Se deja de seguir en cuanto quien mira arrastra el mapa.
let siguiendo = false;
let ultimoSeguimiento = 0;
function marcarSiguiendo(si) {
  siguiendo = si;
  btnRecenter.classList.toggle('activo', si);
  btnRecenter.setAttribute('aria-pressed', si ? 'true' : 'false');
  const t = btnRecenter.querySelector('.t');
  if (t) t.textContent = si ? 'Siguiendo' : 'Seguir';
}

// Al abrir una carrera en directo la cámara ya va con el corredor, salvo que quien mira haya tocado el mapa antes:
// el botón sigue ahí para dejar de seguir (arrastrar el mapa) o volver a seguir.
let tocoElMapa = false, autoSeguido = false, volando = false;
map3dDiv.addEventListener('pointerdown', () => { tocoElMapa = true; }, { passive: true });
map3dDiv.addEventListener('wheel', () => { tocoElMapa = true; }, { passive: true });
// La cámara recorre la ruta (de la salida al corredor, en unos 3 s) y acaba con él. Si quien mira toca el mapa, se corta.
function vueloEntrada(kmFin) {
  volando = true;
  const f = factorKm || 1, dur = 3400;
  const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  let rumbo = map3d.getBearing();
  const llegar = () => {
    volando = false;
    marcarSiguiendo(true);
    ultimoSeguimiento = performance.now() + 900;
    if (riderMarkerPos) map3d.easeTo({ center: [riderMarkerPos[1], riderMarkerPos[0]], zoom: 14, pitch: vista3d ? 55 : 0, duration: 900 });
  };
  const salida = pointAtKm(0);
  map3d.easeTo({ center: [salida[1], salida[0]], zoom: 13, pitch: vista3d ? 60 : 0, duration: 700 });
  const t0 = performance.now() + 750;
  const paso = ahora => {
    if (tocoElMapa) { volando = false; return; }
    const t = Math.max(0, Math.min(1, (ahora - t0) / dur));
    const km = kmFin * ease(t);
    const p = pointAtKm(km / f), q = pointAtKm(Math.min(kmFin, km + 0.4) / f);
    if (p && q) {
      const rad = Math.PI / 180, dl = (q[1] - p[1]) * rad;
      const y = Math.sin(dl) * Math.cos(q[0] * rad);
      const x = Math.cos(p[0] * rad) * Math.sin(q[0] * rad) - Math.sin(p[0] * rad) * Math.cos(q[0] * rad) * Math.cos(dl);
      const objetivo = (Math.atan2(y, x) / rad + 360) % 360;
      rumbo += (((objetivo - rumbo + 540) % 360) - 180) * 0.06;      // gira suave, sin latigazos
      if (t > 0) map3d.jumpTo({ center: [p[1], p[0]], bearing: rumbo, pitch: vista3d ? 60 : 0, zoom: 13 + t });
    }
    if (t < 1) requestAnimationFrame(paso); else llegar();
  };
  requestAnimationFrame(paso);
}

function autoSeguirDirecto() {
  if (autoSeguido || tocoElMapa || siguiendo || !mapReady || !riderMarkerPos) return;
  autoSeguido = true;
  if (!QUIETO && currentKm >= 1.5 && routeLatLon.length > 1 && map3dDiv.offsetParent !== null) { vueloEntrada(currentKm); return; }
  marcarSiguiendo(true);
  ultimoSeguimiento = performance.now() + 900;
  map3d.easeTo({ center: [riderMarkerPos[1], riderMarkerPos[0]], zoom: Math.max(map3d.getZoom(), 13.5), duration: QUIETO ? 0 : 900 });
}

function seguirCorredor(pos) {
  if (volando || !siguiendo || !mapReady || !pos) return;
  // si está haciendo zoom o girando con los dedos, no pelearse con su gesto
  if (map3d.isZooming() || map3d.isRotating()) return;
  // en el mismo fotograma que la foto: la foto queda quieta en pantalla y el mapa se desliza por debajo, sin los
  // tirones de un easeTo por segundo que se reiniciaba a mitad de camino
  if (performance.now() < ultimoSeguimiento) return;     // el botón 🎯 acaba de lanzar su propio viaje
  map3d.jumpTo({ center: [pos[1], pos[0]] });
}

function recenterOnRider() {
  if (!mapReady) return;
  if (riderMarkerPos) {
    marcarSiguiendo(true);
    ultimoSeguimiento = performance.now() + 600;
    map3d.easeTo({ center: [riderMarkerPos[1], riderMarkerPos[0]], zoom: Math.max(map3d.getZoom(), 14), duration: QUIETO ? 0 : 600 });
  } else if (routeBounds) {
    // sin corredor en pantalla, el botón devuelve la vista a la ruta entera
    map3d.fitBounds([[routeBounds[0], routeBounds[1]], [routeBounds[2], routeBounds[3]]],
      { padding: 30, pitch: vista3d ? 50 : 0, bearing: vista3d ? -20 : 0, duration: QUIETO ? 0 : 600 });
  }
}
btnRecenter.addEventListener('click', recenterOnRider);

// --- 2D / 3D ---------------------------------------------------------------
// El mapa es siempre el mismo (satélite + relieve); lo único que cambia es la
// inclinación: 0° se ve en plano (mejor para leer el trazado) y 50° en relieve.
const btnVista = document.getElementById('btn-vista');
let vista3d = true;
function pintarBotonVista() {
  btnVista.textContent = vista3d ? 'Ver en 2D' : 'Ver en 3D';
  btnVista.setAttribute('aria-label', vista3d ? 'Ver el mapa en 2D' : 'Ver el mapa en 3D');
}
pintarBotonVista();
btnVista.addEventListener('click', () => {
  vista3d = !vista3d;
  pintarBotonVista();
  if (!mapReady) return;
  map3d.easeTo({ pitch: vista3d ? 50 : 0, bearing: vista3d ? -20 : 0, duration: QUIETO ? 0 : 700 });
});

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: CARRERA.zona_horaria });
}

// Diferencia entre el reloj de quien mira y el del servidor. Sin esto, un
// móvil con la hora mal puesta enseñaba un cronómetro disparatado (o negativo)
// a todo el que abriera la web.
let desfaseReloj = 0;
function ahoraServidor() { return Date.now() - desfaseReloj; }

// ---------- Sin cobertura: por dónde irá y a qué hora llega ----------------
// Con el ritmo medio desde la salida hasta el último dato (paradas incluidas:
// mejor un poco prudente que prometer de más). Sin datos nuevos, una marca
// transparente avanza por la ruta a ese ritmo; al volver la cobertura llegan
// los puntos guardados en el móvil y manda otra vez la posición real.
let fantasmaEl = null;
function previsiones(km, datoIso) {
  if (!lastStartedAt || !datoIso || !totalRouteKm || km == null || km < 1) return null;
  const t = new Date(datoIso).getTime();
  const v = km / ((t - new Date(lastStartedAt)) / 3600000);       // km/h
  if (!(v > 0.5 && v < 80)) return null;
  const est = Math.min(totalRouteKm, km + v * Math.max(0, ahoraServidor() - t) / 3600000);
  // nunca una hora ya pasada: sin cobertura cerca del final marcaba «Meta ~11:21» a las 11:30
  const hora = k => fmtTime(new Date(Math.max(ahoraServidor(), t + (k - km) / v * 3600000)).toISOString());
  const prox = aidStations.find(a => a.km > est + 0.1 && a.km < totalRouteKm - 0.2);
  return { est, prox, horaProx: prox && hora(prox.km), horaMeta: hora(totalRouteKm), hora };
}

// ---------- avituallamientos: por cuáles ha pasado (y a qué hora) y a qué hora se le espera en los siguientes ----------
function pintarListaAvit(data, km, haArrancado, enMeta) {
  const ul = document.getElementById('lista-avit-cd');
  if (!ul) return;
  const salida = lastStartedAt ? new Date(lastStartedAt).getTime() / 1000 : NaN;
  const kt = Array.isArray(data.km_t) ? data.km_t : [];
  // hora a la que cruzó un km cualquiera: entre los dos km enteros que el servidor apunta
  const tEn = k => {
    const a = Math.floor(k), b = Math.ceil(k), ta = a === 0 ? salida : kt[a - 1], tb = kt[b - 1];
    if (!Number.isFinite(tb)) return Number.isFinite(ta) && a === b ? ta : NaN;
    return Number.isFinite(ta) && a !== b ? ta + (tb - ta) * (k - a) : tb;
  };
  const pr = haArrancado && !enMeta ? previsiones(km, data.data_at) : null;
  const metaEsAvit = !!totalRouteKm && aidStations.length > 0 && aidStations[aidStations.length - 1].km >= totalRouteKm - 0.2;
  const filas = aidStations.map((a, i) => ({ n: (i + 1) + ' · ' + a.name, km: a.km, meta: metaEsAvit && i === aidStations.length - 1,
    sub: 'km ' + num(a.km) + (a.principal ? ' · principal' : a.taller ? ' · asistencia mecánica' : '') }));
  if (totalRouteKm && !metaEsAvit) filas.push({ n: 'Meta', km: totalRouteKm, sub: 'km ' + num(totalRouteKm), meta: true });
  ul.hidden = !filas.length;
  ul.textContent = '';
  filas.forEach(f => {
    const li = document.createElement('li');
    const izq = document.createElement('span'), sub = document.createElement('small');
    izq.textContent = f.n; sub.textContent = f.sub; izq.append(document.createElement('br'), sub);
    const der = document.createElement('span');
    if (f.meta && enMeta && data.finished_at) {
      der.textContent = 'Llegó ' + fmtTime(data.finished_at); der.className = 'hecho';
    } else if (haArrancado && km != null && km >= f.km - 0.05) {
      const t = tEn(f.km);
      der.textContent = Number.isFinite(t) ? 'Pasó ' + fmtTime(new Date(t * 1000).toISOString()) : 'Pasó'; der.className = 'hecho';
    } else if (pr) {
      der.textContent = '~' + pr.hora(f.km);
    }
    li.append(izq, der); ul.append(li);
  });
}

// ---------- tarjeta de ritmo: ritmo medio, llegada prevista y ritmo de cada km ----------
const mmss = s => { s = Math.round(s); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
function pintarRitmo(data, km, haArrancado, enMeta) {
  const caja = document.getElementById('ritmo');
  if (!caja) return;
  const t = data.data_at ? new Date(data.data_at).getTime() : NaN;
  const salida = lastStartedAt ? new Date(lastStartedAt).getTime() : NaN;
  if (!haArrancado || !(km >= 1) || !isFinite(t) || !isFinite(salida) || t <= salida) { caja.hidden = true; return; }
  const sKm = (t - salida) / 1000 / km;                       // segundos por km, con las paradas incluidas
  if (!(sKm > 120 && sKm < 3600)) { caja.hidden = true; return; }
  caja.hidden = false;
  ponerTexto('r-ritmo', mmss(sKm) + ' /km');
  const pr = enMeta ? null : previsiones(km, data.data_at);
  ponerTexto('r-llegada', enMeta ? 'En meta' : pr ? pr.horaMeta : '—');
  let nota = '';
  if (pr && totalRouteKm) {
    const margen = Math.max(2, Math.ceil(Math.max(0, totalRouteKm - km) * sKm / 60 * 0.1));
    nota = 'Si mantiene este ritmo · margen aprox. ±' + margen + ' min';
  }
  ponerTexto('r-nota', nota);
  // ritmo de cada km completo (el servidor apunta a qué hora se cruza cada uno)
  const kt = (Array.isArray(data.km_t) ? data.km_t : []).filter(Number.isFinite);
  const parciales = kt.map((v, i) => v - (i ? kt[i - 1] : salida / 1000)).filter(s => s > 60 && s < 7200).slice(-12);
  const cont = document.getElementById('r-barras'), pie = document.getElementById('r-pie');
  if (parciales.length < 2) { cont.hidden = true; pie.hidden = true; return; }
  const max = Math.max(...parciales), min = Math.min(...parciales);
  const firma = parciales.join(',');
  if (cont.dataset.f !== firma) {
    cont.dataset.f = firma;
    cont.textContent = '';
    parciales.forEach((s, i) => {
      const col = document.createElement('div'); col.className = 'col' + (i === parciales.length - 1 ? ' ultimo' : '');
      const barra = document.createElement('i'); barra.style.height = Math.max(15, 25 + 70 * (s - 0.5 * max) / (0.5 * max)) + '%';   // proporcional: 4 s de diferencia no parecen un mundo
      const et = document.createElement('em'); et.textContent = mmss(s);
      col.title = mmss(s) + ' /km';
      col.append(barra, et); cont.append(col);
    });
  }
  cont.setAttribute('aria-label', 'Ritmo de cada kilómetro: el último ' + mmss(parciales[parciales.length - 1]) +
    ', el mejor ' + mmss(min) + ' y el más lento ' + mmss(max));
  cont.hidden = false; pie.hidden = false;
}

function pintarFantasma(km) {
  const p = km != null && mapReady ? pointAtKm(km / (factorKm || 1)) : null;
  if (!p) {
    if (fantasmaEl) { fantasmaEl.remove(); fantasmaEl = null; }
    return;
  }
  if (!fantasmaEl) {
    const el = document.createElement('div');
    el.className = 'map3d-fantasma';
    el.title = 'Posición estimada (sin cobertura)';
    fantasmaEl = new maplibregl.Marker({ element: el, opacityWhenCovered: '0.99' }).setLngLat([p[1], p[0]]).addTo(map3d);
  } else {
    fantasmaEl.setLngLat([p[1], p[0]]);
  }
}

function fmtElapsedSince(iso) {
  const s = Math.floor((ahoraServidor() - new Date(iso).getTime()) / 1000);
  if (s < 0) return '00:00';
  const hh = String(Math.floor(s / 3600)).padStart(2, '0');
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return hh === '00' ? mm + ':' + ss : hh + ':' + mm + ':' + ss;
}

let lastStartedAt = null;

// ---------- Movimiento fluido ----------------------------------------------
// Los datos llegan a tirones (el servidor pregunta al ciclocomputador cada pocos
// segundos), así que pintar la posición en crudo daba saltos. Aquí se
// interpola entre el punto anterior y el nuevo: la foto se desliza y el
// trazado y el perfil crecen poco a poco.
// dura casi lo mismo que el intervalo de consulta (10 s): así la foto no
// pega un tirón y se para, sino que va andando todo el rato
// ⚠️ Antes duraba 9,5 s fijos, pero el servidor trae un dato cada 15 s: la
// foto andaba 9,5 s y se quedaba quieta 5,5, a tirones. Ahora la duración es
// el tiempo real entre datos (sacado de data_at del servidor), un poco más
// largo para que nunca llegue a pararse antes del siguiente.
let intervaloDatos = 15000;
let ultimoDataAt = null;
let kmPintado = null;
let posPintada = null;
let animacion = null;
let ultimoRepintadoPesado = 0;
let objetivo = null;        // [km, lat, lon] hacia donde va la animación
// ⚠️ Tras un hueco sin cobertura el punto nuevo llega lejos, y la foto
// tardaba hasta 33 s en arrastrarse hasta él: parecía que la web no se
// enteraba. Tras un hueco se pone al día en 2,5 s.
let ponerseAlDia = false;

// el estado de un vistazo, arriba: en directo, en la salida, sin cobertura, en meta
function pildora(texto, clase) {
  const p = document.getElementById('pill-estado');
  if (!p) return;
  p.hidden = !texto;
  if (p.textContent !== texto) p.textContent = texto;
  p.className = 'pill-estado ' + (clase || '');
}

function ponerTexto(id, texto) {
  const el = document.getElementById(id);
  if (el && el.textContent !== texto) el.textContent = texto;
}

function pintarProgreso(km, pos) {
  currentKm = km;
  ponerTexto('m-dist', num(km));
  ponerTexto('m-left', num(Math.max(0, totalRouteKm - km)));
  const barra = document.getElementById('progreso-barra');
  if (barra && totalRouteKm) barra.style.width = Math.min(100, km / totalRouteKm * 100).toFixed(1) + '%';
  if (pos) placeRiderMarker(pos[0], pos[1]);
  seguirCorredor(pos);
  // la línea recorrida y el perfil son caros de repintar (miles de puntos):
  // la foto va a 60 fps, esto a 5 veces por segundo, que no se nota
  const ahora = performance.now();
  if (ahora - ultimoRepintadoPesado > 200) {
    ultimoRepintadoPesado = ahora;
    const grad = pendienteEn(km);
    if (document.getElementById('m-grad').textContent !== grad) {
      ponerTexto('m-grad', grad);
      pintarNivel(grad);
    }
    drawTraveledLine(km);
    perfilSiCambia(km);
  }
}

// Si el corredor está sobre el trazado, la foto avanza POR el trazado
// (punto del km que toca) en vez de en línea recta entre dos lecturas del
// GPS: entre dos datos hay ~100 m y en las curvas y zetas se salía del
// camino. Si está lejos de la ruta (se ha desviado), va a su posición real.
function posicionEn(km, p0, p1, e, pegado) {
  if (pegado && routeLatLon.length) return pointAtKm(km / (factorKm || 1));
  if (p0 && p1) return [p0[0] + (p1[0] - p0[0]) * e, p0[1] + (p1[1] - p0[1]) * e];
  return p1 || p0;
}

function moverSuave(km, pos, pegado) {
  // ⚠️ Cada consulta volvía a arrancar la animación hacia el MISMO destino
  // aunque el dato no hubiera cambiado: la foto frenaba al final de cada
  // tramo. Si el destino es el mismo, se deja seguir la que ya va.
  const nuevo = [km, pos ? pos[0] : null, pos ? pos[1] : null];
  if (objetivo && objetivo.every((v, i) => v === nuevo[i])) return;
  objetivo = nuevo;

  const km0 = kmPintado, p0 = posPintada;
  // primera vez: colocar directo, no hay desde dónde moverse
  if (km0 === null) {
    if (animacion) cancelAnimationFrame(animacion);
    animacion = null;
    kmPintado = km; posPintada = posicionEn(km, null, pos, 1, pegado);
    ultimoRepintadoPesado = 0;
    pintarProgreso(km, posPintada);
    return;
  }
  // un salto grande (recarga, simulación acelerada, cambio de enlace) se
  // recorre deprisa en vez de plantarse de golpe
  const salto = Math.abs(km - km0);
  const duracion = QUIETO ? 1 : salto > 8 ? 1500
    : (ponerseAlDia || salto > 0.6) ? 2500
    : intervaloDatos * 1.1;
  ponerseAlDia = false;
  if (animacion) cancelAnimationFrame(animacion);
  const t0 = performance.now();
  let ultimoFotograma = 0;
  const paso = ahora => {
    const t = Math.min(1, (ahora - t0) / duracion);
    // a ritmo de bici la foto avanza unos pocos píxeles por segundo: con 20
    // fotogramas por segundo se ve igual de suave y el móvil recompone la
    // pantalla un tercio de veces (batería durante toda la carrera)
    if (t < 1 && ahora - ultimoFotograma < 33 && duracion > 2000) {
      animacion = requestAnimationFrame(paso);
      return;
    }
    ultimoFotograma = ahora;
    const e = t;   // a ritmo constante: si se acelera y frena, se nota raro
    kmPintado = km0 + (km - km0) * e;
    posPintada = posicionEn(kmPintado, p0, pos, e, pegado);
    pintarProgreso(kmPintado, posPintada);
    animacion = t < 1 ? requestAnimationFrame(paso) : null;
  };
  animacion = requestAnimationFrame(paso);
}

// ---------- Llegada a meta --------------------------------------------------
// La distancia del GPS nunca cuadra al metro con la del GPX (el trazado mide
// 103,4 km y la guía dice 101), así que "ha llegado" no puede depender de un
// número exacto. Se da por terminada si pasa CUALQUIERA de estas:
//   · está a menos de 200 m del punto de meta y ya lleva más de 80 km
//   · le faltan menos de 400 m de trazado
//   · el panel admin marcó "Finalizada"
// Al terminar, el cronómetro se congela con el tiempo del último dato recibido
// (no con la hora actual) y la velocidad "ahora" pasa a 0: si no, el reloj
// seguía corriendo en meta y la velocidad se quedaba clavada en el último valor.
let enMeta = false;
let haArrancado = false;

// Odegaard12 enciende el GPS en la salida sobre las 08:15, pero la carrera sale a
// las 08:30. Hasta que no son las 08:30 Y no se ha separado 40 m de la línea
// de salida, no se enseña ningún dato: el reloj a cero y las casillas fuera.
const METROS_PARA_ARRANCAR = 0.04;

function yaArrancado(data, km) {
  if (!lastStartedAt) return false;
  const yaEsLaHora = ahoraServidor() >= new Date(lastStartedAt).getTime();
  const salida = routeLatLon[0];
  let lejos = (km || 0) > METROS_PARA_ARRANCAR;
  if (salida && data.lat != null && data.lon != null) {
    lejos = haversineKm([data.lat, data.lon], salida) > METROS_PARA_ARRANCAR;
  }
  // Si ya lleva más de 1 km hecho, está claramente en carrera aunque la hora
  // no cuadre (hora de salida mal puesta, salida adelantada...).
  if ((km || 0) > 1) return true;
  return yaEsLaHora && lejos;
}

function verCasilla(nombre, visible) {
  document.querySelectorAll('[data-tile="' + nombre + '"]').forEach(e => { e.hidden = !visible; });
}

// nivel de burbuja de la pendiente: -15% a la izquierda, +15% a la derecha
function pintarNivel(texto) {
  const marca = document.getElementById('nivel-marca');
  if (!marca) return;
  const n = parseFloat(String(texto).replace('%', '').replace(',', '.'));
  const pct = isNaN(n) ? 50 : Math.max(0, Math.min(100, 50 + (n / 15) * 50));
  marca.style.left = pct + '%';
  const hueco = document.getElementById('m-grad');
  // el color de la rampa, aclarado: las bajadas (azul oscuro) no se leían sobre el fondo
  const aclarar = c => c.replace(/[0-9a-f]{2}/gi, h => Math.round(parseInt(h, 16) + (255 - parseInt(h, 16)) * 0.45).toString(16).padStart(2, '0'));
  if (hueco) hueco.style.color = isNaN(n) ? '' : aclarar(gradColor(n));
}

function esMeta(data, km) {
  // la llegada la apunta el servidor una vez y ya no se desdice
  if (data.finished_at || data.status_label === 'Finalizada') return true;
  if (!totalRouteKm || km == null || km < kmMinimosMeta()) return false;
  if (km >= totalRouteKm - 0.4) return true;
  const meta = routeLatLon[routeLatLon.length - 1];
  if (meta && data.lat != null && data.lon != null) {
    return haversineKm([data.lat, data.lon], meta) < 0.2;
  }
  return false;
}

function fmtFinal(ms) {
  // hacia abajo, como el resultado final: si no, 11h 43m en directo y
  // 11h 42m al cargar resultado.json
  const m = Math.max(0, Math.floor(ms / 60000));
  return Math.floor(m / 60) + 'h ' + String(m % 60).padStart(2, '0') + 'm';
}

function fmtDuracion(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const hh = String(Math.floor(s / 3600)).padStart(2, '0');
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return hh === '00' ? mm + ':' + ss : hh + ':' + mm + ':' + ss;
}

// ---------- Conexión de quien mira --------------------------------------
// ⚠️ Con mala cobertura una petición podía quedarse colgada un minuto y, como
// se pregunta cada 5 s, se amontonaban varias a la vez (peor aún la red). Y
// si la Pi o el túnel caían, Cloudflare devuelve una página de error: la web
// fallaba al leerla y se callaba, sin avisar de que no llegaban datos.
let pidiendo = false, pidiendoDesde = 0;
let llegadaFija = null;     // primer «en meta» sin hora del servidor: el tiempo final no sigue creciendo
let fallosSeguidos = 0;

function fetchConTiempo(url, ms = 8000) {
  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), ms);
  return fetch(url, { signal: control.signal, cache: 'no-store' }).finally(() => clearTimeout(reloj));
}

let desdeCache = 0, yaPintado = false, ultimoLiveOk = 0;
const CLAVE_LIVE = 'sigueme.live';
function guardarLive(txt) {
  ultimoLiveOk = Date.now();
  try { localStorage.setItem(CLAVE_LIVE, JSON.stringify({ t: ultimoLiveOk, d: txt })); } catch (e) {}
}
function liveGuardado() {
  try {
    const g = JSON.parse(localStorage.getItem(CLAVE_LIVE));
    if (g && g.d && Date.now() - g.t < 12 * 3600000) return g;      // de más de 12 h ya no vale
  } catch (e) {}
  return null;
}
function haceTxt(t) {
  const m = Math.max(1, Math.round((Date.now() - t) / 60000));
  return m < 60 ? m + ' min' : Math.floor(m / 60) + ' h ' + String(m % 60).padStart(2, '0') + ' min';
}

// «modo sin cobertura» (carrera.json: modo_offline, casilla del panel). Desactivado = lo de siempre: SIN service worker y
// el que hubiera quedado de versiones antiguas se desinstala (tres versiones antiguas acabaron sirviendo código viejo).
function gestionarSW() {
  if (!('serviceWorker' in navigator) || ARCHIVADA) return;
  if (CARRERA.modo_offline === true) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  } else {
    navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => { if (!r.scope.endsWith('/avisos/')) r.unregister(); })).catch(() => {});
    if (window.caches) caches.keys().then(ks => ks.forEach(k => caches.delete(k))).catch(() => {});
  }
}

let avisoVisto = false, avisoTimer = 0;
function avisoConexion(mal) {
  let el = document.getElementById('aviso-conexion');
  if (!el) {
    el = document.createElement('div');
    el.id = 'aviso-conexion';
    el.className = 'aviso-conexion';
    el.setAttribute('role', 'status');
    document.body.appendChild(el);
  }
  clearTimeout(avisoTimer);
  if (mal) {
    const t = ultimoLiveOk || (liveGuardado() || {}).t;
    el.textContent = (navigator.onLine === false ? 'Sin conexión' : 'No llegan datos') +
      (t ? ' · último dato hace ' + haceTxt(t) : '') + ' · reintentando…';
    el.classList.remove('ok');
    el.classList.add('visible');
    avisoVisto = true;
  } else if (avisoVisto) {                       // volvió la red: se avisa un momento y se va solo
    el.textContent = 'Conexión recuperada ✓';
    el.classList.add('ok', 'visible');
    avisoVisto = false;
    avisoTimer = setTimeout(() => el.classList.remove('visible'), 3500);
  } else {
    el.classList.remove('visible');
  }
}

function pollLive() {
  // hasta saber si hay resultado guardado no se pinta nada: si no, salía un
  // instante "INICIO 08:30 · SÁBADO 26/09" y luego cambiaba todo
  if (!resultadoConsultado) return;
  // la anterior aún no ha vuelto: no amontonar (pero si lleva 20 s, se da por perdida)
  if (pidiendo && Date.now() - pidiendoDesde < 20000) return;
  pidiendo = true;
  pidiendoDesde = Date.now();
  // tramos de 3 s: quien mira a la vez comparte la misma copia en la caché del borde
  precargado('live.json', () => fetchConTiempo('live.json?_=' + Math.floor(Date.now() / 3000)))
    .then(r => {
      if (!r || !r.ok) throw new Error('HTTP ' + (r ? r.status : 'sin respuesta'));
      // la hora del servidor sale de la cabecera Date de la respuesta, no de
      // "updated": si el servidor llevaba minutos sin escribir (sin señal),
      // el cronómetro de quien miraba se atrasaba esos mismos minutos
      const fecha = Date.parse(r.headers.get('Date'));
      if (!isNaN(fecha)) desfaseReloj = Date.now() - fecha;
      return r.text().then(txt => { const d = JSON.parse(txt); guardarLive(txt); desdeCache = 0; return d; });
    })
    .catch(err => {
      // sin red al abrir la web (un túnel, el avión): se pinta el último estado guardado en este móvil
      const g = yaPintado ? null : liveGuardado();
      if (!g) throw err;
      desdeCache = g.t;
      return JSON.parse(g.d);
    })
    .then(data => {
      yaPintado = true;
      fallosSeguidos = desdeCache ? 2 : 0;
      avisoConexion(!!desdeCache);
      lastStartedAt = data.started_at || null;
      document.querySelector('.metricas').classList.remove('esqueleto');

      // sin carrera en marcha y con resultado guardado: se enseña el resultado
      if (resultado && !data.started_at && !data.livetrack_url && !data.en_seguimiento) {
        if (!repitiendo) pintarResultado();
        pildora('Resultado', 'meta');
        ritmoSondeo(60000);
        return;
      }
      ritmoSondeo(5000);
      verCasilla('speed-total', false);
      ponerTexto('m-speed-avg-txt', 'km/h media');
      document.getElementById('resultado').hidden = true;
      document.getElementById('aviso-resultado').hidden = true;
      ponerTexto('sec-ahora', 'Ahora');

      let doneKm = data.dist_km;
      // ⚠️ Al abrir la web a mitad de carrera, la distancia del ciclocomputador sirve
      // SOLO para desempatar en la salida/meta (la ruta es circular), NUNCA
      // como mínimo: esa distancia incluye lo rodado antes de salir y el
      // error del GPS, y con 2 km de más quien abría la web en el km 100,5
      // ya le veía "En meta". La marca dura hasta la primera proyección de
      // verdad: el primer poll suele llegar antes que la ruta y, si se
      // perdía ahí, en el siguiente la distancia del GPS volvía a ser suelo.
      if (!ultimoKmConocido && data.dist_km) { ultimoKmConocido = data.dist_km; anclaDelGps = true; }
      let proyectado = false;
      let lejosDeRuta = Infinity;
      if (data.lat != null && data.lon != null && routeLatLon.length) {
        const pr = projectOntoRoute(data.lat, data.lon);
        doneKm = pr.alongKm * factorKm;
        lejosDeRuta = pr.distKm;
        proyectado = true;
      }
      if (data.data_at && data.data_at !== ultimoDataAt) {
        if (ultimoDataAt) {
          const dt = new Date(data.data_at) - new Date(ultimoDataAt);
          // un hueco (sin cobertura) no es el ritmo normal de los datos
          if (dt > 45000) ponerseAlDia = true;
          else if (dt > 0) intervaloDatos = Math.min(30000, Math.max(5000, dt));
        }
        ultimoDataAt = data.data_at;
      }
      if (doneKm != null && totalRouteKm) {
        doneKm = Math.min(doneKm, totalRouteKm);
        if (!anclaDelGps && doneKm < ultimoKmConocido - 0.5) doneKm = ultimoKmConocido;
        ultimoKmConocido = doneKm;
        if (proyectado) anclaDelGps = false;
      }

      enMeta = esMeta(data, doneKm);
      haArrancado = enMeta || yaArrancado(data, doneKm);

      // qué se enseña en cada momento: antes de salir, nada; en meta,
      // desaparece lo instantáneo (velocidad ahora, pulso, pendiente) y se
      // quedan fijos los totales
      // ⚠️ Si iGPSPORT se calla (su directo muere, o solo va Traccar), el
      // pulso y la cadencia se quedaban clavados en el último valor durante
      // horas. A los 3 min sin datos nuevos se ocultan; las casillas sin
      // dato tampoco se enseñan (con solo Traccar no hay medias).
      const vivo = iso => !!iso && ahoraServidor() - new Date(iso) < 180000;
      // pulso de iGPSPORT o del reloj (miniapp de Amazfit, hr_at)
      const sensoresVivos = vivo(data.igpsport_at) || vivo(data.hr_at);
      const posicionViva = vivo(data.data_at || data.updated);
      verCasilla('speed', haArrancado && !enMeta);
      verCasilla('grad', haArrancado && !enMeta);
      verCasilla('hr', haArrancado && !enMeta && sensoresVivos && data.hr != null);
      verCasilla('cad', haArrancado && data.cadence_avg != null);
      verCasilla('hr-avg', haArrancado && data.hr_avg != null);
      verCasilla('speed-avg', haArrancado && data.speed_kmh_avg != null);
      ['dist', 'time'].forEach(n => verCasilla(n, haArrancado));
      verCasilla('left', haArrancado && !enMeta);
      document.querySelector('.metricas').classList.toggle('sin-datos', !haArrancado);

      // velocidad "ahora" de hace más de 3 min no es "ahora"
      ponerTexto('m-speed', enMeta ? '0' : posicionViva ? num(data.speed_kmh) : '—');
      ponerTexto('m-speed-avg', num(data.speed_kmh_avg));
      ponerTexto('m-hr', enMeta ? '—' : entero(data.hr));
      ponerTexto('m-hr-avg', entero(data.hr_avg));
      ponerTexto('m-cad-avg', entero(data.cadence_avg));

      // último dato NUEVO del ciclocomputador (updated se renueva en cada consulta)
      const ultimoDato = data.data_at || data.updated;
      if (!enMeta) llegadaFija = null;
      const llegada = data.finished_at || llegadaFija || (enMeta ? (llegadaFija = ultimoDato) : ultimoDato);
      if (enMeta && lastStartedAt && llegada) {
        // tiempo final = del pistoletazo a la llegada (o al último dato)
        document.getElementById('m-time').textContent =
          fmtFinal(new Date(llegada) - new Date(lastStartedAt));
      } else if (!haArrancado) {
        document.getElementById('m-time').textContent = '—';
      } else {
        document.getElementById('m-time').textContent =
          lastStartedAt ? fmtElapsedSince(lastStartedAt) : (data.elapsed || '—');
      }

      if (doneKm != null && totalRouteKm && haArrancado) {
        moverSuave(enMeta ? totalRouteKm : doneKm,
                   data.lat != null && data.lon != null ? [data.lat, data.lon] : null,
                   enMeta || lejosDeRuta < 0.08);
      } else if (!data.started_at && kmPintado !== null && kmPintado !== 0) {
        // se reseteó desde el panel: borrar también lo ya pintado en las
        // pantallas que estuvieran abiertas, o se quedan con el progreso
        if (animacion) cancelAnimationFrame(animacion);
        animacion = null;
        kmPintado = 0; posPintada = null; currentKm = 0; ultimoKmConocido = 0;
        objetivo = null; ultimoDataAt = null; anclaDelGps = false;
        idxRecorridoPintado = -1; pixelPerfilPintado = null;
        document.getElementById('m-dist').textContent = '—';
        document.getElementById('m-left').textContent = '—';
        document.getElementById('m-grad').textContent = '—';
        drawTraveledLine(0);
        drawElevationMarkers();
      }

      // renglón de estado bajo las métricas
      const estado = document.getElementById('estado-carrera');
      if (enMeta) {
        estado.classList.remove('previo');
        ponerTexto('estado-carrera', 'En meta · tiempo final ' +
          document.getElementById('m-time').textContent);
        estado.classList.add('meta');
      } else {
        estado.classList.remove('meta');
        estado.classList.remove('previo');
        const hora = lastStartedAt ? fmtTime(lastStartedAt) : CARRERA.hora_salida;
        if (data.lat != null && !haArrancado) {
          // ya está compartiendo y se le ve en el mapa, pero aún no ha salido
          const quien = (CARRERA.corredor || {}).nombre;
          ponerTexto('estado-carrera', 'Sale a las ' + hora + ' · ' + (quien ? quien + ' ya está' : 'ya está') + ' en la salida');
          estado.classList.add('previo');
        } else if (!haArrancado) {
          ponerTexto('estado-carrera', 'Sale a las ' + hora + (diaCarrera() ? ' · ' + diaCarrera() : '') + ' · esta página se actualiza sola');
          estado.classList.add('previo');
        } else {
          const pr = previsiones(doneKm, data.data_at);
          ponerTexto('estado-carrera', pr ? (pr.prox ? 'Próximo avituallamiento: ' + pr.prox.name + ' (km ' + num(pr.prox.km) + ') ~' + pr.horaProx + ' · ' : '') +
            'Meta ~' + pr.horaMeta : '');
        }
      }

      pintarRitmo(data, doneKm, haArrancado, enMeta);
      pintarListaAvit(data, doneKm, haArrancado, enMeta);
      { const vacio = document.getElementById('ritmo-vacio'), cr = document.getElementById('ritmo'); if (vacio && cr) vacio.hidden = !cr.hidden; }

      // pie de estado: en meta, sin señal o la hora del último dato
      const pie = document.getElementById('live-updated');
      const hueco = ultimoDato ? (ahoraServidor() - new Date(ultimoDato)) : 0;
      {
        const pr = haArrancado && !enMeta && hueco > 240000 && data.status_label === 'En carrera'
          ? previsiones(doneKm, data.data_at) : null;
        if (enMeta) pildora('En meta', 'meta');
        else if (data.status_label !== 'En carrera') {
          // carrera preparada para hoy o más adelante: que se vea que va a haber directo
          const hoy = new Date().toLocaleDateString('sv-SE', { timeZone: CARRERA.zona_horaria });
          pildora(CARRERA.fecha && CARRERA.fecha >= hoy ? 'Antes de salir' : '', 'previo');
        }
        else if (!haArrancado) pildora(data.lat != null ? 'En la salida' : 'Antes de salir', 'previo');
        else if (hueco > 240000) pildora('Sin cobertura', 'sin');
        else { pildora('En directo', 'vivo'); autoSeguirDirecto(); }
        pintarFantasma(pr ? pr.est : null);
        if (pr) {
          pie.textContent = 'Sin cobertura desde las ' + fmtTime(ultimoDato) + ', en el km ' + num(doneKm) + '. ' +
            'A su ritmo estará ahora hacia el km ' + num(pr.est, 0) + ' (la marca transparente del mapa).';
        } else if (ultimoDato && hueco > 240000 && data.status_label === 'En carrera') {
          pie.textContent = 'Sin datos nuevos desde las ' + fmtTime(ultimoDato) +
            ' · parado o sin cobertura';
        } else if (ultimoDato && data.lat != null) {
          pie.textContent = 'Última actualización: ' + fmtTime(ultimoDato) +
            (data.fuente_posicion === 'movil' ? ' · GPS del móvil' : data.fuente_posicion === 'igpsport' ? ' · iGPSPORT' : '');
        } else {
          pie.textContent = '';
        }
      }

      if (data.lat != null && data.lon != null) {
        if (!haArrancado) placeRiderMarker(data.lat, data.lon);
        geoHint.textContent = '';
      } else if (!haArrancado) {
        if (riderMarkerEl) {
          riderMarkerEl.remove();
          riderMarkerEl = null;
          riderMarkerPos = null;
        }
        geoHint.textContent = data.status_label === 'En carrera'
          ? 'Buscando la posición del corredor…'
          : '';
      }
    })
    .catch(err => {
      // un fallo suelto (un túnel, un cambio de antena) no se avisa; dos
      // seguidos (~10 s sin datos) sí
      fallosSeguidos++;
      if (fallosSeguidos >= 2) avisoConexion(true);
      if (fallosSeguidos === 8 && ritmoActual === 5000) ritmoSondeo(15000);      // mucho rato sin red: menos batería
      if (!(err instanceof TypeError) && err.name !== 'AbortError' && !/^HTTP/.test(err.message)) {
        console.error('pollLive:', err);   // fallo del código, no de la red
      }
    })
    .finally(() => { pidiendo = false; });
}

// el tiempo transcurrido se refresca cada segundo aunque no llegue poll nuevo;
// en meta NO se toca, que si no el cronómetro seguía corriendo
setInterval(() => {
  if (enMeta) return;
  if (lastStartedAt) document.getElementById('m-time').textContent = fmtElapsedSince(lastStartedAt);
}, 1000);

// ---------- Resultado de la carrera ----------------------------------------
// resultado.json se genera con el FIT del ciclocomputador (tiempos, paso por cada
// avituallamiento y la traza real recortada a salida-meta).
let resultado = null;
let resultadoConsultado = false;
let repitiendo = false;
let kmsTraza = null;

const horaCarrera = iso => new Date(iso).toLocaleTimeString('es-ES',
  { hour: '2-digit', minute: '2-digit', timeZone: CARRERA.zona_horaria });
const fmtHM = s => Math.floor(s / 3600) + 'h ' + String(Math.floor(s % 3600 / 60)).padStart(2, '0') + 'm';

// km de ruta de cada punto de la traza, siempre hacia delante
function calcularKmsTraza() {
  if (kmsTraza || !resultado || !routeLatLon.length) return;
  let km = 0;
  kmsTraza = (resultado.traza || []).map(([la, lo]) => {
    let mejor = Infinity, mk = km;
    for (const tope of [8, Infinity]) {        // tras un hueco largo, sin tope por delante
      for (let j = 0; j < routeLatLon.length; j++) {
        if (routeCumKm[j] < km - 0.5 || routeCumKm[j] > km + tope) continue;
        const d = haversineKm([la, lo], routeLatLon[j]);
        if (d < mejor) { mejor = d; mk = routeCumKm[j]; }
      }
      if (mejor < 0.15) break;
    }
    if (mejor < 0.15) km = Math.max(km, mk);
    return Math.min(totalRouteKm, km * factorKm);
  });
}

// cabecera con lo REAL y, entre paréntesis, lo previsto (carrera.json)
function cabeceraReal(r) {
  const pon = (id, real, unidad, previsto) => {
    const b = document.getElementById(id);
    if (!b || real == null) return;
    b.textContent = real;
    b.dataset.real = '1';
    b.parentElement.lastChild.textContent = ' ' + unidad + (previsto ? ' de ' + previsto : '');   // como «2h 00m de 5 h»
  };
  pon('stat-dist', num(r.distancia_km), 'km', CARRERA.distancia_km ? numKm(CARRERA.distancia_km) : '');
  pon('stat-gain', r.desnivel_m != null ? Number(r.desnivel_m).toLocaleString('es-ES') : null, 'm+',
      CARRERA.desnivel_m ? Number(CARRERA.desnivel_m).toLocaleString('es-ES') : '');
}

function pintarResultado() {
  const r = resultado;
  ['speed', 'hr', 'grad', 'left'].forEach(n => verCasilla(n, false));
  ['dist', 'time', 'speed-avg'].forEach(n => verCasilla(n, true));
  // pulso y cadencia solo si el FIT los trae (si no, salían casillas con «—»)
  verCasilla('hr-avg', r.pulso_medio != null);
  verCasilla('cad', r.cadencia_media != null);
  const barra = document.getElementById('progreso-barra');
  if (barra) barra.style.width = '100%';
  document.querySelector('.metricas').classList.remove('sin-datos');
  ponerTexto('m-dist', num(r.distancia_km));
  ponerTexto('m-time', fmtHM(r.tiempo_oficial_s));
  ponerTexto('m-speed-avg', num(r.velocidad_media_mov));
  ponerTexto('m-speed-avg-txt', 'km/h en movimiento');
  if (r.tiempo_oficial_s) { ponerTexto('m-speed-total', num(r.distancia_km / (r.tiempo_oficial_s / 3600))); verCasilla('speed-total', true); }
  cabeceraReal(r);
  ponerTexto('m-hr-avg', entero(r.pulso_medio));
  ponerTexto('m-cad-avg', entero(r.cadencia_media));
  // el resultado va arriba, antes del mapa: era lo primero que había que ver
  // y quedaba debajo del mapa y la leyenda
  const estado = document.getElementById('estado-carrera');
  estado.classList.remove('previo', 'meta');
  estado.textContent = '';
  ponerTexto('aviso-titulo', 'Terminada en ' + fmtHM(r.tiempo_oficial_s));
  // corto a propósito: en el móvil pequeño partía en dos líneas (el "de 12 h"
  // ya sale en la cabecera)
  ponerTexto('aviso-sub', num(r.distancia_km) + ' km · llegada a las ' + horaCarrera(r.llegada));
  document.getElementById('aviso-resultado').hidden = false;
  ponerTexto('sec-ahora', 'Resultado');
  ponerTexto('stat-limite', fmtHM(r.tiempo_oficial_s));
  const etiqueta = document.querySelector('#stat-limite + i');
  if (etiqueta) etiqueta.textContent = 'de ' + CARRERA.limite_h + ' h';
  document.getElementById('live-updated').textContent =
    r.carrera + ' · datos del ciclocomputador · ' + fmtHM(r.tiempo_movimiento_s) + ' en movimiento';
  // mapa y perfil completos, la foto en meta
  if (totalRouteKm) {
    currentKm = totalRouteKm;
    idxRecorridoPintado = -1; pixelPerfilPintado = null;
    drawTraveledLine(totalRouteKm);
    drawElevationMarkers();
    const fin = (r.traza || [])[(r.traza || []).length - 1];
    if (fin) placeRiderMarker(fin[0], fin[1]);
  }
  const lista = document.getElementById('pasos');
  if (!lista.children.length) {
    const salida = new Date(r.salida);
    (r.pasos || []).forEach((p, i) => {
      const li = document.createElement('li');
      const trans = (new Date(p.hora) - salida) / 1000;
      li.innerHTML = '<span class="n">' + (i + 1) + '</span><span class="nombre"></span>' +
        '<span class="km">km ' + num(p.km) + ' · +' + fmtHM(trans) + '</span><span class="hora">' + horaCarrera(p.hora) + '</span>';
      li.children[1].textContent = p.nombre;   // el nombre como texto, no HTML
      lista.appendChild(li);
    });
  }
  // sin parciales (FIT sin pasos) no se enseña un título con nada debajo
  document.getElementById('resultado').hidden = !lista.children.length;
}

// Repetición: la carrera entera en 60 s, con la foto por la traza real
const DURACION_REPETICION = 60000;
function repetirCarrera() {
  const boton = document.getElementById('btn-repeticion');
  if (repitiendo) { repitiendo = false; return; }
  if (!resultado.traza || resultado.traza.length < 2) return;
  calcularKmsTraza();
  if (!kmsTraza) return;
  repitiendo = true;
  boton.innerHTML = '<span class="ico">■</span><span class="txt"> Parar</span>';
  boton.setAttribute('aria-label', 'Parar la repetición');
  const tr = resultado.traza, total = tr[tr.length - 1][2];
  const salida = new Date(resultado.salida).getTime();
  if (mapReady) {
    map3d.easeTo({ center: [tr[0][1], tr[0][0]], zoom: 12.5, duration: QUIETO ? 0 : 800 });
    marcarSiguiendo(true);
    ultimoSeguimiento = performance.now() + 800;
  }
  idxRecorridoPintado = -1; pixelPerfilPintado = null;
  const items = [...document.querySelectorAll('#pasos li')];
  const t0 = performance.now();
  let i = 0;
  const paso = ahora => {
    const fin = !repitiendo || ahora - t0 >= DURACION_REPETICION;
    const t = fin ? total : (ahora - t0) / DURACION_REPETICION * total;
    while (i < tr.length - 2 && tr[i + 1][2] <= t) i++;
    const a = tr[i], b = tr[i + 1] || a;
    const e = b[2] > a[2] ? Math.min(1, (t - a[2]) / (b[2] - a[2])) : 1;
    const km = kmsTraza[i] + ((kmsTraza[i + 1] ?? kmsTraza[i]) - kmsTraza[i]) * e;
    pintarProgreso(km, [a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e]);
    ponerTexto('m-time', fmtHM(t));
    const reloj = new Date(salida + t * 1000).toISOString();
    ponerTexto('aviso-titulo', '▶ ' + horaCarrera(reloj) + ' · km ' + num(km));
    const pasados = resultado.pasos.filter(p => new Date(p.hora).getTime() <= salida + t * 1000).length;
    items.forEach((li, k) => li.classList.toggle('actual', k === pasados - 1));
    if (!fin) { requestAnimationFrame(paso); return; }
    repitiendo = false;
    boton.innerHTML = '<span class="ico">▶</span><span class="txt"> Ver la carrera</span>';
    boton.setAttribute('aria-label', 'Ver la carrera en 1 minuto');
    items.forEach(li => li.classList.remove('actual'));
    marcarSiguiendo(false);
    if (mapReady && routeBounds) {
      map3d.fitBounds([[routeBounds[0], routeBounds[1]], [routeBounds[2], routeBounds[3]]],
        { padding: 30, pitch: vista3d ? 50 : 0, bearing: vista3d ? -20 : 0, duration: QUIETO ? 0 : 1200 });
    }
    pintarResultado();
  };
  requestAnimationFrame(paso);
}
document.getElementById('btn-repeticion').addEventListener('click', repetirCarrera);

precargado('resultado.json', () => fetchConTiempo('resultado.json?_=' + Date.now(), 8000).then(r => r.ok ? r.json() : null))
  .catch(() => null)
  .then(d => { resultado = d; resultadoConsultado = true; pollLive(); });

// ---------- ayuda de primera vez: un aviso corto, una sola vez en este navegador ----------
(function ayudaPrimeraVez() {
  const caja = document.getElementById('ayuda-cd'), ok = document.getElementById('ayuda-cd-ok');
  if (!caja || !ok) return;
  let vista = false;
  try { vista = localStorage.getItem('sigueme.ayuda') === '1'; } catch (e) {}
  if (!vista) caja.hidden = false;
  ok.addEventListener('click', () => {
    caja.hidden = true;
    try { localStorage.setItem('sigueme.ayuda', '1'); } catch (e) {}
    const b = document.getElementById('ayuda-btn'); if (b) b.focus({ preventScroll: true });
  });
  // el botón «?» de la cabecera: vuelve a enseñar el aviso cuando se quiera
  const btn = document.getElementById('ayuda-btn');
  if (btn) btn.addEventListener('click', () => {
    caja.hidden = false;
    caja.scrollIntoView({ behavior: QUIETO ? 'auto' : 'smooth', block: 'nearest' });
    ok.focus({ preventScroll: true });
  });
})();

// ---------- pestañas de la hoja de datos: Resumen · Ritmo · Avituallamientos (el mapa se ve siempre) ----------
(function pestanasMovil() {
  const nav = document.getElementById('pestanas-cd');
  if (!nav) return;
  const botones = [...nav.querySelectorAll('button')];
  const poner = (t, foco) => {
    document.body.dataset.tab = t;
    botones.forEach(b => { const si = b.dataset.tab === t; b.setAttribute('aria-selected', si ? 'true' : 'false'); b.tabIndex = si ? 0 : -1; if (si && foco) b.focus(); });
    try { sessionStorage.setItem('sigueme.tab', t); } catch (e) {}
  };
  botones.forEach((b, i) => {
    b.addEventListener('click', () => poner(b.dataset.tab, false));
    b.addEventListener('keydown', e => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (d) { e.preventDefault(); poner(botones[(i + d + botones.length) % botones.length].dataset.tab, true); }
    });
  });
  let inicial = 'resumen';
  try { inicial = sessionStorage.getItem('sigueme.tab') || 'resumen'; } catch (e) {}
  poner(botones.some(b => b.dataset.tab === inicial) ? inicial : 'resumen', false);
})();

// ---------- avisos en el móvil (Web Push): salida, avituallamientos y meta, aunque la web esté cerrada ----------
(function campanaAvisos() {
  const btn = document.getElementById('campana'), caja = document.getElementById('campana-ayuda');
  const txt = document.getElementById('campana-txt'), okb = document.getElementById('campana-ok');
  if (!btn || !caja || ARCHIVADA) return;
  const ios = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const instalada = navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;
  const puede = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const decir = t => { txt.textContent = t; caja.hidden = false; };
  okb.addEventListener('click', () => { caja.hidden = true; btn.focus({ preventScroll: true }); });
  const b64 = s => Uint8Array.from(atob((s + '='.repeat((4 - s.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
  const poner = si => {
    btn.setAttribute('aria-pressed', si ? 'true' : 'false'); btn.classList.toggle('activo', si);
    btn.title = si ? 'Avisos activados: toca para quitarlos' : 'Avisarme de la salida, los avituallamientos y la meta';
  };
  const post = (u, d) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
  let clave = null;
  fetch('/api/push/clave').then(r => r.ok ? r.json() : null).then(async d => {
    if (!d || !d.clave) return;                 // avisos sin montar en el servidor: sin campana
    clave = d.clave; btn.hidden = false;
    if (puede) {
      try { const reg = await navigator.serviceWorker.getRegistration('/avisos/'); poner(!!(reg && await reg.pushManager.getSubscription())); } catch (e) {}
    }
  }).catch(() => {});
  btn.addEventListener('click', async () => {
    if (!puede) {
      return decir(ios && !instalada
        ? 'En el iPhone los avisos llegan con la web instalada: toca Compartir → «Añadir a pantalla de inicio», abre Sígueme CC desde el icono y toca otra vez la campana.'
        : 'Este navegador no puede recibir avisos. Prueba con Chrome, Edge, Firefox o Safari al día.');
    }
    // Safari (iPhone) solo deja pedir permiso en el mismo toque: se pide ANTES de cualquier espera
    const activando = btn.getAttribute('aria-pressed') !== 'true';
    const permiso = activando && Notification.permission === 'default' ? Notification.requestPermission() : null;
    try {
      const reg = await navigator.serviceWorker.register('/sw-avisos.js', { scope: '/avisos/' });
      if (!reg.active) {
        const w = reg.installing || reg.waiting;
        if (w) await new Promise(ok => { const mira = () => { if (w.state === 'activated' || w.state === 'redundant') ok(); }; w.addEventListener('statechange', mira); mira(); });
      }
      const actual = await reg.pushManager.getSubscription();
      if (actual) {
        await post('/api/push/baja', { endpoint: actual.endpoint }).catch(() => {});
        await actual.unsubscribe(); poner(false);
        return decir('Avisos quitados. Puedes volver a activarlos con la campana.');
      }
      if ((permiso ? await permiso : Notification.permission) !== 'granted') {
        return decir('Sin permiso no te podemos avisar. Actívalo en los ajustes del navegador (en el iPhone: Ajustes → Notificaciones → Sígueme CC) y vuelve a tocar la campana.');
      }
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(clave) });
      const r = await post('/api/push/alta', sub.toJSON());
      if (!r.ok) { await sub.unsubscribe(); throw new Error('alta ' + r.status); }
      poner(true);
      decir('Listo: te avisaremos de la salida, de cada avituallamiento y de la llegada a meta, aunque tengas la web cerrada.');
    } catch (e) {
      console.warn('[avisos]', e && e.name, e && e.message);
      decir('No se pudieron activar los avisos. Comprueba la conexión y vuelve a intentarlo.');
    }
  });
})();

pollLive();
// con resultado (carrera terminada) basta con mirar cada minuto si empieza otra
ritmoSondeo(5000);
// al desbloquear el móvil o volver a la pestaña, datos al momento (antes había
// que esperar al siguiente turno, y en segundo plano el navegador los frena)
document.addEventListener('visibilitychange', () => { if (!document.hidden) pollLive(); });
window.addEventListener('online', pollLive);
window.addEventListener('offline', () => avisoConexion(true));
window.addEventListener('offline', () => avisoConexion(true));

// las cifras y el estado «laten» una vez cuando cambian: se nota que la web está viva (sin movimiento si el sistema lo pide).
// El crono, que cambia cada segundo, no late.
if (!QUIETO) {
  const vistos = new WeakMap();
  new MutationObserver(muts => {
    for (const m of muts) {
      const el = m.target.nodeType === 3 ? m.target.parentElement : m.target;
      const caja = el && el.closest && el.closest('.metrica, #pill-estado');
      if (!caja || caja.dataset.tile === 'time') continue;
      const t = caja.textContent;
      if (vistos.get(caja) === t) continue;
      if (vistos.has(caja)) { caja.classList.remove('cambia'); void caja.offsetWidth; caja.classList.add('cambia'); }
      vistos.set(caja, t);
    }
  }).observe(document.body, { childList: true, characterData: true, subtree: true });
}
