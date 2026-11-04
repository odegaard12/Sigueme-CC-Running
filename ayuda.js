// Un «?» junto a cada apartado del panel y de Mis carreras: dos líneas que dicen qué hace y qué poner.
// Se pone sobre los títulos que ya existen (por su texto) y sobre los pasos numerados de una ruta. Sin datos de nadie.
'use strict';
(function () {
  const TITULOS = {
    // panel
    'El día de la carrera': 'Lo que pasa el día de la carrera. Con la app de Android o con Traccar la carrera arranca sola; «Empezar a seguir ahora» es solo por si quieres empezar a mano.',
    'Estado': 'Cómo va la carrera: si está en marcha, desde cuándo y si llegan puntos de tu móvil. La hora de llegada solo se pone si el directo se cortó.',
    'Sin la app': 'Traccar es la app gratis para iPhone (o para Android sin la app Sígueme CC). Escanea el QR desde Traccar o copia la dirección y el identificador. El reloj Amazfit va aparte.',
    '¿Qué móvil llevas?': 'Elige iPhone o Android y solo verás lo tuyo. iPhone: Traccar sigue tu posición y los avisos de subidas llegan como notificación de la web instalada. Android: lo hace todo la app Sígueme CC.',
    'Avisos de subidas en tu iPhone': 'En iPhone no hay app. La web instalada en la pantalla de inicio te manda una notificación en cada subida, cima y último km, y tu pulsera la repite. Solo llega con cobertura.',
    'Preparar la carrera': 'Los pasos para dejarla lista: datos, ruta, avituallamientos y avisos. Lo que falta sale marcado.',
    'Datos de la carrera': 'Nombre, día y hora de salida (el tiempo cuenta desde que empiezas a correr, no desde esa hora), límite de tiempo y la distancia oficial si la sabes. La dirección de archivo es «año-nombre».',
    'Ruta (GPX)': 'El fichero de la ruta (de Strava, Komoot, Wikiloc o de la organización). De él salen el perfil, las subidas y los avisos. Ojo: la distancia de la ruta no es la que corres; el resultado usa la medida de tu reloj.',
    'Avituallamientos': 'Nombre y kilómetro de cada uno. Salen en el mapa. Si la organización no dice dónde están, déjalo vacío.',
    'Perfil y avisos': 'Los avisos de subidas, cimas y último km que llegan a la pulsera. «Avisa antes» es cuántos metros antes. En Android los lanza la app (también sin cobertura); en iPhone, la web instalada (con cobertura).',
    'App del móvil': 'Solo Android. Escanea el QR con la cámara: abre una página que instala y configura la app Sígueme CC.',
    'Que los avisos lleguen': 'La app de tu reloj (Mi Fitness, Zepp, Huawei Health) tiene que dejar pasar las notificaciones de «Sígueme CC». Pulsa «Probar aviso» una vez para que aparezca en su lista.',
    'Resultado de la carrera': 'Sube el fichero de tu reloj (FIT o GPX): da tu tiempo real desde que empiezas a correr, la distancia medida y el pulso. Con Strava: la actividad → ⋯ → Exportar GPX (en la web de Strava). Mejor el del reloj que el del móvil: guarda un punto por segundo.',
    'Archivar': 'Cuando el resultado esté bien, pasa la carrera a «Carreras» y deja la portada libre para la siguiente. Antes pon la dirección de archivo («año-nombre») en Datos.',
    'Mis carreras': 'Tus carreras y tus carreras en directo, igual que las de un invitado.',
    'Rutas publicadas': 'Lo que han publicado tus invitados. Puedes quitarlo de la web o borrarlo.',
    'Carreras en directo': 'Carreras con varios corredores, creadas por tus invitados o por ti. Quita las que no deban estar.',
    'Invitados': 'Un usuario y un código que caduca, para que un amigo prepare sus rutas y carreras sin ver tu panel. «Sin caducidad» es para tu propia cuenta.',
    'Avanzado': 'Ajustes poco habituales. Si no sabes qué es, no lo toques.',
    // Mis carreras
    'Tus carreras': 'Las carreras (rutas) que has subido. «Abrir» para editarla, llevártela al reloj, publicarla o correrla en directo.',
    'Subir una ruta': 'Sube el GPX de una ruta. Se prepara sola: perfil, subidas y avisos.',
    'Carreras en las que te puedes apuntar': 'Carreras en directo de otros que aún no han acabado. «Apuntarme» te mete con tu nombre; luego, en «Mi móvil y mi foto», deja listo tu móvil y saldrás en el mapa. Si no corres al final, «Retirarme» te quita del mapa.',
    'Tus carreras en directo': 'Las carreras que has creado o en las que corres. «Invitar» manda el enlace a quien corra contigo; «Mi móvil y mi foto» deja la app o Traccar listos y tu foto; «Retirarme» si al final no corres (y «Volver a la carrera» si fue sin querer).',
  };
  const PASOS = {
    1: 'El GPX sale de Strava, Komoot, Wikiloc o de la web de la carrera.',
    2: 'Pon nombre y kilómetro de cada avituallamiento solo si sabes dónde está. Sirven de puntos de control en el reloj.',
    3: 'Se detectan solas con el perfil del GPX: no hay que hacer nada.',
    4: 'Descarga el GPX y ábrelo con la app de tu reloj (Mi Fitness, Zepp, Huawei Health…). No todos los modelos admiten rutas: mira la guía de tu marca.',
    5: 'Solo publica la ruta (mapa y GPX) para que otros se la lleven al reloj. No tiene que ver con el directo.',
    6: 'Elige día y hora de salida y la carrera sale en la portada. Antes del día: «Mi móvil y mi foto» e «Invitar» a quien corra contigo. El día de la carrera solo enciende el móvil.',
  };
  function poner(ancla, texto) {
    if (ancla.querySelector(':scope > .ayuda-q')) return;
    const b = document.createElement('button'); b.type = 'button'; b.className = 'ayuda-q'; b.textContent = '?';
    b.setAttribute('aria-label', 'Qué es esto'); b.setAttribute('aria-expanded', 'false');
    const t = document.createElement('div'); t.className = 'ayuda-txt'; t.textContent = texto; t.hidden = true;
    b.addEventListener('click', () => { t.hidden = !t.hidden; b.setAttribute('aria-expanded', String(!t.hidden)); });
    ancla.append(b); ancla.after(t);
  }
  document.querySelectorAll('h2').forEach(h => {
    if (h.id === 'guia-titulo' || h.id === 'r-nombre' || h.id === 'r-titulo') return;
    const nombre = h.textContent.trim();
    const k = Object.keys(TITULOS).find(x => nombre === x) || Object.keys(TITULOS).find(x => nombre.startsWith(x));
    if (k) poner(h, TITULOS[k]);
  });
  document.querySelectorAll('.paso').forEach(p => {
    const n = p.querySelector('.n'); const txt = n && PASOS[Number(n.textContent)];
    if (txt) poner(p, txt);
  });
})();
