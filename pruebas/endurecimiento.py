"""Endurecimiento del servidor (v1.30.0): cada defensa de la auditoría, probada directamente sobre las funciones."""
import os, pathlib, sys, tempfile, json

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parent / 'herramientas'))
import server, invitados, generar_resultado

resultados = []


def ok(cond, texto):
    resultados.append(bool(cond))
    print(('OK   ' if cond else 'MAL  ') + texto)


# números del GPS: ni infinitos, ni NaN, ni enteros enormes
ok(server._numero('1e999') is None and server._numero('nan') is None and server._numero('inf') is None, 'infinitos y NaN no pasan como número')
ok(server._numero('1' * 400) is None or server._numero('1' * 400) != float('inf'), 'un entero de 400 cifras no tumba el hilo')
ok(server._numero('3.5') == 3.5 and server._numero(None) is None, 'los números normales siguen valiendo')

# IPv6: un /64 cuenta como una sola persona
ok(server._clave_ip('2001:db8:1:2::1') == server._clave_ip('2001:db8:1:2:ffff::9'), 'dos direcciones del mismo /64 son la misma clave')
ok(server._clave_ip('2001:db8:1:3::1') != server._clave_ip('2001:db8:1:2::1'), '/64 distintos, claves distintas')
ok(server._clave_ip('203.0.113.5') == '203.0.113.5', 'IPv4 sin cambios')

# un punto GPS reenviado (respuesta perdida, cola reintentada) no se apunta dos veces
_p = {'t': 1000.0, 'lat': 41.0, 'lon': -3.0, 'hr': None}
ok(not server._repetido(dict(_p)) and server._repetido(dict(_p)), 'un punto GPS reenviado se reconoce como repetido')
ok(not server._repetido(dict(_p, t=1010.0)), 'otro punto distinto no se confunde con el anterior')

with tempfile.TemporaryDirectory() as t:
    t = pathlib.Path(t)
    # live.json corrupto: siempre un dict
    server.LIVE_PATH = str(t / 'live.json')
    for malo in ('null', '[1,2]', '3', '', '\x00\x00\x00'):
        (t / 'live.json').write_text(malo, encoding='utf-8')
        ok(server.read_live() == {}, f'live.json con {malo!r}: read_live devuelve {{}}')
    (t / 'live.json').write_text('{"a": 1}', encoding='utf-8')
    ok(server.read_live() == {'a': 1}, 'live.json bueno: se lee igual')

    # purga de invitados con la lista ilegible: no se borra nada
    raiz = str(t)
    d = t / 'invitados' / 'ana'
    d.mkdir(parents=True)
    (d / 'r1.ruta').write_text('{}', encoding='utf-8')
    (t / 'invitados' / 'usuarios.dat').write_text('{ esto no es json', encoding='utf-8')
    ok(invitados.purgar(raiz) == 0 and (d / 'r1.ruta').exists(), 'lista de invitados ilegible: purgar no borra las carpetas')
    try:
        invitados.crear(raiz, 'luis', 30)
        ok(False, 'lista ilegible: crear debería negarse')
    except ValueError:
        ok(True, 'lista ilegible: crear se niega (no la sobrescribe)')
    ok((t / 'invitados' / 'usuarios.dat').read_text(encoding='utf-8').startswith('{ esto'), 'el fichero ilegible sigue intacto')

    # sin fichero de usuarios sí se puede crear el primero
    (t / 'invitados' / 'usuarios.dat').unlink()
    codigo = invitados.crear(raiz, 'luis', 30)
    ok(bool(codigo), 'sin lista todavía: se crea el primer invitado')

    # clave GPS: atómica y solo del dueño
    server.GPS_CLAVE_PATH = str(t / 'gps.clave')
    server.ROOT = str(t)
    server.escribir_clave_gps('odg-prueba')
    ok((t / 'gps.clave').read_text(encoding='utf-8').strip() == 'odg-prueba', 'la clave GPS se escribe entera')
    if os.name != 'nt':
        ok(oct((t / 'gps.clave').stat().st_mode & 0o777) == '0o600', 'la clave GPS queda en 0600')
    ok(not [p for p in t.iterdir() if p.name.endswith('.tmp')], 'sin temporales sueltos')

    # escribir_json: si falla, no deja el temporal
    try:
        server.escribir_json('x.json', {'a': object()})
    except TypeError:
        pass
    ok(not [p for p in t.iterdir() if p.name.endswith('.tmp')], 'escribir_json fallido no deja temporales')

