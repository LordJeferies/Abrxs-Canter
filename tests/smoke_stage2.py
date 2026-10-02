"""Prueba de exportación con captions y seguimiento; Vision solo con --vision."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import stage1 as m
import stage2

with tempfile.TemporaryDirectory(prefix='abrxs-stage2-') as temp:
    root = Path(temp)
    video = root / 'master.mp4'
    subprocess.run([m.command('ffmpeg'), '-v','error','-f','lavfi','-i',
        'testsrc2=size=320x180:rate=25:duration=3','-f','lavfi','-i',
        'sine=frequency=440:duration=3','-c:v','libx264','-c:a','aac','-shortest',str(video)], check=True, timeout=30)
    transcript = root / 'words.json'
    m.atomic_json(transcript, {'words':[{'word':'Hola','start':.2,'end':.5},{'word':'mundo','start':.6,'end':1.0},{'word':'ahora.','start':1.1,'end':1.4}]})
    clip = {'id':'stage2-smoke','revision':0,'title':'Prueba etapa 2','source':m.source_identity(video),
        'transcript':str(transcript),'blocks':[{'uid':'a','start':.2,'end':1.5}], 'status':'draft','variant':'MANUAL',
        'format':{'aspect':'1:1','mode':'cover','x':.5,'y':.5},
        'captions':{'mode':'burn','style':stage2.style()},
        'tracking':{'points':[{'time':.2,'x':.3,'y':.5},{'time':1.5,'x':.7,'y':.5}],'format':{'aspect':'1:1'}}}
    m.save_clip({'projectPath':str(root),'clip':clip})
    result = m.export_clips({'projectPath':str(root),'ids':[clip['id']]})
    assert not result['failed'], result
    path = Path(m.load_db(root)['clips'][0]['export']['path'])
    assert path.with_suffix('.srt').is_file() and path.with_suffix('.ass').is_file()
    info = m.media_info(path)
    assert info['width'] == info['height'] == 1080
    assert abs(info['duration'] - 1.3) < .3
    print('OK: captions ASS+SRT, MP4 con captions y recorte dinámico.')
    if '--vision' in sys.argv:
        visual = stage2.visual_job({'projectPath':str(root),'video':str(video),'mode':'analysis','step':1})
        assert len(visual['samples']) >= 2
        assert Path(visual['textPath']).is_file()
        print('OK: Vision local y reporte con timestamps reales.')
