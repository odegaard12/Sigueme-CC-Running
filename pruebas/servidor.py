"""Fase 1: preparar la carrera desde el panel (GPX, carrera, avituallamientos,
avisos) y plan para la app. Servidor local en una carpeta limpia."""
import hashlib, json, os, pathlib, shutil, subprocess, sys, time, urllib.request, urllib.error

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import RAIZ, carpeta, gpx_inventado, puerto_libre
W = carpeta('servidor')
ID = 'odg-' + 'f' * 32
(W / 'gps.clave').write_text(ID + '\n')
malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)

sal = os.urandom(16)
env = dict(os.environ, ADMIN_USER='prueba', BIND_HOST='127.0.0.1', PYTHONIOENCODING='utf-8',
           ADMIN_HASH='scrypt:' + sal.hex() + ':' + hashlib.scrypt(b'clave', salt=sal, n=2**14, r=8, p=1, dklen=32).hex())
PORT = puerto_libre()
srv = subprocess.Popen([sys.executable, 'server.py', str(PORT)], cwd=W, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
import atexit; atexit.register(srv.terminate)   # que un fallo a medias no deje el servidor vivo
U = f'http://127.0.0.1:{PORT}'
for _ in range(60):
    try:
        urllib.request.urlopen(U + '/robots.txt', timeout=1); break
    except Exception:
        time.sleep(0.3)

galleta = ''
def pedir(ruta, cuerpo, tipo='application/json', origen=True, cookie=True):
    cab = {'Content-Type': tipo}
    if origen: cab['Origin'] = U
    if cookie and galleta: cab['Cookie'] = galleta
    datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(U + ruta, datos, cab), timeout=60)
        return r.status, json.load(r), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}'), e.headers

