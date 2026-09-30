#!/bin/zsh
set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"
cargo tauri build --bundles app
echo "Aplicación creada en src-tauri/target/release/bundle/macos/abrxs-Canter.app"

