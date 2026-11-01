"""Carreras en directo de varios corredores (v1.54): un invitado la crea desde su ruta, otro se apunta con la
invitación, y dos móviles (uno como la app Android, otro como Traccar) corren a la vez. Arranque, salida real,
meta y tiempo de cada uno, el plan para la app, la portada, nada privado a la vista y el panel quitándola.
Servidor local en una carpeta limpia, datos inventados."""
import atexit, hashlib, json, math, os, pathlib, re, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import carpeta, gpx_inventado, puerto_libre
W = carpeta('directos')
sys.path.insert(0, str(W / 'herramientas'))
import invitados as inv
malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)

ahora = datetime.now()
salida = (ahora - timedelta(minutes=80)).replace(second=0, microsecond=0)     # vale aunque caiga ayer: va con fecha y hora
codigo = inv.crear(str(W), 'ana', dias=30, nombre='Ana')
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


def http(metodo, ruta, cuerpo=None, cookie='', tipo='application/json'):
    cab = {'Content-Type': tipo, 'Origin': U}
    if cookie: cab['Cookie'] = cookie
    if cuerpo is not None and not isinstance(cuerpo, bytes): cuerpo = json.dumps(cuerpo).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(U + ruta, cuerpo, cab, method=metodo), timeout=60)
        st, h, b = r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        st, h, b = e.code, e.headers, e.read()
    try:
        return st, json.loads(b), h
    except ValueError:
        return st, b, h


# ---- el invitado entra, sube su ruta y crea la carrera
st, _, h = http('POST', '/api/invitado/login', {'usuario': 'ana', 'codigo': codigo})
galleta = h['Set-Cookie'].split(';')[0]
st, d, _ = http('POST', '/api/invitado/gpx?nombre=Trail%20de%20prueba', gpx_inventado(km=10), galleta, 'application/gpx+xml')
ok(st == 200, 'el invitado sube su ruta')
ruta_id = d['ruta']['id']
st, d, _ = http('POST', '/api/invitado/directo', {'ruta': ruta_id, 'fecha': salida.strftime('%Y-%m-%d'), 'hora': salida.strftime('%H:%M'), 'nombre': 'Ana'}, galleta)
ok(st == 200 and d['ident'].startswith('dir-'), 'crea la carrera en directo desde su ruta')
ID, TOKEN, ID_ANA = d['id'], d['invitacion'], d['ident']
st, _, _ = http('POST', '/api/invitado/directo', {'ruta': ruta_id, 'fecha': 'mañana', 'hora': '10:00', 'nombre': 'X'}, galleta)
ok(st == 400, 'sin día bueno no se crea')

# ---- otro se apunta con la invitación (sin cuenta)
st, _, _ = http('POST', '/api/invitado/unirse', {'id': ID, 'token': 'mala', 'nombre': 'Intruso'})
ok(st == 403, 'sin la invitación buena no se apunta nadie')
st, d, _ = http('POST', '/api/invitado/unirse', {'id': ID, 'token': TOKEN, 'nombre': 'Berto'})
ok(st == 200 and d['ident'].startswith('dir-') and d['ident'] != ID_ANA, 'con la invitación se apunta y recibe SU identificador')
ID_BERTO = d['ident']

# ---- la app Android baja el plan con su identificador (la app no cambia)
st, pl, _ = http('POST', '/api/plan', {'device_id': ID_ANA})
ok(st == 200 and len(pl['ruta']) > 50 and pl['carrera']['hora_salida'] == salida.strftime('%H:%M') and len(pl['avisos']) > 0,
   f"la app baja el plan de SU carrera ({len(pl.get('avisos', []))} avisos)")
st, _, _ = http('POST', '/api/plan', {'device_id': 'dir-no-existe-123456789012'})
ok(st == 403, 'un identificador inventado no baja nada')

