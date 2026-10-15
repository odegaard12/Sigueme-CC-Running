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
# carpetas (herramientas/, lib/): se copian dentro de la del mismo nombre
mapfile -t carpetas < <(find "$NUEVO" -mindepth 1 -maxdepth 1 -type d ! -name __pycache__)
[ $((${#ficheros[@]} + ${#carpetas[@]})) -gt 0 ] || { echo "nada que desplegar en $NUEVO"; exit 1; }
reiniciar=no
for f in "${ficheros[@]}"; do
  [ "$(basename "$f")" = server.py ] && ! cmp -s "$f" "$WEB/server.py" && reiniciar=si
done
[ "$reiniciar" = si ] && python3 -m py_compile "$NUEVO/server.py"   # no desplegar algo que no arranca
# PRIMERO en la Pi que tiene la IP flotante: su réplica va hacia la otra, y si
# se copiaba antes a la otra, la réplica podía devolverle lo viejo entre medias
aqui() { [ ${#ficheros[@]} -eq 0 ] || cp "${ficheros[@]}" "$WEB/"; [ ${#carpetas[@]} -eq 0 ] || cp -r "${carpetas[@]}" "$WEB/"; }
alli() { [ ${#ficheros[@]} -eq 0 ] || scp -q "${ficheros[@]}" "$OTRA:$WEB/"; [ ${#carpetas[@]} -eq 0 ] || scp -rq "${carpetas[@]}" "$OTRA:$WEB/"; }
if ip -4 addr show | grep -q "inet ${VIP}/"; then aqui; alli; else alli; aqui; fi
find "$NUEVO" -mindepth 1 -delete
if [ "$reiniciar" = si ]; then
  sudo systemctl restart sigueme
  ssh "$OTRA" 'sudo -n systemctl restart sigueme'
  sleep 2
  echo "servicio: aquí $(systemctl is-active sigueme) · otra $(ssh "$OTRA" systemctl is-active sigueme)"
fi
