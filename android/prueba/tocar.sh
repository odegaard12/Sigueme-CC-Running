#!/bin/bash
# Toca en el emulador el elemento con ese texto exacto (uiautomator). Sale con error si no está.
adb shell uiautomator dump /sdcard/t.xml >/dev/null 2>&1
adb pull /sdcard/t.xml /tmp/t.xml >/dev/null 2>&1
XY=$(python3 - "$1" <<'PY'
import re, sys
s = open('/tmp/t.xml', encoding='utf-8').read()
m = re.search(r'text="' + re.escape(sys.argv[1]) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', s)
if not m:
    sys.exit(1)
a, b, c, d = map(int, m.groups())
print((a + c) // 2, (b + d) // 2)
PY
) || exit 1
adb shell input tap $XY
