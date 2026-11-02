#!/usr/bin/env python3
"""Carreras en directo de varios corredores (v1.54).

Las crea cualquiera con acceso (el dueño o un invitado) desde una de sus rutas: día y hora de salida. Los demás se
apuntan con el enlace de invitación (sin cuenta). Cada corredor tiene su identificador GPS, que pone en la app Android
o en Traccar: el servidor sabe de quién es cada punto por él, así que la app no cambia.

Todo es automático para cada corredor, como aprendimos en la primera carrera con Traccar (1/11/2026):
- en marcha con su primer punto desde 1 h antes de la salida (nadie pulsa nada);
- la salida real es cuando empieza a moverse desde la hora oficial (ese día la salida se retrasó 7 min);
- la meta, el punto más cercano a la meta cuando ya lleva el 80 % (el final del GPX quedaba a 47 m del arco).

Vive en <raíz>/directos/: <id>.dat (la carrera), <id>.<corredor>.dat (su estado) y <id>.<corredor>.pts (sus puntos,
uno por línea). Ninguna extensión se sirve. Las posiciones solo se publican desde que su corredor está en marcha.
"""
import json, math, os, re, secrets, tempfile, threading, time
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from zoneinfo import ZoneInfo

ID_RE = re.compile(r"^[0-9a-f]{10}$")
CID_RE = re.compile(r"^[0-9a-f]{8}$")
IDENT_PREFIJO = "dir-"
MAX_CORREDORES = 30
MAX_DIRECTOS = 40
ZONA = "Europe/Madrid"
ANTES = timedelta(hours=1)          # se pone en marcha con el primer punto desde 1 h antes de la salida
VEL_SALIDA = 5.0                    # km/h (más rápido que 12 min/km): por encima, tres puntos seguidos, ya no anda: corre
CERCA_META_M = 100                  # m: ya llegando a meta
PARTE_PARA_META = 0.8               # la meta solo cuenta con el 80 % de la ruta hecho

_lock = threading.RLock()
_indice = {}                        # identificador → (id de carrera, corredor)
_cum = {}                           # id de carrera → km acumulados de su ruta


def _dir(raiz):
    return os.path.join(raiz, "directos")


def _f(raiz, id_, cid=None, ext="dat"):
    if not ID_RE.match(str(id_)) or (cid is not None and not CID_RE.match(str(cid))):
        raise ValueError("carrera no válida")
    return os.path.join(_dir(raiz), f"{id_}.{cid}.{ext}" if cid else f"{id_}.{ext}")


def _escribir(ruta, datos):
    os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta), prefix=".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ruta)


def _leer(ruta, defecto=None):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def _km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    return 2 * 6371 * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


def _texto(v, largo):
    return re.sub(r"[\x00-\x1f\x7f<>]", "", str(v or "")).strip()[:largo]


def carrera(raiz, id_):
    return _leer(_f(raiz, id_)) if ID_RE.match(str(id_ or "")) else None


def _ids(raiz):
    try:
        return sorted(n[:-4] for n in os.listdir(_dir(raiz)) if n.endswith(".dat") and ID_RE.match(n[:-4]))
    except OSError:
        return []


def salida(c):
    return datetime.fromisoformat(f"{c['fecha']}T{c['hora_salida']}").replace(tzinfo=ZoneInfo(c.get("zona") or ZONA))


def _nuevo_corredor(nombre, usuario=None):
    return {"cid": secrets.token_hex(4), "nombre": _texto(nombre, 30) or "Corredor", "usuario": usuario,
            "ident": IDENT_PREFIJO + secrets.token_urlsafe(18), "creado": datetime.now(timezone.utc).isoformat()}


