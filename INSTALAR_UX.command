#!/bin/zsh
set -euo pipefail
ux_root="${0:A:h}"
ux_source="$ux_root/src-tauri/target/release/bundle/macos/Abrxs-Canter-UX.app"
[[ -d "$ux_source" ]] || { echo "Primero construye la app según UX_3.6.md."; exit 1; }
for ux_destination in "$HOME/Downloads/Abrxs-Canter-UX.app" "$HOME/Applications/Abrxs-Canter-UX.app"; do
  [[ ! -e "$ux_destination" ]] || { echo "Ya existe $ux_destination. No se sobrescribe."; exit 1; }
done
ditto "$ux_source" "$HOME/Downloads/Abrxs-Canter-UX.app"
ditto "$ux_source" "$HOME/Applications/Abrxs-Canter-UX.app"
codesign --verify --deep --strict "$HOME/Applications/Abrxs-Canter-UX.app"
echo "Instalada por separado. Abrir: open $HOME/Applications/Abrxs-Canter-UX.app"
