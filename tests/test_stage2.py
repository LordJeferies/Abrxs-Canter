import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import abraxas_local as engine
import stage2


class Stage2Tests(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'editorial.txt'
            path.write_text(content, encoding='utf-8')
            return engine.parse_editorial(path)

    def test_template_is_not_a_clip(self):
        with self.assertRaisesRegex(ValueError, 'plantilla'):
            self.parse('PLANTILLA PARA REPARAR UN ARCHIVO EDITORIAL\nSUBE A LA IA:\n{"clips": []}')

    def test_response_json_in_txt(self):
        content = {'clips': [{'id': 'C01', 'segments': [
            {'id': 's2', 'order': 2, 'start': '00:00:01.000', 'end': '00:00:02.000'},
            {'id': 's1', 'order': 1, 'start': '00:00:10.000', 'end': '00:00:12.000'}]}]}
        for wrapper in ('{}', 'Respuesta:\n```json\n{}\n```', 'Aquí está:\n{}\nListo.'):
            pieces = self.parse(wrapper.format(json.dumps(content)))
            self.assertEqual([s.start for s in pieces[0].segments], [10, 1])

    def test_plain_timestamps(self):
        result = self.parse('A01\nInicio: 00:04:08.120\nFinal: 00:04:59.520\n')
        self.assertAlmostEqual(result[0].segments[0].start, 248.12)

    def test_invalid_structured_json(self):
        for data in ({'clips': [{'id':'x','segments':[{'start':2,'end':1}]}]},
                     {'clips': [{'id':'x','segments':[{'start':1,'end':2}]},{'id':'x','segments':[{'start':2,'end':3}]}]},
                     {'clips': [{'id':'x','segments':[{'start':1}]}]}):
            with self.assertRaises(ValueError): self.parse(json.dumps(data))

    def test_text_only(self):
        data = {'clips':[{'id':'C01','segments':[{'start':None,'end':None,'text':'Esta es una frase literal.'}]}]}
        self.assertIsNone(self.parse(json.dumps(data))[0].segments[0].start)

    def test_caption_bounds_and_blocks(self):
        words = [{'start':0,'end':.3,'text':'A','blockUid':'a'}, {'start':.3,'end':.6,'text':'B','blockUid':'b'}]
        self.assertEqual(len(stage2.cues(words)), 2)
        with self.assertRaises(ValueError): stage2.style({'color':'red'})
        with self.assertRaises(ValueError): stage2.style({'font':'Arial,Fake'})
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)/'captions'
            stage2.write_captions(base, words, {}, 1080, 1920)
            self.assertIn('00:00:00,000 --> 00:00:00,300', base.with_suffix('.srt').read_text())

    def test_tracking_expression(self):
        tracking = {'points':[{'time':10,'x':0,'y':.5},{'time':12,'x':1,'y':.5}], 'format':{'aspect':'9:16'}}
        result = stage2.tracking_filter({'width':1920,'height':1080}, {'aspect':'9:16','mode':'cover'}, {'start':10,'end':12}, tracking, 'fallback')
        self.assertIn('if(lt(t,2)', result)
        with self.assertRaises(ValueError): stage2.validate_tracking({'points':[{'time':1,'x':float('nan'),'y':0}]})

if __name__ == '__main__': unittest.main()
