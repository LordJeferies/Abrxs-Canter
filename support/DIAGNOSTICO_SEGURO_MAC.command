#!/bin/bash
set -u
printf '\nABRXS · Diagnóstico de solo lectura\n'
printf 'No transcribe, descarga modelos ni cambia proyectos. Revisa rutas antes de compartir.\n\n'
sw_vers
uname -m
df -h /System/Volumes/Data
for abr_tool in ffmpeg ffprobe whisper-cli python3 node cargo; do
  printf '\nHerramienta: %s\n' "$abr_tool"
  command -v "$abr_tool" || true
done
if command -v ffmpeg >/dev/null 2>&1; then ffmpeg -version 2>&1 | head -3; fi
if command -v ffprobe >/dev/null 2>&1; then ffprobe -version 2>&1 | head -2; fi
if command -v python3 >/dev/null 2>&1; then python3 --version; fi
printf '\nPATH de la app puede diferir del de esta Terminal. No se leen historiales ni tokens.\n'
printf 'Copia esta salida y el error concreto del panel Actividad.\n'
