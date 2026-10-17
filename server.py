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
try:
    from curl_cffi import requests as cffi_requests      # solo para iGPSPORT
except ImportError:
    cffi_requests = None
from datetime import datetime, timedelta, timezone
import base64
import mimetypes
import shutil
import unicodedata
import hashlib
import importlib
from zoneinfo import ZoneInfo
import ipaddress
import secrets
import hmac
from hmac import compare_digest
import pathlib
import posixpath
import tempfile
from urllib.parse import parse_qs, unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
LIVE_PATH = os.path.join(ROOT, "live.json")
CARRERA_PATH = os.path.join(ROOT, "carrera.json")


def carrera():
    """Datos de la carrera (carrera.json): distancia, km mínimos para meta…
    Se lee cada vez (es pequeño) para poder cambiarlo sin reiniciar."""
    try:
        with open(CARRERA_PATH, encoding="utf-8-sig") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def carrera_editable():
    """Como carrera(), pero None si el fichero existe y no se entiende: así
    nadie lo sobrescribe con un trozo y se pierden nombre, fecha y hora."""
    if not os.path.exists(CARRERA_PATH):
        return {}
    try:
        with open(CARRERA_PATH, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def zona_carrera():
    try:
        return ZoneInfo(carrera().get("zona_horaria") or "Europe/Madrid")
    except Exception:
        return ZoneInfo("Europe/Madrid")


def km_minimos_meta():
    """Km hechos a partir de los cuales pasar cerca de meta cuenta como llegada
    (la salida suele estar junto a la meta). Por defecto, el 80 % de la ruta."""
    c = carrera()
    return c.get("km_minimos_meta") or 0.8 * (c.get("distancia_km") or 100)
# ⚠️ NUNCA poner la clave de verdad aquí: este fichero estaba servido por la
# propia web (http://.../server.py devolvía 200) y cualquiera podía leerla.
# Ahora la clave llega solo por el entorno (systemd) y, además, el servidor no
# entrega ficheros que no sean los de la web (ver EXTENSIONES_PUBLICAS).
# Panel: usuario y HASH de la clave (scrypt), nunca la clave en claro. Se
# generan con:  python3 server.py --hash-clave
ADMIN_USER = os.environ.get("ADMIN_USER", "")
ADMIN_HASH = os.environ.get("ADMIN_HASH", "")


def _scrypt(clave, sal):
    return hashlib.scrypt(clave.encode(), salt=sal, n=2 ** 14, r=8, p=1, dklen=32).hex()


if sys.argv[1:2] == ["--hash-clave"]:
    import getpass
    _sal = os.urandom(16)
    print(f"ADMIN_HASH=scrypt:{_sal.hex()}:{_scrypt(getpass.getpass('Clave nueva: '), _sal)}")
    sys.exit(0)


# ⚠️ Cada scrypt usa ~16 MB: sin tope, cientos de intentos a la vez dejaban a
# la Pi sin memoria. Como mucho dos a la vez; el resto espera o se rechaza.
_scrypt_sem = threading.BoundedSemaphore(2)


def credenciales_ok(usuario, clave):
    if not (ADMIN_USER and ADMIN_HASH):
        return False
    try:
        tipo, sal, esperado = ADMIN_HASH.split(":")
        sal = bytes.fromhex(sal)
    except ValueError:
        return False
    if not _scrypt_sem.acquire(timeout=3):
        return False
    try:
        calculado = _scrypt(str(clave), sal)
    finally:
        _scrypt_sem.release()
    # en bytes: compare_digest con texto no ASCII ("ñ") lanzaba una excepción.
    # Las dos comparaciones siempre, en tiempo constante.
    return (compare_digest(str(usuario).encode(), ADMIN_USER.encode())
            & compare_digest(calculado.encode(), esperado.encode())) and tipo == "scrypt"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8710
BIND_HOST = os.environ.get("BIND_HOST", "0.0.0.0")
# Preguntar cada 8 s eran 5 400 peticiones en las 12 h de carrera a una API de
# iGPSPORT que no es pública: demasiado para que no se fijen en nosotros. El
# ciclocomputador sube por el móvil cada pocos segundos, así que con 15 s no se pierde
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
# los intentos castigados pasan de uno en uno: con 50 a la vez, cada uno
# esperaba su segundo en paralelo y el freno no frenaba nada
castigo_lock = threading.Lock()


def segundos_de_castigo(ip):
    with intentos_lock:
        fallos, ultimo = intentos.get(ip, (0, 0))
    if fallos < 5:
        return 0
    # del 5º al 9º fallo, frenazo; desde el 10º, 15 min bloqueada esa IP
    castigo = 5 if fallos < 10 else 900
    restante = castigo - (time.time() - ultimo)
    return int(restante) + 1 if restante > 0 else 0


def fallo_de(ip):
    with intentos_lock:
        fallos, _ = intentos.get(ip, (0, 0))
        intentos[ip] = (fallos + 1, time.time())


def acierto_de(ip):
    with intentos_lock:
        intentos.pop(ip, None)

# --- live.json público -------------------------------------------------------
# ⚠️ live.json guarda TODO el estado (enlace de iGPSPORT, batería del móvil,
# avisos, contadores internos). Al público solo va lo que pinta la web.
CAMPOS_PUBLICOS = ("status_label", "started_at", "finished_at", "data_at", "updated", "lat", "lon",
                   "dist_km", "elapsed", "speed_kmh", "speed_kmh_avg", "hr", "hr_avg", "hr_at",
                   "cadence", "cadence_avg", "igpsport_at", "fuente_posicion")


def live_publico():
    d = read_live()
    p = {k: d[k] for k in CAMPOS_PUBLICOS if k in d}
    p["en_seguimiento"] = bool(d.get("livetrack_url"))
    # carrera.json "ocultar_m": si la salida o la meta son en casa, la posición
    # no se publica a menos de esos metros de ellas
    ocultar = carrera().get("ocultar_m") or 0
    if ocultar and p.get("lat") is not None and p.get("lon") is not None:
        try:
            ruta = puntos_de_la_ruta()
            cerca = min(km_entre((p["lat"], p["lon"]), ruta[0]), km_entre((p["lat"], p["lon"]), ruta[-1]))
            if cerca * 1000 < ocultar:
                p["lat"] = p["lon"] = None
        except Exception:
            p["lat"] = p["lon"] = None        # sin poder comprobarlo, mejor no publicarla
    return p


# --- archivo de carreras ---------------------------------------------------
# Cada carrera terminada se guarda en carreras/<AAAA-nombre>/ con sus datos
# (carrera.json, ruta, perfil, avituallamientos, resultado, avatar) y se ve en
# /<AAAA-nombre>/ con la misma web en modo resultado. Índice en /carreras/.
ARCHIVO_DIR = os.path.join(ROOT, "carreras")
mimetypes.add_type("application/geo+json", ".geojson")
mimetypes.add_type("application/manifest+json", ".webmanifest")
SLUG_RE = re.compile(r"^/(\d{4}-[a-z0-9-]{1,60})(/.*)?$")
FICHEROS_CARRERA = ("carrera.json", "route.geojson", "elevation.json", "aid_stations.json", "rider.png", "avisos.json")


def slug_de(c):
    if c.get("slug"):
        return str(c["slug"])
    base = unicodedata.normalize("NFKD", c.get("lugar") or c.get("nombre") or "carrera")
    base = re.sub(r"[^a-z0-9]+", "-", base.encode("ascii", "ignore").decode().lower()).strip("-")[:40]
    return f"{(c.get('fecha') or time.strftime('%Y'))[:4]}-{base or 'carrera'}"


def carreras_archivadas():
    """[(slug, carrera, resultado)] de la más reciente a la más antigua."""
    salida = []
    try:
        nombres = os.listdir(ARCHIVO_DIR)
    except OSError:
        return salida
    for slug in nombres:
        d = os.path.join(ARCHIVO_DIR, slug)
        if not SLUG_RE.match("/" + slug) or not os.path.isdir(d):
            continue
        datos = []
        for n in ("carrera.json", "resultado.json"):
            try:
                with open(os.path.join(d, n), encoding="utf-8") as f:
                    datos.append(json.load(f))
            except (OSError, ValueError):
                datos.append({})
        salida.append((slug, datos[0], datos[1]))
    return sorted(salida, key=lambda x: (x[1].get("fecha") or x[0]), reverse=True)


# --- preparar la carrera desde el panel ------------------------------------
# GPX → ruta y perfil, datos de la carrera, avituallamientos y plan de avisos
# se hacen desde el panel (las mismas funciones que herramientas/*.py). El plan
# de avisos NO lo manda el servidor: lo baja la app del móvil antes de salir y
# lo lanza ella, sin cobertura (el móvil enseña la notificación y Mi Fitness la
# pasa a la pulsera).
AVISOS_PATH = os.path.join(ROOT, "avisos.json")
HERRAMIENTAS = os.path.join(ROOT, "herramientas")
MAX_GPX = 20_000_000          # bytes: un GPX de 100 km con 1 punto/s ronda 5 MB


def herramienta(nombre):
    """Importa herramientas/<nombre>.py al usarla: si falta la carpeta, el
    servidor arranca igual y solo falla esa acción."""
    if HERRAMIENTAS not in sys.path:
        sys.path.insert(0, HERRAMIENTAS)
    # recargado cada vez (son ms): al desplegar una herramienta nueva no hace
    # falta reiniciar el servidor
    return importlib.reload(importlib.import_module(nombre))


def leer_json(nombre, defecto=None):
    try:
        with open(os.path.join(ROOT, nombre), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


datos_lock = threading.Lock()      # carrera.json, avisos.json, ruta…: un cambio cada vez


def escribir_json(nombre, datos):
    """Atómico, como live.json: o el fichero viejo entero o el nuevo entero.
    Temporal con punto (no se sirve), .tmp (no se replica) y nombre único."""
    fd, tmp = tempfile.mkstemp(dir=ROOT, prefix="." + nombre + ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, os.path.join(ROOT, nombre))


def plan_avisos():
    return leer_json("avisos.json")


def generar_plan(antes=None, cada=None, forzar=False):
    """Rehace avisos.json con el perfil, los avituallamientos y el D+ oficial.
    forzar (botón «Rehacer el plan»): con estos ajustes y textos automáticos.
    Si no: los ajustes del plan anterior, y se respetan los textos cambiados y
    los avisos quitados a mano (si siguen en el mismo km).
    Sin perfil escribe un plan vacío (nunca el de la carrera anterior) y devuelve None."""
    perfil = (leer_json("elevation.json") or {}).get("profile") or []
    viejo = plan_avisos() or {}
    if len(perfil) < 10:
        escribir_json("avisos.json", {"avisos": [], "subidas": [], "restante": [], "sin_perfil": True})
        return None
    if not forzar:
        antes = viejo.get("antes_km", 0.3)
        cada = viejo.get("cada_fijo")                                 # None = según la distancia
    plan = herramienta("plan_avisos").calcular(
        perfil, leer_json("aid_stations.json") or [], carrera().get("desnivel_m"), antes or 0.3, cada)
    plan["cada_fijo"] = cada
    if not forzar:
        cerca = lambda a, b: a.get("tipo") == b.get("tipo") and abs(a.get("km", -9) - b.get("km", 9)) < 0.05
        editados = [a for a in viejo.get("avisos", []) if a.get("editado")]
        quitados = [q for q in viejo.get("quitados", []) if isinstance(q, dict)]
        nuevos = []
        for a in plan["avisos"]:
            if any(cerca(a, q) for q in quitados):
                continue
            mio = next((e for e in editados if cerca(a, e)), None)
            nuevos.append(dict(a, texto=mio["texto"], editado=True) if mio else a)
        plan["avisos"], plan["quitados"] = nuevos, quitados
    escribir_json("avisos.json", plan)
    return plan


def _texto(valor, largo):
    return re.sub(r"[\x00-\x1f\x7f]", "", str(valor or "")).strip()[:largo]


def _numero_en(valor, minimo, maximo):
    """Número dentro de [minimo, maximo], None si viene vacío; ValueError si no vale."""
    if valor is None or valor == "":
        return None
    n = float(valor)
    if not (minimo <= n <= maximo):          # también descarta NaN
        raise ValueError
    return n


def limpiar_carrera(d):
    """Valida lo que manda el formulario del panel. Devuelve (carrera, error)."""
    base = carrera_editable()
    if base is None:
        return None, "carrera.json no se puede leer: arréglalo a mano antes de guardar"
    c = dict(base)
    try:
        for k, largo in (("nombre", 80), ("lugar", 80), ("modalidad", 40)):
            if k in d:
                c[k] = _texto(d[k], largo)
        if "fecha" in d:
            c["fecha"] = _texto(d["fecha"], 10)
            if c["fecha"]:
                c["fecha"] = datetime.strptime(c["fecha"], "%Y-%m-%d").date().isoformat()
        if "hora_salida" in d:
            c["hora_salida"] = _texto(d["hora_salida"], 5)
            if c["hora_salida"] and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", c["hora_salida"]):
                return None, "hora de salida no válida (HH:MM)"
        if "zona_horaria" in d:
            c["zona_horaria"] = _texto(d["zona_horaria"], 40) or "Europe/Madrid"
            ZoneInfo(c["zona_horaria"])
        for k, lo, hi in (("limite_h", 0.5, 200), ("distancia_km", 0.1, 2000), ("desnivel_m", 0, 50000),
                          ("km_minimos_meta", 0, 2000), ("ocultar_m", 0, 5000)):
            if k in d:
                c[k] = _numero_en(d[k], lo, hi)
                if c[k] is not None and k in ("desnivel_m", "ocultar_m"):
                    c[k] = int(c[k])
        if "slug" in d:
            c["slug"] = _texto(d["slug"], 65).lower()
            if c["slug"] and not re.fullmatch(r"\d{4}-[a-z0-9-]{1,60}", c["slug"]):
                return None, "dirección del archivo no válida: año-nombre, p. ej. 2027-mi-trail"
        if isinstance(d.get("corredor"), dict):
            c["corredor"] = {k: _texto(d["corredor"].get(k), n) for k, n in
                             (("nombre", 60), ("dorsal", 12), ("club", 60), ("categoria", 40))
                             if _texto(d["corredor"].get(k), n)}
        if isinstance(d.get("bici"), dict):
            piezas = d["bici"].get("piezas") or {}
            if not isinstance(piezas, dict) or len(piezas) > 30:
                return None, "piezas de la bici no válidas"
            c["bici"] = {"modelo": _texto(d["bici"].get("modelo"), 80),
                         "piezas": {_texto(k, 30): _texto(v, 60) for k, v in piezas.items() if _texto(k, 30)}}
            if not c["bici"]["modelo"] and not c["bici"]["piezas"]:
                c["bici"] = None
    except (TypeError, ValueError, KeyError, AttributeError):
        return None, "algún dato no es válido (revisa fecha, números y zona horaria)"
    except Exception:                       # ZoneInfoNotFoundError y compañía
        return None, "zona horaria desconocida (p. ej. Europe/Madrid)"
    c = {k: v for k, v in c.items() if v is not None and v != ""}
    if c.get("km_minimos_meta") and c.get("distancia_km") and c["km_minimos_meta"] >= c["distancia_km"]:
        return None, "los km mínimos para dar meta tienen que ser menos que la distancia (vacío = el 80 %)"
    if not c.get("nombre"):
        return None, "falta el nombre de la carrera"
    return c, None


def limpiar_avituallamientos(lista):
    if not isinstance(lista, list) or len(lista) > 60:
        return None, "lista de avituallamientos no válida"
    total = carrera().get("distancia_km") or 2000
    salida = []
    try:
        for a in lista:
            nombre, km = _texto(a.get("name"), 40), _numero_en(a.get("km"), 0, total + 1)
            if not nombre or km is None:
                raise ValueError
            fila = {"name": nombre, "km": round(km, 2)}
            for marca in ("principal", "taller"):
                if a.get(marca):
                    fila[marca] = True
            salida.append(fila)
    except (AttributeError, TypeError, ValueError):
        return None, f"cada avituallamiento necesita nombre y km (entre 0 y {total:g})"
    return sorted(salida, key=lambda a: a["km"]), None


def plan_para_la_app():
    """Todo lo que la app del móvil baja antes de salir para funcionar sin
    cobertura: carrera, ruta, perfil, avituallamientos y avisos."""
    ruta = leer_json("route.geojson") or {}
    try:
        coords = ruta["features"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError, TypeError):
        coords = []
    plan = plan_avisos() or {}
    return {"carrera": carrera(), "ruta": coords,
            "perfil": [[p["d"], p["ele"]] for p in (leer_json("elevation.json") or {}).get("profile", [])],
            "avituallamientos": leer_json("aid_stations.json") or [],
            "avisos": plan.get("avisos", []), "subidas": plan.get("subidas", []),
            "restante": plan.get("restante", []), "generado": plan.get("generado")}


def preparacion():
    """Lista de comprobación de la carrera para el panel."""
    c, plan = carrera(), plan_avisos()
    ruta = leer_json("route.geojson") or {}
    avit = leer_json("aid_stations.json") or []
    try:
        props = ruta["features"][0]["properties"]
    except (KeyError, IndexError, TypeError):
        props = {}
    live = read_live()
    return {"nombre": c.get("nombre"), "fecha": c.get("fecha"), "hora_salida": c.get("hora_salida"),
            "distancia_km": c.get("distancia_km"), "ruta_km": props.get("distance_km"),
            "avituallamientos": len(avit), "avisos": len((plan or {}).get("avisos", [])),
            "subidas": len((plan or {}).get("subidas", [])), "id_largo": len(clave_gps()) >= 30,
            "resultado_pendiente": os.path.exists(os.path.join(ROOT, "resultado.json")),
            "app_at": live.get("app_at")}


def hay_carrera_en_marcha():
    """En marcha, o preparada para hoy o más adelante: la portada es esa carrera
    (antes, quien entraba a las 08:00 iba al resultado de la anterior)."""
    d = read_live()
    if d.get("started_at") or d.get("livetrack_url"):
        return True
    fecha = carrera().get("fecha") or ""
    try:
        return fecha >= datetime.now(zona_carrera()).date().isoformat() and \
            slug_de(carrera()) not in {a[0] for a in carreras_archivadas()}
    except Exception:
        return False


_csp = {"mtime": None, "valor": ""}


def csp_web():
    """CSP de la web pública. Los dos <script> en línea de index.html van por
    su hash (sin 'unsafe-inline'); teselas de Esri (imagen) y AWS (relieve)."""
    ruta = os.path.join(ROOT, "index.html")
    try:
        mtime = os.path.getmtime(ruta)
        if mtime != _csp["mtime"]:
            with open(ruta, encoding="utf-8") as f:
                scripts = re.findall(r"<script>(.*?)</script>", f.read(), re.S)
            hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(x.encode()).digest()).decode() + "'"
                              for x in scripts)
            teselas = "https://server.arcgisonline.com https://s3.amazonaws.com"
            _csp.update(mtime=mtime, valor=(
                f"default-src 'self'; script-src 'self' {hashes}; style-src 'self' 'unsafe-inline'; "
                f"img-src 'self' data: blob: {teselas}; connect-src 'self' {teselas}; "
                "worker-src 'self' blob:; child-src blob:; font-src 'self'; object-src 'none'; "
                "base-uri 'self'; form-action 'self'; frame-ancestors 'self'"))
    except OSError:
        pass
    return _csp["valor"]


