import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import abraxas_local as engine

class ReviewInterchangeTests(unittest.TestCase):
    def test_web_export_accepted_as_txt_and_json(self):
        code = "const c=require('./review-web/core.js');process.stdout.write(JSON.stringify(c.editorial({source:'master.mp4',name:'Test',clips:[{id:'one',title:'Clip web',blocks:[{start:10,end:15,text:'Hola mundo',role:'HOOK'},{start:20,end:25,text:'Cierre',role:'CTA'}]}]})));"
        raw = subprocess.check_output(['node', '-e', code], cwd=ROOT, text=True)
        with tempfile.TemporaryDirectory() as d:
            for ext in ['txt', 'json']:
                path = Path(d) / ('DECISIONES_ABRXS.' + ext)
                path.write_text(raw)
                pieces = engine.parse_editorial(path)
                self.assertEqual(len(pieces), 1)
                self.assertEqual(pieces[0].id, 'WEB_one')
                self.assertEqual(len(pieces[0].segments), 2)

if __name__ == '__main__':
    unittest.main()
