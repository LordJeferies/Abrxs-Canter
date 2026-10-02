# Corrección preparada · UX 3.6.1

## Evidencia de la grabación suministrada

Se inspeccionaron cinco fotogramas extraídos del MOV con autorización del usuario. No se capturó su pantalla actual. La grabación muestra “Ya hay un proyecto en ejecución” mientras sigue visible el indicador de otro trabajo, y “TypeError: null is not an object (evaluating S.clip.blocks)”.

## Correcciones

- Transcripción y análisis visual comparten la exclusión de trabajo activo. El botón de preparación se desactiva durante otro trabajo y un intento duplicado muestra su estado, sin fingir que el motor existente terminó.
- El análisis visual del máster sin clip no accede a S.clip.blocks. Solo actualiza una ficha si existe y coincide con un clipId explícito.
- Se preserva stderr real en job-finished; se espera a drenar ambos lectores antes de emitir el resultado.
- Guardar el proyecto antes de iniciar está dentro del manejo de errores, de modo que un fallo libera “Procesando” y se explica.
- Se corrigió una rama adicional de MLX: una ejecución exitosa no debe caer en “No hay un motor”. No es la causa confirmada del MOV.

## Uso

Actividad está disponible desde cualquier pantalla: registro solo lectura, historial local acotado, copia del diagnóstico y cancelación del trabajo existente. No es una consola para ejecutar comandos. No se envía fuera del equipo.

Cortes definidos está arriba junto al máster. En Preparar, cargar ambos y pulsar “Preparar y organizar cortes” crea/reutiliza la transcripción, importa fichas después de completar el trabajo y permite revisarlas antes de exportar. No exporta automáticamente. El importador conserva la lógica de alineación y avisos existente.

Referencias del análisis muestra timestamps de muestras visuales. Al pulsarlos, el visor reproduce hasta cinco segundos del máster y se detiene; “Ver máster completo” devuelve reproducción libre. No modifica límites de montaje.

## Validación

20 pruebas de etapas, 5 regresiones de selección de motor y pruebas puras JS. Prueba DOM: exclusión de trabajos, análisis sin clip, recuperación de error de persistencia, pipeline preparar/importar, registro y parada de referencia temporal. Cargo check sin red.

No se ha vuelto a transcribir el máster de 62 minutos, no se descargaron modelos ni se ha verificado el nuevo comportamiento audiovisual en WebKit. Compilación e instalación pendientes de confirmación del usuario.
