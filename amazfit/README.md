# Sígueme para Amazfit (Zepp OS)

Miniapp para relojes Amazfit con Zepp OS 3 o superior (probada la compilación
para el Amazfit Balance, pantalla redonda de 480 px). Manda la **posición GPS
y el pulso del reloj** a la web de seguimiento, por el mismo camino que
Traccar (`/api/gps`).

```
reloj (GPS + pulso, cada 10 s)
  └─ Bluetooth → app Zepp del móvil (servicio de la miniapp)
                   └─ internet → https://odegaard12.online/api/gps
```

- **Sin el móvil al alcance**, los puntos esperan en el reloj (hasta ~4 h).
- **Sin cobertura en el móvil**, esperan en el móvil y se suben todos al
  volver, como hace Traccar.
- Mientras el reloj busca GPS, manda solo el pulso: la web lo muestra sin
  mover al corredor.

## Estado: versión 0.1, sin probar en el reloj

Compila con las herramientas oficiales de Zepp y el servidor está probado con
exactamente lo que envía el móvil, pero **no se ha ejecutado aún en un reloj
de verdad**. Limitación conocida: la app funciona **en primer plano** (deja la
pantalla encendida mientras sigue). Si abres el entrenamiento oficial del
reloj, la miniapp se cierra. Que siga en segundo plano (servicio de Zepp OS)
es lo siguiente a probar.

## Instalar en el reloj (modo desarrollador)

1. En la app **Zepp** del móvil: Perfil → Ajustes → Acerca de → pulsa 7 veces
   el logo para activar el **modo desarrollador**.
2. En el PC, dentro de esta carpeta:
   ```bash
   npm install
   npx zeus login
   npx zeus preview
   ```
   Elige el Amazfit Balance y sale un código QR.
3. En la app Zepp: Perfil → Ajustes → Modo desarrollador → **Escanear**, y
   lee el QR. La miniapp se instala en el reloj.
4. Si `zeus preview` pide un `appId` válido: crea la app en
   https://console.zepp.com y pon su número en `app.json` → `app.appId`.

> `npm install` con npm 11 avisa de scripts bloqueados: no pasa nada. Si
> `zeus` dice `Cannot find module 'zeppos-app-utils'`, falta el alias que ya
> trae `package.json` (`_moduleAliases`): hay que ejecutarlo desde esta
> carpeta.

## Configurar

En la app Zepp → la miniapp **Sígueme** → Ajustes:

- **Dirección del servidor:** `https://odegaard12.online/api/gps`
- **Identificador:** el de la tarjeta "GPS del móvil" del panel admin (el
  mismo que Traccar).

## Usar

Abre **Sígueme** en el reloj y pulsa **Empezar** al salir. En el panel admin,
la línea "GPS del móvil" tiene que decir "ahora mismo", y en la web sale tu
pulso. **Parar** al terminar (lo que quede pendiente se manda solo).

## Ficheros

| Fichero | Qué hace |
|---|---|
| `page/index.js` | Pantalla del reloj: GPS, pulso, cola de puntos y envío al móvil |
| `app-side/index.js` | Servicio en la app Zepp: guarda los puntos y los sube al servidor |
| `setting/index.js` | Ajustes en la app Zepp (servidor e identificador) |
| `app.json` | Permisos (GPS, pulso), pantalla redonda, versión de Zepp OS |
