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
  const listo = () => el('p', 'listo-dir', 'El día de la carrera solo enciéndelo: desde 1 h antes de la salida te pone en marcha él solo, y el tiempo cuenta desde que empiezas a correr.');
  const contenido = {
    android: () => [boton('Configurar la app Sígueme CC', '/app.html#id=' + encodeURIComponent(ident), true),
      el('p', 'nota-dir', 'Si aún no tienes la app, esa página te la deja descargar; luego vuelve y pulsa «Abrir en la app».'), listo()],
    iphone: () => {
      const l = [boton('Abrir en Traccar', traccar, true),
        el('p', 'nota-dir', 'Instala antes Traccar Client (gratis, App Store) y vuelve a pulsar. En Ajustes → Traccar Client → Localización: «Siempre» y «Ubicación exacta».'), listo()];
      // el iPhone no tiene app: los avisos de subidas llegan como notificación de la web instalada (v1.56)
      if (ios && window.avisosMovil) {
        const av = el('div'); av.append(el('p', 'listo-dir', 'Avisos de subidas en tu iPhone'));
        const caja = el('div'); av.append(caja); l.push(av); window.avisosMovil(caja, ident);
      } else l.push(el('p', 'nota-dir', 'Los avisos de subidas se activan desde el propio iPhone, con la web instalada en la pantalla de inicio.'));
      return l;
    },
  };
  const pestana = el('div', 'acciones'), cuerpo = el('div');
  const bs = { android: el('button', 'boton claro', 'Android'), iphone: el('button', 'boton claro', 'iPhone') };
  const ver = que => {
    for (const k of Object.keys(bs)) { bs[k].classList.toggle('claro', k !== que); bs[k].setAttribute('aria-pressed', String(k === que)); }
    cuerpo.textContent = ''; cuerpo.append(...contenido[que]());
  };
  for (const k of Object.keys(bs)) { bs[k].type = 'button'; bs[k].addEventListener('click', () => ver(k)); pestana.append(bs[k]); }
  cont.textContent = '';
  cont.append(el('p', 'listo-dir', '¿Qué móvil llevas?'), pestana, cuerpo);
  if (ios || android) ver(ios ? 'iphone' : 'android');
  else cuerpo.append(el('p', 'nota-dir', 'Abre esta página en el móvil con el que vas a correr, o elige aquí cuál es y te enseño solo lo que necesitas.'));
};