def crear(raiz, usuario, nombre_corredor, ruta, fecha, hora, calcular, limite_h=6):
    """Una carrera en directo desde una ruta (la de invitados._leer_ruta). Devuelve (carrera, su corredor)."""
    fecha, hora = _texto(fecha, 10), _texto(hora, 5)
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise ValueError("pon el día de la carrera")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hora):
        raise ValueError("pon la hora de salida (HH:MM)")
    if not ruta or len(ruta.get("coords") or []) < 2:
        raise ValueError("esa ruta no existe")
    perfil = ruta.get("perfil") or []
    try:
        plan = calcular([{"d": d, "ele": e} for d, e in perfil], [], ruta.get("desnivel_m"), 0.3, None) if len(perfil) >= 10 else {}
    except Exception:
        plan = {}
    for n, a in enumerate(plan.get("avisos", [])):
        a["id"] = n + 1
    yo = _nuevo_corredor(nombre_corredor, usuario)
    c = {"id": secrets.token_hex(5), "nombre": _texto(ruta.get("nombre"), 60) or "Carrera", "fecha": fecha, "hora_salida": hora,
         "zona": ZONA, "limite_h": limite_h, "creador": usuario, "creada": datetime.now(timezone.utc).isoformat(),
         "invitacion": secrets.token_urlsafe(9), "coords": ruta["coords"], "perfil": perfil,
         "distancia_km": ruta.get("distancia_km"), "desnivel_m": ruta.get("desnivel_m"), "subidas": ruta.get("subidas") or [],
         "plan": plan, "corredores": [yo]}
    with _lock:
        if len(_ids(raiz)) >= MAX_DIRECTOS:
            raise ValueError("hay demasiadas carreras en directo: borra alguna antigua")
        _escribir(_f(raiz, c["id"]), c)
        _indice[yo["ident"]] = (c["id"], yo["cid"])
    return c, yo


def unirse(raiz, id_, token, nombre, usuario=None, ahora=None, abierto=False):
    """Apuntarse con el enlace de invitación. Devuelve el corredor nuevo (con su identificador) o None."""
    with _lock:
        c = carrera(raiz, id_)
        if not c:
            return None
        if not (abierto and usuario):                 # con cuenta se puede entrar a una carrera abierta sin el enlace
            if not token or not compare_digest(str(token).encode(), c["invitacion"].encode()):
                return None
        if len(c["corredores"]) >= MAX_CORREDORES:
            raise ValueError("esta carrera ya está llena")
        if (ahora or time.time()) > (salida(c) + timedelta(hours=c.get("limite_h") or 6)).timestamp():
            raise ValueError("esta carrera ya terminó")
        if usuario:                                   # con cuenta: apuntarse dos veces no duplica, devuelve el que ya tiene
            ya = next((x for x in c["corredores"] if x.get("usuario") == usuario), None)
            if ya:
                return ya
        yo = _nuevo_corredor(nombre, usuario)
        c["corredores"].append(yo)
        _escribir(_f(raiz, id_), c)
        _indice[yo["ident"]] = (id_, yo["cid"])
    return yo


def buscar(raiz, ident):
    """(carrera, corredor) de un identificador «dir-…», o (None, None)."""
    ident = str(ident or "")
    if not ident.startswith(IDENT_PREFIJO):
        return None, None
    with _lock:
        if ident not in _indice:                      # carreras nuevas (o de la otra Pi tras un relevo): se relee todo
            _indice.clear()
            for id_ in _ids(raiz):
                for co in (carrera(raiz, id_) or {}).get("corredores", []):
                    _indice[co["ident"]] = (id_, co["cid"])
        id_, cid = _indice.get(ident, (None, None))
        c = carrera(raiz, id_) if id_ else None
        co = next((x for x in (c or {}).get("corredores", []) if x["cid"] == cid and compare_digest(x["ident"], ident)), None)
        return (c, co) if co else (None, None)


def _cum_de(c):
    if c["id"] not in _cum:
        acum = [0.0]
        for a, b in zip(c["coords"], c["coords"][1:]):
            acum.append(acum[-1] + _km((a[1], a[0]), (b[1], b[0])))
        _cum[c["id"]] = acum
    return _cum[c["id"]]


def _km_en_ruta(c, la, lo, desde):
    """Km de la ruta del punto, siempre hacia delante (ventana desde el último km), o None si está lejos (> 150 m)."""
    cum, coords = _cum_de(c), c["coords"]
    mejor, mk = 1e9, None
    for j in range(len(coords)):
        if cum[j] < desde - 0.5:
            continue
        if cum[j] > desde + 8:
            break
        d = _km((la, lo), (coords[j][1], coords[j][0]))
        if d < mejor:
            mejor, mk = d, cum[j]
    return mk if mejor < 0.15 else None


