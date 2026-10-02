# Abrxs-Canter · UX 3.6

Actualización estructural de interfaz, conservando el motor local.

## Flujo único

- Biblioteca: crear o reabrir un proyecto independiente.
- Preparar: elegir el máster, reproducir la fuente, importar una transcripción o generarla. Marca y estructura están plegadas. Después analizar evidencia visual y exportar contexto TXT/JSON.
- Crear: seleccionar palabras o rangos, montar bloques, escuchar entrada/salida con contexto, ajustar límites y exportar. Paneles redimensionables con ratón o flechas en el separador enfocado.
- Revisar: fichas, lista, Kanban o mapa. Importar cortes TXT/JSON/Markdown/HTML, revisar cada clip, aprobar y exportar individualmente o por selección.

Las herramientas anteriores siguen accesibles en “Herramientas de compatibilidad” para no perder resultados heredados. No son la entrada principal.

## Referencias aplicadas

Biblioteca: referencias 4 y 8, superficies claras, tarjetas discretas, navegación lateral persistente. Editor: referencias 2, 12 y 13, visor oscuro, transcripción a la izquierda, montaje a la derecha y timeline inferior. Mapa: referencia 3, puntos suaves y conexiones entre máster, clips, texto y exportaciones. Un acento cálido marca selección y cabezal; no se añadieron texturas pesadas, fuentes externas ni animaciones decorativas.

## Código abierto integrado

- Split.js 1.6.5: separadores reales del editor, tamaños recordados localmente.
- Panzoom 4.6.0: arrastrar el fondo del mapa y zoom. Ctrl/Cmd + rueda o control Zoom; arrastrar las cabeceras mueve los nodos.
- Lucide 0.468.0: cuatro iconos SVG locales para navegación.

Versiones fijadas y licencias en dist/vendor. No CDN ni descarga en tiempo de uso. No se migró la app a React ni se incorporó un editor completo externo. Esto reduce dependencias y evita duplicar el motor de video.

## Límites

Vision detecta rostros, cuerpos y texto visible; todavía no narra acciones o interpreta escenas semánticamente. Las propuestas locales son heurísticas. La reproducción de montajes virtuales puede pausar brevemente al saltar entre rangos. Las miniaturas son caché y tienen botón Mostrar en Finder; no son portadas finales.

## Comprobaciones

node --check dist/ux.js
node tests/stage1-core.test.cjs
python3 -m unittest discover -s tests -p 'test_stage*.py'
node tests/ux-dom.test.cjs

La última prueba usa linkedom 0.18.12 en .build-cache/ui-tests (solo pruebas), verifica rutas, aislamiento y separadores. No verifica apariencia, WebKit ni reproducción audiovisual. Para repetirla: npm install --prefix .build-cache/ui-tests --cache .build-cache/npm linkedom@0.18.12 --ignore-scripts --no-audit --no-fund.

Compilar: CARGO_NET_OFFLINE=true zsh scripts/build_release.sh. Solo APP y ZIP; no DMG. Producto separado Abrxs-Canter-UX, identidad com.abrxs.canter.ux, versión 3.6.0. Importa únicamente el índice de proyectos de Estudio/Etapa 2 cuando su biblioteca nueva aún no existe. Los originales y apps anteriores se conservan.

Publicación pendiente de prueba manual del usuario en un repositorio nuevo público Abrxs-Canter-Estudio.
