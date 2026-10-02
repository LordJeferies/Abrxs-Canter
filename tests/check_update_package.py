"""Comprueba el instalador en una copia temporal, sin red ni compilación."""
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
artifact = Path(sys.argv[1]).read_text()
python = artifact.split("python3 - <<'ABRXS_INSTALLER'\n", 1)[1].rsplit('\nABRXS_INSTALLER', 1)[0]
module = ast.parse(python)
# No ejecutar el arranque interactivo del instalador.
module.body = module.body[:-1]
namespace = {}
exec(compile(module, '<installer>', 'exec'), namespace)
raw = base64.b64decode(namespace['PAYLOAD'])
assert hashlib.sha256(raw).hexdigest() == namespace['DIGEST']
archive = zipfile.ZipFile(io.BytesIO(raw))
manifest = json.loads(archive.read('manifest.json'))
with tempfile.TemporaryDirectory(prefix='abrxs-update-test-') as folder:
    checkout = Path(folder) / 'repo'
    subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', str(root), str(checkout)], check=True)
    subprocess.run(['git', 'remote', 'set-url', 'origin', 'https://github.com/LordJeferies/Abrxs-Canter.git'], cwd=checkout, check=True)
    sentinel = checkout / 'NO_BORRAR.txt'
    sentinel.write_text('Trabajo ajeno preservado')
    namespace['prompt'] = lambda *_: str(checkout)
    answers = iter([True, False, False])
    namespace['ask'] = lambda *_: next(answers)
    namespace['main']()
    for name, info in manifest['files'].items():
        assert hashlib.sha256((checkout / name).read_bytes()).hexdigest() == info['new'], name
    assert sentinel.read_text() == 'Trabajo ajeno preservado'
    assert list(Path(folder).glob('Abrxs-respaldo-etapa1-*/RESPALDO.json'))
    # Una versión incompatible debe detenerse antes de sobrescribir nada.
    (checkout / 'dist/app.js').write_text('Cambio ajeno incompatible')
    namespace['ask'] = lambda *_: True
    try:
        namespace['main']()
        raise AssertionError('No detectó una versión incompatible')
    except RuntimeError as error:
        assert 'adaptar' in str(error)
    assert (checkout / 'dist/app.js').read_text() == 'Cambio ajeno incompatible'
print('OK: paquete aplicado con respaldo; cambios incompatibles y archivos ajenos preservados.')
