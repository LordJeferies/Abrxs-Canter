# Flujo e intercambio

Mac: proyecto → elegir máster → transcripción/análisis → importar o crear decisiones → previsualizar referencias → ordenar bloques → exportar → revisión. Los recortes permanecen como rangos y orden; no se recodifica cada vez que cambias una ficha.

Web: carpeta Drive/video local → notas y/o transcripción importada → fichas → TXT/JSON → mismo máster en Mac. La web no crea tiempos por palabra si no existen. Conserva nombre de fuente, pero no puede certificar identidad mediante un hash del video remoto: comprobar el archivo en Mac.

## Transcripción JSON

```json
{"words":[{"start":10.0,"end":10.4,"word":"Hola"},{"start":10.4,"end":11.0,"word":"mundo"}]}
```

También admite segments con start/end/text y, si están presentes en todos los segmentos, words. SRT/VTT contienen tiempos por frase. TXT temporizado:

```text
[00:00:10.000 --> 00:00:15.000] Esto es un bloque completo.
```

## Editorial para Mac

`DECISIONES_ABRXS.txt` es JSON en un archivo TXT, reconocido por el importador existente. `DECISIONES_ABRXS.json` contiene lo mismo. Lista clips con id, title, type, selected y segments con id/order/role/start/end/text. start/end son segundos del original. Un clip puede reordenar varios bloques; los tiempos NO pasan a ser tiempos del montaje. El importador actual puede añadir 0.2 segundos de margen alrededor del segmento.

`REVISION_ABRXS.txt/json` contiene notas con tiempos del archivo revisado. No importarlo como editorial ni aplicarlo ciegamente al máster. `PROYECTO_ABRXS_REVIEW.json` guarda todo el trabajo web para reabrirlo, sin video ni credenciales. No subir estos documentos a un repo público.

Una plantilla de instrucciones para IA, como PLANTILLA_IA_REPARAR_EDITORIAL, no es un archivo con decisiones finales. El motor debe rechazarla y pedir la respuesta editorial, nunca cortar ejemplos incluidos en la plantilla.
