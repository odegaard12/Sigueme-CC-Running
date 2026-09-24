import http.server
import json
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
    ruta = datos.get("route") or {}
    resumen = ruta.get("summary") or {}
    fuera = {}

    puntos = decode_polyline(ruta.get("gpsCoords") or "")
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
        "User-Agent": "Mozilla/5.0 (compatible; la carreraTracker/1.0)"
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


def leer_telemetria(url):
    """Devuelve (telemetria, via). Con un enlace de iGPSPORT va por su API
    JSON; con cualquier otro, raspado genérico del HTML."""
    ident = igpsport_id(url)
    if ident:
        crudo = fetch_page(IGPSPORT_API + ident)
        return extract_igpsport(json.loads(crudo)), "igpsport"
    return extract_telemetry(fetch_page(url)), "generico"


def huella(t):
    """Lo que cambia cuando de verdad llega un dato nuevo del BSC500."""
    return tuple(t.get(k) for k in ("lat", "lon", "dist_km", "elapsed"))


def poll_loop(url, stop_event):
    first = True
    fallos = 0
    sin_datos = False
    ultima_huella = None
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
                if huella(telemetry) != ultima_huella:
                    ultima_huella = huella(telemetry)
                    patch["data_at"] = datetime.now(timezone.utc).isoformat()
                merge_live(patch)
                fallos = 0
                sin_datos = False
            else:
                fallos += 1
                sin_datos = True
                if first or fallos > 3:
                    merge_live({"extract_status": "sin_datos"})
        except Exception as exc:
            fallos += 1
            # los valores ya recibidos NO se tocan: si deja de compartir (o se
            # queda sin cobertura), la web sigue enseñando el último estado
            codigo = getattr(exc, "code", None)
            sin_datos = False
            if codigo in (403, 429):
                # nos están frenando: retirarse un buen rato, no insistir
                fallos = max(fallos, 6)
                print(f"[poller] iGPSPORT devolvió {codigo}: esperando", flush=True)
            merge_live({"extract_status": ("sin señal" if fallos > 3
                                           else "error: " + str(exc)[:120])})
        first = False
        # espera normal si todo va bien; si falla, el doble cada vez
        espera = POLL_SECONDS if fallos == 0 else min(
            ESPERA_MAXIMA, POLL_SECONDS * (2 ** min(fallos, 5)))
        # "La actividad aún no ha empezado" no es un error: si se pega el
        # enlace a las 08:15 y se espera hasta 5 min entre consultas, la web
        # tardaba eso en enterarse de que ya había salido. Tope de 1 min.
        if sin_datos:
            espera = min(espera, 60)
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
            "data_at": datetime.now(timezone.utc).isoformat(),
        })
        if avance >= 1:
            break
        stop_event.wait(1)
    if not stop_event.is_set():
        merge_live({"status_label": "Finalizada (simulación)"})


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
    merge_live({"started_at": datetime.now(timezone.utc).isoformat(), "livetrack_url": None})
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

    def do_GET(self):
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

        Odegaard12 enciende el GPS en la salida (08:15) pero la carrera arranca a
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

    def do_POST(self):
        if self.path != "/api/live":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        ip = self.client_address[0]
        # ⚠️ Detrás de Cloudflare TODAS las visitas llegan con la misma IP, así
        # que castigar por IP dejaba fuera también a Odegaard12 si alguien probaba
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

        if accion == "simular":
            arrancar_simulacion(int(data.get("segundos", 120)))
            self._send_json(200, {"ok": True, "live": read_live()})
            return

        if accion == "reset":
            parar_simulacion()
            stop_previous_poller()
            current = merge_live({
                "status_label": "Sin iniciar", "livetrack_url": None,
                "extract_status": None, "started_at": None, "elapsed": None,
                "lat": None, "lon": None, "speed_kmh": None, "speed_kmh_avg": None,
                "hr": None, "hr_avg": None, "cadence": None, "cadence_avg": None,
                "dist_km": None, "data_at": None,
            })
            self._send_json(200, {"ok": True, "live": current})
            return

        if accion == "stop":
            parar_simulacion()
            stop_previous_poller()
            # ⚠️ Antes borraba started_at y las medias: pulsar "Finalizar" en
            # meta dejaba la web sin tiempo final y sin medias justo cuando
            # todo el mundo mira el resultado. Solo se para la consulta.
            current = merge_live({
                "status_label": "Finalizada", "livetrack_url": None, "extract_status": None,
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


VIP = os.environ.get("VIP_SIGUEME", "IP_FLOTANTE")


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
            if url and url != poller["url"]:
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
        print(f"la carrera tracker en http://127.0.0.1:{PORT}"
          + ("" if ADMIN_TOKEN else "  ⚠️ SIN ADMIN_TOKEN: el panel no dejará entrar"))
        httpd.serve_forever()
