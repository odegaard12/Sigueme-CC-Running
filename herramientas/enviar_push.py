"""Envía un aviso Web Push a varias suscripciones. Lo lanza avisos_web.py con el Python de ~/sigueme-push/.venv
(el único sitio con pywebpush). Entrada por stdin: {"subs": [...], "data": {...}}; argumento: la clave VAPID privada.
Salida: {"ok": n, "caducadas": [endpoints que el navegador ya dio de baja]}."""
import json, os, sys

from pywebpush import WebPushException, webpush

pem = sys.argv[1]
pedido = json.load(sys.stdin)
contacto = os.environ.get("VAPID_SUB", "mailto:avisos@example.com")
ok, caducadas = 0, []
for s in pedido.get("subs", []):
    try:
        webpush(subscription_info={"endpoint": s["endpoint"], "keys": s["keys"]}, data=json.dumps(pedido["data"]),
                vapid_private_key=pem, vapid_claims={"sub": contacto}, ttl=3600, timeout=10)
        ok += 1
    except WebPushException as e:
        if e.response is not None and e.response.status_code in (404, 410):
            caducadas.append(s["endpoint"])
    except Exception:  # noqa: BLE001 - una suscripción rota no corta las demás
        pass
print(json.dumps({"ok": ok, "caducadas": caducadas}))
