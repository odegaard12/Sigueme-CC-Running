#!/usr/bin/env python3
"""Invitados: amigos con un usuario y un código que caduca, para preparar SUS
rutas (subir un GPX, poner avituallamientos) y llevárselas al reloj. Sin
seguimiento y sin ver nada de la carrera del dueño.

Todo vive en <raíz>/invitados/ con extensiones que el servidor NO sirve (.dat,
.ruta). Del GPX que sube un invitado solo se guarda la ruta ya simplificada y
su perfil; el fichero original no se guarda.
"""
import hashlib, json, os, re, secrets, tempfile, threading
from datetime import date, datetime, timedelta
from hmac import compare_digest

USUARIO_RE = re.compile(r"^[a-z0-9]{3,20}$")
ID_RE = re.compile(r"^[0-9a-f]{12}$")
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"      # sin I, L, O, 0, 1: no se confunden al copiarlas
MAX_USUARIOS = 20
MAX_RUTAS = 5
MAX_AVIT = 30
MARGEN_DIAS = 7                                   # tras caducar, los datos se borran a los 7 días
MAX_GPX = 8_000_000                               # bytes

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
    if not USUARIO_RE.match(usuario) or usuario == "admin":
        raise ValueError("el usuario son 3 a 20 letras minúsculas o números, sin espacios")
    return usuario


def _dias(dias):
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        raise ValueError("los días tienen que ser un número")
    if not 1 <= dias <= 365:
        raise ValueError("de 1 a 365 días")
    return dias


# ---- usuarios (los gestiona el dueño desde el panel) ----

def crear(raiz, usuario, dias=30, nombre=""):
    """Devuelve el código (solo se ve ahora: en disco queda su hash)."""
    usuario, dias = _usuario_valido(usuario), _dias(dias)
    with _lock:
        todos = _usuarios(raiz)
        if usuario in todos:
            raise ValueError("ese usuario ya existe")
        if len(todos) >= MAX_USUARIOS:
            raise ValueError(f"ya hay {MAX_USUARIOS} invitados: quita alguno")
        codigo, sal = _codigo_nuevo(), os.urandom(16)
        todos[usuario] = {"nombre": re.sub(r"[\x00-\x1f]", "", str(nombre or usuario))[:40].strip() or usuario,
                          "hash": f"scrypt:{sal.hex()}:{_hash(_normal(codigo), sal)}",
                          "caduca": (date.today() + timedelta(days=dias)).isoformat(),
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
             "rutas": len(_ids(raiz, u))} for u, r in sorted(_usuarios(raiz).items())]


def activo(raiz, usuario):
    """El registro del invitado si existe y no ha caducado; si no, None."""
    r = _usuarios(raiz).get(str(usuario))
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
        todos = _usuarios(raiz)
        viejos = [u for u, r in todos.items() if r["caduca"] < limite]
        for u in viejos:
            del todos[u]
            _borrar_carpeta(raiz, u)
        if viejos:
            _guardar(raiz, todos)
        # carpetas de usuarios que ya no existen (por si algo se quedó a medias)
        base = _dir(raiz)
        if os.path.isdir(base):
            for n in os.listdir(base):
                if os.path.isdir(os.path.join(base, n)) and n not in todos:
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


def _resumen(r):
    return {"id": r["id"], "nombre": r["nombre"], "creada": r["creada"], "distancia_km": r["distancia_km"],
            "desnivel_m": r["desnivel_m"], "avituallamientos": len(r["avituallamientos"])}


def _detalle(r):
    """Lo que ve el invitado: sin las coordenadas completas (pesan) y con un perfil ligero."""
    perfil = r["perfil"]
    paso = max(1, len(perfil) // 150)
    return dict(_resumen(r), avituallamientos=r["avituallamientos"], subidas=r["subidas"], perfil=perfil[::paso])


def rutas(raiz, usuario):
    out = []
    for i in _ids(raiz, usuario):
        r = _leer(_ruta_path(raiz, usuario, i), None)
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
         "perfil": [[p["d"], p["ele"]] for p in perfil], "avituallamientos": [], "subidas": subidas}
    with _lock:
        if len(_ids(raiz, usuario)) >= MAX_RUTAS:
            raise ValueError(f"ya tienes {MAX_RUTAS} rutas: borra alguna para subir otra")
        _escribir(_ruta_path(raiz, usuario, r["id"]), r)
    return _detalle(r)


def ruta(raiz, usuario, id_):
    r = _leer(_ruta_path(raiz, usuario, id_), None)
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


def guardar_ruta(raiz, usuario, id_, nombre=None, avituallamientos=None):
    with _lock:
        p = _ruta_path(raiz, usuario, id_)
        r = _leer(p, None)
        if not r:
            return None
        if nombre is not None:
            r["nombre"] = _texto(nombre, 60) or r["nombre"]
        if avituallamientos is not None:
            r["avituallamientos"] = limpiar_avit(avituallamientos, r["distancia_km"])
        _escribir(p, r)
        return _detalle(r)


def borrar_ruta(raiz, usuario, id_):
    with _lock:
        p = _ruta_path(raiz, usuario, id_)
        if not os.path.exists(p):
            return False
        os.remove(p)
        return True


def gpx_reloj(raiz, usuario, id_, generar):
    """El GPX para el reloj de una ruta suya. `generar` es gpx_reloj.generar."""
    r = _leer(_ruta_path(raiz, usuario, id_), None)
    if not r:
        return None, None
    return r["nombre"], generar(r["nombre"], r["coords"], r["perfil"], r["avituallamientos"], r["subidas"])
