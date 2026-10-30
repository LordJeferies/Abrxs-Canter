# Comparación automática de cortes (3.8.1)

En la biblioteca, elegir **Comparar y exportar ambas versiones automáticamente** y exportar las fichas seleccionadas. También se aplica a la importación y posterior exportación por lotes. El valor inicial sigue siendo revisión estricta y vuelve a ese valor al cambiar de proyecto.

El modo usa `alignment` (los segmentos editoriales importados) y la transcripción existente; no infiere los tiempos originales restando márgenes a bloques editados ni ejecuta Whisper. Los bloques de edición y las marcas de revisión manual permanecen intactos. Nuevas importaciones automáticas crean una ficha por pieza y fuente, y reutilizan la ficha si ya existe.

Se compara inicio y fin de contenido por separado (tolerancia inicial 0,15 s), antes del margen inicial de 0,2 s. `MATCHED` genera una versión con límites de palabras; `DIFFERENT` conserva ambas interpretaciones. Un texto sin intervalo puede producir solamente `WORD_ALIGNED`. La falta de correspondencia deja `ALIGNMENT_UNRESOLVED`, permite exportar la referencia editorial válida y registra la causa.

## Confianza y límites

`AUTO_ALIGNED_HIGH` requiere similitud de tokens >= 0,96, hasta tres tokens coincidentes en cada extremo, tiempos ordenados y duración plausible (máximo 12 s o 1,8 s por token; máximo 12 tokens/s). Para textos cortos se exige coincidencia exacta. Los candidatos casi iguales con proximidad equivalente se consideran ambiguos. La primera búsqueda abarca ±30 s del inicio editorial. El segundo intento amplía a todo el master, admite diferencias interiores conservadoras y usa el siguiente fragmento de una omisión como contexto cuando está disponible. Una puntuación >= 0,75 sin cumplir los requisitos altos queda `AUTO_ALIGNED_MEDIUM`; nunca habilita una exportación por palabras. El resto es `UNRESOLVED`.

`[...]` o `[…]` divide el texto en fragmentos. Su orden se conserva y dentro de una omisión se exige avanzar en el master. Entre secciones se respeta el orden narrativo, aunque reordene la fuente. Una versión alineada incompleta se descarta íntegramente, conservando la editorial. El margen final de la versión alineada se reduce si alcanza la siguiente palabra; esta diferencia queda en advertencias. No se recorta la referencia editorial para ocultar discrepancias.

No se analiza el audio directamente, no se corrige una transcripción incorrecta y no se concede `VERIFIED`. Un desfase no nulo entre masters se registra como error conservador: este modo requiere transcripción en la línea temporal de la fuente elegida. La correspondencia entre masters distintos sigue siendo una condición confirmada al importarlos con el flujo existente; no se detecta sincronía audiovisual automáticamente.

## Archivos y reutilización

`VIDEOS/COMPARACION_AUTOMATICA` contiene todos los MP4 en una sola carpeta, con prefijo numérico de orden, ID, rol, orientación, variante y firma de receta. En Pocaterra se utiliza `VIDEOS/POCATERRA_66_CORTES`. El orden se contrasta contra los segmentos del intro existentes, incluso al exportar sólo una selección. Cada versión multicorte se concatena en un MP4. `COMPARACION_CORTES.json` conserva ambos intervalos, diferencias en ms, decisiones, candidatos, confianza, márgenes y errores, y se actualiza después de cada ficha. Incluye una fila por pieza/fuente/formato: los 66 cortes en dos masters generan 132 filas.

La firma incluye contenido del master, intervalos finales, encuadre, captions y seguimiento. Antes de reutilizar se comprueba existencia y duración mediante ffprobe. Las exportaciones compatibles se reúnen en la carpeta única mediante enlaces físicos locales (o copia si no son posibles), sin recodificar ni eliminar sus ubicaciones anteriores. El reporte y el visor apuntan a la carpeta única. Las nuevas se registran en `comparisonExports`, sin sustituir la exportación estricta. Un error de una variante no cancela la otra ni el resto del lote.

## Pruebas

- `python3 -m unittest discover -s tests -p 'test_auto_compare.py'`
- `python3 -m unittest discover -s tests -p 'test_stage*.py'`
- `node tests/ux-dom.test.cjs`
- `cargo tauri build --bundles app`

La fixture privada local contiene los 66 cortes reales y su transcripción, sin vídeo. No se publica en GitHub; las dos pruebas que requieren fixtures privadas se omiten cuando esos archivos no están disponibles. La evaluación da 2 MATCHED, 44 DIFFERENT y 20 ALIGNMENT_UNRESOLVED por master con los criterios anteriores. Son resultados de correspondencia textual, no una revisión auditiva.
