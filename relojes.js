// Guía de relojes: «¿Sirve mi reloj?». Busca el modelo en las tablas de cada marca de la propia página (sin datos
// aparte: lo que sale aquí es exactamente lo que dicen las tablas). Sin JavaScript, las tablas se leen igual.
'use strict';
(function () {
  const q = document.getElementById('busca-reloj'), out = document.getElementById('busca-resultado');
  if (!q || !out) return;
  const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const filas = [...document.querySelectorAll('.tabla-modelos tbody tr')].map(tr => {
    const ficha = tr.closest('.marca-tarj'), marca = ficha.querySelector('h3').textContent.trim();
    return { tr, ficha, marca, texto: norm(marca + ' ' + tr.cells[0].textContent) };
  });
  const pinta = () => {
    const t = norm(q.value);
    out.textContent = '';
    if (t.length < 2) { out.hidden = true; return; }
    const palabras = t.split(' ');
    const hay = filas.filter(f => palabras.every(p => f.texto.includes(p))).slice(0, 8);
    out.hidden = false;
    if (!hay.length) {
      const p = document.createElement('p'); p.className = 'nota';
      p.textContent = 'No lo tenemos en la lista. Mira en la app de tu reloj si aparece «Importar ruta», «Rutas» o «Cursos»: si está, la ruta sirve.';
      out.append(p); return;
    }
    hay.forEach(f => {
      const a = document.createElement('a'); a.className = 'resultado-reloj'; a.href = '#' + f.ficha.id;
      const n = document.createElement('b'); n.textContent = f.marca + ' · ' + f.tr.cells[0].textContent.trim();
      const r = document.createElement('span');
      r.append('Ruta', f.tr.cells[1].firstElementChild.cloneNode(true), 'Mapa', f.tr.cells[2].firstElementChild.cloneNode(true));
      a.append(n, r); out.append(a);
    });
  };
  q.addEventListener('input', pinta);
})();

// Una marca a la vez: los botones de marca (y los resultados del buscador) enseñan solo esa ficha.
// Sin JavaScript se ven todas, una debajo de otra.
(function () {
  const caja = document.getElementById('fichas-marca'), nav = document.querySelector('.chips-marcas');
  if (!caja || !nav) return;
  const fichas = [...caja.querySelectorAll('.marca-tarj')], botones = [...nav.querySelectorAll('a')];
  const ver = id => {
    if (!fichas.some(f => f.id === id)) return false;
    fichas.forEach(f => { f.hidden = f.id !== id; });
    botones.forEach(b => b.getAttribute('href') === '#' + id ? b.setAttribute('aria-current', 'true') : b.removeAttribute('aria-current'));
    return true;
  };
  caja.classList.add('una-a-una');
  if (ver(location.hash.slice(1))) nav.scrollIntoView({block: 'start'}); else ver(fichas[0].id);
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href^="#"]');
    if (!a || !ver(a.hash.slice(1))) return;
    e.preventDefault();
    history.replaceState(null, '', a.hash);
    if (!nav.contains(a)) nav.scrollIntoView({behavior: 'smooth', block: 'start'});
  });
  addEventListener('hashchange', () => { if (ver(location.hash.slice(1))) nav.scrollIntoView({block: 'start'}); });
})();
