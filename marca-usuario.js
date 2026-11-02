// Arriba del todo, donde va el nombre del sitio, sale el usuario de quien ha entrado (los invitados; el dueño no).
// Se llama sola al cargar y la puede volver a llamar la página tras entrar (window.marcaUsuario). Texto con textContent.
'use strict';
window.marcaUsuario = function () {
  fetch('/api/invitado/yo', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : {}).then(d => {
    if (!d || !d.usuario) return;
    const entrar = document.querySelector('.barra nav a[href="/mis-rutas.html"]');
    const donde = entrar || document.querySelector('.marca, .marca-cartel');
    if (donde) { donde.textContent = d.usuario; donde.href = '/mis-rutas.html'; donde.title = 'Tu perfil: Mis carreras'; }
  }).catch(() => {});
};
window.marcaUsuario();
