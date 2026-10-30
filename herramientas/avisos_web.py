"""Avisos en el móvil de quien sigue la carrera (Web Push, también en el iPhone con la web instalada).

Quien pulsa la campana en la página de la carrera deja aquí su suscripción. Cada pocos segundos, solo la Pi que tiene
la VIP mira live.json y, si pasa algo nuevo (salida, cada avituallamiento, meta), lo manda. El envío lo hace
enviar_push.py con pywebpush desde su propio entorno (~/sigueme-push/.venv): el servidor sigue sin dependencias y,
si falta ese entorno o las claves, los avisos quedan apagados y la campana no sale.

Ficheros ocultos (no se sirven; la réplica los lleva a la otra Pi): .push_subs.json (suscripciones) y .push_estado.json
(lo ya enviado en esta carrera)."""
import json, os, subprocess, tempfile, time
from urllib.parse import urlparse

DIR = os.environ.get("SIGUEME_PUSH_DIR", os.path.expanduser("~/sigueme-push"))
PY = os.path.join(DIR, ".venv", "bin", "python")
PEM = os.path.join(DIR, "vapid_private.pem")
PUB = os.path.join(DIR, "vapid_public.txt")
ENVIAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enviar_push.py")
SUBS, ESTADO = ".push_subs.json", ".push_estado.json"
MAX_SUBS = 500
# solo servicios de avisos de verdad (si no, la Pi haría peticiones a donde dijera cualquiera)
HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com", "notify.windows.com", "push.services.mozilla.com")


