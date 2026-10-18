"""GPX difíciles: ruido en la elevación, coma decimal, UTF-16 sin BOM."""
import pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'herramientas'))
import preparar_ruta as pr
random.seed(1)
def gpx(n, ruido, coma=False):
    pts = []
    for i in range(n):
        km = i * 0.003
        ele = min(km, 5) * 60 + random.gauss(0, ruido)
        e = f'{ele:.1f}'.replace('.', ',') if coma else f'{ele:.1f}'
        pts.append(f'<trkpt lat="{42 + km / 111.2:.6f}" lon="-8"><ele>{e}</ele></trkpt>')
    return ('<gpx><trk><trkseg>' + ''.join(pts) + '</trkseg></trk></gpx>').encode()
for r in (0, 1, 2):
    d = pr.preparar(gpx(3334, r))[2]['desnivel_m']
    print('ruido', r, d); assert 280 <= d <= 320, d
d = pr.preparar(gpx(200, 0, True))[2]['desnivel_m']
print('coma', d); assert d > 0
try:
    pr.preparar('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE g [<!ENTITY a "x">]><gpx/>'.encode('utf-16-le'))
    raise SystemExit('MAL: UTF-16 sin BOM aceptado')
except ValueError as e:
    print('utf16:', e)
print('TODO BIEN')
