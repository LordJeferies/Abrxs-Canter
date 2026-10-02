# Abrxs Review · instalación y Drive

## Cambios locales del estudio de revisión

### Review 05 · reproducción y recuperación

Drive sigue siendo el visor inicial para todos los videos: seleccionar no descarga el archivo completo. Abrir en Drive siempre enlaza al archivo concreto; puedes verlo en el navegador o la app de Google y regresar para escribir la nota. No hay una capa de controles Abrxs sobre el iframe. Los controles internos de Google/iOS no pueden modificarse desde esta página.

En iPhone, si no existe pantalla completa del navegador para el iframe, se indica Abrir en Drive en lugar de estirar el marco a toda la altura. El reproductor nativo opcional utiliza una carga completa para clips de hasta 32 MB y streaming para tamaños mayores; Cargar clip completo sigue siendo una acción confirmada limitada a 150 MB. Se cancela la carga anterior al cambiar de archivo o modo y se reinicia el video nativo al inicio al cargar los metadatos. Si falla o no está listo en 20 segundos, aparece una explicación debajo del visor y la alternativa de Drive; la descarga completa tiene un límite de espera de 45 segundos.

No se descarga un podcast largo automáticamente ni se vuelve a transcribir. Las pruebas comprueban la lógica de selección, cancelación y notas, no certifican la reproducción de un archivo privado en Safari/iPhone. Las grabaciones anteriores muestran controles superpuestos dentro del visor externo y problemas al cambiar de modo: no se consideran solucionados solo con pruebas de DOM.

### Historial · Review 04

Review 04: notas siempre con tiempos manuales. Pausar, reproducir o escribir no rellena ni altera Desde/Hasta. Las barras son un ajuste manual, no un reloj sincronizado. Editar tiempos manuales enfoca el campo de inicio. Se permite guardar una nota aunque el reproductor nativo aún no tenga metadatos; si la duración es conocida, se validan los límites.

El visor está en una superficie separada, sin notas ni controles propios superpuestos. En modo Google se ocultan Ver selección/Ver completo de la página. El marco respeta las dimensiones conocidas del video (16:9 si no hay información). Pantalla completa utiliza la API del navegador; en Safari/iPhone sin esa API abre una vista ampliada sin notas y mantiene Abrir en Drive como alternativa. Los controles que Google/Safari dibujan dentro del iframe no son controlables por esta página: toca fuera para ocultarlos o utiliza la pantalla completa de su reproductor.

El explorador abre una ventana amplia de carpetas. Selecciona todos los videos o videos/imágenes de la carpeta actual y Añadir selección a revisión. La lista lateral conserva solo lo elegido y permite ordenar/quitar. No recorre subcarpetas automáticamente. Los TXT/JSON se pueden abrir como transcripciones con tiempos; el paquete editorial que asocia cada clip a su texto todavía está pendiente.

El visor es ampliable. Las imágenes individuales admiten notas identificadas; el carrusel comparativo y la aprobación todavía están pendientes. Todos los tiempos de notas se introducen manualmente. Google no expone sus eventos al HTML y no se usa un cronómetro ficticio. Las capas internas de Google y la compatibilidad real de Safari no se pueden certificar con pruebas de DOM.

Copiar revisión con enlaces incluye nombre, archivo, carpeta y tiempos. Autorizar guardado en Drive solicita adicionalmente drive.file; Subir TXT crea un documento nuevo por carpeta de origen después de confirmar. La cuenta debe poder añadir archivos y la carpeta debe estar autorizada a la aplicación. Si Google deniega acceso, descarga el TXT y súbelo manualmente; no se solicita permiso de modificación total de Drive. Actualiza la configuración OAuth si vas a usar esa función. Nunca se reemplazan videos ni imágenes.

Estos cambios locales no se publican automáticamente. La subida real y Safari/PWA deben probarse manualmente antes de distribuirlos a clientes.

