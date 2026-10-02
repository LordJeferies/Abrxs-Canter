# Soporte · reproducción Drive y Review / 02

Este documento puede adjuntarse a un chat de soporte junto con un diagnóstico sin tokens, nombres sensibles ni notas privadas.

## Qué significa cada síntoma

- `popup_closed`: la ventana de autorización se cerró o fue bloqueada. Abrir la página en Safari normal y pulsar Iniciar sesión desde allí. No significa que falló la transcripción de la app Mac.
- Se listan archivos pero no reproduce: el permiso para enumerar Drive no demuestra que el navegador pueda decodificar el original, ni que el visor integrado tenga cookies de la misma cuenta Google.
- Visor online pide acceso: abrir el enlace **Abrir en Drive**, comprobar cuenta y permisos. No cambiar el archivo a público para intentar arreglarlo. Un video recién subido puede estar aún procesándose en Google.
- Error 401 en Reproductor con tiempos: reconectar Drive y volver a seleccionar el video. El token se conserva solo en memoria y caduca; el sistema no promete reproducción offline.
- Error 403: comprobar restricciones de descarga, permisos, cuotas y acceso al archivo. El modo con tiempos necesita permiso para leer el contenido original.
- Error nativo 3/4: archivo o códec no admitido por el navegador, o respuesta multimedia no válida. Probar visor online de Google; su procesado no depende de decodificar directamente el original desde la página.
- Cancelación al cambiar de video: una carga antigua puede abortarse. No es, por sí sola, un fallo del nuevo video. Estas cancelaciones ya no abren Actividad como errores.

## Tiempos y privacidad

El iframe online es de Google y no entrega su cabezal a nuestra página. Las notas se escriben con tiempos manuales. En Reproductor con tiempos o video local, Marcar ahora sí usa el cabezal nativo. Cada nota conserva archivo, clave de procedencia y tiempo del archivo revisado; no se trata automáticamente como tiempo del máster de una transcripción.

El streaming autenticado usa rangos y no guarda videos ni tokens en la caché offline. El modo opcional Cargar clip completo sí transfiere el archivo completo a memoria, con confirmación y límite de 150 MB. No confundirlo con el visor online.

## Datos útiles para soporte

Indicar Safari/iOS/macOS y versión, web o PWA, modo de reproducción, tamaño y formato/códec del archivo si se conoce, si abre directamente en Drive y código concreto de Actividad. No adjuntar claves OAuth secretas, tokens ni archivos privados salvo decisión expresa del propietario.

Las pruebas de lógica no sustituyen una prueba de reproducción con la cuenta real. El cambio para solicitudes multimedia sin clientId protege una sesión aleatoria de corta duración y comprueba que su pestaña propietaria sigue dentro de la página; es una corrección de compatibilidad, no una afirmación de que ese fuera el único fallo observado.
