"""El guiado del panel: el siguiente paso de la preparación, las filas que llevan a su sitio y el aviso en Hoy.
Necesita Playwright (pip install playwright && playwright install chromium); las capturas van a una carpeta temporal."""
import hashlib, json, math, os, pathlib, shutil, struct, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import RAIZ, carpeta, gpx_inventado
W = carpeta('panel', datos=('carrera.json', 'route.geojson', 'elevation.json', 'aid_stations.json'))
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

import tempfile
OUT = pathlib.Path(tempfile.gettempdir()) / 'sigueme-panel'
OUT.mkdir(exist_ok=True)
BASE = {'nombre': 'Mi trail', 'fecha': '2027-05-16', 'hora_salida': '09:00', 'ruta_km': 21.1, 'distancia_km': 21.1,
        'avituallamientos': 3, 'avisos': 20, 'subidas': 4, 'app_at': '2026-10-19T08:00:00Z', 'id_largo': True, 'resultado_pendiente': False}
casos = {'sin_ruta': dict(BASE, ruta_km=None, avisos=0, subidas=0, avituallamientos=0),
         'solo_app': dict(BASE, app_at=None),
         'todo_listo': dict(BASE)}
malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for ancho, alto in ((390, 844), (1440, 900)):
            ctx = b.new_context(viewport={'width': ancho, 'height': alto})
            pg = ctx.new_page(); errores = []
            pg.on('pageerror', lambda e: errores.append(str(e)[:120]))
            pg.goto(U + '/admin.html'); pg.wait_for_timeout(800)
            pg.fill('#usuario', 'prueba'); pg.fill('#token', 'clave'); pg.keyboard.press('Enter'); pg.wait_for_timeout(2000)
            pg.evaluate('clearInterval(sondeo)')
            for nombre, datos in casos.items():
                pg.evaluate('d => pintarPreparacion(d)', datos)
                pg.click('button[data-tab="preparar"]'); pg.wait_for_timeout(300)
                texto = pg.inner_text('#siguiente-txt'); prog = pg.inner_text('#prep-progreso')
                pg.screenshot(path=str(OUT / f'guia-{nombre}-{ancho}.png'), full_page=True)
                if ancho == 390:
                    print(f'  [{nombre}] {prog} · {texto}')
                    if nombre == 'sin_ruta':
                        ok('GPX' in texto, 'sin ruta: el siguiente paso es subir el GPX')
                        pg.click('#siguiente-ir'); pg.wait_for_timeout(1200)
                        ok(pg.evaluate("document.getElementById('sec-ruta').classList.contains('resalta')") and not pg.evaluate("document.getElementById('sec-ruta').hidden"),
                           'el botón lleva y resalta la sección Ruta')
                        pg.screenshot(path=str(OUT / 'guia-tras-ir-390.png'))
                        pg.click('button[data-tab="hoy"]'); pg.wait_for_timeout(300)
                        ok(not pg.evaluate("document.getElementById('hoy-pendientes').hidden"), 'Hoy enseña el aviso de lo que falta')
                        pg.screenshot(path=str(OUT / 'guia-hoy-390.png'), full_page=True)
                    if nombre == 'solo_app':
                        ok('app' in texto.lower(), 'solo falta la app: lo dice')
                        pg.click('#siguiente-ir'); pg.wait_for_timeout(600)
                        ok(pg.evaluate("document.querySelector('.pestanas button[aria-selected=true]').dataset.tab") == 'movil', 'el botón cambia a la pestaña Móvil')
                    if nombre == 'todo_listo':
                        ok('Todo listo' in texto and pg.evaluate("document.getElementById('siguiente-ir').hidden"), 'todo listo: sin botón y con la indicación del día')
                        ok(pg.evaluate("document.getElementById('hoy-pendientes').hidden"), 'todo listo: Hoy sin aviso')
            ok(not errores, f'sin errores JS a {ancho}px: {errores}')
            ctx.close()
        b.close()
finally:
    srv.terminate()
print('TODO BIEN' if not malos else 'FALLOS: ' + str(len(malos)))
sys.exit(1 if malos else 0)
