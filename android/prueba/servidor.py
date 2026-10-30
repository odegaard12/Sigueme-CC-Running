"""Banco de pruebas: el servidor REAL con una carrera inventada de 3 km (hacia el
norte desde 40.8, -4.0), para que la app del emulador la corra de verdad.
Deja el identificador en /tmp/banco/id y se queda sirviendo en :8800."""
import hashlib, json, os, pathlib, shutil, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPO = pathlib.Path(__file__).resolve().parents[2]
W = pathlib.Path('/tmp/banco')
shutil.rmtree(W, ignore_errors=True)
W.mkdir()
for f in ('server.py', 'index.html', 'app.js', 'directo.css', 'admin.html', 'robots.txt'):
    if (REPO / f).exists():
        shutil.copy(REPO / f, W / f)
shutil.copytree(REPO / 'herramientas', W / 'herramientas')
ID = 'odg-' + hashlib.sha256(os.urandom(16)).hexdigest()[:32]
(W / 'gps.clave').write_text(ID + '\n')
(W / 'id').write_text(ID)
sal = os.urandom(16)
env = dict(os.environ, ADMIN_USER='banco', BIND_HOST='127.0.0.1', PYTHONIOENCODING='utf-8',
           ADMIN_HASH='scrypt:' + sal.hex() + ':' + hashlib.scrypt(b'banco', salt=sal, n=2**14, r=8, p=1, dklen=32).hex())
log = open(W / 'servidor.log', 'w')
subprocess.Popen([sys.executable, 'server.py', '8800'], cwd=W, env=env, stdout=log, stderr=log, start_new_session=True)
U = 'http://127.0.0.1:8800'
for _ in range(60):
    try:
        urllib.request.urlopen(U + '/robots.txt', timeout=1); break
    except Exception:
        time.sleep(0.5)

galleta = ''
def pedir(ruta, cuerpo, tipo='application/json'):
    cab = {'Content-Type': tipo, 'Origin': U}
    if galleta: cab['Cookie'] = galleta
    datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
    return urllib.request.urlopen(urllib.request.Request(U + ruta, datos, cab), timeout=60)

r = pedir('/api/login', {'usuario': 'banco', 'password': 'banco'})
galleta = r.headers['Set-Cookie'].split(';')[0]
# 3 km al norte, sube 60 m entre el km 0,6 y el 1,8
g = 1 / 111.195
pts = ''.join(f'<trkpt lat="{40.8 + i * 0.03 * g:.6f}" lon="-4.0"><ele>{900 + 60 * min(max(i * 0.03 - 0.6, 0), 1.2) / 1.2:.1f}</ele></trkpt>'
              for i in range(101))
pedir('/api/gpx', ('<gpx><trk><trkseg>' + pts + '</trkseg></trk></gpx>').encode(), 'application/gpx+xml')
ahora = datetime.now(ZoneInfo('Europe/Madrid'))
salida = ahora - timedelta(minutes=2)
pedir('/api/live', {'action': 'guardar_carrera', 'carrera': {
    'nombre': 'Banco de pruebas', 'fecha': salida.strftime('%Y-%m-%d'), 'hora_salida': salida.strftime('%H:%M'),
    'distancia_km': 3.0, 'zona_horaria': 'Europe/Madrid'}})
pedir('/api/live', {'action': 'guardar_avituallamientos', 'avituallamientos': [{'name': 'Fuente', 'km': 2.0}]})
plan = json.loads(pedir('/api/plan', {'device_id': ID}).read())
# una ruta publicada por un invitado: la app la tiene que enseñar en «Rutas» y bajar su GPX
codigo = json.loads(pedir('/api/live', {'action': 'invitado_crear', 'usuario': 'banco2', 'dias': 30}).read())['codigo']
r = pedir('/api/invitado/login', {'usuario': 'banco2', 'codigo': codigo}); invitada = r.headers['Set-Cookie'].split(';')[0]
galleta_admin, galleta = galleta, invitada
ruta_inv = json.loads(pedir('/api/invitado/gpx?nombre=Ruta%20de%20prueba', ('<gpx><trk><trkseg>' + pts + '</trkseg></trk></gpx>').encode(), 'application/gpx+xml').read())['ruta']
pedir('/api/invitado/ruta', {'id': ruta_inv['id'], 'publica': True, 'ocultar_m': 0, 'avituallamientos': [{'name': 'Fuente del banco', 'km': 1.5}]})
galleta = galleta_admin
print('servidor listo:', len(plan.get('avisos', [])), 'avisos,', len(plan.get('ruta', [])), 'puntos de ruta')
