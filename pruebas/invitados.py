"""Invitados: un amigo con usuario y código que caduca prepara SUS rutas (GPX, avituallamientos)
y descarga el GPX para el reloj. Aislamiento entre invitados y con el panel, ficheros no
públicos, límites y caducidad. Servidor local en una carpeta limpia, datos inventados."""
import atexit, hashlib, json, os, pathlib, subprocess, sys, time, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import RAIZ, carpeta, gpx_inventado
W = carpeta('invitados')
sys.path.insert(0, str(W / 'herramientas'))
import invitados as inv
malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)

sal = os.urandom(16)
env = dict(os.environ, ADMIN_USER='prueba', BIND_HOST='127.0.0.1', PYTHONIOENCODING='utf-8',
           ADMIN_HASH='scrypt:' + sal.hex() + ':' + hashlib.scrypt(b'clave', salt=sal, n=2**14, r=8, p=1, dklen=32).hex())
PORT = 8795
srv = subprocess.Popen([sys.executable, 'server.py', str(PORT)], cwd=W, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
atexit.register(srv.terminate)
U = f'http://127.0.0.1:{PORT}'
for _ in range(60):
    try:
        urllib.request.urlopen(U + '/robots.txt', timeout=1); break
    except Exception:
        time.sleep(0.3)


def http(metodo, ruta, cuerpo=None, cookie='', origen=True, tipo='application/json'):
    cab = {'Content-Type': tipo}
    if origen: cab['Origin'] = U
    if cookie: cab['Cookie'] = cookie
    if cuerpo is not None and not isinstance(cuerpo, bytes): cuerpo = json.dumps(cuerpo).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(U + ruta, cuerpo, cab, method=metodo), timeout=60)
        st, datos, h = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        st, datos, h = e.code, e.read(), e.headers
    try:
        return st, json.loads(datos), h
    except ValueError:
        return st, datos, h


