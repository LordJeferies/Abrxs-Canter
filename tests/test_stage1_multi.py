import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import stage1 as m

class MultiMasterTests(unittest.TestCase):
    def fixture(self, root, pieces):
        path = root / 'decisions.json'
        path.write_text(json.dumps({'format': 'test', 'clips': pieces}))
        return {'projectPath': str(root), 'editorial': str(path), 'sameTimelineConfirmed': True,
                'cutMethod': 'preferred', 'masters': [{'orientation':'horizontal','video':'h.mp4','offset':0}, {'orientation':'vertical','video':'v.mp4','offset':2}]}

    def piece(self, id, kind='video', outputs=None):
        p={'id':id,'title':id,'type':kind,'segments':[{'start':10,'end':15,'text':'Hola'}]}
        if outputs is not None: p['outputs']=outputs
        return p

    def media(self, path):
        return {'duration':60, 'width':1080 if path=='v.mp4' else 1920, 'height':1920 if path=='v.mp4' else 1080}

    def data(self, req):
        path=req.get('video','h.mp4')
        return {'source':{'path':path,'sampleHash':path,'size':100,'mtimeNs':0},'media':self.media(path),'words':[],'transcript':None}

    def test_routing_and_offsets_and_repeat_preserves(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(m,'source_data',side_effect=self.data), patch.object(m,'media_info',side_effect=self.media):
            root=Path(folder)
            req=self.fixture(root,[self.piece('intro','intro'),self.piece('vertical','vertical'),self.piece('horizontal',outputs=['horizontal'])])
            result=m.import_editorial(req)
            self.assertEqual(len(result['clips']),4)
            self.assertEqual(len(result['targetIds']),4)
            vertical=[c for c in result['clips'] if c['outputOrientation']=='vertical']
            self.assertEqual(len(vertical),2)
            self.assertAlmostEqual(vertical[0]['blocks'][0]['start'],11.8)
            self.assertEqual(len(m.import_editorial(req)['clips']),4)

    def test_ambiguous_or_unconfirmed_does_not_write(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(m,'source_data',side_effect=self.data), patch.object(m,'media_info',side_effect=self.media):
            root=Path(folder);req=self.fixture(root,[self.piece('unknown')])
            with self.assertRaisesRegex(ValueError,'no indica formato'):m.import_editorial(req)
            self.assertFalse(m.db_path(root).exists())
            req['sameTimelineConfirmed']=False
            with self.assertRaisesRegex(ValueError,'Confirma'):m.import_editorial(req)

    def test_second_master_failure_keeps_original_library(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(m,'source_data',side_effect=self.data), patch.object(m,'media_info',side_effect=self.media):
            root=Path(folder);req=self.fixture(root,[self.piece('intro','intro')]);m.import_editorial(req)
            original=m.db_path(root).read_bytes()
            req['masters'][1]['offset']=100
            with self.assertRaisesRegex(ValueError,'fuera del máster'):m.import_editorial(req)
            self.assertEqual(m.db_path(root).read_bytes(),original)

if __name__=='__main__':unittest.main()
