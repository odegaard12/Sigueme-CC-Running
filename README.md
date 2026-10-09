# Sígueme · Mi carrera

Web de seguimiento en directo de un corredor de MTB (o a pie) por la ruta de
la carrera: mapa 3D con la posición sobre el trazado, perfil altimétrico,
avituallamientos, tiempos y, al terminar, el resultado con repetición de la
carrera. Corre en una Raspberry Pi (con otra de respaldo) detrás de un túnel
de Cloudflare.

```
 BSC500 ── app iGPSPORT ── nube iGPSPORT ─┐   (cada 15 s, lo consulta el servidor)
 Móvil con Traccar Client ────────────────┼──► server.py ──► live.json ──► web (app.js)
 Reloj Amazfit ── app Zepp del móvil ─────┘   (/api/gps)                    └► panel (admin.html)
```

## Fuentes de datos

| Fuente | Qué da | Cómo llega |
|---|---|---|
| **Traccar Client** (Android/iPhone) | posición, velocidad, batería | `POST/GET /api/gps` (OsmAnd o JSON). Sin cobertura guarda los puntos y los manda al volver. |
| **Miniapp Amazfit** (`amazfit/`) | posición y pulso del reloj | reloj → app Zepp → `POST /api/gps` (JSON con `extras.hr`). |
| **iGPSPORT LiveTrack** | posición, pulso, cadencia, distancia | el servidor consulta el enlace compartido cada 15 s. |

Reglas cuando llegan varias a la vez:
- La **posición** la da el GPS del móvil o del reloj (el que ya mandaba; el otro
  toma el relevo tras 2 min de silencio). iGPSPORT solo si los dos callan.
- El **pulso** del reloj manda sobre el de iGPSPORT.
- Pulso y cadencia se ocultan en la web si su fuente lleva 3 min sin dar nada.
- La **llegada a meta** se detecta sola (cerca de meta y >80 km hechos, o
  habiéndose alejado antes >5 km) y la hora no cambia si después sigue moviéndose.

## Ficheros

| Fichero | Qué es |
|---|---|
| `server.py` | Servidor (biblioteca estándar + `curl_cffi`): estáticos, `/api/gps`, `/api/live` (panel), `/api/login`, lector de iGPSPORT. |
| `index.html`, `app.js`, `style.css` | La web pública (MapLibre servido desde `lib/`). |
| `admin.html` | Panel: enlace de iGPSPORT, hora de salida, finalizar, datos de Traccar, pruebas. |
| `route.geojson`, `elevation.json`, `aid_stations.json` | Trazado, perfil y avituallamientos. |
| `herramientas/generar_resultado.py` | Crea `resultado.json` desde el FIT de la carrera (modo resultado de la web). |
| `amazfit/` | Miniapp para relojes Zepp OS (ver su README). |
| `despliegue/` | Plantillas de systemd, keepalived, réplica entre Pis y script de despliegue. |
| `promo/` | Imágenes para redes. |

**Nunca van al repo** (`.gitignore`): `live.json` (estado), `gps.clave`
(identificador de Traccar/reloj), `historial.jsonl` (registro de todo lo
recibido), `resultado.json` y los FIT.

## Ponerlo en marcha

```bash
pip install curl_cffi
ADMIN_TOKEN='una-clave-larga' python3 server.py 8710
```

- Panel: `/admin.html`. La clave se manda una vez a `/api/login` y el servidor
  devuelve una cookie de sesión HttpOnly firmada (12 h). Los scripts pueden
  mandar `{"token": ...}` en el cuerpo.
- Identificador de Traccar/reloj: está en `gps.clave` y lo enseña el panel.
- Traccar Client: dirección `https://<dominio>/api/gps`, ese identificador,
  frecuencia 10 s, precisión alta.

Producción con dos Pis e IP flotante: `despliegue/README.md`.

## Seguridad

- Lista blanca de lo que se sirve: solo extensiones públicas; `server.py`,
  `gps.clave`, `historial.jsonl`, scripts y configuraciones dan 404.
- Panel con sesión en cookie HttpOnly + SameSite=Strict (+ Secure por https),
  sin estado y válida en las dos Pis; cambiar la clave cierra todas las sesiones.
- Freno a la fuerza bruta de la clave; tamaño máximo de petición (16 KB el
  panel, 2 MB `/api/gps`).
- Cabeceras `nosniff`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy` y HSTS; el panel además con CSP estricta y `noindex`.
- Sin base de datos (todo son ficheros JSON): no hay inyección SQL posible.
