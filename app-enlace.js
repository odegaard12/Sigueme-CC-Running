// El identificador va detrás de "#": el navegador no lo manda al servidor (ni
// sale en ningún registro). El enlace intent:// lo entiende Chrome en Android y
// abre la app con la dirección de esta web y el identificador.
(function () {
  const id = new URLSearchParams(location.hash.slice(1)).get('id') || '';
  document.getElementById('dir').textContent = location.origin;
  const valido = /^[\w-]{8,100}$/.test(id);
  // intent:// solo lo entiende Chrome en Android: en iPhone o en el PC el botón
  // era un enlace muerto; allí se enseña el identificador para Traccar
  const android = /Android/i.test(navigator.userAgent);
  document.getElementById(!valido ? 'sin-id' : android ? 'con-id' : 'sin-android').hidden = false;
  if (valido && !android) document.getElementById('ident').textContent = id;
  if (!valido || !android) return;
  const datos = 'config?u=' + encodeURIComponent(location.origin) + '&id=' + encodeURIComponent(id);
  document.getElementById('abrir').href = 'intent://' + datos + '#Intent;scheme=siguemecc;package=cc.sigueme.app;' +
    'S.browser_fallback_url=' + encodeURIComponent('https://github.com/odegaard12/Sigueme-CC-Running/releases/latest') + ';end';
  // el identificador se queda en esta pestaña: tras instalar la app, se vuelve
  // aquí y se pulsa «Abrir» sin escanear otra vez el código
})();