# ritmo por km: el servidor apunta a qué hora se cruza cada kilómetro entero (10 km/h = 360 s por km)
import time
from datetime import datetime, timezone
with tempfile.TemporaryDirectory() as t2:
    t2 = pathlib.Path(t2)
    server.ROOT = str(t2); server.LIVE_PATH = str(t2 / 'live.json'); server.HISTORIAL_PATH = str(t2 / 'historial.jsonl')
    _salida = time.time() - 3000
    server.escribir_json('live.json', {'started_at': datetime.fromtimestamp(_salida, timezone.utc).isoformat(), 'status_label': 'En carrera'})
    _pts = [{'lat': 40.0 + (10 * (i * 10) / 3600) / 111.19, 'lon': -4.0, 't': _salida + 60 + i * 10, 'kmh': 10.0, 'precision': 5,
             'bateria': None, 'hr': None, 'origen': 'movil'} for i in range(240)]
    server.recibir_gps(_pts)
    _kt = server.read_live().get('km_t') or []
    ok(len(_kt) == 6, f'6,6 km recorridos: 6 cruces de kilómetro apuntados ({len(_kt)})')
    ok(all(abs((b - a) - 360) <= 2 for a, b in zip(_kt, _kt[1:])), 'cada km a 10 km/h son 360 s entre cruces')
    server.recibir_gps([dict(p) for p in _pts])      # el mismo lote reenviado no añade cruces
    ok(len(server.read_live().get('km_t') or []) == 6, 'un lote reenviado no duplica los cruces')

# sesiones del panel: cerrar sesión la revoca de verdad; las anteriores (sin identificador) siguen valiendo hasta caducar
with tempfile.TemporaryDirectory() as t3:
    server.ROOT = str(t3)
    server.ADMIN_HASH = 'scrypt:prueba:prueba'
    server._revocadas_cache.update(mtime=None, datos={})
    _tok = server.nueva_sesion()
    _ck = f'adm={_tok}; otra=1'
    ok(server.sesion_valida(_ck), 'una sesión nueva es válida')
    ok(not server.sesion_valida(f'adm={_tok}x'), 'una cookie con la firma alterada no vale')
    _otra = server.nueva_sesion()
    server.revocar_sesion(_ck)
    ok(not server.sesion_valida(_ck), 'tras cerrar sesión, esa cookie ya no vale (aunque no haya caducado)')
    ok(server.sesion_valida(f'adm={_otra}'), 'las demás sesiones siguen abiertas')
    _exp = int(time.time()) + 3600
    ok(server.sesion_valida(f'adm={_exp}.{server._firma(_exp)}'), 'una sesión anterior a v1.38 sigue valiendo hasta caducar')
    server.revocar_sesion('adm=basura')           # no debe romper
    ok(True, 'revocar con una cookie ilegible no rompe nada')

# la Pi de respaldo no recibe datos de carrera (sin IP flotante configurada siempre es titular)
server.VIP = ''
server._titular.update(t=0.0, v=True)
ok(server.soy_titular(), 'sin SIGUEME_VIP configurada: titular')
server.VIP = '203.0.113.77'                       # una IP que esta máquina no tiene
server._titular.update(t=0.0, v=True)
ok(not server.soy_titular(), 'con una IP flotante que esta máquina no tiene: no titular')
server.VIP = ''
server._titular.update(t=0.0, v=True)

