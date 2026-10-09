# Cambios

Versiones con [SemVer](https://semver.org/lang/es/): la última cifra para
arreglos, la del medio para funciones nuevas. Cada una tiene su etiqueta y su
release en GitHub.

## v1.3.0 · 2026-10-09
- **Para cualquier carrera:** nombre, fecha, hora de salida, distancia, límite,
  km mínimos para meta, corredor y bici salen de `carrera.json`; el código no
  nombra ninguna carrera.
- `herramientas/preparar_ruta.py`: crea la ruta y el perfil desde un GPX.
- `generar_resultado.py` toma la fecha, la hora y la distancia de `carrera.json`.
- README como guía paso a paso (preparar la carrera, arrancar, día de carrera,
  después); README del reloj con el estado en la tienda y la instalación.
- Plantillas de despliegue con nombres genéricos (`sigueme.service`,
  `SIGUEME_VIP`).

## v1.2.0 · 2026-10-09
- Botón de compartir en la cabecera (menú de compartir en el móvil, copiar el
  enlace en el PC) y vista previa con imagen al compartir el enlace.
- Seguridad (revisión): como mucho dos cálculos de clave a la vez (antes una
  ráfaga de logins podía agotar la memoria), usuario o cookie con «ñ» ya no
  rompen la petición, el freno a la fuerza bruta ya no bloquea al panel con
  sesión, conexiones lentas cortadas a los 20 s, rutas normalizadas y ficheros
  ocultos nunca servidos.
- Panel: un solo sondeo aunque se entre varias veces.
- robots.txt: el panel y la API fuera de los buscadores.
- Plantilla del servicio con `SIGUEME_VIP` activa (se había quedado comentada).

## v1.1.1 · 2026-10-09
- Licencia MIT.
- Ficha del repo en GitHub: descripción, web y temas.

## v1.1.0 · 2026-10-09
- Panel con **usuario y clave**; el servidor solo guarda el hash (scrypt), en un
  fichero que solo lee root. `python3 server.py --hash-clave` genera el hash.
- Sin datos personales: nombre de corredor «Odegaard12» y avatar O12 en vez de
  nombre real y foto.
- Versión visible al pie de la web. README con capturas, CHANGELOG y releases.

## v1.0.1 · 2026-10-09
- La IP flotante sale de la configuración del servicio (`SIGUEME_VIP`); sin
  ella, el servidor funciona como una sola máquina.
- `generar_resultado.py`: el FIT se pasa por argumento y la web se busca en la
  raíz del repo (desde `herramientas/` no encontraba el trazado).

## v1.0.0 · 2026-10-09
- La app pasa a llamarse **Sígueme CC**, con icono nuevo (también en el reloj).

## v0.7.1 · 2026-10-09
- Repo ordenado: README, plantillas de despliegue sin datos de la red y
  saltos de línea LF. Se despliega primero en la Pi que tiene la IP flotante.

## v0.7.0 · 2026-10-08
- Login real del panel: cookie de sesión HttpOnly firmada (12 h) en vez de
  guardar la clave en el navegador. Cabeceras de seguridad y CSP en el panel.

## v0.6.0 · 2026-09-28
- Alta disponibilidad sin perder datos: keepalived con `nopreempt`, la IP se
  queda donde está al volver una Pi y la réplica sale de la que la tiene.

## v0.5.1 · 2026-09-28
- Pasada de errores: lotes de Traccar con forma rara, puntos GPS locos, batería
  por URL, primera carga colgada, horas en hora de España.

## v0.5.0 · 2026-09-28
- Miniapp para relojes Amazfit (Zepp OS): posición y pulso del reloj a la web.
- Servidor: un solo origen de posición (móvil o reloj), pulso del reloj sobre el
  de iGPSPORT, velocidad calculada, aviso de identificador incorrecto.

## v0.4.1 · 2026-09-28
- Web fiable con mala cobertura: tiempo máximo por petición, una sola a la vez,
  aviso de conexión y puesta al día al volver.

## v0.4.0 · 2026-09-28
- Modo resultado: tiempo final, paso por avituallamientos y repetición de la
  carrera. Carga sin pantalla vacía y diseño para móvil, horizontal y PC.

## v0.3.0 · 2026-09-27
- GPS del móvil con Traccar Client, con cola sin cobertura. Convivencia con
  iGPSPORT, sensores caducados ocultos, carrera solo con Traccar, meta detectada
  aunque el seguimiento empiece a mitad y «Finalizar» con hora de llegada.

## v0.2.0 · 2026-09-24
- Seguimiento fluido pegado al trazado, cámara que sigue al corredor, mapa que
  se rehace solo si se cuelga y menos batería en el móvil de quien mira.

## v0.1.0 · 2026-09-24
- Primera versión: mapa 3D con la posición sobre el trazado, perfil,
  avituallamientos, panel y lector del directo de iGPSPORT.
