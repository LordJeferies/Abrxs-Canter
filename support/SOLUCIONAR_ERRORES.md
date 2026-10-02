# Resolver problemas sin perder proyectos

## No se genera transcripción

1. Abrir Actividad y copiar desde inicio de trabajo hasta error final. Indicar motor elegido, duración y si avanzó el progreso. No iniciar otro trabajo a la vez.
2. Ejecutar DIAGNOSTICO_SEGURO_MAC.command. Comprobar FFmpeg/ffprobe y espacio libre. Verificar audio con ffprobe sobre el archivo, sin modificarlo. No basta que un motor esté disponible en Terminal: la app gráfica puede tener otro PATH.
3. Para whisper.cpp confirmar el archivo de modelo existente; no descargar modelos sin permiso. Para MLX comprobar el Python que usa realmente la app, no otro entorno.
4. Si dice permiso denegado, probar una copia del archivo en una carpeta autorizada sin borrar el original. Si el códec no es compatible, recomendar conversión a una copia, no sobrescribir.
5. Conservar stderr. Un mensaje genérico de salida 1 no demuestra falta de modelo ni de audio. El arreglo preparado para MLX evita declarar fallo después de una ejecución exitosa.

## Exportación FFmpeg

Guardar comando y stderr. VideoToolbox puede fallar; el motor debe reconstruir una orden válida con libx264, no cambiar solo el nombre del códec dejando opciones incompatibles. Confirmar encoder con `ffmpeg -encoders`. El exportador escribe primero `.partial.mp4` y renombra al terminar: un parcial no es una exportación completa. No borrar parciales sin confirmar si el usuario los necesita.

## Drive/iPhone

`origin_mismatch`: revisar origen JavaScript exacto (dominio, protocolo y puerto, sin ruta). `access_denied`: cuenta no añadida como test user o falta consentimiento. 403: API, permisos, cuota, política de cuenta o descarga bloqueada; distinguir por respuesta. 401: reconectar. popup_closed/failed: iniciar desde botón, abrir Safari, revisar bloqueo de ventanas. Reproducción sin duración: esperar metadatos; si no llega, revisar formato o conexión. La carga completa tiene límite de 150 MB; no descargar un máster grande silenciosamente.

## Recuperación y privacidad

Descargar Guardar proyecto antes de cambiar de origen, borrar datos o pasar entre Safari/PWA. Un registro no incluye deliberadamente credenciales, pero sí puede incluir rutas/nombres. Revisar antes de compartir. Una corrección de tiempo del montaje no se traduce automáticamente al máster reordenado.