try:
    # ---- el dueño crea invitados desde el panel
    st, d, h = http('POST', '/api/login', {'usuario': 'prueba', 'password': 'clave'})
    admin = h['Set-Cookie'].split(';')[0]
    st, d, _ = http('POST', '/api/live', {'action': 'invitados'}, admin)
    ok(st == 200 and d['invitados'] == [], 'sin invitados al principio')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_crear', 'usuario': 'ana', 'dias': 30}, admin)
    codigo_ana = d.get('codigo', '')
    ok(st == 200 and len(codigo_ana) == 14 and codigo_ana.count('-') == 2, f'crear ana: código de {len(codigo_ana)} caracteres, caduca {d["invitados"][0]["caduca"]}')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_crear', 'usuario': 'ben', 'dias': 30}, admin)
    codigo_ben = d.get('codigo', '')
    ok(st == 200, 'crear ben')
    for malo in ('ana', 'Ad min', 'admin', 'x', 'a' * 30):
        st, d, _ = http('POST', '/api/live', {'action': 'invitado_crear', 'usuario': malo}, admin)
        ok(st == 400, f'rechaza el usuario {malo!r}: {d.get("error")}')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_crear', 'usuario': 'cleo', 'dias': 0}, admin)
    ok(st == 400, f'rechaza 0 días: {d.get("error")}')
    st, d, _ = http('POST', '/api/live', {'action': 'invitados'})
    ok(st == 403, 'el listado sin sesión del panel: 403')
    datos_disco = (W / 'invitados' / 'usuarios.dat').read_text(encoding='utf-8')
    ok(codigo_ana not in datos_disco and codigo_ana.replace('-', '') not in datos_disco and 'scrypt:' in datos_disco,
       'en disco solo queda el hash, no el código')
    if os.name == 'posix':
        ok(oct((W / 'invitados' / 'usuarios.dat').stat().st_mode & 0o777) == '0o600', 'usuarios.dat solo lo lee su dueño (600)')

    # ---- entrar
    st, d, _ = http('POST', '/api/invitado/login', {'usuario': 'ana', 'codigo': 'AAAA-AAAA-AAAA'}, origen=False)
    ok(st == 403, 'código malo: 403')
    st, d, _ = http('POST', '/api/invitado/login', {'usuario': 'nadie', 'codigo': codigo_ana}, origen=False)
    ok(st == 403, 'usuario que no existe: 403')
    st, d, h = http('POST', '/api/invitado/login', {'usuario': 'Ana', 'codigo': codigo_ana.replace('-', '').lower()}, origen=False)
    ana = h.get('Set-Cookie', '').split(';')[0]
    ok(st == 200 and ana.startswith('inv=') and 'HttpOnly' in h['Set-Cookie'] and 'Path=/api/invitado' in h['Set-Cookie'],
       'entrar con el código sin guiones y en minúsculas; cookie HttpOnly solo de /api/invitado')
    st, d, h = http('POST', '/api/invitado/login', {'usuario': 'ben', 'codigo': codigo_ben}, origen=False)
    ben = h.get('Set-Cookie', '').split(';')[0]
    ok(st == 200, 'entra ben')

    # ---- ni el panel vale aquí ni la cookie del invitado vale en el panel
    st, d, _ = http('POST', '/api/live', {'action': 'config'}, ana)
    ok(st == 403, 'la sesión de invitado no abre el panel')
    st, d, _ = http('POST', '/api/live', {'action': 'invitados'}, ana)
    ok(st == 403, '  ni lista a los invitados')
    st, d, _ = http('GET', '/api/invitado/rutas', cookie=admin)
    ok(st == 403, 'la sesión del panel no abre el espacio de invitado')
    st, d, _ = http('GET', '/api/invitado/rutas')
    ok(st == 403, 'sin sesión: 403')
    st, d, _ = http('GET', '/api/reloj.gpx', cookie=ana)
    ok(st == 403, 'el GPX de la carrera del dueño: no con sesión de invitado')
    forjada = 'inv=ana.9999999999.' + 'a' * 64
    st, d, _ = http('GET', '/api/invitado/rutas', cookie=forjada)
    ok(st == 403, 'cookie forjada: 403')

    st, d, _ = http('GET', '/api/invitado/yo', cookie=ana)
    st2, d2, _ = http('GET', '/api/invitado/yo')
    ok(st == 200 and d == {'sesion': True} and st2 == 200 and d2 == {'sesion': False}, '«¿hay sesión?»: sí con cookie, no sin ella (sin 403)')

    # ---- subir una ruta
    st, d, _ = http('GET', '/api/invitado/rutas', cookie=ana)
    ok(st == 200 and d['usuario'] == 'ana' and d['rutas'] == [] and d['caduca'] == (date.today() + timedelta(days=30)).isoformat(), 'ana sin rutas y con su fecha de caducidad')
    gpx = gpx_inventado(30)
    st, d, _ = http('POST', '/api/invitado/gpx?nombre=Mi%20ruta', gpx, ana, origen=False, tipo='application/gpx+xml')
    ok(st == 403, 'subir sin Origin (CSRF): 403')
    st, d, _ = http('POST', '/api/invitado/gpx?nombre=Mi%20ruta', b'no es un gpx', ana, tipo='application/gpx+xml')
    ok(st == 400, f'un GPX roto: 400 ({d.get("error")})')
    st, d, _ = http('POST', '/api/invitado/gpx?nombre=Mi%20ruta', gpx, ana, tipo='application/gpx+xml')
    ruta = d.get('ruta', {})
    ok(st == 200 and 27 <= ruta['distancia_km'] <= 33 and ruta['desnivel_m'] > 100 and ruta['subidas'] and 20 < len(ruta['perfil']) <= 160,
       f"ruta subida: {ruta.get('distancia_km')} km, +{ruta.get('desnivel_m')} m, {len(ruta.get('subidas', []))} subidas")
    rid = ruta['id']
    ok(not any(p.suffix == '.gpx' for p in W.rglob('*')), 'el GPX original no se guarda')
    st, d, _ = http('GET', '/api/invitado/rutas', cookie=ana)
    ok(len(d['rutas']) == 1 and d['rutas'][0]['nombre'] == 'Mi ruta', 'sale en su lista')

    # ---- avituallamientos y el GPX del reloj
    avit = [{'name': 'Avit 1', 'km': 10}, {'name': 'Meta', 'km': 30}]
    for malo in ([{'name': 'x', 'km': 999}], [{'name': '', 'km': 5}], [{'name': 'x'}], 'no lista', [{'name': 'x', 'km': 1}] * 31):
        st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'avituallamientos': malo}, ana)
        ok(st == 400, f'rechaza avituallamientos malos: {str(malo)[:30]}')
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'nombre': '<b>Mi trail</b>', 'avituallamientos': avit}, ana)
    ok(st == 200 and d['ruta']['avituallamientos'] == avit and d['ruta']['nombre'] == '<b>Mi trail</b>', 'guarda avituallamientos y nombre (el texto se queda como texto)')
    nsub = len(d['ruta']['subidas'])
    st, cuerpo, h = http('GET', f'/api/invitado/reloj.gpx?id={rid}', cookie=ana)
    raiz = ET.fromstring(cuerpo)
    ns = {'g': 'http://www.topografix.com/GPX/1/1'}
    wpts, trk = raiz.findall('g:wpt', ns), raiz.findall('.//g:trkpt', ns)
    ok(st == 200 and 'attachment' in h['Content-Disposition'] and 'b-mi-trail-b' in h['Content-Disposition'],
       f"GPX del reloj: {h['Content-Disposition']}")
    ok(len(wpts) == 2 + 2 * nsub and len(trk) > 100 and all(p.find('g:ele', ns) is not None for p in trk + wpts),
       f'  {len(wpts)} puntos de control (2 avituallamientos, {nsub} subidas) y {len(trk)} puntos con altitud')

    # ---- aislamiento entre invitados
    st, d, _ = http('GET', '/api/invitado/rutas', cookie=ben)
    ok(d['rutas'] == [] and d['usuario'] == 'ben', 'ben no ve las rutas de ana')
    for ruta_ben in (f'/api/invitado/ruta?id={rid}', f'/api/invitado/reloj.gpx?id={rid}'):
        st, d, _ = http('GET', ruta_ben, cookie=ben)
        ok(st == 404, f'ben no abre la ruta de ana: {ruta_ben.split("?")[0]} → {st}')
    st, d, _ = http('POST', '/api/invitado/borrar', {'id': rid}, ben)
    ok(st == 404 and http('GET', f'/api/invitado/ruta?id={rid}', cookie=ana)[0] == 200, 'ben no borra la ruta de ana')
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'nombre': 'robada'}, ben)
    ok(st == 404 and http('GET', f'/api/invitado/ruta?id={rid}', cookie=ana)[1]['ruta']['nombre'] == '<b>Mi trail</b>', 'ben no edita la ruta de ana')
    for malo in ('../../usuarios', '..%2f..%2fcarrera', 'xx', 'A' * 12, ''):
        st, d, _ = http('GET', f'/api/invitado/ruta?id={malo}', cookie=ana)
        ok(st in (400, 404), f'id raro {malo!r}: {st}')

    # ---- los datos no se sirven como ficheros
    for f in ('/invitados/usuarios.dat', f'/invitados/ana/{rid}.ruta', '/invitados/', '/invitados', '/INVITADOS/usuarios.dat', '/invitados/../server.py'):
        try:
            urllib.request.urlopen(U + f); ok(False, f'{f} se sirve')
        except urllib.error.HTTPError as e:
            ok(e.code in (403, 404), f'{f} no se sirve ({e.code})')
    st, pagina, h = http('GET', '/rutas.html')
    ok(st == 200 and 'noindex' in h.get('X-Robots-Tag', '') and b'rutas.js' in pagina, 'la página de invitados se sirve (con noindex)')

    # ---- límites: 5 rutas por invitado; GPX demasiado grande
    for i in range(4):
        st, d, _ = http('POST', f'/api/invitado/gpx?nombre=r{i}', gpx_inventado(10 + i), ana, tipo='application/gpx+xml')
        ok(st == 200, f'ruta {i + 2} de 5')
    st, d, _ = http('POST', '/api/invitado/gpx?nombre=otra', gpx, ana, tipo='application/gpx+xml')
    ok(st == 400 and '5 rutas' in d['error'], f'la sexta: {d.get("error")}')
    try:
        inv.crear_ruta(str(W), 'ben', 'x', b'x' * (inv.MAX_GPX + 1), lambda *a: None, lambda *a: None)
        ok(False, 'GPX enorme aceptado')
    except ValueError as e:
        ok(True, f'GPX enorme: {e}')
    st, d, _ = http('POST', '/api/invitado/borrar', {'id': rid}, ana)
    ok(st == 200 and http('GET', f'/api/invitado/ruta?id={rid}', cookie=ana)[0] == 404, 'borrar una ruta suya')

    # ---- renovar, código nuevo, caducidad y purga
    f = W / 'invitados' / 'usuarios.dat'
    def poner_caducidad(usuario, dias):
        datos = json.loads(f.read_text(encoding='utf-8'))
        datos['usuarios'][usuario]['caduca'] = (date.today() + timedelta(days=dias)).isoformat()
        f.write_text(json.dumps(datos), encoding='utf-8')
    poner_caducidad('ben', -1)
    st, d, _ = http('POST', '/api/invitado/login', {'usuario': 'ben', 'codigo': codigo_ben}, origen=False)
    ok(st == 403, 'ben caducado ayer: no entra')
    st, d, _ = http('GET', '/api/invitado/rutas', cookie=ben)
    ok(st == 403, '  y su sesión de antes tampoco vale')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_renovar', 'usuario': 'ben', 'dias': 30}, admin)
    ok(st == 200 and d['caduca'] == (date.today() + timedelta(days=30)).isoformat(), f'renovar 30 días: {d.get("caduca")}')
    st, d, _ = http('POST', '/api/invitado/login', {'usuario': 'ben', 'codigo': codigo_ben}, origen=False)
    ok(st == 200, '  y vuelve a entrar')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_codigo', 'usuario': 'ana'}, admin)
    nuevo = d['codigo']
    st, _, _ = http('POST', '/api/invitado/login', {'usuario': 'ana', 'codigo': codigo_ana}, origen=False)
    ok(nuevo != codigo_ana and st == 403, 'código nuevo: el viejo deja de valer')
    st, _, _ = http('POST', '/api/invitado/login', {'usuario': 'ana', 'codigo': nuevo}, origen=False)
    ok(st == 200, '  y el nuevo vale')
    poner_caducidad('ben', -10)
    (W / 'invitados' / 'ben').mkdir(exist_ok=True)
    (W / 'invitados' / 'ben' / '0123456789ab.ruta').write_text('{}', encoding='utf-8')
    (W / 'invitados' / 'fantasma').mkdir()
    st, _, _ = http('POST', '/api/invitado/login', {'usuario': 'ana', 'codigo': nuevo}, origen=False)   # entrar purga
    ok('ben' not in f.read_text(encoding='utf-8') and not (W / 'invitados' / 'ben').exists() and not (W / 'invitados' / 'fantasma').exists(),
       'a los 7 días de caducar se borran su usuario y sus rutas (y carpetas huérfanas)')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_borrar', 'usuario': 'ana'}, admin)
    ok(st == 200 and d['invitados'] == [] and not (W / 'invitados' / 'ana').exists(), 'quitar a ana borra también sus rutas')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_borrar', 'usuario': 'ana'}, admin)
    ok(st == 400, 'quitar a quien no existe: 400')

    # ---- freno a la fuerza bruta
    codigos = []
    for i in range(12):
        st, _, _ = http('POST', '/api/invitado/login', {'usuario': 'ana', 'codigo': f'MALO-{i:04d}-XXXX'}, origen=False)
        codigos.append(st)
    ok(429 in codigos and codigos[-1] == 429, f'tras muchos fallos, 429: {codigos}')
finally:
    srv.terminate()
print('TODO BIEN' if not malos else f'FALLAN {len(malos)}: {malos}')
sys.exit(1 if malos else 0)
