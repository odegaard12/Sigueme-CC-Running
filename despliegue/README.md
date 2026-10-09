# Despliegue en dos Raspberry Pi

Dos Pis sirven la misma web; una IP flotante (keepalived, VRRP) apunta a la que
está activa y el túnel de Cloudflare va a esa IP. Si la activa cae, la otra
coge la IP en ~20 s y sigue sola (también con el lector de iGPSPORT, que solo
corre en la que tiene la IP).

| Fichero | Dónde va | Qué hace |
|---|---|---|
| `sigueme.service` | `/etc/systemd/system/` (las dos) | El servidor. Poner la clave del panel en `ADMIN_TOKEN`. |
| `keepalived-sigueme.conf` | bloque dentro de `/etc/keepalived/keepalived.conf` (las dos) | IP flotante. Prioridad 101 en una y 100 en la otra; el resto igual. |
| `replicar.sh` + `sigueme-replica.{service,timer}` | `~/` y systemd (las dos) | Cada 20 s copia la carpeta de la web a la otra Pi, **solo desde la que tiene la IP**. |
| `desplegar.sh` | `~/` de una de ellas | Copia los ficheros nuevos a las dos y reinicia si cambió `server.py`. |

Rellenar en las plantillas: `IP_FLOTANTE`, `IP_OTRA_PI`, `USUARIO`, `CLAVE_VRRP`.

## Por qué así (lecciones aprendidas)

- **`nopreempt` y `state BACKUP` en las dos.** Con una MASTER que recupera la IP
  al volver, volvía con su `live.json` viejo y la réplica lo copiaba encima de
  los datos buenos de la otra: se perdían distancia, pulso y la llegada a meta.
- **`chk_leguas weight 0`.** Con `nopreempt`, bajar la prioridad no hace ceder
  la IP; un fallo del servidor tiene que pasar la instancia a FAULT.
- **Réplica en las dos direcciones**, siempre desde la que tiene la IP.
- **Desplegar en las dos a la vez**: si solo se copia a una y la IP está en la
  otra, la réplica machaca lo nuevo con lo viejo.
- Copiar `server.py` no basta: el servicio de la otra Pi hay que reiniciarlo.

## Probar la conmutación

1. Parar el servicio en la activa: la IP pasa a la otra en ~20 s.
2. Mandar puntos (Traccar/reloj): los recibe la otra.
3. Arrancar la primera: la IP se queda donde está y la réplica le copia los datos.
4. Parar la otra: la IP vuelve sin perder nada.
