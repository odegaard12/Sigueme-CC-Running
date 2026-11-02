// Arriba del todo, donde va el nombre del sitio, sale el usuario de quien ha entrado (los invitados; el dueño no).
// Se llama sola al cargar y la puede volver a llamar la página tras entrar (window.marcaUsuario). Texto con textContent.
'use strict';
window.marcaUsuario = function () {
  fetch('/api/invitado/yo', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : {}).then(d => {
    const m = document.querySelector('.marca, .marca-cartel');
    if (m && d && d.usuario) m.textContent = d.usuario;
  }).catch(() => {});
};
window.marcaUsuario();
