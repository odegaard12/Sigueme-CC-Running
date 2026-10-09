# -*- coding: utf-8 -*-
"""Prepara la ruta de una carrera desde un GPX (el que da la organización o el
que exportas de Strava, Komoot, Wikiloc…).

    python herramientas/preparar_ruta.py ruta.gpx [--nombre "Mi carrera"] [--distancia 103.4]

Escribe en la raíz del proyecto:
  route.geojson   el trazado (simplificado a ~1.800 puntos, suficiente para el mapa)
  elevation.json  el perfil y las pendientes

--distancia: los km OFICIALES si no coinciden con los del GPX (la web escala
los km de la ruta para que la meta caiga en esa cifra).

Después: pon los avituallamientos en aid_stations.json y revisa carrera.json.
Solo usa la biblioteca estándar."""
import argparse, json, math, pathlib, sys
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MAX_PUNTOS = 1800
UMBRAL_DESNIVEL = 3.0     # m: por debajo es ruido del GPS/barómetro y no suma desnivel


def km_entre(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def leer_gpx(ruta):
    """[(lat, lon, ele|None)] de los <trkpt> (o <rtept> si no hay track)."""
    raiz = ET.parse(ruta).getroot()
    puntos = [e for e in raiz.iter() if e.tag.rsplit('}', 1)[-1] == 'trkpt'] or \
             [e for e in raiz.iter() if e.tag.rsplit('}', 1)[-1] == 'rtept']
    salida = []
    for p in puntos:
        ele = next((h.text for h in p if h.tag.rsplit('}', 1)[-1] == 'ele'), None)
        salida.append((float(p.get('lat')), float(p.get('lon')), float(ele) if ele else None))
    return salida


def desnivel(eles):
    """Subida y bajada con histéresis: solo cuentan los cambios > UMBRAL."""
    sube = baja = 0.0
    ref = eles[0]
    for e in eles[1:]:
        if e - ref >= UMBRAL_DESNIVEL:
            sube += e - ref; ref = e
        elif ref - e >= UMBRAL_DESNIVEL:
            baja += ref - e; ref = e
    return round(sube), round(baja)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('gpx')
    ap.add_argument('--nombre', default='Ruta')
    ap.add_argument('--distancia', type=float, help='km oficiales (si no, los del GPX)')
    a = ap.parse_args()

    pts = leer_gpx(a.gpx)
    if len(pts) < 2:
        sys.exit('El GPX no tiene puntos de track ni de ruta.')
    cum = [0.0]
    for p, q in zip(pts, pts[1:]):
        cum.append(cum[-1] + km_entre(p, q))
    largo = cum[-1]
    oficial = a.distancia or round(largo, 2)
    factor = oficial / largo

    # elevación: si faltan datos en algún punto, se rellena con el anterior
    eles, ultima = [], None
    for p in pts:
        ultima = p[2] if p[2] is not None else ultima
        eles.append(ultima)
    con_ele = any(e is not None for e in eles)
    if con_ele:
        primera = next(e for e in eles if e is not None)
        eles = [primera if e is None else e for e in eles]
    sube, baja = desnivel(eles) if con_ele else (0, 0)

    # puntos repartidos por igual, siempre con el primero y el último
    m = min(len(pts), MAX_PUNTOS)
    idx = sorted({round(i * (len(pts) - 1) / (m - 1)) for i in range(m)})
    ruta = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {
        'name': a.nombre, 'distance_km': oficial, 'elevation_gain_m': sube, 'elevation_loss_m': baja,
        'points_original': len(pts), 'points_simplified': len(idx)},
        'geometry': {'type': 'LineString', 'coordinates': [[round(pts[i][1], 6), round(pts[i][0], 6)] for i in idx]}}]}
    (RAIZ / 'route.geojson').write_text(json.dumps(ruta, ensure_ascii=False), encoding='utf-8')

    perfil, grads = [], []
    if con_ele:
        tramo = max(0.05, oficial / 1300)          # un punto cada ~80 m en 100 km
        d, j = 0.0, 0
        while d <= oficial + 1e-9:
            while j < len(cum) - 2 and cum[j + 1] * factor < d:
                j += 1
            t = (d - cum[j] * factor) / (((cum[j + 1] - cum[j]) * factor) or 1e-9)
            e = eles[j] + max(0.0, min(1.0, t)) * (eles[j + 1] - eles[j])
            g = 0.0 if not perfil else (e - perfil[-1]['ele']) / ((d - perfil[-1]['d']) * 1000 or 1e-9) * 100
            perfil.append({'d': round(d, 2), 'ele': round(e, 1), 'grad': round(g, 1)})
            grads.append(g)
            d += tramo
    subidas = [g for g in grads if g > 0.5]
    elev = {'distance_km': oficial, 'elevation_gain_m': sube, 'elevation_loss_m': baja,
            'max_grad_pct': round(max(grads, default=0), 1), 'min_grad_pct': round(min(grads, default=0), 1),
            'avg_up_grad_pct': round(sum(subidas) / len(subidas), 1) if subidas else 0,
            'min_ele_m': round(min(eles), 0) if con_ele else 0, 'max_ele_m': round(max(eles), 0) if con_ele else 0,
            'profile': perfil}
    (RAIZ / 'elevation.json').write_text(json.dumps(elev, ensure_ascii=False), encoding='utf-8')

    print(f'{len(pts)} puntos en el GPX · {largo:.2f} km medidos · {oficial} km oficiales')
    print(f'route.geojson: {len(idx)} puntos · elevation.json: {len(perfil)} puntos de perfil, +{sube} m / -{baja} m')
    if not con_ele:
        print('⚠ El GPX no trae elevación: el perfil saldrá plano.')
    print(f'Pon en carrera.json: "distancia_km": {oficial}, "desnivel_m": {sube}')


if __name__ == '__main__':
    main()
