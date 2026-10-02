# Abrxs-Canter · contexto para soporte

Aplicación macOS Tauri, frontend HTML/CSS/JS sin React, backend Rust y motor local Python/FFmpeg. Vision local tiene worker Swift. La app de escritorio transcribe, analiza, importa editoriales, compone rangos no destructivos y exporta clips. Abrxs Review es una página estática complementaria: Drive de solo lectura, reproducción, notas temporales, fichas y exportación de decisiones. No ejecuta el motor de Mac en el iPhone.

Para soporte comparte este documento, el diagnóstico, una descripción de los pasos y el error exacto de Actividad. No compartas tokens, OAuth secretos, conversaciones completas ni videos personales si no hacen falta. Los registros pueden contener rutas y nombres: revísalos antes de subirlos.

Correcciones preparadas en UX 3.6.1: evita falso fallo después de transcripción MLX exitosa; captura errores de persistencia al iniciar; conserva stderr de procesos; evita acceder a bloques de una ficha inexistente; impide trabajos simultáneos incompatibles; pone cortes en preparación y añade referencia temporal de evidencias. El panel Actividad es un registro de lectura, no una consola que ejecute comandos.

Compilar y firmar no prueba el arranque gráfico. Un test con mocks no prueba una transcripción real. Si un técnico afirma que funciona, pedir qué caso probó y con qué archivo. No borrar proyecto, modelo, caché, app ni fuentes como primera solución. No reinstalar todo automáticamente.

Rutas del proyecto deben verificarse en la máquina. Esta copia usa `work/abraxas-tauri`. El motor está en `engine/abraxas_local.py`; el importador en `engine/stage1.py`; la UI en `dist`; puente Rust en `src-tauri/src/lib.rs`; la página en `review-web`.