# --- sesión del panel --------------------------------------------------------
# Antes el panel guardaba la CLAVE en el navegador (sessionStorage) y la mandaba
# en cada petición: cualquier script que corriera en la página podía leerla.
# Ahora la clave se manda una vez y el servidor devuelve una cookie HttpOnly
# (JavaScript no la ve) firmada con HMAC. Sin estado: vale en las dos Pis (las
# dos tienen la misma clave) y cambiar la clave invalida todas las sesiones.
SESION_HORAS = 12


def _firma(exp):
    clave = hashlib.sha256(b"sesion-panel\0" + ADMIN_HASH.encode()).digest()
    return hmac.new(clave, str(exp).encode(), hashlib.sha256).hexdigest()


def nueva_sesion():
    exp = int(time.time()) + SESION_HORAS * 3600
    return f"{exp}.{_firma(exp)}"


def sesion_valida(cabecera_cookie):
    if not ADMIN_HASH or not cabecera_cookie:
        return False
    for trozo in cabecera_cookie.split(";"):
        nombre, _, valor = trozo.strip().partition("=")
        if nombre == "adm":
            exp, _, firma = valor.partition(".")
            if exp.isascii() and exp.isdigit() and len(exp) < 15 and int(exp) > time.time() \
                    and compare_digest(firma.encode(), _firma(int(exp)).encode()):
                return True
    return False


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

    if resumen.get("totalTime") is not None:
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
        if cffi_requests is None:
            raise RuntimeError("falta curl_cffi en el servidor (pip install curl_cffi) para leer iGPSPORT")
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
        "User-Agent": "Mozilla/5.0 (compatible; SiguemeCC/1.3)"
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
    """Último punto de la ruta; se vuelve a leer si cambia route.geojson."""
    mtime = os.path.getmtime(os.path.join(ROOT, "route.geojson"))
    if not _meta or _meta[0] != mtime:
        _meta[:] = [mtime, puntos_de_la_ruta()[-1]]
    return _meta[1]


