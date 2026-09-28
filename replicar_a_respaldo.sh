#!/bin/bash
# Replica la web de la carrera de la Pi titular (.103) al respaldo (.104).
#
# Solo corre si ESTA Pi tiene puesta la VIP IP_FLOTANTE: si la carrera la
# está sirviendo la otra, copiar en esta dirección machacaría los datos buenos
# del titular con los del respaldo parado.
set -u

VIP="IP_FLOTANTE"
# En la .104 va el mismo script con DESTINO la .103: la réplica sale de la
# que tenga la VIP (con nopreempt puede quedarse en la .104 tras una caída).
DESTINO="USUARIO@IP_OTRA_PI"
ORIGEN="/home/USUARIO/sigueme/"
LOG="/home/USUARIO/sigueme_replica.log"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

if ! ip -4 addr show eth0 | grep -q "inet ${VIP}/"; then
    exit 0
fi

if cambios=$(rsync -a --delete --itemize-changes \
        --exclude '__pycache__' --exclude '*.bak*' --exclude '*.tmp' \
        -e "$SSH" \
        "$ORIGEN" "${DESTINO}:/home/USUARIO/sigueme/" 2>>"$LOG"); then
    # solo se apunta cuando se copió algo de la web (no el live.json de cada
    # vez): antes era una línea cada 20 s, ~190 KB al día
    if grep -v ' live\.json$' <<< "$cambios" | grep -q '^[<>c]f'; then
        log "OK: copiado al respaldo: $(grep -v ' live\.json$' <<< "$cambios" | grep '^[<>c]f' | awk '{print $2}' | tr '\n' ' ')"
    fi
else
    log "ERROR: fallo la replica al respaldo"
    exit 1
fi

# ⚠️ Copiar server.py no basta: el respaldo sigue ejecutando el código viejo
# que tiene en memoria hasta que se reinicia. Pasó con el arreglo de
# Cloudflare: estuvo copiado en la .104 sin estar activo.
if grep -q ' server\.py$' <<< "$cambios"; then
    if $SSH "$DESTINO" 'sudo -n systemctl restart sigueme' 2>>"$LOG"; then
        log "OK: server.py cambió, servicio del respaldo reiniciado"
    else
        log "ERROR: no se pudo reiniciar el servicio del respaldo"
    fi
fi
