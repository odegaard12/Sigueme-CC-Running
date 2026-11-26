"""Posiciones de un corredor (identificador válido) mientras muchos espectadores piden la página del directo sin parar:
ninguna puede rechazarse con «identificador incorrecto». Antes el servidor recargaba el módulo de los directos en cada
petición y, al coincidir dos, el índice de corredores quedaba vacío un instante. Servidor local, datos inventados."""
import atexit, hashlib, json, os, pathlib, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import carpeta, gpx_inventado, puerto_libre
W = carpeta('concurrencia')
sys.path.insert(0, str(W / 'herramientas'))
import invitados as inv, directos as dm, plan_avisos as pa, preparar_ruta as pr
malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)

sal = os.urandom(16)
env = dict(os.environ, ADMIN_USER='prueba', BIND_HOST='127.0.0.1', PYTHONIOENCODING='utf-8',
           ADMIN_HASH='scrypt:' + sal.hex() + ':' + hashlib.scrypt(b'clave', salt=sal, n=2**14, r=8, p=1, dklen=32).hex())
PORT = puerto_libre()
srv = subprocess.Popen([sys.executable, 'server.py', str(PORT)], cwd=W, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
atexit.register(srv.terminate)
U = f'http://127.0.0.1:{PORT}'
for _ in range(60):
    try:
        urllib.request.urlopen(U + '/robots.txt', timeout=1); break
    except Exception:
        time.sleep(0.3)
det = inv.crear_ruta(str(W), inv.DUENO, 'Ruta', gpx_inventado(km=10), pr.preparar, pa.calcular)
ruta = inv._leer_ruta(str(W), inv.DUENO, det['id'])
salida = datetime.now() - timedelta(minutes=20)
c, yo = dm.crear(str(W), inv.DUENO, 'Dueno', ruta, salida.strftime('%Y-%m-%d'), salida.strftime('%H:%M'), pa.calcular)
for _ in range(34):                              # una web con muchas carreras: releer el índice tarda más y la ventana del fallo es mayor
    dm.crear(str(W), inv.DUENO, 'Otro', ruta, salida.strftime('%Y-%m-%d'), salida.strftime('%H:%M'), pa.calcular)
time.sleep(6)
parar = [False]
def espectador():
    while not parar[0]:
        try: urllib.request.urlopen(U + '/api/directo?id=' + c['id'], timeout=20).read()
        except Exception: pass
hilos = [threading.Thread(target=espectador, daemon=True) for _ in range(12)]
[h.start() for h in hilos]
codigos = {}
lat, lon = ruta['coords'][20][1], ruta['coords'][20][0]
for i in range(600):
    q = urllib.parse.urlencode({'id': yo['ident'], 'lat': lat, 'lon': lon, 'timestamp': int(time.time()) + i, 'batt': 70})
    try: s = urllib.request.urlopen(urllib.request.Request(U + '/api/gps?' + q, data=b'', method='POST'), timeout=20).status
    except urllib.error.HTTPError as e: s = e.code
    codigos[s] = codigos.get(s, 0) + 1
parar[0] = True
ok(codigos == {200: 600}, f'600 posiciones válidas con 12 espectadores pidiendo la página sin parar: todas aceptadas ({codigos})')
st = 0
try:
    urllib.request.urlopen(urllib.request.Request(U + '/api/gps?id=dir-inventado-xxxxxxxxxxxxxxxx&lat=1&lon=1', data=b'', method='POST'), timeout=20)
except urllib.error.HTTPError as e:
    st = e.code
ok(st == 403, 'y un identificador inventado sigue dando 403')
print('\nTODO BIEN' if not malos else f'\nFALLOS: {len(malos)}')
sys.exit(0 if not malos else 1)
