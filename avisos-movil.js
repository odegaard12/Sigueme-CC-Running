// «Avisos de subidas en este iPhone»: activa las notificaciones (Web Push) para el corredor con ESE identificador.
// El servidor manda «SUBIDA LARGA…», cimas y último km a ese móvil según dónde va en la ruta (Traccar da la posición);
// la pulsera los repite. Solo con cobertura. En iPhone solo funciona con la web instalada en la pantalla de inicio.
// Usa el mismo aviso del navegador que la campana de la carrera (mismo service worker). Textos con textContent.
'use strict';
window.avisosMovil = function (cont, ident) {
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt) e.textContent = txt; return e; };
  const ios = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const instalada = navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;
  const puede = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const clave = 'avisos_subidas.' + ident;
  const b64 = s => Uint8Array.from(atob((s + '='.repeat((4 - s.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
  const post = (u, d) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
  let activo = false; try { activo = localStorage.getItem(clave) === '1'; } catch (e) { /* da igual */ }
  cont.textContent = '';
  const btn = el('button', 'boton', ''); btn.type = 'button';
  const msg = el('p', 'nota-dir', '');
  const pintar = () => { btn.textContent = activo ? 'Avisos activados · desactivar' : 'Activar los avisos de subidas'; btn.classList.toggle('claro', activo); };
  const dec = t => { msg.textContent = t; };
  pintar();
  if (!puede) {
    dec(ios && !instalada
      ? 'Para recibir avisos en el iPhone hay que instalar la web: en Safari toca Compartir → «Añadir a pantalla de inicio», ábrela desde su icono, vuelve a esta pantalla y pulsa el botón.'
      : 'Este navegador no puede recibir avisos. En iPhone: Safari al día con la web instalada en la pantalla de inicio.');
  } else if (ios && !instalada) {
    dec('En el iPhone los avisos solo llegan con la web instalada: Compartir → «Añadir a pantalla de inicio», ábrela desde el icono y pulsa el botón desde allí.');
  } else {
    dec(activo ? 'Te avisaremos de cada subida, cima y del último km en este móvil. Solo llegan con cobertura.' : 'Pulsa y acepta las notificaciones. Te avisaremos de cada subida, cima y del último km; tu pulsera los repite. Solo llegan con cobertura.');
  }
  btn.addEventListener('click', async () => {
    if (!puede || (ios && !instalada)) return;
    // Safari (iPhone) solo deja pedir permiso en el mismo toque: se pide ANTES de cualquier espera
    const permiso = !activo && Notification.permission === 'default' ? Notification.requestPermission() : null;
    btn.disabled = true;
    try {
      const reg = await navigator.serviceWorker.register('/sw-avisos.js', { scope: '/avisos/' });
      if (!reg.active) {
        const w = reg.installing || reg.waiting;
        if (w) await new Promise(ok => { const mira = () => { if (w.state === 'activated' || w.state === 'redundant') ok(); }; w.addEventListener('statechange', mira); mira(); });
      }
      const actual = await reg.pushManager.getSubscription();
      if (activo) {
        if (actual) await post('/api/push/mio/baja', { ident, endpoint: actual.endpoint }).catch(() => {});
        activo = false; try { localStorage.removeItem(clave); } catch (e) { /* da igual */ }
        pintar(); return dec('Avisos de subidas desactivados en este móvil.');
      }
      if ((permiso ? await permiso : Notification.permission) !== 'granted') {
        return dec('Sin permiso no te podemos avisar. Actívalo en Ajustes → Notificaciones → Sígueme CC y vuelve a pulsar.');
      }
      const k = await fetch('/api/push/clave').then(r => r.ok ? r.json() : null);
      if (!k || !k.clave) return dec('Los avisos no están disponibles ahora mismo en el servidor.');
      const sub = actual || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(k.clave) });
      const r = await post('/api/push/mio', { ident, sub: sub.toJSON() });
      if (!r.ok) throw new Error('alta ' + r.status);
      activo = true; try { localStorage.setItem(clave, '1'); } catch (e) { /* da igual */ }
      pintar(); dec('Listo: en la carrera te avisaremos de cada subida, cima y del último km en este móvil. Solo llegan con cobertura.');
    } catch (e) {
      console.warn('[avisos subidas]', e && e.name, e && e.message);
      dec('No se pudieron activar los avisos. Comprueba la conexión y vuelve a intentarlo.');
    } finally { btn.disabled = false; }
  });
  cont.append(btn, msg);
};
