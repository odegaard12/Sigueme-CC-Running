// ---------- Estado y utilidades de la ruta ----------
let routeGeojson = null;
let routeBounds = null;      // [west, south, east, north]
let routeLatLon = [];        // [[lat,lon], ...]
let routeCumKm = [];         // km acumulados en cada punto de routeLatLon
let totalRouteKm = 0;
let aidStations = [];

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
  btnRecenter.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="12" cy="7.5" r="3.2"/><path d="M5.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/></svg>';
}
const geoHint = document.getElementById('geo-hint');

const botonFicha = document.getElementById('ver-ficha');
if (botonFicha) {
  botonFicha.addEventListener('click', () => {
    const ficha = document.getElementById('ficha');
    ficha.hidden = !ficha.hidden;
    // OJO: cambiar textContent del botón borraba la foto que lleva dentro.
    // Solo se toca el <span> del texto.
    document.getElementById('ver-ficha-txt').textContent = ficha.hidden ? 'Mi ficha' : 'Cerrar';
    if (!ficha.hidden) ficha.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

function quitarPantallaDeCarga() {
  const tapa = document.getElementById('cargando');
  if (!tapa || tapa.classList.contains('fuera')) return;
  tapa.classList.add('fuera');
  setTimeout(() => tapa.remove(), 500);
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
          attribution: 'Tiles &copy; Esri'
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
    center: [-8.2, 43.48],
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
    if (!map3d.getTerrain()) map3d.setTerrain({ source: 'terrain', exaggeration: 1.4 });
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
      paint: { 'line-color': '#8fe06a', 'line-width': 5, 'line-opacity': 0.95 }
    });

    map3d.addSource('traveled', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
    map3d.addLayer({
      id: 'traveled-line', type: 'line', source: 'traveled',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#5cc2e8', 'line-width': 6 }
    });

    mapReady = true;
    ajustarTamanoCorredor();
    onMapReady();
  });

  // la foto del corredor crece al acercar y encoge al alejar: a zoom de toda
  // la ruta tapaba media provincia
  map3d.on('zoom', ajustarTamanoCorredor);
}

let chinchetasPuestas = false;

// ⚠️ Visto en pruebas: a veces el mapa se queda a medias (el estilo nunca
// termina de montarse) y, como la pantalla de carga se quita a los 8 s, el
// resultado es un recuadro negro sin chinchetas y sin ningún aviso. También
// puede pasar en el móvil si el navegador se lleva por delante el contexto
// gráfico al cambiar de app. Este vigilante lo detecta y rehace el mapa.
let intentosDeMapa = 0;

function montarMapa() {
  try {
    buildMap3D();
  } catch (e) {
    map3dDiv.innerHTML = '<p style="color:#eef2ee;text-align:center;padding:40px 16px">No se pudo cargar el mapa 3D: ' + e.message + '</p>';
    return;
  }
  // si el contexto gráfico se pierde (cambiar de app, memoria baja), rehacer
  const lienzo = map3d.getCanvas();
  if (lienzo) lienzo.addEventListener('webglcontextlost', () => rehacerMapa('contexto gráfico perdido'));
  // ⚠️ Con la pestaña en segundo plano el navegador congela el dibujado y el
  // mapa NO se monta hasta que se mira: eso no es un fallo y no hay que
  // rehacer nada. Se comprueba solo con la página a la vista.
  const revisar = () => {
    if (document.hidden) return;
    if (!mapReady || !map3d.isStyleLoaded()) rehacerMapa('el mapa no terminó de cargar');
  };
  setTimeout(revisar, 12000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !mapReady) setTimeout(revisar, 12000);
  });
}

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
  try { map3d.remove(); } catch (e) {}
  mapReady = false;
  chinchetasPuestas = false;
  marcadoresConPopup.length = 0;
  riderMarkerEl = null;
  tamanoCorredorActual = 0;
  kmPintado = null;
  montarMapa();
}

