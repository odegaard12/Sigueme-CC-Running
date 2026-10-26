# Sígueme CC para relojes Garmin (Connect IQ) · EXPERIMENTAL

Miniapp de reloj (`watch-app`) que **graba la actividad** y **manda posición y pulso a la web** (`/api/gps`), como la
miniapp de Amazfit. Usa el móvil (Bluetooth) para salir a internet; sin móvil guarda hasta 600 puntos y los manda al volver.

> **Estado: sin compilar ni probar en un reloj real.** Está escrita con la documentación de Connect IQ pero no se ha podido
> compilar (hace falta el SDK de Garmin) ni probar. Puede necesitar retoques: es un punto de partida.

## Qué hace
- **START**: empieza o pausa la grabación (una actividad de carrera que se guarda en Garmin Connect).
- **ATRÁS**: pregunta «¿Guardar y salir?» y guarda la actividad.
- Cada 10 s manda un lote de puntos en el mismo formato que Traccar Client (el que ya entiende la web), con
  `origen: garmin` y el pulso.
- La pantalla enseña el estado, la calidad del GPS, el pulso y cuántos puntos esperan a enviarse.

## Cómo compilarla
1. Instala el [SDK de Connect IQ](https://developer.garmin.com/connect-iq/sdk/) y, en Visual Studio Code, la extensión
   «Monkey C».
2. Abre la carpeta `garmin/`. En `manifest.xml` están algunos modelos (Forerunner 255/265/955/965, Fenix 7, Venu 2/3):
   añade el de tu reloj con «Monkey C: Edit Products» (los identificadores no coinciden con el nombre comercial).
3. «Monkey C: Build for Device» y elige tu modelo. Sale un `.prg`.
4. Conecta el reloj por USB y copia el `.prg` a la carpeta `GARMIN/APPS` del reloj.

## Cómo configurarla (la limitación importante)
La app necesita dos datos: **dirección de la web** e **identificador** (panel → Móvil → Sin la app → Ver la configuración).
Vale pegar el **enlace de configuración** del panel en el primer campo: saca de él los dos.

- **Instalada desde la tienda de Connect IQ** (o como app de pruebas privada de tu cuenta de desarrollador): los dos
  campos se editan en Garmin Connect, en los ajustes de la app.
- **Copiada por USB (sideload):** Garmin Connect no enseña sus ajustes. Para uso personal, escribe antes de compilar los
  valores por defecto en `resources/properties/properties.xml` (`<property id="url">` e `id`) y vuelve a compilar.

## Qué no hace (todavía)
- No usa el LiveTrack de Garmin (la web no lo lee).
- No lanza los avisos de subida y avituallamiento en el reloj: eso lo hace la app de Android (en iPhone no hay).
- No guarda la cola al cerrar la app; si se sale sin cobertura, los puntos pendientes se pierden (la actividad grabada sí queda).
