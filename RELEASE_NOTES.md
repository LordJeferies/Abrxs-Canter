# Abrxs-Canter 3.4.1

Consolidación de la línea 3.4 utilizada localmente, con la corrección de unión de palabras y puntuación integrada en el código fuente y versiones coherentes en la interfaz y el paquete.

## Descargar e instalar

Descarga `Abrxs-Canter-3.4.1-macOS-arm64.zip`, descomprímelo y copia la aplicación a tu carpeta Aplicaciones. Requiere una Mac Apple Silicon y las dependencias locales indicadas en el README; los motores y modelos no están incluidos en el ZIP.

La aplicación lleva firma ad hoc local y no está notarizada por Apple. macOS puede requerir autorización en Privacidad y seguridad para abrir una aplicación descargada.

## Comprobaciones realizadas

- Compilación Rust/Tauri y comprobación de sintaxis Python/JavaScript.
- Firma del paquete `.app` válida y prueba de integridad del ZIP.
- Siete salidas derivadas del máster del webinar idénticas a las generadas por el normalizador de la app 3.4 instalada: JSON y TSV por palabra, JSON y TXT compacto, TXT limpio, SRT y reporte de correcciones.

La apertura y el flujo completo de la nueva build 3.4.1 requieren una comprobación manual. La equivalencia del normalizador no equivale a validar todas las funciones de la aplicación. Se publica como prerelease para conservar esta distinción.

El repositorio no incluye videos, transcripciones personales, proyectos, cachés, modelos ni credenciales. El motor experimental 3.5 queda fuera de esta versión.