montarMapa();


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
  if (!aidStations.length) return;
  chinchetasPuestas = true;

  map3d.fitBounds(
    [[routeBounds[0], routeBounds[1]], [routeBounds[2], routeBounds[3]]],
    { padding: 30, pitch: 50, bearing: -20, duration: 0 }
  );

  // salida y meta son el mismo punto (recorrido circular)
  const startPos = routeLatLon[0];
  if (startPos) {
    const el = document.createElement('div');
    el.className = 'aid-pin';
    el.innerHTML = aidPinSVG('#f3f6f2', '🏁');
    pulsarAbrePopup(
      new maplibregl.Marker({ element: el, anchor: 'bottom', opacityWhenCovered: '0.99' })
        .setLngLat([startPos[1], startPos[0]])
        .setPopup(nuevoPopup(30).setHTML(
          '<div class="globo"><span class="globo-tipo">Salida y meta</span>' +
          '<b>Paseo Marítimo de Xuvia</b>' +
          '<span class="globo-km">km 0 · km ' + totalRouteKm.toFixed(1) + '</span></div>'))
        .addTo(map3d),
      el);
  }

  // avituallamientos como chinchetas numeradas: verde normal, naranja el
  // principal (comida caliente), azul los talleres MTB, igual que la guía
  aidStations.forEach((s, i) => {
    const pos = pointAtKm(s.km);
    if (!pos) return;
    const color = s.principal ? '#e08a3a' : s.taller ? '#5cc2e8' : '#8fe06a';
    const tipo = s.principal ? 'Comida caliente · bolsa de vida'
      : s.taller ? 'Avituallamiento + taller MTB'
      : 'Avituallamiento';
    const el = document.createElement('div');
    el.className = 'aid-pin';
    el.innerHTML = aidPinSVG(color, s.taller ? '🔧' : String(i + 1));
    pulsarAbrePopup(
      new maplibregl.Marker({ element: el, anchor: 'bottom', opacityWhenCovered: '0.99' })
        .setLngLat([pos[1], pos[0]])
        .setPopup(nuevoPopup(30).setHTML(
          '<div class="globo"><span class="globo-tipo" style="color:' + color + '">' + tipo + '</span>' +
          '<b>' + (i + 1) + '. ' + s.name + '</b>' +
          '<span class="globo-km">km ' + s.km + ' · faltan ' +
          (totalRouteKm - s.km).toFixed(1) + ' km para meta</span></div>'))
        .addTo(map3d),
      el);
  });

  if (riderMarkerPos) placeRiderMarker(riderMarkerPos[0], riderMarkerPos[1]);
}

fetch('route.geojson')
  .then(r => r.json())
  .then(geojson => {
    routeGeojson = geojson;
    const props = geojson.features[0].properties;
    document.getElementById('stat-dist').textContent = props.distance_km;
    document.getElementById('stat-gain').textContent = props.elevation_gain_m;
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
function loadAidStations() {
  fetch('aid_stations.json')
    .then(r => r.ok ? r.json() : [])
    .then(stations => {
      aidStations = stations || [];
      drawElevationMarkers();
      onMapReady();
    })
    .catch(() => {});
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

fetch('elevation.json')
  .then(r => r.json())
  .then(data => {
    lastEleData = data;
    drawElevationChart(data.profile, data.min_ele_m, data.max_ele_m);
  });

// Pendiente del tramo en el que va ahora mismo, sacada del propio perfil.
function pendienteEn(km) {
  if (!lastEleData) return '—';
  const perfil = lastEleData.profile;
  const maxD = perfil[perfil.length - 1].d;
  const i = Math.min(perfil.length - 1, Math.max(1, Math.round(km / maxD * (perfil.length - 1))));
  const g = perfil[i].grad;
  return (g > 0 ? '+' : '') + g.toFixed(1) + '%';
}

function drawElevationMarkers() {
  if (lastEleData) drawElevationChart(lastEleData.profile, lastEleData.min_ele_m, lastEleData.max_ele_m);
}

function drawElevationChart(profile, minEle, maxEle) {
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
    const color = s.principal ? '#e08a3a' : s.taller ? '#5cc2e8' : '#8fe06a';
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
}

window.addEventListener('resize', () => drawElevationMarkers());

function drawTraveledLine(doneKm) {
  const idx = traveledIndex(doneKm / (factorKm || 1));
  const traveledPts = routeLatLon.slice(0, idx + 1);
  if (mapReady) {
    const src = map3d.getSource('traveled');
    if (src) {
      src.setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: traveledPts.map(p => [p[1], p[0]]) }
      });
    }
  }
}

