# Estado local · 2 de octubre de 2026

## Review 05 · recuperación del reproductor

Drive permanece como visor inicial, sin descargar automáticamente los videos. Abrir en Drive es una alternativa visible para ver el archivo en el navegador o app de Google y volver a escribir las notas manualmente. No se estira el iframe a una falsa pantalla completa en iPhone. Las cargas nativas opcionales se cancelan al cambiar de modo/archivo; se reinicia el tiempo al cargar los metadatos y se explican errores/esperas en lugar de mantener una carga silenciosa. Clips de hasta 32 MB usan carga completa solo al elegir el reproductor nativo; videos grandes conservan streaming opcional.

Las dos grabaciones del usuario muestran superposición de controles internos de Google/iOS y fallos de cambio de modo. No se afirma que esas capas internas estén resueltas: no son manipulables desde el HTML. Pruebas breves de lógica Review, cola, importación y Rust pasan. La prueba de navegador studio-ui no se ejecutó porque falta Playwright; no se instaló una dependencia ni se renderizó el podcast para ello. Reproducción privada real en iPhone pendiente.

Actualización de código del programa 3.8.1 y Review 05 preparada para sus repositorios; esto no instala una app nueva en la Mac.

## Review 04 · visor limpio y notas manuales

Cambio solicitado después de Review 03: los tiempos de las notas son manuales en ambos modos, sin captura al pausar ni pausa al escribir. El formulario está fuera del visor. La superficie muestra solo el medio activo; en Google se ocultan controles propios adicionales. El marco respeta la proporción del video y Pantalla completa usa la API disponible o una vista ampliada sin formulario. Los controles internos de Google/Safari siguen siendo responsabilidad de esos reproductores, no se eliminan desde esta página. Commit web: 6f67310.

## Actualización posterior · 3.8.1 y Review 03

Review 03 publicado en https://lordjeferies.github.io/Abrxs-Review/ (commit 2248944 del repositorio Abrxs-Review). Verificado en la página pública: explorador separado, compositor de notas y opciones de TXT. Esto no certifica OAuth ni reproducción en iPhone real.

App 3.8.1: visor flotante de Mapa/Kanban, plegable, cerrable y acoplable; selección de ficha reinicia el rango aun reutilizando el mismo máster. Compilación y firma verificadas; no se reemplaza automáticamente la app 3.8 que el usuario tiene abierta. La publicación de código no equivale a instalar esa app.

## Implementado en el código de esta carpeta

- Estudio 3.8: fichas solas por defecto con elección explícita de exportación; importación con transcripción existente sin repetir Whisper; fichas compartidas entre Lista, Kanban y Mapa; visor del máster junto a Lista/Mapa.
- Exportación de activas pendientes, identificación de recetas iguales y reutilización de archivos existentes. Un cambio de límites, fuente o ajustes requiere una nueva exportación.
- Alineación de texto con palabras de apertura/cierre; timestamp como pista de búsqueda. Los cortes solo por timestamp quedan provisionales. Confirmación manual de límites diferenciada de alineación textual.
- Cola serial persistida, prioridad de pendientes, cancelación, reintento, registro por proceso y progreso real por sección. Revisar no exige detener la exportación. Continuar reutiliza resultados completos; no continúa a mitad de una sección codificada.
- Servidor local de medios con rangos, sin cargar el podcast entero en memoria. Panel de acceso/duración/palabras existentes, diagnósticos breves.
- Selección de texto conectada al visor/cabezal; búsqueda pausada resalta palabras; el inspector sigue el bloque alcanzado en modo máster.
- Review web: explorador amplio separado de lista seleccionada, selección de todos los videos o medios de una carpeta, orden de revisión, imagen individual y notas con identidad/enlaces de Drive. Comentario debajo de la imagen; tiempos y sliders manuales, sin captura al pausar ni pausa al escribir.
- TXT con nombre/ID/enlace/carpeta/tiempos, copia al portapapeles y subida explícita a carpetas de origen. La subida requiere permiso de edición de carpeta y autorización de esa carpeta para la aplicación; drive.file no garantiza acceso a todas las carpetas compartidas. Si falla, descarga el TXT y súbelo manualmente.

## No entregar como terminado todavía

- La app instalada sigue siendo la compilación del usuario: estos cambios requieren compilar y abrir una app nueva. No se ha instalado ni sustituido su aplicación en este turno.
- La actualización pública de Review y la subida de código de escritorio son publicaciones separadas; no se instala automáticamente la app.
- Safari/PWA real y OAuth de Drive no se han probado aquí. El error NotSupported y la capa/controles internos del visor de Google no están resueltos de forma demostrada. El tamaño/capas propios de la página sí se ajustaron, pero no se controla el iframe de Google.
- No existe acceso automático al tiempo/play/pausa del iframe de Drive. Las notas usan tiempos manuales en ambos modos; no se simula exactitud con un cronómetro de pared.
- Pendiente: dos másteres horizontal/vertical en una misma importación y selección de formatos por pieza, paquete de entrega que asocie automáticamente video/texto/palabras, lectura de ese paquete en Review, carruseles comparados y aprobaciones, mapa interactivo completo, selección recursiva de subcarpetas y revisión de miniaturas en reproducción sin exportar.
- Un enlace público de carpeta no permite enumerar sus archivos sin un mecanismo de acceso/API. La navegación actual requiere sesión OAuth; no se promete acceso anónimo universal.

## Validación ligera y siguiente trabajo

Pruebas sintéticas de interfaz/cola/importación/recetas, alineación textual, rangos de archivo y compilación de Rust. No sustituyen la reproducción real de WebKit/Safari, ni certifican todos los códecs. No se ha transcrito ni renderizado el podcast largo para probar.

Primero: abrir la app nueva y validar fuente, ficha y cancelación con un tramo breve; en iPhone validar modo nativo/online y notas. Después: completar paquete de entrega y asociación de texto, carruseles/aprobación, dos másteres y mapa editable. Finalmente publicar archivos web verificados y código/documentación a sus repositorios, manteniendo fuera proyectos y videos personales.

React Flow/xyflow sirve como base para un mapa editable, pero todavía no se integró: este proyecto usa JavaScript sin React. No se incorporaron los motores de IA de node-banana ni Vibe-Workflow.
