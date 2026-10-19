#!/usr/bin/env python3
"""Ruta + avituallamientos + subidas -> un GPX para importar en el reloj
(Huawei Health, Zepp, Garmin, Coros...): el trazado con su altitud y, como
puntos de control, los avituallamientos y el principio y la cima de cada subida.

Desde la consola (en la carpeta de la web):
    python herramientas/gpx_reloj.py > ruta-reloj.gpx
"""
import bisect, json, math, os, sys
from xml.sax.saxutils import escape


def _km(a, b):
    """Distancia en km entre dos puntos [lon, lat] (haversine)."""
    f1, f2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((f2 - f1) / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _coma(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",")


def generar(nombre, coords, perfil, avituallamientos=(), subidas=()):
    """coords: [[lon, lat], ...]; perfil: [[km, altitud_m], ...] (el de elevation.json)."""
    if len(coords) < 2:
        raise ValueError("la ruta no tiene puntos")
    acum = [0.0]
    for a, b in zip(coords, coords[1:]):
        acum.append(acum[-1] + _km(a, b))
    # la ruta del mapa va simplificada: se reparte para que el km final sea el del perfil
    total = perfil[-1][0] if perfil else acum[-1]
    esc = (total / acum[-1]) if acum[-1] else 1
    km = [x * esc for x in acum]
    pd = [p[0] for p in perfil]

    def altitud(k):
        if not perfil:
            return None
        i = bisect.bisect_left(pd, k)
        if i <= 0:
            return perfil[0][1]
        if i >= len(perfil):
            return perfil[-1][1]
        (d0, e0), (d1, e1) = perfil[i - 1], perfil[i]
        return e0 + (e1 - e0) * ((k - d0) / (d1 - d0) if d1 > d0 else 0)

    def punto(k):
        i = min(max(bisect.bisect_left(km, k), 1), len(km) - 1)
        t = (k - km[i - 1]) / (km[i] - km[i - 1]) if km[i] > km[i - 1] else 0
        t = min(max(t, 0), 1)
        a, b = coords[i - 1], coords[i]
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t

    def wpt(k, nom, desc, tipo):
        lon, lat = punto(k)
        e = altitud(k)
        return (f'<wpt lat="{lat:.6f}" lon="{lon:.6f}">' + (f"<ele>{e:.1f}</ele>" if e is not None else "") +
                f"<name>{escape(nom)}</name><desc>{escape(desc)}</desc><type>{tipo}</type></wpt>")

    puntos = []
    for a in sorted(avituallamientos, key=lambda x: x["km"]):
        puntos.append(wpt(a["km"], str(a["name"])[:24], f"Km {_coma(a['km'])}", "Avituallamiento"))
    for s in subidas:
        puntos.append(wpt(s["inicio"], f"Sube {s['n']} +{round(s['desnivel_m'])}m",
                          f"Km {_coma(s['inicio'])} · {_coma(s['largo_km'], 2)} km · {_coma(s['pendiente'])} %", "Subida"))
        puntos.append(wpt(s["fin"], f"Cima {s['n']}", f"Km {_coma(s['fin'])}", "Cima"))
    traza = []
    for (lon, lat), k in zip(coords, km):
        e = altitud(k)
        traza.append(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}">' + (f"<ele>{e:.1f}</ele>" if e is not None else "") + "</trkpt>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="Sigueme CC" xmlns="http://www.topografix.com/GPX/1/1">\n'
            f"<metadata><name>{escape(nombre)}</name></metadata>\n" + "\n".join(puntos) +
            f"\n<trk><name>{escape(nombre)}</name><trkseg>\n" + "\n".join(traza) + "\n</trkseg></trk>\n</gpx>\n")


def desde_ficheros(raiz="."):
    def leer(n, defecto):
        try:
            with open(os.path.join(raiz, n), encoding="utf-8-sig") as f:
                return json.load(f)
        except (OSError, ValueError):
            return defecto
    ruta = leer("route.geojson", {})
    try:
        coords = ruta["features"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("falta la ruta: sube antes el GPX")
    perfil = [[p["d"], p["ele"]] for p in leer("elevation.json", {}).get("profile", [])]
    plan = leer("avisos.json", {}) or {}
    nombre = (leer("carrera.json", {}) or {}).get("nombre") or "Ruta"
    return generar(nombre, coords, perfil, leer("aid_stations.json", []) or [], plan.get("subidas", []))


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(desde_ficheros(".").encode("utf-8"))
    except ValueError as e:
        sys.exit(str(e))
