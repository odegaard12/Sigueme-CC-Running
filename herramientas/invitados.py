#!/usr/bin/env python3
"""Invitados: amigos con un usuario y un código que caduca, para preparar SUS
rutas (subir un GPX, poner avituallamientos) y llevárselas al reloj. Sin
seguimiento y sin ver nada de la carrera del dueño.

Todo vive en <raíz>/invitados/ con extensiones que el servidor NO sirve (.dat,
.ruta). Del GPX que sube un invitado solo se guarda la ruta ya simplificada y
su perfil; el fichero original no se guarda.

Cada ruta es PRIVADA hasta que su dueño la publica. Lo público se ve recortado
(por defecto sin los primeros y últimos 300 m: ahí suele estar su casa) y deja de
verse en cuanto caduca el acceso del invitado.
"""
import bisect, hashlib, json, math, os, re, secrets, tempfile, threading
from datetime import date, datetime, timedelta
from hmac import compare_digest

USUARIO_RE = re.compile(r"^[a-z0-9]{3,20}$")
ID_RE = re.compile(r"^[0-9a-f]{12}$")
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"      # sin I, L, O, 0, 1: no se confunden al copiarlas
MAX_USUARIOS = 20
MAX_RUTAS = 5
MAX_AVIT = 30
MARGEN_DIAS = 0                                   # el día siguiente a la fecha de caducidad se borra todo
MAX_GPX = 8_000_000                               # bytes
RESERVADOS = {"admin", "dueno"}
SIN_CADUCIDAD = "2099-12-31"                      # días=0: una cuenta que no caduca (la del dueño)
OCULTAR_POR_DEFECTO = 300                         # m sin enseñar al principio y al final de lo público

_lock = threading.RLock()
# cada scrypt usa ~16 MB: como mucho dos a la vez (la Pi es pequeña)
_scrypt_sem = threading.BoundedSemaphore(2)


def _dir(raiz):
    return os.path.join(raiz, "invitados")


def _fichero(raiz):
    return os.path.join(_dir(raiz), "usuarios.dat")


def _escribir(ruta, datos):
    """Atómico: o el fichero viejo entero o el nuevo entero; solo lo lee su dueño."""
    os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta), prefix=".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, ruta)


