# -*- coding: utf-8 -*-
"""resultado.json a partir del FIT de la carrera: tiempos, pasos por
avituallamiento y la traza real recortada a salida-meta. La fecha, la hora
de salida, la distancia y el nombre salen de carrera.json.

    python herramientas/generar_resultado.py actividad.fit

El panel hace lo mismo al subir el FIT (pestaña «Más»). Necesita fitdecode
(pip install fitdecode)."""
import io, json, math, pathlib, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# la web (route.geojson, aid_stations.json, resultado.json) está en la raíz del repo
RAIZ = pathlib.Path(__file__).resolve().parent.parent
SC = 180 / 2 ** 31


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _es_gpx(datos):
    if isinstance(datos, (str, pathlib.Path)):
        return str(datos).lower().endswith('.gpx')
    return b'.FIT' not in datos[:16] and b'<gpx' in datos[:4096].lower()


def _leer_gpx(datos):
    """GPX de un reloj o pulsera (Mi Fitness, Huawei Health, Zepp, Strava…) → (puntos [(hora, lat, lon)], sesión).
    Necesita la hora de cada punto; el pulso y la altura, si los trae."""
    import xml.etree.ElementTree as ET
    if not isinstance(datos, bytes):
        datos = pathlib.Path(datos).read_bytes()
    try:
        raiz = ET.fromstring(datos)
    except ET.ParseError as exc:
        raise ValueError(f'no se pudo leer el GPX ({str(exc)[:60]})')
    local = lambda e: e.tag.rsplit('}', 1)[-1]
    recs, hrs, alts = [], [], []
    for pt in raiz.iter():
        if local(pt) != 'trkpt':
            continue
        try:
            la, lo = float(pt.get('lat')), float(pt.get('lon'))
        except (TypeError, ValueError):
            continue
        hora = ele = hr = None
        for h in pt.iter():
            n = local(h)
            try:
                if n == 'time' and h.text:
                    hora = datetime.fromisoformat(h.text.strip().replace('Z', '+00:00'))
                elif n == 'ele' and h.text:
                    ele = float(h.text)
                elif n == 'hr' and h.text:
                    hr = float(h.text)
            except ValueError:
                pass
        if hora is None:
            continue
        if hora.tzinfo is None:
            hora = hora.replace(tzinfo=timezone.utc)
        recs.append((hora, la, lo))
        if hr and 30 < hr < 250:
            hrs.append(hr)
        if ele is not None:
            alts.append(ele)
    recs.sort(key=lambda r: r[0])
    mov = 0.0                      # tiempo en movimiento: tramos de menos de 1 min a más de 1 km/h
    for a, b in zip(recs, recs[1:]):
        dt = (b[0] - a[0]).total_seconds()
        if 0 < dt <= 60 and hav(a[1:], b[1:]) / dt * 3600 > 1:
            mov += dt
    sube, ref = 0.0, alts[0] if alts else 0.0       # desnivel con 3 m de histéresis (el ruido del barómetro no suma)
    for e in alts:
        if e - ref >= 3:
            sube += e - ref
            ref = e
        elif ref - e >= 3:
            ref = e
    return recs, {'total_timer_time': mov, 'total_ascent': round(sube) if alts else None,
                  'avg_heart_rate': round(sum(hrs) / len(hrs)) if hrs else None}


