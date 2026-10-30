# Cambios

Versiones con [SemVer](https://semver.org/lang/es/): la última cifra para
arreglos, la del medio para funciones nuevas. Cada una tiene su etiqueta y su
release en GitHub.

## v1.47.0 · 2026-10-30
- **Avisos en el móvil de quien sigue la carrera:** campana en la cabecera de la página de la carrera; avisa de la salida, de cada avituallamiento y de la llegada a meta aunque la web esté cerrada (Web Push). En Android, en el navegador; en el iPhone, con la web instalada (Compartir → «Añadir a pantalla de inicio», iOS 16.4 o más). Sin ráfagas: si se juntan varios, solo el último.
- Solo envía la Pi con la IP flotante; el envío va con pywebpush en su propio entorno (~/sigueme-push) y el servidor sigue sin dependencias: sin ese entorno, la campana no sale. Suscripciones solo de servicios de avisos reales (Apple, Google, Mozilla, Microsoft), en un fichero oculto que no se sirve.
- Service worker propio para los avisos, aparte del de «sin cobertura»: apagar ese modo ya no borra las suscripciones.

## v1.46.1 · 2026-10-30
- **Repaso en el teléfono:** la barra del sistema (Android, Safari) sale oscura como la web, no lima; con la web instalada en el iPhone la cabecera del directo ya no queda debajo de la muesca; los chips de marcas de la portada del mismo tamaño que en las demás páginas.

## v1.46.0 · 2026-10-30
- **«Mis rutas» y el panel con el mismo diseño que la web:** cabecera oscura con la misma barra (adiós a la franja lima), enlaces en gris sin subrayar, el resumen de la carrera del panel en tarjeta oscura con el lima solo en la etiqueta y el botón, chips de marcas iguales y la guía de primera vez en tarjeta oscura con borde lima (antes, blanca).
- Capturas del repo al día.

## v1.45.0 · 2026-10-30
- **Un solo diseño en toda la web:** Carreras, Rutas y relojes, la guía de pulseras y la página de cada ruta dejan el bloque lima gigante y pasan al diseño oscuro de la portada y del directo (títulos, tarjetas, botones y chips iguales en todas).
- **Un solo menú:** «Inicio · Carreras · Rutas y relojes» arriba en todas las páginas, también en la página de cada carrera (cuenta como «Carreras»). Fuera los menús repetidos: «Inicio» en la cabecera del directo, enlaces del pie, «‹ Volver al inicio» y «‹ INICIO».
- Pie de la carrera sin el «·» colgando; hojas de estilo con versión nueva para que nadie vea la vieja de la caché.
- Capturas del repo al día.

## v1.44.2 · 2026-10-30
- **Guía de pulseras con las pestañas fijas** (Carrera · Carreras · Rutas y relojes), como el resto de páginas públicas. Auditoría en producción: sin enlaces rotos, todas las páginas y recursos en 200 y sin errores en el registro.

## v1.44.1 · 2026-10-30
- **Repaso del diseño nuevo:** el estado (sin cobertura, antes de salir, resultado) alineado con el título; el botón de la repetición visible (salía oscuro sobre oscuro); el aviso «antes de salir» sin bloque lima; el perfil de altitud ya no queda tapado por la hoja de datos; las cifras en la misma línea que las pestañas.
- **Capturas del repo al día** (`docs/capturas/`) con el diseño nuevo.

## v1.44.0 · 2026-10-30
- **Página en directo nueva («C»):** el mapa manda, a lo alto en el móvil y a la izquierda en el ordenador; los datos van en una hoja oscura con tres pestañas, **Resumen · Ritmo · Avituallamientos**, y el mapa se ve siempre (antes, la pestaña de datos lo tapaba). Cabecera oscura y compacta en vez de la franja lima.
- **Pestañas fijas en las páginas públicas:** Carrera · Carreras · Rutas y relojes, en la portada, en el índice de carreras y en Rutas y relojes.
- **Portada nueva:** la carrera (en directo, próxima o última) en una tarjeta grande con su botón; al lado en el ordenador, o debajo en el móvil, las últimas tres carreras y el acceso a Rutas y relojes con las marcas.
- Avisos (resultado y ayuda) sin bloques lima: fondo oscuro y el lima solo en el botón.

## v1.43.0 · 2026-10-30
- **Pantallas anchas alineadas:** en la página en directo y en la del resultado, el mapa, los datos, la ficha y la barra de la repetición usan el mismo margen que la cabecera (antes: mapa y datos en un bloque centrado de 1280 px y la barra de lado a lado, que en un monitor grande no parecían alineados).
- **«Mis rutas» alineada:** el logo, el título y el saludo van en la misma columna que las tarjetas.
- **Portada sin huecos:** debajo de la carrera, dos accesos claros, «Todas las carreras» (con cuántas hay) y «Rutas y relojes»; antes, con una sola carrera, quedaba todo vacío. El pie se queda en «Entrar (dueño e invitados)».

## v1.42.0 · 2026-10-30
- **Todo alineado:** un solo margen lateral en todas las páginas públicas (portada, rutas y relojes, carreras, guía de pulseras), el mismo que la página en directo: 16 px en el móvil y hasta 36 px en el ordenador. Antes se mezclaban 16, 18 y 22 px, y la guía de pulseras y «Llévala al reloj» iban en una columna centrada.

## v1.41.0 · 2026-10-29
- **Botón «?» de ayuda en la página en directo:** en la cabecera, junto a «Compartir». Vuelve a enseñar el aviso de «cómo leer esta página» cuando se quiera (antes salía una sola vez y no había forma de repetirlo).
- **Cabecera del móvil con sitio para todo:** el nombre «SÍGUEME CC» ya no se parte en dos líneas; «Mi ficha» enseña su texto solo desde 460 px de ancho (antes 380), y en pantallas estrechas queda solo la foto.

## v1.40.0 · 2026-10-29
- **Guía de primera vez y botón «? Ayuda» en «Mis rutas»** (el espacio de los invitados), como la del panel: la primera vez que entran se abre sola una visita de 5 pasos (bienvenida, subir el GPX, avituallamientos, llevársela al reloj y **su fecha de caducidad**, con lo que pasa al caducar), señalando cada cosa en pantalla. Se puede saltar o cerrar con Esc, no vuelve a salir sola y se repite con el botón «? Ayuda» de la cabecera.

## v1.39.1 · 2026-10-29
- **Capturas del repo con la portada nueva** (`docs/capturas/`): la portada con la carrera primero (ordenador y móvil), la página «Rutas y relojes» y el resto al día, con la carrera de ejemplo. Sin cambios de código.

## v1.39.0 · 2026-10-29
**La carrera primero.** Sígueme CC es una web de seguimiento; las rutas y los GPX son un extra y ya no ocupan la portada.
- **Portada (`/inicio`):** la carrera, con su estado («En directo», «Próxima carrera» o «Última carrera») y un botón grande («Ver en directo», «Ver la carrera» o «Ver el resultado»). Debajo, las carreras anteriores.
- **Nueva página «Rutas y relojes» (`/rutas`):** las rutas publicadas, los botones de marca (Xiaomi, Huawei, Amazfit, Garmin, Coros, Android, iPhone), el GPX de la carrera y la guía completa.
- **Menús más claros:** «Admin» sale del menú de las páginas públicas (queda como «Entrar», discreto, en el pie); el pie de la página en directo pasa de cuatro enlaces de rutas y relojes a uno, «Rutas y relojes».
- Los botones de «Rutas y relojes» y de la guía de pulseras se ven ahora sobre fondo oscuro (antes eran negros sobre negro).
- Pruebas actualizadas y nuevas para `/inicio` y `/rutas`.

## v1.38.1 · 2026-10-26
- **Capturas del repo al día** (`docs/capturas/`): el panel nuevo con barra lateral y resumen, la página en directo con la tarjeta de ritmo, el anillo del corredor y el rastro de cometa, la portada y las pantallas de ruta, todas con la carrera de ejemplo. Sin cambios de código.

## v1.38.0 · 2026-10-26
- **Cerrar sesión en el panel la cierra de verdad:** cada sesión lleva un identificador propio y «Cerrar sesión» lo revoca (en las dos Pis, por la réplica). Antes solo se borraba la cookie del navegador, y una cookie copiada seguía valiendo hasta 12 h. Las demás sesiones abiertas no se tocan, y las anteriores a esta versión siguen valiendo hasta caducar.
- **Solo la Pi titular recibe datos de carrera:** `/api/gps` y `/api/plan` contestan 503 en la Pi que no tiene la IP flotante (el móvil o Traccar guardan los puntos y reintentan, y los coge la titular), en vez de aceptarlos para que la réplica los borrara a los 20 s. Sin la IP flotante configurada, no cambia nada.
- Pruebas nuevas de ambas cosas.

## v1.37.0 · 2026-10-26
- **Ayuda de primera vez en la página en directo:** un aviso corto («esta página se actualiza sola; Datos y Ritmo tienen los números y la llegada prevista; Seguir lleva la cámara con el corredor») con botón «Entendido». Sale una sola vez en cada navegador.

## v1.36.0 · 2026-10-25
- **Pestañas en el móvil: Mapa · Datos · Ritmo.** Un control segmentado fino que se queda fijo arriba al bajar; menos scroll. En el PC sigue todo a la vez. Se recuerda la pestaña y el mapa recupera su tamaño al volver a él.
- **Cabecera con aire en el móvil:** un nombre de carrera largo en dos líneas, el estado, las cifras y la hora ya no van casi pegados.
- **Animaciones del mapa 3D** (todas respetan «movimiento reducido»):
  - **Vuelo de entrada:** al abrir una carrera en directo, la cámara recorre la ruta desde la salida hasta el corredor en unos 3 s y se queda siguiéndole. Si tocas el mapa, se corta.
  - **Rastro de cometa:** el último kilómetro recorrido brilla en la cabeza y se apaga hacia atrás, y un anillo late bajo la foto del corredor.
  - **Relieve vivo:** el relieve sube suave al abrir y las sombras del terreno siguen al sol de la hora real (de noche, casi sin sombras).
- **Miniapp para relojes Garmin (Connect IQ), EXPERIMENTAL** en `garmin/`: graba la actividad y manda posición y pulso a la web por el móvil, como la de Amazfit. **Sin compilar ni probar en un reloj real**; el servidor ya acepta su formato (probado). Instrucciones y limitaciones en `garmin/README.md`.
- La guía de Garmin lo menciona.

## v1.35.0 · 2026-10-25
- **Guías para todas las marcas y móviles**, con botones de marca (Xiaomi, Huawei, Amazfit, Garmin, Coros, Android, iPhone) arriba de la guía y en las pantallas de ruta (la pública y la de «Mis rutas»), que llevan directos a su tarjeta:
  - **Garmin** (nueva, separada de Coros): avisos desde Garmin Connect, importar la ruta como Curso en connect.garmin.com, por qué el LiveTrack de Garmin no vale para el directo (lo da el móvil) y cómo exportar el FIT original para el resultado.
  - **Coros** (tarjeta propia).
  - **Android**: instalar el APK de la última versión, configurar con el QR del panel y quitar el ahorro de batería.
  - **iPhone**: seguimiento en directo con Traccar Client y, dicho claramente, que todavía no hay avisos de subida ni de avituallamiento (no hay app para iPhone).
- La tarjeta de la marca elegida se resalta al llegar desde un botón.
- Nueva prueba `pruebas/guias.py`.

## v1.34.0 · 2026-10-25
- **Tarjeta de ritmo en la página en directo:**
  - **Ritmo medio** desde la salida («6:37 /km») y **llegada prevista** a la hora de meta, con un margen aproximado.
  - **Gráfico del ritmo de cada kilómetro** (los últimos 12): cuanto más alta la barra, más lento ese km; la última, resaltada. Con descripción para lectores de pantalla.
  - Sale solo cuando hay datos (desde el km 1) y se queda con la carrera terminada.
- **Servidor:** apunta a qué hora se cruza cada kilómetro (`km_t`, interpolada entre dos puntos GPS; no duplica con un lote reenviado) y lo publica en `/live.json`. Se borra al reiniciar o empezar otra carrera.
- Pruebas nuevas del cálculo de cruces por km.

## v1.33.0 · 2026-10-25
- **El resultado calcula el tiempo en movimiento, el desnivel, el pulso medio y la cadencia solo del tramo salida-meta.** Antes salían de toda la actividad grabada: con calentamiento, trayecto al coche o vuelta a casa en el fichero, la velocidad media y el D+ publicados no eran los de la carrera (en una prueba inventada, 6,7 km/h y 131 ppm en vez de 10,0 km/h y 160 ppm). Si el fichero es casi todo carrera (menos de un 5 % de más), se siguen usando los datos del reloj. Vale para FIT y GPX.
- **El historial no apunta dos veces el mismo punto GPS** cuando el móvil o el reloj reenvían un lote porque no les llegó la respuesta.
- Nueva prueba `pruebas/resultado_tramo.py`.

## v1.32.0 · 2026-10-25
App Android y CI tras la auditoría:
- **Un 403 de la red ya no bloquea el envío para siempre:** solo se considera «identificador no válido» (y pide volver a escanear) si el servidor lo dice; un 403 de un cortafuegos o de Cloudflare se reintenta a los 15 minutos, con su aviso propio.
- **Un lote que el servidor rechaza (400, 413, 422) ya no atasca la cola:** se descarta y se sigue con los de detrás.
- **La pantalla ya no lee el fichero de la cola cada 2 s:** solo lo cuenta cuando cambia de tamaño (con horas sin cobertura podía congelarse).
- **Enlace de configuración (`siguemecc://`):** solo vale con el dominio (sin ruta ni parámetros) y el aviso de confirmación enseña también el principio del identificador.
- **CI:** una etiqueta sin el secreto de firma falla en vez de publicar un APK firmado con la clave de depuración, que no actualiza a los ya instalados.

## v1.31.0 · 2026-10-25
Arreglos de cliente tras la auditoría:
- **Sin cobertura de verdad:** si el túnel o la Pi caen y devuelven un error 5xx, el service worker enseña la última copia guardada en vez de la página de error.
- **La ruta y el perfil se reintentan solos** (cada vez más espaciados) si fallan; antes, un fallo dejaba la web sin km hasta recargar. El resultado de la carrera tiene tiempo límite y ya no puede dejar la página congelada.
- **Movimiento reducido:** con esa opción del sistema, la cámara y la foto del corredor no se animan (antes solo algunos movimientos).
- **Portada:** un fallo de red ya no dice «todavía no hay rutas publicadas»; lo dice claro.
- **Ficha de una ruta:** sin WebGL el mapa se oculta en vez de quedar un recuadro vacío.
- **Botones táctiles de 44 px** (botones del mapa, pestañas del panel, avituallamientos) y marcas de avituallamiento con área pulsable más grande.
- **Panel:** la sesión caducada se detecta aunque el 403 no traiga JSON y también en Invitados; el sondeo no se solapa, tiene tiempo límite y se calla con la pestaña oculta; el foco del teclado no se pierde al repintar los pasos; la guía devuelve el foco al botón, no deja escapar el Tab y su marco sigue al scroll.
- **Reloj Amazfit:** un punto malformado o un envío colgado ya no bloquean las subidas para siempre, el móvil no duplica puntos si el reloj reenvía un lote, vale pegar el enlace de configuración también en el campo del identificador, se completa `https://` si falta, y el reloj no reescribe toda la cola en la memoria tras cada envío.

## v1.30.0 · 2026-10-25
Endurecimiento del servidor tras una auditoría completa:
- **Enlace de seguimiento (SSRF):** ya no se siguen las redirecciones, que podían llevar al servidor a pedir páginas de la red de casa.
- **Freno a la fuerza bruta:** un /64 de IPv6 cuenta como una sola persona y la tabla de intentos no puede crecer sin fin.
- **GPS:** los números infinitos o NaN ya no dejan `live.json` inválido para el navegador, un entero enorme no tumba el hilo, y adivinar el identificador de `/api/gps` tiene freno (30 malos por minuto).
- **`live.json` corrupto** (bytes nulos tras un apagón, `null`, una lista): se trata como vacío en vez de tumbar la web y todas las escrituras.
- **Invitados:** si la lista de usuarios no se puede leer, ya no se purga ni se crea nada (antes se podían borrar las rutas de todos).
- **GPX del resultado:** misma defensa que el de la ruta (sin DOCTYPE/ENTITY ni UTF-16).
- **Clave GPS:** se escribe de forma atómica y con permisos 0600; los temporales fallidos se borran.
- **Peticiones raras:** una línea de petición rota o una ruta con byte nulo ya no dejan trazas.
- Nueva prueba `pruebas/endurecimiento.py` con cada una de estas defensas.

## v1.29.0 · 2026-10-24
- **Textos de ayuda del panel más cortos:** las explicaciones de Carrera, Móvil (app, pulsera, Traccar y
  Amazfit), Preparar (ruta, reloj, avisos), Resultado, Archivar y Rutas dicen lo mismo con menos palabras:
  una idea por frase y el paso concreto primero.

## v1.28.0 · 2026-10-24
- **Guía de primera vez en el panel:** al entrar por primera vez se abre sola una visita de 5 pasos
  (bienvenida, resumen, los 5 pasos, «qué toca ahora» y listo), señalando cada cosa en pantalla. Se puede
  saltar o cerrar con Esc, no vuelve a salir sola y se repite con el botón «? Guía» de la cabecera.

## v1.27.0 · 2026-10-24
- **Panel de administración nuevo:**
  - Cabecera fina (antes, un «ADMIN» gigante que ocupaba un tercio de la pantalla).
  - En el PC, los cinco pasos van en una barra lateral que se queda fija; en el móvil siguen arriba, en pestañas.
  - Arriba del todo, el resumen de la carrera: estado, nombre, fecha, hora y km, un botón grande («Ir a empezar»,
    «Ver el directo» o «Subir el resultado» según toque) y cuatro cifras: listo, móvil, avisos a la pulsera y ruta.

## v1.26.0 · 2026-10-24
- **Seguimiento automático:** al abrir una carrera en directo la cámara ya va con el corredor
  (zoom cercano); si arrastras o haces zoom en el mapa, deja de seguir y respeta tu vista.
- **Botones del mapa con texto:** «Seguir» / «Siguiendo» (el icono late mientras sigue) y
  «Vista 2D» / «Vista 3D», en vez de un icono suelto y un «2D» críptico.

## v1.25.1 · 2026-10-24
- **Seguimiento más fluido:** con 🎯 la cámara va pegada al corredor en cada fotograma (antes, un
  movimiento por segundo que se reiniciaba a mitad y daba tirones); la foto se mueve a ~30 fps.
- **La portada no repite la carrera:** si una ruta publicada es la misma que una carrera
  archivada (mismo nombre y distancia), solo sale la carrera.

## v1.25.0 · 2026-10-24
- **Cabecera compacta** en la página en directo: ocupa mucho menos alto y deja el mapa a la vista.
- **Animaciones con sentido:** los números se resaltan un momento cuando cambian.
- **Cortes y reconexión:** aviso «Sin conexión · último dato hace N min · reintentando…» y, al volver la red, «Conexión recuperada ✓», que se va solo.
- **GPX de la ruta público** (`/ruta-carrera.gpx`, también de carreras archivadas) para cargarlo en cualquier reloj.
- **Guía «Pulseras y relojes»** (`/pulseras`): Xiaomi, Huawei, Amazfit y el resto.
- **Sincronizar sin teclear claves:** el panel copia un enlace de configuración y la miniapp de Amazfit lo acepta pegado.
- Las pruebas usan puertos libres.

## v1.24.0 · 2026-10-24
- **La página en directo, más clara:**
  - **Lo importante, donde se ve:** la frase de estado («Sin cobertura desde las
    11:57, en el km 9,0. A su ritmo estará ahora hacia el km 12 (la marca
    transparente del mapa)») pasa de debajo del mapa, fuera de pantalla en el
    móvil, a la cabecera, junto al estado.
  - **El botón de la ficha dice «Mi ficha»** también en el móvil (antes, un círculo
    sin texto) cuando cabe (desde 380 px de ancho).
  - **El perfil de altura lleva escala:** «Altura 900–1020 m · ruta 21,1 km».
  - **Los números, iguales en todas partes:** 21,1 km (antes «21,10» arriba y
    «21,1» en el resto) y 103,36 si hace falta; «tiempo de carrera» en vez de
    «tiempo».
  - **Antes de salir**, dice que la página se actualiza sola.
- **Mis rutas:** el texto de entrada separa lo del invitado (su acceso caduca y, pasada
  la fecha, se borra todo lo suyo) de lo del dueño; ya dentro, el invitado ve esa
  misma advertencia; y el botón de «elegir fichero» tiene el diseño de la web, en
  Mis rutas y en el panel (antes, el gris del navegador).
- Capturas del repo al día (página en directo, datos de la carrera con la casilla
  nueva y guía).

## v1.23.0 · 2026-10-23
- **La web en directo con cortes de cobertura:**
  - **El último dato se guarda en el móvil de quien mira** (siempre activo): si abre
    la web sin red, ve el último estado en vez de una pantalla vacía, y el aviso
    dice cuánto hace: «Sin conexión · último dato hace 12 min · reintentando…». Tras
    mucho rato sin red, la web pregunta menos (cada 15 s) para gastar menos batería.
  - **«Web que se abre sin cobertura» (experimental, casilla en Datos de la
    carrera; desactivada por defecto):** un service worker guarda la página, la
    ruta, el perfil y las teselas del mapa que ya se vieron, y la web se abre aunque
    no haya red. Probado en un navegador real: abrir, cortar la red, recargar, volve
    la red, y que una versión nueva del código llegue aunque lo tenga todo guardado
    (el fallo de las tres versiones antiguas). Lo vivo (`live.json`, `/api/`) nunca se
    guarda. Desactivada, la web funciona como siempre: sin service worker y
    desinstalando el que hubiera quedado de versiones antiguas.

## v1.22.0 · 2026-10-23
- **Xiaomi, Huawei y Amazfit:**
  - **Resultado desde un GPX:** además del FIT, el panel acepta el GPX que
    exportan Xiaomi Mi Fitness (Smart Band 8 Pro y otras), Huawei Health, Zepp o
    Strava, si trae la hora de cada punto: tiempo oficial, pasos por avituallamiento,
    pulso medio, desnivel y repetición (prueba nueva).
  - **Consejos por marca en la app:** la guía de «activar Sígueme CC en la pulsera»
    añade lo propio de Mi Fitness, Huawei Health y Zepp, y lo que hay que toca
    en móviles Xiaomi (HyperOS/MIUI) y Huawei/Honor, que cierran las apps en
    segundo plano.
  - **Ruta en el reloj:** las páginas de cada ruta explican cómo importarla en
    Amazfit con Zepp (GTR 4, GTS 4, Balance…) y avisan de que las Xiaomi Smart
    Band no importan rutas (se usan los avisos de la app).
- **Distancia oficial:** si cambias los km en el panel después de subir el GPX, el
  perfil y la ruta se reescalan y el plan de avisos se rehace; antes los avisos
  de la app y los km de la web quedaban en dos escalas y se desplazaban unos metros.
- **EMPEZAR sin cobertura y sin hora oficial:** el crono cuenta desde que se pulsó
  EMPEZAR, no desde que vuelve la cobertura (la app manda la hora; solo se acepta
  si es de las últimas 6 h).
- **Km en rutas con pocos puntos:** la app recibe la ruta con un punto como mucho
  cada 100 m. Con un GPX de ruta (pocos puntos) o una ruta de más de 300 km
  reducida a 1800 puntos, a mitad de tramo decía «fuera de la ruta» y el km
  avanzaba a saltos.

## v1.21.0 · 2026-10-23
- **Privacidad:** sin EMPEZAR (un día de prueba, o con el móvil en casa) la web
  ya no publica tu posición, y 15 min después de meta deja de moverse. Antes se
  veía en el mapa aunque el servidor dijera «otro día: la web no cambia».
- **Meta falsa en la salida:** con EMPEZAR en casa, los km hasta la salida se
  sumaban; en un recorrido circular superaban los mínimos y la web daba «En meta
  · 0h 00m» nada más salir. Lo de antes de la salida ya no suma (prueba nueva).
- **Directo:** en una ida y vuelta el km de la web iba hacia atrás toda la vuelta;
  un salto imposible del GPS ya no se publica como posición; el km hecho se
  guarda para quien abre la web a mitad de carrera; un GPX sin altura ya no
  rompe la animación ni la repetición.
- **App:** tras meta el seguimiento se para a los 15 min aunque ya no estés sobre
  la ruta (camino del coche); una línea cortada de la cola ya no estropea la
  siguiente.
- **Panel:** bloqueado por intentos o servidor sin clave ya no se anuncian como
  «usuario o clave incorrectos».
- **Reloj Amazfit:** vale con escribir el dominio (se completa con `/api/gps`; antes
  no llegaba ningún punto), la cola se guarda tras cada envío (sin reenvíos
  repetidos) y colores del diseño cartel.

## v1.20.5 · 2026-10-23
- La plantilla del servicio (`despliegue/sigueme.service`) también deja `/home` de
  solo lectura salvo la carpeta del servidor: `ProtectSystem=strict` no cubre
  `/home`, y sin `ProtectHome=read-only` el servidor aún podía escribir, po
  ejemplo, en `~/.ssh`. Comprobado al encerrar el servicio de verdad en las dos Pis.

## v1.20.4 · 2026-10-23
- **Invitados:**
  - La purga automática de lo caducado usaba otra copia del módulo de invitados,
    con su propio cerrojo: podía pisar una renovación, borrar la carpeta de un
    invitado recién creado o dejar el índice de rutas públicas desfasado.
  - Con «Código nuevo», o al borrar un invitado y crear otro con el mismo nombre,
    las sesiones abiertas seguían valiendo hasta 12 h (la nueva cuenta quedaba
    abierta al anterior). Ahora dejan de valer al momento (prueba nueva).
  - Publicar con un valor raro de «ocultar» mandaba 0 m y la ruta salía entera:
    ahora 300 m. Un GPX vacío lo dice; un acceso sin caducidad ya no pone
    «hasta el 31/12/2099»; `ocultar_m` infinito ya no deja la petición colgada.
- **Portada:** con una carrera ya pasada y sin archivar, `/` saltaba al resultado
  de la carrera anterior; ahora enseña esa carrera. La distancia de cada carrera,
  igual en la portada y en `/carreras/` aunque falte en su `carrera.json`.
- **App, pestaña Rutas:** sin cobertura avisa y deja reintentar (antes abría el
  navegador); el doble toque ya no baja dos copias; un fallo a medias no deja un
  GPX vacío en Descargas; abrir otra ruta deprisa ya no pinta la anterior.

## v1.20.3 · 2026-10-22
- **Seguridad:** un JSON anidado a propósito (miles de niveles de `[[[[`) dejaba
  la petición sin respuesta, también en `/api/gps` sin autenticar: ahora se
  contesta como cualquier JSON malo (prueba nueva en `pruebas/servidor.py`).
- **Servicio encerrado** (`despliegue/sigueme.service`): solo escribe en su
  carpeta, sin privilegios nuevos, `/tmp` propio y el sistema de solo lectura.
- **CI:** acciones de GitHub fijadas por commit (una etiqueta se puede mover) y
  sin guardar las credenciales del checkout.
- Revisado frente a php2shell (CVE-2026-109618 y CVE-2026-109619): el proyecto no
  usa PHP; no le afecta.

## v1.20.2 · 2026-10-22
- **App Android al día:** Android Gradle Plugin 9.4.1 y Kotlin 2.4.21 (las dos
  PR de Dependabot, juntas: por separado no compilan). Con AGP 9 Kotlin va
  dentro del plugin de Android y el CI compila con la última versión de Gradle.
  Probado en el emulador (avisos sin cobertura y carrera completa).
- La misma distancia de cada carrera en la portada y en `/carreras/` (la oficial;
  la recorrida sale en su resultado). En la página en directo, el enlace de
  arriba se llama «Inicio», como en el resto.

## v1.20.1 · 2026-10-21
- **Índice de carreras (`/carreras/`) y página de la app (la del código QR) con el
  diseño cartel**, la misma cabecera que el resto (nombre del sitio, Inicio, Admin).
- **Arreglos:** el índice decía «Carrera en directo ahora» con una carrera solo
  preparada para otro día; ahora solo cuando de verdad está en marcha. En la
  portada, las carreras salen con el dibujo de su recorrido, el tiempo como en el
  resto de la web («2h 32m») y, en el móvil, se ve el tiempo en vez de los km. La
  fecha del índice, como en la portada («16 may 2027»). La página de la app ya no
  habla de «Listo para salir / Arreglar» (pantalla vieja de la app) y nombra
  Huawei Health.

## v1.20.0 · 2026-10-20
- **La página de la carrera en directo, con el diseño cartel:** franja lima con el
  nombre de la carrera en letra condensada, cifras grandes, estado (en directo,
  sin cobertura, resultado) y el mismo aspecto para las carreras archivadas y su
  resultado. El nombre del sitio sale del dominio, como en el resto de páginas.
- **La app Android, con el mismo diseño:** cabecera lima, botones y títulos en
  letra condensada, colores lima y negro, esquinas rectas. La pantalla de la
  carrera sigue enseñando el botón de empezar sin bajar.
- **Icono nuevo** (app, web, pantalla de inicio del móvil y vista previa al
  compartir): chincheta negra con «CC» sobre lima.
- **Revisión de diseño:** el acento de «Sígueme» ya no pisa la línea de arriba en
  el titular de la portada, los desplegables enseñan un «+», las casillas del
  panel salen en lima y la página en directo ya no enseña «admin» ni la versión.
- **Capturas del repo regeneradas** (portada, panel, guía paso a paso, rutas,
  app) con una carrera inventada.
- Banco del emulador: toca los botones sin distinguir mayúsculas y baja la
  pantalla si el botón no se ve.

## v1.19.1 · 2026-10-19
- **Al caducar un acceso se borra todo, y a tiempo:** el día siguiente a la fecha
  de caducidad desaparecen el usuario, sus rutas y las que había publicado (antes
  esperaba siete días y solo se limpiaba cuando alguien entraba). Ahora el servido
  lo revisa solo cada 6 horas.

## v1.19.0 · 2026-10-19
- **Una sola cabecera en todas las páginas** y el mismo diseño cartel (lima, negro,
  letra condensada) en la portada, la página de cada ruta, «Mis rutas» y el panel.
  Botón **Inicio** siempre a mano y un único botón **Admin**: al dueño lo lleva al
  panel (que incluye «Mis rutas»), al invitado a su espacio, donde administra sus rutas.
- **El titular lleva el nombre del dominio** (p. ej. «RUTAS ODEGAARD12»), en la web
  y en la app. Quitado el crédito de la tipografía de las pantallas.
- **El dueño entra directo a «Mis rutas»**, sin cuenta de invitado: vale la sesión
  del panel o su usuario y clave del panel. Sus rutas no caducan.
- **Arreglos:** el nombre de la ruta es el título de su página; pruebas del flujo
  del dueño.

## v1.18.1 · 2026-10-19
- El mensaje de la portada cuando no hay rutas nombra el botón «Mis rutas».

## v1.18.0 · 2026-10-19
- **Portada de rutas** (estilo cartel: lima, negro y letra condensada): es la web
  en `/` cuando no hay una carrera para hoy, y siempre en `/inicio`. Enseña las
  rutas publicadas, las carreras archivadas y, si la hay, la próxima carrera;
  arriba, «Mis rutas» (invitados) y «Admin». Antes redirigía al último resultado.
- **Cada ruta, su página** (`/r/…`): titular, cifras, mapa de satélite con la
  ruta, perfil de altura, avituallamientos, subidas, **Descargar GPX para el
  reloj** y Compartir. Sale con su vista previa al compartir el enlace.
- **Los invitados publican.** Cada ruta es privada hasta que su dueño la publica.
  Lo público va **recortado** (por defecto sin los primeros y últimos 300 m, donde
  suele estar su casa; se puede elegir 0, 500 m o 1 km), con la firma que quiera, y
  deja de verse en cuanto caduca su acceso. En la pestaña nueva **Rutas** del panel
  ves todo lo publicado y lo quitas o borras; también hay cuentas sin caducidad
  (la tuya). El espacio del invitado pasa a `/mis-rutas.html` (el nombre viejo
  redirige).
- **App Android:** pestañas **Rutas | Carrera**. Rutas es la misma portada
  (lista, pantalla de cada ruta con su perfil) y **guarda el GPX en Descargas**
  (Android 10 o más) con «Abrir con…» y «Compartir». Sin cobertura enseña las
  últimas rutas que bajó. Con el seguimiento en marcha, siempre la carrera.
- **Arreglos:** Huawei Health no se detectaba en Android 11 o más (faltaba en el
  manifiesto, error de la v1.16.0); la app solo intentaba bajar el plan al abrirse,
  y sin cobertura en ese momento no volvía a probar: ahora reintenta cada 10 s.
- El banco del emulador publica una ruta y comprueba que la app la muestra, la
  abre y guarda su GPX. Tipografía Anton (SIL OFL) en `fonts/`.

## v1.17.0 · 2026-10-19
- **Invitados:** un amigo prepara **sus** rutas y se las lleva al reloj, sin ver
  nada de tu carrera ni de tu panel. En el panel (pestaña Resultado →
  Invitados) creas un usuario con un código que caduca (30 días por defecto;
  se renueva con un botón, se cambia el código o se quita). Él entra en
  `/rutas.html` desde cualquier móvil, iPhone incluido: sube un GPX, pone sus
  avituallamientos, ve el perfil y las subidas y descarga el GPX para el reloj.
- **Datos de los invitados:** del GPX que suben no se guarda el original, solo
  la ruta simplificada y su perfil; en un sitio que el servidor nunca sirve.
  El código solo se ve al crearlo (en disco queda su hash). Sus datos se
  borran 7 días después de caducar. Máximo 20 invitados y 5 rutas cada uno.
- **Seguridad:** sesión propia (cookie `inv`, firmada con otra clave) que no
  vale en el panel ni al revés; un invitado no ve ni toca las rutas de otro;
  freno a la fuerza bruta; GPX de hasta 8 MB, uno a la vez; la página no sale
  en buscadores.
- Prueba nueva `pruebas/invitados.py` (aislamiento, caducidad, límites,
  ficheros no públicos) y el paso en el flujo de pruebas.

## v1.16.0 · 2026-10-19
- **La ruta en el reloj:** en la tarjeta «Ruta (GPX)» del panel, el botón
  **Descargar GPX para el reloj**. Lleva la altitud y, como puntos de control,
  los avituallamientos y el principio y la cima de cada subida. Se importa en
  Huawei Health (Yo → Mi ruta → Importar ruta → Enviar al reloj), Zepp, Garmin
  o Coros. También desde la consola: `python herramientas/gpx_reloj.py`. Solo
  con sesión del panel. Importación probada solo hasta el fichero: falta
  comprobarla en un reloj Huawei real (Watch Fit 4).
- **Huawei Health** como app de la pulsera en la app Android: la reconoce, la
  guía de «Activar Sígueme CC» y el aviso de «falta la app» la incluyen y
  ofrece instalarla.
- El panel y la guía lo explican; prueba nueva del servidor (sesión, puntos de
  control, altitud en cada punto).

## v1.15.1 · 2026-10-19
- Capturas nuevas: la app con el **siguiente paso**, y el panel en el
  ordenador con las pestañas a lo ancho; las de la guía («Preparar la
  carrera», datos, ruta, avituallamientos y avisos) con el diseño de ahora, y
  una nueva de la tarjeta «Que los avisos lleguen a la pulsera».
- README y guía con los nombres de las pestañas actuales (Preparar, Móvil,
  Carrera y Resultado) y los títulos sin numerar. Sin cambios de código.

## v1.15.0 · 2026-10-19
- **La app te lleva de la mano:** arriba sale el **siguiente paso** («Paso 6
  de 7: instala la app de tu pulsera») con un solo botón verde, hasta «Todo
  listo». «Empezar seguimiento» se queda en gris mientras falten pasos. La
  lista de abajo («Comprobaciones») sigue ahí y cada fila lleva a su sitio.
- **La pulsera, lo que más falla:** Mi Fitness y Zepp traen Sígueme CC
  **desactivada** por defecto. El aviso de prueba ahora es un aviso real
  («Prueba: subida larga en 300 m»), y al volver a la app pregunta «¿Te llegó
  a la pulsera?»; si no, explica paso a paso cómo activarla y abre Mi Fitness.
- **Mensajes con el diseño de la app** (no los del sistema), con título,
  texto claro y botones grandes; «Cómo funciona» en tres líneas.
- Transiciones: la pantalla entra por partes, los botones responden al
  pulsarlos y los cambios se animan; respeta «reducir movimiento».
- **Panel en el PC a lo ancho:** las pestañas son los pasos (1 Preparar, 2
  Móvil, 3 Carrera, 4 Resultado) con su estado y una marca al completarse, y
  el contenido va en dos columnas. Explicaciones en pasos cortos, «Siguiente»
  al final de cada pestaña, una tarjeta nueva para la pulsera y lo de
  iGPSPORT plegado. Al abrir con cosas pendientes, va directo a Preparar.
- App: los botones crecen con la letra grande del móvil. Arreglos: sin cierre
  si el móvil no tiene la pantalla de ahorro de batería y sin ventana colgada
  al girar con un mensaje abierto.
- El banco del emulador guarda el registro de Android cuando una prueba falla.

## v1.14.0 · 2026-10-19
- **El panel guía la preparación de la carrera:** «Preparar la carrera»
  enseña cuántos pasos hay listos («4 de 7 listos»), dice cuál es el
  **siguiente paso** con un botón que te lleva a su sitio (cambia de pestaña,
  baja hasta la sección y la resalta), y cada fila de la lista es pulsable.
  Si falta la ruta, el siguiente paso es subir el GPX; si ya está todo, dice
  «Todo listo. El día de la carrera, abre la app y pulsa Empezar seguimiento».
- La pestaña **Hoy** avisa de lo que falta preparar mientras no haya una
  carrera en marcha.
- Prueba nueva (`pruebas/panel.py`, con Playwright): comprueba los tres
  estados y que el botón lleva a la pestaña y la sección correctas.

## v1.13.10 · 2026-10-19
- **Enlace de seguimiento validado:** el servidor solo usa la vía de iGPSPORT
  si el servidor del enlace es de verdad iGPSPORT (no si el texto lo
  contiene), y cualquier otro enlace solo puede ser http(s) a una dirección
  pública: ni `file://` ni direcciones de la red de casa.
- **Un «NaN» en la respuesta de iGPSPORT (o desde el panel) ya no congela la
  web:** se descarta en vez de escribirse en el live.json, que el navegador
  no aceptaba.
- **«Simular» sin ruta subida** deja un error claro («falta la ruta») en vez
  de una carrera fantasma en marcha que bloqueaba el panel.
- **Foto del corredor:** solo PNG de hasta 1024×1024 (el panel la recorta a
  256); una imagen que declaraba un tamaño enorme obligaba a cada navegador a
  descodificarla.
- **Web:** sin cobertura cerca del final, la hora prevista de meta ya no se
  queda en el pasado.
- Pruebas nuevas para la foto, la simulación sin ruta y el NaN.

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
