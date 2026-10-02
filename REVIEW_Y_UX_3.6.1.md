# Entrega preparada · Review y UX 3.6.1

La fuente desktop incorpora los arreglos descritos en ARREGLOS_UX_3.6.1.md y una capa CSS discreta de bordes, tarjetas, fondos y mapa. No se sustituyó el motor ni se generó una imagen de interfaz. Versión de metadatos 3.6.1. La compilación e instalación no se ejecutaron en esta entrega: el script de Terminal permite compilación local opcional con confirmación y deja una copia aparte en Descargas.

`review-web` contiene página/PWA estática con biblioteca de Drive, OAuth Google Identity Services, reproductor privado mediante service worker y Range, alternativa explícita de carga completa hasta 150 MB, video local, notas temporales, transcript selection, fichas, orden de bloques, ajuste de inicio/final, mapa de procedencia y exportaciones. Las transcripciones largas se muestran en páginas de 400 unidades para evitar crear miles de controles simultáneos.

`support` contiene contexto, formatos, guía de errores, diagnóstico de solo lectura y prompt para soporte con un chat. `outputs/PREPARAR_ABRXS_REVIEW.command`, dos niveles por encima de este archivo, prepara la distribución sin publicar ni instalar dependencias.

## Verificación realizada

- review-core: parseo TXT/JSON/SRT/VTT, validación temporal y editorial.
- review-sw: Range, no token en URL, aislamiento entre clientes, cierre de sesión y exclusión de videos de caché; peticiones sintéticas, no cuenta real.
- review-dom: selección, ficha, timeline, descarga TXT, nota y aislamiento de proyectos. DOM sintético: no captura ni render de pantalla.
- test_review_interchange: TXT y JSON de la web aceptados por parse_editorial real.
- 20 tests stage existentes, 5 regresiones backend y ux-dom existentes pasaron.
- Cargo check offline, sintaxis JS y scripts, diff sin errores de espacio.

Pendiente: ID OAuth del usuario, configuración Google/Pages, prueba real Drive/iPhone/Safari, nueva transcripción de un video real y arranque de la app compilada. No prometer sincronización en Drive ni aplicar notas del montaje al máster automáticamente. No se publica ningún repo ni se envían videos.
