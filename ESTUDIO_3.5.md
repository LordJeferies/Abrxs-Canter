# Abrxs-Canter · Estudio 3.5

App independiente `Abrxs-Canter-Estudio.app`. Conserva las etapas anteriores.
No edites el mismo proyecto simultáneamente en dos versiones. Importa una copia
del índice de Etapa 2 o de la biblioteca original, sin borrar esos registros.

## Recorrido

1. **Preparar:** selecciona el máster y las fuentes. Genera las transcripciones
   con el flujo existente. Marca y estructura permanecen opcionales. Los botones
   de resultados permiten analizar visualmente y exportar contexto TXT + JSON.
2. **Crear desde cero:** selecciona texto o añade un bloque desde el cabezal.
   La bandeja guarda fragmentos por proyecto y huella del máster. El texto sigue
   la reproducción; puedes desactivar ese seguimiento sin perder la selección.
   Las pestañas Texto / Visual / Bandeja comparten el visor.
3. **Revisar:** Fichas, Lista, Kanban y Mapa representan las mismas recetas.
   El mapa enlaza máster, clips, texto y archivos exportados. Arrastra cabeceras,
   usa las flechas con foco para moverlas o pulsa Ordenar mapa. Busca para acotar
   bibliotecas grandes: el mapa muestra hasta 150 resultados a la vez.
4. **Editar:** cambia límites escuchando contexto; reordena bloques. El timeline
   muestra miniaturas cuando generas la caché. Enfoque oculta los inspectores;
   vuelve a pulsarlo para recuperarlos. Exporta individualmente o por selección.

## Datos y resultados

`EDICIONES/ESTUDIO.json` guarda bandeja, posiciones y referencia visual.
El guardado es atómico. `CONTEXTO_IA/<identificador>/` contiene TXT y JSON nuevos
en cada exportación. No copia el máster ni envía contenido a internet.
El mapa conserva referencias a las nuevas versiones exportadas y sus TXT.
Las versiones anteriores existentes en disco no se reconstruyen automáticamente
si el registro previo nunca guardó sus referencias.
Miniaturas son caché técnica, no imágenes generativas ni portadas exportadas.
Los botones Mostrar en Finder señalan el archivo correspondiente.

## Límites honestos

- Vision obtiene muestras de rostros, cuerpos y OCR: **no narra acciones ni
  detecta límites semánticos de escenas**. La pestaña Visual muestra evidencia,
  no descripciones inventadas. El muestreo puede omitir eventos breves.
- Sugerencias locales separan frases por duración y las ordenan por coincidencias
  con palabras clave escritas. No interpretan semánticamente archivos de marca
  ni estructura. Estos archivos sí se incluyen en el contexto para un chat externo.
- No hay chat integrado, nuevos modelos, Remotion ni editor de efectos adicional.
- El preview virtual puede pausar brevemente al saltar entre segmentos. Revisa
  el MP4 final. Conserva un máster compatible con WebKit.
- Captions y seguimiento existentes permanecen opcionales y experimentales.
- Los formatos TXT admitidos y la plantilla de reparación siguen descritos en
  `ETAPA_2.md`. Ningún importador puede garantizar entender cualquier texto.

## Construcción local

Requiere las herramientas existentes: Python, Node, Rust/Cargo, Tauri CLI,
FFmpeg/ffprobe y herramientas de Xcode para Swift. No instala dependencias sola.

```bash
python3 -m unittest discover -s tests -p 'test_stage*.py'
node tests/stage1-core.test.cjs
python3 tests/smoke_stage1.py
python3 tests/smoke_stage2.py
CARGO_NET_OFFLINE=true zsh scripts/build_release.sh
```

La construcción produce únicamente el bundle app y un ZIP local; no DMG.
Una firma ad hoc no es notarización Apple. Las pruebas automatizadas no sustituyen
probar la app instalada con un proyecto pequeño en la sesión real de macOS.

## Publicación

Destino solicitado: repositorio público nuevo `LordJeferies/Abrxs-Canter-Estudio`,
**después de la prueba del usuario**. Publicar únicamente código, documentos y
ejemplos genéricos; excluir proyectos, credenciales, modelos, cachés y medios.
No se copia código propietario de herramientas profesionales: se adaptan
patrones de texto/timeline, jerarquía editorial y visualización de relaciones.
