import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
import stage1 as m


class Stage1Tests(unittest.TestCase):
    def test_bounds(self):
        for block in [{'start':-1,'end':1},{'start':1,'end':1},{'start':0,'end':float('nan')},{'start':0,'end':12}]:
            with self.assertRaises(ValueError): m.validate_blocks([block],10)

    def test_reordered_words(self):
        words=[{'text':'hola','start':30,'end':31}]
        blocks=[{'uid':'a','start':30,'end':35},{'uid':'b','start':15,'end':45},{'uid':'c','start':30,'end':35}]
        result=m.virtual_words(words,blocks)
        self.assertEqual([w['start'] for w in result],[0,20,35])
        self.assertEqual(words[0]['start'],30)

    def test_invalid_format(self):
        with self.assertRaises(ValueError): m.validate_format({'aspect':'4:3'})
        with self.assertRaises(ValueError): m.validate_format({'x':float('inf')})

    def test_cache_safety(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'VIDEOS').mkdir(); original=root/'VIDEOS/original.mp4';original.write_bytes(b'keep')
            cache=m.cache_dir(root);cache.mkdir();(cache/'test.mp4').write_bytes(b'cache')
            m.prune_cache(root,limit=0)
            self.assertTrue(original.exists());self.assertFalse((cache/'test.mp4').exists())

    def test_atomic_json_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.json';m.atomic_json(path,{'valid':1})
            with self.assertRaises(ValueError):m.atomic_json(path,{'invalid':float('nan')})
            self.assertEqual(m.read_json(path),{'valid':1})

    def test_export_invalidated(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'clip.mp4';path.write_bytes(b'old')
            clip={'source':{'size':10,'sampleHash':'x'},'blocks':[{'start':0,'end':1}], 'format':{},'variant':'MANUAL'}
            clip['export']={'path':str(path),'signature':m.recipe_signature(clip)}
            m.mark_export(clip);self.assertEqual(clip['exportState'],'exported')
            clip['blocks'][0]['end']=2;m.mark_export(clip);self.assertEqual(clip['exportState'],'outdated')
            self.assertEqual(path.read_bytes(),b'old')

    def test_report_migration_padding_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'master.mp4';source.write_bytes(b'master')
            output=root/'output';output.mkdir()
            summary={'video':str(source),'media':{'duration':10},'padding_before_seconds':.2,'padding_after_seconds':.2,'pieces':[
                {'piece':'A01','title':'A','variants':{'TIMESTAMP':1},'source':{'segments':[{'start':1,'end':2,'text':'hola'}]},'videos':[]}]}
            m.atomic_json(output/'PROYECTO.json',summary)
            db=m.migrate_reports(root,output);self.assertEqual(len(db['clips']),1)
            self.assertAlmostEqual(db['clips'][0]['blocks'][0]['start'],.8)
            self.assertEqual(len(m.migrate_reports(root,output)['clips']),1)

    def test_revision_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'master.mp4';source.write_bytes(b'master')
            clip={'id':'same','revision':0,'source':m.source_identity(source),'duration':10,'blocks':[{'start':1,'end':2}],'format':{},'title':'Test'}
            with patch.object(m,'media_info',return_value={'duration':10}):
                saved=m.save_clip({'projectPath':folder,'clip':clip})
                self.assertEqual(saved['revision'],1)
                with self.assertRaises(ValueError):m.save_clip({'projectPath':folder,'clip':clip})


if __name__=='__main__':unittest.main()
