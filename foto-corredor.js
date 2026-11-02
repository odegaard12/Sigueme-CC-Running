// «Mi foto» de un corredor de una carrera en directo: se recorta cuadrada y se reduce a 256 px AQUÍ, en el navegador,
// y al servidor solo llega un PNG pequeño (sin los datos de la cámara). Lo identifica su identificador (cabecera X-Ident).
// La foto es opcional, sale solo en esa carrera y se quita cuando se quiera. Textos con textContent.
'use strict';
window.fotoCorredor = function (cont, ident, alCambiar) {
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt) e.textContent = txt; return e; };
  const entrada = el('input'); entrada.type = 'file'; entrada.accept = 'image/*'; entrada.hidden = true;
  const subir = el('button', 'boton claro', 'Mi foto: elegir o hacer una'); subir.type = 'button';
  const quitar = el('button', 'boton claro', 'Quitar mi foto'); quitar.type = 'button';
  const msg = el('p', 'nota-dir', 'Opcional. Sale en la página pública de esta carrera, junto a tu nombre. Puedes quitarla cuando quieras.');
  const di = t => { msg.textContent = t; };
  const mandar = async (cuerpo, quitando) => {
    try {
      const r = await fetch('/api/invitado/foto', { method: 'POST', credentials: 'same-origin',
        headers: Object.assign({ 'X-Ident': ident, 'Content-Type': 'image/png' }, quitando ? { 'X-Quitar': '1' } : {}), body: cuerpo });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.error || 'No se pudo guardar la foto.');
      di(quitando ? 'Foto quitada.' : 'Foto guardada: ya sale en la carrera.');
      if (alCambiar) alCambiar();
    } catch (e) { di(e.message || 'No se pudo guardar la foto.'); }
  };
  subir.addEventListener('click', () => entrada.click());
  quitar.addEventListener('click', () => mandar(new Blob([]), true));
  entrada.addEventListener('change', () => {
    const f = entrada.files[0]; if (!f) return;
    const img = new Image();
    img.onload = () => {
      const lado = Math.min(img.width, img.height), cv = document.createElement('canvas');
      cv.width = cv.height = 256;
      cv.getContext('2d').drawImage(img, (img.width - lado) / 2, (img.height - lado) / 2, lado, lado, 0, 0, 256, 256);
      URL.revokeObjectURL(img.src);
      cv.toBlob(b => mandar(b, false), 'image/png');
    };
    img.onerror = () => di('No se pudo abrir esa imagen.');
    img.src = URL.createObjectURL(f);
    entrada.value = '';
  });
  cont.textContent = '';
  const acc = el('div', 'acciones'); acc.append(subir, quitar);
  cont.append(entrada, acc, msg);
};
