# -*- coding: utf-8 -*-
"""Plan de avisos para la pulsera, a partir del perfil de la ruta.

    python herramientas/plan_avisos.py [--antes 0.3] [--cada 3]

Lee elevation.json, aid_stations.json y carrera.json y escribe avisos.json:
una tabla «en el km X → este texto», calculada ANTES de la carrera para
revisarla en casa. En carrera el servidor solo mira en qué km vas y manda el
aviso que toca (si llega tarde por falta de cobertura, manda el estado actual,
nunca un aviso viejo).

Qué avisa (textos cortos, caben en la pulsera):
  - 300 m antes de cada subida: tipo, largo, % medio, D+ y rampa si la hay
      SUBIDA LARGA · 2,1km · 8% · +170m      (más de 1 km)
      CORTA DURA · 400m · 14% · +55m          (menos de 500 m y más del 12 %)
      RAMPA 22% · 150m · camina               (muy corta y muy dura)
  - a mitad de las largas: MITAD · quedan 900m · +80m
  - en la cima: BAJADA 1,5km · -140m · quedan +450m
  - 300 m antes de cada avituallamiento
  - resumen cada pocos km: KM 9 · faltan 6km · +210m
  - ÚLTIMA SUBIDA y ÚLTIMO KM
Los repechos de menos de 30 m de desnivel no avisan. Dos avisos a menos de
400 m se juntan en uno. Solo biblioteca estándar."""
import argparse, json, pathlib, sys
from datetime import datetime, timezone

RAIZ = pathlib.Path(__file__).resolve().parent.parent
D_MIN = 30          # m: una subida de menos no avisa (repecho)
CORTE = 10          # m: bajar esto desde lo más alto termina la subida
JUNTAR = 0.4        # km: avisos más cerca que esto se juntan
PEND_MIN = 3.0      # %: por debajo es falso llano, no avisa


def km_txt(km):
    return f"{round(km * 1000 / 50) * 50:.0f}m" if km < 1 else f"{km:.1f}".replace(".", ",") + "km"


def suavizar(perfil, ventana=0.2):
    """Media móvil de ±ventana/2 km: quita el ruido del GPS/barómetro."""
    d = [p["d"] for p in perfil]
    e = [p["ele"] for p in perfil]
    out, i0, i1, suma = [], 0, 0, 0.0
    for i, x in enumerate(d):
        while i1 < len(d) and d[i1] <= x + ventana / 2:
            suma += e[i1]; i1 += 1
        while d[i0] < x - ventana / 2:
            suma -= e[i0]; i0 += 1
        out.append(suma / (i1 - i0))
    return d, out


def subidas(d, e):
    """Subidas con histéresis: empiezan al ganar 10 m desde un mínimo y
    acaban al perder 10 m desde el máximo (así una subida con bajadas dentro
    se parte en varias, que es como se corre)."""
    res, estado = [], "busca"
    imin = imax = 0
    for i in range(len(e)):
        if estado == "busca":
            if e[i] < e[imin]:
                imin = i
            elif e[i] - e[imin] >= CORTE:
                estado, imax = "sube", i
        else:
            if e[i] > e[imax]:
                imax = i
            elif e[imax] - e[i] >= CORTE:
                res.append((imin, imax)); estado, imin = "busca", i
    if estado == "sube":
        res.append((imin, imax))
    return [(a, b) for a, b in res
            if e[b] - e[a] >= D_MIN and (e[b] - e[a]) / ((d[b] - d[a]) * 1000 or 1) * 100 >= PEND_MIN]


