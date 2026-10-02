#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
cd "$ROOT"
VERSION="$(python3 -c 'import json; print(json.load(open("src-tauri/tauri.conf.json"))["version"])')"

python3 -m py_compile engine/abraxas_local.py engine/transcript_quality.py
python3 -m py_compile engine/stage1.py engine/stage2.py engine/stage3.py
node --check dist/app.js
node --check dist/stage1.js
node --check dist/ux.js
node --check dist/activity.js
node --check dist/hotfix.js
node --check dist/batch.js
node --check dist/processes.js
node --check dist/media.js
node --check dist/floating-preview.js
node --check dist/vendor/icons.js
mkdir -p engine/native
mkdir -p .build-cache/swift
xcrun swiftc engine/vision_worker.swift -module-cache-path "$ROOT/.build-cache/swift" -O -target "$(uname -m)-apple-macosx12.0" -o engine/native/abrxs-vision
cargo check --manifest-path src-tauri/Cargo.toml
cargo tauri build --bundles app

PRODUCT="$(python3 -c 'import json; print(json.load(open("src-tauri/tauri.conf.json"))["productName"])')"
APP="src-tauri/target/release/bundle/macos/$PRODUCT.app"
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
