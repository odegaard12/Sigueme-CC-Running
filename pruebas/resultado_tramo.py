"""Resultado de la carrera: tiempo en movimiento, desnivel y pulso salen SOLO del tramo salida-meta, aunque el reloj
grabara calentamiento y vuelta. Carrera y GPX inventados (10 km al norte, 1 h)."""
import json, pathlib, sys, tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'herramientas'))
import generar_resultado as gr

KM_LAT = 111.19            # km por grado de latitud
LON = -4.0
LAT0 = 40.0
resultados = []


def ok(cond, texto):
    resultados.append(bool(cond))
    print(('OK   ' if cond else 'MAL  ') + texto)


def lat_en(km):
    return LAT0 + km / KM_LAT


with tempfile.TemporaryDirectory() as t:
    raiz = pathlib.Path(t)
    (raiz / 'carrera.json').write_text(json.dumps({'nombre': 'Prueba', 'fecha': '2026-10-24', 'hora_salida': '10:00',
                                                   'zona_horaria': 'UTC', 'distancia_km': 10.0}), encoding='utf-8')
    coords = [[LON, lat_en(k / 10)] for k in range(0, 101)]
    (raiz / 'route.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': coords}}]}), encoding='utf-8')
    (raiz / 'aid_stations.json').write_text('[]', encoding='utf-8')

    pts = []
    t0 = datetime(2026, 10, 24, 9, 40, tzinfo=timezone.utc)
    # 20 min parado en la salida (pulso 90, altura 100)
    for i in range(0, 1200, 10):
        pts.append((t0 + timedelta(seconds=i), 0.0, 100.0, 90))
    # 1 h de carrera a 10 km/h, subiendo 300 m (pulso 160)
    for i in range(0, 3601, 10):
        km = 10 * i / 3600
        pts.append((datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc) + timedelta(seconds=i), km, 100.0 + 300 * i / 3600, 160))
    # 30 min de vuelta andando hacia la salida, bajando (pulso 100)
    for i in range(10, 1801, 10):
        pts.append((datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc) + timedelta(seconds=i), 10 - 5 * i / 3600, 400.0 - 150 * i / 1800, 100))
    gpx = '<?xml version="1.0"?><gpx version="1.1"><trk><trkseg>' + ''.join(
        f'<trkpt lat="{lat_en(km):.6f}" lon="{LON}"><ele>{ele:.1f}</ele><time>{h.strftime("%Y-%m-%dT%H:%M:%SZ")}</time>'
        f'<extensions><gpxtpx:TrackPointExtension xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"><gpxtpx:hr>{hr}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions></trkpt>'
        for h, km, ele, hr in pts) + '</trkseg></trk></gpx>'
    r = gr.generar(gpx.encode(), raiz)

    ok(abs(r['tiempo_oficial_s'] - 3600) <= 30, f"tiempo oficial ≈ 1 h ({r['tiempo_oficial_s']} s)")
    ok(abs(r['distancia_km'] - 10.0) < 0.3, f"distancia ≈ 10 km ({r['distancia_km']})")
    ok(r['pulso_medio'] is not None and 156 <= r['pulso_medio'] <= 164, f"pulso medio solo de la carrera ({r['pulso_medio']}, no el de calentamiento y vuelta)")
    ok(r['desnivel_m'] is not None and 270 <= r['desnivel_m'] <= 320, f"desnivel solo de la carrera ({r['desnivel_m']} m)")
    ok(3400 <= r['tiempo_movimiento_s'] <= 3700, f"tiempo en movimiento solo de la carrera ({r['tiempo_movimiento_s']} s)")
    ok(r['velocidad_media_mov'] is not None and 9.3 <= r['velocidad_media_mov'] <= 10.7, f"velocidad media en movimiento ≈ 10 km/h ({r['velocidad_media_mov']})")

print('\nTODO BIEN' if all(resultados) else f'\nFALLOS: {resultados.count(False)}')
sys.exit(0 if all(resultados) else 1)
