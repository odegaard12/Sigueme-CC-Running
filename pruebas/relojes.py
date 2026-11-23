"""Banco de pruebas de relojes: sin tener cada reloj delante, comprueba con ficheros inventados al estilo de cada marca
(1) que el GPX de resultado que exporta cada app se lee bien (hora, pulso, altura, zonas horarias y rarezas de formato),
(2) que el GPX de ruta que generamos es válido para importar y no trae nombres ni puntos que den problemas, y
(3) que los textos de los avisos caben en la pantalla de un reloj.
Datos inventados; no necesita servidor."""
import math, pathlib, re, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'herramientas'))
import generar_resultado as gr
import gpx_reloj
import plan_avisos

resultados = []


def ok(cond, texto):
    resultados.append(bool(cond))
    print(('OK   ' if cond else 'MAL  ') + texto)


def info(texto):
    print('INFO ' + texto)


# ---------------------------------------------------------------- 1. resultado: cada marca exporta a su manera
N, T0 = 120, datetime(2026, 11, 23, 9, 0, 0, tzinfo=timezone.utc)
KM_LAT = 111.19


def puntos():
    """10 km al norte en 1 h: (segundos, lat, lon, altitud, pulso)."""
    return [(i * 30, 40.0 + (i * 30 / 3600 * 10) / KM_LAT, -4.0, 700 + 40 * math.sin(i / 8), 140 + i % 20) for i in range(N)]


