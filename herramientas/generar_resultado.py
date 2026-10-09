# -*- coding: utf-8 -*-
"""resultado.json a partir del FIT del 26/09: tiempos, pasos por
avituallamiento y la traza real recortada a salida-meta."""
import json, math, pathlib, sys
from datetime import datetime, timezone
import fitdecode

# la web (route.geojson, aid_stations.json, resultado.json) está en la raíz del repo
AQUI = pathlib.Path(__file__).resolve().parent.parent
if len(sys.argv) != 2:
    sys.exit('uso: python herramientas/generar_resultado.py actividad.fit')
FIT = pathlib.Path(sys.argv[1])
SC = 180 / 2 ** 31
SALIDA_OFICIAL = datetime(2026, 9, 26, 6, 30, tzinfo=timezone.utc)   # 08:30


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


# ruta tal como la usa la web (route.geojson) y avituallamientos
ruta = [(c[1], c[0]) for c in json.loads((AQUI / 'route.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates']]
cum = [0.0]
for a, b in zip(ruta, ruta[1:]):
    cum.append(cum[-1] + hav(a, b))
TOTAL_OFICIAL = 103.36
factor = TOTAL_OFICIAL / cum[-1]
avis = json.loads((AQUI / 'aid_stations.json').read_text(encoding='utf-8-sig'))


def punto_en_km(k):
    for i in range(len(cum) - 1):
        if cum[i + 1] >= k:
            t = (k - cum[i]) / ((cum[i + 1] - cum[i]) or 1e-9)
            return (ruta[i][0] + t * (ruta[i + 1][0] - ruta[i][0]), ruta[i][1] + t * (ruta[i + 1][1] - ruta[i][1]))
    return ruta[-1]


recs, sesion = [], {}
with fitdecode.FitReader(str(FIT)) as fr:
    for f in fr:
        if isinstance(f, fitdecode.FitDataMessage):
            d = {x.name: x.value for x in f.fields}
            if f.name == 'record' and d.get('position_lat') is not None:
                recs.append((d['timestamp'], d['position_lat'] * SC, d['position_long'] * SC))
            elif f.name == 'session':
                sesion = d

# km de ruta de cada punto, siempre hacia delante (como la web)
km, kms = 0.0, []
for _, la, lo in recs:
    mejor, mk = 1e9, km
    for j in range(len(ruta)):
        if cum[j] < km - 0.5 or cum[j] > km + 8:
            continue
        dd = hav((la, lo), ruta[j])
        if dd < mejor:
            mejor, mk = dd, cum[j]
    if mejor < 0.15:
        km = max(km, mk)
    kms.append(km)

salida_pt, meta_pt = ruta[0], ruta[-1]
# salida: primer punto a las 08:30 o después que ya se aleja de la línea
i0 = next(i for i, (t, la, lo) in enumerate(recs) if t >= SALIDA_OFICIAL)
# meta: punto más cercano a meta en el último tramo (km de ruta > 100)
finales = [i for i in range(len(recs)) if kms[i] > 100]
i1 = min(finales, key=lambda i: hav(recs[i][1:], meta_pt))
llegada = recs[i1][0]
print('salida', recs[i0][0], '· llegada', llegada, f'a {hav(recs[i1][1:], meta_pt) * 1000:.0f} m de meta')

tramo = recs[i0:i1 + 1]
dist = sum(hav(a[1:], b[1:]) for a, b in zip(tramo, tramo[1:]))

# pasos por avituallamiento: momento de máxima cercanía a la chincheta
pasos, desde = [], i0
for s in avis:
    pin = punto_en_km(s['km'])
    candidatos = [i for i in range(desde, i1 + 1) if abs(kms[i] - s['km']) < 3]
    if not candidatos:
        continue
    i = min(candidatos, key=lambda k: hav(recs[k][1:], pin))
    if hav(recs[i][1:], pin) > 0.3:
        continue
    pasos.append({'nombre': s['name'], 'km': s['km'], 'hora': recs[i][0].isoformat(),
                  'principal': bool(s.get('principal')), 'taller': bool(s.get('taller'))})
    desde = i

# traza cada 20 s (hora relativa a la salida oficial)
traza, ultimo = [], None
for t, la, lo in tramo:
    if ultimo is None or (t - ultimo).total_seconds() >= 20:
        traza.append([round(la, 5), round(lo, 5), int((t - SALIDA_OFICIAL).total_seconds())])
        ultimo = t
traza.append([round(meta_pt[0], 5), round(meta_pt[1], 5), int((llegada - SALIDA_OFICIAL).total_seconds())])

mov = sesion.get('total_timer_time') or 0
res = {
    'carrera': 'Mi carrera MTB',
    'salida': SALIDA_OFICIAL.isoformat(),
    'llegada': llegada.isoformat(),
    'tiempo_oficial_s': int((llegada - SALIDA_OFICIAL).total_seconds()),
    'tiempo_movimiento_s': int(mov),
    'distancia_km': round(dist, 1),
    'desnivel_m': sesion.get('total_ascent'),
    'pulso_medio': sesion.get('avg_heart_rate'),
    'cadencia_media': sesion.get('avg_cadence'),
    'velocidad_media_mov': round(dist / (mov / 3600), 1) if mov else None,
    'pasos': pasos,
    'traza': traza,
}
(AQUI / 'resultado.json').write_text(json.dumps(res, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
h, m = divmod(res['tiempo_oficial_s'] // 60, 60)
print(f"tiempo oficial {h}h {m:02d}m · {res['distancia_km']} km · media en movimiento {res['velocidad_media_mov']} km/h")
print(f"pasos por avituallamiento: {len(pasos)} de {len(avis)} · traza {len(traza)} puntos · "
      f"{(AQUI / 'resultado.json').stat().st_size // 1024} KB")
for p in pasos:
    print(f"   {p['hora'][11:16]} UTC  km {p['km']:5}  {p['nombre']}")