def km_entre(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def ha_llegado(t, se_alejo=False):
    """A menos de 200 m del punto de meta, y o bien con los km mínimos hechos
    (carrera.json, km_minimos_meta), o
    bien habiéndose alejado antes más de 5 km de meta. La ruta solo pasa tan
    cerca de meta en la salida (km 0-0,2) y en los últimos 200 m.
    ⚠️ Solo con los km mínimos, un seguimiento nuevo empezado a mitad de carrera
    (que cuenta desde 0) no llegaba nunca a meta: pasó el 26/09."""
    if t.get("lat") is None or t.get("lon") is None:
        return False
    if (t.get("dist_km") or 0) < km_minimos_meta() and not se_alejo:
        return False
    try:
        return km_entre((t["lat"], t["lon"]), punto_de_meta()) < 0.2
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False                      # sin ruta no hay meta, pero la posición se publica


def alejado_de_meta(lat, lon):
    try:
        return lat is not None and lon is not None and km_entre((lat, lon), punto_de_meta()) > 5
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False


# --- GPS del móvil (Traccar Client) --------------------------------------
# En la carrera del 26/09/2026 la posición de iGPSPORT iba a saltos con los
# datos del móvil y, a las 14:51 (km 46), dejó de llegar para siempre: su
# directo depende de ciclocomputador -> Bluetooth -> app -> servidor de iGPSPORT, y
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


def hace_segundos(iso):
    try:
        return time.time() - datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return float("inf")


# Dos envíos a la vez (Traccar reintentando y el reloj, o el poller) leían el
# mismo estado y uno pisaba la distancia del otro
gps_lock = threading.Lock()
rechazo = {"t": 0.0}


def gps_reciente(live):
    t = live.get("gps_t")
    return bool(t) and time.time() - t < GPS_VIGENTE


def _segundos(valor):
    """Hora del punto: segundos o milisegundos Unix, o ISO 8601."""
    if valor in (None, ""):
        return time.time()
    try:
        n = float(valor)
        if math.isfinite(n):
            return n / 1000 if n > 1e11 else n
        return time.time()
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


def _fraccion(valor):
    """Traccar 9 (JSON) da la batería de 0 a 1; la URL, en %: "batt=1" es 1 %."""
    n = _numero(valor)
    return n * 100 if n is not None and n <= 1 else n


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
                for k in ("coords", "battery", "extras"):
                    if not isinstance(loc.get(k), dict):
                        loc[k] = {}
                c = loc["coords"]
                v = _numero(c.get("speed"))
                crudos.append({"lat": c.get("latitude"), "lon": c.get("longitude"),
                               "t": _segundos(loc.get("timestamp")),
                               "kmh": v * 3.6 if v is not None and v >= 0 else None,
                               "precision": c.get("accuracy"),
                               "bateria": _fraccion((loc.get("battery") or {}).get("level")),
                               # el reloj (miniapp de Amazfit) manda el pulso aquí
                               "hr": (loc.get("extras") or {}).get("hr"),
                               "origen": (loc.get("extras") or {}).get("origen")})
        elif j is None:
            try:
                q.update({k: v[0] for k, v in parse_qs(cuerpo.decode("utf-8")).items()})
            except UnicodeDecodeError:
                pass
    if "lat" in q and "lon" in q:
        v = _numero(q.get("speed"))
        crudos.append({"lat": q["lat"], "lon": q["lon"], "t": _segundos(q.get("timestamp")),
                       "kmh": v * 1.852 if v is not None and v >= 0 else None,
                       "precision": q.get("accuracy"), "bateria": q.get("batt"), "hr": q.get("hr")})
    ident = ident or q.get("id") or q.get("deviceid")

    puntos = []
    ahora = time.time()
    for p in crudos:
        # ⚠️ Un aparato con la hora adelantada dejaba gps_t en el futuro y
        # todos los puntos buenos siguientes se descartaban por "viejos": la
        # foto se quedaba clavada hasta que el reloj real alcanzaba esa hora.
        p["t"] = min(p["t"], ahora)
        if p["t"] < ahora - 86400:
            continue                     # de hace más de un día: no es de esta carrera
        hr = _numero(p.get("hr"))
        hr = hr if hr is not None and 30 <= hr <= 240 else None
        bateria = _numero(p["bateria"])
        lat, lon = _numero(p["lat"]), _numero(p["lon"])
        precision = _numero(p["precision"])
        valida = not (lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180)
                      or (lat == 0 and lon == 0)
                      or (precision is not None and precision > PRECISION_MAXIMA))
        if not valida:
            # sin posición buena pero con pulso (el reloj aún buscando GPS):
            # vale para el pulso
            if hr is None:
                continue
            lat = lon = None
        puntos.append({"lat": lat, "lon": lon, "t": p["t"], "kmh": p["kmh"] if valida else None,
                       "precision": precision, "bateria": bateria, "hr": hr,
                       "origen": str(p.get("origen") or "movil")[:20]})
    return ident, puntos


