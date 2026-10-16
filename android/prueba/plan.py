# Plan inventado para el emulador: 5 km rectos al norte, una subida y un avituallamiento.
import json
g = 1 / 111.195
ruta = [[-4.0, round(40.8 + i * 0.05 * g, 6)] for i in range(101)]
plan = {"carrera": {"nombre": "Trail de prueba", "distancia_km": 5.0}, "ruta": ruta,
        "perfil": [[i * 0.05, 900 + i] for i in range(101)],
        "avisos": [{"id": 1, "km": 0.3, "tipo": "subida", "texto": "SUBIDA LARGA · 1,2km · 7% · +84m", "valido_hasta": 0.9},
                   {"id": 2, "km": 1.2, "tipo": "avituallamiento", "texto": "AVITUALLAMIENTO {dist} · Fuente", "valido_hasta": 1.7, "objetivo_km": 1.5}],
        "subidas": [{"inicio": 0.6, "fin": 1.8, "desnivel_m": 84, "largo_km": 1.2}],
        "avituallamientos": [{"name": "Fuente", "km": 1.5}], "restante": [[0, 84], [1.8, 0]]}
print(json.dumps(plan))