def _leer(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def _usuarios(raiz):
    return _leer(_fichero(raiz), {}).get("usuarios", {})


def _usuarios_seguro(raiz):
    """Como _usuarios, pero devuelve None si el fichero EXISTE y no se puede leer (SD con errores, apagón):
    quien borra o sobrescribe tiene que parar en ese caso."""
    try:
        with open(_fichero(raiz), encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    u = d.get("usuarios") if isinstance(d, dict) else None
    return u if isinstance(u, dict) else None


def _guardar(raiz, usuarios):
    _escribir(_fichero(raiz), {"usuarios": usuarios})


def _hash(codigo, sal):
    with _scrypt_sem:
        return hashlib.scrypt(codigo.encode(), salt=sal, n=2 ** 14, r=8, p=1, dklen=32).hex()


def _normal(codigo):
    return re.sub(r"[\s-]", "", str(codigo)).upper()


def _codigo_nuevo():
    c = "".join(secrets.choice(ALFABETO) for _ in range(12))
    return "-".join(c[i:i + 4] for i in range(0, 12, 4))


def _usuario_valido(usuario):
    usuario = str(usuario or "").strip().lower()
    if not USUARIO_RE.match(usuario) or usuario in RESERVADOS:
        raise ValueError("el usuario son 3 a 20 letras minúsculas o números, sin espacios")
    return usuario


def _dias(dias, cero=False):
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        raise ValueError("los días tienen que ser un número")
    if not (0 if cero else 1) <= dias <= 365:
        raise ValueError("de 1 a 365 días" + (" (0 = sin caducidad)" if cero else ""))
    return dias


# ---- usuarios (los gestiona el dueño desde el panel) ----

def crear(raiz, usuario, dias=30, nombre=""):
    """Devuelve el código (solo se ve ahora: en disco queda su hash)."""
    usuario, dias = _usuario_valido(usuario), _dias(dias, cero=True)
    with _lock:
        todos = _usuarios_seguro(raiz)
        if todos is None:
            raise ValueError("no se pudo leer la lista de invitados: no se crea nada para no perderla")
        if usuario in todos:
            raise ValueError("ese usuario ya existe")
        if len(todos) >= MAX_USUARIOS:
            raise ValueError(f"ya hay {MAX_USUARIOS} invitados: quita alguno")
        codigo, sal = _codigo_nuevo(), os.urandom(16)
        todos[usuario] = {"nombre": re.sub(r"[\x00-\x1f]", "", str(nombre or usuario))[:40].strip() or usuario,
                          "hash": f"scrypt:{sal.hex()}:{_hash(_normal(codigo), sal)}",
                          "caduca": (date.today() + timedelta(days=dias)).isoformat() if dias else SIN_CADUCIDAD,
                          "creado": datetime.now().isoformat(timespec="seconds")}
        _guardar(raiz, todos)
    return codigo


def renovar(raiz, usuario, dias=30):
    """Alarga el acceso `dias` días desde hoy (o desde que caduque, si aún vale más)."""
    usuario, dias = _usuario_valido(usuario), _dias(dias)
    with _lock:
        todos = _usuarios(raiz)
        if usuario not in todos:
            raise ValueError("ese usuario no existe")
        if todos[usuario]["caduca"] == SIN_CADUCIDAD:
            return SIN_CADUCIDAD                      # ya no caduca
        base = max(date.today(), date.fromisoformat(todos[usuario]["caduca"]))
        todos[usuario]["caduca"] = (base + timedelta(days=dias)).isoformat()
        _guardar(raiz, todos)
        return todos[usuario]["caduca"]


def codigo_nuevo(raiz, usuario):
    usuario = _usuario_valido(usuario)
    with _lock:
        todos = _usuarios(raiz)
        if usuario not in todos:
            raise ValueError("ese usuario no existe")
        codigo, sal = _codigo_nuevo(), os.urandom(16)
        todos[usuario]["hash"] = f"scrypt:{sal.hex()}:{_hash(_normal(codigo), sal)}"
        _guardar(raiz, todos)
    return codigo


def borrar(raiz, usuario):
    usuario = _usuario_valido(usuario)
    with _lock:
        todos = _usuarios(raiz)
        if todos.pop(usuario, None) is None:
            raise ValueError("ese usuario no existe")
        _guardar(raiz, todos)
        _borrar_carpeta(raiz, usuario)
    _reindexar(raiz)


def _borrar_carpeta(raiz, usuario):
    carpeta = os.path.join(_dir(raiz), usuario)
    if os.path.isdir(carpeta):
        for n in os.listdir(carpeta):
            try:
                os.remove(os.path.join(carpeta, n))
            except OSError:
                pass
        try:
            os.rmdir(carpeta)
        except OSError:
            pass


def listar(raiz):
    hoy = date.today().isoformat()
    return [{"usuario": u, "nombre": r.get("nombre", u), "caduca": r["caduca"], "activo": r["caduca"] >= hoy,
             "sin_caducidad": r["caduca"] == SIN_CADUCIDAD, "rutas": len(_ids(raiz, u)),
             "publicas": sum(1 for i in _ids(raiz, u) if (_leer(_ruta_path(raiz, u, i), {}) or {}).get("publica"))}
            for u, r in sorted(_usuarios(raiz).items())]


DUENO = "dueno"       # el dueño de la web: sus rutas viven en invitados/dueno/, sin crear cuenta y sin caducidad


def _registro(raiz, usuario):
    if usuario == DUENO:
        return {"nombre": "Tú", "caduca": SIN_CADUCIDAD}
    return _usuarios(raiz).get(str(usuario))


def activo(raiz, usuario):
    """El registro del invitado si existe y no ha caducado; si no, None."""
    r = _registro(raiz, usuario)
    return r if r and r["caduca"] >= date.today().isoformat() else None


def comprobar(raiz, usuario, codigo):
    """Usuario y código correctos y sin caducar. Siempre hace el scrypt (mismo tiempo exista o no)."""
    r = activo(raiz, str(usuario).strip().lower())
    try:
        _, sal, esperado = (r or {}).get("hash", "scrypt:00:00").split(":")
        calculado = _hash(_normal(codigo), bytes.fromhex(sal or "00"))
    except ValueError:
        return False
    return bool(r) and compare_digest(calculado.encode(), esperado.encode())


def purgar(raiz):
    """Borra a quien lleva más de MARGEN_DIAS caducado. Devuelve cuántos."""
    limite = (date.today() - timedelta(days=MARGEN_DIAS)).isoformat()
    with _lock:
        todos = _usuarios_seguro(raiz)
        if todos is None:
            return 0                     # lista ilegible: no se borra nada
        viejos = [u for u, r in todos.items() if r["caduca"] < limite]
        for u in viejos:
            del todos[u]
            _borrar_carpeta(raiz, u)
        if viejos:
            _guardar(raiz, todos)
            _reindexar(raiz)
        # carpetas de usuarios que ya no existen (por si algo se quedó a medias)
        base = _dir(raiz)
        if os.path.isdir(base):
            for n in os.listdir(base):
                if os.path.isdir(os.path.join(base, n)) and n not in todos and n != DUENO:
                    _borrar_carpeta(raiz, n)
    return len(viejos)


# ---- rutas de cada invitado ----

def _ids(raiz, usuario):
    carpeta = os.path.join(_dir(raiz), usuario)
    try:
        return sorted(n[:-5] for n in os.listdir(carpeta) if n.endswith(".ruta") and ID_RE.match(n[:-5]))
    except OSError:
        return []


def _ruta_path(raiz, usuario, id_):
    if not ID_RE.match(str(id_)) or not USUARIO_RE.match(usuario):
        raise ValueError("ruta no válida")
    return os.path.join(_dir(raiz), usuario, id_ + ".ruta")


def _norm(r):
    """Las rutas de antes de poder publicar no traen estos campos."""
    r.setdefault("publica", False)
    r.setdefault("ocultar_m", OCULTAR_POR_DEFECTO)
    r.setdefault("autor", "")
    r.setdefault("publicada", None)
    return r


def _resumen(r):
    return {"id": r["id"], "nombre": r["nombre"], "creada": r["creada"], "distancia_km": r["distancia_km"],
            "desnivel_m": r["desnivel_m"], "avituallamientos": len(r["avituallamientos"]), "publica": r["publica"]}


def _detalle(r):
    """Lo que ve su dueño: sin las coordenadas completas (pesan) y con un perfil ligero."""
    perfil = r["perfil"]
    paso = max(1, len(perfil) // 150)
    return dict(_resumen(r), avituallamientos=r["avituallamientos"], subidas=r["subidas"], perfil=perfil[::paso],
                ocultar_m=r["ocultar_m"], autor=r["autor"], publicada=r["publicada"])


def _leer_ruta(raiz, usuario, id_):
    r = _leer(_ruta_path(raiz, usuario, id_), None)
    return _norm(r) if r else None


def rutas(raiz, usuario):
    out = []
    for i in _ids(raiz, usuario):
        r = _leer_ruta(raiz, usuario, i)
        if r:
            out.append(_resumen(r))
    return sorted(out, key=lambda r: r["creada"], reverse=True)


def _texto(valor, largo):
    return re.sub(r"[\x00-\x1f\x7f]", "", str(valor or "")).strip()[:largo]


def crear_ruta(raiz, usuario, nombre, gpx, preparar, calcular):
    """Procesa el GPX en memoria y guarda solo la ruta simplificada y su perfil.
    `preparar` y `calcular` son las de preparar_ruta y plan_avisos."""
    if len(gpx) > MAX_GPX:
        raise ValueError(f"el GPX tiene que pesar menos de {MAX_GPX // 1_000_000} MB")
    with _lock:
        if len(_ids(raiz, usuario)) >= MAX_RUTAS:
            raise ValueError(f"ya tienes {MAX_RUTAS} rutas: borra alguna para subir otra")
    nombre = _texto(nombre, 60) or "Ruta"
    ruta, elev, resumen = preparar(gpx, nombre, None)         # ValueError si no es un GPX válido
    coords = ruta["features"][0]["geometry"]["coordinates"]
    perfil = elev.get("profile") or []
    try:
        subidas = calcular(perfil, [], None, 0.3, None)["subidas"] if len(perfil) >= 10 else []
    except Exception:
        subidas = []
    r = {"id": secrets.token_hex(6), "nombre": nombre, "creada": datetime.now().isoformat(timespec="seconds"),
         "distancia_km": resumen["distancia_km"], "desnivel_m": resumen["desnivel_m"], "coords": coords,
         "perfil": [[p["d"], p["ele"]] for p in perfil], "avituallamientos": [], "subidas": subidas,
         "publica": False, "ocultar_m": OCULTAR_POR_DEFECTO, "autor": "", "publicada": None}
    with _lock:
        if len(_ids(raiz, usuario)) >= MAX_RUTAS:
            raise ValueError(f"ya tienes {MAX_RUTAS} rutas: borra alguna para subir otra")
        _escribir(_ruta_path(raiz, usuario, r["id"]), r)
    return _detalle(r)


def ruta(raiz, usuario, id_):
    r = _leer_ruta(raiz, usuario, id_)
    return _detalle(r) if r else None


def limpiar_avit(lista, total_km):
    if not isinstance(lista, list) or len(lista) > MAX_AVIT:
        raise ValueError(f"hasta {MAX_AVIT} avituallamientos")
    salida = []
    for a in lista:
        try:
            nombre, km = _texto(a.get("name"), 40), float(a.get("km"))
        except (AttributeError, TypeError, ValueError):
            raise ValueError("cada avituallamiento necesita nombre y km")
        if not nombre or not 0 <= km <= total_km + 1:
            raise ValueError(f"cada avituallamiento necesita nombre y un km entre 0 y {total_km:g}")
        salida.append({"name": nombre, "km": round(km, 2)})
    return sorted(salida, key=lambda a: a["km"])


def guardar_ruta(raiz, usuario, id_, nombre=None, avituallamientos=None, publica=None, ocultar_m=None, autor=None):
    with _lock:
        p = _ruta_path(raiz, usuario, id_)
        r = _leer_ruta(raiz, usuario, id_)
        if not r:
            return None
        estaba = r["publica"]
        if nombre is not None:
            r["nombre"] = _texto(nombre, 60) or r["nombre"]
        if avituallamientos is not None:
            r["avituallamientos"] = limpiar_avit(avituallamientos, r["distancia_km"])
        if ocultar_m is not None:
            try:
                r["ocultar_m"] = int(ocultar_m)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("los metros a ocultar tienen que ser un número")
            if not 0 <= r["ocultar_m"] <= 1000:
                raise ValueError("se pueden ocultar de 0 a 1000 m")
        if autor is not None:
            r["autor"] = _texto(autor, 30)
        if publica is not None:
            r["publica"] = bool(publica)
            r["publicada"] = (r["publicada"] or datetime.now().isoformat(timespec="seconds")) if r["publica"] else None
        _escribir(p, r)
        if estaba or r["publica"]:
            _reindexar(raiz)
        return _detalle(r)


def borrar_ruta(raiz, usuario, id_):
    with _lock:
        p = _ruta_path(raiz, usuario, id_)
        if not os.path.exists(p):
            return False
        os.remove(p)
        _reindexar(raiz)
        return True


def gpx_reloj(raiz, usuario, id_, generar):
    """El GPX para el reloj de una ruta suya. `generar` es gpx_reloj.generar."""
    r = _leer_ruta(raiz, usuario, id_)
    if not r:
        return None, None
    return r["nombre"], generar(r["nombre"], r["coords"], r["perfil"], r["avituallamientos"], r["subidas"])


# ---- lo público: rutas publicadas, recortadas, con un índice para la portada ----

def _km(a, b):
    """Distancia en km entre dos puntos [lon, lat] (haversine)."""
    f1, f2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((f2 - f1) / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _desnivel(perfil):
    """D+ con un umbral de 3 m (el ruido del GPS no suma)."""
    gana, ref = 0.0, perfil[0][1] if perfil else 0
    for _, e in perfil[1:]:
        if e - ref >= 3:
            gana, ref = gana + e - ref, e
        elif e < ref:
            ref = e
    return round(gana)


def _muestra(lista, n):
    paso = max(1, math.ceil(len(lista) / n))
    sal = lista[::paso]
    return sal if sal[-1] is lista[-1] else sal + [lista[-1]]


def _publico(r):
    """La ruta tal y como se enseña al público: sin los primeros y últimos `ocultar_m` metros
    (nunca más de un cuarto por lado), con los km, avituallamientos y subidas ajustados."""
    coords, perfil = r["coords"], r["perfil"]
    total = perfil[-1][0] if perfil else r["distancia_km"]
    a = max(0.0, min(r["ocultar_m"] / 1000, total / 4))
    km = [0.0]
    for p, q in zip(coords, coords[1:]):
        km.append(km[-1] + _km(p, q))
    esc = (total / km[-1]) if km[-1] else 1
    km = [x * esc for x in km]
    if a > 0:
        i0 = bisect.bisect_left(km, a)
        i1 = max(bisect.bisect_right(km, total - a) - 1, i0 + 1)
        coords = coords[i0:i1 + 1]
        perfil = [[round(d - a, 3), e] for d, e in perfil if a <= d <= total - a]
        avit = [dict(x, km=round(x["km"] - a, 2)) for x in r["avituallamientos"] if a <= x["km"] <= total - a]
        subidas = [dict(s, inicio=round(s["inicio"] - a, 2), fin=round(s["fin"] - a, 2))
                   for s in r["subidas"] if s["inicio"] >= a and s["fin"] <= total - a]
        for n, s in enumerate(subidas, 1):
            s["n"] = n
        distancia, desnivel = round(total - 2 * a, 2), _desnivel(perfil)
    else:
        avit, subidas, distancia, desnivel = r["avituallamientos"], r["subidas"], r["distancia_km"], r["desnivel_m"]
    return {"id": r["id"], "nombre": r["nombre"], "autor": r["autor"], "publicada": r["publicada"],
            "distancia_km": distancia, "desnivel_m": desnivel, "coords": coords, "perfil": perfil,
            "avituallamientos": avit, "subidas": subidas}


def _indice(raiz):
    return os.path.join(_dir(raiz), "publicas.dat")


def _reindexar(raiz):
    """Reconstruye el índice de rutas publicadas (lo que lee la portada, sin abrir cada ruta)."""
    with _lock:
        sal = []
        base = _dir(raiz)
        if os.path.isdir(base):
            for u in sorted(os.listdir(base)):
                if not (USUARIO_RE.match(u) and os.path.isdir(os.path.join(base, u))):
                    continue
                for i in _ids(raiz, u):
                    r = _leer_ruta(raiz, u, i)
                    if not r or not r["publica"] or not r["coords"]:
                        continue
                    p = _publico(r)
                    sal.append({"id": p["id"], "u": u, "nombre": p["nombre"], "autor": p["autor"], "publicada": p["publicada"],
                                "distancia_km": p["distancia_km"], "desnivel_m": p["desnivel_m"],
                                "avituallamientos": len(p["avituallamientos"]),
                                "traza": [[round(x, 4), round(y, 4)] for x, y in _muestra(p["coords"], 60)],
                                "perfil": [[round(d, 2), round(e)] for d, e in _muestra(p["perfil"], 40)] if p["perfil"] else []})
        sal.sort(key=lambda x: x["publicada"] or "", reverse=True)
        _escribir(_indice(raiz), {"rutas": sal})


_cache_indice = {"mtime": None, "datos": []}


def _leer_indice(raiz):
    try:
        st = os.stat(_indice(raiz))
        m = (st.st_mtime_ns, st.st_size, st.st_ino)
    except OSError:
        return []
    if m != _cache_indice["mtime"]:
        _cache_indice.update(mtime=m, datos=_leer(_indice(raiz), {}).get("rutas", []))
    return _cache_indice["datos"]


def publicas(raiz):
    """Las rutas publicadas de invitados con el acceso vigente, la más nueva primero (sin decir de quién son)."""
    hoy = date.today().isoformat()
    vivos = {u for u, r in _usuarios(raiz).items() if r["caduca"] >= hoy} | {DUENO}
    return [{k: v for k, v in x.items() if k != "u"} for x in _leer_indice(raiz) if x["u"] in vivos]


def publica_detalle(raiz, id_):
    """Una ruta publicada con todo lo que pinta su página (y nada más), o None."""
    if not ID_RE.match(str(id_)):
        return None
    hoy = date.today().isoformat()
    for x in _leer_indice(raiz):
        if x["id"] == id_:
            u = _registro(raiz, x["u"])
            if not u or u["caduca"] < hoy:
                return None
            r = _leer_ruta(raiz, x["u"], id_)
            if not r or not r["publica"]:
                return None
            p = _publico(r)
            lon, lat = [c[0] for c in p["coords"]], [c[1] for c in p["coords"]]
            p["coords"] = _muestra(p["coords"], 500)
            p["perfil"] = _muestra(p["perfil"], 200) if p["perfil"] else []
            p["bbox"] = [min(lon), min(lat), max(lon), max(lat)]
            return p
    return None


def gpx_publico(raiz, id_, generar):
    """El GPX para el reloj de una ruta publicada (con el recorte, igual que la página)."""
    if not publica_detalle(raiz, id_):
        return None, None
    r = _leer_ruta(raiz, next(x["u"] for x in _leer_indice(raiz) if x["id"] == id_), id_)
    p = _publico(r)
    return p["nombre"], generar(p["nombre"], p["coords"], p["perfil"], p["avituallamientos"], p["subidas"])


# ---- moderación (el dueño, desde el panel) ----

def todas(raiz):
    """Todas las rutas de todos los invitados, para que el dueño vea qué hay publicado."""
    sal = []
    hoy = date.today().isoformat()
    for u, reg in sorted(_usuarios(raiz).items()) + [(DUENO, _registro(raiz, DUENO))]:
        for i in _ids(raiz, u):
            r = _leer_ruta(raiz, u, i)
            if r:
                sal.append({"usuario": u, "id": r["id"], "nombre": r["nombre"], "distancia_km": r["distancia_km"],
                            "publica": r["publica"], "autor": r["autor"], "publicada": r["publicada"],
                            "activo": reg["caduca"] >= hoy})
    return sorted(sal, key=lambda x: (not x["publica"], x["usuario"], x["nombre"]))


def moderar(raiz, usuario, id_, accion):
    usuario = usuario if usuario == DUENO else _usuario_valido(usuario)
    if accion == "borrar":
        if not borrar_ruta(raiz, usuario, id_):
            raise ValueError("esa ruta no existe")
    elif accion == "despublicar":
        if guardar_ruta(raiz, usuario, id_, publica=False) is None:
            raise ValueError("esa ruta no existe")
    else:
        raise ValueError("acción no válida")
