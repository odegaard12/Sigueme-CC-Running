import http.server
import json
import math
import os
import re
import socket
import socketserver
import sys
import threading
import time
import urllib.request
from curl_cffi import requests as cffi_requests
from datetime import datetime, timezone
from hmac import compare_digest
from urllib.parse import parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
LIVE_PATH = os.path.join(ROOT, "live.json")
# ⚠️ NUNCA poner la clave de verdad aquí: este fichero estaba servido por la
# propia web (http://.../server.py devolvía 200) y cualquiera podía leerla.
# Ahora la clave llega solo por el entorno (systemd) y, además, el servidor no
# entrega ficheros que no sean los de la web (ver EXTENSIONES_PUBLICAS).
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8710
BIND_HOST = os.environ.get("BIND_HOST", "0.0.0.0")
# Preguntar cada 8 s eran 5 400 peticiones en las 12 h de carrera a una API de
# iGPSPORT que no es pública: demasiado para que no se fijen en nosotros. El
# BSC500 sube por el móvil cada pocos segundos, así que con 15 s no se pierde
# nada útil. Ante errores se espera cada vez más (hasta 5 min) en vez de
# insistir, que es lo que de verdad hace que te corten.
POLL_SECONDS = 15
ESPERA_MAXIMA = 300

live_lock = threading.Lock()
poller = {"thread": None, "stop": None, "url": None}

# --- freno a la fuerza bruta contra el panel admin -------------------------
# La web es pública el día de la carrera: sin esto, cualquiera puede probar
# claves a mil por hora. A partir del 5º fallo desde la misma IP, cada intento
# espera; a los 10, medio minuto. Un acierto lo borra todo.
intentos_lock = threading.Lock()
intentos = {}   # ip -> [fallos, momento_del_ultimo_fallo]


def segundos_de_castigo(ip):
    with intentos_lock:
        fallos, ultimo = intentos.get(ip, (0, 0))
    if fallos < 5:
        return 0
    castigo = 5 if fallos < 10 else 30
    restante = castigo - (time.time() - ultimo)
    return int(restante) + 1 if restante > 0 else 0


def fallo_de(ip):
    with intentos_lock:
        fallos, _ = intentos.get(ip, (0, 0))
        intentos[ip] = (fallos + 1, time.time())


def acierto_de(ip):
    with intentos_lock:
        intentos.pop(ip, None)

# --- iGPSPORT ---------------------------------------------------------------
# El enlace que comparte la app (prod.en.igpsport.com/.../GetShareHtml?id=...)
# es solo el envoltorio: redirige a analyse.en.igpsport.com/livetracing y ESA
# página pide los datos, cada pocos segundos, a una API JSON abierta (sin
# login):
#
#   https://analyse.en.igpsport.com/en/analyse/api/Track/GetLivetrack?id=<id>
#
# Descubierto el 2026-09-22 espiando las peticiones del navegador con un
# enlace real. Devuelve:
#   data.route.gpsCoords  -> polilínea codificada (algoritmo de Google), el
#                            último punto es la posición actual
#   data.route.summary    -> totalDistance, totalTime, currentSpeed, avgSpeed,
#                            currentHeartrate, avgHeartrate, currentCadence...
# OJO: pulso y cadencia valen 255 (y potencia 65535) cuando el sensor NO está
# conectado; hay que tratarlos como "sin dato", no como 255 ppm.
IGPSPORT_API = "https://analyse.en.igpsport.com/en/analyse/api/Track/GetLivetrack?id="
# 255/65535 = sensor ausente. El 0 solo es "sin dato" en pulso y cadencia: en
# velocidad o distancia un 0 es real (parado, o recién salido).
SIN_SENSOR = {255, 65535}
SIN_SENSOR_PULSO = {0, 255, 65535}


def igpsport_id(url):
    """Saca el id de cualquier enlace de iGPSPORT (share o livetracing)."""
    if "igpsport.com" not in url:
        return None
    m = re.search(r"[?&]id=([^&]+)", url)
    return m.group(1) if m else None


