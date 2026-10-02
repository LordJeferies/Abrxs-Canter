"""Prueba real de FFmpeg con vídeo sintético; no usa archivos del usuario."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import stage1 as m

with tempfile.TemporaryDirectory(prefix='abrxs-smoke-') as temp:
    root = Path(temp)
    video = root / 'master.mp4'
    subprocess.run([m.command('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=320x180:rate=25:duration=4', '-f', 'lavfi', '-i',
                    'sine=frequency=440:duration=4', '-c:v', 'libx264', '-c:a', 'aac',
                    '-shortest', str(video)], check=True, timeout=30)
    clip = {'id': 'smoke', 'revision': 0, 'title': 'Prueba',
            'source': m.source_identity(video), 'transcript': None, 'duration': 4,
            'blocks': [{'uid': 'a', 'start': 2, 'end': 2.6},
                       {'uid': 'b', 'start': .2, 'end': .8}],
            'status': 'draft', 'variant': 'MANUAL',
            'format': {'aspect': '1:1', 'mode': 'contain', 'x': .5, 'y': .5}}
    saved = m.save_clip({'projectPath': str(root), 'clip': clip})
    # save_clip returns the persisted recipe.
    assert saved['revision'] == 1
    result = m.export_clips({'projectPath': str(root), 'ids': ['smoke'], 'sections': True})
    assert not result['failed'], result
    exported = m.load_db(root)['clips'][0]['export']
    info = m.media_info(exported['path'])
    assert info['width'] == info['height'] == 1080, info
    assert abs(info['duration'] - 1.2) < .3, info
    assert Path(exported['path']).with_suffix('.txt').exists()
    first = Path(exported['path'])
    changed = m.load_db(root)['clips'][0]
    changed['blocks'][0]['end'] = 2.8
    m.save_clip({'projectPath': str(root), 'clip': changed})
    again = m.export_clips({'projectPath': str(root), 'ids': ['smoke']})
    assert not again['failed'], again
    assert first.exists(), 'La exportación anterior debe conservarse'
    assert m.load_db(root)['clips'][0]['export']['path'] != str(first)
    print('OK: montaje reordenado, MP4+TXT, formato y versiones conservadas.')