try:
    st, _, h = pedir('/api/login', {'usuario': 'prueba', 'password': 'clave'})
    galleta = h['Set-Cookie'].split(';')[0]
    ok(st == 200, 'login')
    st, d, _ = pedir('/api/live', {'action': 'config'})
    ok(st == 200 and d['carrera']['nombre'] and d['plan'] is None, f"config: {d['carrera'].get('nombre')}")

    # 1) datos de la carrera
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba', 'fecha': '2027-03-14',
        'hora_salida': '09:00', 'limite_h': '6', 'corredor': {'nombre': 'Corredor', 'dorsal': '27'},
        'bici': {'modelo': '', 'piezas': {}}, 'slug': '2027-trail-prueba', 'zona_horaria': 'Europe/Madrid', 'ocultar_m': ''}})
    c = json.loads((W / 'carrera.json').read_text(encoding='utf-8'))
    ok(st == 200 and c['nombre'] == 'Trail de prueba' and c['limite_h'] == 6 and 'bici' not in c and 'ocultar_m' not in c,
       f'guardar_carrera: {st} {c}')
    for malo, txt in (({'nombre': 'x', 'fecha': '2027-13-40'}, 'fecha mala'), ({'nombre': 'x', 'hora_salida': '25:00'}, 'hora mala'),
                      ({'nombre': 'x', 'zona_horaria': 'Marte/Olympus'}, 'zona mala'), ({'nombre': 'x', 'limite_h': 'nan'}, 'NaN'),
                      ({'nombre': 'x', 'slug': '../../etc'}, 'slug malo'), ({'nombre': ''}, 'sin nombre'),
                      ({'nombre': 'x', 'distancia_km': 1e9}, 'distancia enorme'),
                      ({'nombre': 'x', 'distancia_km': 21, 'km_minimos_meta': 30}, 'km mínimos > distancia')):
        st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': malo})
        ok(st == 400, f'rechaza {txt}: {d.get("error")}')
    ok(json.loads((W / 'carrera.json').read_text(encoding='utf-8'))['nombre'] == 'Trail de prueba', '  y carrera.json no cambia')

    # 2) GPX
    gpx = gpx_inventado()
    st, d, _ = pedir('/api/gpx', gpx, 'application/gpx+xml', origen=False)
    ok(st == 403, 'GPX sin Origin: 403')
    st, d, _ = pedir('/api/gpx', gpx, 'application/gpx+xml', cookie=False)
    ok(st == 403, 'GPX sin sesión: 403')
    st, d, _ = pedir('/api/gpx', b'<?xml version="1.0"?><!DOCTYPE g [<!ENTITY a "aaaa">]><gpx>&a;</gpx>', 'application/gpx+xml')
    ok(st == 400 and 'ENTITY' in d['error'], f'GPX con entidades: {d.get("error")}')
    st, d, _ = pedir('/api/gpx', b'esto no es xml', 'application/gpx+xml')
    ok(st == 400, f'GPX roto: {d.get("error")}')
    st, d, _ = pedir('/api/gpx?distancia=abc', gpx, 'application/gpx+xml')
    ok(st == 400, f'distancia mala: {d.get("error")}')
    t0 = time.time()
    st, d, _ = pedir('/api/gpx?distancia=103.36', gpx, 'application/gpx+xml')
    ok(st == 200 and d['resumen']['distancia_km'] == 103.36 and d['plan'] and len(d['plan']['avisos']) > 10,
       f"GPX subido en {time.time() - t0:.1f}s: {d.get('resumen')} · {len((d.get('plan') or {}).get('avisos', []))} avisos")
    c = json.loads((W / 'carrera.json').read_text(encoding='utf-8'))
    st2, d2, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba', 'km_minimos_meta': 100}})
    st3, d3, _ = pedir('/api/gpx?distancia=50', gpx, 'application/gpx+xml')
    ok(st2 == 200 and st3 == 200 and 'km_minimos_meta' not in d3['carrera'], 'GPX más corto quita los km mínimos viejos')
    st, d, _ = pedir('/api/gpx?distancia=103.36', gpx, 'application/gpx+xml')
    ok(c['distancia_km'] == 103.36 and c['desnivel_m'] == d['resumen']['desnivel_m'], f"carrera.json con km y D+: {c['distancia_km']} / {c['desnivel_m']}")
    ok((W / 'route.geojson').exists() and (W / 'elevation.json').exists() and not list(W.glob('.*.tmp')), 'route.geojson y elevation.json escritos, sin temporales')

    # 3) avituallamientos
    st, d, _ = pedir('/api/live', {'action': 'guardar_avituallamientos', 'avituallamientos': [
        {'name': 'Meta', 'km': '103.36', 'principal': True}, {'name': 'Avit 1', 'km': 25.5}, {'name': 'Avit 2', 'km': '60'}]})
    ok(st == 200 and [a['name'] for a in d['avituallamientos']] == ['Avit 1', 'Avit 2', 'Meta'], f"avituallamientos ordenados: {d.get('avituallamientos')}")
    ok(any(a['tipo'] == 'avituallamiento' for a in d['plan']['avisos']), '  y el plan trae sus avisos')
    for malo in ([{'name': '', 'km': 3}], [{'name': 'x', 'km': 500}], [{'name': 'x', 'km': 'abc'}], 'nolista', [{'name': 'x'}] * 61, [5]):
        st, d, _ = pedir('/api/live', {'action': 'guardar_avituallamientos', 'avituallamientos': malo})
        ok(st == 400, f'rechaza avituallamientos malos: {str(malo)[:30]} → {d.get("error")}')

    # 4) avisos
    st, d, _ = pedir('/api/live', {'action': 'generar_avisos', 'antes_m': '500', 'cada_km': '20'})
    plan = d.get('plan') or {}
    ok(st == 200 and plan.get('antes_km') == 0.5 and plan.get('cada_km') == 20 and plan.get('cada_fijo') == 20,
       f"generar_avisos 500 m / 20 km: {plan.get('antes_km')} {plan.get('cada_km')}")
    st, d, _ = pedir('/api/live', {'action': 'generar_avisos', 'antes_m': '5', 'cada_km': ''})
    ok(st == 400, f'rechaza ajustes malos: {d.get("error")}')
    av = plan['avisos']
    st, d, _ = pedir('/api/live', {'action': 'guardar_avisos', 'avisos': [{'id': av[0]['id'], 'texto': 'MI TEXTO\x07'}, {'id': av[1]['id'], 'texto': ''}]})
    nuevo = d['plan']['avisos']
    ok(st == 200 and nuevo[0]['texto'] == 'MI TEXTO' and len(nuevo) == len(av) - 1, f'guardar_avisos: cambia uno y quita otro ({len(av)}→{len(nuevo)})')
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba', 'desnivel_m': 3000}})
    ok(st == 200 and d['plan']['cada_fijo'] == 20 and d['plan']['antes_km'] == 0.5, '  cambiar el D+ rehace el plan con los mismos ajustes')

    # 5) plan para la app
    st, d, _ = pedir('/api/plan', {'device_id': 'odg-malo'}, cookie=False, origen=False)
    ok(st == 403, 'app con identificador malo: 403')
    st, d, _ = pedir('/api/plan', {'device_id': ID}, cookie=False, origen=False)
    ok(st == 200 and len(d['ruta']) > 100 and len(d['perfil']) > 100 and d['avisos'] and d['avituallamientos'] and d['carrera']['nombre'],
       f"app baja el plan: {len(d.get('ruta', []))} puntos, {len(d.get('perfil', []))} de perfil, {len(d.get('avisos', []))} avisos")
    st, d, _ = pedir('/api/live', {'action': 'gps_info'})
    ok(d['preparacion'].get('app_at'), '  el panel ve que la app bajó el plan')
    publico = urllib.request.urlopen(U + '/live.json').read().decode()
    ok('app_at' not in publico, '  y no sale en live.json público')
    for ruta in ('/herramientas/plan_avisos.py', '/.carrera.json.tmp', '/gps.clave'):
        try:
            urllib.request.urlopen(U + ruta); ok(False, f'{ruta} se sirve')
        except urllib.error.HTTPError as e:
            ok(e.code in (403, 404), f'{ruta} no se sirve ({e.code})')

    # 5a) la ruta para el reloj: GPX con altitud y puntos de control, solo con sesión
    import xml.etree.ElementTree as ET
    def reloj(sesion=True):
        r = urllib.request.Request(U + '/api/reloj.gpx', headers={'Cookie': galleta} if sesion else {})
        try:
            x = urllib.request.urlopen(r, timeout=30)
            return x.status, x.read().decode('utf-8'), x.headers
        except urllib.error.HTTPError as e:
            return e.code, '', e.headers
    st, _, _ = reloj(False)
    ok(st == 403, 'GPX para el reloj sin sesión: 403')
    st, cuerpo, h = reloj()
    ns = {'g': 'http://www.topografix.com/GPX/1/1'}
    raiz = ET.fromstring(cuerpo)
    wpts, trk = raiz.findall('g:wpt', ns), raiz.findall('.//g:trkpt', ns)
    avit = json.loads((W / 'aid_stations.json').read_text(encoding='utf-8'))
    subidas = json.loads((W / 'avisos.json').read_text(encoding='utf-8'))['subidas']
    ok(st == 200 and 'gpx' in h['Content-Type'] and 'attachment' in h.get('Content-Disposition', ''),
       f"GPX para el reloj con sesión: {st}, {h.get('Content-Disposition')}")
    ok(len(wpts) == len(avit) + 2 * len(subidas) and len(trk) > 100 and all(p.find('g:ele', ns) is not None for p in trk + wpts),
       f'  {len(wpts)} puntos de control ({len(avit)} avituallamientos, {len(subidas)} subidas) y {len(trk)} puntos con altitud')
    ok(any(w.findtext('g:name', namespaces=ns) == 'Cima 1' for w in wpts), '  con su cima')

    # 5b) EMPEZAR desde la app: otro día no toca la web; hoy sí, y una sola vez
    st, d, _ = pedir('/api/plan', {'device_id': ID, 'accion': 'empezar'}, cookie=False, origen=False)
    ok(st == 200 and d.get('estado') == 'otro_dia' and not json.load(urllib.request.urlopen(U + '/live.json')).get('started_at'),
       f"app EMPEZAR otro día: {d.get('estado')} · {d.get('mensaje')}")
    from datetime import datetime as _dt, timedelta as _td
    hoy = _dt.now()
    hora = (hoy + _td(minutes=15)).strftime('%H:%M') if hoy.hour < 23 else '23:59'
    pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba', 'fecha': hoy.strftime('%Y-%m-%d'), 'hora_salida': hora}})
    st, d, _ = pedir('/api/plan', {'device_id': ID, 'accion': 'empezar'}, cookie=False, origen=False)
    live = json.load(urllib.request.urlopen(U + '/live.json'))
    salida = _dt.fromisoformat(live.get('started_at') or '2000-01-01T00:00:00+00:00').astimezone()
    ok(st == 200 and d.get('estado') == 'empezada' and live.get('status_label') == 'En carrera' and salida.strftime('%H:%M') == hora,
       f"app EMPEZAR el día de la carrera: {d.get('estado')}, crono desde las {salida.strftime('%H:%M')} (oficial {hora}), no desde ahora")
    st, d, _ = pedir('/api/plan', {'device_id': ID, 'accion': 'empezar'}, cookie=False, origen=False)
    ok(d.get('estado') == 'ya_estaba', f"  pulsar otra vez no la reinicia: {d.get('estado')}")
    pedir('/api/live', {'action': 'reset'})

    # 5c) resultado desde el panel: un FIT inventado que recorre la ruta desde la salida
    import struct, zlib
    TABLA = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401, 0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]
    def crc(datos, c=0):
        for b in datos:
            for n in (b & 0xF, b >> 4):
                t = TABLA[c & 0xF]; c = (c >> 4) & 0x0FFF; c = c ^ t ^ TABLA[n]
        return c
    def fit(puntos, mov_s):
        cuerpo = bytes([0x40, 0, 0]) + struct.pack('<HB', 20, 3) + bytes([253, 4, 0x86, 0, 4, 0x85, 1, 4, 0x85])
        for t, la, lo in puntos:
            cuerpo += bytes([0]) + struct.pack('<Iii', int(t - 631065600), int(la / 180 * 2**31), int(lo / 180 * 2**31))
        cuerpo += bytes([0x41, 0, 0]) + struct.pack('<HB', 18, 1) + bytes([7, 4, 0x86]) + bytes([1]) + struct.pack('<I', mov_s * 1000)
        cab = struct.pack('<BBHI4s', 14, 0x20, 2093, len(cuerpo), b'.FIT')
        cab += struct.pack('<H', crc(cab))
        return cab + cuerpo + struct.pack('<H', crc(cuerpo))
    coords = json.loads((W / 'route.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates']
    c = json.loads((W / 'carrera.json').read_text(encoding='utf-8'))
    t0 = _dt.fromisoformat(f"{c['fecha']}T{c['hora_salida']}").astimezone().timestamp()
    puntos = [(t0 - 300 + i * 6, la, lo) for i, (lo, la) in enumerate(coords)]
    st, d, _ = pedir('/api/fit', fit(puntos[:400], 3000), 'application/octet-stream')
    ok(st == 400 and 'meta' in d.get('error', ''), f"FIT que no llega a meta: {d.get('error')}")
    st, d, _ = pedir('/api/fit', b'basura' * 100, 'application/octet-stream')
    ok(st == 400, f"FIT roto: {d.get('error')}")
    st, d, _ = pedir('/api/fit', fit(puntos, 10000), 'application/octet-stream')
    r = json.loads((W / 'resultado.json').read_text(encoding='utf-8')) if (W / 'resultado.json').exists() else {}
    ok(st == 200 and r.get('tiempo_oficial_s', 0) > 0 and len(r.get('pasos', [])) >= 2,
       f"FIT bueno → resultado: {d.get('resultado')} · {d.get('pasos')} pasos por avituallamiento")
    (W / 'resultado.json').unlink()

    # 5d) foto del corredor (PNG) desde el panel
    def png(lado=8):
        fila = b'\x00' + b'\x7f\xd4\x6a' * lado
        bloque = lambda tipo, datos: struct.pack('>I', len(datos)) + tipo + datos + struct.pack('>I', zlib.crc32(tipo + datos))
        return (b'\x89PNG\r\n\x1a\n' + bloque(b'IHDR', struct.pack('>IIBBBBB', lado, lado, 8, 2, 0, 0, 0))
                + bloque(b'IDAT', zlib.compress(fila * lado)) + bloque(b'IEND', b''))
    st, d, _ = pedir('/api/avatar', b'GIF89a' + b'x' * 50, 'image/png')
    ok(st == 400, f"foto que no es PNG: {d.get('error')}")
    grande = png(8)[:16] + struct.pack('>II', 30000, 30000) + png(8)[24:]
    st, d, _ = pedir('/api/avatar', grande, 'image/png')
    ok(st == 400, f'foto que dice ser de 30000 x 30000: {st}')
    st, d, _ = pedir('/api/avatar', png(), 'image/png', cookie=False)
    ok(st == 403, 'foto sin sesión: 403')
    st, d, _ = pedir('/api/avatar', png(), 'image/png')
    ok(st == 200 and d['carrera'].get('avatar_v') and (W / 'rider.png').read_bytes() == png(), f"foto subida, avatar_v={d['carrera'].get('avatar_v')}")
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba',
        'corredor': {'nombre': 'Corredor', 'dorsal': '27', 'club': 'Club Montaña', 'categoria': 'Veterano A'}}})
    ok(st == 200 and d['carrera']['corredor'].get('club') == 'Club Montaña' and d['carrera'].get('avatar_v'),
       f"club y categoría guardados, la foto sigue: {d['carrera']['corredor']}")

    # 5e) arreglos de la revisión
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba', 'fecha': '2027-1-5'}})
    ok(d['carrera'].get('fecha') == '2027-01-05', f"fecha sin ceros se guarda como {d['carrera'].get('fecha')}")
    st, d, _ = pedir('/api/live', {'action': 'guardar_avituallamientos', 'avituallamientos': [
        {'name': 'Taller', 'km': 30, 'taller': True}, {'name': 'Avit 2', 'km': 60}]})
    ok(d['avituallamientos'][0].get('taller') is True, 'el marcado de taller se conserva')
    plan = d['plan']; a0 = plan['avisos'][0]; a1 = plan['avisos'][1]
    pedir('/api/live', {'action': 'guardar_avisos', 'avisos': [{'id': a0['id'], 'texto': 'TEXTO MIO'}, {'id': a1['id'], 'texto': ''}]})
    st, d, _ = pedir('/api/live', {'action': 'guardar_avituallamientos', 'avituallamientos': [
        {'name': 'Taller', 'km': 30, 'taller': True}, {'name': 'Avit 2', 'km': 61}]})
    textos = [x['texto'] for x in d['plan']['avisos']]
    ok('TEXTO MIO' in textos and a1['texto'] not in textos, 'cambiar los avituallamientos respeta el texto editado y el aviso quitado')
    st, d, _ = pedir('/api/live', {'action': 'generar_avisos', 'antes_m': '', 'cada_km': ''})
    ok(d['plan']['cada_fijo'] is None and d['plan']['antes_km'] == 0.3 and 'TEXTO MIO' not in [x['texto'] for x in d['plan']['avisos']],
       'Rehacer el plan con campos vacíos: automático y textos automáticos')
    # carrera.json con BOM (editado en Windows): se lee bien y no se pierde nada
    cj = W / 'carrera.json'
    cj.write_bytes(b'\xef\xbb\xbf' + cj.read_bytes())
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'lugar': 'Otro sitio'}})
    ok(st == 200 and d['carrera'].get('nombre') == 'Trail de prueba' and d['carrera'].get('distancia_km'), 'carrera.json con BOM: no se pierden los datos')
    roto = cj.read_bytes(); cj.write_text('{roto', encoding='utf-8')
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'x'}})
    ok(st == 400 and cj.read_text(encoding='utf-8') == '{roto', f"carrera.json roto: no se sobrescribe ({d.get('error')})")
    cj.write_bytes(roto)
    # EMPEZAR repetido tras la medianoche (otro día) con carrera en marcha: no reinicia
    pedir('/api/live', {'action': 'empezar', 'hora_salida': '23:59'})
    pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba', 'fecha': '2020-01-01'}})
    st, d, _ = pedir('/api/plan', {'device_id': ID, 'accion': 'empezar'}, cookie=False, origen=False)
    ok(d.get('estado') == 'ya_estaba', f"carrera en marcha y otro día: {d.get('estado')}, no se reinicia")
    pedir('/api/live', {'action': 'reset'})
    # GPX sin altura: plan vacío (no el de la carrera anterior) y sin D+ viejo
    sin_ele = b'<?xml version="1.0"?><gpx><trk><trkseg>' + b''.join(
        f'<trkpt lat="{40.8 + i * 0.001:.6f}" lon="-4.0"></trkpt>'.encode() for i in range(300)) + b'</trkseg></trk></gpx>'
    st, d, _ = pedir('/api/gpx', sin_ele, 'application/gpx+xml')
    st2, d2, _ = pedir('/api/plan', {'device_id': ID}, cookie=False, origen=False)
    ok(st == 200 and d2.get('avisos') == [] and 'desnivel_m' not in d['carrera'], 'GPX sin altura: plan vacío y sin el D+ viejo')
    pedir('/api/gpx?distancia=103.36', gpx, 'application/gpx+xml')

    # 6) con carrera en marcha no se toca nada
    pedir('/api/live', {'action': 'empezar', 'hora_salida': '09:00'})
    st, d, _ = pedir('/api/gpx', gpx, 'application/gpx+xml')
    ok(st == 409, f'GPX en carrera: {d.get("error")}')
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'otro'}})
    ok(st == 409, 'carrera en carrera: 409')
    st, d, _ = pedir('/api/live', {'action': 'guardar_avituallamientos', 'avituallamientos': []})
    ok(st == 409, 'avituallamientos en carrera: 409')
    pedir('/api/live', {'action': 'reset'})
    st, d, _ = pedir('/api/live', {'action': 'aviso_prueba'})
    ok('ntfy' not in json.dumps(d) and 'ntfy' not in (W / 'server.py').read_text(encoding='utf-8').lower(), 'ntfy ya no existe')
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Trail de prueba', 'hora_salida': ''}})
    ok(st == 200, f'carrera sin hora de salida se guarda: {st} {d.get("error")}')
    # empezar pegando un enlace: nada de la carrera anterior (km de una prueba en casa, pulso)
    vivo = json.loads((W / 'live.json').read_text(encoding='utf-8'))
    vivo.update({'gps_dist_km': 99, 'hr_suma': 5000, 'hr_n': 50, 'gps_t': 2_000_000_000, 'started_at': None, 'finished_at': None})
    (W / 'live.json').write_text(json.dumps(vivo), encoding='utf-8')
    st, d, _ = pedir('/api/live', {'livetrack_url': 'http://127.0.0.1:9/x', 'hora_salida': ''})
    v = d.get('live') or json.loads((W / 'live.json').read_text(encoding='utf-8'))
    ok(st == 200 and not v.get('gps_dist_km') and not v.get('hr_suma') and not v.get('gps_t') and v.get('started_at'),
       f"enlace nuevo empieza de cero: {st} {v.get('gps_dist_km')} {v.get('hr_suma')} {v.get('gps_t')}")
    pedir('/api/live', {'action': 'reset'})
    # simular sin ruta: error claro y sin carrera fantasma que bloquee el panel
    pedir('/api/live', {'action': 'reset'})
    (W / 'route.geojson').unlink()
    st, d, _ = pedir('/api/live', {'action': 'simular', 'segundos': 60})
    vivo = json.loads((W / 'live.json').read_text(encoding='utf-8'))
    ok(st == 400 and not vivo.get('started_at'), f"simular sin ruta: {st} {d.get('error')}, started_at={vivo.get('started_at')}")
    # «nan» desde el panel no llega al live.json (el navegador no lo leería)
    pedir('/api/live', {'speed_kmh': 'nan', 'hr': 'inf'})
    texto = (W / 'live.json').read_text(encoding='utf-8')
    ok('NaN' not in texto and 'Infinity' not in texto, 'sin NaN ni Infinity en live.json')
    # tope del cuerpo
    st, d, _ = pedir('/api/live', {'action': 'guardar_avisos', 'avisos': [{'id': 1, 'texto': 'x' * 100}] * 700})
    ok(st == 413, f'cuerpo de más de 64 KB: {st}')
    # la guía de pulseras y relojes
    r = urllib.request.urlopen(U + '/pulseras'); html = r.read()
    ok(r.status == 200 and b'Xiaomi' in html and b'Huawei' in html and b'Amazfit' in html, '/pulseras: la guía de pulseras y relojes')
    # el service worker se sirve como JavaScript y no es una puerta a nada más
    r = urllib.request.urlopen(U + '/sw.js')
    ok(r.status == 200 and 'javascript' in r.headers.get('Content-Type', '') and b'sigueme-v' in r.read(), 'sw.js: se sirve como JavaScript')
    # la casilla «web sin cobertura»: se guarda solo si está marcada
    base_c = {'nombre': 'Trail de prueba', 'fecha': '2027-03-14', 'hora_salida': '09:00'}
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': dict(base_c, modo_offline=True)})
    ok(st == 200 and d['carrera'].get('modo_offline') is True, 'modo sin cobertura: se guarda activado')
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': dict(base_c, modo_offline=False)})
    ok(st == 200 and 'modo_offline' not in d['carrera'], 'modo sin cobertura: desactivado no deja rastro (lo de siempre)')
    # JSON anidado a propósito (miles de niveles): respuesta normal, no una petición sin contestar
    anidado = b'[' * 5000 + b']' * 5000
    for ruta in ('/api/gps', '/api/live', '/api/plan', '/api/invitado/login'):
        try:
            st = pedir(ruta, anidado)[0]
        except Exception as e:
            st = type(e).__name__
        ok(isinstance(st, int) and st < 500, f'JSON anidado en {ruta}: {st}')
finally:
    srv.terminate()
    err = srv.stderr.read().decode(errors='replace')
    if 'Traceback' in err:
        print(err[-2000:]); malos.append('traceback en el servidor')
print('\nTODO BIEN' if not malos else f'\nFALLOS: {len(malos)}')

sys.exit(1 if malos else 0)