Página estática para revisión y fichas. No necesita npm, modelos ni servidor privado. Incluye los archivos HTML, CSS y JS: hay que subir **todos**, no solo index.html. GitHub Pages sirve la interfaz pública; no aloja tus videos de Drive.

## Configurar Google una sola vez

1. En https://console.cloud.google.com/ crea un proyecto y habilita **Google Drive API**.
2. En Google Auth Platform configura nombre, correo y audiencia. Para uso personal, déjalo en pruebas y añade tu cuenta como usuario de prueba. Google puede exigir volver a autorizar sesiones; el acceso no es permanente.
3. Crea un cliente OAuth de tipo **Aplicación web**. En orígenes JavaScript autorizados añade `https://lordjeferies.github.io` y, para probar en Mac, `http://localhost:8765`. El origen no lleva `/nombre-del-repo/`. No necesitas secreto de cliente, cuenta de servicio ni clave API en esta página.
4. Copia el **ID público**, terminado en `.apps.googleusercontent.com`. En la página abre Configurar conexión a Drive, pégalo, pulsa Preparar inicio de sesión y después Iniciar sesión en Drive. Las dos acciones evitan abrir una ventana de Google fuera del gesto del usuario.
5. Autoriza lectura y pega el enlace de tu carpeta. También puedes navegar desde Mi Drive. Abrir y revisar no cambia archivos. La escritura de TXT es una acción separada y explícita.

Esta versión usa `drive.readonly`: permite leer archivos de la cuenta, no solo una carpeta. La UI navega por la carpeta elegida, pero **el permiso es amplio**. Se eligió así porque `drive.file` con Picker no concede automáticamente acceso a todos los hijos de una carpeta. Solo conecta una cuenta que quieras autorizar. Para distribuir la conexión a otras personas, revisa los requisitos de verificación de Google para scopes restringidos; publicar el HTML no completa esa verificación.

Fuentes oficiales: https://developers.google.com/workspace/drive/api/quickstart/js · https://developers.google.com/identity/oauth2/web/guides/use-token-model · https://developers.google.com/workspace/drive/api/guides/api-specific-auth

## Publicar en GitHub Pages (cuando tú decidas)

Sube el contenido de esta carpeta a la raíz de un repositorio dedicado, por ejemplo `Abrxs-Review`. No subas videos, transcripciones, copias de proyecto, registros ni secretos. En Settings → Pages selecciona Deploy from a branch, main, /(root). La dirección será `https://lordjeferies.github.io/Abrxs-Review/`. No cambia el repositorio de la app. Puedes alojarlo en una subcarpeta también: las rutas son relativas.

En iPhone abre la dirección en Safari → Compartir → Añadir a pantalla de inicio → abrir como app web. Si Google bloquea la ventana desde la app instalada, abre la misma dirección en Safari y conecta allí. Son entornos que pueden guardar borradores separados: exporta una copia para transferirlos. No se ha probado todavía tu sesión OAuth ni un iPhone real.

## Usar

