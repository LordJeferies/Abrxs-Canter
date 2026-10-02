# Abrxs-Canter 3.8 · estabilización local

## Ajuste 3.8.1 · visor flotante y reinicio de ficha

En Mapa/Kanban el visor abre flotante al revisar una ficha: mueve su cabecera, cambia tamaño desde la esquina, pliega, cierra o acopla. Mostrar visor lo recupera. En Lista permanece acoplado por defecto; puedes hacerlo flotar. No se crea un segundo reproductor. Plegar/cerrar pausa el video y no altera la receta.

Cada selección de ficha vuelve al inicio de su primer bloque en el máster, aunque el archivo ya tenga metadatos cargados; el MP4 exportado empieza en cero. Los cambios rápidos de ficha descartan respuestas anteriores. La barra del montaje usa tiempos desde cero; los controles nativos del máster pueden mostrar sus tiempos absolutos, por ejemplo 00:39:32 para una ficha cuyo inicio es ese momento del podcast.

## Flujo

Carga máster + transcripción + decisiones. El botón pregunta siempre si quieres **solo fichas** (predeterminado) o **fichas y exportación**, también si antes usaste el modo antiguo Cortar. Con transcripción existente importa las fichas sin repetir Whisper. Revisa en Fichas, Lista, Kanban o Mapa; Lista/Mapa mantienen el visor al lado. Exportar activas pendientes usa fichas Por revisar/Aprobadas, no Borradores ni recetas ya exportadas.

## Precisión

Los timestamps son pistas de búsqueda. La alineación busca primero cerca de ellos y comprueba que coincidan las palabras iniciales y finales, además de la similitud del texto. Prefiere TEXT_ALIGNED/VERIFIED sobre TIMESTAMP cuando hay conflicto. Esto verifica contra la transcripción, no demuestra que la transcripción sea perfecta respecto al audio: reproduce ambos extremos antes de aprobar. Se conservan los márgenes de 0,2 segundos.

Una ficha importada solo por timestamps queda provisional y no se exporta automáticamente. Corrige su texto o revisa los límites en el editor y pulsa Confirmar límites revisados. Esa confirmación es manual; no se presenta como verificación automática. Los ajustes existentes de fichas previamente importadas no se sobrescriben al reimportar: revisa el aviso.

## Procesos

Procesos aparece debajo de Revisar: cola persistida localmente, prioridad para trabajos pendientes, cancelación, continuación/reintento y diagnóstico por trabajo. Un motor a la vez. Durante exportación puedes buscar, cambiar vista y reproducir fichas; editar una receta o cambiar de proyecto sigue protegido mientras hay un trabajo activo. Tras reabrir, ningún proceso interrumpido se reinicia automáticamente. Abre su proyecto y pulsa Continuar/reintentar.

Continuar reutiliza secciones completas y exportaciones equivalentes; la sección que estaba a medio codificar comienza de nuevo. Priorizar no interrumpe una sección activa. Las preparaciones antiguas aparecen en el historial; se vuelven a iniciar desde Preparar, no desde la cola de exportación.

FFmpeg informa segundos codificados, velocidad medida y ETA por sección. El ensamblado final y la comprobación de duración son pasos separados: el ETA de una sección no es promesa de duración del proyecto completo. Para 897 segundos de contenido: a 1× unos 15 min; a 2× unos 7,5 min; a 0,5× unos 30 min, más ensamblado/comprobación.

La cancelación señala el grupo del motor y comprueba después si debe terminarlo forzosamente. El módulo de exportación cancela también su FFmpeg. No busca ni mata procesos ajenos. Las versiones completas anteriores se conservan.

## Fuentes grandes y diagnósticos

El reproductor local utiliza un servidor privado en 127.0.0.1, con direcciones aleatorias y transferencia en bloques/Range. No carga el podcast entero en una variable ni convierte el máster automáticamente. El tamaño no garantiza compatibilidad: la reproducción real del podcast de 9,1 GB aún requiere comprobarse en WebKit/macOS con la app compilada.

Preparar informa acceso a la fuente, dimensiones, duración y cantidad de palabras cargadas. No es un certificado de que todos los motores funcionen: transcripción, reproducción, análisis y exportación deben probarse por separado.

Las recetas equivalentes reutilizan MP4 existente, también entre variantes si tienen los mismos límites y ajustes. Cambios en límites, fuente, encuadre, captions o seguimiento generan una nueva exportación. Copiar diagnóstico en Actividad limita el resumen a 4.000 caracteres; Procesos permite copiar un trabajo concreto.

## Alcance y validación

Esta actualización es local. No publica automáticamente el repositorio ni cambia GitHub Pages. La web conserva su reproductor de Drive y sus límites documentados; no usa este servidor local de Tauri.

Pruebas automáticas: DOM de navegación/importación/exportado, cola serial, aislamiento de proyectos, alineación de extremos, timestamps ambiguos, reutilización de exportaciones, rangos HTTP y compilación Rust. Pendiente: reproducción real de 9,1 GB, cancelación y exportación completa del podcast en la app macOS recién compilada. No borres el proyecto ni repitas su transcripción como primera medida.
