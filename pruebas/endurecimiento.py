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