def decode_polyline(encoded):
    """Polilínea codificada de Google -> [(lat, lon), ...]."""
    puntos, i, lat, lon = [], 0, 0, 0
    while i < len(encoded):
        for eje in range(2):
            shift, result = 0, 0
            while i < len(encoded):
                b = ord(encoded[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if eje == 0:
                lat += delta
            else:
                lon += delta
        puntos.append((lat / 1e5, lon / 1e5))
    return puntos


def _num(valor, sentinelas=SIN_SENSOR):
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return None if n in sentinelas else n


def extract_igpsport(payload):
    datos = payload.get("data") or {}
    if not isinstance(datos, dict):
        return None
    # por si otra sesión llega sin el nivel "route" (no se pudo comprobar el
    # 26/09: el seguimiento nuevo no dio datos y no quedó su respuesta)
    ruta = datos.get("route") if isinstance(datos.get("route"), dict) else datos
    resumen = ruta.get("summary") or datos.get("summary") or {}
    fuera = {}

    coords = ruta.get("gpsCoords") or datos.get("gpsCoords") or ""
    puntos = decode_polyline(coords) if isinstance(coords, str) else []
    if puntos:
        fuera["lat"], fuera["lon"] = puntos[-1]

    for clave, campo, sentinelas in (
            ("speed_kmh", "currentSpeed", SIN_SENSOR),
            ("speed_kmh_avg", "avgSpeed", SIN_SENSOR),
            ("hr", "currentHeartrate", SIN_SENSOR_PULSO),
            ("hr_avg", "avgHeartrate", SIN_SENSOR_PULSO),
            ("cadence", "currentCadence", SIN_SENSOR_PULSO),
            ("cadence_avg", "avgCadence", SIN_SENSOR_PULSO),
            ("dist_km", "totalDistance", SIN_SENSOR)):
        valor = _num(resumen.get(campo), sentinelas)
        if valor is not None:
            fuera[clave] = valor

    if resumen.get("totalTime"):
        fuera["elapsed"] = resumen["totalTime"]

    return fuera or None


PATTERNS = {
    "lat": re.compile(r'"lat(?:itude)?"\s*:\s*(-?\d{1,3}\.\d+)', re.I),
    "lon": re.compile(r'"l(?:ng|on|ongitude)"\s*:\s*(-?\d{1,3}\.\d+)', re.I),
    "speed_kmh": re.compile(r'"speed(?:_?kmh)?"\s*:\s*(-?\d+(?:\.\d+)?)', re.I),
    "hr": re.compile(r'"(?:hr|heart_?rate)"\s*:\s*(\d{2,3})', re.I),
    "cadence": re.compile(r'"cadence"\s*:\s*(\d{1,3})', re.I),
    "dist_km": re.compile(r'"dist(?:ance)?(?:_?km)?"\s*:\s*(-?\d+(?:\.\d+)?)', re.I),
}


def extract_telemetry(html):
    found = {}
    for key, pattern in PATTERNS.items():
        m = pattern.search(html)
        if m:
            found[key] = float(m.group(1))
    if "lat" not in found or "lon" not in found:
        return None
    return found


class RespuestaHTTP(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def fetch_page(url):
    # ⚠️ Cloudflare bloquea por huella TLS (JA3), no por cabeceras: con
    # urllib.request daba 403 SIEMPRE, aunque llevara User-Agent, Referer y
    # sec-ch-ua de Chrome de verdad. curl_cffi reproduce la huella TLS real
    # de Chrome (BoringSSL) y con eso Cloudflare deja pasar la petición.
    if "igpsport.com" in url:
        r = cffi_requests.get(url, impersonate="chrome120", timeout=10)
        # curl_cffi no lanza excepción con los errores HTTP (urllib sí), así que
        # el freno ante 403/429 no saltaba nunca. OJO: iGPSPORT contesta 403
        # CON su JSON {"code":40604} cuando la actividad aún no ha empezado;
        # eso no es un bloqueo y se deja pasar para que se lea como "sin datos".
        cuerpo = r.text
        if r.status_code == 429 or (r.status_code >= 400 and not cuerpo.lstrip().startswith("{")):
            raise RespuestaHTTP(r.status_code)
        return cuerpo
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; 21LeguasTracker/1.0)"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read(2_000_000).decode("utf-8", errors="ignore")


def read_live():
    try:
        with open(LIVE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_live(current):
    """Escritura atómica: fichero temporal + reemplazo.

    Si se va la luz justo mientras se guarda, con la escritura normal el
    live.json podía quedar a medias; al arrancar, el JSON roto se leía como
    vacío y se perdían el enlace y la hora de salida (la carrera "empezaba de
    cero"). Con os.replace, o está el fichero viejo entero o el nuevo entero.
    """
    tmp = LIVE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, LIVE_PATH)


def merge_live(patch):
    with live_lock:
        current = read_live()
        current.update(patch)
        current["updated"] = datetime.now(timezone.utc).isoformat()
        write_live(current)
        return current


# lo último que dijo iGPSPORT cuando NO dio datos (p. ej. 40604 "no se
# encuentra la actividad, ¿ha terminado o no ha empezado?")
aviso_igpsport = {"texto": None}
_formato_visto = set()


def leer_telemetria(url):
    """Devuelve (telemetria, via). Con un enlace de iGPSPORT va por su API
    JSON; con cualquier otro, raspado genérico del HTML."""
    ident = igpsport_id(url)
    if ident:
        crudo = fetch_page(IGPSPORT_API + ident)
        payload = json.loads(crudo)
        codigo = payload.get("code") if isinstance(payload, dict) else None
        # iGPSPORT contesta en chino; el caso de siempre, traducido
        mensaje = ("su directo ha terminado o aún no ha empezado" if codigo == 40604
                   else payload.get("message", "") if isinstance(payload, dict) else "")
        aviso_igpsport["texto"] = (None if codigo in (0, None) else f"{codigo}: {mensaje}"[:160])
        telemetria = extract_igpsport(payload)
        # iGPSPORT dice "bien" pero no entendemos lo que manda: se guarda la
        # respuesta (una vez por enlace) para poder adaptar el lector
        if telemetria is None and codigo in (0, None) and ident not in _formato_visto:
            _formato_visto.add(ident)
            datos = payload.get("data") if isinstance(payload, dict) else None
            apuntar_historial("igpsport_formato_desconocido", id=ident,
                              claves=sorted(datos) if isinstance(datos, dict) else str(type(datos)),
                              muestra=crudo[:3000])
            print(f"[poller] iGPSPORT respondió bien pero sin datos reconocibles (id {ident})", flush=True)
        if telemetria is None and codigo in (0, None):
            aviso_igpsport["texto"] = "respuesta con un formato que no reconocemos (guardada en el historial)"
        return telemetria, "igpsport"
    return extract_telemetry(fetch_page(url)), "generico"


_meta = []


def punto_de_meta():
    if not _meta:
        _meta.append(puntos_de_la_ruta()[-1])
    return _meta[0]


def km_entre(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def ha_llegado(t, se_alejo=False):
    """A menos de 200 m del punto de meta, y o bien con más de 80 km hechos, o
    bien habiéndose alejado antes más de 5 km de meta. La ruta solo pasa tan
    cerca de meta en la salida (km 0-0,2) y en los últimos 200 m.
    ⚠️ Solo con los 80 km, un seguimiento nuevo empezado a mitad de carrera
    (que cuenta desde 0) no llegaba nunca a meta: pasó el 26/09."""
    if t.get("lat") is None or t.get("lon") is None:
        return False
    if (t.get("dist_km") or 0) < 80 and not se_alejo:
        return False
    return km_entre((t["lat"], t["lon"]), punto_de_meta()) < 0.2


def alejado_de_meta(lat, lon):
    return lat is not None and lon is not None and km_entre((lat, lon), punto_de_meta()) > 5


# --- GPS del móvil (Traccar Client) --------------------------------------
# En la carrera del 26/09/2026 la posición de iGPSPORT iba a saltos con los
# datos del móvil y, a las 14:51 (km 46), dejó de llegar para siempre: su
# directo depende de BSC500 -> Bluetooth -> app -> servidor de iGPSPORT, y
# con cobertura mala esa cadena se rompe y no recupera lo perdido.
# Traccar Client (gratis, Android e iPhone) manda la posición del móvil
# directamente aquí y, sin cobertura, GUARDA los puntos y los envía todos al
# volver. Mientras mande posición, manda sobre la de iGPSPORT; iGPSPORT sigue
# aportando pulso, cadencia y distancia.
GPS_CLAVE_PATH = os.path.join(ROOT, "gps.clave")      # no se sirve: sin extensión pública
HISTORIAL_PATH = os.path.join(ROOT, "historial.jsonl")  # ídem
GPS_VIGENTE = 120      # s: con un punto del móvil más reciente, no se usa el de iGPSPORT
PRECISION_MAXIMA = 100  # m: puntos peores se descartan (arranque en frío, túneles)


def clave_gps():
    try:
        with open(GPS_CLAVE_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def apuntar_historial(fuente, **datos):
    """Una línea por dato recibido: para poder auditar después qué llegó y
    cuándo (el día de la carrera solo se guardaba el último punto)."""
    try:
        with open(HISTORIAL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"recibido": datetime.now(timezone.utc).isoformat(),
                                "fuente": fuente, **datos}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def gps_reciente(live):
    t = live.get("gps_t")
    return bool(t) and time.time() - t < GPS_VIGENTE


def _segundos(valor):
    """Hora del punto: segundos o milisegundos Unix, o ISO 8601."""
    if valor in (None, ""):
        return time.time()
    try:
        n = float(valor)
        return n / 1000 if n > 1e11 else n
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def puntos_traccar(query, cuerpo):
    """Devuelve (identificador, [puntos]). Acepta los dos formatos de Traccar
    Client: parámetros en la URL (protocolo OsmAnd, velocidad en nudos, que
    usan también OsmAnd y GPSLogger) y JSON (Traccar Client 9, velocidad en
    m/s, varios puntos de golpe cuando vuelve la cobertura)."""
    q = {k: v[0] for k, v in parse_qs(query).items()}
    crudos, ident = [], None
    if cuerpo:
        try:
            j = json.loads(cuerpo)
        except (ValueError, UnicodeDecodeError):
            j = None
        if isinstance(j, dict):
            ident = j.get("device_id") or j.get("id")
            locs = j.get("location") or j.get("locations") or []
            for loc in (locs if isinstance(locs, list) else [locs]):
                if not isinstance(loc, dict):
                    continue
                c = loc.get("coords") or {}
                v = _numero(c.get("speed"))
                crudos.append({"lat": c.get("latitude"), "lon": c.get("longitude"),
                               "t": _segundos(loc.get("timestamp")),
                               "kmh": v * 3.6 if v is not None and v >= 0 else None,
                               "precision": c.get("accuracy"),
                               "bateria": (loc.get("battery") or {}).get("level")})
        elif j is None:
            try:
                q.update({k: v[0] for k, v in parse_qs(cuerpo.decode("utf-8")).items()})
            except UnicodeDecodeError:
                pass
    if "lat" in q and "lon" in q:
        v = _numero(q.get("speed"))
        crudos.append({"lat": q["lat"], "lon": q["lon"], "t": _segundos(q.get("timestamp")),
                       "kmh": v * 1.852 if v is not None and v >= 0 else None,
                       "precision": q.get("accuracy"), "bateria": q.get("batt")})
    ident = ident or q.get("id") or q.get("deviceid")

    puntos = []
    for p in crudos:
        lat, lon = _numero(p["lat"]), _numero(p["lon"])
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) \
                or (lat == 0 and lon == 0):
            continue
        precision = _numero(p["precision"])
        if precision is not None and precision > PRECISION_MAXIMA:
            continue
        bateria = _numero(p["bateria"])
        if bateria is not None and bateria <= 1:
            bateria *= 100          # el JSON la da de 0 a 1
        puntos.append({"lat": lat, "lon": lon, "t": p["t"], "kmh": p["kmh"],
                       "precision": precision, "bateria": bateria})
    return ident, puntos


def recibir_gps(puntos):
    puntos.sort(key=lambda p: p["t"])
    for p in puntos:
        apuntar_historial("gps", lat=p["lat"], lon=p["lon"],
                          hora=datetime.fromtimestamp(p["t"], timezone.utc).isoformat(),
                          kmh=p["kmh"], precision=p["precision"], bateria=p["bateria"])
    ultimo = puntos[-1]
    live = read_live()
    # los que llegan de la cola (sin cobertura) pueden ser más viejos que lo
    # que ya tenemos: al historial sí, a la posición en directo no
    if ultimo["t"] <= (live.get("gps_t") or 0):
        return
    # Distancia recorrida con el GPS del móvil: sin enlace de iGPSPORT no
    # había ninguna, y la llegada a meta la necesita (más de 80 km). Los
    # saltos imposibles (más de 90 km/h entre dos puntos) no suman.
    dist = live.get("gps_dist_km") or 0.0
    previo = live.get("gps_ult")
    for p in puntos:
        if previo and p["t"] > previo[2]:
            tramo = km_entre((previo[0], previo[1]), (p["lat"], p["lon"]))
            if tramo / max(1.0, p["t"] - previo[2]) * 3600 < 90:
                dist += tramo
        if not previo or p["t"] > previo[2]:
            previo = [p["lat"], p["lon"], p["t"]]
    hora = datetime.fromtimestamp(ultimo["t"], timezone.utc).isoformat()
    patch = {"lat": ultimo["lat"], "lon": ultimo["lon"], "gps_t": ultimo["t"],
             "gps_at": hora, "data_at": hora, "fuente_posicion": "movil",
             "gps_dist_km": round(dist, 3), "gps_ult": previo}
    distancia = max(live.get("dist_km") or 0, dist)
    se_alejo = live.get("lejos_de_meta") or any(alejado_de_meta(p["lat"], p["lon"]) for p in puntos)
    if se_alejo and not live.get("lejos_de_meta"):
        patch["lejos_de_meta"] = True
    if not live.get("finished_at") and live.get("started_at") and \
            ha_llegado({"lat": ultimo["lat"], "lon": ultimo["lon"], "dist_km": distancia}, se_alejo):
        patch["finished_at"] = hora
    if ultimo["kmh"] is not None:
        patch["speed_kmh"] = round(ultimo["kmh"], 1)
    if ultimo["bateria"] is not None:
        patch["bateria_movil"] = round(ultimo["bateria"])
    merge_live(patch)


def huella(t):
    """Lo que cambia cuando de verdad llega un dato nuevo del BSC500."""
    return tuple(t.get(k) for k in ("lat", "lon", "dist_km", "elapsed"))


def poll_loop(url, stop_event):
    first = True
    fallos = 0
    sin_datos = False
    ultima_huella = None
    ultimos_sensores = None
    frenados = False
    sums = {"speed_kmh": 0.0, "hr": 0.0, "cadence": 0.0}
    counts = {"speed_kmh": 0, "hr": 0, "cadence": 0}
    while not stop_event.is_set():
        try:
            telemetry, via = leer_telemetria(url)
            if telemetry:
                patch = dict(telemetry)
                # iGPSPORT ya da sus propias medias; solo las calculamos
                # nosotros cuando la fuente no las trae
                for key in ("speed_kmh", "hr", "cadence"):
                    if key in telemetry and key + "_avg" not in telemetry:
                        sums[key] += telemetry[key]
                        counts[key] += 1
                        patch[key + "_avg"] = round(sums[key] / counts[key], 1)
                patch["extract_status"] = "ok (" + via + ")"
                # ⚠️ "updated" se renueva en CADA consulta, llegue algo nuevo o
                # no: con el móvil sin cobertura la web seguía diciendo
                # "Última actualización: ahora" con la posición congelada, y en
                # meta el tiempo final seguía creciendo. data_at solo avanza
                # cuando el dato cambia de verdad.
                nuevo = huella(telemetry) != ultima_huella
                sensores = (telemetry.get("hr"), telemetry.get("cadence"))
                # igpsport_at: cuándo dio iGPSPORT algo nuevo por última vez.
                # La web oculta pulso y cadencia si lleva 3 min callado: si su
                # directo muere, se quedaban clavados en el último valor.
                if nuevo or sensores != ultimos_sensores:
                    ultimos_sensores = sensores
                    patch["igpsport_at"] = datetime.now(timezone.utc).isoformat()
                if nuevo:
                    ultima_huella = huella(telemetry)
                    patch["data_at"] = datetime.now(timezone.utc).isoformat()
                    apuntar_historial("igpsport", **{k: telemetry.get(k) for k in (
                        "lat", "lon", "dist_km", "elapsed", "speed_kmh", "hr", "cadence")})
                # ⚠️ La posición de iGPSPORT solo se escribe si es un punto
                # NUEVO y el móvil lleva 2 min sin mandar nada. Antes se
                # reescribía en cada consulta aunque no cambiara: si Traccar
                # se callaba, la foto saltaba hacia atrás al último punto
                # (más viejo) de iGPSPORT.
                if not nuevo or gps_reciente(read_live()):
                    for k in ("lat", "lon", "speed_kmh"):
                        patch.pop(k, None)
                if "lat" in patch:
                    patch["fuente_posicion"] = "igpsport"
                patch["igpsport_aviso"] = None
                # la hora de llegada se apunta UNA vez: si después sigue
                # pedaleando (hasta el coche, a casa) el tiempo final no crece
                estado = read_live()
                se_alejo = estado.get("lejos_de_meta") or alejado_de_meta(
                    telemetry.get("lat"), telemetry.get("lon"))
                if se_alejo and not estado.get("lejos_de_meta"):
                    patch["lejos_de_meta"] = True
                if ha_llegado(telemetry, se_alejo) and not estado.get("finished_at") \
                        and estado.get("started_at"):
                    patch["finished_at"] = datetime.now(timezone.utc).isoformat()
                merge_live(patch)
                fallos = 0
                sin_datos = False
            else:
                fallos += 1
                # solo se apunta al empezar a faltar datos, no cada 20 s
                if not sin_datos:
                    apuntar_historial("igpsport_sin_datos", aviso=aviso_igpsport["texto"])
                    print(f"[poller] iGPSPORT sin datos: {aviso_igpsport['texto']}", flush=True)
                sin_datos = True
                if first or fallos > 3:
                    merge_live({"extract_status": "sin_datos",
                                "igpsport_aviso": aviso_igpsport["texto"]})
        except Exception as exc:
            fallos += 1
            # los valores ya recibidos NO se tocan: si deja de compartir (o se
            # queda sin cobertura), la web sigue enseñando el último estado
            codigo = getattr(exc, "code", None)
            sin_datos = False
            frenados = codigo in (403, 429)
            if frenados:
                # nos están frenando: retirarse un buen rato, no insistir
                fallos = max(fallos, 6)
                print(f"[poller] iGPSPORT devolvió {codigo}: esperando", flush=True)
            else:
                print(f"[poller] error: {str(exc)[:160]}", flush=True)
            merge_live({"extract_status": ("sin señal" if fallos > 3
                                           else "error: " + str(exc)[:120])})
        first = False
        # espera normal si todo va bien; si falla, el doble cada vez
        espera = POLL_SECONDS if fallos == 0 else min(
            ESPERA_MAXIMA, POLL_SECONDS * (2 ** min(fallos, 5)))
        # "La actividad aún no ha empezado" no es un error: si se pega el
        # enlace a las 08:15 y se espera hasta 5 min entre consultas, la web
        # tardaba eso en enterarse de que ya había salido. Tope de 1 min.
        # ⚠️ Con un fallo de red cualquiera se llegaba a esperar 5 min: al
        # volver la cobertura la web tardaba en enterarse. Solo un bloqueo de
        # verdad (403/429 sin datos) espera tanto; lo demás, 1 min como mucho,
        # y "aún sin datos", 20 s.
        if not frenados:
            espera = min(espera, 60)
        if sin_datos:
            espera = min(espera, 20)
        frenados = False
        stop_event.wait(espera)


# --- simulador de carrera --------------------------------------------------
# Recorre la ruta real a toda pastilla escribiendo en live.json lo mismo que
# escribiría el BSC500. Sirve para ver moverse la foto, el trazado azul, el
# perfil y las métricas sin esperar al sábado.
simulador = {"thread": None, "stop": None}


def puntos_de_la_ruta():
    with open(os.path.join(ROOT, "route.geojson"), encoding="utf-8") as f:
        coords = json.load(f)["features"][0]["geometry"]["coordinates"]
    return [(lat, lon) for lon, lat in coords]


def simular_loop(stop_event, segundos):
    puntos = puntos_de_la_ruta()
    total = len(puntos)
    inicio = time.time()
    hr_base, cad_base = 138, 82
    i = 0
    while not stop_event.is_set() and i < total:
        avance = (time.time() - inicio) / segundos      # 0 -> 1
        i = min(total - 1, int(avance * total))
        lat, lon = puntos[i]
        recorrido = 103.36 * (i / (total - 1))
        merge_live({
            "status_label": "SIMULACIÓN",
            "lat": lat, "lon": lon,
            "speed_kmh": round(22 + 8 * ((i % 37) / 37), 1),
            "speed_kmh_avg": 24.5,
            "hr": hr_base + (i % 25),
            "hr_avg": hr_base + 6,
            "cadence": cad_base + (i % 11),
            "cadence_avg": cad_base + 3,
            "dist_km": round(recorrido, 2),
            "extract_status": "simulación",
            "igpsport_at": datetime.now(timezone.utc).isoformat(),
            "data_at": datetime.now(timezone.utc).isoformat(),
        })
        if avance >= 1:
            break
        stop_event.wait(1)
    if not stop_event.is_set():
        merge_live({"status_label": "Finalizada (simulación)",
                    "finished_at": datetime.now(timezone.utc).isoformat()})


def parar_simulacion():
    if simulador["stop"] is not None:
        simulador["stop"].set()
    simulador["thread"] = None
    simulador["stop"] = None


def arrancar_simulacion(segundos=120):
    parar_simulacion()
    stop_event = threading.Event()
    hilo = threading.Thread(target=simular_loop, args=(stop_event, segundos), daemon=True)
    simulador["thread"] = hilo
    simulador["stop"] = stop_event
    merge_live({"started_at": datetime.now(timezone.utc).isoformat(), "livetrack_url": None,
                "finished_at": None})
    hilo.start()


def start_poller(url):
    stop_previous_poller()
    stop_event = threading.Event()
    thread = threading.Thread(target=poll_loop, args=(url, stop_event), daemon=True)
    poller["thread"] = thread
    poller["stop"] = stop_event
    poller["url"] = url
    thread.start()


def stop_previous_poller():
    if poller["stop"] is not None:
        poller["stop"].set()
    poller["thread"] = None
    poller["stop"] = None
    poller["url"] = None


# Lista blanca: cualquier otra cosa (server.py, los .sh de réplica, las
# configuraciones de keepalived con su auth_pass, __pycache__...) se responde
# como si no existiera.
EXTENSIONES_PUBLICAS = {
    ".html", ".css", ".js", ".json", ".geojson", ".webmanifest",
    ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".txt",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _ruta_publica(self):
        ruta = self.path.split("?")[0].split("#")[0]
        if ruta in ("/", "/index.html"):
            return True
        if ruta.endswith("/"):          # nada de listados de directorio
            return False
        return os.path.splitext(ruta)[1].lower() in EXTENSIONES_PUBLICAS

    def _gps(self, cuerpo=b""):
        _, _, query = self.path.partition("?")
        ident, puntos = puntos_traccar(query, cuerpo)
        clave = clave_gps()
        if not clave or not ident or not compare_digest(str(ident), clave):
            self._send_json(403, {"error": "identificador incorrecto"})
            return
        if puntos:
            recibir_gps(puntos)
        # Traccar solo borra los puntos de su cola si le contestamos 200
        self._send_json(200, {"ok": True, "puntos": len(puntos)})

    def do_GET(self):
        if self.path.startswith("/api/gps"):
            self._gps()
            return
        if not self._ruta_publica():
            self.send_error(404, "Not Found")
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._ruta_publica():
            self.send_error(404, "Not Found")
            return
        super().do_HEAD()

    def end_headers(self):
        # El navegador se quedaba con el css/js viejo y el usuario veía la web
        # rota después de desplegar. Con no-cache revalida siempre: para
        # ficheros de 16 KB no cuesta nada y evita enseñar una versión antigua.
        ruta = self.path.split("?")[0]
        if ruta.endswith((".html", ".css", ".js", ".json", "/")):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def hora_a_iso(hhmm):
        """'08:30' -> instante UTC de HOY a esa hora local del servidor.

        Óscar enciende el GPS en la salida (08:15) pero la carrera arranca a
        las 08:30; sin esto el cronómetro de la web iría 15 min adelantado."""
        try:
            h, m = [int(x) for x in str(hhmm).strip().split(":")[:2]]
        except Exception:
            return None
        if not (0 <= h < 24 and 0 <= m < 60):
            return None
        local = datetime.now().astimezone().replace(
            hour=h, minute=m, second=0, microsecond=0)
        return local.astimezone(timezone.utc).isoformat()

    def hora_de_llegada(self, data, actual):
        """Hora de llegada al pulsar "Finalizar": la que se escriba en el
        panel; si no, la que detectó el GPS; si no, la del último dato si es
        reciente; y si no, ahora.
        ⚠️ Antes usaba siempre el último dato: con la web clavada desde las
        14:51, el tiempo final habría salido de cuando se cortó el directo."""
        escrita = str(data.get("hora_llegada") or "").strip()
        if escrita and self.hora_a_iso(escrita):
            return self.hora_a_iso(escrita)
        if actual.get("finished_at"):
            return actual["finished_at"]
        ultimo = actual.get("data_at")
        if ultimo:
            try:
                if (datetime.now(timezone.utc) - datetime.fromisoformat(ultimo)).total_seconds() < 300:
                    return ultimo
            except ValueError:
                pass
        return datetime.now(timezone.utc).isoformat()

    def do_POST(self):
        if self.path.startswith("/api/gps"):
            try:
                largo = int(self.headers.get("Content-Length", 0))
            except ValueError:
                largo = -1
            # con la cola llena (horas sin cobertura) Traccar manda muchos
            # puntos de golpe: tope generoso, pero tope
            if not 0 <= largo <= 2_000_000:
                self._send_json(413, {"error": "petición demasiado grande"})
                return
            self._gps(self.rfile.read(largo) if largo else b"")
            return
        if self.path != "/api/live":
            self._send_json(404, {"error": "not found"})
            return
        # el panel manda unos pocos cientos de bytes; sin tope, cualquiera
        # podía hacer que el servidor leyera en memoria lo que quisiera
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if not 0 <= length <= 16_384:
            self._send_json(413, {"error": "petición demasiado grande"})
            return
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        ip = self.client_address[0]
        # ⚠️ Detrás de Cloudflare TODAS las visitas llegan con la misma IP, así
        # que castigar por IP dejaba fuera también a Óscar si alguien probaba
        # claves. Ahora el castigo NO rechaza de entrada: frena el intento un
        # segundo y luego compara. Al que acierta le da igual; al que adivina,
        # le limita el ritmo igual que antes.
        if segundos_de_castigo(ip):
            time.sleep(1)

        if not ADMIN_TOKEN:
            print("[admin] ADMIN_TOKEN vacío: no se admite ningún acceso", flush=True)
            self._send_json(503, {"error": "servidor sin clave configurada"})
            return
        if not compare_digest(str(data.get("token", "")), ADMIN_TOKEN):
            fallo_de(ip)
            print(f"[admin] clave incorrecta desde {ip}", flush=True)
            self._send_json(403, {"error": "clave incorrecta"})
            return
        acierto_de(ip)

        accion = data.get("action")

        if accion == "gps_info":
            self._send_json(200, {"ok": True, "gps_id": clave_gps(), "live": read_live()})
            return

        if accion == "simular":
            arrancar_simulacion(int(data.get("segundos", 120)))
            self._send_json(200, {"ok": True, "live": read_live()})
            return

        if accion == "reset":
            apuntar_historial("reset")
            parar_simulacion()
            stop_previous_poller()
            current = merge_live({
                "status_label": "Sin iniciar", "livetrack_url": None,
                "extract_status": None, "started_at": None, "elapsed": None,
                "lat": None, "lon": None, "speed_kmh": None, "speed_kmh_avg": None,
                "hr": None, "hr_avg": None, "cadence": None, "cadence_avg": None,
                "dist_km": None, "data_at": None, "finished_at": None,
                "gps_t": None, "gps_at": None, "bateria_movil": None,
                "gps_dist_km": None, "gps_ult": None, "igpsport_at": None,
                "fuente_posicion": None, "igpsport_aviso": None, "lejos_de_meta": None,
            })
            self._send_json(200, {"ok": True, "live": current})
            return

        if accion == "empezar":
            # Carrera solo con Traccar: sin enlace de iGPSPORT el crono no
            # arrancaba nunca (se ponía en marcha al pegar el enlace).
            hora = str(data.get("hora_salida") or read_live().get("hora_salida") or "").strip()
            inicio = self.hora_a_iso(hora) if hora else None
            parar_simulacion()
            stop_previous_poller()
            apuntar_historial("empezar", hora_salida=hora)
            current = merge_live({
                "status_label": "En carrera", "livetrack_url": None, "extract_status": None,
                "started_at": inicio or datetime.now(timezone.utc).isoformat(),
                "hora_salida": hora or None, "finished_at": None, "elapsed": None,
                "speed_kmh": None, "speed_kmh_avg": None, "hr": None, "hr_avg": None,
                "cadence": None, "cadence_avg": None, "dist_km": None, "data_at": None,
                "gps_dist_km": 0, "gps_ult": None, "igpsport_at": None, "igpsport_aviso": None,
                "lejos_de_meta": None,
            })
            self._send_json(200, {"ok": True, "live": current})
            return

        if accion == "stop":
            parar_simulacion()
            stop_previous_poller()
            # ⚠️ Antes borraba started_at y las medias: pulsar "Finalizar" en
            # meta dejaba la web sin tiempo final y sin medias justo cuando
            # todo el mundo mira el resultado. Solo se para la consulta.
            actual = read_live()
            current = merge_live({
                "status_label": "Finalizada", "livetrack_url": None, "extract_status": None,
                # si el GPS ya marcó la llegada se respeta; si no (móvil muerto
                # en los últimos km), vale la hora del último dato recibido
                "finished_at": self.hora_de_llegada(data, actual),
            })
            self._send_json(200, {"ok": True, "live": current})
            return

        # los campos de número se fuerzan a número: si en "Avanzado" se cuela
        # un texto, la web recibía NaN y se quedaba con la gráfica en blanco
        NUMEROS = ("speed_kmh", "hr", "cadence", "dist_km", "lat", "lon",
                   "speed_kmh_avg", "hr_avg", "cadence_avg")
        patch = {}
        for key in ("status_label", "livetrack_url", "elapsed") + NUMEROS:
            if key not in data:
                continue
            valor = data[key]
            if key in NUMEROS and valor is not None and valor != "":
                try:
                    valor = float(valor)
                except (TypeError, ValueError):
                    continue
            patch[key] = valor

        # cualquier enlace que se pegue reinicia el seguimiento y el reloj,
        # aunque sea el mismo: si lo vuelves a pegar es que quieres empezar
        new_url = data.get("livetrack_url")
        if new_url:
            patch.setdefault("status_label", "En carrera")
            patch["finished_at"] = None
            patch["extract_status"] = "buscando…"
            # Si hay hora oficial de salida, el reloj cuenta SIEMPRE desde
            # ella. Si no la hubiera, solo se pone en marcha la primera vez:
            # así, pegar otro enlace a mitad de carrera (móvil muerto, app
            # cerrada...) no reinicia el cronómetro.
            actual = read_live()
            guardada = actual.get("hora_salida")
            if guardada and self.hora_a_iso(guardada):
                patch["started_at"] = self.hora_a_iso(guardada)
            elif not actual.get("started_at"):
                patch["started_at"] = datetime.now(timezone.utc).isoformat()
            apuntar_historial("enlace", id=igpsport_id(new_url), url=new_url[:300])
            print(f"[admin] enlace nuevo: id={igpsport_id(new_url)}", flush=True)
            patch["igpsport_aviso"] = None
            start_poller(new_url)

        # hora oficial de salida (HH:MM). Manda sobre el momento de pegar el
        # enlace, pero por sí sola NO pone el crono en marcha: guardarla días
        # antes no puede hacer que la web se crea que la carrera ha empezado.
        if "hora_salida" in data:
            valor = str(data.get("hora_salida") or "").strip()
            if not valor:
                patch["hora_salida"] = None
            else:
                iso = self.hora_a_iso(valor)
                if iso:
                    patch["hora_salida"] = valor
                    en_marcha = new_url or read_live().get("livetrack_url")
                    if en_marcha:
                        patch["started_at"] = iso

        current = merge_live(patch)
        self._send_json(200, {"ok": True, "live": current})

    def log_message(self, fmt, *args):
        pass


VIP = os.environ.get("VIP_21LEGUAS", "192.168.68.202")


def tengo_la_vip():
    """¿Es esta Pi la que está sirviendo la carrera?

    Se comprueba intentando reservar un puerto cualquiera en la VIP: si la
    dirección no está puesta en esta máquina, el sistema lo impide. Sin
    dependencias ni llamar a `ip`."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((VIP, 0))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def watch_live_file():
    """En el respaldo, live.json llega replicado desde el titular. Si trae un
    enlace distinto del que estamos siguiendo, arrancamos el poller aquí — así
    la Pi de respaldo sigue dando datos si el titular se cae."""
    while True:
        try:
            # ⚠️ El respaldo recibe live.json replicado CON el enlace dentro.
            # Sin esta comprobación, las dos Pis preguntaban a iGPSPORT a la
            # vez: el doble de peticiones (más papeletas para que nos corten)
            # y dos escrituras pisándose. Solo consulta quien tiene la VIP.
            if not tengo_la_vip():
                if poller["url"]:
                    stop_previous_poller()
                threading.Event().wait(20)
                continue
            url = read_live().get("livetrack_url")
            # ⚠️ si el hilo del poller muere por algo imprevisto (p. ej. un
            # error al guardar dentro de su propio except), nadie lo relanzaba:
            # el seguimiento se paraba en silencio hasta reiniciar el servicio
            muerto = poller["thread"] is not None and not poller["thread"].is_alive()
            if url and (url != poller["url"] or muerto):
                if muerto:
                    print("[poller] el hilo había muerto: relanzado", flush=True)
                start_poller(url)
            elif not url and poller["url"]:
                stop_previous_poller()
        except Exception:
            pass
        threading.Event().wait(20)


if __name__ == "__main__":
    live = read_live()
    if live.get("livetrack_url") and tengo_la_vip():
        start_poller(live["livetrack_url"])
    threading.Thread(target=watch_live_file, daemon=True).start()
    # ThreadingHTTPServer y NO TCPServer: el de un solo hilo atiende una
    # petición cada vez, así que un móvil con mala cobertura dejaba clavado al
    # resto. Con la web abierta en varios teléfonos pidiendo live.json cada
    # 15 s, eso llegó a tumbar el chequeo de keepalived y a mover la VIP.
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer.daemon_threads = True
    with http.server.ThreadingHTTPServer((BIND_HOST, PORT), Handler) as httpd:
        print(f"21 Leguas tracker en http://127.0.0.1:{PORT}"
          + ("" if ADMIN_TOKEN else "  ⚠️ SIN ADMIN_TOKEN: el panel no dejará entrar"))
        httpd.serve_forever()
