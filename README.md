<p align="center">
  <img src="icon-192.png" width="112" alt="Sígueme CC">
</p>

<h1 align="center">Sígueme CC</h1>

<p align="center">
  Web para que tu familia y amigos te sigan <b>en directo</b> en una carrera de MTB o a pie:<br>
  mapa 3D con tu posición sobre el trazado, perfil, avituallamientos, tiempos y,<br>
  al terminar, el resultado con la repetición de la carrera.
</p>

<p align="center">
  <img alt="versión" src="https://img.shields.io/badge/versión-v1.40.0-1f8a4c">
  <img alt="Python" src="https://img.shields.io/badge/servidor-Python%203%20·%20stdlib-3776ab">
  <img alt="MapLibre" src="https://img.shields.io/badge/mapa-MapLibre%204.7-396cb2">
  <img alt="Zepp OS" src="https://img.shields.io/badge/reloj-Zepp%20OS%203-ff6a00">
  <img alt="licencia MIT" src="https://img.shields.io/badge/licencia-MIT-555">
</p>

<p align="center">
  <img src="docs/capturas/portada.png" width="900" alt="En directo, sin cobertura, ficha del corredor y resultado, en el móvil">
</p>
<p align="center">
  <img src="docs/capturas/pc.jpg" width="900" alt="La web en el ordenador">
</p>
<p align="center">
  <img src="docs/capturas/inicio.png" width="900" alt="La portada: la carrera primero, con su estado y un botón grande, en el ordenador y en el móvil">
</p>
<p align="center">
  <img src="docs/capturas/panel.png" width="820" alt="Panel en el ordenador: las pestañas son los pasos (Preparar, Móvil, Carrera, Resultado y Rutas) y dice cuál es el siguiente">
</p>
<p align="center">
  <img src="docs/capturas/rutas.png" width="900" alt="La página «Rutas y relojes» en el ordenador y la página de una ruta en el móvil">
</p>

---

## Índice

> **¿Primera carrera?** Sigue la guía visual [Preparar una carrera, paso a paso](docs/GUIA-CARRERA.md).

