#!/bin/bash
# Toca en el emulador el elemento con ese texto (uiautomator), sin distinguir mayúsculas: los botones de la app van en versalitas.
# Si no se ve en pantalla, baja un poco y lo vuelve a buscar. Sale con error si no está.
buscar() {
  adb shell uiautomator dump /sdcard/t.xml >/dev/null 2>&1
  adb pull /sdcard/t.xml /tmp/t.xml >/dev/null 2>&1
  python3 - "$1" <<'PY'
import re, sys
s = open('/tmp/t.xml', encoding='utf-8').read()
m = re.search(r'text="' + re.escape(sys.argv[1]) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', s, re.I)
if not m:
    sys.exit(1)
a, b, c, d = map(int, m.groups())
print((a + c) // 2, (b + d) // 2)
PY
}
XY=$(buscar "$1") || { adb shell input swipe 540 1800 540 700 300; sleep 1; XY=$(buscar "$1"); } || exit 1
adb shell input tap $XY