def recibir_gps(puntos):
    puntos.sort(key=lambda p: p["t"])
    for p in puntos:
        apuntar_historial("gps", lat=p["lat"], lon=p["lon"],
                          hora=datetime.fromtimestamp(p["t"], timezone.utc).isoformat(),
                          kmh=p["kmh"], precision=p["precision"], bateria=p["bateria"], hr=p["hr"])
    live = read_live()
    extra = {}
    # pulso del reloj: el más reciente, y la media de todo lo recibido
    nuevos_hr = [p for p in puntos if p["hr"] is not None and p["t"] > (live.get("hr_t") or 0)]
    if nuevos_hr:
        suma = (live.get("hr_suma") or 0) + sum(p["hr"] for p in nuevos_hr)
        n = (live.get("hr_n") or 0) + len(nuevos_hr)
        u = nuevos_hr[-1]
        extra.update(hr=round(u["hr"]), hr_t=u["t"], hr_suma=suma, hr_n=n, hr_avg=round(suma / n),
                     hr_at=datetime.fromtimestamp(u["t"], timezone.utc).isoformat())
    con_bateria = [p for p in puntos if p["bateria"] is not None]
    if con_bateria:
        extra["bateria_movil"] = round(con_bateria[-1]["bateria"])
    puntos = [p for p in puntos if p["lat"] is not None]
    # Móvil (Traccar) y reloj (Amazfit) a la vez: la posición la da solo UNO,
    # el que ya estaba mandando. Alternando entre dos GPS la foto temblaba y
    # la distancia sumaba el zigzag entre los dos. Si el que manda se calla
    # 2 min, toma el relevo el otro. El pulso vale de cualquiera.
    manda = live.get("gps_origen") if gps_reciente(live) else None
    if puntos:
        manda = manda or puntos[-1]["origen"]
        puntos = [p for p in puntos if p["origen"] == manda]
    # los que llegan de la cola (sin cobertura) pueden ser más viejos que lo
    # que ya tenemos: al historial sí, a la posición en directo no
    if not puntos or puntos[-1]["t"] <= (live.get("gps_t") or 0):
        if extra:
            merge_live(extra)
        return
    ultimo = puntos[-1]
    # Distancia recorrida con el GPS del móvil: sin enlace de iGPSPORT no
    # había ninguna, y la llegada a meta la necesita (km mínimos). Los
    # saltos imposibles (más de 90 km/h entre dos puntos) no suman.
    dist = live.get("gps_dist_km") or 0.0
    previo = live.get("gps_ult")
    velocidad = None
    for p in puntos:
        if previo and p["t"] > previo[2]:
            tramo = km_entre((previo[0], previo[1]), (p["lat"], p["lon"]))
            v = tramo / max(1.0, p["t"] - previo[2]) * 3600
            if v < 90:
                dist += tramo
                # el reloj no manda velocidad: se saca de los dos últimos
                # puntos (si no, se quedaba la última de iGPSPORT, de horas antes)
                velocidad = v if p["t"] - previo[2] <= 120 else None
            elif p["t"] - previo[2] < 60:
                # salto imposible: se ignora el punto y la referencia sigue
                # siendo el último bueno (si el "salto" dura más de 1 min, es
                # que la referencia era la mala y se cambia)
                continue
        if not previo or p["t"] > previo[2]:
            previo = [p["lat"], p["lon"], p["t"]]
        p["_dist"] = dist                 # km hechos en este punto (meta dentro del lote)
    hora = datetime.fromtimestamp(ultimo["t"], timezone.utc).isoformat()
    patch = {"lat": ultimo["lat"], "lon": ultimo["lon"], "gps_t": ultimo["t"],
             "gps_at": hora, "data_at": hora, "fuente_posicion": "movil", "gps_origen": manda,
             "gps_dist_km": round(dist, 3), "gps_ult": previo}
    distancia = max(live.get("dist_km") or 0, dist)
    try:
        salida_t = datetime.fromisoformat(live["started_at"]).timestamp() if live.get("started_at") else None
    except ValueError:
        salida_t = None
    # ⚠️ antes de la salida no cuenta nada: con EMPEZAR a las 09:45 y la salida
    # junto a la meta, llegar a la salida «desde lejos» se daba por llegada
    # ⚠️ y solo los NUEVOS: si la app reenvía un lote que ya había llegado (se
    # perdió la respuesta), los puntos de la salida, junto a la meta, daban la
    # carrera por terminada con tiempo 0
    previo_t = live.get("gps_t") or 0
    en_carrera = [q for q in puntos if salida_t is not None and q["t"] >= salida_t and q["t"] > previo_t
                  and q.get("lat") is not None]
    # punto a punto y en orden: «se alejó de meta» solo cuenta lo que pasó ANTES
    # de cada punto (mirando el lote entero, el de la salida ya era «llegada»)
    lejos = bool(live.get("lejos_de_meta"))
    base = live.get("dist_km") or 0
    for q in en_carrera:
        if not live.get("finished_at") and "finished_at" not in patch and                 ha_llegado({"lat": q["lat"], "lon": q["lon"], "dist_km": max(base, q.get("_dist", dist))}, lejos):
            patch["finished_at"] = datetime.fromtimestamp(q["t"], timezone.utc).isoformat()
        lejos = lejos or alejado_de_meta(q["lat"], q["lon"])
    if lejos and not live.get("lejos_de_meta"):
        patch["lejos_de_meta"] = True
    if ultimo["kmh"] is not None:
        patch["speed_kmh"] = round(ultimo["kmh"], 1)
    else:
        patch["speed_kmh"] = round(velocidad, 1) if velocidad is not None else None
    patch.update(extra)
    merge_live(patch)


def huella(t):
    """Lo que cambia cuando de verdad llega un dato nuevo del ciclocomputador."""
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
            if stop_event.is_set():
                break                     # lo pararon mientras preguntaba: no escribir datos viejos
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
                # pulso: si llega del reloj, manda el reloj (si no, la cifra
                # y la media saltaban entre los dos cada pocos segundos)
                if hace_segundos(read_live().get("hr_at")) < GPS_VIGENTE:
                    patch.pop("hr", None)
                    patch.pop("hr_avg", None)
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
# escribiría el ciclocomputador. Sirve para ver moverse la foto, el trazado azul, el
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
        recorrido = (carrera().get("distancia_km") or 100) * (i / (total - 1))
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


poller_lock = threading.RLock()     # el panel y el vigilante no arrancan dos a la vez


def start_poller(url):
    with poller_lock:
        stop_previous_poller()
        stop_event = threading.Event()
        thread = threading.Thread(target=poll_loop, args=(url, stop_event), daemon=True)
        poller["thread"] = thread
        poller["stop"] = stop_event
        poller["url"] = url
        thread.start()


