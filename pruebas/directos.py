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

# ---- v1.68: parciales por km (Ana a 10 km/h: unos 6 min por km)
ana_cid = next(g['cid'] for g in p['corredores'] if g['nombre'] == 'Ana')
st, pa, _ = http('GET', f'/api/directo/parciales?id={ID}&cid={ana_cid}')
parc = pa.get('parciales') or []
ok(st == 200 and len(parc) >= 9 and all(300 <= s <= 420 for s in parc[1:-1]), f'parciales de Ana: {len(parc)} km, unos 6 min cada uno ({parc[:3]}…)')
ok(http('GET', f'/api/directo/parciales?id={ID}&cid=00000000')[0] == 404, 'un corredor que no existe da 404')

# ---- v1.69: el GPX de la carrera en directo
r = urllib.request.urlopen(U + f'/d/{ID}/ruta.gpx'); gx = r.read()
ok(r.status == 200 and b'<gpx' in gx and b'<trkpt' in gx and 'attachment' in r.headers.get('Content-Disposition', ''), 'el GPX de la carrera en directo se baja')
ok(http('GET', '/d/0000000000/ruta.gpx')[0] == 404, 'de una carrera que no existe, 404')

# ---- v1.70: seguir la carrera (la campana del directo)
sub_seg = {'endpoint': 'https://web.push.apple.com/seguidor', 'keys': {'p256dh': 'x', 'auth': 'y'}}
st, _, _ = http('POST', '/api/push/directo', {'id': ID, 'sub': sub_seg})
ok(st == 200, 'un móvil se apunta a los avisos de la carrera en directo')
st, _, _ = http('POST', '/api/push/directo', {'id': '0000000000', 'sub': sub_seg})
ok(st == 400, 'a una carrera que no existe, no')
st, _, _ = http('POST', '/api/push/directo', {'id': ID, 'sub': {'endpoint': 'https://evil.example/x', 'keys': {'p256dh': 'x', 'auth': 'y'}}})
ok(st == 400, 'una suscripción que no es de un servicio de avisos, no')
st, _, _ = http('POST', '/api/push/directo/baja', {'id': ID, 'endpoint': sub_seg['endpoint']})
ok(st == 200, 'y se quita')

# ---- la portada, la página y lo privado
st, c, _ = http('GET', '/api/carreras')
ok(any(x['id'] == ID and x['estado'] == 'en_directo' for x in c['directos']), 'sale en la portada como «en directo»')
st, pag, _ = http('GET', f'/d/{ID}')
ok(st == 200 and b'directo.js' in pag and b'{{' not in pag, 'la página del directo se sirve')
ok(http('GET', '/d/0000000000')[0] == 404, 'una carrera que no existe da 404')
ok(http('GET', f'/directos/{ID}.dat')[0] == 404, 'los datos de la carrera no se sirven')
st, m, _ = http('GET', '/api/invitado/directos', cookie=galleta)
ok(st == 200 and m['directos'][0]['invitacion'] == TOKEN and m['directos'][0]['ident'] == ID_ANA, 'en Mis rutas: su carrera, su invitación y su móvil')

# ---- avisos de subidas en el iPhone: solo con un identificador de verdad
sub = {'endpoint': 'https://web.push.apple.com/abc', 'keys': {'p256dh': 'x', 'auth': 'y'}}
st, _, _ = http('POST', '/api/push/mio', {'ident': ID_ANA, 'sub': sub})
ok(st == 200, 'con su identificador, el móvil se apunta a los avisos de subidas')
st, _, _ = http('POST', '/api/push/mio', {'ident': 'dir-inventado-123456789012', 'sub': sub})
ok(st == 403, 'con un identificador inventado, no')
st, _, _ = http('POST', '/api/push/mio', {'ident': ID_ANA, 'sub': {'endpoint': 'https://evil.example/x', 'keys': {'p256dh': 'x', 'auth': 'y'}}})
ok(st == 400, 'una suscripción que no es de un servicio de avisos, no')
st, _, _ = http('POST', '/api/push/mio/baja', {'ident': ID_ANA, 'endpoint': sub['endpoint']})
ok(st == 200, 'y se da de baja')

