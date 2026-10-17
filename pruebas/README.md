# Pruebas

Todas arrancan el servidor de verdad en una carpeta temporal, con los datos de
ejemplo del repo y un GPX inventado. No tocan nada fuera de esa carpeta.

| Prueba | Qué comprueba |
| --- | --- |
| `gpx.py` | El lector de GPX: desnivel sin ruido del GPS, elevación con coma, UTF-16 sin BOM. |
| `servidor.py` | Panel (sesión, CSRF, bloqueo por intentos), subir GPX/FIT, datos de la carrera, avituallamientos, plan para la app. |
| `ensayo.py` | Una carrera entera: preparar, EMPEZAR desde la app, corte de cobertura, meta sola, Finalizar, FIT, archivar. |
| `carga.py [N]` | N espectadores pidiendo el directo cada segundo mientras llegan posiciones. |
| `rendimiento.py` | La web en un móvil lento (4G floja, CPU ×4): tiempos y errores de consola. Necesita Playwright. |

```bash
python pruebas/servidor.py
```

Las corre GitHub Actions en cada cambio (`.github/workflows/pruebas.yml`). La
app Android tiene las suyas en `android/` (pruebas de la JVM y una carrera en
el emulador contra este mismo servidor).