// ---------- Corredor: posición extraída del enlace BSC500 vía admin ----------
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
    el.innerHTML = '<span><img src="rider.png?v=3" alt="Dorsal 1017"></span>';
    // opacityWhenCovered: con terreno 3D MapLibre da por "tapado" todo lo que
    // está pegado al suelo y lo deja casi invisible al acercar. Aquí no
    // interesa: el corredor tiene que verse siempre.
    riderMarkerEl = new maplibregl.Marker({ element: el, opacityWhenCovered: '0.99' })
      .setLngLat([lon, lat])
      .setPopup(nuevoPopup(18).setHTML(
        '<div class="globo"><span class="globo-tipo">Dorsal 1017</span>' +
        '<b>Óscar García</b><span class="globo-km">Berria Bravo 4.1</span></div>'))
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

function recenterOnRider() {
  if (!mapReady) return;
  if (riderMarkerPos) {
    map3d.easeTo({ center: [riderMarkerPos[1], riderMarkerPos[0]], zoom: Math.max(map3d.getZoom(), 14), duration: 600 });
  } else if (routeBounds) {
    // sin corredor en pantalla, el botón devuelve la vista a la ruta entera
    map3d.fitBounds([[routeBounds[0], routeBounds[1]], [routeBounds[2], routeBounds[3]]],
      { padding: 30, pitch: vista3d ? 50 : 0, bearing: vista3d ? -20 : 0, duration: 600 });
  }
}
btnRecenter.addEventListener('click', recenterOnRider);

// --- 2D / 3D ---------------------------------------------------------------
// El mapa es siempre el mismo (satélite + relieve); lo único que cambia es la
// inclinación: 0° se ve en plano (mejor para leer el trazado) y 50° en relieve.
const btnVista = document.getElementById('btn-vista');
let vista3d = true;
function pintarBotonVista() { btnVista.textContent = vista3d ? '2D' : '3D'; }
pintarBotonVista();
btnVista.addEventListener('click', () => {
  vista3d = !vista3d;
  pintarBotonVista();
  if (!mapReady) return;
  map3d.easeTo({ pitch: vista3d ? 50 : 0, bearing: vista3d ? -20 : 0, duration: 700 });
});

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
}

// Diferencia entre el reloj de quien mira y el del servidor. Sin esto, un
// móvil con la hora mal puesta enseñaba un cronómetro disparatado (o negativo)
// a todo el que abriera la web.
let desfaseReloj = 0;
function ahoraServidor() { return Date.now() - desfaseReloj; }

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
// Los datos llegan a tirones (el servidor pregunta al BSC500 cada pocos
// segundos), así que pintar la posición en crudo daba saltos. Aquí se
// interpola entre el punto anterior y el nuevo: la foto se desliza y el
// trazado y el perfil crecen poco a poco.
// dura casi lo mismo que el intervalo de consulta (10 s): así la foto no
// pega un tirón y se para, sino que va andando todo el rato
const SUAVIZADO_MS = 9500;
let kmPintado = null;
let posPintada = null;
let animacion = null;
let ultimoRepintadoPesado = 0;