# GPX del resultado: DOCTYPE no
try:
    generar_resultado._leer_gpx(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><gpx></gpx>')
    ok(False, 'un GPX con DOCTYPE debería rechazarse')
except ValueError:
    ok(True, 'el GPX del resultado rechaza DOCTYPE/ENTITY')

# redirecciones: el opener no las sigue
ok(server._SinRedireccion().redirect_request(None, None, 302, 'x', {}, 'http://10.0.0.1/') is None, 'el enlace de seguimiento no sigue redirecciones')

# --- v1.74.0: fotos subidas reconstruidas (nada escondido dentro ni detrás) ---------------------------
import zlib as _z
def _png(ancho, alto, color=6, extra=b'', detras=b'', idat=None):
    canales = {0: 1, 2: 3, 6: 4}[color]
    crudo = b''.join(b'\x00' + bytes(ancho * canales) for _ in range(alto))
    ihdr = ancho.to_bytes(4, 'big') + alto.to_bytes(4, 'big') + bytes([8, color, 0, 0, 0])
    return (server._PNG_FIRMA + server._trozo_png(b'IHDR', ihdr) + extra
            + server._trozo_png(b'IDAT', idat if idat is not None else _z.compress(crudo))
            + server._trozo_png(b'IEND', b'') + detras)

_bueno = _png(16, 16)
_limpio = server.png_limpio(_bueno, 512)
ok(_limpio is not None and _limpio.startswith(server._PNG_FIRMA), 'un PNG normal pasa')
ok(server.png_limpio(_limpio, 512) is not None, 'el PNG reconstruido vuelve a pasar')
_html = b'<html><script>alert(1)</script></html>'
_r = server.png_limpio(_bueno + _html, 512)
ok(_r is not None and _html not in _r, 'lo pegado detrás del PNG (una página, un ejecutable) se tira')
_r = server.png_limpio(_png(16, 16, extra=server._trozo_png(b'tEXt', b'Comment\x00' + _html)), 512)
ok(_r is not None and b'script' not in _r, 'un trozo de texto con código dentro se quita')
_r = server.png_limpio(_png(16, 16, extra=server._trozo_png(b'eXIf', b'MM\x00*GPS 42.6 -8.1')), 512)
ok(_r is not None and b'GPS' not in _r, 'los metadatos (eXIf con la posición GPS) se quitan')
_crudo = b''.join(b'\x00' + bytes(64) for _ in range(16))
ok(server.png_limpio(_png(16, 16, idat=_z.compress(_crudo) + _html), 512) is None, 'datos de más escondidos tras la imagen comprimida: fuera')
ok(server.png_limpio(_png(16, 16, idat=_z.compress(_crudo + _html)), 512) is None, 'datos de más dentro de la imagen comprimida: fuera')
_malo = bytearray(_bueno); _malo[30] ^= 1
ok(server.png_limpio(bytes(_malo), 512) is None, 'un PNG con la suma de control mal: fuera')
ok(server.png_limpio(_png(600, 16), 512) is None, 'más grande que el tope: fuera')
ok(server.png_limpio(b'GIF89a' + _bueno[6:], 512) is None and server.png_limpio(b'', 512) is None, 'lo que no es PNG: fuera')
ok(server.png_limpio(_png(16, 16, extra=server._trozo_png(b'ZZZZ', b'x')), 512) is None, 'un trozo crítico inventado: fuera')

# --- v1.74.0: GPX con codificación disfrazada (cp037 escribe «<!ENTITY» con otros bytes) -----------------
for _cod, _vale in (('UTF-8', True), ('iso-8859-1', True), ('cp037', False), ('utf-7', False)):
    ok(generar_resultado.codificacion_segura(f'<?xml version="1.0" encoding="{_cod}"?><gpx/>'.encode()) == _vale,
       f'codificación {_cod}: {"se admite" if _vale else "se rechaza"}')
ok(generar_resultado.codificacion_segura(b'<gpx/>'), 'sin declaración (UTF-8 por defecto): se admite')
try:
    generar_resultado._leer_gpx('<?xml version="1.0" encoding="cp037"?><gpx/>'.encode('cp037'))
    ok(False, 'un GPX en EBCDIC debería rechazarse')
except ValueError:
    ok(True, 'el GPX en EBCDIC (cp037) se rechaza antes de leerlo')

# --- v1.74.0: avisos push con la lista llena: no se echa a los de verdad -----------------------------
import avisos_web, directos as _dm
with tempfile.TemporaryDirectory() as t4:
    _s = lambda n: {'endpoint': f'https://fcm.googleapis.com/fcm/send/{n}', 'keys': {'p256dh': 'a', 'auth': 'b'}}
    _viejo = avisos_web.MAX_SUBS
    avisos_web.MAX_SUBS = 3
    for n in range(3):
        avisos_web.alta(t4, _s(n))
    ok(not avisos_web.alta(t4, _s('atacante')), 'con la lista llena, un alta nueva se rechaza')
    _eps = [x['endpoint'] for x in avisos_web._leer(t4, avisos_web.SUBS, [])]
    ok(_eps[0].endswith('/0') and len(_eps) == 3, 'los suscriptores que ya estaban siguen todos')
    ok(avisos_web.alta(t4, _s(1)), 'quien ya estaba puede renovar su alta aunque esté llena')
    avisos_web.MAX_SUBS = _viejo

# --- v1.74.0: login: con la Pi ocupada o el freno global, «prueba luego» y no «clave incorrecta» -------
server.ADMIN_USER, server.ADMIN_HASH = 'dueno', 'scrypt:' + '00' * 16 + ':' + server._scrypt('buena', bytes(16))
ok(server.credenciales_ok('dueno', 'buena') is True and server.credenciales_ok('dueno', 'mala') is False, 'clave buena True, mala False')
for _ in range(2):
    server._scrypt_sem.acquire()
ok(server.credenciales_ok('dueno', 'buena') is None, 'con la Pi ocupada: None (503), no «clave incorrecta»')
for _ in range(2):
    server._scrypt_sem.release()
server._fallos_admin[:] = [time.time()] * server.FALLOS_GLOBALES
ok(server.credenciales_ok('dueno', 'buena') is None, f'tras {server.FALLOS_GLOBALES} fallos en una hora desde donde sea: no se comprueba ninguna clave')
server._fallos_admin.clear()
ok(server.credenciales_ok('dueno', 'buena') is True, 'pasada la hora, vuelve a entrar')

# --- v1.75.0: DNS rebinding: se conecta a la IP ya comprobada, aunque el nombre diga otra cosa -------------
import http.server as _hs, threading as _th
class _Eco(_hs.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'hola desde la ip fijada')
    def log_message(self, *a): pass
_srv = _hs.HTTPServer(('127.0.0.1', 0), _Eco)
_th.Thread(target=_srv.serve_forever, daemon=True).start()
import urllib.request as _ur
_r = server._abrir_fijado('127.0.0.1').open(_ur.Request(f'http://no-existe.invalid:{_srv.server_port}/'), timeout=5)
ok(_r.read() == b'hola desde la ip fijada', 'con la IP fijada se conecta a ella aunque el nombre no resuelva (no vuelve a preguntar al DNS)')
_srv.shutdown()
try:
    server.fetch_page('http://localhost:9/')
    ok(False, 'localhost debería rechazarse')
except ValueError:
    ok(True, 'un enlace a localhost se rechaza antes de conectar')

# --- v1.75.0: tope de conexiones simultáneas -------------------------------------------------------------
import socket as _so
_a, _b = _so.socketpair()
_sv = server._Servidor.__new__(server._Servidor)
_viejas = server._Servidor._plazas
server._Servidor._plazas = _th.BoundedSemaphore(1)
server._Servidor._plazas.acquire()                      # la única plaza, ocupada
_sv.process_request(_a, ('127.0.0.1', 1))
ok(_b.recv(1) == b'', 'sin plazas libres la conexión se cierra sin atenderla')
server._Servidor._plazas = _viejas
_b.close()

# --- v1.75.0: la IP de Cloudflare solo se cree si llega de un proxy declarado --------------------------
class _Req:
    def __init__(self, local): self._l = local
    def getsockname(self): return (self._l, 8710)
def _h(origen, cf, local='10.1.2.202'):
    h = object.__new__(server.Handler)
    h.client_address = (origen, 5555)
    h.headers = {'CF-Connecting-IP': cf} if cf else {}
    class _Hd(dict):
        def get(self, k, d=None): return super().get(k, d)
    h.headers = _Hd(h.headers)
    h.request = _Req(local)
    return h
_antes = server.PROXIES_CONFIANZA
server.PROXIES_CONFIANZA = set()
ok(_h('10.1.2.77', '203.0.113.9').ip_cliente() == '203.0.113.9', 'sin SIGUEME_PROXIES: se cree a la cabecera desde cualquier IP privada (como antes)')
server.PROXIES_CONFIANZA = {'10.1.2.104'}
ok(_h('10.1.2.77', '203.0.113.9').ip_cliente() == '10.1.2.77', 'con SIGUEME_PROXIES: un equipo de la red que no es proxy no puede inventarse la IP')
ok(_h('10.1.2.104', '203.0.113.9').ip_cliente() == '203.0.113.9', 'con SIGUEME_PROXIES: el proxy declarado sí vale')
ok(_h('10.1.2.202', '203.0.113.9').ip_cliente() == '203.0.113.9', 'el túnel de esta misma máquina vale')
ok(_h('127.0.0.1', '203.0.113.9').ip_cliente() == '203.0.113.9', 'el bucle local vale')
server.PROXIES_CONFIANZA = _antes

# --- v1.76.0: carrera acabada sin llegada detectada: el tiempo se para en el último punto (antes contaba para siempre) ---
import directos as _dir, json as _js
with tempfile.TemporaryDirectory() as t5:
    from datetime import datetime as _dt, timedelta as _td
    from zoneinfo import ZoneInfo as _zi
    _sal = _dt.now(_zi('Europe/Madrid')) - _td(hours=5)
    _ruta = {'nombre': 'Prueba', 'coords': [[-8.0, 42.0], [-8.0, 42.1]], 'perfil': [], 'distancia_km': 11.1}
    _c, _yo = _dir.crear(t5, None, 'Corredor', _ruta, _sal.date().isoformat(), _sal.strftime('%H:%M'), lambda *a: {}, limite_h=3)
    _t0 = _sal.timestamp() + 60
    _st = {'en_marcha': 'x', 'salida_real': _t0, 'km': 9.0, 'ult': [42.08, -8.0, _t0 + 3600]}
    _dir._escribir(_dir._f(t5, _c['id'], _yo['cid']), _st)
    _g = _dir.publico(t5, _c['id'])['corredores'][0]
    ok(_g['tiempo_s'] == 3600, f"carrera acabada sin llegada: el tiempo se para en su último punto ({_g['tiempo_s']} s, no {int(time.time() - _t0)} s)")
    ok(_dir.publico(t5, _c['id'])['estado'] == 'terminada', 'y la carrera sale terminada')

# --- v1.76.0: recorrido que pasa dos veces por la misma calle (ida y vuelta): el km no salta al otro paso, la llegada no se da antes ---
import random as _rnd
def _simular(sigma, ritmo_kmh, apagar_a_m=None, semilla=1):
    r = _rnd.Random(semilla)
    ida = [[-8.0, 42.0 + i * 0.0005] for i in range(101)]
    vuelta = [[-8.00005, 42.05 - i * 0.0005] for i in range(101)]            # vuelve por la misma calle, a 4 m
    ruta = {'nombre': 'Ida y vuelta', 'coords': ida + vuelta, 'perfil': [], 'distancia_km': 11.1}
    with tempfile.TemporaryDirectory() as t6:
        c, yo = _dir.crear(t6, None, 'Corredor', ruta, '2026-11-28', '19:30', lambda *a: {}, limite_h=3)
        cum = _dir._cum_de(c); total = cum[-1]; sal = _dir.salida(c).timestamp()
        t, k, errmax, llegada_real = sal - 120, 0.0, 0.0, None
        while k < total + 0.15:
            if t >= sal:
                k += ritmo_kmh * 10 / 3600
            if apagar_a_m is not None and total - k < apagar_a_m / 1000:
                break
            kk = min(k, total)
            i = min(range(len(cum)), key=lambda j: abs(cum[j] - kk))
            la, lo = c['coords'][i][1], c['coords'][i][0]
            if sigma:
                la, lo = la + r.gauss(0, sigma) / 111190, lo + r.gauss(0, sigma) / 82000
            _dir.recibir(t6, yo['ident'], [{'t': t, 'lat': la, 'lon': lo}], ahora=t + 1)
            st = _dir.estado(t6, c['id'], yo['cid'])
            if st.get('salida_real'):
                errmax = max(errmax, abs(st.get('km', 0) - kk))
            if llegada_real is None and kk >= total:
                llegada_real = t
            if st.get('llegada') and kk < total - 0.2:
                return 'llegada antes de tiempo', errmax, None, None
            t += 10
        pub = _dir.publico(t6, c['id'], ahora=t + 300)['corredores'][0]
        return pub, errmax, total, (llegada_real - sal if llegada_real else None)
for _sig in (5, 15):
    _pub, _err, _tot, _real = _simular(_sig, 10, semilla=_sig)
    ok(isinstance(_pub, dict) and _err < 0.45, f'ida y vuelta por la misma calle, GPS con {_sig} m de ruido: el km no salta al otro paso (error máximo {_err * 1000:.0f} m)')
    ok(isinstance(_pub, dict) and _pub['situacion'] == 'en_meta' and _real and abs(_pub['tiempo_s'] - _real) < 40,
       f"y la llegada sale en su sitio ({_pub['tiempo_s'] if isinstance(_pub, dict) else '-'} s frente a {_real} s reales)")
_pub, _err, _tot, _real = _simular(6, 10, apagar_a_m=30, semilla=2)
ok(isinstance(_pub, dict) and _pub['situacion'] == 'en_meta', 'apaga el móvil a 30 m de la meta: a los 2 min sin mandar se da por llegado')

# --- v1.76.0: salida por el fondo de la cola: andar entre la gente (3,5 km/h, GPS con ruido) no cuenta como salir ---------------
def _salida_por_el_fondo(semilla, sigma=8):
    r = _rnd.Random(semilla)
    ruta = {'nombre': 'Recta', 'coords': [[-8.0, 42.0 + i * 0.0005] for i in range(201)], 'perfil': [], 'distancia_km': 11.1}
    with tempfile.TemporaryDirectory() as t7:
        c, yo = _dir.crear(t7, None, 'Corredor', ruta, '2026-11-28', '19:30', lambda *a: {}, limite_h=3)
        cum = _dir._cum_de(c); sal = _dir.salida(c).timestamp()
        espera, andando = 240, 180                      # 4 min quieto y 3 min andando antes de correr
        t, k, real = sal - 300, 0.0, None
        while t < sal + espera + andando + 300:
            rel = t - sal
            if rel >= espera + andando:
                real = real if real is not None else rel
                k += 10 * 10 / 3600
            elif rel >= espera:
                k += 3.5 * 10 / 3600
            i = min(range(len(cum)), key=lambda j: abs(cum[j] - k))
            la, lo = c['coords'][i][1] + r.gauss(0, sigma) / 111190, c['coords'][i][0] + r.gauss(0, sigma) / 82000
            _dir.recibir(t7, yo['ident'], [{'t': t, 'lat': la, 'lon': lo}], ahora=t + 1)
            t += 10
        st = _dir.estado(t7, c['id'], yo['cid'])
        return (st['salida_real'] - sal) - real if st.get('salida_real') else None
_difs = [_salida_por_el_fondo(s) for s in range(8)]
ok(all(d is not None and -45 <= d <= 30 for d in _difs), f'salida por el fondo (4 min quieto, 3 min andando, GPS 8 m): la salida se marca al echar a correr, no al andar ({sorted(_difs)} s)')

# --- v1.76.0: privacidad: con el móvil encendido antes de la salida no se ve a quien está lejos de ella; acabada la carrera no se sigue a quien no llegó ---
def _privacidad():
    ida = [[-8.0, 42.0 + i * 0.0005] for i in range(101)]
    ruta = {'nombre': 'Recta', 'coords': ida, 'perfil': [], 'distancia_km': 5.5}
    with tempfile.TemporaryDirectory() as t8:
        c, yo = _dir.crear(t8, None, 'Corredor', ruta, '2026-11-28', '19:30', lambda *a: {}, limite_h=3)
        sal = _dir.salida(c).timestamp()
        def punto(rel, lat):
            _dir.recibir(t8, yo['ident'], [{'t': sal + rel, 'lat': lat, 'lon': -8.0}], ahora=sal + rel + 1)
            return _dir.publico(t8, c['id'], ahora=sal + rel + 2)['corredores'][0]
        lejos = punto(-2400, 42.05)                      # 40 min antes, a 5,5 km de la salida (en casa)
        cerca = punto(-300, 42.001)                      # 5 min antes, a 110 m de la salida
        for i in range(12):                              # empieza a correr a 10 km/h, pasados 2 min de la hora de salida
            corre = punto(120 + i * 10, 42.0005 + i * 0.00025)
        _dir.recibir(t8, yo['ident'], [{'t': sal + 3600 + 3 * 3600, 'lat': 42.06, 'lon': -8.0}], ahora=sal + 3600 + 3 * 3600)    # tras el límite, de vuelta a casa
        despues = _dir.publico(t8, c['id'], ahora=sal + 3 * 3600 + 700 + 3600)['corredores'][0]
        return lejos, cerca, corre, despues
_l, _c, _r, _d = _privacidad()
ok(_l['situacion'] == 'sin_empezar' and 'lat' not in _l, 'móvil encendido 40 min antes y lejos de la salida: «Aún sin salir» y sin posición pública')
ok(_c['situacion'] == 'en_la_salida' and 'lat' in _c, 'a 110 m de la salida sí se ve («En la salida»)')
ok(_r['situacion'] == 'corriendo' and 'lat' in _r, 'corriendo se ve normal')
ok('lat' not in _d, 'acabada la carrera, quien no llegó deja de verse en público (de vuelta a casa)')

# --- v1.76.0: minimización: no se guarda lo de antes de la carrera (en casa), ni lo de días después, ni lo de después de llegar ---
def _minimizacion():
    ida = [[-8.0, 42.0 + i * 0.0005] for i in range(101)]
    ruta = {'nombre': 'Recta', 'coords': ida, 'perfil': [], 'distancia_km': 5.5}
    with tempfile.TemporaryDirectory() as t9:
        c, yo = _dir.crear(t9, None, 'Corredor', ruta, '2026-11-28', '19:30', lambda *a: {}, limite_h=3)
        sal = _dir.salida(c).timestamp()
        for rel, lat in ((-4 * 3600, 42.06), (-1800, 42.001), (600, 42.002), (3 * 3600 + 3000, 42.003), (3 * 86400, 42.07)):
            _dir.recibir(t9, yo['ident'], [{'t': sal + rel, 'lat': lat, 'lon': -8.0}], ahora=sal + rel + 1)
        guardados = [json.loads(l)[0] - sal for l in open(_dir._f(t9, c['id'], yo['cid'], 'pts'), encoding='utf-8')]
        return sorted(round(g) for g in guardados)
_g = _minimizacion()
ok(_g == [-1800, 600], f'solo se guarda lo que cae en la carrera: 4 h antes, 50 min tras el límite y 3 días después no ({_g})')

print('\nTODO BIEN' if all(resultados) else f'\nFALLOS: {resultados.count(False)}')
sys.exit(0 if all(resultados) else 1)
