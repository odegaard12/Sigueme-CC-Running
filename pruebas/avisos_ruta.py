"""Avisos de subidas en el iPhone del corredor: solo a SU móvil, una vez cada uno, nunca los ya pasados, solo con posición
fresca y solo con la carrera en marcha. Sin enviar nada real (se captura lo que enviaría). Datos inventados."""
import json, pathlib, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'herramientas'))
import avisos_web as aw, avisos_ruta as ar

malos = []
def ok(c, t):
    print('OK ' if c else 'MAL', t)
    if not c: malos.append(t)

raiz = tempfile.mkdtemp(prefix='avruta-')
enviados = []
aw.enviar = lambda subs, datos: (enviados.append((len(subs), datos['body'], datos['tag'])), set())[1]
aw.clave_publica = lambda: 'clave-de-prueba'
# una ruta recta hacia el este de ~10 km (0,0001° de longitud ≈ 8,3 m a esta latitud)
LAT = 42.0
coords = [[-8.0 + i * 0.0001, LAT] for i in range(1200)]
m_por_grado = 111.195 * 0.743
avisos = [{'id': 1, 'km': 2.0, 'valido_hasta': 2.4, 'texto': 'SUBIDA 1', 'tipo': 'subida'},
          {'id': 2, 'km': 5.0, 'valido_hasta': 5.4, 'texto': 'CIMA', 'tipo': 'cima'},
          {'id': 3, 'km': 8.0, 'valido_hasta': 8.4, 'texto': 'ULTIMO KM', 'tipo': 'ultimo_km'}]
ruta = {'features': [{'geometry': {'coordinates': coords}}]}
plan = {'avisos': avisos}
SUB = {'endpoint': 'https://web.push.apple.com/abc', 'keys': {'p256dh': 'x', 'auth': 'y'}}
CLAVE = 'clave-dueno-de-prueba-12345678'
T0 = 1_800_000_000.0

def en_km(km, t, salida=True):
    return {'started_at': 'hoy' if salida else None, 'gps_ult': [LAT, -8.0 + km / m_por_grado, t]}

ok(not ar.alta(raiz, aw, CLAVE, {'endpoint': 'https://evil.example/x', 'keys': {'p256dh': 'x', 'auth': 'y'}}), 'una suscripción de un servicio que no es de avisos no se guarda')
ok(ar.alta(raiz, aw, CLAVE, SUB) and ar.alta(raiz, aw, CLAVE, SUB) and len(json.load(open(pathlib.Path(raiz) / '.push_corredor.json'))[CLAVE]) == 1, 'su móvil se apunta (dos veces no se duplica)')
ok(ar.revisar(raiz, aw, en_km(1.0, T0), plan, ruta, CLAVE, None, T0) == 0, 'km 1: aún no hay aviso')
ok(ar.revisar(raiz, aw, en_km(2.1, T0 + 60), plan, ruta, CLAVE, None, T0 + 60) == 1 and enviados[-1][1:] == ('SUBIDA 1', 'subida-1'), 'km 2,1: «SUBIDA 1» a su móvil')
ok(ar.revisar(raiz, aw, en_km(2.2, T0 + 90), plan, ruta, CLAVE, None, T0 + 90) == 0, 'km 2,2: no se repite')
ok(ar.revisar(raiz, aw, en_km(5.1, T0 + 1200), plan, ruta, CLAVE, None, T0 + 1200) == 1 and enviados[-1][1] == 'CIMA', 'km 5,1 (tras un tramo sin cobertura): solo «CIMA»')
n = len(enviados)
ok(ar.revisar(raiz, aw, en_km(9.0, T0 + 2000), plan, ruta, CLAVE, None, T0 + 2000) == 0 and len(enviados) == n, 'km 9: «ULTIMO KM» ya pasó (valía hasta el 8,4): no se manda tarde')
ok(ar.revisar(raiz, aw, en_km(8.1, T0 + 2100), plan, ruta, CLAVE, None, T0 + 2100) == 0, 'los avisos ya dados por pasados no vuelven si el GPS salta atrás')
# casos que no deben mandar nada
raiz2 = tempfile.mkdtemp(prefix='avruta2-'); ar.alta(raiz2, aw, CLAVE, SUB); n = len(enviados)
ok(ar.revisar(raiz2, aw, en_km(2.1, T0, salida=False), plan, ruta, CLAVE, None, T0) == 0, 'carrera sin empezar: nada')
ok(ar.revisar(raiz2, aw, en_km(2.1, T0 - 600), plan, ruta, CLAVE, None, T0) == 0, 'posición de hace 10 min: nada')
lejos = {'started_at': 'hoy', 'gps_ult': [LAT + 0.01, -8.0 + 2.1 / m_por_grado, T0]}
ok(ar.revisar(raiz2, aw, lejos, plan, ruta, CLAVE, None, T0) == 0, 'a más de 150 m de la ruta: nada (no sabe dónde va)')
ok(ar.revisar(raiz2, aw, en_km(2.1, T0), plan, ruta, 'otra-clave', None, T0) == 0 and len(enviados) == n, 'sin móvil apuntado para esa clave: nada')
ar.baja(raiz2, aw, CLAVE, SUB['endpoint'])
ok(ar.revisar(raiz2, aw, en_km(2.1, T0), plan, ruta, CLAVE, None, T0) == 0, 'tras darse de baja: nada')

# una carrera de varios corredores: cada uno el suyo
class Dm:
    def __init__(s): s.c = {'id': 'abcdef0123', 'plan': {'avisos': avisos}, 'corredores': [{'cid': 'c1', 'ident': 'dir-uno'}, {'cid': 'c2', 'ident': 'dir-dos'}]}
    def _ids(s, r): return ['abcdef0123']
    def carrera(s, r, i): return s.c
    def estado(s, r, i, cid): return {'c1': {'salida_real': T0, 'km': 2.1, 'ult': [LAT, -8.0, T0]}, 'c2': {'salida_real': T0, 'km': 5.2, 'ult': [LAT, -8.0, T0]}}[cid]
raiz3 = tempfile.mkdtemp(prefix='avruta3-'); ar.alta(raiz3, aw, 'dir-uno', SUB)
n = len(enviados)
ok(ar.revisar(raiz3, aw, {}, {}, {}, CLAVE, Dm(), T0) == 1 and enviados[-1][1] == 'SUBIDA 1' and len(enviados) == n + 1, 'directo de varios: el corredor «uno» recibe su aviso (el «dos» no tiene móvil apuntado)')

print('\nTODO BIEN' if not malos else f'\nFALLOS: {len(malos)}')
sys.exit(1 if malos else 0)
