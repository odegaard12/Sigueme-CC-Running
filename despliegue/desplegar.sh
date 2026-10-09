#!/bin/bash
# Copia lo que haya en ~/nuevo_sigueme a la web de LAS DOS Pis y reinicia el
# servicio si cambió server.py. Las dos a la vez: con la IP flotante en la otra,
# su réplica machacaría lo nuevo con lo viejo.
set -e
WEB=/home/USUARIO/sigueme
NUEVO=/home/USUARIO/nuevo_sigueme    # carpeta propia: ~/nuevo la usan otros proyectos
OTRA=IP_OTRA_PI
VIP=IP_FLOTANTE

mapfile -t ficheros < <(find "$NUEVO" -maxdepth 1 -type f)
[ ${#ficheros[@]} -gt 0 ] || { echo "nada que desplegar en $NUEVO"; exit 1; }
reiniciar=no
for f in "${ficheros[@]}"; do
  [ "$(basename "$f")" = server.py ] && ! cmp -s "$f" "$WEB/server.py" && reiniciar=si
done
[ "$reiniciar" = si ] && python3 -m py_compile "$NUEVO/server.py"   # no desplegar algo que no arranca
# PRIMERO en la Pi que tiene la IP flotante: su réplica va hacia la otra, y si
# se copiaba antes a la otra, la réplica podía devolverle lo viejo entre medias
if ip -4 addr show | grep -q "inet ${VIP}/"; then
  cp "${ficheros[@]}" "$WEB/"; scp -q "${ficheros[@]}" "$OTRA:$WEB/"
else
  scp -q "${ficheros[@]}" "$OTRA:$WEB/"; cp "${ficheros[@]}" "$WEB/"
fi
find "$NUEVO" -maxdepth 1 -type f -delete
if [ "$reiniciar" = si ]; then
  sudo systemctl restart sigueme
  ssh "$OTRA" 'sudo -n systemctl restart sigueme'
  sleep 2
  echo "servicio: aquí $(systemctl is-active sigueme) · otra $(ssh "$OTRA" systemctl is-active sigueme)"
fi
