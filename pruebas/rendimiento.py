"""Web pública en un móvil lento (4G floja, CPU ×4): peso, tiempos y errores en
consola en cada estado (antes de salir, en directo, sin cobertura, resultado).
Servidor local con datos inventados."""
import hashlib, json, math, os, pathlib, shutil, struct, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import RAIZ, carpeta, gpx_inventado
W = carpeta('rendimiento', datos=('carrera.json', 'route.geojson', 'elevation.json', 'aid_stations.json'))
ID = 'odg-' + 'r' * 32
(W / 'gps.clave').write_text(ID + '\n')
sal = os.urandom(16)
env = dict(os.environ, ADMIN_USER='prueba', BIND_HOST='127.0.0.1', PYTHONIOENCODING='utf-8',
           ADMIN_HASH='scrypt:' + sal.hex() + ':' + hashlib.scrypt(b'clave', salt=sal, n=2**14, r=8, p=1, dklen=32).hex())
srv = subprocess.Popen([sys.executable, 'server.py', '8800'], cwd=W, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
import atexit; atexit.register(srv.terminate)   # que un fallo a medias no deje el servidor vivo
U = 'http://127.0.0.1:8800'
for _ in range(60):
    try:
        urllib.request.urlopen(U + '/robots.txt', timeout=1); break
    except Exception:
        time.sleep(0.3)
coords = json.loads((W / 'route.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates']
import http.cookiejar
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def post(r, d, origen=True, tipo='application/json'):
    h = {'Content-Type': tipo}
    if origen: h['Origin'] = U
    return op.open(urllib.request.Request(U + r, d if isinstance(d, bytes) else json.dumps(d).encode(), h)).read()
post('/api/login', {'usuario': 'prueba', 'password': 'clave'})

def medir(pg_ctx, nombre):
    pg = pg_ctx.new_page()
    errores = []
    pg.on('console', lambda m: m.type == 'error' and errores.append(m.text[:120]))
    pg.on('pageerror', lambda e: errores.append('JS: ' + str(e)[:120]))
    pg.on('response', lambda r: r.status >= 400 and errores.append(f'{r.status} {r.url}'))
    cdp = pg_ctx.new_cdp_session(pg)
    cdp.send('Network.enable')
    cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 150, 'downloadThroughput': 1_600_000 / 8, 'uploadThroughput': 750_000 / 8})
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    bytes_propios = [0]
    pg.on('response', lambda r: r.url.startswith(U) and bytes_propios.__setitem__(0, bytes_propios[0] + int(r.headers.get('content-length') or 0)))
    t0 = time.time()
    pg.goto(U + '/', wait_until='domcontentloaded')
    t_dom = time.time() - t0
    t_datos = None
    while time.time() - t0 < 30:
        if pg.evaluate("!document.querySelector('.metricas').classList.contains('esqueleto')"):
            t_datos = time.time() - t0; break
        pg.wait_for_timeout(100)
    try:
        pg.wait_for_selector('#cargando.fuera', timeout=60000); t_mapa = time.time() - t0
    except Exception:
        t_mapa = None
    pg.wait_for_timeout(4000)
    pill = pg.evaluate("(document.getElementById('pill-estado')||{}).textContent || ''")
    estado = pg.evaluate("(document.getElementById('estado-carrera')||{}).textContent || ''")
    print(f"{nombre:13} píldora «{pill}» · DOM {t_dom:.1f}s · datos {t_datos and round(t_datos,1)}s · mapa {t_mapa and round(t_mapa,1)}s · "
          f"{bytes_propios[0] // 1024} KB propios · estado «{estado[:60]}»")
    for e in errores: print('     error:', e)
    pg.close()
    return errores

try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=angle', '--enable-gpu', '--ignore-gpu-blocklist'])
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
        malos = []
        ahora = datetime.now().astimezone()
        luego = ahora + timedelta(minutes=40)
        if luego.date() != ahora.date() or (ahora - timedelta(minutes=90)).date() != ahora.date():
            print('(cerca de la medianoche: sin estados de carrera)'); sys.exit(0)
        post('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Mi trail', 'fecha': ahora.strftime('%Y-%m-%d'), 'hora_salida': luego.strftime('%H:%M')}})
        malos += medir(ctx, 'antes')
        salida = (ahora - timedelta(minutes=90)).replace(second=0, microsecond=0)
        post('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Mi trail', 'hora_salida': salida.strftime('%H:%M')}})
        post('/api/live', {'action': 'empezar', 'hora_salida': salida.strftime('%H:%M')})
        t_s = salida.astimezone(timezone.utc)
        def lote(hasta, fin):
            n = int(len(coords) * hasta)
            pts = [{'timestamp': (t_s + (fin - t_s) * (i / n)).isoformat(), 'coords': {'latitude': coords[i][1], 'longitude': coords[i][0], 'accuracy': 5}}
                   for i in range(0, n, 8)]
            post('/api/gps', {'device_id': ID, 'location': pts}, origen=False)
        lote(0.35, datetime.now(timezone.utc) - timedelta(minutes=12))
        malos += medir(ctx, 'sin cobertura')
        lote(0.55, datetime.now(timezone.utc) - timedelta(seconds=20))
        malos += medir(ctx, 'en directo')
        res = {'carrera': 'Mi trail', 'salida': t_s.isoformat(), 'llegada': (t_s + timedelta(hours=2)).isoformat(), 'tiempo_oficial_s': 7200,
               'tiempo_movimiento_s': 6900, 'distancia_km': 21.1, 'desnivel_m': 309, 'pulso_medio': 151, 'cadencia_media': None,
               'velocidad_media_mov': 11, 'pasos': [], 'traza': [[c[1], c[0], i * 4] for i, c in enumerate(coords[::5])]}
        post('/api/live', {'action': 'stop'})
        (W / 'resultado.json').write_text(json.dumps(res), encoding='utf-8')
        post('/api/live', {'action': 'reset'})
        malos += medir(ctx, 'resultado')
        b.close()
        print('\nSIN ERRORES EN CONSOLA' if not malos else f'\nERRORES: {len(malos)}')
finally:
    srv.terminate()
    err = srv.stderr.read().decode(errors='replace')
    if 'Traceback' in err: print(err[-2000:])
