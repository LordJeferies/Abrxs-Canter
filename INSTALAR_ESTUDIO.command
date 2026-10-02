#!/bin/zsh
set -euo pipefail
studio_root="${0:A:h}"
studio_product="Abrxs-Canter-Estudio.app"
studio_source="$studio_root/src-tauri/target/release/bundle/macos/$studio_product"
if [[ ! -d "$studio_source" ]]; then
  print "Falta la app compilada. Ejecuta primero scripts/build_release.sh."
  exit 1
fi
codesign --verify --deep --strict "$studio_source"
for studio_destination in "$HOME/Downloads/$studio_product" "$HOME/Applications/$studio_product"; do
  if [[ -e "$studio_destination" ]]; then
    print "Se conserva la copia existente: $studio_destination"
    print "Mueve esa copia si deseas instalar otra; este script no la sobrescribe."
    exit 1
  fi
done
mkdir -p "$HOME/Applications"
ditto "$studio_source" "$HOME/Downloads/$studio_product"
ditto "$studio_source" "$HOME/Applications/$studio_product"
codesign --verify --deep --strict "$HOME/Applications/$studio_product"
print "Instalada por separado. Abre $HOME/Applications/$studio_product"