def hora(t, estilo):
    h = T0 + timedelta(seconds=t)
    return {'z': h.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'ms': h.strftime('%Y-%m-%dT%H:%M:%S.') + '000Z',
            'siete': h.strftime('%Y-%m-%dT%H:%M:%S.') + '1234567Z',                                   # .NET: 7 decimales
            'offset': (h + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S') + '+01:00',
            'offset_sin_dos_puntos': (h + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S') + '+0100',
            'naive': h.strftime('%Y-%m-%dT%H:%M:%S')}[estilo]


def gpx(cabecera, ext, estilo='z', ele=True, hr=True, bom=False, trkseg_cada=None):
    cuerpo = []
    for i, (t, la, lo, e, h) in enumerate(puntos()):
        if trkseg_cada and i and i % trkseg_cada == 0:
            cuerpo.append('</trkseg><trkseg>')
        x = f'<trkpt lat="{la:.6f}" lon="{lo:.6f}">'
        if ele:
            x += f'<ele>{e:.1f}</ele>'
        x += f'<time>{hora(t, estilo)}</time>'
        if hr:
            x += ext.format(hr=h)
        cuerpo.append(x + '</trkpt>')
    s = cabecera + '<trk><name>Trail</name><trkseg>' + ''.join(cuerpo) + '</trkseg></trk></gpx>'
    return (b'\xef\xbb\xbf' if bom else b'') + s.encode('utf-8')


GPX11 = '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="{c}" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" xmlns:ns3="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">'
GPX10 = '<?xml version="1.0"?><gpx version="1.0" creator="{c}" xmlns="http://www.topografix.com/GPX/1/0">'
EXT_TPX = '<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{hr}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions>'
EXT_NS3 = '<extensions><ns3:TrackPointExtension><ns3:hr>{hr}</ns3:hr></ns3:TrackPointExtension></extensions>'
EXT_PLANA = '<extensions><hr>{hr}</hr></extensions>'
CASOS = [
    ('Garmin Connect (ns3, milisegundos)', gpx(GPX11.format(c='Garmin Connect'), EXT_NS3, 'ms'), True, True),
    ('Strava (gpxtpx, sin milisegundos)', gpx(GPX11.format(c='Strava'), EXT_TPX, 'z'), True, True),
    ('Huawei Health (pulso suelto en extensions)', gpx(GPX11.format(c='HUAWEI Health'), EXT_PLANA, 'z'), True, True),
    ('Zepp/Amazfit (hora con zona +01:00)', gpx(GPX11.format(c='Zepp'), EXT_TPX, 'offset'), True, True),
    ('Mi Fitness (GPX 1.0, offset +0100)', gpx(GPX10.format(c='Mi Fitness'), EXT_PLANA, 'offset_sin_dos_puntos'), True, True),
    ('Coros (varios trkseg por pausas)', gpx(GPX11.format(c='COROS'), EXT_TPX, 'ms', trkseg_cada=30), True, True),
    ('Polar Flow (BOM al principio)', gpx(GPX11.format(c='Polar Flow'), EXT_TPX, 'ms', bom=True), True, True),
    ('Suunto (7 decimales en la hora)', gpx(GPX11.format(c='Suunto'), EXT_TPX, 'siete'), True, True),
    ('reloj sin pulso ni altura', gpx(GPX11.format(c='Reloj básico'), '', 'z', ele=False, hr=False), False, False),
]
for nombre, datos, con_hr, con_ele in CASOS:
    try:
        recs, ses = gr._leer_gpx(datos)
    except Exception as exc:
        ok(False, f'{nombre}: no se pudo leer ({exc})')
        continue
    primero = recs[0][0] if recs else None
    esperado = T0 if 'offset' not in nombre and '+0100' not in nombre else T0
    ok(len(recs) == N and primero is not None and abs((primero - esperado).total_seconds()) < 1,
       f'{nombre}: {len(recs)} puntos, primera hora {primero.isoformat() if primero else "-"}')
    if con_hr:
        ok(ses.get('avg_heart_rate') and 140 <= ses['avg_heart_rate'] <= 160, f'{nombre}: pulso medio {ses.get("avg_heart_rate")}')
    if con_ele:
        ok(ses.get('total_ascent') is not None, f'{nombre}: desnivel {ses.get("total_ascent")} m')
    mov_min = ses['total_timer_time'] / 60
    ok(58 <= mov_min <= 61, f'{nombre}: tiempo en movimiento {mov_min:.1f} min (1 h inventada)')

# rarezas que deben dar un mensaje claro, no un fallo
for nombre, datos, texto in [
    ('GPX de ruta sin horas', gpx('<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">', '', 'z').replace(b'<time>', b'<t>').replace(b'</time>', b'</t>'), None),
    ('UTF-16', '<gpx/>'.encode('utf-16'), 'UTF-16'),
    ('con DOCTYPE', b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><gpx/>', 'DOCTYPE'),
    ('XML roto', b'<gpx><trk>', 'GPX'),
]:
    try:
        recs, ses = gr._leer_gpx(datos)
        ok(not recs, f'{nombre}: sin puntos con hora, lo trata sin romper ({len(recs)})')
    except ValueError as exc:
        ok(texto is None or texto.lower() in str(exc).lower(), f'{nombre}: rechazado con mensaje claro ({str(exc)[:60]})')
    except Exception as exc:
        ok(False, f'{nombre}: fallo inesperado {exc!r}')

# horas sin zona (algunos relojes escriben la hora local sin decir cuál): se leen como UTC, y lo dejamos dicho
r, _ = gr._leer_gpx(gpx(GPX11.format(c='x'), EXT_TPX, 'naive'))
info(f'una hora SIN zona se interpreta como UTC ({r[0][0].isoformat()}); si el reloj escribe hora local, el tramo salida-meta saldría desplazado')

# ---------------------------------------------------------------- 2. la ruta que generamos para el reloj
m = 400
coords = [[-8.1 + 0.00005 * i, 42.6 + 0.00004 * math.sin(i / 20) + 0.0001 * i] for i in range(m)]
perfil = [[i * 0.05, 300 + 120 * math.sin(i / 60)] for i in range(m)]
avit = [{'km': 5.0, 'name': 'Avituallamiento Puente de la Ermita del Santo'}, {'km': 12.0, 'name': 'Fonte'}]
subidas = [{'n': 1, 'inicio': 2.0, 'fin': 3.4, 'desnivel_m': 140, 'largo_km': 1.4, 'pendiente': 10.0}]
xml = gpx_reloj.generar('Trail Entre Pontes', coords, perfil, avit, subidas)
try:
    raiz = ET.fromstring(xml.encode('utf-8'))
    valido = True
except ET.ParseError:
    valido = False
ok(valido, 'la ruta del reloj es un XML válido')
if valido:
    ns = {'g': 'http://www.topografix.com/GPX/1/1'}
    trk = raiz.findall('.//g:trkpt', ns)
    wpt = raiz.findall('g:wpt', ns)
    ok(len(trk) == m and all(-90 <= float(t.get('lat')) <= 90 and -180 <= float(t.get('lon')) <= 180 for t in trk), f'{len(trk)} puntos de traza con coordenadas válidas')
    ok(all(t.find('g:ele', ns) is not None for t in trk), 'todos los puntos llevan altitud')
    nombres = [w.find('g:name', ns).text for w in wpt]
    ok(len(wpt) == 4 and all(nombres), f'{len(wpt)} puntos de control con nombre: {nombres}')
    ok(max(len(n) for n in nombres) <= 24, f'los nombres de los puntos caben (máx. {max(len(n) for n in nombres)} caracteres)')
    largos = [n for n in nombres if len(n) > 15]
    if largos:
        info(f'nombres de más de 15 caracteres, que algunos relojes (Garmin) recortan en pantalla: {largos}')
    ok(len(xml.encode('utf-8')) < 5_000_000, f'el fichero pesa {len(xml.encode("utf-8")) // 1024} KB')
    ok(not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', xml), 'sin caracteres de control')

# ---------------------------------------------------------------- 3. los avisos caben en la pantalla del reloj
perfil_av = [{'d': i * 0.1, 'ele': 400 + 250 * math.sin(i / 25) + 80 * math.sin(i / 7)} for i in range(400)]
plan = plan_avisos.calcular(perfil_av, [{'km': 15.0, 'name': 'Avituallamiento'}], None, 0.3, None)
textos = [str(a.get('texto') or '') for a in plan.get('avisos', [])]
info(f'{len(textos)} avisos de ejemplo; el más largo: {max(textos, key=len) if textos else "-"!r}')
ok(textos, 'el plan de avisos genera textos')
if textos:
    mas = max(len(t) for t in textos)
    ok(mas <= 80, f'el aviso más largo tiene {mas} caracteres (una pantalla de reloj enseña unos 80 sin cortar)')
    ok(all(not re.search(r'[^\x00-\x7fáéíóúüñÁÉÍÓÚÜÑ¿¡·–—«»º°€…↑↓→]', t) for t in textos), 'los avisos solo llevan letras y signos que los relojes dibujan')

print('\nTODO BIEN' if all(resultados) else f'\nFALLOS: {resultados.count(False)}')
sys.exit(0 if all(resultados) else 1)