# ---- v1.57: otro usuario ve la carrera abierta y se apunta sin enlace; retirarse; aviso de prueba
codigo_luis = inv.crear(str(W), 'luis', dias=30, nombre='Luis')
st, _, h = http('POST', '/api/invitado/login', {'usuario': 'luis', 'codigo': codigo_luis})
galleta_luis = h['Set-Cookie'].split(';')[0]
st, y, _ = http('GET', '/api/invitado/yo', cookie=galleta_luis)
ok(st == 200 and y.get('usuario') == 'luis', 'con sesión, la web sabe el usuario para ponerlo arriba')
st, y, _ = http('GET', '/api/invitado/yo')
ok(st == 200 and not y.get('usuario'), 'sin sesión no da ningún usuario')
st, ab, _ = http('GET', '/api/invitado/abiertas', cookie=galleta_luis)
ok(st == 200 and any(x['id'] == ID for x in ab['abiertas']), 'otro usuario ve la carrera abierta')
ok('invitacion' not in json.dumps(ab) and 'dir-' not in json.dumps(ab), 'sin la invitación ni identificadores')
st, ab_ana, _ = http('GET', '/api/invitado/abiertas', cookie=galleta)
ok(st == 200 and not any(x['id'] == ID for x in ab_ana['abiertas']), 'quien la creó no la ve como abierta (ya es suya)')
st, _, _ = http('POST', '/api/invitado/apuntarme', {'id': ID, 'nombre': 'Luis'})
ok(st == 403, 'sin sesión no se apunta')
st, d, _ = http('POST', '/api/invitado/apuntarme', {'id': '0000000000', 'nombre': 'Luis'}, galleta_luis)
ok(st == 404, 'una carrera que no existe, no')
st, d, _ = http('POST', '/api/invitado/apuntarme', {'id': ID, 'nombre': 'Luis'}, galleta_luis)
ID_LUIS = d.get('ident', '')
ok(st == 200 and ID_LUIS.startswith('dir-') and ID_LUIS not in (ID_ANA, ID_BERTO), 'con cuenta se apunta sin enlace y recibe SU identificador')
st, d, _ = http('POST', '/api/invitado/apuntarme', {'id': ID, 'nombre': 'Luis'}, galleta_luis)
ok(st == 200 and d['ident'] == ID_LUIS, 'apuntarse dos veces no duplica')
st, ab, _ = http('GET', '/api/invitado/abiertas', cookie=galleta_luis)
ok(not any(x['id'] == ID for x in ab['abiertas']), 'ya apuntado, deja de salir como abierta')
st, m, _ = http('GET', '/api/invitado/directos', cookie=galleta_luis)
ok(st == 200 and m['directos'][0]['ident'] == ID_LUIS and m['directos'][0]['invitacion'] is None, 'sale en sus carreras con su móvil, sin la invitación')
http('GET', f'/api/gps?id={ID_LUIS}&lat=40.6&lon=-4.2&timestamp={int(time.time())}')
st, p, _ = http('GET', f'/api/directo?id={ID}')
ok(any(g['nombre'] == 'Luis' for g in p['corredores']), 'Luis sale en la carrera')
st, _, _ = http('POST', '/api/invitado/retirarme', {'ident': 'dir-inventado-123456789012'})
ok(st == 403, 'retirarse con un identificador inventado, no')
st, _, _ = http('POST', '/api/invitado/retirarme', {'ident': ID_LUIS})
ok(st == 200, 'Luis se retira (basta su identificador)')
st, _, _ = http('POST', '/api/invitado/retirarme', {'ident': ID_LUIS})
ok(st == 200, 'retirarse otra vez no da error')
http('GET', f'/api/gps?id={ID_LUIS}&lat=40.61&lon=-4.21&timestamp={int(time.time()) + 5}')
st, p, _ = http('GET', f'/api/directo?id={ID}')
gl = {g['nombre']: g for g in p['corredores']}
ok(gl['Luis']['situacion'] == 'retirado' and gl['Luis'].get('lat') is None, 'retirado: sin posición en el mapa y sus puntos ya no cuentan')
ok(p['corredores'][-1]['nombre'] == 'Luis' and p['estado'] == 'en_directo', 'el retirado va al final y la carrera sigue en directo')
ok(gl['Ana']['situacion'] == 'en_meta' and gl['Berto']['situacion'] == 'corriendo', 'los demás siguen igual')
st, c, _ = http('GET', '/api/carreras')
ok(not any('Luis' in [g['nombre'] for g in x['corredores']] for x in c['directos'] if x['id'] == ID), 'la portada no lo lista')
st, _, _ = http('POST', '/api/push/mio/prueba', {'ident': ID_LUIS})
ok(st == 400, 'aviso de prueba sin avisos activados: avisa')
st, _, _ = http('POST', '/api/push/mio/prueba', {'ident': 'dir-inventado-123456789012'})
ok(st == 403, 'aviso de prueba con identificador inventado, no')

# ---- v1.65: volver a la carrera y no retirarse tras la meta
st, d, _ = http('POST', '/api/invitado/volver', {'ident': ID_LUIS})
ok(st == 200, 'Luis vuelve a la carrera (deshace «Retirarme»)')
st, p, _ = http('GET', f'/api/directo?id={ID}')
ok(next(g for g in p['corredores'] if g['nombre'] == 'Luis')['situacion'] != 'retirado', 'ya no sale como retirado')
st, m, _ = http('GET', '/api/invitado/directos', cookie=galleta_luis)
ok(st == 200 and m['directos'][0]['retirado'] is False, 'en sus carreras ya no consta como retirado')
st, d, _ = http('POST', '/api/invitado/volver', {'ident': 'dir-inventado-123456789012'})
ok(st == 403, 'volver con un identificador inventado, no')
st, d, _ = http('POST', '/api/invitado/retirarme', {'ident': ID_ANA})
ok(st == 400 and 'meta' in d.get('error', ''), 'quien ya llegó a meta no se puede retirar (su tiempo se queda)')
http('POST', '/api/invitado/retirarme', {'ident': ID_LUIS})
st, m, _ = http('GET', '/api/invitado/directos', cookie=galleta_luis)
ok(m['directos'][0]['retirado'] is True, 'retirado otra vez: en sus carreras consta como retirado')

