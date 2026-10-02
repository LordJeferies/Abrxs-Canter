# Estudio 3.7 · visor y lote multiformato

## Lista y mapa

Haz clic en Revisar o en el cuerpo de una ficha para abrir el visor a la derecha, sin abandonar la lista/mapa. Es una secuencia virtual de rangos del máster: no renderiza ni consume modelos. Un solo reproductor activo. El control Posición del montaje usa tiempos desde cero; los controles nativos del video reflejan el tiempo del máster. La selección de texto del mapa abre esa referencia en el visor. Editar ficha abre el editor completo.

Desde máster reproduce los recortes; MP4 exportado abre la última versión disponible. Verificar identidad de la fuente antes de mostrarla: si el contenido cambió, no se reproduce como si fuese el original. El estado se vuelve a consultar tras cada clip exportado y al terminar el lote, tanto en las fichas como en el visor. Un fallo conserva versiones anteriores y se diferencia de Exportado/desactualizado.

## Una importación, dos fuentes

Importar cortes y Preparar con cortes abren la elección Solo fichas o Crear fichas y exportar. La exportación, si se pide, empieza después de importar, solo sobre las fichas incluidas en ese lote, no toda la biblioteca.

Activa másteres del lote y selecciona horizontal/vertical (se recuerdan como preferencias locales por proyecto). Comprueba que son la misma grabación, con la misma escala temporal. Si el mismo momento está desplazado, indica segundos por fuente: +2 busca el segundo 12 cuando el editorial dice 10. Esto no sincroniza versiones reeditadas, aceleradas, con tomas distintas o cortes internos; en esos casos hay que preparar tiempos específicos para cada fuente. Se comprueban dimensiones, duración, tiempos finitos y límites.

En TXT/HTML, el tipo reconocido por el importador debe ser horizontal, vertical o intro. Intro produce ambas fuentes. En JSON puedes definir outputs por clip; sobrescribe el tipo:

```json
{"clips":[
  {"id":"INTRO","title":"Intro","type":"intro","outputs":["horizontal","vertical"],"segments":[{"start":10,"end":15,"text":"Inicio"}]},
  {"id":"V01","title":"Clip vertical","type":"vertical","segments":[{"start":30,"end":45,"text":"Cuerpo"}]},
  {"id":"H01","title":"Clip horizontal","type":"horizontal","segments":[{"start":50,"end":65,"text":"Cierre"}]}
]}
```

Un archivo que solo dice video necesita la elección de destino para clips sin formato; por defecto se detiene, no inventa. Una versión por corte elige VERIFIED/TIMESTAMP si existen, evitando duplicar cada clip por alternativa alineada. Puedes pedir conservar alternativas. El margen histórico de 0.2 s se conserva.

La importación multiformato prepara todos los resultados antes de escribir una sola biblioteca. Si falta un máster o falla un rango, no se guarda media importación. Las fichas existentes se conservan, no se sobrescriben. Cada orientación tiene identidad separada, fuente asignada y exportación independiente. No se transforma una fuente horizontal en vertical automáticamente: se usa el máster correspondiente que seleccionaste.

## Pruebas y límites

Pruebas del motor para rutas por formato, desfases, atomicidad e importación repetida. DOM sintético para visor sin entrar al editor, exportación encadenada, estados y aislamiento de proyectos. Sintaxis JS y Cargo check. No reemplaza una prueba de reproducción/render real con tus dos másteres ni una comprobación visual en WebKit.
