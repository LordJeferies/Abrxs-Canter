# Abrxs-Canter

## Estudio 3.8 · actualización local pendiente de instalación

Cola de procesos, importación de fichas sin exportar por defecto, reutilización de exportaciones idénticas, límites alineados con palabras y reproducción local mediante rangos de archivo. La selección de palabras desplaza el visor y el cabezal; el cabezal resalta la palabra actual también al buscar con el video pausado. Consulta [ESTUDIO_3.8.md](ESTUDIO_3.8.md) y [ESTADO_ACTUAL.md](ESTADO_ACTUAL.md). Las secciones anteriores son historial, no certificación de funcionamiento de la app instalada.

## UX 3.6 — interfaz nueva, versión de prueba independiente

Biblioteca y navegación persistente Preparar / Crear / Revisar, vista previa de la fuente, paneles redimensionables y mapa con pan/zoom. Producto separado Abrxs-Canter-UX. Consulta [UX_3.6.md](UX_3.6.md). Las apps anteriores se conservan. Pendiente de prueba visual y audiovisual manual; las pruebas de DOM no sustituyen esa revisión.

Nueva navegación editorial, mapa de resultados, bandeja de fragmentos,
transcripción sincronizada, evidencia visual y contexto exportable.
Consulta [ESTUDIO_3.5.md](ESTUDIO_3.5.md) para uso, construcción y limitaciones.
La base 3.4.1 y las etapas 1/2 se conservan como referencia histórica.

Abrxs-Canter es una aplicación local para macOS que convierte videos largos en clips verificables mediante transcripción por palabra, alineación textual y edición no destructiva.

La versión `3.4.1` consolida la versión 3.4 utilizada en producción. Integra en el código fuente la corrección de reconstrucción de palabras y puntuación que antes estaba aplicada directamente sobre la aplicación instalada.

## Funciones principales

- Biblioteca local de proyectos independientes.
- Transcripción word-level con MLX Whisper o whisper.cpp.
- Conservación de `MASTER_WORD_LEVEL.json` como fuente técnica reutilizable.
- Transcripción legible en TXT, JSON, TSV y SRT.
- Lectura de decisiones editoriales desde TXT, Markdown, HTML o JSON.
- Alineación de texto contra la transcripción por palabra.
- Exportación separada de variantes `TIMESTAMP` y `TEXT_ALIGNED` cuando existe conflicto.
- Editor visual basado en transcripción, bloques y timeline.
- Borradores persistentes por proyecto.
- Revisión de clips y reexportación individual.
- VideoToolbox H.264 a 40 Mb/s, AAC a 192 kb/s y respaldo con `libx264`.
- Procesamiento local: los videos y transcripciones permanecen en la Mac.

## Requisitos

- macOS 12 o posterior en Apple Silicon.
- FFmpeg y FFprobe.
- Python 3.
- Rust y Cargo para compilar la aplicación.
- Uno de estos motores word-level:
  - `mlx-whisper`, recomendado en Apple Silicon.
  - `whisper.cpp` con un modelo configurado mediante `ABRAXAS_WHISPER_CPP_MODEL`.

Instalación recomendada de dependencias:

```bash
brew install ffmpeg whisper-cpp rust
python3 -m pip install mlx-whisper
```

## Compilar

```bash
./CONSTRUIR_ABRXS_CANTER.command
```

La aplicación se genera en:

```text
src-tauri/target/release/bundle/macos/abrxs-Canter.app
```

Para construir y verificar el paquete distribuible:

```bash
./scripts/build_release.sh
```

Los artefactos se guardan localmente en `releases/` y no se incluyen en el historial de Git.

## Uso básico

1. Abre Abrxs-Canter.
2. Crea un proyecto con nombre o abre un proyecto anterior.
3. Selecciona el video máster.
4. Añade una transcripción word-level o deja que la app la genere.
5. Importa las decisiones editoriales o prepara el paquete para una IA.
6. Revisa los clips detectados.
7. Ajusta bloques y puntos de entrada/salida en el editor.
8. Exporta solo cuando el montaje esté listo.

La guía detallada está en [`GUIA_USO_3.4.md`](GUIA_USO_3.4.md).

## Datos que no se publican

El repositorio excluye deliberadamente:

- videos originales y clips exportados;
- proyectos del usuario;
- transcripciones y cachés;
- modelos de Whisper;
- tokens de Hugging Face;
- configuración específica de una computadora.

## Estado de la versión

Esta copia incluye las etapas editoriales y UX 3.6. Es una versión de prueba independiente; no debe presentarse como estable hasta completar la revisión manual audiovisual. La línea publicada anteriormente puede diferir de esta copia local.

## Firma y distribución

Una compilación local puede llevar firma ad hoc y ser rechazada por Gatekeeper en otras computadoras. Para distribución pública sin advertencias se necesita un certificado Apple Developer ID y notarización. El código fuente puede publicarse y compilarse sin ese certificado.
