// «Tu móvil» en una carrera en directo: configurarlo de un toque en el MISMO móvil (sin QR ni panel).
// Android: la app Sígueme CC (app.html abre la app con la dirección y el identificador).
// iPhone: Traccar Client con su enlace de configuración (dirección, identificador y ajustes buenos para iPhone:
// precisión máxima, cada 10 s, sin detección de paradas y guardando sin cobertura).
// Lo usan directo.js y mis-rutas.js. Los textos, siempre con textContent.
'use strict';
window.pintarMovil = function (cont, ident) {
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  const android = /Android/i.test(ua);
  const traccar = 'org.traccar.client://config?url=' + encodeURIComponent(location.origin + '/api/gps') +
    '&id=' + encodeURIComponent(ident) + '&accuracy=highest&interval=10&distance=0&angle=0&heartbeat=0&buffer=true&stop_detection=false';
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt) e.textContent = txt; return e; };
  const boton = (txt, href, principal) => { const a = el('a', principal ? 'boton' : 'boton claro', txt); a.href = href; return a; };
  const andr = boton('Configurar la app Sígueme CC', '/app.html#id=' + encodeURIComponent(ident), android || !ios);
  const iph = boton('Abrir en Traccar (iPhone)', traccar, ios);
  const notaA = el('p', 'nota-dir', 'Android: si aún no tienes la app, esa página te la deja descargar; luego vuelve y pulsa «Abrir en la app».');
  const notaI = el('p', 'nota-dir', 'iPhone: instala antes Traccar Client (gratis, App Store) y vuelve a pulsar. En Ajustes → Traccar Client → Localización: «Siempre» y «Ubicación exacta».');
  const listo = el('p', 'listo-dir', 'El día de la carrera solo enciéndelo: desde 1 h antes de la salida te pone en marcha él solo, y el tiempo cuenta desde que empiezas a correr.');
  const acc = el('div', 'acciones');
  cont.textContent = '';
  if (ios) { acc.append(iph); cont.append(acc, notaI); }
  else if (android) { acc.append(andr); cont.append(acc, notaA); }
  else { acc.append(andr, iph); cont.append(el('p', 'nota-dir', 'Abre esta página en el móvil con el que vas a correr y pulsa su botón.'), acc, notaA, notaI); }
  cont.append(listo);
  // iPhone: no hay app, así que los avisos de subidas llegan como notificación de la web instalada (v1.56)
  if (ios && window.avisosMovil) {
    const av = el('div'); av.append(el('p', 'listo-dir', 'Avisos de subidas en tu iPhone'));
    const caja = el('div'); av.append(caja); cont.append(av); window.avisosMovil(caja, ident);
  }
};
