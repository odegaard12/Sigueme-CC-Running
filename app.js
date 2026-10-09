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
const entero = v => (v == null || v === '' || isNaN(v)) ? '—' : String(Math.round(v));

// Datos pedidos desde el <head> (index.html) para no esperar a la librería
// del mapa. Si no están (o fallaron), se piden aquí.
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
let anclaDelGps = false;   // ultimoKmConocido viene del BSC500, no de la ruta
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
  // arrastrar el mapa = quiere mirar otra cosa: se deja de seguir
  map3d.on('dragstart', () => marcarSiguiendo(false));
}

let chinchetasPuestas = false;

// ⚠️ Visto en pruebas: a veces el mapa se queda a medias (el estilo nunca
// termina de montarse) y, como la pantalla de carga se quita a los 8 s, el
// resultado es un recuadro negro sin chinchetas y sin ningún aviso. También
// puede pasar en el móvil si el navegador se lleva por delante el contexto
// gráfico al cambiar de app. Este vigilante lo detecta y rehace el mapa.
let intentosDeMapa = 0;
let lienzoActual = null;
let revisarActual = null;
const alPerderContexto = () => rehacerMapa('contexto gráfico perdido');

function montarMapa() {
  try {
    buildMap3D();
  } catch (e) {
    map3dDiv.innerHTML = '<p style="color:#eef2ee;text-align:center;padding:40px 16px">No se pudo cargar el mapa 3D: ' + e.message + '</p>';
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
  setTimeout(revisar, 20000);
  revisarActual = revisar;
}

// UNA sola escucha: si se ponía dentro de montarMapa, cada mapa rehecho añadía
// otra, y al volver a la pestaña saltaban todas y gastaban los reintentos
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !mapReady && revisarActual) setTimeout(revisarActual, 20000);
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
  tamanoCorredorActual = 0;
  kmPintado = null;
  objetivo = null;      // si no, el siguiente poll no repinta la línea azul
  idxRecorridoPintado = -1;
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
          '<span class="globo-km">km 0 · km ' + num(totalRouteKm) + '</span></div>'))
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
          '<span class="globo-km">km ' + num(s.km) + ' · faltan ' +
          num(totalRouteKm - s.km) + ' km para meta</span></div>'))
        .addTo(map3d),
      el);
  });

  if (riderMarkerPos) placeRiderMarker(riderMarkerPos[0], riderMarkerPos[1]);
}

