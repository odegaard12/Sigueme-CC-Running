<p align="center">
  <img src="icon-192.png" width="112" alt="Sígueme CC">
</p>

<h1 align="center">Sígueme CC</h1>

<p align="center">
  Seguimiento en directo de una carrera de MTB (o a pie): mapa 3D, perfil, avituallamientos,<br>
  tiempos y, al terminar, el resultado con la repetición de la carrera.
</p>

<p align="center">
  <img alt="versión" src="https://img.shields.io/badge/versión-v1.1.1-1f8a4c">
  <img alt="Python" src="https://img.shields.io/badge/servidor-Python%203%20·%20stdlib-3776ab">
  <img alt="MapLibre" src="https://img.shields.io/badge/mapa-MapLibre%204.7-396cb2">
  <img alt="Zepp OS" src="https://img.shields.io/badge/reloj-Zepp%20OS%203-ff6a00">
  <img alt="licencia MIT" src="https://img.shields.io/badge/licencia-MIT-555">
</p>

<p align="center">
  <img src="docs/capturas/movil.jpg" width="230" alt="Web en el móvil">
  &nbsp;
  <img src="docs/capturas/ficha.jpg" width="230" alt="Ficha del corredor">
  &nbsp;
  <img src="docs/capturas/panel.jpg" width="230" alt="Panel de administración">
</p>
<p align="center">
  <img src="docs/capturas/pc.jpg" width="720" alt="Web en el ordenador">
</p>

Estrenada en la **Mi carrera MTB** (103 km, 2.629 m+). Corre en una
Raspberry Pi, con otra de respaldo, detrás de un túnel de Cloudflare.

## Cómo funciona

```
 BSC500 ── app iGPSPORT ── nube iGPSPORT ─┐   (cada 15 s, lo consulta el servidor)
 Móvil con Traccar Client ────────────────┼──► server.py ──► live.json ──► web (app.js)
 Reloj Amazfit ── app Zepp del móvil ─────┘   (/api/gps)                    └► panel (admin.html)
```

| Fuente | Qué da | Cómo llega |
|---|---|---|
| **Traccar Client** (Android/iPhone) | posición, velocidad, batería | `/api/gps` (OsmAnd o JSON). Sin cobertura guarda los puntos y los manda al volver. |
| **Miniapp Amazfit** ([`amazfit/`](amazfit/)) | posición y pulso del reloj | reloj → app Zepp → `/api/gps` (JSON con `extras.hr`). |
| **iGPSPORT LiveTrack** | posición, pulso, cadencia, distancia | el servidor consulta el enlace compartido cada 15 s. |

Cuando llegan varias a la vez:

- La **posición** la da el GPS del móvil o del reloj (el que ya mandaba; el otro
  toma el relevo tras 2 min de silencio). iGPSPORT solo si los dos callan.
- El **pulso** del reloj manda sobre el de iGPSPORT. Pulso y cadencia se ocultan
  si su fuente lleva 3 min sin dar nada.
- La **llegada a meta** se detecta sola y la hora no cambia aunque después siga
  moviéndose. Con mala cobertura, la web enseña un aviso y se pone al día sola.

## Estructura

```
├── server.py              servidor: web, /api/gps, panel, login, lector de iGPSPORT
├── index.html · app.js · style.css    la web pública
├── admin.html             panel (enlace de iGPSPORT, hora de salida, finalizar…)
├── route.geojson · elevation.json · aid_stations.json    trazado, perfil y avituallamientos
├── lib/                   MapLibre servido desde la propia Pi
├── herramientas/          generar_resultado.py: resultado.json desde el FIT
├── amazfit/               miniapp para relojes Zepp OS
├── despliegue/            plantillas de systemd, keepalived, réplica y despliegue
└── docs/capturas/         imágenes de este README
```

No van al repo (`.gitignore`): `live.json` (estado), `gps.clave` (identificador
de Traccar/reloj), `historial.jsonl` (registro de todo lo recibido),
`resultado.json` y los FIT.

## Ponerlo en marcha

```bash
pip install curl_cffi
python3 server.py --hash-clave            # pide la clave y escribe ADMIN_HASH=…
ADMIN_USER=usuario ADMIN_HASH='scrypt:…' python3 server.py 8710
```

- **Panel:** `/admin.html`, con usuario y clave. El servidor solo guarda el hash
  (scrypt) y da una cookie de sesión HttpOnly firmada de 12 h.
- **Traccar Client:** dirección `https://<dominio>/api/gps`, el identificador que
  enseña el panel, frecuencia 10 s, precisión alta.
- **Dos Pis con IP flotante:** `VIP_SIGUEME` y las plantillas de
  [`despliegue/`](despliegue/README.md).
- **Resultado tras la carrera:** `python herramientas/generar_resultado.py actividad.fit`
  (necesita `fitdecode`).

## Seguridad

- Solo se sirven extensiones públicas: `server.py`, `gps.clave`,
  `historial.jsonl`, scripts y configuraciones dan 404.
- Panel con usuario y clave (hash scrypt), sesión en cookie HttpOnly +
  SameSite=Strict (+ Secure por https), freno a la fuerza bruta y tamaño
  máximo de petición.
- Cabeceras `nosniff`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy` y HSTS; el panel además con CSP estricta y `noindex`.
- Sin base de datos (todo son ficheros JSON): no hay inyección SQL posible.

## Versiones

Cada versión es un commit con su etiqueta y su release. Historial completo en
[`CHANGELOG.md`](CHANGELOG.md).

## Licencia

[MIT](LICENSE): úsalo, cámbialo y compártelo; solo hay que mantener el aviso de copyright.