def stop_previous_poller():
    with poller_lock:
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
    server_version = "SiguemeCC"   # antes "SimpleHTTP/0.6 Python/3.x"
    sys_version = ""
    timeout = 20

    def send_error(self, code, message=None, explain=None):
        """Errores en español y con la cara de la web (la página por defecto,
        en inglés, delataba http.server)."""
        textos = {400: ("Petición no válida", "Algo en la dirección no está bien."),
                  404: ("No encontrado", "Esta página no existe."),
                  405: ("No permitido", "Esta acción no está permitida."),
                  500: ("Error del servidor", "Algo ha fallado. Prueba otra vez en un momento.")}
        titulo, texto = textos.get(code, ("Error", "No se ha podido atender la petición."))
        cuerpo = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width,initial-scale=1">'
                  f'<title>{code} · {titulo} · Sígueme CC</title><style>body{{background:#0b1210;color:#eef2ee;'
                  'font-family:system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;'
                  'text-align:center}h1{font-size:3rem;margin:0}a{color:#7fd46a}</style></head><body><main>'
                  f'<h1>{code}</h1><p>{texto}</p><p><a href="/">Volver a Sígueme CC</a></p></main></body></html>').encode()
        self.send_response(code, titulo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        if getattr(self, "command", None) != "HEAD":
            self.wfile.write(cuerpo)

    def ip_cliente(self):
        """IP real: detrás del túnel de Cloudflare todas llegan desde una IP
        privada; ahí (y solo ahí) se cree a CF-Connecting-IP. Así el freno a la
        fuerza bruta es por persona y un atacante no bloquea al dueño."""
        directa = self.client_address[0]
        try:
            privada = ipaddress.ip_address(directa).is_private
            real = self.headers.get("CF-Connecting-IP", "").strip()
            if privada and real:
                ipaddress.ip_address(real)
                return real
        except ValueError:
            pass
        return directa

    def mismo_origen(self):
        """Protección CSRF: un navegador siempre manda Origin (o Referer) en un
        POST; si viene de otra web, fuera."""
        origen = self.headers.get("Origin") or self.headers.get("Referer") or ""
        if not origen:
            return None                       # sin cabecera: no es un navegador
        return urlparse(origen).netloc == self.headers.get("Host", "")
    # una conexión que no manda nada no se queda un hilo para siempre

    def _ruta(self):
        """Ruta pedida, decodificada y normalizada ("/./admin.html", "//admin.html"
        o "%61dmin.html" son "/admin.html": si no, se saltaban las cabeceras)."""
        crudo = unquote(self.path.split("?")[0].split("#")[0])
        return "/" + posixpath.normpath(crudo).lstrip("/") if crudo.strip("/") else "/"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _ruta_publica(self):
        if self.path.split("?")[0].endswith("/") and self.path.split("?")[0] != "/":
            return False                 # nada de listados de directorio
        ruta = self._ruta()
        if ruta in ("/", "/index.html"):
            return True
        # nada de carpetas o ficheros ocultos (.git, .vscode, .claude…)
        if any(trozo.startswith(".") for trozo in ruta.split("/")):
            return False
        return os.path.splitext(ruta)[1].lower() in EXTENSIONES_PUBLICAS

    def _gps(self, cuerpo=b""):
        _, _, query = self.path.partition("?")
        ident, puntos = puntos_traccar(query, cuerpo)
        clave = clave_gps()
        if not clave or not ident or not compare_digest(str(ident).encode(), clave.encode()):
            # El panel avisa: con el identificador mal copiado, Traccar o el
            # reloj mandaban y la web no se movía, sin pista de por qué. Solo
            # la hora (live.json es público) y como mucho una vez por minuto.
            # (solo si trae identificador: un escáner cualquiera sin él no avisa)
            if puntos and ident and time.time() - rechazo["t"] > 60:
                rechazo["t"] = time.time()
                merge_live({"gps_rechazado_at": datetime.now(timezone.utc).isoformat()})
            self._send_json(403, {"error": "identificador incorrecto"})
            return
        if puntos:
            try:
                with gps_lock:
                    recibir_gps(puntos)
            except Exception as exc:
                # contestar igual: si no, el móvil reintenta ese lote para
                # siempre. Los puntos ya quedaron en el historial.
                print(f"[gps] error procesando {len(puntos)} puntos: {exc!r}", flush=True)
        # Traccar solo borra los puntos de su cola si le contestamos 200
        self._send_json(200, {"ok": True, "puntos": len(puntos)})

    def do_GET(self):
        if self.path.startswith("/api/gps"):
            self._gps()
            return
        crudo = self.path.split("?")[0]
        ruta = self._ruta()
        if ruta == "/carreras":
            return self._indice_carreras()
        m = SLUG_RE.match(ruta)
        if m and os.path.isdir(os.path.join(ARCHIVO_DIR, m.group(1))):
            if not m.group(2) and not crudo.endswith("/"):
                return self._redirigir("/" + m.group(1) + "/", 301)   # sin la barra, los enlaces relativos fallan
            return self._servir_archivada(m.group(1), (m.group(2) or "/").lstrip("/"))
        if ruta in ("/", "/index.html") and not hay_carrera_en_marcha() \
                and not os.path.exists(os.path.join(ROOT, "resultado.json")):
            # sin carrera en marcha: la portada lleva al último resultado (302,
            # no 301: cuando empiece la siguiente carrera, la portada será ella)
            archivadas = carreras_archivadas()
            if archivadas:
                return self._redirigir("/" + archivadas[0][0] + "/", 302)
        if not self._ruta_publica():
            self.send_error(404, "Not Found")
            return
        ruta = self._ruta()
        if ruta == "/live.json":
            self._send_json(200, live_publico(), cache="public, max-age=3, s-maxage=3")
            return
        if ruta == "/resultado.json" and not os.path.exists(os.path.join(ROOT, "resultado.json")):
            # sin resultado todavía: «null», no un 404 (que salía en rojo en la consola de cada visitante)
            self._send_json(200, None, cache="public, max-age=30, s-maxage=30")
            return
        if ruta in ("/", "/index.html") and os.path.exists(os.path.join(ROOT, "resultado.json")):
            self._index_resultado()
            return
        if ruta in ("/", "/index.html"):
            self._index_vivo()
            return
        super().do_GET()

    def _index_vivo(self):
        """index.html con og:url y og:image del dominio de quien la sirve: la
        vista previa de WhatsApp sale con TU dominio, no con uno escrito a mano."""
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        host = self.headers.get("Host", "")
        if re.fullmatch(r"[A-Za-z0-9.-]+(:\d{1,5})?", host):
            html = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + f"https://{host}/", html, count=1)
            html = re.sub(r'(<meta property="og:image" content=")[^"]*', lambda m: m.group(1) + f"https://{host}/og.jpg", html, count=1)
        cuerpo = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def _redirigir(self, destino, codigo):
        self.send_response(codigo)
        self.send_header("Location", destino)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _servir_fichero(self, ruta_fichero):
        with open(ruta_fichero, "rb") as f:
            cuerpo = f.read()
        tipo = mimetypes.guess_type(ruta_fichero)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def _servir_archivada(self, slug, nombre):
        """/<slug>/X: X de la carpeta de la carrera si lo tiene (sus datos);
        si no, el de la web (app.js, estilos, librería)."""
        if nombre in ("", "index.html"):
            return self._index_resultado(os.path.join(ARCHIVO_DIR, slug), slug)
        if ".." in nombre or nombre.startswith(".") or os.path.splitext(nombre)[1].lower() not in EXTENSIONES_PUBLICAS:
            return self.send_error(404)
        propio = os.path.join(ARCHIVO_DIR, slug, nombre)
        if "/" not in nombre and os.path.isfile(propio):
            return self._servir_fichero(propio)
        if nombre == "live.json":                    # carrera archivada: ya terminó
            return self._send_json(200, {"status_label": "Finalizada"}, cache="public, max-age=300")
        if nombre == "admin.html" or nombre in ("resultado.json", "carrera.json"):
            return self.send_error(404)
        web = os.path.join(ROOT, nombre)
        if os.path.isfile(web):
            return self._servir_fichero(web)
        return self.send_error(404)

    def _indice_carreras(self):
        esc = lambda t: str(t).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        filas = []
        for slug, c, r in carreras_archivadas():
            h, m = divmod(int(r.get("tiempo_oficial_s") or 0) // 60, 60)
            f = c.get("fecha", "")
            fecha = "/".join(reversed(f.split("-"))) if re.match(r"^\d{4}-\d{2}-\d{2}$", f) else f
            datos = " · ".join(x for x in (
                fecha, c.get("lugar", ""), f"{h}h {m:02d}m" if r.get("tiempo_oficial_s") else "",
                f"{str(r.get('distancia_km', '')).replace('.', ',')} km" if r.get("distancia_km") else "",
                f"{r['desnivel_m']} m+" if r.get("desnivel_m") else "") if x)
            filas.append(f'<li><a href="/{esc(slug)}/"><b>{esc(c.get("nombre") or slug)}</b>'
                         f'<span>{esc(datos)}</span></a></li>')
        en_marcha = '<p class="indice-vivo"><a href="/">● Carrera en directo ahora</a></p>' if hay_carrera_en_marcha() else ""
        html = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>Carreras · Sígueme CC</title><meta name="description" content="Todas las carreras seguidas con Sígueme CC">'
                '<link rel="icon" type="image/png" href="/favicon.png?v=3"><link rel="stylesheet" href="/style.css?v=indice">'
                '</head><body class="indice"><header class="topbar"><div class="marca"><h1>Sígueme <span>CC</span></h1>'
                '<p class="marca-sub">Todas las carreras</p></div></header><main class="indice-main">'
                f'{en_marcha}<ul class="indice-lista">{"".join(filas) or "<li>Todavía no hay carreras archivadas.</li>"}</ul>'
                '</main></body></html>').encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _index_resultado(self, base=ROOT, slug=None):
        """Con resultado.json, el título, la descripción y la vista previa del
        enlace dicen "Resultado" (los buscadores y WhatsApp no ejecutan JS).
        En una carrera archivada, además, la web no sondea (meta archivo)."""
        try:
            with open(os.path.join(base, "resultado.json"), encoding="utf-8") as f:
                r = json.load(f)
            try:
                with open(os.path.join(base, "carrera.json"), encoding="utf-8") as f:
                    c = json.load(f)
            except (OSError, ValueError):
                c = {}
            nombre = c.get("nombre") or r.get("carrera") or "la carrera"
            h, m = divmod(int(r.get("tiempo_oficial_s") or 0) // 60, 60)
            desc = f"{nombre}: terminada en {h}h {m:02d}m · {str(r.get('distancia_km', '')).replace('.', ',')} km"
            with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
                html = f.read()
            titulo = f"Resultado · {nombre}"
            esc = lambda t: t.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
            html = re.sub(r"<title>.*?</title>", lambda _: f"<title>{esc(titulo)}</title>", html, count=1)
            html = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda x: x.group(1) + esc(titulo), html, count=1)
            html = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda x: x.group(1) + esc(desc), html, count=1)
            html = re.sub(r'(<meta name="description" content=")[^"]*', lambda x: x.group(1) + esc(desc), html, count=1)
            if slug:
                url = f"https://{self.headers.get('Host', '')}/{slug}/"
                html = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda x: x.group(1) + esc(url), html, count=1)
                html = html.replace("<head>", '<head>\n<meta name="archivo" content="1">', 1)
            cuerpo = html.encode("utf-8")
        except (OSError, ValueError):
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_HEAD(self):
        if not self._ruta_publica():
            self.send_error(404, "Not Found")
            return
        super().do_HEAD()

    def end_headers(self):
        # El navegador se quedaba con el css/js viejo y el usuario veía la web
        # rota después de desplegar. Con no-cache revalida siempre: para
        # ficheros de 16 KB no cuesta nada y evita enseñar una versión antigua.
        ruta = self._ruta()
        if ruta.startswith("/lib/"):
            # la librería lleva la versión en el nombre y no cambia nunca: sin
            # esto, Cloudflare preguntaba a la Pi en cada visita (REVALIDATED)
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        elif ruta == "/admin.html":
            self.send_header("Cache-Control", "no-store")
        elif ruta.endswith((".html", ".css", ".js", ".json", "/")):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        # buenas prácticas: que nadie meta la web en un iframe ajeno, que el
        # navegador no "adivine" tipos, y no regalar la URL al salir
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        self.send_header("Strict-Transport-Security", "max-age=31536000")
        if ruta == "/admin.html":
            # el panel solo habla con su propio servidor y no sale en Google
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                             "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("X-Robots-Tag", "noindex, nofollow")
        elif csp_web():
            self.send_header("Content-Security-Policy", csp_web())
        super().end_headers()

    def _send_json(self, status, payload, cookie=None, cache="no-store"):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", cache)
        if cookie is not None:
            # Secure solo si llega por https (Cloudflare); por la red de casa
            # (http) el navegador no guardaría una cookie Secure
            https = "https" in (self.headers.get("X-Forwarded-Proto", "") + self.headers.get("Cf-Visitor", ""))
            self.send_header("Set-Cookie", f"adm={cookie}; Path=/api; HttpOnly; SameSite=Strict"
                             + ("; Secure" if https else "")
                             + (f"; Max-Age={SESION_HORAS * 3600}" if cookie else "; Max-Age=0"))
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
        local = datetime.now(zona_carrera()).replace(
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
            llegada = datetime.fromisoformat(self.hora_a_iso(escrita))
            if llegada > datetime.now(timezone.utc) + timedelta(minutes=5):
                llegada -= timedelta(days=1)          # escrita pasada la medianoche
            return llegada.isoformat()
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

    def _sesion_panel(self):
        """Peticiones del panel que no son JSON (subir el GPX): solo con sesión
        y desde esta misma web."""
        return self.mismo_origen() is True and sesion_valida(self.headers.get("Cookie"))

    def _en_carrera(self):
        live = read_live()
        return bool(live.get("started_at") and not live.get("finished_at"))

    def _subir_gpx(self):
        if not self._sesion_panel():
            self._send_json(403, {"error": "sesión caducada"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
        except ValueError:
            largo = -1
        if not 0 < largo <= MAX_GPX:
            self._send_json(413, {"error": "el GPX tiene que pesar menos de 20 MB"})
            return
        cuerpo = self.rfile.read(largo)
        if self._en_carrera():
            self._send_json(409, {"error": "hay una carrera en marcha: termínala antes de cambiar la ruta"})
            return
        consulta = parse_qs(urlparse(self.path).query)
        try:
            distancia = _numero_en((consulta.get("distancia") or [""])[0], 0.1, 2000)
        except ValueError:
            self._send_json(400, {"error": "distancia oficial no válida"})
            return
        c = carrera_editable()
        if c is None:
            self._send_json(409, {"error": "carrera.json no se puede leer: arréglalo antes de subir la ruta"})
            return
        try:
            ruta, elev, resumen = herramienta("preparar_ruta").preparar(cuerpo, c.get("nombre") or "Ruta", distancia)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        escribir_json("route.geojson", ruta)
        escribir_json("elevation.json", elev)
        # la distancia y el D+ de la carrera pasan a ser los de esta ruta
        c["distancia_km"] = resumen["distancia_km"]
        if resumen["con_elevacion"]:
            c["desnivel_m"] = resumen["desnivel_m"]
        else:
            c.pop("desnivel_m", None)          # el de la carrera anterior no vale
        # ⚠️ km mínimos de la carrera anterior (80 en una de 21 km): la llegada
        # no se detectaría nunca. Fuera, y vale el 80 % de la ruta nueva.
        if (c.get("km_minimos_meta") or 0) >= resumen["distancia_km"]:
            c.pop("km_minimos_meta", None)
        escribir_json("carrera.json", c)
        try:
            plan = generar_plan()
        except Exception as exc:
            print(f"[gpx] no se pudo rehacer el plan: {exc!r}", flush=True)
            plan = None
        apuntar_historial("gpx", km=resumen["distancia_km"], puntos=resumen["puntos_gpx"])
        self._send_json(200, {"ok": True, "resumen": resumen, "carrera": c, "plan": plan, "preparacion": preparacion()})

    def _subida(self, maximo, que):
        """Cuerpo de una subida del panel (con sesión), o None si ya se contestó."""
        if not self._sesion_panel():
            self._send_json(403, {"error": "sesión caducada"})
            return None
        try:
            largo = int(self.headers.get("Content-Length", 0))
        except ValueError:
            largo = -1
        if not 0 < largo <= maximo:
            self._send_json(413, {"error": f"{que} tiene que pesar menos de {maximo // 1_000_000} MB"})
            return None
        return self.rfile.read(largo)

    def _subir_fit(self):
        """El FIT del reloj o del ciclocomputador → resultado.json (modo resultado)."""
        cuerpo = self._subida(40_000_000, "el FIT")
        if cuerpo is None:
            return
        if self._en_carrera():
            self._send_json(409, {"error": "la carrera sigue en marcha: pulsa antes «Finalizar seguimiento»"})
            return
        try:
            res = herramienta("generar_resultado").generar(cuerpo, pathlib.Path(ROOT))
        except ImportError as exc:
            self._send_json(500, {"error": "falta fitdecode en el servidor (pip install fitdecode)" if "fitdecode" in str(exc)
                                  else f"falta una herramienta en el servidor ({exc})"})
            return
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception as exc:
            print(f"[fit] {exc!r}", flush=True)
            self._send_json(400, {"error": "no se pudo sacar el resultado de ese FIT (¿la ruta subida es la de esta carrera?)"})
            return
        escribir_json("resultado.json", res)
        apuntar_historial("resultado", tiempo_s=res["tiempo_oficial_s"])
        self._send_json(200, {"ok": True, "resultado": {k: res[k] for k in
                              ("tiempo_oficial_s", "distancia_km", "llegada", "velocidad_media_mov")},
                              "pasos": len(res["pasos"]), "preparacion": preparacion()})

    def _subir_avatar(self):
        """Foto del corredor: el panel la recorta a 256×256 y la manda en PNG."""
        cuerpo = self._subida(2_000_000, "la foto")
        if cuerpo is None:
            return
        if not cuerpo.startswith(b"\x89PNG\r\n\x1a\n"):
            self._send_json(400, {"error": "la foto tiene que llegar en PNG"})
            return
        tmp = os.path.join(ROOT, ".rider.png.tmp")
        with open(tmp, "wb") as f:
            f.write(cuerpo)
        os.replace(tmp, os.path.join(ROOT, "rider.png"))
        c = carrera_editable()
        if c is None:
            self._send_json(200, {"ok": True, "carrera": carrera()})
            return
        c["avatar_v"] = int(time.time())        # la web pide rider.png?v=… y no enseña la vieja
        escribir_json("carrera.json", c)
        self._send_json(200, {"ok": True, "carrera": c})

    def _preparar(self, accion, data):
        if accion in ("guardar_carrera", "guardar_avituallamientos") and self._en_carrera():
            self._send_json(409, {"error": "hay una carrera en marcha: termínala antes de cambiar sus datos"})
            return
        if accion == "guardar_carrera":
            c, error = limpiar_carrera(data.get("carrera") if isinstance(data.get("carrera"), dict) else {})
            if error:
                self._send_json(400, {"error": error})
                return
            antes = carrera()
            escribir_json("carrera.json", c)
            # el D+ oficial escala el "quedan +X m" de los avisos
            plan = generar_plan() if c.get("desnivel_m") != antes.get("desnivel_m") else plan_avisos()
            self._send_json(200, {"ok": True, "carrera": c, "plan": plan, "preparacion": preparacion()})
            return
        if accion == "guardar_avituallamientos":
            lista, error = limpiar_avituallamientos(data.get("avituallamientos"))
            if error:
                self._send_json(400, {"error": error})
                return
            escribir_json("aid_stations.json", lista)
            self._send_json(200, {"ok": True, "avituallamientos": lista, "plan": generar_plan(), "preparacion": preparacion()})
            return
        if accion == "generar_avisos":
            try:
                antes = _numero_en(data.get("antes_m"), 50, 2000)
                cada = _numero_en(data.get("cada_km"), 1, 100)
            except (TypeError, ValueError):
                self._send_json(400, {"error": "ajustes no válidos: aviso entre 50 y 2000 m antes, resumen cada 1–100 km"})
                return
            plan = generar_plan(antes / 1000 if antes else 0.3, cada or None, forzar=True)
            if plan is None:
                self._send_json(400, {"error": "falta la ruta con perfil: sube antes el GPX"})
                return
            self._send_json(200, {"ok": True, "plan": plan, "preparacion": preparacion()})
            return
        # guardar_avisos: textos cambiados a mano; vacío = ese aviso se quita
        plan = plan_avisos()
        cambios = data.get("avisos")
        if not plan or not isinstance(cambios, list) or len(cambios) > 1000:
            self._send_json(400, {"error": "no hay plan de avisos que cambiar"})
            return
        textos = {}
        for x in cambios:
            if isinstance(x, dict) and isinstance(x.get("id"), int):
                textos[x["id"]] = _texto(x.get("texto"), 120)
        quitados = plan.get("quitados", [])
        nuevos = []
        for a in plan["avisos"]:
            t = textos.get(a["id"], a["texto"])
            if not t:
                quitados.append({"tipo": a["tipo"], "km": a["km"]})
            elif t != a["texto"]:
                nuevos.append(dict(a, texto=t, editado=True))
            else:
                nuevos.append(a)
        plan["avisos"], plan["quitados"] = nuevos, quitados
        escribir_json("avisos.json", plan)
        self._send_json(200, {"ok": True, "plan": plan, "preparacion": preparacion()})

    def _empezar(self, hora, origen="panel"):
        """Carrera en marcha: el crono cuenta desde la hora OFICIAL (si se empieza
        a las 09:45 para salir a las 10:00, la web dice «en la salida» hasta las
        10:00 y luego cuenta desde las 10:00, no desde las 09:45)."""
        inicio = self.hora_a_iso(hora) if hora else None
        parar_simulacion()
        stop_previous_poller()
        apuntar_historial("empezar", hora_salida=hora, origen=origen)
        return merge_live({
            "status_label": "En carrera", "livetrack_url": None, "extract_status": None,
            "started_at": inicio or datetime.now(timezone.utc).isoformat(),
            "hora_salida": hora or None, "finished_at": None, "elapsed": None,
            "speed_kmh": None, "speed_kmh_avg": None, "hr": None, "hr_avg": None,
            "cadence": None, "cadence_avg": None, "dist_km": None, "data_at": None,
            "gps_dist_km": 0, "gps_ult": None, "igpsport_at": None, "igpsport_aviso": None,
            "gps_t": None, "gps_at": None, "lejos_de_meta": None, "hr_t": None, "hr_at": None, "hr_suma": None, "hr_n": None,
            "ruta_km": None, "aviso_id": None, "aviso_t": None, "aviso_texto": None,
            "gps_origen": None, "gps_rechazado_at": None,
        })

    def _empezar_desde_app(self):
        """EMPEZAR en la app = carrera en marcha en la web, sin abrir el panel.
        Solo el día de la carrera (otro día es una prueba: no toca la web) y una
        vez: si ya está en marcha hoy, no se reinicia."""
        c = carrera()
        zona = zona_carrera()
        hoy = datetime.now(zona).date().isoformat()
        live = read_live()
        try:
            empezada = datetime.fromisoformat(live["started_at"]) if live.get("started_at") else None
        except ValueError:
            empezada = None
        reciente = empezada is not None and datetime.now(timezone.utc) - empezada < timedelta(hours=20)
        if reciente and not live.get("finished_at"):
            return "ya_estaba", "La carrera ya estaba en marcha en la web"
        if reciente:
            return "terminada", "La carrera de hoy ya está terminada en la web"
        if c.get("fecha") and c["fecha"] != hoy:
            return "otro_dia", f"La carrera es el {c['fecha']}: hoy es solo una prueba (la web no cambia)"
        self._empezar(c.get("hora_salida") or "", origen="app")
        return "empezada", f"Carrera en marcha en la web (salida a las {c.get('hora_salida') or 'ya'})"

    def _plan_app(self):
        """La app del móvil baja aquí el plan, con el mismo identificador que
        usa para mandar la posición (no hace falta la clave del panel)."""
        ip = "app:" + self.ip_cliente()
        if segundos_de_castigo(ip) > 5:
            self._send_json(429, {"error": "demasiados intentos: espera unos minutos"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo = json.loads(self.rfile.read(largo) if 0 < largo <= 4096 else b"{}")
            ident = str(cuerpo.get("device_id") or "")
        except (ValueError, AttributeError):
            cuerpo, ident = {}, ""
        clave = clave_gps()
        if not clave or not ident or not compare_digest(ident.encode(), clave.encode()):
            fallo_de(ip)
            self._send_json(403, {"error": "identificador incorrecto"})
            return
        acierto_de(ip)
        merge_live({"app_at": datetime.now(timezone.utc).isoformat()})
        respuesta = plan_para_la_app()
        if cuerpo.get("accion") == "empezar":
            respuesta["estado"], respuesta["mensaje"] = self._empezar_desde_app()
        self._send_json(200, respuesta)

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
        if self.path.startswith("/api/gpx") or self.path in ("/api/fit", "/api/avatar"):
            with datos_lock:
                {"/api/fit": self._subir_fit, "/api/avatar": self._subir_avatar}.get(self.path, self._subir_gpx)()
            return
        if self.path == "/api/plan":
            self._plan_app()
            return
        if self.path == "/api/logout":
            self._send_json(200, {"ok": True}, cookie="")
            return
        if self.path not in ("/api/live", "/api/login"):
            self._send_json(404, {"error": "not found"})
            return
        # el panel manda pocos KB (formularios, avisos); sin tope, cualquiera
        # podía hacer que el servidor leyera en memoria lo que quisiera
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if not 0 <= length <= 65_536:
            self._send_json(413, {"error": "petición demasiado grande"})
            return
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid json"})
            return

        ip = self.ip_cliente()
        # ⚠️ Detrás de Cloudflare TODAS las visitas llegan con la misma IP, así
        # que castigar por IP dejaba fuera también a Odegaard12 si alguien probaba
        # claves. Ahora el castigo NO rechaza de entrada: frena el intento un
        # segundo y luego compara. Al que acierta le da igual; al que adivina,
        # le limita el ritmo igual que antes.
        # ⚠️ Solo frena los intentos CON clave: antes frenaba también al panel
        # (con sesión), y detrás de Cloudflare todos comparten IP: un atacante
        # dejaba a Odegaard12 sin poder pulsar "Finalizar" en plena carrera.
        # Sin cola infinita: si ya hay uno esperando, 429.
        pide_clave = self.path == "/api/login" or (isinstance(data, dict) and "password" in data)
        espera = segundos_de_castigo(ip) if pide_clave else 0
        if espera > 5:
            # 10 fallos desde esta IP: bloqueada un rato (solo ella)
            self.send_response(429)
            self.send_header("Retry-After", str(espera))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "demasiados intentos: espera unos minutos"}')
            return
        if espera:
            if not castigo_lock.acquire(timeout=5):
                self._send_json(429, {"error": "demasiados intentos: espera un poco"})
                return
            try:
                time.sleep(1)
            finally:
                castigo_lock.release()

        if not (ADMIN_USER and ADMIN_HASH):
            print("[admin] sin ADMIN_USER/ADMIN_HASH: no se admite ningún acceso", flush=True)
            self._send_json(503, {"error": "servidor sin clave configurada"})
            return
        if not isinstance(data, dict):
            self._send_json(400, {"error": "invalid json"})
            return
        # login: usuario y clave una vez, a cambio de la cookie de sesión
        if self.path == "/api/login":
            if not credenciales_ok(data.get("usuario", ""), data.get("password", "")):
                fallo_de(ip)
                print(f"[admin] clave incorrecta (login) desde {ip}", flush=True)
                self._send_json(403, {"error": "clave incorrecta"})
                return
            acierto_de(ip)
            self._send_json(200, {"ok": True}, cookie=nueva_sesion())
            return
        # el resto: con sesión (panel) o con usuario y clave en el cuerpo (scripts)
        con_clave = "password" in data and credenciales_ok(data.get("usuario", ""), data.get("password", ""))
        # ⚠️ el fallo se cuenta ANTES de mirar el origen: sin Origin (curl) cada
        # clave falsa se iba por «origen no permitido» sin sumar al bloqueo
        if "password" in data and not con_clave:
            fallo_de(ip)
            print(f"[admin] clave incorrecta desde {ip}", flush=True)
            self._send_json(403, {"error": "sesión caducada o clave incorrecta"})
            return
        # con sesión de navegador, la petición tiene que venir de esta misma web
        if not con_clave and self.mismo_origen() is not True:
            self._send_json(403, {"error": "origen no permitido"})
            return
        if not con_clave and not sesion_valida(self.headers.get("Cookie")):
            self._send_json(403, {"error": "sesión caducada o clave incorrecta"})
            return
        if con_clave:
            acierto_de(ip)

        accion = data.get("action")

        if accion == "rotar_gps":
            # identificador nuevo (32 caracteres al azar) para cada carrera: el
            # viejo deja de valer al momento; hay que ponerlo en Traccar/reloj
            nueva = "odg-" + secrets.token_urlsafe(24)
            with open(GPS_CLAVE_PATH, "w", encoding="utf-8") as f:
                f.write(nueva + "\n")
            apuntar_historial("gps_rotado")
            self._send_json(200, {"ok": True, "gps_id": nueva, "live": read_live()})
            return

        if accion == "config":
            # lo que el panel necesita para los formularios de preparación
            self._send_json(200, {"ok": True, "carrera": carrera(), "avituallamientos": leer_json("aid_stations.json") or [],
                                  "plan": plan_avisos(), "preparacion": preparacion()})
            return

        if accion in ("guardar_carrera", "guardar_avituallamientos", "generar_avisos", "guardar_avisos"):
            with datos_lock:
                self._preparar(accion, data)
            return

        if accion == "gps_info":
            self._send_json(200, {"ok": True, "gps_id": clave_gps(), "live": read_live(), "preparacion": preparacion()})
            return

        if accion == "simular":
            if self._en_carrera() and read_live().get("status_label") != "SIMULACIÓN":
                self._send_json(409, {"error": "hay una carrera en marcha: no se puede simular encima"})
                return
            try:
                segundos = min(3600, max(10, int(data.get("segundos", 120))))
            except (TypeError, ValueError):
                self._send_json(400, {"error": "segundos no válidos"})
                return
            arrancar_simulacion(segundos)
            self._send_json(200, {"ok": True, "live": read_live()})
            return

        archivada = None
        if accion == "archivar":
            # la carrera terminada pasa a carreras/<slug>/ y la portada queda
            # libre para la siguiente (después se hace lo mismo que "reset")
            if not os.path.exists(os.path.join(ROOT, "resultado.json")):
                self._send_json(400, {"error": "falta resultado.json: genéralo antes con el FIT"})
                return
            archivada = slug_de(carrera())
            if not re.fullmatch(r"\d{4}-[a-z0-9-]{1,60}", archivada or ""):
                self._send_json(400, {"error": "la dirección del archivo no vale: pon «Dirección al archivarla» en los datos (año-nombre)"})
                return
            destino = os.path.join(ARCHIVO_DIR, archivada)
            if os.path.exists(destino):
                self._send_json(409, {"error": f"ya hay una carrera archivada en /{archivada}/ (pon otro \"slug\" en carrera.json)"})
                return
            # se llena en una carpeta oculta y se renombra de golpe: si falla a
            # medias (tarjeta llena) no queda un archivo cojo que bloquee los reintentos
            os.makedirs(ARCHIVO_DIR, exist_ok=True)
            tmp = tempfile.mkdtemp(dir=ARCHIVO_DIR, prefix="." + archivada + ".")
            try:
                for n in FICHEROS_CARRERA + ("resultado.json",):
                    if os.path.exists(os.path.join(ROOT, n)):
                        shutil.copy2(os.path.join(ROOT, n), tmp)
                os.rename(tmp, destino)
            except OSError:
                shutil.rmtree(tmp, ignore_errors=True)
                self._send_json(409, {"error": f"no se pudo archivar en /{archivada}/ (¿ya existe o falta espacio?)"})
                return
            os.remove(os.path.join(ROOT, "resultado.json"))
            apuntar_historial("archivada", slug=archivada)
            accion = "reset"

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
                "hr_t": None, "hr_at": None, "hr_suma": None, "hr_n": None, "gps_origen": None, "gps_rechazado_at": None,
                "ruta_km": None, "aviso_id": None, "aviso_t": None, "aviso_texto": None, "aviso_km": None,
            })
            self._send_json(200, {"ok": True, "live": current, "archivada": archivada})
            return

        if accion == "empezar":
            # Carrera solo con Traccar: sin enlace de iGPSPORT el crono no
            # arrancaba nunca (se ponía en marcha al pegar el enlace).
            hora = str(data.get("hora_salida") or read_live().get("hora_salida") or "").strip()
            self._send_json(200, {"ok": True, "live": self._empezar(hora)})
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
            if not actual.get("started_at") or actual.get("finished_at"):
                # carrera nueva: fuera los km y el pulso de la anterior (o de una
                # prueba en casa), como en _empezar; si no, se sumaba casa→salida
                patch.update({"gps_dist_km": 0, "gps_ult": None, "gps_t": None, "gps_at": None, "gps_origen": None,
                              "hr_suma": None, "hr_n": None, "hr_t": None, "hr_at": None, "dist_km": None,
                              "ruta_km": None, "lejos_de_meta": None, "aviso_id": None, "aviso_t": None,
                              "aviso_texto": None, "elapsed": None})
                actual["started_at"] = None
            guardada = actual.get("hora_salida")
            if guardada and self.hora_a_iso(guardada):
                patch["started_at"] = self.hora_a_iso(guardada)
            elif not actual.get("started_at"):
                patch["started_at"] = datetime.now(timezone.utc).isoformat()
            apuntar_historial("enlace", id=igpsport_id(new_url), url=new_url[:300])
            print(f"[admin] enlace nuevo: id={igpsport_id(new_url)}", flush=True)
            patch["igpsport_aviso"] = None

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
        # ⚠️ el poller arranca DESPUÉS de guardar el enlace: si arrancaba antes,
        # el vigilante (watch_live_file) podía leer el enlace viejo del disco
        # justo en medio y volver a lanzar el poller con él
        if new_url:
            start_poller(new_url)
        self._send_json(200, {"ok": True, "live": current})

    def log_message(self, fmt, *args):
        pass


# IP flotante (keepalived) de la instalación con dos Pis, desde la configuración
# del servicio. Sin ella, una sola máquina: siempre es la que sirve.
VIP = os.environ.get("SIGUEME_VIP", "")


def tengo_la_vip():
    """¿Es esta Pi la que está sirviendo la carrera?

    Se comprueba intentando reservar un puerto cualquiera en la VIP: si la
    dirección no está puesta en esta máquina, el sistema lo impide. Sin
    dependencias ni llamar a `ip`."""
    if not VIP:
        return True
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
            with poller_lock:
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


def asegurar_clave_gps():
    if not clave_gps():
        with open(GPS_CLAVE_PATH, "w", encoding="utf-8") as f:
            f.write("odg-" + secrets.token_urlsafe(24) + "\n")
        print("[gps] identificador nuevo creado (se cambia en el panel: Móvil → Ver la configuración)", flush=True)


if __name__ == "__main__":
    asegurar_clave_gps()
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
    # cola de conexiones: con 5 (lo de serie), una oleada de espectadores (todos
    # sondean a la vez) recibía conexiones rechazadas; medido con f1/carga.py
    http.server.ThreadingHTTPServer.request_queue_size = 128
    # quien cierra la pestaña a mitad de respuesta no es un fallo: sin esto, cada
    # una dejaba un Traceback en el registro y tapaba los errores de verdad
    _error_de_serie = http.server.ThreadingHTTPServer.handle_error
    def _sin_ruido(srv, peticion, cliente):
        if not isinstance(sys.exc_info()[1], ConnectionError):
            _error_de_serie(srv, peticion, cliente)
    http.server.ThreadingHTTPServer.handle_error = _sin_ruido
    with http.server.ThreadingHTTPServer((BIND_HOST, PORT), Handler) as httpd:
        print(f"Sígueme CC en http://127.0.0.1:{PORT}"
          + ("" if ADMIN_USER and ADMIN_HASH else "  ⚠️ SIN ADMIN_USER/ADMIN_HASH: el panel no dejará entrar")
          + ("" if VIP else "  · sin SIGUEME_VIP: una sola máquina (con dos Pis, las dos leerían iGPSPORT)"))
        httpd.serve_forever()
