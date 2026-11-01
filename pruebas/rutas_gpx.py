"""Carga de rutas: muchos tipos de GPX dan la misma ruta (distancia y D+), los saltos de GPS no la inflan y los
ficheros malos se rechazan con una explicación. Sin servidor: llama a herramientas/preparar_ruta.py."""
import math, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "herramientas"))
import preparar_ruta as pr

R = 20.0 / (2 * math.pi) / 111.0
fallos = []


def ok(c, t):
    print(("OK   " if c else "MAL  ") + t)
    if not c:
        fallos.append(t)


def circuito(n=2000, ele=True, picos=False):
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        la, lo = 42.6 + R * math.sin(a), -8.1 + R * math.cos(a) / math.cos(math.radians(42.6))
        e = 300 + 150 * math.exp(-((i / n - 0.25) / 0.05) ** 2) + 90 * math.exp(-((i / n - 0.65) / 0.04) ** 2)
        if picos and i % 400 == 200:
            la += 0.01
        pts.append((la, lo, round(e, 1) if ele else None))
    return pts


def gpx(pts, etiqueta="trkpt", ns=True):
    cab = '<?xml version="1.0"?><gpx version="1.1"' + (' xmlns="http://www.topografix.com/GPX/1/1"' if ns else "") + ">"
    cuerpo = "".join(f'<{etiqueta} lat="{p[0]:.6f}" lon="{p[1]:.6f}">' + (f"<ele>{p[2]}</ele>" if p[2] is not None else "") + f"</{etiqueta}>" for p in pts)
    return (cab + ("<rte>" + cuerpo + "</rte>" if etiqueta == "rtept" else "<trk><trkseg>" + cuerpo + "</trkseg></trk>") + "</gpx>").encode()


base = pr.preparar(gpx(circuito()))[2]
ok(19.5 <= base["distancia_km"] <= 20.5 and 200 <= base["desnivel_m"] <= 300, f"track normal: {base['distancia_km']} km, +{base['desnivel_m']} m")
for nombre, cuerpo in (("ruta <rtept>", gpx(circuito(), "rtept")), ("sin espacio de nombres", gpx(circuito(), ns=False)),
                       ("con BOM", b"\xef\xbb\xbf" + gpx(circuito())), ("con saltos de GPS", gpx(circuito(picos=True)))):
    r = pr.preparar(cuerpo)[2]
    ok(abs(r["distancia_km"] - base["distancia_km"]) < 0.3, f"{nombre}: {r['distancia_km']} km (como el normal)")
ok(pr.preparar(gpx(circuito(ele=False)))[2]["con_elevacion"] is False, "sin altura: entra sin D+ inventado")
ok(abs(pr.preparar(gpx(circuito()), "x", 21.1)[2]["distancia_km"] - 21.1) < 0.01, "distancia oficial: la ruta se ajusta")
for nombre, cuerpo in (("no es XML", b"hola"), ("sin puntos", gpx([])), ("menos de 100 m", gpx(circuito()[:5])),
                       ("con ENTITY", b'<!DOCTYPE g [<!ENTITY a "a">]><gpx>&a;</gpx>'), ("UTF-16", gpx(circuito()[:50]).decode().encode("utf-16"))):
    try:
        pr.preparar(cuerpo)
        ok(False, f"{nombre}: tenía que rechazarse")
    except ValueError as exc:
        ok(bool(str(exc)), f"{nombre}: rechazado ({exc})")
print("\nTODO BIEN" if not fallos else f"\nFALLOS: {len(fallos)}")
sys.exit(1 if fallos else 0)
