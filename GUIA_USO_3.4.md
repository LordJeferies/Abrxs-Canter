# Abrxs-Canter 3.4.1 — guía de uso

## 1. Crear o volver a un proyecto

Al abrir la aplicación aparecen dos caminos:

- **Proyecto nuevo:** escribe un nombre, pulsa **Crear y continuar** y elige dónde guardar su carpeta.
- **Proyectos anteriores:** abre una tarjeta para recuperar únicamente los archivos, la revisión y el borrador de ese proyecto.

Cada proyecto está aislado. Crear uno nuevo abre un espacio vacío. El borrador del editor se guarda en `EDICIONES/BORRADOR_ACTUAL.json` dentro de su propia carpeta.

## 2. Preparar un video sin transcripción

1. Entra en **Preparar para IA**.
2. Selecciona el video máster.
3. Deja vacío **Transcript word-level** si no tienes uno.
4. Opcionalmente añade información de marca y estructura editorial.
5. Pulsa **Crear transcripciones y paquete IA**.

La aplicación detecta primero MLX Whisper y whisper.cpp. Genera:

- una transcripción JSON y TSV con timestamps por palabra;
- una transcripción compacta por frases;
- un paquete para llevar a una IA;
- el acceso al editor manual.

## 3. Abrir el editor

Después de preparar el máster aparece **Abrir editor**. El editor usa el video original para la vista previa: mover bloques o ajustar bordes no crea archivos temporales ni recodifica el video.

La pantalla tiene cuatro zonas:

1. **Transcripción**, a la izquierda.
2. **Video máster**, en el centro.
3. **Bloques del montaje**, a la derecha.
4. **Timeline del clip**, abajo.

## 4. Crear un bloque desde el texto

1. Arrastra sobre las palabras desde la primera hasta la última.
2. Pulsa **Ver** para comprobar ese rango en el máster.
3. Pulsa **Añadir bloque**.

También puedes pulsar una de las **Frases detectadas** debajo del reproductor. Son atajos; no limitan la selección palabra por palabra.

El buscador localiza palabras o frases. Pulsa `Enter` para ir pasando por las coincidencias.

## 5. Construir el montaje

Los bloques aparecen en el panel derecho y en el timeline:

- usa `↑` y `↓` para reordenarlos;
- **Dividir** corta el bloque seleccionado en la posición actual del reproductor;
- **Unir** fusiona rangos vecinos del máster;
- **Pulir** une automáticamente bloques consecutivos separados por un segundo o menos;
- **Eliminar** quita el bloque del montaje, sin tocar el video original.

Los bloques que vienen de minutos distintos ya se reproducen juntos en el orden elegido; no es necesario fusionarlos en un rango que incluya el material intermedio.

## 6. Ajustar entrada y salida

Selecciona un bloque y usa cualquiera de estas opciones:

- arrastra el extremo izquierdo o derecho del bloque en el timeline;
- escribe el segundo exacto en **Entrada** o **Salida**;
- usa los botones de ajuste de `0.20 s`.

Mientras arrastras, el reproductor se mueve sobre el máster para mostrar el nuevo límite. **Ajustar** encaja el montaje completo en el ancho del timeline y **Zoom** aumenta la precisión visual.

## 7. Previsualizar

El botón grande de reproducción reproduce la secuencia completa. Al terminar un bloque, la aplicación salta al inicio del siguiente rango del máster. Es una vista previa ligera y no crea video nuevo.

Los botones `|◀` y `▶|` cambian de bloque. También puedes seleccionar un bloque en la lista o en el timeline.

## 8. Guardado, deshacer y recuperación

Los cambios se guardan automáticamente dentro del proyecto. La barra superior indica **Guardado local**. Usa `⌘Z` para deshacer y `⇧⌘Z` para rehacer.

Salir con **Proyecto** conserva el borrador. Al volver al mismo proyecto y abrir el editor se restaura. Otro proyecto nunca carga ese borrador.

## 9. Aplicar y exportar

1. Ponle nombre al clip.
2. Pulsa **Aplicar y exportar**.
3. La aplicación crea una decisión editorial JSON y la envía al cortador.
4. FFmpeg exporta con VideoToolbox a 40 Mb/s, audio AAC a 192 kb/s y MP4 con `faststart`.

Solo en este paso se procesa video. Al terminar, el resultado aparece en **Revisar videos**.

## 10. Revisar y corregir un resultado

En **Revisar videos** puedes:

- reproducir el MP4;
- marcarlo como aprobado, por corregir o descartado;
- guardar notas;
- crear una copia con entrada y salida ajustadas.

Para un cambio estructural, vuelve al editor, modifica los bloques y exporta otra vez.

## 11. Importar decisiones externas

En **Cortar videos**, selecciona un HTML, JSON, Markdown o TXT con timestamps, texto literal o ambos. Si el timestamp editorial y la alineación por texto difieren más de un segundo, el motor conserva variantes separadas para revisión.

También reconoce fichas con encabezados como `CLIP VERTICAL C01`, secciones de `TRAZABILIDAD DE LOS TRAMOS` y clips multicorte con varios bloques. Cada bloque lejano se conserva como una sección independiente.

Si un archivo no produce clips, aparece **Crear plantilla para IA**. La aplicación guarda `PLANTILLA_IA_REPARAR_EDITORIAL.txt` dentro del proyecto. Sube a la IA:

1. el archivo no reconocido;
2. la transcripción compacta del mismo video;
3. la plantilla generada;
4. opcionalmente la marca y estructura editorial.

La IA devolverá un JSON que puedes seleccionar nuevamente en **Decisiones de corte**. Los paquetes nuevos creados por **Preparar para IA** también incluyen `06_REPARAR_ARCHIVO_NO_RECONOCIDO.txt` automáticamente.

## 12. Seguridad de los archivos

- El video máster nunca se modifica.
- El timeline trabaja con referencias de tiempo hasta exportar.
- Cada proyecto conserva por separado su configuración, borrador y revisiones.
- Las transcripciones y exportaciones permanecen en tu Mac.