def estado(raiz, id_, cid):
    return _leer(_f(raiz, id_, cid), {}) or {}


def recibir(raiz, ident, puntos, ahora=None):
    """Puntos de un corredor (los de server.puntos_traccar). False si el identificador no es de ninguna carrera."""
    c, co = buscar(raiz, ident)
    if not c:
        return False
    ahora = ahora or time.time()
    con_pos = sorted((p for p in puntos if p.get("lat") is not None), key=lambda p: p["t"])
    with _lock:
        st = estado(raiz, c["id"], co["cid"])
        if st.get("retirado"):
            return True                                   # retirado: se ignoran sus puntos
        bat = [p["bateria"] for p in puntos if p.get("bateria") is not None]
        if bat:
            st["bateria"] = round(bat[-1])
        if con_pos:
            with open(_f(raiz, c["id"], co["cid"], "pts"), "a", encoding="utf-8") as f:
                for p in con_pos:
                    f.write(json.dumps([round(p["t"], 1), round(p["lat"], 6), round(p["lon"], 6)]) + "\n")
        sal = salida(c)
        fin = sal + timedelta(hours=c.get("limite_h") or 6)
        if not st.get("en_marcha") and con_pos and sal - ANTES <= datetime.fromtimestamp(ahora, timezone.utc) <= fin:
            st["en_marcha"] = sal.astimezone(timezone.utc).isoformat()
        meta = (c["coords"][-1][1], c["coords"][-1][0])
        minimo_meta = PARTE_PARA_META * _cum_de(c)[-1]
        for p in con_pos:
            ult = st.get("ult")
            if ult and p["t"] <= ult[2]:
                continue                                  # repetido o viejo (la cola de Traccar al volver la cobertura)
            v = _km((ult[0], ult[1]), (p["lat"], p["lon"])) / max(1.0, p["t"] - ult[2]) * 3600 if ult else 0
            st["ult"] = [p["lat"], p["lon"], p["t"]]
            if not st.get("en_marcha") or st.get("llegada"):
                continue
            # salida real: tres puntos seguidos moviéndose, desde la hora oficial (cuenta desde el primero)
            if not st.get("salida_real") and p["t"] >= sal.timestamp():
                if v > VEL_SALIDA:
                    st.setdefault("mov_t0", p["t"])
                    st["mov_n"] = st.get("mov_n", 0) + 1
                    if st["mov_n"] >= 3:
                        st["salida_real"] = st.pop("mov_t0")
                        st.pop("mov_n", None)
                else:
                    st.pop("mov_t0", None)
                    st["mov_n"] = 0
            k = _km_en_ruta(c, p["lat"], p["lon"], st.get("km", 0))
            if k is not None and st.get("salida_real"):
                st["km"] = max(st.get("km", 0), k)
            # meta: el punto más cercano a la meta del tramo final, en cuanto se aleja o se para
            if st.get("salida_real") and st.get("km", 0) >= minimo_meta:
                d = _km((p["lat"], p["lon"]), meta) * 1000
                cerca = st.get("cerca")
                if d < CERCA_META_M and (not cerca or d < cerca[0]):
                    st["cerca"], st["lejos_n"] = [d, p["t"]], 0
                elif cerca:
                    st["lejos_n"] = st.get("lejos_n", 0) + (1 if d > cerca[0] + 3 or v < 2 else 0)
                    if st["lejos_n"] >= 2 or d >= CERCA_META_M:
                        st["llegada"] = cerca[1]
        _escribir(_f(raiz, c["id"], co["cid"]), st)
    return True


def empezar_desde_app(raiz, ident):
    """«Empezar seguimiento» en la app Android: en marcha si es el día (como el primer punto)."""
    c, co = buscar(raiz, ident)
    if not c:
        return "no", "Este móvil no es de ninguna carrera"
    sal, ahora = salida(c), datetime.now(timezone.utc)
    if not sal - timedelta(hours=6) <= ahora <= sal + timedelta(hours=c.get("limite_h") or 6):
        return "otro_dia", f"La carrera es el {c['fecha']} a las {c['hora_salida']}: hoy es solo una prueba"
    with _lock:
        st = estado(raiz, c["id"], co["cid"])
        if st.get("en_marcha"):
            return "ya_estaba", "Ya estabas en marcha en la web"
        st["en_marcha"] = sal.astimezone(timezone.utc).isoformat()
        _escribir(_f(raiz, c["id"], co["cid"]), st)
    return "empezada", f"En marcha en la web (salida a las {c['hora_salida']})"


