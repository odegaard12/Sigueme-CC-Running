// Arriba del todo sale el usuario de quien ha entrado (los invitados) o «Mi panel» (el dueño con sesión).
// Se llama sola al cargar y la puede volver a llamar la página tras entrar (window.marcaUsuario). Texto con textContent.
'use strict';
window.marcaUsuario = function () {
  fetch('/api/invitado/yo', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : {}).then(d => {
    const entrar = document.querySelector('.barra nav a[href="/mis-rutas.html"], .barra-cartel nav a[href="/mis-rutas.html"]');
    if (d && d.dueno) {                     // el dueño: «Mi panel» (sus rutas están dentro del panel)
      if (entrar) {
        const nav = entrar.parentElement, aqui = location.pathname;
        nav.textContent = '';
        for (const [txt, href] of [['Mi panel', '/admin.html']]) {                 // todo (también tus rutas) está dentro del panel
          const a = document.createElement('a'); a.textContent = txt; a.href = href;
          if (aqui === href) continue;                                        // ya estás ahí: el título lo dice
          nav.append(a);
        }
      }
      return;
    }
    if (!d || !d.usuario) return;
    const donde = entrar || document.querySelector('.marca, .marca-cartel');
    if (donde) { donde.textContent = d.usuario; donde.href = '/mis-rutas.html'; donde.title = 'Tu perfil: Mis carreras'; }
  }).catch(() => {});
};
window.marcaUsuario();