precargado('route.geojson', () => fetch('route.geojson').then(r => r.json()))
  .then(geojson => {
    routeGeojson = geojson;
    const props = geojson.features[0].properties;
    document.getElementById('stat-dist').textContent = num(props.distance_km, 2);
    document.getElementById('stat-gain').textContent = Number(props.elevation_gain_m).toLocaleString('es-ES');
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
  precargado('aid_stations.json', () => fetch('aid_stations.json').then(r => r.ok ? r.json() : []))
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

precargado('elevation.json', () => fetch('elevation.json').then(r => r.json()))
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
    el.innerHTML = '<span><img src="rider.png?v=5" alt="Dorsal 1"></span>';
    // opacityWhenCovered: con terreno 3D MapLibre da por "tapado" todo lo que
    // está pegado al suelo y lo deja casi invisible al acercar. Aquí no
    // interesa: el corredor tiene que verse siempre.
    riderMarkerEl = new maplibregl.Marker({ element: el, opacityWhenCovered: '0.99' })
      .setLngLat([lon, lat])
      .setPopup(nuevoPopup(18).setHTML(
        '<div class="globo"><span class="globo-tipo">Dorsal 1</span>' +
        '<b>Odegaard12</b><span class="globo-km">Mi bici</span></div>'))
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
}

function seguirCorredor(pos) {
  if (!siguiendo || !mapReady || !pos) return;
  // si está haciendo zoom o girando con los dedos, no pelearse con su gesto
  if (map3d.isZooming() || map3d.isRotating()) return;
  const ahora = performance.now();
  // una vez por segundo con un deslizamiento de un segundo: la cámara va
  // continua y no se fuerza al móvil a redibujar el relieve 60 veces/s
  if (ahora - ultimoSeguimiento < 1000) return;
  ultimoSeguimiento = ahora;
  map3d.easeTo({ center: [pos[1], pos[0]], duration: 1000, easing: t => t });
}

function recenterOnRider() {
  if (!mapReady) return;
  if (riderMarkerPos) {
    marcarSiguiendo(true);
    ultimoSeguimiento = performance.now() + 600;
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
  return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid' });
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

function ponerTexto(id, texto) {
  const el = document.getElementById(id);
  if (el && el.textContent !== texto) el.textContent = texto;
}

function pintarProgreso(km, pos) {
  currentKm = km;
  ponerTexto('m-dist', num(km));
  ponerTexto('m-left', num(Math.max(0, totalRouteKm - km)));
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
  const duracion = salto > 8 ? 1500
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
    if (t < 1 && ahora - ultimoFotograma < 50 && duracion > 2000) {
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
const DIA_CARRERA = 'SÁBADO 26/09';
const HORA_SALIDA = '08:30';

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
  if (hueco) hueco.style.color = isNaN(n) ? '' : gradColor(n);
}

function esMeta(data, km) {
  // la llegada la apunta el servidor una vez y ya no se desdice
  if (data.finished_at || data.status_label === 'Finalizada') return true;
  if (!totalRouteKm || km == null || km < 80) return false;
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
let pidiendo = false;
let fallosSeguidos = 0;

function fetchConTiempo(url, ms = 8000) {
  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), ms);
  return fetch(url, { signal: control.signal, cache: 'no-store' }).finally(() => clearTimeout(reloj));
}

function avisoConexion(mal) {
  let el = document.getElementById('aviso-conexion');
  if (!el) {
    el = document.createElement('div');
    el.id = 'aviso-conexion';
    el.className = 'aviso-conexion';
    el.setAttribute('role', 'status');
    el.hidden = true;
    document.body.appendChild(el);
  }
  if (mal) el.textContent = navigator.onLine === false
    ? 'Sin conexión · reintentando…' : 'No llegan datos · reintentando…';
  el.hidden = !mal;
}

function pollLive() {
  // hasta saber si hay resultado guardado no se pinta nada: si no, salía un
  // instante "INICIO 08:30 · SÁBADO 26/09" y luego cambiaba todo
  if (!resultadoConsultado) return;
  if (pidiendo) return;          // la anterior aún no ha vuelto: no amontonar
  pidiendo = true;
  precargado('live.json', () => fetchConTiempo('live.json?_=' + Date.now()))
    .then(r => {
      if (!r || !r.ok) throw new Error('HTTP ' + (r ? r.status : 'sin respuesta'));
      // la hora del servidor sale de la cabecera Date de la respuesta, no de
      // "updated": si el servidor llevaba minutos sin escribir (sin señal),
      // el cronómetro de quien miraba se atrasaba esos mismos minutos
      const fecha = Date.parse(r.headers.get('Date'));
      if (!isNaN(fecha)) desfaseReloj = Date.now() - fecha;
      return r.json();
    })
    .then(data => {
      fallosSeguidos = 0;
      avisoConexion(false);
      lastStartedAt = data.started_at || null;
      document.querySelector('.metricas').classList.remove('cargando');

      // sin carrera en marcha y con resultado guardado: se enseña el resultado
      if (resultado && !data.started_at && !data.livetrack_url) {
        if (!repitiendo) pintarResultado();
        return;
      }
      document.getElementById('resultado').hidden = true;
      document.getElementById('aviso-resultado').hidden = true;

      let doneKm = data.dist_km;
      // ⚠️ Al abrir la web a mitad de carrera, la distancia del BSC500 sirve
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

      // último dato NUEVO del BSC500 (updated se renueva en cada consulta)
      const ultimoDato = data.data_at || data.updated;
      const llegada = data.finished_at || ultimoDato;
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
      } else if (kmPintado !== null && kmPintado !== 0) {
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
        estado.textContent = '🏁 En meta · tiempo final ' +
          document.getElementById('m-time').textContent;
        estado.classList.add('meta');
      } else {
        estado.classList.remove('meta');
        estado.classList.remove('previo');
        const hora = lastStartedAt ? fmtTime(lastStartedAt) : HORA_SALIDA;
        if (data.lat != null && !haArrancado) {
          // ya está compartiendo y se le ve en el mapa, pero aún no ha salido
          estado.textContent = 'INICIO ' + hora + ' · Odegaard12 ya está en la salida';
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
      const hueco = ultimoDato ? (ahoraServidor() - new Date(ultimoDato)) : 0;
      {
        if (ultimoDato && hueco > 240000 && data.status_label === 'En carrera') {
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
// resultado.json se genera con el FIT del BSC500 (tiempos, paso por cada
// avituallamiento y la traza real recortada a salida-meta).
let resultado = null;
let resultadoConsultado = false;
let repitiendo = false;
let kmsTraza = null;

const horaNaron = iso => new Date(iso).toLocaleTimeString('es-ES',
  { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid' });
const fmtHM = s => Math.floor(s / 3600) + 'h ' + String(Math.floor(s % 3600 / 60)).padStart(2, '0') + 'm';

// km de ruta de cada punto de la traza, siempre hacia delante
function calcularKmsTraza() {
  if (kmsTraza || !resultado || !routeLatLon.length) return;
  let km = 0;
  kmsTraza = resultado.traza.map(([la, lo]) => {
    let mejor = Infinity, mk = km;
    for (let j = 0; j < routeLatLon.length; j++) {
      if (routeCumKm[j] < km - 0.5 || routeCumKm[j] > km + 8) continue;
      const d = haversineKm([la, lo], routeLatLon[j]);
      if (d < mejor) { mejor = d; mk = routeCumKm[j]; }
    }
    if (mejor < 0.15) km = Math.max(km, mk);
    return Math.min(totalRouteKm, km * factorKm);
  });
}

function pintarResultado() {
  const r = resultado;
  ['speed', 'hr', 'grad', 'left'].forEach(n => verCasilla(n, false));
  ['dist', 'time', 'speed-avg', 'hr-avg', 'cad'].forEach(n => verCasilla(n, true));
  document.querySelector('.metricas').classList.remove('sin-datos');
  ponerTexto('m-dist', num(r.distancia_km));
  ponerTexto('m-time', fmtHM(r.tiempo_oficial_s));
  ponerTexto('m-speed-avg', num(r.velocidad_media_mov));
  ponerTexto('m-hr-avg', entero(r.pulso_medio));
  ponerTexto('m-cad-avg', entero(r.cadencia_media));
  // el resultado va arriba, antes del mapa: era lo primero que había que ver
  // y quedaba debajo del mapa y la leyenda
  const estado = document.getElementById('estado-carrera');
  estado.classList.remove('previo', 'meta');
  estado.textContent = '';
  ponerTexto('aviso-titulo', '🏁 Terminada en ' + fmtHM(r.tiempo_oficial_s));
  // corto a propósito: en el móvil pequeño partía en dos líneas (el "de 12 h"
  // ya sale en la cabecera)
  ponerTexto('aviso-sub', num(r.distancia_km) + ' km · llegada a las ' + horaNaron(r.llegada));
  document.getElementById('aviso-resultado').hidden = false;
  ponerTexto('stat-limite', fmtHM(r.tiempo_oficial_s));
  const etiqueta = document.querySelector('#stat-limite + i');
  if (etiqueta) etiqueta.textContent = 'de 12 h';
  document.getElementById('live-updated').textContent =
    r.carrera + ' · datos del ciclocomputador · ' + fmtHM(r.tiempo_movimiento_s) + ' en movimiento';
  // mapa y perfil completos, la foto en meta
  if (totalRouteKm) {
    currentKm = totalRouteKm;
    idxRecorridoPintado = -1; pixelPerfilPintado = null;
    drawTraveledLine(totalRouteKm);
    drawElevationMarkers();
    const fin = r.traza[r.traza.length - 1];
    placeRiderMarker(fin[0], fin[1]);
  }
  const lista = document.getElementById('pasos');
  if (!lista.children.length) {
    const salida = new Date(r.salida);
    r.pasos.forEach((p, i) => {
      const li = document.createElement('li');
      const trans = (new Date(p.hora) - salida) / 1000;
      li.innerHTML = '<span class="n">' + (i + 1) + '</span><span class="nombre"></span>' +
        '<span class="km">km ' + num(p.km) + ' · +' + fmtHM(trans) + '</span><span class="hora">' + horaNaron(p.hora) + '</span>';
      li.children[1].textContent = p.nombre;   // el nombre como texto, no HTML
      lista.appendChild(li);
    });
  }
  document.getElementById('resultado').hidden = false;
}

// Repetición: la carrera entera en 60 s, con la foto por la traza real
const DURACION_REPETICION = 60000;
function repetirCarrera() {
  const boton = document.getElementById('btn-repeticion');
  if (repitiendo) { repitiendo = false; return; }
  calcularKmsTraza();
  if (!kmsTraza) return;
  repitiendo = true;
  boton.innerHTML = '<span class="ico">■</span><span class="txt"> Parar</span>';
  const tr = resultado.traza, total = tr[tr.length - 1][2];
  const salida = new Date(resultado.salida).getTime();
  if (mapReady) {
    map3d.easeTo({ center: [tr[0][1], tr[0][0]], zoom: 12.5, duration: 800 });
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
    ponerTexto('aviso-titulo', '▶ ' + horaNaron(reloj) + ' · km ' + num(km));
    const pasados = resultado.pasos.filter(p => new Date(p.hora).getTime() <= salida + t * 1000).length;
    items.forEach((li, k) => li.classList.toggle('actual', k === pasados - 1));
    if (!fin) { requestAnimationFrame(paso); return; }
    repitiendo = false;
    boton.innerHTML = '<span class="ico">▶</span><span class="txt"> Ver la carrera</span>';
    items.forEach(li => li.classList.remove('actual'));
    marcarSiguiendo(false);
    if (mapReady && routeBounds) {
      map3d.fitBounds([[routeBounds[0], routeBounds[1]], [routeBounds[2], routeBounds[3]]],
        { padding: 30, pitch: 50, bearing: -20, duration: 1200 });
    }
    pintarResultado();
  };
  requestAnimationFrame(paso);
}
document.getElementById('btn-repeticion').addEventListener('click', repetirCarrera);

precargado('resultado.json', () => fetch('resultado.json?_=' + Date.now()).then(r => r.ok ? r.json() : null))
  .catch(() => null)
  .then(d => { resultado = d; resultadoConsultado = true; pollLive(); });

pollLive();
setInterval(pollLive, 5000);
// al desbloquear el móvil o volver a la pestaña, datos al momento (antes había
// que esperar al siguiente turno, y en segundo plano el navegador los frena)
document.addEventListener('visibilitychange', () => { if (!document.hidden) pollLive(); });
window.addEventListener('online', pollLive);
window.addEventListener('offline', () => avisoConexion(true));
