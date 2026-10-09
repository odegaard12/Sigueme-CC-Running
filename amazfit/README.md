# Sígueme CC para relojes Amazfit (Zepp OS)

Miniapp que manda la **posición GPS y el pulso del reloj** a tu servidor de
Sígueme CC, por el mismo camino que Traccar (`/api/gps`).

```
reloj (GPS + pulso, cada 10 s)
  └─ Bluetooth → app Zepp del móvil (servicio de la miniapp)
                   └─ internet → https://tu-dominio/api/gps
```

- **Sin el móvil al alcance**, los puntos esperan en el reloj (hasta ~4 h).
- **Sin cobertura en el móvil**, esperan en el móvil y se suben todos al volver.
- Mientras busca GPS manda solo el pulso: la web lo enseña sin mover al corredor.
- Si la app se cierra, al volver a abrirla sigue sola sin perder puntos.

## ¿Está en la tienda de Amazfit (Zepp App Store)?

**Todavía no.** De momento se instala en **modo desarrollador** (abajo). Para
publicarla en la tienda hace falta:

1. Probarla en un reloj de verdad (aún no se ha probado fuera del simulador de
   compilación).
2. Una cuenta de desarrollador en [console.zepp.com](https://console.zepp.com)
   y crear allí la app (da el `appId` definitivo para `app.json`).
3. Capturas, descripción y política de privacidad, y enviarla a revisión.

Ten en cuenta que la miniapp necesita **un servidor de Sígueme CC propio** (la
dirección y el identificador se ponen en sus ajustes): en la tienda sería útil
para quien monte el suyo.

## Compatibilidad

Relojes con **Zepp OS 3 o superior** (probada la compilación para el Amazfit
Balance, pantalla redonda de 480 px).

**Limitación conocida:** funciona **en primer plano**, con la pantalla
encendida. Si abres el entrenamiento oficial del reloj, la miniapp se cierra.

## Instalarla (modo desarrollador)

1. En la app **Zepp** del móvil: Perfil → Ajustes → Acerca de → pulsa 7 veces el
   logo. Se activa el **modo desarrollador**.
2. En un ordenador con [Node.js](https://nodejs.org) 18 o superior, dentro de
   esta carpeta:
   ```bash
   npm install
   npx zeus login        # con tu cuenta de Zepp
   npx zeus preview      # elige tu reloj: sale un código QR
   ```
3. En la app Zepp: Perfil → Ajustes → Modo desarrollador → **Escanear**, y lee el
   QR. La miniapp se instala en el reloj.

> Si `npx zeus` dice `Cannot find module 'zeppos-app-utils'`, ejecútalo desde
> esta carpeta: el alias que lo arregla está en `package.json` (`_moduleAliases`).
> Si pide un `appId` válido, crea la app en console.zepp.com y pon su número en
> `app.json` → `app.appId`.

## Configurarla

En la app Zepp → **Sígueme CC** → Ajustes:

- **Dirección del servidor:** `https://tu-dominio/api/gps`
- **Identificador:** el de la tarjeta «GPS del móvil» del panel (el mismo que Traccar).

## Usarla

Abre **Sígueme CC** en el reloj y pulsa **Empezar** al salir. En el panel, la
línea «GPS del móvil» tiene que decir «ahora mismo» y en la web sale tu pulso.
Mientras sigue, el botón atrás no la cierra: sal con **Parar** (lo pendiente se
manda solo).

## Ficheros

| Fichero | Qué hace |
|---|---|
| `page/index.js` | Pantalla del reloj: GPS, pulso, cola de puntos y envío al móvil |
| `app-side/index.js` | Servicio en la app Zepp: guarda los puntos y los sube al servidor |
| `setting/index.js` | Ajustes en la app Zepp (servidor e identificador) |
| `app.json` | Permisos (GPS, pulso), pantalla redonda, versión de Zepp OS |