function pintarProgreso(km, pos) {
  currentKm = km;
  document.getElementById('m-dist').textContent = km.toFixed(1);
  document.getElementById('m-left').textContent = Math.max(0, totalRouteKm - km).toFixed(1);
  if (pos) placeRiderMarker(pos[0], pos[1]);
  // la línea recorrida y el perfil son caros de repintar (miles de puntos):
  // la foto va a 60 fps, esto a 5 veces por segundo, que no se nota
  const ahora = performance.now();
  if (ahora - ultimoRepintadoPesado > 200) {
    ultimoRepintadoPesado = ahora;
    const grad = pendienteEn(km);
    document.getElementById('m-grad').textContent = grad;
    pintarNivel(grad);
    drawTraveledLine(km);
    drawElevationMarkers();
  }
}

function moverSuave(km, pos) {
  const km0 = kmPintado, p0 = posPintada;
  // primera vez: colocar directo, no hay desde dónde moverse
  if (km0 === null) {
    if (animacion) cancelAnimationFrame(animacion);
    animacion = null;
    kmPintado = km; posPintada = pos;
    ultimoRepintadoPesado = 0;
    pintarProgreso(km, pos);
    return;
  }
  // un salto grande (simulación acelerada, cambio de enlace) se recorre
  // deprisa en vez de plantarse de golpe: así tampoco va a tirones
  const duracion = Math.abs(km - km0) > 8 ? 1500 : SUAVIZADO_MS;
  if (Math.abs(km - km0) < 0.0005 && !pos) return;
  if (animacion) cancelAnimationFrame(animacion);
  const t0 = performance.now();
  const paso = ahora => {
    const t = Math.min(1, (ahora - t0) / duracion);
    const e = t;   // a ritmo constante: si se acelera y frena, se nota raro
    kmPintado = km0 + (km - km0) * e;
    posPintada = (p0 && pos) ? [p0[0] + (pos[0] - p0[0]) * e, p0[1] + (pos[1] - p0[1]) * e] : (pos || p0);
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
const DIA_CARRERA = 'SÁBADO 26/09';
const HORA_SALIDA = '08:30';

// Óscar enciende el GPS en la salida sobre las 08:15, pero la carrera sale a
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
  if (hueco) hueco.style.color = isNaN(n) ? '' : gradColor(n);
}

function esMeta(data, km) {
  if (data.status_label === 'Finalizada') return true;
  if (!totalRouteKm || km == null || km < 80) return false;
  if (km >= totalRouteKm - 0.4) return true;
  const meta = routeLatLon[routeLatLon.length - 1];
  if (meta && data.lat != null && data.lon != null) {
    return haversineKm([data.lat, data.lon], meta) < 0.2;
  }
  return false;
}

function fmtFinal(ms) {
  const m = Math.max(0, Math.round(ms / 60000));
  return Math.floor(m / 60) + 'h ' + String(m % 60).padStart(2, '0') + 'm';
}

function fmtDuracion(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const hh = String(Math.floor(s / 3600)).padStart(2, '0');
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return hh === '00' ? mm + ':' + ss : hh + ':' + mm + ':' + ss;
}

function pollLive() {
  fetch('live.json?_=' + Date.now())
    .then(r => r.json())
    .then(data => {
      if (data.updated) desfaseReloj = Date.now() - new Date(data.updated).getTime();
      lastStartedAt = data.started_at || null;

      let doneKm = data.dist_km;
      if (!ultimoKmConocido && data.dist_km) ultimoKmConocido = data.dist_km;
      if (data.lat != null && data.lon != null && routeLatLon.length) {
        doneKm = projectOntoRoute(data.lat, data.lon).alongKm * factorKm;
      }
      if (doneKm != null && totalRouteKm) {
        doneKm = Math.min(doneKm, totalRouteKm);
        if (doneKm < ultimoKmConocido - 0.5) doneKm = ultimoKmConocido;
        ultimoKmConocido = doneKm;
      }

      enMeta = esMeta(data, doneKm);
      haArrancado = enMeta || yaArrancado(data, doneKm);

      // qué se enseña en cada momento: antes de salir, nada; en meta,
      // desaparece lo instantáneo (velocidad ahora, pulso, pendiente) y se
      // quedan fijos los totales
      ['speed', 'hr', 'grad'].forEach(n => verCasilla(n, haArrancado && !enMeta));
      ['dist', 'time', 'speed-avg', 'hr-avg', 'cad'].forEach(n => verCasilla(n, haArrancado));
      verCasilla('left', haArrancado && !enMeta);
      document.querySelector('.metricas').classList.toggle('sin-datos', !haArrancado);

      document.getElementById('m-speed').textContent = enMeta ? '0' : (data.speed_kmh ?? '—');
      document.getElementById('m-speed-avg').textContent = data.speed_kmh_avg ?? '—';
      document.getElementById('m-hr').textContent = enMeta ? '—' : (data.hr ?? '—');
      document.getElementById('m-hr-avg').textContent = data.hr_avg ?? '—';
      document.getElementById('m-cad-avg').textContent = data.cadence_avg ?? '—';

      if (enMeta && lastStartedAt && data.updated) {
        // tiempo final = del pistoletazo al último dato que llegó, congelado
        document.getElementById('m-time').textContent =
          fmtFinal(new Date(data.updated) - new Date(lastStartedAt));
      } else if (!haArrancado) {
        document.getElementById('m-time').textContent = '—';
      } else {
        document.getElementById('m-time').textContent =
          lastStartedAt ? fmtElapsedSince(lastStartedAt) : (data.elapsed || '—');
      }

      if (doneKm != null && totalRouteKm && haArrancado) {
        moverSuave(enMeta ? totalRouteKm : doneKm,
                   data.lat != null && data.lon != null ? [data.lat, data.lon] : null);
      } else if (kmPintado !== null && kmPintado !== 0) {
        // se reseteó desde el panel: borrar también lo ya pintado en las
        // pantallas que estuvieran abiertas, o se quedan con el progreso
        if (animacion) cancelAnimationFrame(animacion);
        animacion = null;
        kmPintado = 0; posPintada = null; currentKm = 0; ultimoKmConocido = 0;
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
        estado.textContent = '🏁 En meta · tiempo final ' +
          document.getElementById('m-time').textContent;
        estado.classList.add('meta');
      } else {
        estado.classList.remove('meta');
        estado.classList.remove('previo');
        const hora = lastStartedAt ? fmtTime(lastStartedAt) : HORA_SALIDA;
        if (data.lat != null && !haArrancado) {
          // ya está compartiendo y se le ve en el mapa, pero aún no ha salido
          estado.textContent = 'INICIO ' + hora + ' · Óscar ya está en la salida';
          estado.classList.add('previo');
        } else if (!haArrancado) {
          estado.textContent = 'INICIO ' + hora + ' · ' + DIA_CARRERA;
          estado.classList.add('previo');
        } else {
          estado.textContent = '';
        }
      }

      // pie de estado: en meta, sin señal o la hora del último dato
      const pie = document.getElementById('live-updated');
      const hueco = data.updated ? (Date.now() - new Date(data.updated)) : 0;
      {
        if (data.updated && hueco > 240000 && data.status_label === 'En carrera') {
          pie.textContent = 'Sin datos nuevos desde las ' + fmtTime(data.updated) +
            ' · puede ser cobertura';
        } else if (data.updated && data.lat != null) {
          pie.textContent = 'Última actualización: ' + fmtTime(data.updated);
        } else {
          pie.textContent = '';
        }
      }

      if (data.lat != null && data.lon != null) {
        if (!haArrancado) placeRiderMarker(data.lat, data.lon);
        geoHint.textContent = '';
      } else {
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
    .catch(() => {});
}

// el tiempo transcurrido se refresca cada segundo aunque no llegue poll nuevo;
// en meta NO se toca, que si no el cronómetro seguía corriendo
setInterval(() => {
  if (enMeta) return;
  if (lastStartedAt) document.getElementById('m-time').textContent = fmtElapsedSince(lastStartedAt);
}, 1000);

pollLive();
setInterval(pollLive, 10000);