def plan_app(c):
    """Lo mismo que el plan de la carrera del dueño, para la app Android (que no cambia)."""
    pl = c.get("plan") or {}
    return {"carrera": {"nombre": c["nombre"], "fecha": c["fecha"], "hora_salida": c["hora_salida"], "zona_horaria": c.get("zona") or ZONA,
                        "distancia_km": c.get("distancia_km"), "desnivel_m": c.get("desnivel_m"), "limite_h": c.get("limite_h")},
            "ruta": [[x[0], x[1]] for x in c["coords"]],
            "perfil": c.get("perfil") or [], "avituallamientos": [],
            "avisos": pl.get("avisos", []), "subidas": pl.get("subidas", []), "restante": pl.get("restante", []),
            "generado": c.get("creada")}


def retirar(raiz, ident):
    """El corredor se retira: deja de salir en el mapa y sus puntos ya no cuentan. False si el identificador no vale."""
    c, co = buscar(raiz, ident)
    if not c:
        return False
    with _lock:
        st = estado(raiz, c["id"], co["cid"])
        if not st.get("retirado"):
            st["retirado"] = time.time()
            _escribir(_f(raiz, c["id"], co["cid"]), st)
    return True


def abiertas(raiz, usuario, ahora=None):
    """Las carreras de otros a las que un usuario con cuenta puede apuntarse sin enlace (no terminadas ni llenas)."""
    ahora = ahora or time.time()
    out = []
    for id_ in _ids(raiz):
        c = carrera(raiz, id_)
        if not c or c.get("creador") == usuario or any(x.get("usuario") == usuario for x in c["corredores"]):
            continue
        if len(c["corredores"]) >= MAX_CORREDORES or ahora > (salida(c) + timedelta(hours=c.get("limite_h") or 6)).timestamp():
            continue
        out.append({"id": id_, "nombre": c["nombre"], "fecha": c["fecha"], "hora_salida": c["hora_salida"],
                    "distancia_km": c.get("distancia_km"), "salida_ts": salida(c).timestamp(),
                    "corredores": [x["nombre"] for x in c["corredores"] if not estado(raiz, id_, x["cid"]).get("retirado")]})
    out.sort(key=lambda x: x["salida_ts"])
    return out


def _situacion(st):
    if st.get("retirado"):
        return "retirado"
    if st.get("llegada"):
        return "en_meta"
    if st.get("salida_real"):
        return "corriendo"
    if st.get("en_marcha"):
        return "en_la_salida"
    return "sin_empezar"


