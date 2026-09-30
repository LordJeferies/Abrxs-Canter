#!/bin/zsh
set -e

SCRIPT_DIR="${0:A:h}"
SOURCE_APP="$SCRIPT_DIR/abrxs-Canter.app"
DESTINATION_DIR="$HOME/Applications"
DESTINATION_APP="$DESTINATION_DIR/abrxs-Canter.app"

if [[ ! -d "$SOURCE_APP" ]]; then
  echo "No se encontró abrXS-Canter.app junto a este instalador."
  read -k 1 "?Pulsa una tecla para cerrar."
  exit 1
fi

mkdir -p "$DESTINATION_DIR"
ditto "$SOURCE_APP" "$DESTINATION_APP"
xattr -dr com.apple.quarantine "$DESTINATION_APP" 2>/dev/null || true
open "$DESTINATION_APP"

echo "Abrxs-Canter 3.4.1 quedó instalado en $DESTINATION_APP"
