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
  // a mano: por si el enlace no abre Traccar (otro navegador, versión vieja). Los dos datos largos, con botón de copiar.
  const aMano = () => {
    const d = el('details', 'nota-dir');
    d.append(el('summary', '', 'Si el botón no abre Traccar: ponerlo a mano'));
    d.append(el('p', 'nota-dir', 'En Traccar Client escribe estos datos (los nombres pueden variar un poco según el idioma y la versión):'));
    const dato = (rotulo, valor) => {
      const p = el('p', 'nota-dir', rotulo + ': '), b = el('b', '', valor), c = el('button', 'boton claro', 'Copiar');
      b.style.cssText = 'overflow-wrap:anywhere;text-transform:none;font:600 .95rem/1.5 ui-monospace,Menlo,Consolas,monospace;letter-spacing:0;color:var(--texto)'; c.type = 'button'; c.style.marginLeft = '8px';
      c.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(valor); c.textContent = 'Copiado'; } catch (e) { c.textContent = 'Mantén pulsado el texto para copiarlo'; }
      });
      p.append(b, el('br'), c); return p;
    };
    d.append(dato('Identificador del dispositivo', ident), dato('Dirección del servidor (URL)', location.origin + '/api/gps'));
    d.append(el('p', 'nota-dir', 'Frecuencia: 10 segundos · Distancia: 0 · Ángulo: 0 · Precisión: máxima · Búfer sin conexión: activado · Detección de paradas: desactivada.'));
    return d;
  };
  const listo = () => el('p', 'listo-dir', 'El día de la carrera solo enciéndelo; puedes hacerlo 1 o 2 horas antes (con poca batería, mejor media hora antes). Sales en el mapa al llegar a la zona de salida, y el tiempo cuenta desde que empiezas a correr de verdad, no desde la hora oficial si sales por el fondo.');
  // pasos numerados: cada uno, una sola cosa que hacer (los textos de los botones no cambian: ya están en los mensajes enviados)
  const paso = (n, titulo, ...resto) => { const d = el('div', 'paso-dir'); const t = el('p', 'listo-dir'); t.textContent = n + '. ' + titulo; d.append(t, ...resto); return d; };
  const contenido = {
    android: () => [
      paso(1, 'Configura la app', boton('Configurar la app Sígueme CC', '/app.html#id=' + encodeURIComponent(ident), true),
        el('p', 'nota-dir', 'Si aún no la tienes, esa página te deja descargarla (el móvil avisará de «origen desconocido»: permítelo). Después vuelve aquí y pulsa «Abrir en la app».')),
      paso(2, 'Dale los permisos', el('p', 'nota-dir', 'En la app, sigue el «Siguiente paso» hasta «Todo listo»: ubicación «Permitir siempre» y sin ahorro de batería.')),
      paso(3, 'El día de la carrera', listo())],
    iphone: () => {
      const l = [
        paso(1, 'Instala Traccar Client', el('p', 'nota-dir', 'Es gratis, en la App Store. Solo la primera vez.')),
        paso(2, 'Ábrelo con tus datos', boton('Abrir en Traccar', traccar, true), aMano()),
        paso(3, 'Dale los permisos', el('p', 'nota-dir', 'Ajustes del iPhone → Traccar Client → Localización: «Siempre» y «Ubicación exacta».')),
        paso(4, 'El día de la carrera', listo())];
      // opcional y al final: los avisos de subidas llegan como notificación de la web instalada (v1.56)
      const op = el('details', 'nota-dir'); op.append(el('summary', '', 'Opcional: avisos de subidas en el iPhone'));
      if (ios && window.avisosMovil) { const caja = el('div'); op.append(caja); window.avisosMovil(caja, ident); }
      else op.append(el('p', 'nota-dir', 'Se activan desde el propio iPhone, con la web instalada en la pantalla de inicio.'));
      l.push(op);
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
