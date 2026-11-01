// Service worker SOLO de los avisos en el móvil (ámbito /avisos/): aparte del de «sin cobertura» (sw.js), para que
// apagar ese modo en el panel no borre las suscripciones. No guarda nada en caché.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) {}
  e.waitUntil(self.registration.showNotification(d.title || 'Sígueme CC', {
    body: d.body || '', icon: '/icon-192.png?v=4', badge: '/icon-192.png?v=4', tag: d.tag, data: { url: d.url || '/' } }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || '/', self.location.origin).href;
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(ws => {
    for (const w of ws) if (w.url.startsWith(self.location.origin) && 'focus' in w) return w.focus();
    return clients.openWindow(url);
  }));
});
