#!/usr/bin/env python3
"""Avisos de subidas, cimas y último km en el iPhone del CORREDOR (Web Push, con la web instalada) — v1.56.

La app de Android lanza esos avisos ella sola, sin cobertura. En iPhone no hay app: con Traccar mandando la posición, el
servidor ve en qué kilómetro de la ruta va el corredor y, al llegar a cada aviso del plan, manda una notificación SOLO a
sus móviles (la Band la repite como cualquier otra). Solo llega con cobertura. Distinto de avisos_web (campana): ese avisa
de salida, avituallamientos y meta a todos los seguidores.

Ficheros ocultos (no se sirven; la réplica los lleva a la otra Pi): .push_corredor.json ({identificador: [suscripciones]})
y .push_corredor_estado.json (por identificador: carrera, avisos ya enviados y último km). Los envíos los hace avisos_web."""
import json, math, time

SUBS, ESTADO = ".push_corredor.json", ".push_corredor_estado.json"
MAX_IDENT, MAX_POR_IDENT = 100, 3
FRESCO_S = 180                       # solo con una posición de hace menos de 3 min
_cum_cache = {}


def alta(root, av, ident, sub):
    """Guarda la suscripción de ESTE móvil para ese corredor. `av` es la herramienta avisos_web."""
    if not ident or not av.valida(sub):
        return False
    d = av._leer(root, SUBS, {})
    if ident not in d and len(d) >= MAX_IDENT:
        return False
    nuevas = [s for s in d.get(ident, []) if s.get("endpoint") != sub["endpoint"]] + [{"endpoint": sub["endpoint"], "keys": sub["keys"]}]
    d[ident] = nuevas[-MAX_POR_IDENT:]
    av._escribir(root, SUBS, d)
    return True


def baja(root, av, ident, endpoint):
    d = av._leer(root, SUBS, {})
    if ident in d:
        d[ident] = [s for s in d[ident] if s.get("endpoint") != endpoint]
        if not d[ident]:
            del d[ident]
        av._escribir(root, SUBS, d)


def _km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    return 2 * 6371 * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


def _acumulados(coords):
    k = (len(coords), tuple(coords[0][:2]), tuple(coords[-1][:2]))
    if k not in _cum_cache:
        a = [0.0]
        for p, q in zip(coords, coords[1:]):
            a.append(a[-1] + _km((p[1], p[0]), (q[1], q[0])))
        _cum_cache.clear()
        _cum_cache[k] = a
    return _cum_cache[k]


def km_en_ruta(coords, lat, lon, desde=0.0):
    """Km de la ruta del punto, siempre hacia delante (ventana desde el último km), o None si va a más de 150 m."""
    cum = _acumulados(coords)
    mejor, mk = 1e9, None
    for j, p in enumerate(coords):
        if cum[j] < desde - 0.5:
            continue
        if cum[j] > desde + 8:
            break
        d = _km((lat, lon), (p[1], p[0]))
        if d < mejor:
            mejor, mk = d, cum[j]
    return mk if mejor < 0.15 else None


def _id(a):
    return str(a.get("id") if a.get("id") is not None else f"{a.get('tipo')}{a.get('km')}")


def _enviar_si_toca(root, av, estado, ident, clave_carrera, avisos, km_ahora, subs):
    """Los avisos del plan a los que ya ha llegado: se manda el último que sigue vigente; los de antes se dan por pasados."""
    est = estado.get(ident) if (estado.get(ident) or {}).get("carrera") == clave_carrera else {"carrera": clave_carrera, "enviados": []}
    hechos = set(est.get("enviados", []))
    llegados = [a for a in avisos if isinstance(a.get("km"), (int, float)) and a["km"] <= km_ahora]
    vigentes = [a for a in llegados if km_ahora <= a.get("valido_hasta", a["km"] + 0.5) and _id(a) not in hechos]
    est["enviados"] = sorted(hechos | {_id(a) for a in llegados})
    est["km"] = km_ahora
    estado[ident] = est
    if not vigentes:
        return 0
    a = sorted(vigentes, key=lambda x: x["km"])[-1]
    texto = str(a.get("texto") or "").strip()
    if texto:
        caducadas = av.enviar(subs, {"title": "Sígueme CC", "body": texto, "tag": "subida-" + _id(a), "url": "/"})
        if caducadas:
            d = av._leer(root, SUBS, {})
            d[ident] = [s for s in d.get(ident, []) if s.get("endpoint") not in caducadas]
            av._escribir(root, SUBS, d)
        return 1
    return 0


def revisar(root, av, live, plan, ruta, clave_dueno, dm, ahora=None):
    """Cada pocos segundos, solo la Pi con la VIP. Devuelve cuántos avisos ha mandado (para las pruebas)."""
    ahora = ahora or time.time()
    subs = av._leer(root, SUBS, {})
    if not subs or not av.clave_publica():
        return 0
    estado = av._leer(root, ESTADO, {})
    antes = json.dumps(estado, sort_keys=True)
    enviados = 0
    # la carrera del dueño: su identificador es la clave del GPS
    ult = live.get("gps_ult") or []
    if clave_dueno in subs and live.get("started_at") and not live.get("finished_at") and len(ult) == 3 and ahora - ult[2] < FRESCO_S:
        try:
            coords = ruta["features"][0]["geometry"]["coordinates"]
        except (KeyError, IndexError, TypeError):
            coords = []
        if len(coords) > 1:
            k = km_en_ruta(coords, ult[0], ult[1], (estado.get(clave_dueno) or {}).get("km", 0.0))
            if k is not None:
                enviados += _enviar_si_toca(root, av, estado, clave_dueno, "dueno:" + str(live.get("started_at")), (plan or {}).get("avisos", []), k, subs[clave_dueno])
    # las carreras en directo de varios corredores: el km de cada uno ya lo lleva su estado
    for id_ in (dm._ids(root) if dm else []):
        c = dm.carrera(root, id_)
        for co in (c or {}).get("corredores", []):
            if co["ident"] not in subs:
                continue
            st = dm.estado(root, id_, co["cid"])
            u = st.get("ult") or []
            if st.get("salida_real") and not st.get("llegada") and len(u) == 3 and ahora - u[2] < FRESCO_S:
                enviados += _enviar_si_toca(root, av, estado, co["ident"], "dir:" + id_, (c.get("plan") or {}).get("avisos", []), st.get("km", 0.0), subs[co["ident"]])
    if json.dumps(estado, sort_keys=True) != antes:
        av._escribir(root, ESTADO, estado)
    return enviados