- Conecta Drive y elige un video, o abre un video del dispositivo. El streaming privado usa peticiones parciales; el token solo vive en memoria. Si el navegador suspende el reproductor, reconecta y selecciona de nuevo el video. Nunca se añade el token al enlace.
- Si el streaming falla, Cargar clip completo descarga a memoria únicamente videos de hasta 150 MB y pide confirmación. Para másteres grandes, descarga desde Drive y abre como archivo local. MP4 H.264/AAC es la opción de mayor compatibilidad; no se convierte el video desde esta página.
- Escribe Desde/Hasta mirando el contador del video, añade comentario y guarda. Pausar o escribir no cambia los tiempos. Los tiempos de notas pertenecen al **archivo revisado**. Un montaje reordenado no tiene una conversión simple al máster. No se inventa esa relación.
- Carga JSON `words`/`segments`, SRT, VTT o TXT `[00:00:10.000 --> 00:00:15.000] texto`. Sin tiempos no puede seleccionarse con precisión. Si solo hay tiempos por frase, la selección es por frase, no por palabra ficticia.
- Escribe el nombre exacto del máster. Toca el primer y el último fragmento, añade bloque, crea otras fichas y ordena con ↑ ↓. Ajusta los tiempos de cada bloque para empezar antes o terminar después. La referencia reproduce solo ese intervalo si has abierto el máster con ese nombre; debes comprobar que sea el archivo correcto.
- Exporta Cortes TXT/JSON. Ambos contienen el mismo JSON editorial compatible con el importador de Mac. Selecciona **el mismo máster** allí. El importador actual añade normalmente 0.2 s de margen: revisa antes de renderizar. Las notas TXT/JSON son documentos de revisión, **no órdenes de corte automáticas**.
- Guardar proyecto descarga una copia completa con notas, transcripción y fichas. No contiene videos ni tokens. Abrir copia recupera el trabajo. El borrador del navegador puede perderse si borras datos, cambia el origen o iOS libera almacenamiento: descarga copias regularmente.

## Privacidad y límites

Sin analítica, anuncios ni envío de notas a un servicio propio. El inicio de sesión contacta Google y Drive; Google aplica sus políticas. El ID OAuth público se guarda localmente; el token nunca se guarda en localStorage ni en caché. El service worker guarda solamente los archivos públicos de interfaz. No hay sincronización automática; la escritura de TXT requiere permiso y acción explícita. La página no transcribe, analiza con IA ni renderiza: entrega decisiones a la app local. El mapa no es un editor de efectos ni una imagen generada.

La interfaz utiliza formas, bordes y textura de puntos creados con CSS/SVG. No hay una imagen de interfaz fingiendo controles funcionales. Se adaptó el patrón OAuth del repositorio oficial `googleworkspace/browser-samples` (Apache-2.0); se conserva su licencia. Se evitó copiar el repositorio completo o añadir una librería de arrastre: los controles ↑ ↓ funcionan también con touch y teclado.
# Review / 02 · reproducción y biblioteca

La selección de un video abre ahora el visor online de Google Drive. No se descarga primero el archivo completo, no se hace público y no se envía el token OAuth en la URL del visor. El visor utiliza la sesión web de Google: en Safari/PWA, restricciones de cookies, cuenta equivocada, permisos o procesamiento pendiente de Google pueden impedir verlo. Usa **Abrir en Drive** con la misma cuenta como alternativa. El inicio OAuth de la biblioteca no garantiza acceso dentro del iframe.

Google no expone a esta página el cabezal de su reproductor integrado. En **Visor de Drive · online**, introduce manualmente los tiempos que ves en Google; Marcar ahora y reproducir intervalos quedan desactivados para evitar referencias falsas. Si Drive facilita la duración, se validan los límites; si no, la duración no puede comprobarse. **Reproductor con tiempos** usa streaming autenticado por rangos, sin caché de videos, para las referencias automáticas; depende del formato y de la sesión activa. **Cargar clip completo** sigue siendo una alternativa opcional, confirmada y limitada a 150 MB, no el modo inicial.

La biblioteca incorpora carpetas por capas, filas compactas para videos, búsqueda dentro de la carpeta actual, recorrido de carpetas, Atrás y Actualizar. El visor permanece junto a la biblioteca en escritorio y encima de las herramientas en móvil. El mapa utiliza paneles oscuros, bordes finos y trama de puntos; el mismo visor permanece disponible al cambiar de herramienta.

Pruebas automatizadas cubren selección online sin descarga, notas manuales, aislamiento de archivos, búsqueda, navegación, actualización sin perder el recorrido, cierre de sesión, rangos y cancelaciones. No equivalen a probar un archivo privado real en un iPhone. Después de publicar, recarga la página en Safari; una PWA ya abierta puede necesitar cerrarse y abrirse de nuevo para activar la actualización.