def clave_publica():
    """La clave VAPID pública, o None si los avisos no están montados en esta Pi."""
    try:
        if not (os.path.exists(PY) and os.path.exists(PEM)):
            return None
        with open(PUB, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _leer(root, nombre, defecto):
    try:
        with open(os.path.join(root, nombre), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def _escribir(root, nombre, datos):
    fd, tmp = tempfile.mkstemp(dir=root, prefix="." + nombre + ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, os.path.join(root, nombre))


def valida(sub):
    """Una suscripción del navegador con buena pinta: endpoint https de un servicio de avisos y sus dos claves."""
    if not isinstance(sub, dict):
        return False
    url, keys = sub.get("endpoint"), sub.get("keys")
    if not isinstance(url, str) or len(url) > 1000 or not isinstance(keys, dict):
        return False
    u = urlparse(url)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not any(host == h or host.endswith("." + h) for h in HOSTS):
        return False
    return all(isinstance(keys.get(k), str) and 0 < len(keys[k]) <= 200 for k in ("p256dh", "auth"))


def alta(root, sub):
    if not valida(sub):
        return False
    subs = [s for s in _leer(root, SUBS, []) if s.get("endpoint") != sub["endpoint"]]
    subs.append({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"]}, "t": int(time.time())})
    _escribir(root, SUBS, subs[-MAX_SUBS:])
    return True


def baja(root, endpoint):
    subs = _leer(root, SUBS, [])
    _escribir(root, SUBS, [s for s in subs if s.get("endpoint") != endpoint])


def km(v):
    return str(round(v, 1)).replace(".", ",")


def eventos(live, avit, nombre):
    """Lo que ya ha pasado en esta carrera, en orden: [(id, título, texto)]."""
    if not live.get("started_at"):
        return []
    nombre = nombre or "La carrera"
    ev = [("salida", nombre, "¡Salida! Ya está corriendo. Toca para seguirla en directo.")]
    hecho = live.get("dist_km") or 0
    for i, a in enumerate(avit or []):
        try:
            k = float(a.get("km"))
        except (TypeError, ValueError):
            continue
        if hecho >= k:
            ev.append((f"avit{i}", nombre, f"Pasa por el avituallamiento {i + 1}" + (f" ({a['name']})" if a.get("name") else "") + f", km {km(k)}."))
    if live.get("finished_at"):
        ev.append(("meta", nombre, "¡En meta! Toca para ver el tiempo y la repetición."))
    return ev


def pendientes(live, avit, nombre, estado):
    """Lo nuevo desde el último aviso. Si se juntan varios (servicio reiniciado a mitad), solo el último: sin ráfagas."""
    carrera = live.get("started_at") or ""
    hechos = set(estado.get("enviados", [])) if estado.get("carrera") == carrera else set()
    nuevos = [e for e in eventos(live, avit, nombre) if e[0] not in hechos]
    return carrera, hechos, nuevos[-1:] if len(nuevos) > 1 else nuevos


def revisar(root, live, avit, nombre):
    """Llamado cada pocos segundos por la Pi titular."""
    if not live.get("started_at") or not clave_publica():
        return
    estado = _leer(root, ESTADO, {})
    carrera, hechos, nuevos = pendientes(live, avit, nombre, estado)
    if not nuevos:
        return
    # se apunta ANTES de enviar: si el envío falla a medias, no se repite en bucle cada 15 s
    _escribir(root, ESTADO, {"carrera": carrera, "enviados": sorted(hechos | {e[0] for e in eventos(live, avit, nombre)})})
    subs = _leer(root, SUBS, [])
    if not subs:
        return
    _id, titulo, texto = nuevos[0]
    caducadas = enviar(subs, {"title": titulo, "body": texto, "tag": "carrera-" + _id, "url": "/"})
    if caducadas:
        _escribir(root, SUBS, [s for s in _leer(root, SUBS, []) if s.get("endpoint") not in caducadas])


def enviar(subs, datos):
    """Manda el aviso a todos; devuelve los endpoints caducados (el navegador se dio de baja) para borrarlos."""
    try:
        r = subprocess.run([PY, ENVIAR, PEM], input=json.dumps({"subs": subs, "data": datos}), capture_output=True,
                           text=True, timeout=120)
        salida = json.loads(r.stdout or "{}")
        print(f"[avisos] enviados {salida.get('ok', 0)} de {len(subs)} · {datos['body'][:60]}", flush=True)
        return set(salida.get("caducadas", []))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"[avisos] no se pudo enviar: {exc}", flush=True)
        return set()


if __name__ == "__main__":
    # comprobación rápida de la lógica (sin enviar nada)
    av = [{"km": 5, "name": "Collado"}, {"km": 14}]
    assert eventos({}, av, "X") == []
    assert [e[0] for e in eventos({"started_at": "t", "dist_km": 6}, av, "X")] == ["salida", "avit0"]
    c, h, n = pendientes({"started_at": "t", "dist_km": 15}, av, "X", {})
    assert [e[0] for e in n] == ["avit1"], n                       # tres pendientes de golpe: solo el último
    c, h, n = pendientes({"started_at": "t", "dist_km": 15}, av, "X", {"carrera": "t", "enviados": ["salida", "avit0"]})
    assert [e[0] for e in n] == ["avit1"]
    c, h, n = pendientes({"started_at": "t2", "dist_km": 0}, av, "X", {"carrera": "t", "enviados": ["salida", "avit0", "avit1"]})
    assert [e[0] for e in n] == ["salida"]                          # carrera nueva: empieza de cero
    assert valida({"endpoint": "https://web.push.apple.com/abc", "keys": {"p256dh": "x", "auth": "y"}})
    assert not valida({"endpoint": "https://evil.example/abc", "keys": {"p256dh": "x", "auth": "y"}})
    assert not valida({"endpoint": "http://fcm.googleapis.com/abc", "keys": {"p256dh": "x", "auth": "y"}})
    d = tempfile.mkdtemp()
    s = {"endpoint": "https://fcm.googleapis.com/fcm/send/a", "keys": {"p256dh": "x", "auth": "y"}}
    assert alta(d, s) and alta(d, s) and len(_leer(d, SUBS, [])) == 1   # sin duplicados
    baja(d, s["endpoint"]); assert _leer(d, SUBS, []) == []
    print("avisos_web: TODO BIEN")
