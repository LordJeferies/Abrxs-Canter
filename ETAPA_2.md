# Abrxs-Canter · Etapa 2

App independiente: `Abrxs-Canter-Etapa-2.app`, preparada en Descargas para
arrastrarla a Aplicaciones. No reemplaza la Etapa 1. Su identificador propio
permite distinguir las apps; al abrirla por primera vez importa una copia del
índice de proyectos de la versión anterior, sin borrarlo. No abras el mismo
proyecto para editarlo en dos versiones a la vez.

## Importación de cortes

Acepta TXT con `A01 / Inicio / Final`, HTML del flujo existente y el contrato
JSON `clips / segments`, incluso guardado en `.txt`, con bloque Markdown o una
frase introductoria de la IA. Comprueba intervalos, IDs y órdenes duplicados.
No promete entender cualquier texto arbitrario: si falla, utiliza la plantilla
de reparación con la IA y vuelve a importar su respuesta.

`PLANTILLA_IA_REPARAR_EDITORIAL.txt` contiene instrucciones y un ejemplo, no
cortes reales. Seleccionarla muestra una explicación en lugar de cortar el
ejemplo C01. La respuesta de la IA puede guardarse como `DECISIONES_ABRXS.txt`
o `.json`. Se incluye `DECISIONES_ABRXS_EJEMPLO.txt` para estudiar el formato;
sustituye sus tiempos antes de usarlo.

En Editor y biblioteca, **Importar decisiones sin exportar** admite cortes por
timestamps sin transcripción. Para localizar texto literal o comprobar un
desfase hace falta la transcripción del máster. Texto e intervalos en conflicto
generan fichas separadas TIMESTAMP/TEXT_ALIGNED cuando todas sus secciones
son verificables. Se mantiene 1 segundo como umbral y márgenes de 0.20 s.

## Captions opcionales

En el inspector, abre **Captions y Vision · Etapa 2**. Selecciona:

- Desactivados: no añade captions.
- Archivos SRT + ASS: guarda archivos editables junto al MP4.
- Incrustar en MP4: genera un MP4 con texto; necesita FFmpeg con libass.

**Cargar estilo JSON** lee fuente, tamaño, color, fondo, posición, negrita,
caja, palabras por frase, margen y borde. Se incluye
`ESTILO_CAPTIONS_EJEMPLO.json`. Utiliza fuentes instaladas. No interpreta diseños
a partir de una imagen ni añade animaciones complejas/Remotion.

El preview HTML de captions es aproximado; revisa el MP4 final para comprobar
tipografía y saltos de línea. Los timestamps se trasladan al montaje, incluso
en bloques reordenados. No se generan captions desde resúmenes editoriales.

## Vision local: función pendiente de validación en tu sesión de macOS

El componente nativo compila, pero la prueba de Vision en el entorno restringido
de desarrollo devuelve `Failed to create CVPixelBuffer`. No se puede afirmar
que el análisis/seguimiento funcione en tu sesión hasta probarlo fuera de ese
entorno. Si falla, muestra un error; no inventa detecciones ni cambia el clip.

**Analizar visualmente el máster** muestrea hasta 600 fotogramas, con rostros,
cuerpos y OCR. Guarda JSON/TXT con tiempos bajo `ANALISIS_VISUAL`, y una copia
del TXT en el paquete para IA cuando existe. No narra acciones, no reconoce
identidades ni determina quién habla. El muestreo puede omitir eventos breves.

Para seguimiento selecciona un bloque, formato no original y **Recortar para
llenar**. Puedes elegir rostro principal, cuerpo principal u objeto delimitado
por `x,y,ancho,alto`, números entre 0 y 1 desde la esquina superior izquierda
del máster. El seguimiento debe revisarse: puede perder el objetivo; rostro y
cuerpo pueden adquirir otra persona después de una pérdida.

Los puntos suavizados controlan el recorte y su preview. No es un sistema
automático de realización multicámara. Quita/recalcula el seguimiento al
cambiar de formato o al dividir/duplicar bloques. El recorte dinámico con puntos
sintéticos sí pasó una prueba de exportación real.

## Verificación sin screenshots ni descargas

Desde la carpeta del código:

```bash
python3 -m unittest discover -s tests -p 'test_stage*.py'
node tests/stage1-core.test.cjs
python3 tests/smoke_stage2.py --vision
```

La última prueba genera un video sintético pequeño, comprueba captions y
recorte, y ejecuta Vision. No usa tus videos ni descarga modelos. Si falla
Vision, conserva la salida: captions y edición no dependen de esa función.

No se publicó en GitHub, no se creó DMG, no se añadieron modelos ni Remotion.
