import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import stage1
import stage3

class StudioTests(unittest.TestCase):
    def test_invalid_fragment(self):
        for start, end in ((-1, 2), (2, 2), (0, float('nan'))):
            with self.assertRaises(ValueError):
                stage3.validate_workspace({'fragments': [{'start': start, 'end': end}]})

    def test_duplicate_ids(self):
        with self.assertRaises(ValueError):
            stage3.validate_workspace({'fragments': [{'id':'a','start':0,'end':2}]*2})

    def test_project_isolation_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            value=stage3.default_workspace()
            value.update(view='map', positions={'clip-a':{'x':20,'y':40}}, fragments=[{'id':'a','start':1,'end':4,'sourceHash':'abc','text':'Hola'}])
            stage1.dispatch({'op':'studio_save','projectPath':one,'workspace':value})
            self.assertEqual(stage1.dispatch({'op':'studio_load','projectPath':one}),value)
            self.assertEqual(stage1.dispatch({'op':'studio_load','projectPath':two})['fragments'],[])

    def test_visual_outside_project_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            value=stage3.default_workspace();value['visual']='/outside/report.json'
            stage1.dispatch({'op':'studio_save','projectPath':root,'workspace':value})
            with self.assertRaises(ValueError):stage1.dispatch({'op':'studio_visual','projectPath':root})

    def test_suggestions_and_context(self):
        data={'source':{'path':'master.mp4','sampleHash':'abc'},'media':{'duration':80},'words':[{'start':i,'end':i+1,'text':'sillas.' if i%10==0 else 'texto'} for i in range(80)]}
        with tempfile.TemporaryDirectory() as root, patch.object(stage1,'source_data',return_value=data):
            req={'projectPath':root,'op':'studio_suggest','seconds':20,'keywords':'sillas'}
            result=stage1.dispatch(req)
            self.assertGreater(len(result['items']),0)
            self.assertIn('sillas',result['items'][0]['reason'])
            context=stage1.dispatch({**req,'op':'studio_context'})
            self.assertTrue(Path(context['textPath']).is_file())
            self.assertTrue(Path(context['path'],'CONTEXTO.json').is_file())

if __name__=='__main__':unittest.main()
