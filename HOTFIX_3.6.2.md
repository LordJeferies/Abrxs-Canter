# Hotfix UX 3.6.2

Corrección de las capturas del usuario, sin migrar proyectos ni cambiar los renders.

- Confirmaciones: permiso Tauri dialog:allow-confirm explícito y respuesta asíncrona esperada. Cancelar ya no se interpreta como un Promise verdadero.
- Miniaturas: el protocolo de recursos conserva su alcance previo y añade solamente `**/.abrxs-cache-stage1/**`, carpeta oculta usada por el generador. No se habilita globalmente el acceso a todas las carpetas ocultas. Si una imagen falla, la ficha muestra un aviso en lugar de un icono roto; el timeline oculta esa imagen.
- Mapa: texto, tarjetas, badges y botones reciben colores explícitos legibles sobre los nodos claros. Se elimina la herencia de blanco sobre blanco.
- Timeline: cada clip abre en secuencia de montaje desde cero, ajustado al ancho, sin heredar zoom ni vista del clip anterior. Inicio/final del bloque están arriba del inspector. Precisión, captions y encuadre quedan plegados en Más ajustes. Reproducir, deshacer y dividir tienen acceso directo. Selección azul y tiradores visibles; no ondas inventadas.
- Distribución: botón Mostrar carpeta de ancho normal, bloque de texto acotado, controles agrupados y registro flotante más pequeño. Metadatos 3.6.2.

No se modifican transcripciones ni se silencia un error de identidad del máster. Si una ficha advierte que cambió el video, revisa o relocaliza la fuente correcta antes de guardar. La coincidencia semántica de una transcripción no puede comprobarse solo con una captura.

Verificación: sintaxis JS, Cargo check offline, pruebas DOM y del motor. No equivalen a prueba visual WebKit real. El script de Terminal recompila con confirmación y deja una app aparte en Descargas; no reemplaza la instalada.
