#!/bin/bash
# En el emulador: instala, mete un plan, empieza, mueve el GPS y comprueba que salen los avisos.
set -x
P=cc.sigueme.app
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
for p in ACCESS_FINE_LOCATION ACCESS_COARSE_LOCATION POST_NOTIFICATIONS; do adb shell pm grant $P android.permission.$p; done
adb shell dumpsys deviceidle whitelist +$P
adb shell am start -n $P/.MainActivity; sleep 6
adb exec-out screencap -p > capturas/1-sin-configurar.png
python3 android/prueba/plan.py > /tmp/plan.json
adb push /tmp/plan.json /data/local/tmp/plan.json
adb shell "run-as $P mkdir -p files && run-as $P cp /data/local/tmp/plan.json files/plan.json"
adb shell am force-stop $P; adb shell am start -n $P/.MainActivity; sleep 5
adb exec-out screencap -p > capturas/2-plan-listo.png
adb emu geo fix -4.0 40.8
adb shell uiautomator dump /sdcard/ui.xml >/dev/null; adb pull /sdcard/ui.xml /tmp/ui.xml
XY=$(python3 -c "import re;s=open(\"/tmp/ui.xml\",encoding=\"utf-8\").read();m=re.search(r\"text=.EMPEZAR SEGUIMIENTO.[^>]*bounds=.\[(\d+),(\d+)\]\[(\d+),(\d+)\]\",s);a,b,c,d=map(int,m.groups());print((a+c)//2,(b+d)//2)")
adb shell input tap $XY; sleep 4; adb shell input keyevent KEYCODE_BACK; sleep 1
for i in $(seq 0 32); do adb emu geo fix -4.0 $(python3 -c "print(40.8 + $i*0.05/111.195)"); sleep 2; done
sleep 3
adb exec-out screencap -p > capturas/3-siguiendo.png
adb shell cmd statusbar expand-notifications; sleep 2
adb exec-out screencap -p > capturas/4-avisos.png
adb shell dumpsys notification --noredact > capturas/notificaciones.txt
grep -c "SUBIDA LARGA" capturas/notificaciones.txt; grep -c "AVITUALLAMIENTO" capturas/notificaciones.txt
grep -q "SUBIDA LARGA" capturas/notificaciones.txt && grep -q "AVITUALLAMIENTO" capturas/notificaciones.txt && echo AVISOS_OK > capturas/resultado.txt || echo AVISOS_MAL > capturas/resultado.txt
cat capturas/resultado.txt
