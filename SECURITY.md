# Seguridad

## Cómo avisar de un fallo

No abras un *issue* público. Usa **Security → Report a vulnerability** en
GitHub (aviso privado). Se contesta en unos días.

## Qué cuenta

- Acceso al panel sin la clave, saltarse el bloqueo por intentos o la
  comprobación de origen (CSRF).
- Publicar o falsear posiciones sin el identificador del móvil.
- Que la web pública enseñe algo que no debe (identificador GPS, enlace de
  seguimiento, batería, datos de la carrera fuera de la zona visible).
- Lectura o escritura de ficheros fuera de la carpeta de la web.

## Lo que el proyecto ya hace

- El servidor solo usa la biblioteca estándar de Python.
- Ningún secreto vive en el repositorio: la clave del panel va en una variable
  de entorno (hash scrypt) y el identificador GPS en `gps.clave`, ignorado.
- La APK se firma en GitHub Actions con una clave guardada como secreto.

Versión soportada: la última publicada.
