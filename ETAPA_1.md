# Abrxs-Canter · Etapa 1

Esta actualización añade un editor no destructivo al proyecto existente. No
requiere Codex, no añade servicios de pago y no carga modelos nuevos.

## Uso

1. Crea o abre un proyecto desde la bienvenida. Selecciona su máster y prepara
   la transcripción con el flujo existente, si no la tienes.
2. Abre **Editor y biblioteca**. Importa decisiones sin exportar o crea una ficha
   nueva. Los informes anteriores se recuperan cuando contienen rangos válidos.
3. Selecciona palabras en la transcripción y añádelas como bloques. Reordena,
   divide, duplica o une bloques consecutivos. El texto original no se modifica.
4. En **Origen**, arrastra los límites y escucha el contexto anterior/posterior.
   En **Montaje**, reproduce la secuencia de bloques desde el máster. No se
   generan MP4 durante el ajuste. Los saltos entre bloques pueden tener una
   breve pausa de búsqueda: esta reproducción no sustituye revisar el MP4 final.
5. Guarda la ficha. Marca su estado editorial por separado del estado de
   exportación. Revisa fichas individualmente, en lista, cuadrícula o Kanban.
6. Exporta una o varias fichas. Cambiar un corte marca el MP4 anterior como
   desactualizado; reexportar conserva la versión anterior.

Los proyectos guardan recetas en `EDICIONES`, videos en `VIDEOS` y recursos
opcionales en `RECURSOS`. No se crean carpetas vacías para extras inexistentes.
Los borradores se guardan tras los cambios; espera a que termine el guardado
antes de cerrar. No cambies de proyecto durante una tarea activa.

## Incluido

- Correspondencia entre tiempos del máster y del montaje, también con bloques
  repetidos o reordenados.
- Preflight de fuente, audio, duración, límites y espacio libre.
- Miniaturas en una pasada y onda de audio real, bajo demanda y con caché.
- Ajuste de encuadre manual: original, vertical, horizontal o cuadrado; encajar
  con bandas o recortar. No es seguimiento automático.
- Cola secuencial de exportación, cancelación y reporte de errores por ficha.
  Una cola interrumpida no se reanuda sola: selecciona los pendientes y exporta.
- VideoToolbox 40M; alternativa libx264 si falla. MP4+TXT+JSON por receta.
- Comprobación de revisiones para evitar sobrescribir una edición más reciente.

## Límites importantes

No incluye todavía análisis visual con modelos, seguimiento automático,
Remotion ni subtítulos incrustados. Eso corresponde a la etapa 2.

Los extras editoriales XR/voiceover se conservan como información; el nuevo
editor no recoloca automáticamente sus posiciones al cambiar el montaje ni
genera su audio. Revisa los extras después de editar; el exportador anterior
sigue disponible para sus flujos existentes.

El reproductor usa WebKit y necesita un codec compatible. Si no reproduce el
máster, utiliza una copia compatible; no se genera un proxy automáticamente.
La vinculación de un máster movido comprueba tamaño y huella parcial, no un
hash íntegro del archivo. Las miniaturas tienen tiempos aproximados.

La caché tiene un objetivo de 8 GB; puede superarlo mientras conserva las
secciones del trabajo activo. **Limpiar caché** no borra originales ni MP4 finales.
No se deben abrir dos instancias editando el mismo proyecto simultáneamente.

## Verificación

`python3 -m unittest discover -s tests -p 'test_stage1.py'`

`node tests/stage1-core.test.cjs`

`python3 tests/smoke_stage1.py` prueba la exportación con un video sintético.
Los tests y Cargo no demuestran por sí solos que toda la interfaz funcione en
una sesión real. Comprueba un proyecto pequeño antes de un trabajo largo.
