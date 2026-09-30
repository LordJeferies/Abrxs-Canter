#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
cd "$ROOT"

python3 -m py_compile engine/abraxas_local.py engine/transcript_quality.py
node --check dist/app.js
cargo check --manifest-path src-tauri/Cargo.toml

SECRET_PATTERN='(ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|hf_[A-Za-z0-9]{20,}|/Users/'"lordjef"')'

if rg -n --hidden \
  --glob '!src-tauri/target/**' \
  --glob '!engine/__pycache__/**' \
  --glob '!scripts/verify_source.sh' \
  "$SECRET_PATTERN" .; then
  echo "Se detectó información local o una posible credencial." >&2
  exit 1
fi

echo "Fuente verificada."