# ---- v1.62: foto de cada corredor
import struct, zlib
def png_de(w, h):
    crudo = b''.join(b'\x00' + b'\x80\x80\x80' * w for _ in range(h))
    trozo = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + trozo(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + trozo(b'IDAT', zlib.compress(crudo)) + trozo(b'IEND', b'')
def foto_post(ident, cuerpo, quitar=False):
    cab = {'Origin': U, 'X-Ident': ident, 'Content-Type': 'image/png'}
    if quitar: cab['X-Quitar'] = '1'
    try:
        return urllib.request.urlopen(urllib.request.Request(U + '/api/invitado/foto', cuerpo, cab, method='POST'), timeout=30).status
    except urllib.error.HTTPError as e:
        return e.code
ok(foto_post('dir-inventado-123456789012', png_de(16, 16)) == 403, 'una foto con un identificador inventado, no')
ok(foto_post(ID_BERTO, b'esto no es una foto') == 400, 'lo que no es un PNG, no')
ok(foto_post(ID_BERTO, png_de(2000, 2000)) == 400, 'un PNG que declara medidas enormes, no')
ok(foto_post(ID_BERTO, png_de(256, 256)) == 200, 'el corredor sube su foto')
st, p, _ = http('GET', f'/api/directo?id={ID}')
berto = next(g for g in p['corredores'] if g['nombre'] == 'Berto')
ok(berto.get('foto') and 'dir-' not in json.dumps(p), 'sale en lo público (sin identificadores)')
r = urllib.request.urlopen(U + f"/d/{ID}/foto/{berto['cid']}.png")
ok(r.status == 200 and r.headers['Content-Type'] == 'image/png' and r.read()[:8] == b'\x89PNG\r\n\x1a\n', 'y la foto se sirve como PNG')
ok(foto_post(ID_BERTO, b'', quitar=True) == 200, 'el corredor quita su foto')
st, p, _ = http('GET', f'/api/directo?id={ID}')
ok(not next(g for g in p['corredores'] if g['nombre'] == 'Berto').get('foto') and http('GET', f"/d/{ID}/foto/{berto['cid']}.png")[0] == 404, 'ya no sale en lo público ni se sirve')
ok(foto_post(ID_BERTO, png_de(256, 256)) == 200, 'puede subir otra')

# ---- v1.58: una carrera terminada (todos llegaron o se retiraron) no admite a nadie, aunque falten horas del límite
st, d, _ = http('POST', '/api/invitado/gpx?nombre=Corta', gpx_inventado(km=10), galleta_luis, 'application/gpx+xml')
st, d, _ = http('POST', '/api/invitado/directo', {'ruta': d['ruta']['id'], 'fecha': salida.strftime('%Y-%m-%d'), 'hora': salida.strftime('%H:%M'), 'nombre': 'Luis'}, galleta_luis)
ID2, TOKEN2, IDENT2 = d['id'], d['invitacion'], d['ident']
st, ab, _ = http('GET', '/api/invitado/abiertas', cookie=galleta)
ok(any(x['id'] == ID2 for x in ab['abiertas']), 'una carrera sin empezar sí sale como abierta')
http('POST', '/api/invitado/retirarme', {'ident': IDENT2})
st, ab, _ = http('GET', '/api/invitado/abiertas', cookie=galleta)
ok(not any(x['id'] == ID2 for x in ab['abiertas']), 'terminada (su único corredor se retiró): ya no sale como abierta')
st, _, _ = http('POST', '/api/invitado/apuntarme', {'id': ID2, 'nombre': 'Ana'}, galleta)
ok(st == 400, 'y no se puede apuntar')
st, _, _ = http('POST', '/api/invitado/unirse', {'id': ID2, 'token': TOKEN2, 'nombre': 'Tarde'})
ok(st == 400, 'ni con el enlace de invitación')
http('POST', '/api/invitado/directo', {'accion': 'borrar', 'id': ID2}, galleta_luis)

# ---- v1.66: un invitado que caduca sale de las carreras en directo (se queda el recorrido)
todos = inv._usuarios_seguro(str(W)); todos['luis']['caduca'] = '2000-01-01'; inv._guardar(str(W), todos)
http('POST', '/api/invitado/login', {'usuario': 'ana', 'codigo': codigo})         # entrar lanza la purga
st, p, _ = http('GET', f'/api/directo?id={ID}')
ok(st == 200 and 'Luis' not in [g['nombre'] for g in p['corredores']] and len(p['ruta']) > 10, 'Luis caducado: fuera de la carrera (nombre, tiempo, puntos); el recorrido se queda')
ok(http('GET', f'/api/gps?id={ID_LUIS}&lat=40.6&lon=-4.2&timestamp={int(time.time())}')[0] == 403, 'su identificador ya no vale')
ok({'Ana', 'Berto'} <= {g['nombre'] for g in p['corredores']}, 'los demás siguen igual')

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
