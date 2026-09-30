# Abrxs-Canter

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

Esta rama corresponde a la línea funcional 3.4. La versión experimental 3.5 con procesamiento mixto por bloques no forma parte de este paquete estable.

## Firma y distribución

Una compilación local puede llevar firma ad hoc y ser rechazada por Gatekeeper en otras computadoras. Para distribución pública sin advertencias se necesita un certificado Apple Developer ID y notarización. El código fuente puede publicarse y compilarse sin ese certificado.
