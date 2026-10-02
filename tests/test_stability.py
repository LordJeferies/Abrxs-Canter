import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import stage1 as m
import abraxas_local as engine

class StabilityTests(unittest.TestCase):
    def test_signature_ignores_variant_uid_but_not_boundaries(self):
        a={'source':{'size':12,'sampleHash':'abc'},'blocks':[{'uid':'a','start':1,'end':8}], 'variant':'TIMESTAMP'}
        b={**a,'variant':'VERIFIED','blocks':[{'uid':'b','start':1,'end':8}]}
        self.assertEqual(m.recipe_signature(a),m.recipe_signature(b))
        b['blocks'][0]['end']=9
        self.assertNotEqual(m.recipe_signature(a),m.recipe_signature(b))

    def test_missing_end_words_not_verified(self):
        words=[engine.Word(t,i,i+1) for i,t in enumerate('uno dos tres cuatro cinco seis siete ocho'.split())]
        start,end,score=engine.align_text('uno dos tres cuatro cinco seis siete ocho cierre inexistente',words)
        self.assertIsNone(end)

    def test_timestamp_hint_disambiguates_repeated_text(self):
        words=[engine.Word(t,i+offset,i+offset+1) for offset in (0,200) for i,t in enumerate('uno dos tres cuatro'.split())]
        class Segment:
            text='uno dos tres cuatro';start=200;end=205
        class Piece: segments=[Segment()]
        engine.align_pieces([Piece()],words)
        self.assertEqual(Piece.segments[0].aligned_start,200)

    def test_identical_export_is_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'clip.mp4';target.write_bytes(b'existing')
            clip={'id':'a','title':'Uno','source':{'path':'original','size':1,'sampleHash':'x'},'blocks':[{'start':0,'end':2}]}
            clip['export']={'path':str(target),'signature':m.recipe_signature(clip)}
            m.atomic_json(m.db_path(root),{'schemaVersion':m.SCHEMA,'clips':[clip]})
            with patch.object(m,'root_for',return_value=root),patch.object(m,'source_identity',return_value=clip['source']),patch.object(m,'export_one') as render:
                result=m.export_clips({'ids':['a']})
            render.assert_not_called();self.assertEqual(result['reused'],['a'])

    def test_unverified_timestamp_cannot_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m.atomic_json(m.db_path(root),{'schemaVersion':m.SCHEMA,'clips':[{'id':'a','title':'Uno','origin':'A01','variant':'TIMESTAMP'}]})
            with patch.object(m,'root_for',return_value=root),patch.object(m,'export_one') as render:
                result=m.export_clips({'ids':['a']})
            render.assert_not_called();self.assertEqual(len(result['failed']),1)
