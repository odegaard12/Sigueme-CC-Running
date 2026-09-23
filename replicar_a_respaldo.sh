#!/bin/bash
# Replica la web de 21 Leguas de la Pi titular (.103) al respaldo (.104).
#
# Solo corre si ESTA Pi tiene puesta la VIP 192.168.68.202: si la carrera la
# está sirviendo la otra, copiar en esta dirección machacaría los datos buenos
# del titular con los del respaldo parado.
set -u

VIP="192.168.68.202"
DESTINO="odegaard12@192.168.68.104"
ORIGEN="/home/odegaard12/21leguas/"
LOG="/home/odegaard12/21leguas_replica.log"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

if ! ip -4 addr show eth0 | grep -q "inet ${VIP}/"; then
    exit 0
fi

if rsync -a --delete \
        --exclude '__pycache__' \
        -e "ssh -o BatchMode=yes -o ConnectTimeout=10" \
        "$ORIGEN" "${DESTINO}:/home/odegaard12/21leguas/" 2>>"$LOG"; then
    log "OK: web y live.json replicados al respaldo"
else
    log "ERROR: fallo la replica al respaldo"
    exit 1
fi
