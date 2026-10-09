#!/bin/bash
# Copia la carpeta de la web a la otra Pi. Va en LAS DOS y solo actúa en la que
# tiene la IP flotante: copiar desde la parada machacaría los datos buenos.
set -u

VIP="IP_FLOTANTE"
DESTINO="USUARIO@IP_OTRA_PI"
WEB="/home/USUARIO/sigueme/"
LOG="/home/USUARIO/sigueme_replica.log"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

ip -4 addr show | grep -q "inet ${VIP}/" || exit 0

if cambios=$(rsync -a --delete --itemize-changes \
        --exclude '__pycache__' --exclude '*.bak*' --exclude '*.tmp' \
        -e "$SSH" "$WEB" "${DESTINO}:${WEB}" 2>>"$LOG"); then
    # se apunta solo si cambió algo más que live.json (si no, una línea cada 20 s)
    copiados=$(grep -v ' live\.json$' <<< "$cambios" | grep '^[<>c]f' | awk '{print $2}' | tr '\n' ' ')
    [ -n "$copiados" ] && log "OK: copiado: $copiados"
else
    log "ERROR: fallo la replica"
    exit 1
fi

# copiar server.py no basta: la otra Pi sigue con el código viejo en memoria
if grep -q ' server\.py$' <<< "$cambios"; then
    $SSH "$DESTINO" 'sudo -n systemctl restart sigueme' 2>>"$LOG" \
        && log "OK: server.py cambió, servicio de la otra Pi reiniciado" \
        || log "ERROR: no se pudo reiniciar el servicio de la otra Pi"
fi
