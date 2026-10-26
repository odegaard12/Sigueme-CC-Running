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

print('\nTODO BIEN' if all(resultados) else f'\nFALLOS: {resultados.count(False)}')
sys.exit(0 if all(resultados) else 1)
