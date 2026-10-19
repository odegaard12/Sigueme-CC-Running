"""Invitados: un amigo con usuario y código que caduca prepara SUS rutas (GPX, avituallamientos)
y descarga el GPX para el reloj. Aislamiento entre invitados y con el panel, ficheros no
públicos, límites y caducidad. Servidor local en una carpeta limpia, datos inventados."""
import atexit, hashlib, json, os, pathlib, subprocess, sys, time, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import RAIZ, carpeta, gpx_inventado
W = carpeta('invitados')
_c = json.loads((W / 'carrera.json').read_text(encoding='utf-8')); _c['fecha'] = '2099-01-01'
(W / 'carrera.json').write_text(json.dumps(_c), encoding='utf-8')     # una carrera lejana: la portada es la de rutas
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
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_crear', 'usuario': 'cleo', 'dias': -1}, admin)
    ok(st == 400, f'rechaza días negativos: {d.get("error")}')
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
    ok(st == 200 and d['dueno'] and d['caduca'] == '2099-12-31', 'el dueño (sesión del panel) entra directo a Mis rutas, sin caducidad')
    st, d, _ = http('GET', '/api/invitado/rutas')
    ok(st == 403, 'sin sesión: 403')
    st, d, _ = http('GET', '/api/reloj.gpx', cookie=ana)
    ok(st == 403, 'el GPX de la carrera del dueño: no con sesión de invitado')
    forjada = 'inv=ana.9999999999.' + 'a' * 64
    st, d, _ = http('GET', '/api/invitado/rutas', cookie=forjada)
    ok(st == 403, 'cookie forjada: 403')

    st, d, _ = http('GET', '/api/invitado/yo', cookie=ana)
    st2, d2, _ = http('GET', '/api/invitado/yo')
    ok(st == 200 and d == {'sesion': True, 'dueno': False} and st2 == 200 and d2 == {'sesion': False, 'dueno': False}, '«¿hay sesión?»: sí con cookie, no sin ella (sin 403)')

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

    # ---- publicar: privado por defecto, recortado, sin decir de quién es
    privada = json.loads((W / 'invitados' / 'ana' / f'{rid}.ruta').read_text(encoding='utf-8'))
    km0, ini0 = privada['distancia_km'], privada['coords'][0]
    st, d, _ = http('GET', '/api/rutas-publicas')
    ok(st == 200 and d['rutas'] == [], 'nada publicado por defecto')
    st, d, _ = http('GET', f'/api/ruta-publica?id={rid}')
    ok(st == 404, 'una ruta privada no se ve en público')
    st, d, _ = http('GET', f'/api/ruta-publica/reloj.gpx?id={rid}')
    ok(st == 404, '  ni se descarga')
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'publica': True, 'ocultar_m': 300, 'autor': 'Ana'}, ben)
    ok(st == 404, 'ben no publica la ruta de ana')
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'publica': True, 'ocultar_m': 5000}, ana)
    ok(st == 400, f'no se pueden ocultar más de 1000 m: {d.get("error")}')
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'publica': True, 'ocultar_m': 300, 'autor': 'Ana'}, ana)
    ok(st == 200 and d['ruta']['publica'] and d['ruta']['publicada'] and d['ruta']['autor'] == 'Ana', 'ana publica su ruta')
    st, d, h = http('GET', '/api/rutas-publicas')
    r0 = d['rutas'][0] if d['rutas'] else {}
    ok(st == 200 and len(d['rutas']) == 1 and 'u' not in r0 and '"ana"' not in json.dumps(d) and 'public' in h.get('Cache-Control', ''),
       'sale en la lista pública, sin decir quién es el usuario y con caché')
    ok(abs(r0['distancia_km'] - (km0 - 0.6)) < 0.05 and r0['traza'] and r0['perfil'] and r0['traza'][0] != [round(ini0[0], 4), round(ini0[1], 4)],
       f"lo público va recortado: {r0['distancia_km']} km de {km0}, y no empieza donde la ruta privada")
    st, p, h = http('GET', f'/api/ruta-publica?id={rid}')
    ok(st == 200 and p['autor'] == 'Ana' and len(p['coords']) > 50 and p['bbox'] and 'u' not in p and 'usuario' not in p,
       'la página pública trae su ruta, perfil y bbox')
    ok(p['coords'][0] != ini0 and abs(p['distancia_km'] - (km0 - 0.6)) < 0.05 and [a['km'] for a in p['avituallamientos']] == [9.7],
       f"  recortada, con el avituallamiento a 9,7 y sin la meta (cae en lo oculto): {p['avituallamientos']}")
    st, cuerpo, h = http('GET', f'/api/ruta-publica/reloj.gpx?id={rid}')
    raiz_p = ET.fromstring(cuerpo)
    ok(st == 200 and 'attachment' in h['Content-Disposition'] and len(raiz_p.findall('g:wpt', ns)) == 1 + 2 * len(p['subidas']),
       f"el GPX público (sin sesión) lleva el mismo recorte: {len(raiz_p.findall('g:wpt', ns))} puntos de control")
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'ocultar_m': 0}, ana)
    st, p0, _ = http('GET', f'/api/ruta-publica?id={rid}')
    ok(p0['distancia_km'] == km0 and len(p0['avituallamientos']) == 2 and p0['coords'][0] == ini0, 'con 0 m ocultos sale entera')
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'ocultar_m': 300}, ana)
    # el dueño ve todo y modera
    st, d, _ = http('POST', '/api/live', {'action': 'rutas_todas'}, admin)
    ok(st == 200 and [x['usuario'] for x in d['rutas'] if x['publica']] == ['ana'] and d['invitados'], 'el panel lista lo publicado')
    st, d, _ = http('POST', '/api/live', {'action': 'rutas_todas'}, ana)
    ok(st == 403, '  y solo con la sesión del panel')
    st, d, _ = http('POST', '/api/live', {'action': 'ruta_moderar', 'usuario': 'ana', 'id': rid, 'accion': 'despublicar'}, admin)
    st2, d2, _ = http('GET', '/api/rutas-publicas')
    ok(st == 200 and d2['rutas'] == [] and http('GET', f'/api/ruta-publica?id={rid}')[0] == 404, 'el dueño la despublica y desaparece')
    st, d, _ = http('GET', f'/api/invitado/ruta?id={rid}', cookie=ana)
    ok(st == 200 and d['ruta']['publica'] is False, '  pero ana conserva su ruta (privada)')
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid, 'publica': True}, ana)
    ok(len(http('GET', '/api/rutas-publicas')[1]['rutas']) == 1, 'ana la vuelve a publicar')

    # ---- la portada y la página de la ruta
    for ruta_web in ('/inicio', '/'):
        r = urllib.request.urlopen(U + ruta_web)
        ok(r.status == 200 and b'inicio.js' in r.read() and 'noindex' in r.headers.get('X-Robots-Tag', ''),
           f'{ruta_web}: la portada de rutas (sin carrera para hoy), con noindex')
    st, pagina, h = http('GET', f'/r/{rid}')
    texto = pagina.decode('utf-8')
    ok(st == 200 and '&lt;b&gt;Mi trail&lt;/b&gt;' in texto and '<b>Mi trail' not in texto and 'ruta.js' in texto,
       'la página de la ruta lleva su nombre en el título (escapado)')
    st, pagina, h = http('GET', '/r/aaaaaaaaaaaa')
    ok(st == 404 and b'ruta.js' in pagina, 'una ruta que no existe: 404, con la página que lo explica')
    for f_, tipo in (('/cartel.css', 'css'), ('/fonts/anton.woff2', 'woff2'), ('/ruta.js', 'javascript'), ('/inicio.js', 'javascript')):
        r = urllib.request.urlopen(U + f_)
        ok(r.status == 200 and tipo in r.headers['Content-Type'], f'{f_} se sirve ({r.headers["Content-Type"]})')
    r = urllib.request.urlopen(U + '/index.html')
    ok(r.status == 200 and b'inicio.js' not in r.read(), '/index.html sigue siendo la página de la carrera')
    # caducar = desaparecer de la web al momento (sin esperar a la purga)
    fichero = W / 'invitados' / 'usuarios.dat'
    datos = json.loads(fichero.read_text(encoding='utf-8'))
    datos['usuarios']['ana']['caduca'] = (date.today() - timedelta(days=1)).isoformat()
    fichero.write_text(json.dumps(datos), encoding='utf-8')
    ok(http('GET', '/api/rutas-publicas')[1]['rutas'] == [] and http('GET', f'/api/ruta-publica?id={rid}')[0] == 404,
       'al caducar el acceso de ana, su ruta deja de verse en la web')
    datos['usuarios']['ana']['caduca'] = (date.today() + timedelta(days=30)).isoformat()
    fichero.write_text(json.dumps(datos), encoding='utf-8')
    ok(len(http('GET', '/api/rutas-publicas')[1]['rutas']) == 1, '  y vuelve al renovarlo')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_crear', 'usuario': 'oscar', 'dias': 0}, admin)
    g = [x for x in d['invitados'] if x['usuario'] == 'oscar'][0]
    ok(st == 200 and g['sin_caducidad'] and g['caduca'] == '2099-12-31', 'una cuenta sin caducidad (la del dueño)')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_renovar', 'usuario': 'oscar', 'dias': 30}, admin)
    ok(d['caduca'] == '2099-12-31', '  renovarla no la toca')
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_borrar', 'usuario': 'oscar'}, admin)
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_crear', 'usuario': 'dueno'}, admin)
    ok(st == 400, 'el usuario «dueno» está reservado')

    # ---- los datos no se sirven como ficheros
    for f in ('/invitados/publicas.dat', '/invitados/usuarios.dat', f'/invitados/ana/{rid}.ruta', '/invitados/', '/invitados', '/INVITADOS/usuarios.dat', '/invitados/../server.py'):
        try:
            urllib.request.urlopen(U + f); ok(False, f'{f} se sirve')
        except urllib.error.HTTPError as e:
            ok(e.code in (403, 404), f'{f} no se sirve ({e.code})')
    st, pagina, h = http('GET', '/mis-rutas.html')
    ok(st == 200 and 'noindex' in h.get('X-Robots-Tag', '') and b'mis-rutas.js' in pagina, 'la página de invitados se sirve (con noindex)')
    r = urllib.request.urlopen(U + '/rutas.html')
    ok(r.status == 200 and r.url.endswith('/mis-rutas.html'), 'el nombre viejo /rutas.html redirige a /mis-rutas.html')
    st, d, _ = http('GET', '/api/carreras')
    ok(st == 200 and isinstance(d['carreras'], list) and 'proxima' in d, '/api/carreras (público) para la portada')

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
    ok(http('GET', '/api/rutas-publicas')[1]['rutas'] == [], '  y si estaba publicada, desaparece de la web')

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
    ok(st == 200 and d['invitados'] == [] and not (W / 'invitados' / 'ana').exists(), f"quitar a ana borra también sus rutas: quedan {[x['usuario'] for x in d.get('invitados', [])]}, carpeta {(W / 'invitados' / 'ana').exists()}")
    st, d, _ = http('POST', '/api/live', {'action': 'invitado_borrar', 'usuario': 'ana'}, admin)
    ok(st == 400, 'quitar a quien no existe: 400')

    # ---- el dueño: sus propias rutas, sin crear cuenta (con la sesión del panel o con su usuario y clave)
    st, d, h = http('POST', '/api/invitado/login', {'usuario': 'prueba', 'codigo': 'clave'}, origen=False)
    dueno = h.get('Set-Cookie', '').split(';')[0]
    ok(st == 200 and dueno.startswith('inv='), 'el dueño entra en Mis rutas con su usuario y su clave del panel')
    st, d, _ = http('POST', '/api/invitado/login', {'usuario': 'prueba', 'codigo': 'mala'}, origen=False)
    ok(st == 403, '  y con la clave mala, no')
    st, d, _ = http('POST', '/api/invitado/gpx?nombre=Mi%20casa', gpx_inventado(12), dueno, tipo='application/gpx+xml')
    ok(st == 200, 'el dueño sube una ruta suya')
    rid_d = d['ruta']['id']
    st, d, _ = http('POST', '/api/invitado/ruta', {'id': rid_d, 'publica': True, 'ocultar_m': 300}, admin)     # vale la sesión del panel
    ok(st == 200 and d['ruta']['publica'], '  y la publica (también vale la sesión del panel, sin otra cookie)')
    ok(any(x['id'] == rid_d for x in http('GET', '/api/rutas-publicas')[1]['rutas']), 'sale en la portada')
    st, d, _ = http('POST', '/api/live', {'action': 'rutas_todas'}, admin)
    ok(any(x['usuario'] == 'dueno' and x['id'] == rid_d for x in d['rutas']) and all(g['usuario'] != 'dueno' for g in d['invitados']),
       'el panel la ve como del dueño, y «dueno» no cuenta como invitado')
    http('POST', '/api/live', {'action': 'invitados'}, admin)                                                  # purga
    ok((W / 'invitados' / 'dueno').exists(), 'la purga no borra la carpeta del dueño')
    st, d, _ = http('POST', '/api/live', {'action': 'ruta_moderar', 'usuario': 'dueno', 'id': rid_d, 'accion': 'borrar'}, admin)
    ok(st == 200 and rid_d not in [x['id'] for x in http('GET', '/api/rutas-publicas')[1]['rutas']], 'el dueño la borra desde el panel')
    # el nombre del sitio sale del dominio
    r = urllib.request.urlopen(urllib.request.Request(U + '/inicio', headers={'Host': 'odegaard12.online'}))
    pg = r.read().decode('utf-8')
    ok('Rutas<br>odegaard12' in pg and '<title>Rutas odegaard12</title>' in pg, 'la portada se titula con el dominio: «Rutas odegaard12»')
    ok('Tipografía' not in pg, '  y sin el crédito de la tipografía')

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
