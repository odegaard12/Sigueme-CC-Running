"""Ensayo de una carrera entera como la usaría el corredor, contra un servidor
local: preparar → EMPEZAR desde la app → carrera con un corte de cobertura (la
app manda la cola al volver) → meta detectada sola → Finalizar → FIT →
archivar → índice y portada. Datos inventados."""
import hashlib, json, math, os, pathlib, shutil, struct, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import RAIZ, carpeta, gpx_inventado
W = carpeta('ensayo')
ID = 'odg-' + 'e' * 32
(W / 'gps.clave').write_text(ID + '\n')
malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)

sal = os.urandom(16)
env = dict(os.environ, ADMIN_USER='prueba', BIND_HOST='127.0.0.1', PYTHONIOENCODING='utf-8',
           ADMIN_HASH='scrypt:' + sal.hex() + ':' + hashlib.scrypt(b'clave', salt=sal, n=2**14, r=8, p=1, dklen=32).hex())
srv = subprocess.Popen([sys.executable, 'server.py', '8798'], cwd=W, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
import atexit; atexit.register(srv.terminate)   # que un fallo a medias no deje el servidor vivo
U = 'http://127.0.0.1:8798'
for _ in range(60):
    try:
        urllib.request.urlopen(U + '/robots.txt', timeout=1); break
    except Exception:
        time.sleep(0.3)
galleta = ''
def pedir(ruta, cuerpo=None, tipo='application/json', panel=True, metodo=None):
    cab = {'Content-Type': tipo}
    if panel:
        cab['Origin'] = U
        if galleta: cab['Cookie'] = galleta
    datos = None if cuerpo is None else (cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode())
    try:
        r = urllib.request.urlopen(urllib.request.Request(U + ruta, datos, cab, method=metodo), timeout=60)
        cuerpo_r = r.read()
        return r.status, (json.loads(cuerpo_r) if r.headers.get('Content-Type', '').startswith('application/json') else cuerpo_r), r
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e
class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
sin_red = urllib.request.build_opener(SinRedireccion)
publico = lambda: json.load(urllib.request.urlopen(U + '/live.json?x=' + str(time.time())))

# ruta inventada (la del ejemplo del repo)
pts = []
for i in range(2101):
    a = 2 * math.pi * i / 2100; k = 21 * i / 2100
    ele = 900 + 120 * math.sin(math.pi * k / 7) ** 2 if k < 14 else 900 + 70 * max(0, 1 - abs(k - 17) / 0.4)
    pts.append((40.80 + 0.030 * math.sin(a), -4.00 + 0.040 * math.cos(a), ele))
gpx = ('<?xml version="1.0"?><gpx version="1.1"><trk><trkseg>' + ''.join(
    f'<trkpt lat="{la:.6f}" lon="{lo:.6f}"><ele>{e:.1f}</ele></trkpt>' for la, lo, e in pts) + '</trkseg></trk></gpx>').encode()

try:
    st, d, r = pedir('/api/login', {'usuario': 'prueba', 'password': 'clave'})
    galleta = r.headers['Set-Cookie'].split(';')[0]
    ahora = datetime.now().astimezone()
    salida = (ahora - timedelta(minutes=95)).replace(second=0, microsecond=0)
    if salida.date() != ahora.date():
        print('(son menos de las 01:35: el ensayo necesita que la salida sea hoy)'); sys.exit(0)

    # 1) preparar
    st, d, _ = pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Ensayo 2027', 'lugar': 'Mi pueblo',
        'fecha': ahora.strftime('%Y-%m-%d'), 'hora_salida': salida.strftime('%H:%M'), 'limite_h': 4, 'slug': '2027-ensayo',
        'corredor': {'nombre': 'Corredor', 'dorsal': '7', 'club': 'Club'}}})
    ok(st == 200, 'preparar: datos de la carrera')
    st, d, _ = pedir('/api/gpx?distancia=21.1', gpx, 'application/gpx+xml')
    ok(st == 200 and len(d['plan']['avisos']) > 5, f"preparar: GPX ({d['resumen']['distancia_km']} km, {len(d['plan']['avisos'])} avisos)")
    st, d, _ = pedir('/api/live', {'action': 'guardar_avituallamientos', 'avituallamientos': [
        {'name': 'Avit 1', 'km': 7.5}, {'name': 'Avit 2', 'km': 14, 'principal': True}, {'name': 'Meta', 'km': 21.1}]})
    ok(st == 200, 'preparar: avituallamientos')

    # 2) EMPEZAR desde la app (sin panel)
    st, d, _ = pedir('/api/plan', {'device_id': ID, 'accion': 'empezar'}, panel=False)
    live = publico()
    t_salida = datetime.fromisoformat(live['started_at'])
    ok(d.get('estado') == 'empezada' and abs((t_salida - salida).total_seconds()) < 1 and live['status_label'] == 'En carrera',
       f"EMPEZAR desde la app: {d.get('estado')}, crono desde la hora oficial {t_salida.astimezone():%H:%M}")

    # la app: posiciones a ritmo constante hasta 1 min antes de ahora
    total = len(pts) - 1
    fin = datetime.now(timezone.utc) - timedelta(minutes=1)
    def punto(i):
        t = t_salida + (fin - t_salida) * (i / total)
        return {'timestamp': t.isoformat(), 'coords': {'latitude': pts[i][0], 'longitude': pts[i][1], 'speed': 3.5, 'accuracy': 6},
                'battery': {'level': 0.8}, 'extras': {'origen': 'app'}}
    def mandar(desde, hasta, paso=10, lote=1):
        idx = list(range(desde, hasta + 1, paso))
        for n in range(0, len(idx), lote):
            st, d, _ = pedir('/api/gps', {'device_id': ID, 'location': [punto(i) for i in idx[n:n + lote]]}, panel=False)
            if st != 200: return st
        return 200
    km_i = lambda km: int(total * km / 21)

    # 3) km 0 → 8 en directo
    ok(mandar(0, km_i(8)) == 200, 'carrera: km 0 → 8 en directo, punto a punto')
    live = publico()
    ok(live.get('lat') and live.get('fuente_posicion') == 'movil' and not live.get('finished_at'), f"web: posición del móvil, sin meta ({live.get('lat')})")
    ok('app_at' not in live and 'bateria_movil' not in live and 'livetrack_url' not in live, 'web pública: sin datos internos')
    # 4) corte de cobertura del km 8 al 15: la app guarda; al volver manda la cola de golpe
    ok(mandar(km_i(8), km_i(15), lote=300) == 200, 'al volver la cobertura: la cola (km 8 → 15) en un lote')
    live = publico()
    ok(not live.get('finished_at'), 'tras la cola: sigue en carrera, sin meta falsa')
    # lote repetido (la app reintenta uno que sí había llegado): no debe romper nada
    ok(mandar(km_i(14), km_i(15), lote=300) == 200 and not publico().get('finished_at'), 'lote repetido: se acepta sin meta falsa')
    # lote viejo reenviado entero (desde la salida, junto a la meta): no es llegada
    ok(mandar(0, km_i(15), lote=300) == 200 and not publico().get('finished_at'), 'lote viejo reenviado desde la salida: sin meta falsa')
    # 5) hasta meta
    ok(mandar(km_i(15), total) == 200, 'carrera: km 15 → meta')
    live = publico()
    ok(bool(live.get('finished_at')), f"meta detectada sola: {live.get('finished_at')}")
    if live.get('finished_at'):
        dur = (datetime.fromisoformat(live['finished_at']) - t_salida).total_seconds() / 60
        esperado = (fin - t_salida).total_seconds() / 60
        ok(abs(dur - esperado) < 3, f"tiempo final {dur:.0f} min (esperado ~{esperado:.0f})")
    # EMPEZAR otra vez (la app reiniciada) tras la meta: no reinicia
    st, d, _ = pedir('/api/plan', {'device_id': ID, 'accion': 'empezar'}, panel=False)
    ok(d.get('estado') == 'terminada' and publico().get('finished_at'), f"EMPEZAR tras la meta: {d.get('estado')}, la meta se mantiene")

    # 6) Finalizar en el panel (respeta la hora de meta del GPS)
    antes = publico()['finished_at']
    pedir('/api/live', {'action': 'stop'})
    ok(publico()['finished_at'] == antes, 'Finalizar: respeta la hora de meta detectada')

    # 7) FIT y archivar
    TABLA = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401, 0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]
    def crc(datos, c=0):
        for b in datos:
            for n in (b & 0xF, b >> 4):
                t = TABLA[c & 0xF]; c = (c >> 4) & 0x0FFF; c = c ^ t ^ TABLA[n]
        return c
    cuerpo = bytes([0x40, 0, 0]) + struct.pack('<HB', 20, 3) + bytes([253, 4, 0x86, 0, 4, 0x85, 1, 4, 0x85])
    for i in range(0, len(pts), 5):
        t = datetime.fromisoformat(punto(i)['timestamp']).timestamp()
        cuerpo += bytes([0]) + struct.pack('<Iii', int(t - 631065600), int(pts[i][0] / 180 * 2**31), int(pts[i][1] / 180 * 2**31))
    cab = struct.pack('<BBHI4s', 14, 0x20, 2093, len(cuerpo), b'.FIT'); cab += struct.pack('<H', crc(cab))
    st, d, _ = pedir('/api/fit', cab + cuerpo + struct.pack('<H', crc(cuerpo)), 'application/octet-stream')
    ok(st == 200 and isinstance(d, dict) and d.get('pasos') == 3, f"FIT → resultado: {d.get('resultado') if isinstance(d, dict) else d}")
    st, d, _ = pedir('/api/live', {'action': 'archivar'})
    ok(st == 200 and d.get('archivada') == '2027-ensayo' and (W / 'carreras/2027-ensayo/resultado.json').exists(), f"archivada en /{d.get('archivada') if isinstance(d, dict) else d}/")
    live = publico()
    ok(not live.get('started_at') and live.get('status_label') == 'Sin iniciar', 'tras archivar: portada a cero')
    try:
        sin_red.open(U + '/')
        ok(False, 'la portada redirige al último resultado')
    except urllib.error.HTTPError as e:
        ok(e.code == 302 and e.headers['Location'].endswith('/2027-ensayo/'), f"portada → {e.headers['Location']}")
    st, html, _ = pedir('/2027-ensayo/', panel=False)
    ok(st == 200 and b'Ensayo 2027' in html, 'la carrera archivada se ve en su dirección')
    st, html, _ = pedir('/carreras/', panel=False)
    ok(st == 200 and b'Ensayo 2027' in html, 'sale en el índice de carreras')
    for f in ('resultado.json', 'carrera.json', 'route.geojson', 'rider.png', 'avisos.json'):
        st, _, _ = pedir('/2027-ensayo/' + f, panel=False)
        ok(st == 200, f'archivo: /2027-ensayo/{f}')
    # nombre con HTML en el índice: escapado
    c = json.loads((W / 'carreras/2027-ensayo/carrera.json').read_text(encoding='utf-8'))
    c['nombre'] = '<img src=x onerror=alert(1)>'
    (W / 'carreras/2027-ensayo/carrera.json').write_text(json.dumps(c), encoding='utf-8')
    st, html, _ = pedir('/carreras/', panel=False)
    ok(b'<img src=x' not in html, 'índice: un nombre con HTML sale escapado')

    # 8) un nombre con «\» no rompe la carrera archivada ni el índice
    c['nombre'] = r'Trail \d C:\x'
    (W / 'carreras/2027-ensayo/carrera.json').write_text(json.dumps(c), encoding='utf-8')
    ok(pedir('/2027-ensayo/', panel=False)[0] == 200 and pedir('/carreras/', panel=False)[0] == 200, 'nombre con «\»: archivo e índice siguen funcionando')

    # 9) carrera nueva preparada para hoy: la portada es ella, no el último resultado
    luego = (datetime.now().astimezone() + timedelta(minutes=30))
    if luego.date() == datetime.now().date():
        pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Otra 2027', 'fecha': luego.strftime('%Y-%m-%d'),
                                                                     'hora_salida': luego.strftime('%H:%M'), 'slug': '2027-otra'}})
        try:
            r = sin_red.open(U + '/'); ok(r.status == 200, 'carrera preparada para hoy: la portada es la nueva')
        except urllib.error.HTTPError as e:
            ok(False, f'carrera preparada para hoy: la portada redirige a {e.headers.get("Location")}')
        # EMPEZAR a la media hora de la salida y pasar por salida/meta desde lejos: NO es llegada
        pedir('/api/plan', {'device_id': ID, 'accion': 'empezar'}, panel=False)
        t0 = datetime.now(timezone.utc)
        lejos = {'timestamp': (t0 - timedelta(minutes=3)).isoformat(), 'coords': {'latitude': pts[1050][0], 'longitude': pts[1050][1], 'accuracy': 5}}
        salida_pt = {'timestamp': (t0 - timedelta(minutes=1)).isoformat(), 'coords': {'latitude': pts[0][0], 'longitude': pts[0][1], 'accuracy': 5}}
        pedir('/api/gps', {'device_id': ID, 'location': [lejos, salida_pt]}, panel=False)
        ok(not publico().get('finished_at'), 'antes de la salida: llegar a la salida desde lejos no es meta')
        pedir('/api/live', {'action': 'reset'})

    # 10) meta dentro de un lote de la cola: el paso por meta y 400 m más
    antes = (datetime.now().astimezone() - timedelta(minutes=80)).replace(second=0, microsecond=0)
    if antes.date() == datetime.now().date():
        pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Otra 2027', 'fecha': antes.strftime('%Y-%m-%d'), 'hora_salida': antes.strftime('%H:%M')}})
        pedir('/api/live', {'action': 'empezar', 'hora_salida': antes.strftime('%H:%M')})
        t_s = datetime.fromisoformat(publico()['started_at']); fin2 = datetime.now(timezone.utc) - timedelta(minutes=2)
        idx = list(range(0, total + 1, 10)) + list(range(10, 50, 10))      # vuelta entera y 400 m más
        lote = [{'timestamp': (t_s + (fin2 - t_s) * (n / len(idx))).isoformat(),
                 'coords': {'latitude': pts[i][0], 'longitude': pts[i][1], 'accuracy': 5}} for n, i in enumerate(idx)]
        pedir('/api/gps', {'device_id': ID, 'location': lote}, panel=False)
        f2 = publico().get('finished_at')
        cruce = t_s + (fin2 - t_s) * ((len(idx) - 5) / len(idx))
        ok(bool(f2) and abs((datetime.fromisoformat(f2) - cruce).total_seconds()) < 120, f'meta dentro del lote: {f2} (paso por meta ~{cruce:%H:%M:%S})')
        pedir('/api/live', {'action': 'reset'})

    # 10b) un archivo con carrera.json roto («null») no tumba el índice ni la portada
    roto = W / 'carreras' / '2020-roto'; roto.mkdir(parents=True, exist_ok=True)
    (roto / 'carrera.json').write_text('null', encoding='utf-8')
    (roto / 'resultado.json').write_text('[]', encoding='utf-8')
    for ruta in ('/carreras/', '/'):
        try:
            st = urllib.request.urlopen(U + ruta, timeout=10).status
        except urllib.error.HTTPError as e:
            st = e.code
        ok(st in (200, 302), f'{ruta} con un archivo roto: {st}')
    html = urllib.request.urlopen(U + '/carreras/', timeout=10).read().decode('utf-8')
    ok('indice-traza' in html and 'Todas las carreras' in html, 'índice con el dibujo del recorrido')

    # 11) bloqueo por claves falsas también sin Origin (antes no contaban)
    for n in range(12):
        st, _, _ = pedir('/api/live', {'usuario': 'prueba', 'password': 'mala', 'action': 'config'}, panel=False)
    ok(st == 429, f'11 claves falsas sin Origin: bloqueado ({st})')
finally:
    srv.terminate()
    err = srv.stderr.read().decode(errors='replace')
    if 'Traceback' in err:
        print(err[-3000:]); malos.append('traceback en el servidor')
print('\nTODO BIEN' if not malos else f'\nFALLOS: {len(malos)}')
sys.exit(1 if malos else 0)
