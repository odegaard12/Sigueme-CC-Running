"""Lo común de las pruebas: una carpeta limpia con la web del repo y un GPX
inventado (nunca una ruta real: el repo es público)."""
import math, pathlib, shutil, socket, tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
WEB = ('server.py', 'index.html', 'app.js', 'sw.js', 'admin.html', 'style.css', 'robots.txt', 'rider.png',
       'favicon.png', 'app.html', 'app-enlace.js', 'og.jpg', 'manifest.webmanifest', 'icon-192.png', 'mis-rutas.html', 'rutas.html', 'rutas.js', 'mis-rutas.js', 'inicio.html', 'pulseras.html', 'inicio.js', 'ruta.html', 'ruta.js', 'cartel.css')


def carpeta(prefijo, datos=('carrera.json',)):
    """Carpeta temporal con la web, lib/, herramientas/ y los datos de ejemplo pedidos."""
    w = pathlib.Path(tempfile.mkdtemp(prefix='sigueme-' + prefijo + '-'))
    for f in WEB + tuple(datos):
        if (RAIZ / f).exists():
            shutil.copy(RAIZ / f, w / f)
    shutil.copytree(RAIZ / 'lib', w / 'lib')
    shutil.copytree(RAIZ / 'herramientas', w / 'herramientas')
    if (RAIZ / 'fonts').exists():
        shutil.copytree(RAIZ / 'fonts', w / 'fonts')
    return w


def gpx_inventado(km=100, lat0=40.6, lon0=-4.2):
    """Bucle de ~km kilómetros por el centro de la península, con subidas y
    bajadas: lo bastante largo y movido para que el plan tenga avisos."""
    n = int(km / 0.05)
    r = km / (2 * math.pi) / 111.2
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        ele = 700 + 250 * math.sin(a * 5) + 80 * math.sin(a * 17)
        pts.append(f'<trkpt lat="{lat0 + r * math.sin(a):.6f}" lon="{lon0 + r * (1 - math.cos(a)) / math.cos(math.radians(lat0)):.6f}">'
                   f'<ele>{ele:.1f}</ele></trkpt>')
    return ('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
            + ''.join(pts) + '</trkseg></trk></gpx>').encode()


def puerto_libre():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p