# ---- los dos móviles: 3 min parados en la salida y luego a correr (Ana, como la app, a 10 km/h hasta meta;
# Berto, como Traccar, a 8 km/h, va por la mitad)
pts = [(float(a), float(b)) for a, b in re.findall(r'lat="([-\d.]+)" lon="([-\d.]+)"', gpx_inventado(km=10).decode())]
t0 = salida.timestamp()
def recorrido(kmh, hasta_km, espera_s=180, parado_meta_s=120):
    out, t = [], t0
    for _ in range(espera_s // 10):
        out.append((t, pts[0][0] + 0.00002, pts[0][1])); t += 10
    paso = 0.05 / kmh * 3600
    for la, lo in pts[1:int(hasta_km / 0.05) + 1]:
        t += paso; out.append((t, la, lo))
    for _ in range(parado_meta_s // 10):
        t += 10; out.append((t, out[-1][1] + 0.00001, out[-1][2]))
    return out
ana = recorrido(10, 10)
berto = recorrido(8, 5, parado_meta_s=0)
for i in range(0, len(ana), 6):
    lote = [{'timestamp': datetime.fromtimestamp(t).astimezone().isoformat(), 'coords': {'latitude': la, 'longitude': lo, 'speed': 2.7, 'accuracy': 5},
             'battery': {'level': 0.8}, 'extras': {'origen': 'app'}} for t, la, lo in ana[i:i + 6]]
    http('POST', '/api/gps', {'device_id': ID_ANA, 'location': lote})
for t, la, lo in berto:
    http('GET', f'/api/gps?id={ID_BERTO}&lat={la}&lon={lo}&timestamp={int(t)}&batt=70')

st, p, h = http('GET', f'/api/directo?id={ID}')
gente = {g['nombre']: g for g in p['corredores']}
a, o = gente['Ana'], gente['Berto']
ok(st == 200 and p['estado'] == 'en_directo', f"la carrera está en directo ({p['estado']})")
ok(a['situacion'] == 'en_meta' and abs(a.get('tiempo_s', 0) - 3600) < 60, f"Ana en meta: {a.get('tiempo_s', 0) // 60} min (10 km a 10 km/h, sin los 3 min parado en la salida)")
ok(abs(a.get('salida', 0) - (t0 + 180)) <= 30, f"su salida real es cuando empieza a correr ({int(a.get('salida', 0) - t0)} s después de la hora)")
ok(o['situacion'] == 'corriendo' and 4.5 < o['km'] < 5.5 and o.get('lat'), f"Berto corriendo por el km {o['km']}")
ok(p['corredores'][0]['nombre'] == 'Ana', 'el que ya llegó va primero')
texto = json.dumps(p)
ok('dir-' not in texto and TOKEN not in texto, 'lo público no lleva identificadores ni la invitación')

# ---- la portada, la página y lo privado
st, c, _ = http('GET', '/api/carreras')
ok(any(x['id'] == ID and x['estado'] == 'en_directo' for x in c['directos']), 'sale en la portada como «en directo»')
st, pag, _ = http('GET', f'/d/{ID}')
ok(st == 200 and b'directo.js' in pag and b'{{' not in pag, 'la página del directo se sirve')
ok(http('GET', '/d/0000000000')[0] == 404, 'una carrera que no existe da 404')
ok(http('GET', f'/directos/{ID}.dat')[0] == 404, 'los datos de la carrera no se sirven')
st, m, _ = http('GET', '/api/invitado/directos', cookie=galleta)
ok(st == 200 and m['directos'][0]['invitacion'] == TOKEN and m['directos'][0]['ident'] == ID_ANA, 'en Mis rutas: su carrera, su invitación y su móvil')

# ---- el dueño la quita desde el panel
st, _, h = http('POST', '/api/login', {'usuario': 'prueba', 'password': 'clave'})
adm = h['Set-Cookie'].split(';')[0]
st, d, _ = http('POST', '/api/live', {'action': 'rutas_todas'}, adm)
ok(st == 200 and any(x['id'] == ID for x in d['directos']), 'el panel la ve')
st, d, _ = http('POST', '/api/live', {'action': 'directo_borrar', 'id': ID}, adm)
ok(st == 200 and not d['directos'] and http('GET', f'/api/directo?id={ID}')[0] == 404, 'el panel la quita (para todos)')
ok(http('GET', f'/api/gps?id={ID_BERTO}&lat=40.6&lon=-4.2&timestamp={int(time.time())}')[0] == 403, 'su identificador deja de valer')

print('\nTODO BIEN' if not malos else f'\nFALLOS: {len(malos)}')
sys.exit(1 if malos else 0)