def publico(raiz, id_, ahora=None):
    """Lo que ve cualquiera en /d/<id>: la carrera y cada corredor (posición solo desde que está en marcha)."""
    c = carrera(raiz, id_)
    if not c:
        return None
    ahora = ahora or time.time()
    gente = []
    for co in c["corredores"]:
        st = estado(raiz, id_, co["cid"])
        sit = _situacion(st)
        x = {"cid": co["cid"], "nombre": co["nombre"], "situacion": sit, "km": round(st.get("km", 0), 2)}
        if sit not in ("sin_empezar", "retirado") and st.get("ult"):
            x["lat"], x["lon"], x["visto"] = st["ult"][0], st["ult"][1], st["ult"][2]
            x["bateria"] = st.get("bateria")
        if st.get("salida_real"):
            x["salida"] = st["salida_real"]
            x["tiempo_s"] = int((st.get("llegada") or ahora) - st["salida_real"])
        if sit == "en_meta":
            x["lat"], x["lon"] = c["coords"][-1][1], c["coords"][-1][0]
        gente.append(x)
    gente.sort(key=lambda g: (g["situacion"] == "retirado", g["situacion"] != "en_meta", g.get("tiempo_s") if g["situacion"] == "en_meta" else -g["km"]))
    sal = salida(c)
    return {"id": id_, "nombre": c["nombre"], "fecha": c["fecha"], "hora_salida": c["hora_salida"],
            "distancia_km": c.get("distancia_km"), "desnivel_m": c.get("desnivel_m"),
            "ruta": [[round(x[0], 5), round(x[1], 5)] for x in c["coords"][::max(1, len(c["coords"]) // 600)]],
            "perfil": (c.get("perfil") or [])[::max(1, len(c.get("perfil") or []) // 150)],
            "subidas": c.get("subidas") or [], "salida_ts": sal.timestamp(),
            "estado": _estado_carrera(c, gente, ahora), "corredores": gente}


def _estado_carrera(c, gente, ahora):
    sal = salida(c).timestamp()
    if gente and all(g["situacion"] in ("en_meta", "retirado") for g in gente):
        return "terminada"
    if ahora > sal + (c.get("limite_h") or 6) * 3600:
        return "terminada"
    if any(g["situacion"] not in ("sin_empezar", "retirado") for g in gente):     # alguien ya salió (o llegó): en directo hasta que lleguen todos
        return "en_directo"
    return "proxima"


def lista(raiz, ahora=None):
    """Para la portada y Carreras: las de los últimos 60 días y las próximas. Primero las que están en directo."""
    ahora = ahora or time.time()
    out = []
    for id_ in _ids(raiz):
        p = publico(raiz, id_, ahora)
        if not p or ahora - p["salida_ts"] > 60 * 86400:
            continue
        out.append({"id": id_, "nombre": p["nombre"], "fecha": p["fecha"], "hora_salida": p["hora_salida"],
                    "distancia_km": p["distancia_km"], "desnivel_m": p["desnivel_m"], "estado": p["estado"],
                    "corredores": [{"nombre": g["nombre"], "tiempo_s": g.get("tiempo_s") if g["situacion"] == "en_meta" else None}
                                   for g in p["corredores"] if g["situacion"] != "retirado"],
                    "traza": p["ruta"][::max(1, len(p["ruta"]) // 80)], "salida_ts": p["salida_ts"]})
    orden = {"en_directo": 0, "proxima": 1, "terminada": 2}
    out.sort(key=lambda x: (orden[x["estado"]], x["salida_ts"] if x["estado"] == "proxima" else -x["salida_ts"]))
    return out


def mias(raiz, usuario):
    """Las carreras de un usuario (las que creó y en las que corre), con SU identificador para configurar el móvil."""
    out = []
    for id_ in _ids(raiz):
        c = carrera(raiz, id_)
        if not c:
            continue
        yo = next((x for x in c["corredores"] if x.get("usuario") == usuario), None)
        if c.get("creador") != usuario and not yo:
            continue
        out.append({"id": id_, "nombre": c["nombre"], "fecha": c["fecha"], "hora_salida": c["hora_salida"],
                    "creador": c.get("creador") == usuario, "invitacion": c["invitacion"] if c.get("creador") == usuario else None,
                    "ident": yo["ident"] if yo else None, "corredores": [x["nombre"] for x in c["corredores"]]})
    out.sort(key=lambda x: x["fecha"], reverse=True)
    return out


def borrar(raiz, id_, usuario=None):
    """La borra su creador (o el dueño de la web, con usuario=None)."""
    with _lock:
        c = carrera(raiz, id_)
        if not c or (usuario is not None and c.get("creador") != usuario):
            return False
        for co in c["corredores"]:
            _indice.pop(co["ident"], None)
            for ext in ("dat", "pts"):
                try:
                    os.remove(_f(raiz, id_, co["cid"], ext))
                except OSError:
                    pass
        os.remove(_f(raiz, id_))
        _cum.pop(id_, None)
    return True


def todas(raiz):
    """Para el panel del dueño."""
    return [{"id": i, "nombre": c["nombre"], "fecha": c["fecha"], "hora_salida": c["hora_salida"], "creador": c.get("creador"),
             "corredores": [x["nombre"] for x in c["corredores"]]} for i in _ids(raiz) for c in [carrera(raiz, i)] if c]