def rampa_max(d, e, a, b, tramo=0.1):
    """% máximo en 100 m dentro de la subida."""
    mejor, j = 0.0, a
    for i in range(a, b + 1):
        while j < b and d[j] - d[i] < tramo:
            j += 1
        if d[j] - d[i] >= tramo * 0.8:
            mejor = max(mejor, (e[j] - e[i]) / ((d[j] - d[i]) * 1000) * 100)
    return mejor


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--antes', type=float, default=0.3, help='km antes de subidas y avituallamientos (0,3)')
    ap.add_argument('--cada', type=float, help='resumen cada tantos km (por defecto según la distancia)')
    a = ap.parse_args()

    perfil = json.loads((RAIZ / 'elevation.json').read_text(encoding='utf-8')).get('profile') or []
    if len(perfil) < 10:
        sys.exit('elevation.json no tiene perfil: créalo antes con preparar_ruta.py')
    try:
        avitus = json.loads((RAIZ / 'aid_stations.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        avitus = []
    d, e = suavizar(perfil)
    total = d[-1]
    try:
        oficial = json.loads((RAIZ / 'carrera.json').read_text(encoding='utf-8')).get('desnivel_m')
    except (OSError, ValueError):
        oficial = None
    cada = a.cada or (3 if total <= 30 else 5 if total <= 60 else 10)

    # D+ que queda desde cada punto (con el perfil suavizado)
    restante = [0.0] * len(e)
    for i in range(len(e) - 2, -1, -1):
        restante[i] = restante[i + 1] + max(0.0, e[i + 1] - e[i])
    # el perfil suavizado da menos D+ que el oficial: se escala para que cuadre
    escala = (oficial / restante[0]) if oficial and restante[0] else 1.0
    restante = [r * escala for r in restante]
    def dplus_desde(km):
        i = min(range(len(d)), key=lambda k: abs(d[k] - km))
        return restante[i]

    lista_subidas = []
    for n, (i, j) in enumerate(subidas(d, e)):
        largo, gan = d[j] - d[i], e[j] - e[i]
        pend, rmax = gan / (largo * 1000) * 100 if largo else 0, rampa_max(d, e, i, j)
        tipo = ("rampa" if largo < 0.3 and rmax >= 18 else "corta_dura" if largo < 0.5 and pend >= 12
                else "larga" if largo >= 1 else "subida")
        # bajada hasta el siguiente mínimo
        k = j
        while k + 1 < len(e) and e[k + 1] <= e[k] + 2:
            k += 1
        lista_subidas.append({"n": n + 1, "inicio": round(d[i], 2), "fin": round(d[j], 2), "largo_km": round(largo, 2),
                              "desnivel_m": round(gan), "pendiente": round(pend, 1), "rampa_max": round(rmax),
                              "tipo": tipo, "bajada_km": round(d[k] - d[j], 2), "bajada_m": round(e[j] - e[k])})

    avisos = []
    def poner(km, tipo, texto, hasta, prio, objetivo=None):
        if 0 <= km <= total:
            av = {"km": round(km, 2), "tipo": tipo, "texto": texto, "valido_hasta": round(hasta, 2), "prio": prio}
            if objetivo is not None:
                av["objetivo_km"] = round(objetivo, 2)   # {dist} = lo que falta hasta aquí, al enviarlo
            avisos.append(av)

    for s in lista_subidas:
        ultima = s is lista_subidas[-1]
        if s["tipo"] == "rampa":
            txt = f"RAMPA {s['rampa_max']}% · {km_txt(s['largo_km'])} · camina"
        else:
            nombre = {"larga": "SUBIDA LARGA", "corta_dura": "CORTA DURA"}.get(s["tipo"], "SUBIDA")
            txt = f"{nombre} · {km_txt(s['largo_km'])} · {s['pendiente']:.0f}% · +{s['desnivel_m']}m"
            if s["rampa_max"] >= 18:
                txt += f" · rampa {s['rampa_max']}%"
        if ultima:
            txt = "ÚLTIMA " + txt
        poner(s["inicio"] - a.antes, "subida", txt, s["inicio"] + 0.3, 1)
        if s["largo_km"] >= 1.5:
            mitad = (s["inicio"] + s["fin"]) / 2
            poner(mitad, "mitad", f"MITAD · quedan {km_txt(s['fin'] - mitad)} · +{round(s['desnivel_m'] / 2)}m", s["fin"], 2)
        if s["bajada_m"] >= D_MIN:
            poner(s["fin"], "cima", f"CIMA · bajada {km_txt(s['bajada_km'])} · -{s['bajada_m']}m · quedan +{round(dplus_desde(s['fin']))}m",
                  s["fin"] + 0.3, 2)
    for av in avitus:
        poner(av["km"] - a.antes, "avituallamiento", f"AVITUALLAMIENTO {{dist}} · {av['name']}", av["km"] + 0.2, 1, av["km"])
    k = cada
    while k < total - 1.5:
        poner(k, "resumen", f"KM {k:.0f} · faltan {km_txt(total - k)} · +{round(dplus_desde(k))}m", k + 0.8, 3)
        k += cada
    poner(total - 1, "ultimo_km", "ÚLTIMO KM · ¡a por ello!", total, 1)

    # juntar los que caen casi en el mismo sitio (manda el más importante)
    avisos.sort(key=lambda x: (x["km"], x["prio"]))
    final = []
    for av in avisos:
        if final and av["km"] - final[-1]["km"] < JUNTAR:
            if av["tipo"] == "resumen":
                continue                                # el resumen sobra si hay otro aviso
            previo = final[-1]
            if previo["tipo"] == "resumen":
                final[-1] = av
                continue
            primero, segundo = (previo, av) if previo["prio"] <= av["prio"] else (av, previo)
            final[-1] = {**segundo, **primero, "texto": primero["texto"] + " · " + segundo["texto"],
                         "valido_hasta": max(previo["valido_hasta"], av["valido_hasta"])}
        else:
            final.append(av)
    for n, av in enumerate(final):
        av["id"] = n + 1
        av.pop("prio", None)

    salida = {"generado": datetime.now(timezone.utc).isoformat(), "distancia_km": round(total, 2),
              "antes_km": a.antes, "subidas": lista_subidas, "avisos": final,
              "restante": [[round(d[i], 2), round(restante[i])] for i in range(0, len(d), max(1, len(d) // 200))]}
    (RAIZ / 'avisos.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f"{len(lista_subidas)} subidas · {len(final)} avisos · resumen cada {cada:g} km → avisos.json\n")
    print("SUBIDAS")
    for s in lista_subidas:
        print(f"  {s['n']:>2}. km {s['inicio']:6.2f}–{s['fin']:6.2f}  {km_txt(s['largo_km']):>7}  +{s['desnivel_m']:>4} m  "
              f"{s['pendiente']:4.1f}%  máx {s['rampa_max']:>2}%  {s['tipo']}")
    print("\nAVISOS (revísalos: si alguno no te convence, cambia el texto en avisos.json)")
    for av in final:
        print(f"  km {av['km']:6.2f}  {av['texto'].replace('{dist}', 'en ' + km_txt(a.antes))}")


if __name__ == '__main__':
    main()