1. [Qué necesitas](#1-qué-necesitas)
2. [Arrancar el servidor](#2-arrancar-el-servidor)
3. [Preparar tu carrera](#3-preparar-tu-carrera)
4. [Elegir cómo se manda tu posición](#4-elegir-cómo-se-manda-tu-posición)
5. [El día de la carrera](#5-el-día-de-la-carrera)
6. [Después de la carrera](#6-después-de-la-carrera)
7. [Cómo funciona por dentro](#cómo-funciona-por-dentro) · [Seguridad](#seguridad) · [Versiones](#versiones)

---

## 1. Qué necesitas

- Un ordenador siempre encendido con **Python 3.9 o superior** (una Raspberry Pi
  va de sobra) y una forma de publicarlo en internet con **https**: un túnel de
  Cloudflare (gratis) es lo más sencillo.
- El **GPX** de la ruta.
- Al menos una forma de mandar tu posición: la **app Sígueme CC** (Android,
  recomendada: avisos sin cobertura), **Traccar Client** (iPhone), un **reloj
  Amazfit** o el directo de un ciclocomputador **iGPSPORT**.

## 2. Arrancar el servidor

```bash
pip install curl_cffi fitdecode            # opcionales: iGPSPORT y el resultado desde el FIT
python3 server.py --hash-clave             # pide una clave y escribe ADMIN_HASH=…
ADMIN_USER=tu_usuario ADMIN_HASH='scrypt:…' python3 server.py 8710
```

- La web queda en `http://localhost:8710` y el **panel** en `/admin.html`
  (usuario y clave del paso anterior; el servidor solo guarda el hash).
- Sin `curl_cffi` funciona todo menos iGPSPORT; sin `fitdecode`, todo menos el
  resultado desde el FIT. En Raspberry Pi OS:
  `pip install --user --break-system-packages curl_cffi fitdecode`.
- El **identificador** de los móviles y relojes se crea solo al primer arranque.
  Para cambiarlo (recomendable en cada carrera): panel → **Móvil** → «Sin la app:
  iPhone, Traccar o reloj» → **Ver la configuración** → **Generar identificador
  nuevo**, y vuelve a escanear el código en la app.
- Para dejarlo como servicio, y para tener **dos Raspberry** con una de
  respaldo, sigue [`despliegue/README.md`](despliegue/README.md).

## 3. Preparar tu carrera

Todo desde el **panel**: las cuatro pestañas son los pasos (**Preparar**,
**Móvil**, **Carrera** y **Resultado**) y arriba pone cuál es el **siguiente paso**.
La guía con capturas: **[Preparar una carrera, paso a paso](docs/GUIA-CARRERA.md)**.

1. **Datos de la carrera:** nombre, fecha, hora de salida, límite, corredor…
2. **Ruta:** subes el GPX y salen el trazado y el perfil.
3. **Avituallamientos:** nombre y km de cada uno.
4. **Avisos a la pulsera:** salen solos del perfil (subidas, cimas,
   avituallamientos, lo que queda); los revisas y cambias los textos.
5. **App del móvil:** escaneas el código QR y baja todo para ir sin cobertura.
6. **La ruta en el reloj (opcional):** un botón descarga el GPX con altitudes y, como
   puntos de control, los avituallamientos y las subidas, para importarlo en Huawei Health,
   Zepp (Amazfit), Garmin o Coros. Las **Xiaomi Smart Band** no importan rutas: con ellas se usan los avisos
   de la app (Mi Fitness los pasa a la banda) y el resultado se saca después del GPX de Mi Fitness.

Todo queda en ficheros de la raíz que puedes editar a mano si prefieres
(`carrera.json`, `route.geojson`, `elevation.json`, `aid_stations.json`,
`avisos.json`); el código no nombra ninguna carrera. Campos de `carrera.json`:

| Campo | Qué es | Ejemplo |
|---|---|---|
| `nombre`, `lugar` | Salen en la ficha y al pie de la web | `"Mi carrera MTB"` |
| `fecha`, `hora_salida` | Día y hora oficial de salida (el cronómetro y la app cuentan desde ahí) | `"2027-05-16"`, `"09:00"` |
| `zona_horaria` | Para enseñar las horas bien aunque quien mira esté en otro país | `"Europe/Madrid"` |
| `distancia_km`, `desnivel_m` | Las rellena la ruta (paso 2); cámbialas si la organización da otras | `21.1`, `309` |
| `limite_h` | Horas para terminar | `5` |
| `km_minimos_meta` | Km hechos para que pasar por meta cuente como llegada (si la salida está junto a la meta). Si falta, el 80 % | `17` |
| `modalidad` | MTB, trail… | `"Trail"` |
| `corredor` | `nombre`, `dorsal`, `club` y `categoria` | `{"nombre": "Ana", "dorsal": "27"}` |
| `bici` | `modelo` y `piezas` para la ficha (opcional) | ver el ejemplo |
| `ocultar_m` | Si la salida o la meta son en tu casa: a menos de estos metros no se publica tu posición | `500` |
| `slug` | Dirección de la carrera al archivarla (opcional) | `"2027-mi-carrera"` |

Tu **foto** se sube en el panel (pestaña **Preparar** → Datos de la carrera → «Cambiar la foto»): se
recorta cuadrada en el navegador y sale en el mapa y en la ficha (`rider.png`).

Sin panel, las mismas herramientas desde la consola:
`python herramientas/preparar_ruta.py ruta.gpx --distancia 21.1` y
`python herramientas/plan_avisos.py`.

### Invitados: las rutas de un amigo, en su reloj

Para que un amigo prepare **sus** rutas y se las lleve al reloj sin ver nada de tu
carrera: en el panel, pestaña **Resultado** → **Invitados**, creas un usuario con
un código que caduca (30 días por defecto; puedes renovarlo o quitarlo). Él entra
en `https://tu-dominio/mis-rutas.html` desde cualquier móvil (iPhone incluido), sube
un GPX, pone sus avituallamientos y descarga el GPX para el reloj. No hay
seguimiento ni se guarda su GPX original (solo la ruta simplificada y su perfil);
al día siguiente de caducar se borra todo lo suyo (usuario y rutas). Máximo 20 invitados y 5 rutas
cada uno. Cada ruta es **privada hasta que su dueño la publica**: lo público se ve
recortado (por defecto sin los primeros y últimos 300 m, donde suele estar su casa) y
deja de verse en cuanto caduca el acceso. Tú, desde la pestaña **Rutas** del panel,
ves todo lo publicado y puedes quitarlo.

La **portada** de la web (`/`, cuando no hay una carrera para hoy; siempre en `/inicio`) enseña
las rutas publicadas y las carreras archivadas, y una carrera de otro día como «próxima». Cada
ruta tiene su página (`/r/…`) con mapa, perfil, avituallamientos, subidas y el GPX para el reloj.
Tipografía Anton (SIL OFL) servida desde `fonts/`.

## 4. Elegir cómo se manda tu posición

<p align="center"><img src="docs/capturas/app.jpg" width="640" alt="App Android: las rutas, una ruta con su perfil y el seguimiento de la carrera"></p>

Puedes usar una sola o varias a la vez; la web decide sola cuál usar.

| Opción | Ventaja | Cómo |
|---|---|---|
| **App Sígueme CC** (Android, recomendada) | Lanza los avisos a la pulsera **sin cobertura** y guarda tu posición hasta que vuelve | APK en la [última release](../../releases/latest). En el panel, pestaña **Móvil** → «App del móvil»: escanea el código con la cámara y pulsa «Abrir en la app». |
| **Traccar Client** (Android/iPhone, gratis) | Sin cobertura guarda los puntos y los manda al volver | En la app: dirección `https://tu-dominio/api/gps`, identificador = el del panel (Móvil → «Sin la app…» → Ver la configuración), frecuencia 10 s, precisión alta. En Android, quítale el ahorro de batería. |
| **Reloj Amazfit** (Zepp OS 3) | No dependes del móvil en la mano; manda también el pulso | Miniapp de [`amazfit/`](amazfit/README.md) (de momento se instala en modo desarrollador, no está en la tienda). |
| **iGPSPORT LiveTrack** | Pulso, cadencia y distancia del ciclocomputador | En la app de iGPSPORT, compartir el seguimiento en vivo y pegar el enlace en el panel. |

Si llegan varias: la **posición** la da el móvil o el reloj (el que ya mandaba;
el otro toma el relevo tras 2 min de silencio) e iGPSPORT solo si los dos
callan; el **pulso** del reloj manda sobre el de iGPSPORT.

## 5. El día de la carrera

1. Con la **app**: pulsa **Empezar seguimiento** cuando quieras, aunque sea una
   hora antes. Baja el plan al día y pone la carrera en marcha en la web; hasta
   la hora oficial la web dice «En la salida», el crono no corre y no hay
   avisos. Guarda el móvil: sigue solo con la pantalla apagada.
2. Sin la app (Traccar, reloj o iGPSPORT): en el panel, pestaña **Carrera**, pulsa
   **Empezar a seguir** y arranca Traccar o el reloj antes de salir.
3. Comparte el enlace con el botón de la cabecera de la web: en WhatsApp sale
   con su vista previa (con tu dominio; la imagen es `og.jpg`, cámbiala por la tuya).
   Con la carrera preparada para hoy, la portada ya es esa carrera.
4. **Sin cobertura** la web lo dice («Sin cobertura desde las 12:03, km 44»),
   una marca transparente avanza por la ruta a tu ritmo medio y salen las horas
   previstas al próximo avituallamiento y a meta. Al volver la cobertura llegan
   los puntos guardados en el móvil.
5. La **llegada se detecta sola**. Si el directo se cortó antes de meta, pon la
   hora de llegada en el panel y pulsa **Finalizar seguimiento**.

Si algo falla, el panel lo dice: identificador mal copiado, enlace de iGPSPORT
caducado, sin datos desde hace X minutos…

## 6. Después de la carrera

En el panel, pestaña **Resultado**, sube el **FIT** de tu reloj o ciclocomputador (en
Garmin Connect, Strava o la app del reloj: exportar el original). La web pasa a
**modo resultado**: tiempo oficial, paso por cada avituallamiento y repetición de
la carrera. Desde la consola hace lo mismo
`python herramientas/generar_resultado.py actividad.fit`.

Después, en el panel (pestaña **Resultado**), **Archivar la carrera terminada**: se guarda en
`carreras/<año-nombre>/` y queda en su propia dirección (`/2026-mi-carrera/`),
con el mismo diseño en modo resultado, y en el índice **`/carreras/`**. La
portada queda a cero para la siguiente: mientras no haya otra en marcha, lleva
al último resultado (así los enlaces que ya compartiste siguen sirviendo).
La dirección sale de `slug` en `carrera.json` o, si no hay, del año y el lugar
(o el nombre).

---

## Cómo funciona por dentro

```
 App Sígueme CC (Android) ──── /api/plan + /api/gps ─┐
 Ciclocomputador ── app iGPSPORT ── nube iGPSPORT ───┤  (el servidor lo consulta cada 15 s)
 Móvil con Traccar Client ───────────────────────────┼──► server.py ──► live.json ──► web (app.js)
 Reloj Amazfit ── app Zepp del móvil ────────────────┘    (/api/gps)                 └► panel (admin.html)
```

| Fichero | Qué es |
|---|---|
| `server.py` | Servidor (biblioteca estándar; `curl_cffi` solo para iGPSPORT): web, `/api/gps`, `/api/plan`, panel, login, lector de iGPSPORT |
| `index.html` · `app.js` · `style.css` | La web pública (MapLibre servido desde `lib/`) |
| `admin.html` | Panel de control |
| `carrera.json` · `route.geojson` · `elevation.json` · `aid_stations.json` | Tu carrera (paso 2) |
| `herramientas/` | `preparar_ruta.py` (GPX → ruta), `plan_avisos.py` (perfil → avisos; los dos los usa también el panel) y `generar_resultado.py` (FIT → resultado) |
| `android/` | App Android (Kotlin, sin librerías): GPS con la pantalla apagada, avisos locales y cola de posiciones. La compila GitHub Actions y sube el APK a cada release |
| `app.html` | Página del código QR: instala y configura la app |
| `amazfit/` | Miniapp para relojes Zepp OS |
| `despliegue/` | systemd, keepalived, réplica entre dos Pis y despliegue |

**No van al repo** (`.gitignore`): `live.json` (estado), `gps.clave`
(identificador de la app, Traccar y el reloj), `historial.jsonl` (registro de
todo lo recibido), `avisos.json`, `resultado.json`, `carreras/` (el archivo) y
los FIT.

## Seguridad

- Solo se sirven ficheros públicos: `server.py`, `gps.clave`, `historial.jsonl`,
  scripts, configuraciones y carpetas ocultas dan 404 (página propia en español).
- `live.json` público recortado a lo que pinta la web: nada de enlace de
  iGPSPORT, batería del móvil ni datos internos (el panel pide el estado completo
  con su sesión). Con `ocultar_m`, sin posición cerca de salida y meta.
- Identificador de la app, Traccar y el reloj de 36 caracteres al azar (se crea
  al primer arranque y se cambia desde el panel); el servidor no guarda registros de peticiones y descarta puntos de
  hace más de un día.
- Panel con usuario y clave (hash scrypt), sesión en cookie HttpOnly +
  SameSite=Strict (+ Secure por https), comprobación de origen (CSRF), freno a
  la fuerza bruta por IP real (10 fallos: 15 min bloqueada esa IP, no las
  demás), tope de peticiones y conexiones lentas cortadas.
- Cabeceras `nosniff`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, HSTS y CSP (en la web, scripts por hash y solo las
  teselas de Esri y AWS); el panel además con `noindex`.
- Sin base de datos (todo son ficheros JSON): no hay inyección SQL posible.

## Versiones

Cada versión es un commit con su etiqueta y su release. Historial completo en
[`CHANGELOG.md`](CHANGELOG.md).

## Licencia

[MIT](LICENSE): úsalo, cámbialo y compártelo; solo hay que mantener el aviso de copyright.

## Pruebas

`python pruebas/servidor.py`, `pruebas/ensayo.py`, `pruebas/gpx.py` y
`pruebas/carga.py` arrancan el servidor de verdad en una carpeta temporal con
datos inventados. GitHub Actions las corre en cada cambio; más detalle en
[pruebas/README.md](pruebas/README.md).
