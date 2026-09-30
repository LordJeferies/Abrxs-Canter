#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
cd "$ROOT"
VERSION="$(python3 -c 'import json; print(json.load(open("src-tauri/tauri.conf.json"))["version"])')"

python3 -m py_compile engine/abraxas_local.py engine/transcript_quality.py
node --check dist/app.js
cargo check --manifest-path src-tauri/Cargo.toml
cargo tauri build --bundles app

APP="src-tauri/target/release/bundle/macos/abrxs-Canter.app"
RELEASES="$ROOT/releases"

# Tauri puede dejar una firma ad hoc incompleta al incluir recursos externos.
# Se vuelve a firmar el paquete completo antes de distribuirlo.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

mkdir -p "$RELEASES"
ditto -c -k --sequesterRsrc --keepParent \
  "$APP" \
  "$RELEASES/Abrxs-Canter-${VERSION}-macOS-arm64.zip"

shasum -a 256 \
  "$RELEASES/Abrxs-Canter-${VERSION}-macOS-arm64.zip" \
  > "$RELEASES/SHA256SUMS.txt"

echo
echo "Abrxs-Canter ${VERSION} construido y verificado."
echo "Artefactos: $RELEASES"
