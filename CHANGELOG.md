# Cambios

Versiones con [SemVer](https://semver.org/lang/es/): la última cifra para
arreglos, la del medio para funciones nuevas. Cada una tiene su etiqueta y su
release en GitHub.

## v1.13.9 · 2026-10-19
- **Réplica entre las dos Pis (`despliegue/replicar.sh`):** si la IP flotante
  cambiaba de Pi justo cuando empezaba una copia, la copia llegaba después y
  machacaba los datos nuevos del titular (y con `--delete`, una carrera recién
  archivada). Ahora la Pi de destino se niega si es ella la que tiene la IP.
  Probado: sin la protección la copia entra; con ella, se rechaza.
- Un corte de red a mitad de una copia ya no la deja colgada horas sin
  avisar: `rsync --timeout=30`, ssh con `ServerAlive` y `TimeoutStartSec` en
  el servicio.

## v1.13.8 · 2026-10-18
- **Idas y vueltas por el mismo camino:** si el GPS se perdía unos minutos
  cerca del giro y volvía ya en la vuelta, la app se situaba en el mismo sitio
  de la ida y el km iba hacia atrás el resto de la carrera, sin avisos de la
  vuelta. Ahora busca primero hacia delante y solo retrocede (0,5 km) si no
  encuentra nada. Con su prueba.
- Entre 975 y 999 m la distancia salía «en 1000m»; ahora «en 1,0km».
- **Reloj Amazfit:** con la cola llena (más de ~4 h sin móvil o sin red), los
  puntos que llegaban mientras se enviaba un lote hacían borrar, al
  confirmarse el envío, puntos que no se habían mandado (en el reloj y en el
  lado del móvil). Ahora se quita exactamente lo enviado.

## v1.13.7 · 2026-10-18
- **Dependencias al día** (las PRs de Dependabot, probadas con el emulador y
  la carrera de prueba): actions/checkout 7, actions/setup-java 6,
  gradle/actions 6, actions/upload-artifact 7 y org.json 20260814 (solo para
  las pruebas). El salto a Android Gradle Plugin 9 y Kotlin 2.4 queda aparte:
  son cambios mayores y piden su propia prueba.
- **CI también en las PRs:** pruebas y APK de depuración, para que las
  próximas de Dependabot lleguen ya probadas.
- La guía y el README al día con la app: busca sola Zepp, Mi Fitness o Zepp
  Life, el aviso de prueba llega a los 5 s y el plan se pone al día solo.

## v1.13.6 · 2026-10-18
- **La app con el mismo criterio de diseño que la web:** el estado en frase
  normal («Siguiendo», «Parado») y «Listo para salir» como título, no en
  mayúsculas pequeñas espaciadas; las tarjetas y los botones sin borde fino
  (se separan por tono); el km en grande (76 sp); «Parar seguimiento» como
  botón relleno en rojo apagado en vez de una caja con borde; sin emojis y
  nada de texto por debajo de 14 sp.
- Banco de pruebas del emulador: cierra los avisos del propio sistema
  («Pixel Launcher no responde») que a veces tapaban la app.

## v1.13.5 · 2026-10-18
- **Las pruebas, en el repo y en cada cambio:** `pruebas/` (lector de GPX,
  panel y seguridad del servidor, ensayo de una carrera entera, carga con 60
  espectadores y la web en un móvil lento) y un flujo de GitHub Actions que
  las corre en cada cambio. Usan un GPX inventado, nunca una ruta real.
- **Índice de carreras nuevo:** título grande y cada carrera con el dibujo de
  su propio recorrido, su tiempo destacado y una entrada suave de las filas.
- **Arreglado:** un `carrera.json` archivado que no fuera un objeto (`null`,
  una lista, una fecha numérica) tumbaba el índice y también la portada
  cuando no hay carrera en marcha. Con su prueba.
- **Página de instalación:** en iPhone o en el PC el botón principal era un
  enlace que solo entiende Chrome en Android; ahora allí explica que la app
  es para Android y enseña el identificador para usarlo en Traccar Client.

## v1.13.4 · 2026-10-18
- **Panel revisado con el mismo inspector** (de 10 fallos a 0): los títulos
  sin numeración («Datos de la carrera», no «1 · Datos…»; el orden ya lo da
  la página), la píldora de estado en frase normal, las tarjetas y botones
  sin borde fino (se separan por tono), el botón de elegir el GPX con la piel
  del panel, sin halo degradado en el fondo y sin ✓/⚠ en los mensajes.
- **Pantalla de resultado:** el titular «Terminada en…» bastante más grande
  (es lo primero que se mira), la cabecera dice «21,1 km de 21,10» en vez de
  «(prev. 21,10)» y, si el FIT no trae parciales, ya no sale el título «Paso
  por los avituallamientos» con nada debajo.
- App y panel hablan ya de Zepp o Mi Fitness (no solo Mi Fitness) y de la
  pestaña Móvil.

## v1.13.3 · 2026-10-17
- **Revisión de diseño con un inspector en navegador real** (tasteskill): de
  28 fallos a 0 en el código y de 6 a 3 en la página (los 3 que quedan son de
  una web de presentación, no de una pantalla de seguimiento: fotos, vídeo y
  tamaño de párrafo).
- Fuera los adornos sin función: el halo verde del fondo, el degradado de la
  barra de progreso, el desenfoque de las casillas, las rayas finas y los
  bordes de 1 px (las superficies se separan por tono), la sombra del dorsal
  y el resplandor de la foto del corredor.
- Sin emojis en la interfaz: meta «M» y asistencia «T» en las chinchetas,
  «pulso» en vez de ♥ y textos sin 🏁/📡.
- **Más legible:** nada por debajo de 13 px (leyenda, datos de la ruta,
  créditos), la pendiente aclarada (las bajadas, azul oscuro sobre negro, se
  leían a 2,2:1) y los créditos a un ancho de lectura.
- Se mantiene lo que flota sobre el mapa (sombras de chinchetas, botones y
  el velo del perfil) y la escala de color de la pendiente, que es un dato.

## v1.13.2 · 2026-10-17
- **Diseño más limpio en la web:** las cifras se separan por tono de fondo y
  no por bordes finos; las etiquetas y títulos van en frase normal, no en
  mayúsculas pequeñas espaciadas; las cifras son más grandes y, en el PC, el
  tiempo ocupa su propia fila (la columna de datos quedaba medio vacía). Antes
  de la salida, la hora sale en grande: «Sale a las 10:00 · sábado 17/10».
- **Servidor:** quien cierra la pestaña a mitad de una respuesta ya no deja
  un error en el registro (tapaba los errores de verdad).
- **Repositorio más seguro:** escaneo de secretos con bloqueo al subir,
  alertas y arreglos automáticos de Dependabot (también para las Actions y
  Gradle), la rama principal sin «force push» ni borrado, las Actions con
  permisos de solo lectura salvo el paso que publica la APK, y `SECURITY.md`
  con cómo avisar de un fallo en privado.

## v1.13.1 · 2026-10-17
- **Banco de pruebas con el servidor real:** en cada cambio de la app, el
  emulador corre una carrera de 3 km contra el servidor de verdad: baja el plan
  solo al abrirse, EMPEZAR pone en marcha la web, la mitad del recorrido va en
  modo avión y, al volver la red, la cola se vacía, la web da la meta y sale el
  aviso del avituallamiento (`android/prueba/carrera.sh`). La versión de
  pruebas habla por http con el servidor del banco; la APK publicada no.
- **App sin cobertura:** la cola de posiciones se lee una vez y se limpia de
  golpe (antes, tras horas sin red, se reescribía entera por cada lote y podía
  congelar la pantalla); sin red, la espera entre intentos crece de 20 s a
  5 min (batería y radio) y, en cuanto Android avisa de que vuelve la
  cobertura, la cola sale al momento.
- **Servidor con muchos espectadores:** con una simulación de ~1000 personas
  mirando a la vez rechazaba conexiones (solo admitía 5 en espera); ahora 128
  y ningún error.

## v1.13.0 · 2026-10-17
- **La web carga antes:** la librería del mapa (800 KB) ya no frena el resto.
  Medido en un móvil lento con 4G floja, la primera visita enseña los datos a
  los 2,7 s en vez de a los 9 s; el mapa llega detrás. Si la librería no
  carga (sin red), sale el aviso de mapa roto en vez de un recuadro negro.
- **La app busca la app de la pulsera:** reconoce Zepp (Amazfit), Mi Fitness y
  Zepp Life (Xiaomi) y Gadgetbridge, comprueba que tenga «Acceso a
  notificaciones» y dice qué activar y dónde («Listo para salir» → Arreglar).
  Sin ninguna, ofrece instalar Zepp o Mi Fitness.
- **Aviso de prueba más realista:** llega a los 5 s, para dar tiempo a
  bloquear el móvil (muchas apps solo pasan avisos con la pantalla apagada), y
  ofrece abrir la app de la pulsera.
- **Sin cobertura en la salida:** el plan se pone al día solo cada vez que se
  abre la app con red, y la lista dice cuándo se guardó. Volver a abrir la app
  a mitad de carrera ya no pone el km a 0.
- La app ya no relee y analiza el plan entero cada 2 s (pantalla más ligera).
- Página de instalación: el botón baja el APK directamente y explica lo de la
  pulsera y el iPhone (Traccar).

## v1.12.7 · 2026-10-17
- **Desnivel inflado por el ruido del GPS:** con un punto cada pocos metros, el
  ruido de la elevación se contaba como subida (300 m reales salían 450 con
  1 m de ruido, y más de 2000 con 2 m). Ahora se suaviza ±50 m antes de contar.
- Un GPX con la elevación escrita con coma («12,5») o vacía ya no pierde los
  puntos: solo se pierde esa elevación. Antes se rechazaba el fichero entero.
- Un GPX en UTF-16 sin marca de orden de bytes ya no se cuela por el filtro de
  declaraciones DOCTYPE/ENTITY.

## v1.12.6 · 2026-10-17
- **Archivar ya no puede dejar un archivo a medias:** se llena en una carpeta
  oculta y se mueve de golpe. Antes, un fallo a mitad (tarjeta llena) dejaba
  una carpeta coja que bloqueaba los reintentos con «ya hay una carrera
  archivada», y dos toques a la vez daban un error 500.
- `generar_resultado.py` desde la consola escribe el resultado entero o nada:
  quien abría la web en ese momento podía leer un JSON cortado.

## v1.12.5 · 2026-10-17
- **Empezar con un enlace de LiveTrack arrastraba la carrera anterior:** los km y
  el pulso medio de una prueba en casa (o de la última carrera) se sumaban a los
  de la nueva, y tras «Finalizar» sin hora de salida el crono contaba desde días
  atrás. Ahora una carrera nueva empieza de cero también por esa vía.
- **Panel:** se pueden guardar los datos de la carrera sin hora de salida (antes
  fallaba todo el formulario); «Generar identificador nuevo» y «Archivar»
  avisan si no hay conexión o el servidor falla, en vez de quedarse callados;
  los botones se bloquean mientras se guarda, para que dos toques no suban la
  ruta ni archiven dos veces.

## v1.12.4 · 2026-10-16
- **Meta falsa con un lote repetido:** si la app reenviaba un lote que ya había
  llegado (se perdió la respuesta) y traía los puntos de la salida, junto a la
  meta, la carrera se daba por terminada con tiempo 0. Ahora solo cuentan los
  puntos nuevos. Lo destapó una medición de la web en un móvil simulado.
- **App, carreras largas:** un plan a medio escribir ya no deja la app sin
  avisos toda la carrera (se escribe entero o nada y, si falla, se queda el
  anterior); ante «identificador no válido» o «demasiados intentos» deja de
  insistir en vez de alargar el bloqueo; en meta avisa y se para sola a los
  15 min; avisa si se apaga el GPS o falta el permiso; los envíos no se
  amontonan con mala cobertura y la cola se reescribe sin riesgo; avisa antes
  de empezar si las notificaciones están apagadas; no se cierra si una
  respuesta llega con la pantalla cerrada; consejo para Samsung («Apps que
  nunca se suspenden»); hora de salida «9:00» aceptada.
- **Web, carreras largas:** el directo ya no se puede quedar congelado si una
  respuesta se corta a medias; un dato vacío pasajero no borra lo pintado; el
  aviso de «no se pudo cargar el mapa» vuelve a salir y el mapa recupera sus
  reintentos tras un rato funcionando; los lectores de pantalla no repiten el
  estado cada 5 s; el resultado sin traza o sin pasos no rompe la vista; la
  repetición no se clava tras un hueco largo; el perfil no se repinta al mover
  la barra del navegador; en meta sin hora del servidor el tiempo final no
  sigue creciendo; píldora «Antes de salir» con la carrera preparada.
- Sin errores en la consola del navegador (antes, un 404 de resultado.json en
  cada visita).

## v1.12.3 · 2026-10-16
- **Llegada a meta más fiable:** tras un corte de cobertura, la cola trae el
  paso por meta y lo de después; ahora se mira punto a punto y vale la hora del
  paso real. Nunca hay «llegada» antes de la salida oficial (con EMPEZAR antes
  de la hora y la salida junto a la meta, llegar a la salida contaba como meta).
  El punto de meta se vuelve a leer si cambia la ruta (antes quedaba el de la
  carrera anterior hasta reiniciar).
- **Seguridad:** las claves falsas sin cabecera Origin no sumaban al bloqueo
  por fuerza bruta; ahora sí.
- **Portada:** con una carrera preparada para hoy o más adelante, la portada es
  esa carrera (antes llevaba al último resultado hasta pulsar EMPEZAR).
- La vista previa al compartir (WhatsApp) sale con el dominio de cada uno.
- El servidor arranca sin `curl_cffi` (solo lo necesita iGPSPORT) y crea el
  identificador de los móviles al primer arranque.
- Miniapp de Amazfit: sin dirección por defecto (cada uno pone la de su web) y
  sin perder puntos pendientes al cerrar Zepp.
- Más robusto: el lector de iGPSPORT no escribe después de pararlo ni arranca
  dos veces; «Simular» no machaca una carrera en marcha; sin ruta no se
  publica la posición si hay zona privada; nombres con «\» o tiempos vacíos ya
  no rompen el archivo; entradas raras (horas NaN, cookies absurdas) no dan error.
- Documentación al día: requisitos, cómo crear y cambiar el identificador,
  nombres de botones, la app como opción principal, despliegue paso a paso.

## v1.12.2 · 2026-10-16
- **Avisos legibles en la pulsera** (Xiaomi Band con Mi Fitness, relojes
  Amazfit con Zepp): el título dice lo importante («Subida larga en 300 m»,
  «Avituallamiento en 200 m», «Cima», «Km 12») en vez de repetir «Sígueme CC»;
  el cuerpo lleva los números con espacio («1,2 km · 7 % · +84 m») y lo de
  «rampa» o «quedan +X m» en su propia línea. La distancia a la subida se
  calcula al avisar, como la del avituallamiento.
- La app enseña el último aviso con el mismo formato, y el km como «1,5 de 5,0 km».
- Historial del repositorio limpio de datos de la carrera real (ruta,
  avituallamientos y capturas viejas), sin cambiar el código.

## v1.12.1 · 2026-10-16
- **Ejemplo sin datos reales:** la ruta, el perfil y los avituallamientos de
  ejemplo son ahora un bucle inventado de 21 km; el código ya no nombra ningún
  sitio (el popup de salida usa el lugar de cada carrera) ni centra el mapa en
  una zona concreta.
- Salida y meta: dos banderas si no son el mismo sitio.
- Servidor: un GPX sin altura deja el plan de avisos vacío (antes quedaba el
  de la carrera anterior y la app lo bajaba) y quita el D+ viejo; carrera.json
  con BOM se lee bien y uno roto ya no se sobrescribe; guardados simultáneos
  sin pisarse; la fecha se guarda siempre como AAAA-MM-DD; la hora oficial, en
  la zona de la carrera; EMPEZAR repetido pasada la medianoche no reinicia la
  carrera; /api/plan con su propio contador de fallos; el marcado de taller y
  los textos de avisos cambiados a mano se conservan al guardar.
- Resultado: FIT con datos raros no da error mudo, y los largos se procesan
  mucho más rápido.
- Web: la línea recorrida sale aunque no llegue un dato nuevo; sin
  avituallamientos el mapa encuadra la ruta; las métricas ya no tapan la
  pantalla mientras cargan; cabecera sin cortes en móviles estrechos.
- Panel: el sondeo se para al caducar la sesión.
- App: volver a pulsar EMPEZAR a mitad de carrera sigue donde iba (antes, desde
  el km 40, dejaba de dar avisos); una línea rota en la cola ya no la tumba;
  girar el móvil no la cierra; un identificador viejo no se reintenta sin fin;
  PARAR no pone después la carrera en marcha; avisa si Android la detiene.

## v1.12.0 · 2026-10-16
- **Resultado desde el panel:** se sube el FIT (pestaña «Más») y la web pasa a
  modo resultado; si el FIT no vale (no llega a meta, es de otra carrera), dice
  por qué. Ya no hace falta la consola en ningún paso.
- **Ficha del corredor nueva:** foto, dorsal como un dorsal de carrera, club y
  categoría, y la carrera en casillas (modalidad, distancia, desnivel, salida,
  límite).
- **Foto del corredor desde el panel:** se recorta y se reduce en el navegador
  (sin datos EXIF) y la web la refresca sola.
- **Panel coherente:** la hora de salida está en un solo sitio (los datos de la
  carrera); en «Hoy» sale primero lo que toca (empezar, o el estado en carrera);
  Traccar y Amazfit quedan plegados como alternativa a la app.
- Modo resultado sin casillas vacías de pulso o cadencia, y la barra llena.
- Capturas nuevas en el README (móvil, PC y panel).

## v1.11.0 · 2026-10-16
- **Todo desde la app:** EMPEZAR pone también la carrera en marcha en la web
  (sin abrir el panel) y baja el plan al día. Sin cobertura en ese momento, lo
  reintenta sola con cada envío. Solo el día de la carrera (otro día es una
  prueba y la web no cambia) y una vez (pulsar otra vez no la reinicia).
- **Empezar antes de la hora:** si se pulsa a las 09:45 para salir a las 10:00,
  la web dice «En la salida» y el crono cuenta desde las 10:00; la app no da
  km ni avisos hasta la hora oficial. Se activa y se deja en el bolsillo.
- **Menos códigos QR:** tras instalar la app se vuelve a la misma página para
  abrirla (sin escanear otra vez), y no hace falta volver a escanear en cada
  carrera.
- **Web rediseñada:** estado arriba de un vistazo (En directo, En la salida,
  Sin cobertura, En meta), números grandes, barra de progreso, mapa de borde a
  borde en el móvil, previsiones en tarjeta; leyenda solo con los tipos de
  avituallamiento que tiene la carrera, sin textos propios de MTB.
- **Panel rediseñado** en pestañas (Hoy · Preparar · Móvil · Más), con el
  estado de la carrera arriba y lo importante primero en cada pestaña.

## v1.10.0 · 2026-10-16
- **App rediseñada** con los colores de la web: tarjeta con el km, la barra de
  progreso y el último aviso; botón grande para empezar o parar; lista «Listo
  para salir» (servidor, plan, ubicación, notificaciones, batería, aviso de
  prueba) en la que cada fila lleva a arreglarlo. Se refresca sola.
- **Ida y vuelta por el mismo camino:** el km podía saltar a la vuelta y se
  perdían los avisos de en medio; ahora vale la primera pasada.
- La pantalla ya no dice «Siguiendo» si Android cerró la app; el servicio se
  relanza solo si lo matan y sale limpio si Android no le deja arrancar.
- Un plan actualizado en plena carrera se usa al momento.
- La notificación fija se actualiza una vez por minuto (antes cada 5 s).
- Solo servidores https; avisa si las notificaciones están apagadas.
- Prueba en un emulador Android 14 en GitHub Actions: instala la app, simula
  el GPS por una ruta y comprueba que los avisos salen de verdad.

## v1.9.0 · 2026-10-16
- **App Android Sígueme CC** (`android/`, Kotlin sin librerías, Android 8 o
  superior): sigue tu km con el GPS del móvil con la pantalla apagada, lanza los
  avisos del plan como notificaciones (Mi Fitness las pasa a la pulsera) **sin
  cobertura**, y guarda cada posición para mandarla a la web cuando vuelve. Por
  estado: tras un rato sin GPS sale el aviso de ahora, no los atrasados.
  Botones para probar un aviso y quitar el ahorro de batería.
- GitHub Actions compila la app, pasa sus pruebas y sube el APK firmado a cada
  release (firma fija: las versiones nuevas se instalan encima).
- El QR del panel lleva a `app.html` de tu web, que instala la app y la abre ya
  configurada; el identificador va tras «#» y no llega a ningún registro.

## v1.8.0 · 2026-10-16
- **La carrera se prepara entera desde el panel**, sin consola: datos de la
  carrera, subir el GPX (trazado y perfil), avituallamientos y plan de avisos
  (ajustes «avisar antes» y «resumen cada», textos editables). Todo validado en
  el servidor y bloqueado con una carrera en marcha.
- **Avisos sin cobertura:** el servidor ya no los manda (fuera ntfy). El plan
  lo baja la app del móvil por `/api/plan` con el identificador del GPS, y el
  panel enseña el código QR para configurarla. La app Android, en la siguiente
  versión.
- **Web sin cobertura:** «Sin cobertura desde las HH:MM (km X)», marca
  transparente con la posición estimada a su ritmo medio, y hora prevista al
  próximo avituallamiento y a meta.
- Avisos: una subida con un llano delante empezaba en el llano y se descartaba
  por falso llano (una rampa de 400 m al 17 % medía 3 km al 2 %); la bajada ya
  no cuenta el llano del final; la subida que empieza en la salida avisa en el
  km 0.
- Al subir una ruta más corta se quitan los «km mínimos para dar meta» de la
  carrera anterior (la llegada no se habría detectado nunca).
- `desplegar.sh` copia también carpetas (`herramientas/`, `lib/`).

## v1.7.0 · 2026-10-16
- **Avisos de desnivel a la pulsera:** `herramientas/plan_avisos.py` calcula
  desde el perfil las subidas (larga, corta y dura, rampa), su mitad, la cima con
  la bajada y el D+ que queda, los avituallamientos, resúmenes, la última subida
  y el último km. En carrera el servidor sigue tu km de ruta y manda por ntfy el
  aviso que toca; tras un corte de cobertura manda el estado de ahora, nunca
  avisos atrasados. La distancia al avituallamiento se calcula al enviarlo.
- Panel: lista «Preparar la carrera» (qué está listo y qué falta) y tarjeta
  «Avisos a la pulsera» con aviso de prueba.
- Guía visual `docs/GUIA-CARRERA.md` para preparar una carrera, comprobada con
  un ensayo completo (GPX → plan → carrera simulada con corte → meta → archivo).
- Las carreras archivadas guardan también su plan de avisos.

## v1.6.0 · 2026-10-15
- **Carreras por carpetas:** cada carrera terminada se archiva (botón en el
  panel) en `carreras/<año-nombre>/` y se ve en `/<año-nombre>/` con la misma
  web en modo resultado, sin sondear nada.
- Índice de todas las carreras en `/carreras/` (fecha, lugar, tiempo,
  distancia y desnivel) y enlace «Todas las carreras» al pie.
- Sin carrera en marcha, la portada redirige (302) al último resultado: los
  enlaces viejos siguen sirviendo y la portada vuelve a ser la carrera en
  cuanto empieza la siguiente.
- Compartir comparte la página en la que estás; cada carrera archivada tiene su
  título y su vista previa.

## v1.5.0 · 2026-10-15
Auditoría externa:
- Panel: bloqueo de 15 min por IP real tras 10 fallos (sin bloquear al dueño),
  comprobación de origen (CSRF) y robots.txt sin anunciar rutas.
- GPS: identificador nuevo de 32 caracteres desde el panel; puntos de hace más
  de un día descartados.
- Errores en español con página propia; el servidor ya no se anuncia.
- CSP en la web (scripts por hash; teselas de Esri y AWS).
- `live.json` público sin enlace de iGPSPORT, batería ni datos internos;
  `ocultar_m` en carrera.json para no publicar la posición junto a casa.
- Con resultado: sondeo cada minuto en vez de cada 5 s y live.json cacheable
  3 s; cabecera con distancia y desnivel REALES (previstos entre paréntesis);
  media en movimiento y media total; título y vista previa «Resultado · …».
- Atribución completa de las imágenes de satélite; avatar con texto alternativo.

## v1.4.0 · 2026-10-09
- Arreglado: en directo, antes de haber resultado, salía una caja vacía con el
  botón ▶ encima del mapa; y el aviso de salida llevaba un nombre fijo en vez
  del corredor de `carrera.json`.
- Legibilidad: etiquetas de los datos a 0,72 rem como mínimo (antes ~9 px) y
  créditos con contraste suficiente; «rpm media» en la cadencia.
- Accesibilidad: nombres y estado en los botones del mapa, la ficha y la
  repetición; foco visible con teclado; perfil con descripción; avisos de
  estado anunciados; menos movimiento si el sistema lo pide.
- Botones de 44 px, la muesca del iPhone en horizontal ya no tapa nada y al
  acabar la repetición se respeta la vista 2D/3D elegida.
- Panel: el resultado de «Guardar» siempre a la vista, sin doble envío, las
  pruebas que borran la carrera plegadas, el aviso de identificador mal copiado
  en rojo y textos sin aparatos concretos.

## v1.3.1 · 2026-10-09
- Capturas del README con la carrera de ejemplo.

## v1.3.0 · 2026-10-09
- **Para cualquier carrera:** nombre, fecha, hora de salida, distancia, límite,
  km mínimos para meta, corredor y bici salen de `carrera.json`; el código no
  nombra ninguna carrera.
- `herramientas/preparar_ruta.py`: crea la ruta y el perfil desde un GPX.
- `generar_resultado.py` toma la fecha, la hora y la distancia de `carrera.json`.
- README como guía paso a paso (preparar la carrera, arrancar, día de carrera,
  después); README del reloj con el estado en la tienda y la instalación.
- Plantillas de despliegue con nombres genéricos (`sigueme.service`,
  `SIGUEME_VIP`).

## v1.2.0 · 2026-10-09
- Botón de compartir en la cabecera (menú de compartir en el móvil, copiar el
  enlace en el PC) y vista previa con imagen al compartir el enlace.
- Seguridad (revisión): como mucho dos cálculos de clave a la vez (antes una
  ráfaga de logins podía agotar la memoria), usuario o cookie con «ñ» ya no
  rompen la petición, el freno a la fuerza bruta ya no bloquea al panel con
  sesión, conexiones lentas cortadas a los 20 s, rutas normalizadas y ficheros
  ocultos nunca servidos.
- Panel: un solo sondeo aunque se entre varias veces.
- robots.txt: el panel y la API fuera de los buscadores.
- Plantilla del servicio con `SIGUEME_VIP` activa (se había quedado comentada).

## v1.1.1 · 2026-10-09
- Licencia MIT.
- Ficha del repo en GitHub: descripción, web y temas.

## v1.1.0 · 2026-10-09
- Panel con **usuario y clave**; el servidor solo guarda el hash (scrypt), en un
  fichero que solo lee root. `python3 server.py --hash-clave` genera el hash.
- Sin datos personales: nombre de corredor «Odegaard12» y avatar O12 en vez de
  nombre real y foto.
- Versión visible al pie de la web. README con capturas, CHANGELOG y releases.

## v1.0.1 · 2026-10-09
- La IP flotante sale de la configuración del servicio (`SIGUEME_VIP`); sin
  ella, el servidor funciona como una sola máquina.
- `generar_resultado.py`: el FIT se pasa por argumento y la web se busca en la
  raíz del repo (desde `herramientas/` no encontraba el trazado).

## v1.0.0 · 2026-10-09
- La app pasa a llamarse **Sígueme CC**, con icono nuevo (también en el reloj).

## v0.7.1 · 2026-10-09
- Repo ordenado: README, plantillas de despliegue sin datos de la red y
  saltos de línea LF. Se despliega primero en la Pi que tiene la IP flotante.

## v0.7.0 · 2026-10-08
- Login real del panel: cookie de sesión HttpOnly firmada (12 h) en vez de
  guardar la clave en el navegador. Cabeceras de seguridad y CSP en el panel.

## v0.6.0 · 2026-09-28
- Alta disponibilidad sin perder datos: keepalived con `nopreempt`, la IP se
  queda donde está al volver una Pi y la réplica sale de la que la tiene.

## v0.5.1 · 2026-09-28
- Pasada de errores: lotes de Traccar con forma rara, puntos GPS locos, batería
  por URL, primera carga colgada, horas en hora de España.

## v0.5.0 · 2026-09-28
- Miniapp para relojes Amazfit (Zepp OS): posición y pulso del reloj a la web.
- Servidor: un solo origen de posición (móvil o reloj), pulso del reloj sobre el
  de iGPSPORT, velocidad calculada, aviso de identificador incorrecto.

## v0.4.1 · 2026-09-28
- Web fiable con mala cobertura: tiempo máximo por petición, una sola a la vez,
  aviso de conexión y puesta al día al volver.

## v0.4.0 · 2026-09-28
- Modo resultado: tiempo final, paso por avituallamientos y repetición de la
  carrera. Carga sin pantalla vacía y diseño para móvil, horizontal y PC.

## v0.3.0 · 2026-09-27
- GPS del móvil con Traccar Client, con cola sin cobertura. Convivencia con
  iGPSPORT, sensores caducados ocultos, carrera solo con Traccar, meta detectada
  aunque el seguimiento empiece a mitad y «Finalizar» con hora de llegada.

## v0.2.0 · 2026-09-24
- Seguimiento fluido pegado al trazado, cámara que sigue al corredor, mapa que
  se rehace solo si se cuelga y menos batería en el móvil de quien mira.

## v0.1.0 · 2026-09-24
- Primera versión: mapa 3D con la posición sobre el trazado, perfil,
  avituallamientos, panel y lector del directo de iGPSPORT.
