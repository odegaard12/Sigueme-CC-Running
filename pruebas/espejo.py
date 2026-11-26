"""El móvil del dueño alimenta las dos páginas de la misma carrera: la principal (con la clave del GPS) y la compartida
(con su identificador de corredor). Y una carrera en directo de OTRO día no se mezcla con la principal.
Servidor local en una carpeta limpia, datos inventados."""
import atexit, hashlib, json, os, pathlib, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import carpeta, gpx_inventado, puerto_libre
W = carpeta('espejo')
sys.path.insert(0, str(W / 'herramientas'))
import invitados as inv, directos as dm, plan_avisos as pa, preparar_ruta as pr
malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)

salida = (datetime.now() - timedelta(minutes=30)).replace(second=0, microsecond=0)
fecha, hora = salida.strftime('%Y-%m-%d'), salida.strftime('%H:%M')
(W / 'carrera.json').write_text(json.dumps({'nombre': 'Carrera de prueba', 'fecha': fecha, 'hora_salida': hora, 'zona_horaria': 'Europe/Madrid',
                                            'distancia_km': 10, 'limite_h': 3}), encoding='utf-8')
CLAVE = 'clave-del-gps-de-prueba-0123456789abcdef'
(W / 'gps.clave').write_text(CLAVE, encoding='utf-8')
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
c_mismo, yo = dm.crear(str(W), inv.DUENO, 'Dueno', ruta, fecha, hora, pa.calcular)             # la MISMA carrera (día y hora) que la principal
otro = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
c_otro, yo_otro = dm.crear(str(W), inv.DUENO, 'Dueno', ruta, otro, hora, pa.calcular)           # OTRO día: no debe mezclarse
time.sleep(6)                                                                                    # el servidor reindexa cada pocos segundos
lat, lon = ruta['coords'][50][1], ruta['coords'][50][0]


def mandar(ident, desplazo):
    q = urllib.parse.urlencode({'id': ident, 'lat': lat + desplazo, 'lon': lon, 'timestamp': int(time.time()) - 5, 'batt': 77})
    return urllib.request.urlopen(urllib.request.Request(U + '/api/gps?' + q, data=b'', method='POST'), timeout=20).status


def en_la_principal():
    try:
        return json.loads((W / 'live.json').read_text(encoding='utf-8')).get('gps_ult')
    except (OSError, ValueError):
        return None


# 1) el móvil manda con su identificador de corredor de la carrera compartida → también la principal
ok(mandar(yo['ident'], 0.0001) == 200, 'el móvil manda con el identificador de la carrera compartida')
ult = dm.estado(str(W), c_mismo['id'], yo['cid']).get('ult')
ok(ult is not None, 'y la carrera compartida lo recibe')
ok(en_la_principal() is not None, 'y la principal también (ya no se queda en «Sin iniciar»)')
ok(dm.estado(str(W), c_otro['id'], yo_otro['cid']).get('ult') is None, 'la carrera en directo de otro día no recibe nada')
# 2) el móvil sigue configurado con la clave de la principal → también su corredor en la compartida
(W / 'live.json').unlink(missing_ok=True)
ok(mandar(CLAVE, 0.0002) == 200, 'el móvil manda con la clave de la carrera principal')
ult2 = dm.estado(str(W), c_mismo['id'], yo['cid']).get('ult')
ok(ult2 is not None and ult2[2] >= ult[2], 'y su corredor en la carrera compartida también se mueve (no se queda en «Aún sin salir»)')
ok(en_la_principal() is not None, 'y la principal sigue recibiéndolo')
ok(dm.estado(str(W), c_otro['id'], yo_otro['cid']).get('ult') is None, 'la de otro día sigue sin recibir nada')
# 3) un identificador cualquiera sigue sin valer
try:
    s = mandar('clave-inventada-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 0)
except urllib.error.HTTPError as e:
    s = e.code
ok(s == 403, 'un identificador inventado sigue dando 403')
print('\nTODO BIEN' if not malos else f'\nFALLOS: {len(malos)}')
sys.exit(0 if not malos else 1)
