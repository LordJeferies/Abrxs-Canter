"""Empaqueta un actualizador autocontenido, sin lanzar asistentes ni Codex."""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['dist/app.js', 'dist/index.html', 'dist/stage1-core.js',
         'dist/stage1.js', 'dist/stage1.css', 'engine/stage1.py',
         'src-tauri/src/lib.rs', 'src-tauri/tauri.conf.json',
         'tests/test_stage1.py', 'tests/stage1-core.test.cjs',
         'tests/smoke_stage1.py', 'ETAPA_1.md', 'scripts/package_stage1_update.py']

INSTALLER = r'''#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta Python 3. Instálalo antes de ejecutar este actualizador."
  exit 1
fi
python3 - <<'ABRXS_INSTALLER'
import base64, hashlib, io, json, os, pathlib, shutil, subprocess, sys, tempfile, zipfile
from datetime import datetime

PAYLOAD = '__PAYLOAD__'
DIGEST = '__DIGEST__'
HOME = pathlib.Path.home()

def ask(text, default=False):
    with open('/dev/tty', 'w') as display:
        display.write(text + (' [S/n]: ' if default else ' [s/N]: ')); display.flush()
    with open('/dev/tty', 'r') as keyboard:
        answer = keyboard.readline().strip().lower()
    return default if not answer else answer in ('s', 'si', 'sí', 'y', 'yes')

def prompt(text, default):
    with open('/dev/tty', 'w') as display:
        display.write(f'{text}\nEnter = {default}\n> '); display.flush()
    with open('/dev/tty', 'r') as keyboard:
        return keyboard.readline().strip() or str(default)

def run(args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)

def output(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    print('\nABRXS-CANTER · ACTUALIZADOR ETAPA 1\n')
    print('Añade biblioteca, edición por texto/timeline, preview del máster y exportación selectiva.')
    print('No abre Codex. No genera DMG. No sube nada a GitHub ni cambia tus proyectos.')
    print('Puede descargar el repositorio; compilar e instalar la app requiere confirmación aparte.')
    if not ask('¿Aplicar el código de la etapa 1?'):
        return
    raw = base64.b64decode(PAYLOAD, validate=True)
    if digest(raw) != DIGEST:
        raise RuntimeError('El paquete está incompleto o fue modificado.')
    archive = zipfile.ZipFile(io.BytesIO(raw))
    manifest = json.loads(archive.read('manifest.json'))
    names = list(manifest['files'])
    if set(archive.namelist()) != set(names) | {'manifest.json'}:
        raise RuntimeError('Contenido del paquete inesperado.')
    for name in names:
        path = pathlib.PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
            raise RuntimeError('Ruta del paquete no válida.')
        if digest(archive.read(name)) != manifest['files'][name]['new']:
            raise RuntimeError('Archivo dañado: ' + name)
    default = HOME / 'Documents' / 'Abrxs-Canter-Etapa-1'
    root = pathlib.Path(prompt('Carpeta de desarrollo (puede ser una copia existente):', default)).expanduser().resolve()
    if root == HOME or root == pathlib.Path('/') or root == HOME / 'Documents':
        raise RuntimeError('Selecciona una carpeta exclusiva del código de Abrxs-Canter.')
    if not shutil.which('git'):
        raise RuntimeError('Falta Git. Instala las herramientas de desarrollo de macOS primero.')
    if not root.exists():
        run(['git', 'clone', 'https://github.com/LordJeferies/Abrxs-Canter.git', str(root)])
    if output(['git', 'rev-parse', '--show-toplevel'], root) != str(root):
        raise RuntimeError('La carpeta no es la raíz del repositorio.')
    remote = output(['git', 'remote', 'get-url', 'origin'], root).lower().removesuffix('.git').rstrip('/')
    if remote not in ('https://github.com/lordjeferies/abrxs-canter', 'git@github.com:lordjeferies/abrxs-canter'):
        raise RuntimeError('El repositorio seleccionado no es LordJeferies/Abrxs-Canter.')
    conflicts = []
    for name, info in manifest['files'].items():
        path = root / name
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root.parent):
            raise RuntimeError('No se modifican rutas con enlaces simbólicos: ' + name)
        current = digest(path.read_bytes()) if path.exists() else None
        if current not in (info['old'], info['new']):
            conflicts.append(name)
    if conflicts:
        print('\nNo se tocó ningún archivo. Esta copia tiene cambios incompatibles:')
        print('\n'.join(conflicts))
        raise RuntimeError('Se necesita adaptar el actualizador a esta versión; no fuerces la instalación.')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = root.parent / ('Abrxs-respaldo-etapa1-' + stamp)
    backup.mkdir(exist_ok=False)
    changed = []
    try:
        for name in names:
            dest = root / name
            if dest.exists() and digest(dest.read_bytes()) == manifest['files'][name]['new']:
                continue
            existed = dest.exists()
            if existed:
                saved = backup / name; saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, saved)
            changed.append((name, existed))
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as stream:
                stream.write(archive.read(name)); stream.flush(); os.fsync(stream.fileno())
                temporary = pathlib.Path(stream.name)
            os.replace(temporary, dest)
    except Exception:
        for name, existed in reversed(changed):
            dest = root / name
            if existed: shutil.copy2(backup / name, dest)
            else: dest.unlink(missing_ok=True)
        raise
    (backup / 'RESPALDO.json').write_text(json.dumps({'root': str(root), 'files': changed}, indent=2))
    print('\nCódigo aplicado. Respaldo:', backup)
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_stage1.py'], root)
    missing = [tool for tool in ('node', 'ffmpeg') if not shutil.which(tool)]
    if missing and shutil.which('brew') and ask('Falta ' + ', '.join(missing) + '. ¿Instalar solo esas herramientas con Homebrew?'):
        run(['brew', 'install', *missing])
    if shutil.which('node'):
        for name in ('dist/app.js', 'dist/stage1.js', 'dist/stage1-core.js'):
            run(['node', '--check', name], root)
        run(['node', 'tests/stage1-core.test.cjs'], root)
    if shutil.which('ffmpeg') and ask('¿Probar el exportador con un video sintético pequeño (sin tus videos)?'):
        run([sys.executable, 'tests/smoke_stage1.py'], root)
    if not ask('¿Compilar ahora una .app local, SIN DMG? Puede tardar y descargar dependencias de Rust.'):
        print('Queda el código actualizado; todavía no se generó una app nueva.'); return
    if not shutil.which('cargo') or not shutil.which('node') or not shutil.which('ffmpeg'):
        raise RuntimeError('El código está aplicado, pero faltan Cargo/Rust, Node o FFmpeg para compilar y usar la app.')
    tauri = subprocess.run(['cargo', 'tauri', '--version'], capture_output=True)
    if tauri.returncode:
        if not ask('Falta Tauri CLI. ¿Instalar tauri-cli versión 2 con Cargo?'):
            print('Código aplicado; compilación pendiente.'); return
        run(['cargo', 'install', 'tauri-cli', '--version', '^2', '--locked'])
    run(['cargo', 'tauri', 'build', '--bundles', 'app'], root)
    bundles = list((root / 'src-tauri/target/release/bundle/macos').glob('*.app'))
    if len(bundles) != 1:
        raise RuntimeError('No se encontró un único bundle generado; no se instalará ninguno automáticamente.')
    bundle = bundles[0]
    run(['codesign', '--force', '--deep', '--sign', '-', str(bundle)])
    run(['codesign', '--verify', '--deep', '--strict', str(bundle)])
    print('App generada:', bundle)
    print('La firma local no equivale a notarización ni a una prueba de funcionamiento de la interfaz.')
    if ask('¿Copiarla a ~/Applications como Abrxs-Canter-Etapa-1.app, sin reemplazar la app anterior?'):
        target = HOME / 'Applications' / 'Abrxs-Canter-Etapa-1.app'
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not ask('Ya existe esa copia. ¿Conservarla con sufijo de respaldo y poner la nueva?'):
                return
            target.rename(target.with_name('Abrxs-Canter-Etapa-1-respaldo-' + stamp + '.app'))
        run(['ditto', str(bundle), str(target)])
        print('Instalada:', target)
    print('\nNo se hizo commit ni push. Revisa ETAPA_1.md y prueba un proyecto pequeño antes de publicar.')

try:
    main()
except (Exception, KeyboardInterrupt) as error:
    print('\nDETENIDO:', error, file=sys.stderr)
    print('No se reintenta automáticamente. Conserva esta salida para revisar el problema.', file=sys.stderr)
    sys.exit(1)
ABRXS_INSTALLER
'''

def main():
    payload = io.BytesIO()
    manifest = {'schema': 1, 'baseCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'files': {}}
    with zipfile.ZipFile(payload, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            data = (ROOT / name).read_bytes()
            old = subprocess.run(['git', 'show', 'HEAD:' + name], cwd=ROOT, capture_output=True)
            manifest['files'][name] = {'old': hashlib.sha256(old.stdout).hexdigest() if old.returncode == 0 else None,
                                       'new': hashlib.sha256(data).hexdigest()}
            archive.writestr(name, data)
        archive.writestr('manifest.json', json.dumps(manifest, indent=2))
    raw = payload.getvalue()
    out = Path(sys.argv[1]).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(INSTALLER.replace('__PAYLOAD__', base64.b64encode(raw).decode()).replace('__DIGEST__', hashlib.sha256(raw).hexdigest()))
    out.chmod(0o755)
    out.with_suffix('.zip').write_bytes(raw)
    print(out)

if __name__ == '__main__':
    main()