def generar(fit, raiz=RAIZ):
    """FIT o GPX (ruta o bytes) → diccionario de resultado.json. ValueError con el
    motivo en castellano si el fichero no vale para esta carrera."""
    carrera = json.loads((raiz / 'carrera.json').read_text(encoding='utf-8'))
    try:
        salida_oficial = datetime.fromisoformat(f"{carrera['fecha']}T{carrera['hora_salida']}").replace(
            tzinfo=ZoneInfo(carrera.get('zona_horaria', 'Europe/Madrid')))
    except (KeyError, ValueError):
        raise ValueError('falta la fecha o la hora de salida en los datos de la carrera')

    # ruta tal como la usa la web (route.geojson) y avituallamientos
    ruta = [(c[1], c[0]) for c in json.loads((raiz / 'route.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates']]
    if len(ruta) < 2:
        raise ValueError('falta la ruta de la carrera (sube antes el GPX)')
    cum = [0.0]
    for a, b in zip(ruta, ruta[1:]):
        cum.append(cum[-1] + hav(a, b))
    total_oficial = carrera.get('distancia_km') or cum[-1]
    try:
        avis = json.loads((raiz / 'aid_stations.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        avis = []

    def punto_en_km(k):
        for i in range(len(cum) - 1):
            if cum[i + 1] >= k:
                t = (k - cum[i]) / ((cum[i + 1] - cum[i]) or 1e-9)
                return (ruta[i][0] + t * (ruta[i + 1][0] - ruta[i][0]), ruta[i][1] + t * (ruta[i + 1][1] - ruta[i][1]))
        return ruta[-1]

    recs, sesion = [], {}
    if _es_gpx(fit):
        recs, sesion = _leer_gpx(fit)
    else:
        import fitdecode
        try:
            with fitdecode.FitReader(io.BytesIO(fit) if isinstance(fit, bytes) else str(fit)) as fr:
                for f in fr:
                    if isinstance(f, fitdecode.FitDataMessage):
                        d = {x.name: x.value for x in f.fields}
                        if (f.name == 'record' and d.get('position_lat') is not None
                                and d.get('position_long') is not None and d.get('timestamp')):
                            recs.append((d['timestamp'], d['position_lat'] * SC, d['position_long'] * SC))
                        elif f.name == 'session':
                            sesion = d
        except Exception as exc:
            raise ValueError(f'no se pudo leer el FIT ({exc.__class__.__name__})')
    if len(recs) < 10:
        raise ValueError('el fichero no trae posiciones GPS con hora')

    # km de ruta de cada punto, siempre hacia delante (como la web), en km oficiales
    # ventana que solo avanza: antes recorría la ruta entera por cada punto y un
    # FIT largo tenía el servidor minutos ocupado
    km, kms, j0 = 0.0, [], 0
    for _, la, lo in recs:
        mejor, mk = 1e9, km
        while j0 < len(ruta) - 1 and cum[j0] < km - 0.5:
            j0 += 1
        for j in range(j0, len(ruta)):
            if cum[j] > km + 8:
                break
            dd = hav((la, lo), ruta[j])
            if dd < mejor:
                mejor, mk = dd, cum[j]
        if mejor < 0.15:
            km = max(km, mk)
        kms.append(km)
    kms = [k * total_oficial / cum[-1] for k in kms]

    meta_pt = ruta[-1]
    # salida: primer punto desde la hora oficial de salida
    i0 = next((i for i, (t, la, lo) in enumerate(recs) if t >= salida_oficial), None)
    if i0 is None:
        raise ValueError(f'el FIT termina antes de la salida oficial ({salida_oficial:%d/%m %H:%M}): ¿es de otra carrera?')
    # meta: punto más cercano a meta en el último tramo (últimos 3,5 km de ruta)
    finales = [i for i in range(i0, len(recs)) if kms[i] > total_oficial - 3.5]
    if not finales:
        raise ValueError(f'el FIT no llega a meta (se queda en el km {kms[-1]:.1f} de {total_oficial:g})')
    i1 = min(finales, key=lambda i: hav(recs[i][1:], meta_pt))
    llegada = recs[i1][0]

    tramo = recs[i0:i1 + 1]
    dist = sum(hav(a[1:], b[1:]) for a, b in zip(tramo, tramo[1:]))

    # pasos por avituallamiento: momento de máxima cercanía a la chincheta
    pasos, desde = [], i0
    for s in avis:
        pin = punto_en_km(s['km'] * cum[-1] / total_oficial)
        candidatos = [i for i in range(desde, i1 + 1) if abs(kms[i] - s['km']) < 3]
        if not candidatos:
            continue
        i = min(candidatos, key=lambda k: hav(recs[k][1:], pin))
        if hav(recs[i][1:], pin) > 0.3:
            continue
        pasos.append({'nombre': s['name'], 'km': s['km'], 'hora': recs[i][0].isoformat(),
                      'principal': bool(s.get('principal')), 'taller': bool(s.get('taller'))})
        desde = i

    # traza cada 20 s (hora relativa a la salida oficial)
    traza, ultimo = [], None
    for t, la, lo in tramo:
        if ultimo is None or (t - ultimo).total_seconds() >= 20:
            traza.append([round(la, 5), round(lo, 5), int((t - salida_oficial).total_seconds())])
            ultimo = t
    traza.append([round(meta_pt[0], 5), round(meta_pt[1], 5), int((llegada - salida_oficial).total_seconds())])

    mov = sesion.get('total_timer_time') or 0
    return {
        'carrera': carrera.get('nombre', ''),
        'salida': salida_oficial.isoformat(),
        'llegada': llegada.isoformat(),
        'tiempo_oficial_s': int((llegada - salida_oficial).total_seconds()),
        'tiempo_movimiento_s': int(mov),
        'distancia_km': round(dist, 1),
        'desnivel_m': sesion.get('total_ascent'),
        'pulso_medio': sesion.get('avg_heart_rate'),
        'cadencia_media': sesion.get('avg_cadence'),
        'velocidad_media_mov': round(dist / (mov / 3600), 1) if mov else None,
        'pasos': pasos,
        'traza': traza,
    }


def main():
    if len(sys.argv) != 2:
        sys.exit('uso: python herramientas/generar_resultado.py actividad.fit')
    try:
        res = generar(pathlib.Path(sys.argv[1]))
    except ValueError as exc:
        sys.exit(str(exc))
    tmp = RAIZ / '.resultado.json.tmp'          # entero o nada: la web lo lee mientras tanto
    tmp.write_text(json.dumps(res, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(RAIZ / 'resultado.json')
    h, m = divmod(res['tiempo_oficial_s'] // 60, 60)
    print(f"tiempo oficial {h}h {m:02d}m · {res['distancia_km']} km · media en movimiento {res['velocidad_media_mov']} km/h")
    print(f"pasos por avituallamiento: {len(res['pasos'])} · traza {len(res['traza'])} puntos")
    for p in res['pasos']:
        print(f"   {p['hora'][11:16]} UTC  km {p['km']:5}  {p['nombre']}")


if __name__ == '__main__':
    main()
