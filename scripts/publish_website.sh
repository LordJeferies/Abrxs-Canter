#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPO="LordJeferies/Abrxs-Canter"
gh auth status
[ "$(git branch --show-current)" = main ] || { echo 'Debes estar en la rama main.'; exit 1; }
[ "$(git remote get-url origin)" = "https://github.com/$REPO.git" ] || { echo 'El remoto origin no coincide con Abrxs-Canter.'; exit 1; }
[ -z "$(git diff --cached --name-only)" ] || { echo 'Hay archivos preparados por otro trabajo. Revísalos antes de publicar.'; exit 1; }
git add docs/index.html docs/styles.css docs/.nojekyll scripts/publish_website.sh
if ! git diff --cached --quiet; then
  git commit -m 'Add public Spanish usage guide for GitHub Pages'
fi
if git grep -q -E 'ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|/Users/lordjef' HEAD -- ':!scripts/verify_source.sh' ':!scripts/publish_website.sh'; then
  echo 'Publicación detenida: posible credencial o ruta personal.'; exit 1
else
  result=$?
  [ "$result" -eq 1 ] || exit "$result"
fi
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main
PAGES_INFO="$(mktemp /tmp/abrxs-pages.XXXXXX)"
if gh api "repos/$REPO/pages" > "$PAGES_INFO" 2>&1; then
  gh api --method PUT "repos/$REPO/pages" -f build_type=legacy -f 'source[branch]=main' -f 'source[path]=/docs'
elif grep -q 'HTTP 404' "$PAGES_INFO"; then
  gh api --method POST "repos/$REPO/pages" -f build_type=legacy -f 'source[branch]=main' -f 'source[path]=/docs'
else
  cat "$PAGES_INFO"
  echo 'No se pudo comprobar Pages. La subida de código terminó; revisa este error antes de activar la web.'
  exit 1
fi
echo
echo 'GitHub Pages configurado. La primera publicación puede tardar unos minutos.'
echo 'Web: https://lordjeferies.github.io/Abrxs-Canter/'
echo 'Estado: https://github.com/LordJeferies/Abrxs-Canter/actions'
