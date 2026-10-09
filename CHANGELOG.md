# Cambios

Versiones con [SemVer](https://semver.org/lang/es/): la última cifra para
arreglos, la del medio para funciones nuevas. Cada una tiene su etiqueta y su
release en GitHub.

## v1.1.0 · 2026-10-09
- Panel con **usuario y clave**; el servidor solo guarda el hash (scrypt), en un
  fichero que solo lee root. `python3 server.py --hash-clave` genera el hash.
- Sin datos personales: nombre de corredor «Odegaard12» y avatar O12 en vez de
  nombre real y foto.
- Versión visible al pie de la web. README con capturas, CHANGELOG y releases.

## v1.0.1 · 2026-10-09
- La IP flotante sale de la configuración del servicio (`VIP_SIGUEME`); sin
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
