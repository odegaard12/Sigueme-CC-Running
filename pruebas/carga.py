"""Simulación de carga: N espectadores pidiendo live.json cada segundo (como
5×N con el sondeo real de 5 s) mientras la app manda posiciones cada 5 s y se
abre la portada. Mide latencias y errores del servidor real (sin la caché de
Cloudflare: el peor caso)."""
import hashlib, json, os, pathlib, shutil, subprocess, sys, threading, time, urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import RAIZ, carpeta, gpx_inventado
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
DURA = 45
W = carpeta('carga', datos=('carrera.json', 'route.geojson', 'elevation.json', 'aid_stations.json'))
ID = 'odg-' + 'c' * 32
(W / 'gps.clave').write_text(ID + '\n')
sal = os.urandom(16)
env = dict(os.environ, ADMIN_USER='prueba', BIND_HOST='127.0.0.1', PYTHONIOENCODING='utf-8',
           ADMIN_HASH='scrypt:' + sal.hex() + ':' + hashlib.scrypt(b'clave', salt=sal, n=2**14, r=8, p=1, dklen=32).hex())
srv = subprocess.Popen([sys.executable, 'server.py', '8810'], cwd=W, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
import atexit; atexit.register(srv.terminate)   # que un fallo a medias no deje el servidor vivo
U = 'http://127.0.0.1:8810'
for _ in range(60):
    try:
        urllib.request.urlopen(U + '/robots.txt', timeout=1); break
    except Exception:
        time.sleep(0.3)
import http.cookiejar
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def post(r, d, origen=True):
    h = {'Content-Type': 'application/json'}
    if origen: h['Origin'] = U
    return op.open(urllib.request.Request(U + r, json.dumps(d).encode(), h), timeout=30).read()
post('/api/login', {'usuario': 'prueba', 'password': 'clave'})
ahora = datetime.now().astimezone()
post('/api/live', {'action': 'guardar_carrera', 'carrera': {'nombre': 'Carga', 'fecha': ahora.strftime('%Y-%m-%d'), 'hora_salida': (ahora - timedelta(minutes=1)).strftime('%H:%M')}})
post('/api/live', {'action': 'empezar', 'hora_salida': (ahora - timedelta(minutes=1)).strftime('%H:%M')})
coords = json.loads((W / 'route.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates']

lat, err, fin = {'live': [], 'portada': [], 'gps': []}, {'live': 0, 'portada': 0, 'gps': 0}, time.time() + DURA
cerrojo = threading.Lock()
def medir(tipo, f):
    t = time.time()
    try:
        f(); d = time.time() - t
        with cerrojo: lat[tipo].append(d)
    except Exception:
        with cerrojo: err[tipo] += 1

def espectador(i):
    time.sleep(i * 1.0 / N)
    medir('portada', lambda: urllib.request.urlopen(U + '/', timeout=10).read())
    while time.time() < fin:
        medir('live', lambda: urllib.request.urlopen(U + f'/live.json?_={int(time.time() / 3)}', timeout=10).read())
        time.sleep(1)

def movil():
    i = 0
    while time.time() < fin:
        c = coords[min(i, len(coords) - 1)]; i += 3
        p = [{'timestamp': datetime.now(timezone.utc).isoformat(), 'coords': {'latitude': c[1], 'longitude': c[0], 'accuracy': 5}}]
        medir('gps', lambda: post('/api/gps', {'device_id': ID, 'location': p}, origen=False))
        time.sleep(5)

hilos = [threading.Thread(target=espectador, args=(i,)) for i in range(N)] + [threading.Thread(target=movil)]
for h in hilos: h.start()
for h in hilos: h.join()
srv.terminate()
e = srv.stderr.read().decode(errors='replace')
p = lambda v, q: sorted(v)[min(len(v) - 1, int(len(v) * q))] * 1000 if v else float('nan')
print(f'{N} espectadores × 1 petición/s ≈ {N * 5} con el sondeo real · {DURA} s')
for k in lat:
    print(f'  {k:8} {len(lat[k]):5} peticiones · mediana {p(lat[k], .5):6.0f} ms · p95 {p(lat[k], .95):6.0f} ms · máx {p(lat[k], 1):6.0f} ms · errores {err[k]}')
malo = any(err.values()) or 'Traceback' in e or p(lat['live'], .95) > 2000 or p(lat['gps'], .95) > 3000   # holgado: un equipo cargado no es un fallo
if 'Traceback' in e: print(e[-1500:])
print('CARGA MAL' if malo else 'CARGA OK')
sys.exit(1 if malo else 0)
