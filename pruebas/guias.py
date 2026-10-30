"""Guía de relojes: una ficha por marca (con avisos, ruta y mapa), una fila por marca en la tabla, cada botón de marca
lleva a una ficha que existe, y lo de iPhone y Garmin dicho claramente."""
import pathlib, re, sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
resultados = []


def ok(cond, texto):
    resultados.append(bool(cond))
    print(('OK   ' if cond else 'MAL  ') + texto)


MARCAS = ['xiaomi', 'huawei', 'amazfit', 'garmin', 'coros', 'polar', 'suunto', 'apple']
guia = (RAIZ / 'pulseras.html').read_text(encoding='utf-8')
ids = set(re.findall(r'<article class="marca-tarj" id="([a-z]+)"', guia))
ok(set(MARCAS + ['android', 'iphone']) <= ids, f'la guía tiene una ficha por marca y móvil ({sorted(ids)})')
tabla = re.search(r'<table class="tabla-relojes">.*?</table>', guia, re.S)
ok(tabla and re.findall(r'href="#([a-z]+)"', tabla.group(0)) == MARCAS, 'la tabla tiene una fila por marca, en orden')
for m in MARCAS:
    ficha = re.search(rf'<article class="marca-tarj" id="{m}">.*?</article>', guia, re.S)
    ok(ficha and all(x in ficha.group(0) for x in ('Avisos', 'Ruta en el reloj', 'Mapa en el reloj')), f'{m}: dice avisos, ruta y mapa')
botones = re.findall(r'<nav class="chips-marcas".*?</nav>', guia, re.S)
ok(len(botones) == 1, 'la guía tiene su fila de botones de marca')
enlaces = re.findall(r'href="#([a-z]+)"', botones[0]) if botones else []
ok(enlaces == MARCAS + ['android'], f'los botones de la guía van a cada ficha, en orden ({enlaces})')
ok(all(e in ids for e in enlaces), 'ningún botón apunta a una ficha que no existe')
for f in ('ruta.html', 'mis-rutas.html'):
    t = (RAIZ / f).read_text(encoding='utf-8')
    destinos = re.findall(r'href="/pulseras#([a-z]+)"', t)
    ok(destinos == MARCAS, f'{f}: botones de marca que llevan a la guía ({len(destinos)})')
garmin = re.search(r'<article class="marca-tarj" id="garmin">.*?</article>', guia, re.S)
ok(garmin and all(x in garmin.group(0) for x in ('Cursos', 'Exportar original', 'LiveTrack')), 'Garmin: ruta, resultado FIT y aviso sobre LiveTrack')
iphone = re.search(r'<article class="marca-tarj" id="iphone">.*?</article>', guia, re.S)
ok(iphone and 'Traccar' in iphone.group(0) and 'no hay avisos' in iphone.group(0), 'iPhone: Traccar y la limitación de los avisos, dicha claramente')
for f in ('cartel.css', 'cartel-panel.css'):
    ok('.chips-marcas a' in (RAIZ / f).read_text(encoding='utf-8'), f'{f}: estilo de los botones de marca')

print('\nTODO BIEN' if all(resultados) else f'\nFALLOS: {resultados.count(False)}')
sys.exit(0 if all(resultados) else 1)
