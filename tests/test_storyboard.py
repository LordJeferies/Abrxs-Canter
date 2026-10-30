import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import stage1 as s
import storyboard
from spoken_alignment import SpokenIndex


def words(text,start=1):
    return [{'text':t,'start':start+i*.4,'end':start+i*.4+.3} for i,t in enumerate(text.split())]


class StoryboardTests(unittest.TestCase):
    def test_repeated_utterances_need_context(self):
        idx=SpokenIndex(words('esta frase esta repetida',1)+words('esta frase esta repetida',10),30)
        self.assertEqual(idx.locate('esta frase esta repetida')['confidence'],'UNRESOLVED')
        self.assertEqual(idx.locate('esta frase esta repetida',10)['start'],10)

    def test_repetition_normalization_does_not_change_words_or_times(self):
        original=words('si estamos pensando en colonizar otros planetas')
        before=copy.deepcopy(original);idx=SpokenIndex(original,30)
        r=idx.locate('sí estamos pensando en en en colonizar otros planetas',1)
        self.assertEqual(r['confidence'],'AUTO_ALIGNED_HIGH')
        self.assertEqual(original,before)
        self.assertEqual((r['start'],r['end']),(original[0]['start'],original[-1]['end']))

    def test_meaningful_adjacent_repetition_is_not_lost(self):
        idx=SpokenIndex(words('traslado casa-trabajo trabajo-casa'),30)
        self.assertEqual(idx.locate('traslado casa trabajo trabajo casa',1)['confidence'],'AUTO_ALIGNED_HIGH')

    def test_unselected_dialogue_is_rejected(self):
        idx=SpokenIndex(words('comienza nuestra propuesta pero cambiemos completamente de tema termina propuesta'),30)
        self.assertEqual(idx.locate('comienza nuestra propuesta termina propuesta',1)['confidence'],'UNRESOLVED')

    def test_numbers_aliases_and_zero_duration_are_explicit(self):
        data=words('dos años con Huawei');data[0]['end']=data[0]['start'];original=copy.deepcopy(data)
        idx=SpokenIndex(data,30,{'dos':'2','huawei':'wawa'})
        r=idx.locate('2 años con Wawa',1)
        self.assertEqual(r['confidence'],'AUTO_ALIGNED_HIGH')
        self.assertEqual(r['timingConfidence'],'COLLAPSED_WORD_TIMES')
        self.assertTrue(r['zeroDurationRepairs'])
        self.assertEqual(original,data)

    @unittest.skipUnless((Path(__file__).parent/'fixtures/pocaterra_66.json').is_file() and (Path(__file__).parent/'fixtures/pocaterra_intro_revisado.json').is_file(), "Requiere fixtures privadas locales; no se publican transcripciones.")
    def test_all_64_subcuts_and_51_paragraphs_with_real_transcript(self):
        fixtures=Path(__file__).parent/'fixtures'
        d=json.loads((fixtures/'pocaterra_intro_revisado.json').read_text());transcript=json.loads((fixtures/'pocaterra_66.json').read_text())
        index=SpokenIndex(transcript['words'],d['duration'],d['aliases'])
        self.assertEqual(len(d['jsonClips']),64)
        self.assertEqual(len(d['items']),72)
        speech=[i for i in d['items'] if i['type']=='speech'];self.assertEqual(len(speech),51)
        self.assertEqual(len({cid for i in speech for cid in i['sourceIds']}),64)
        self.assertEqual(sum(i['type']=='black' and i['duration']==2 for i in d['items']),19)
        self.assertEqual(sum(i['type']=='voiceover' and i['duration']==10 for i in d['items']),2)
        for item in speech:
            for fragment in item['matches']:
                with self.subTest(paragraph=item['id'],text=fragment['text']):
                    result=index.locate(fragment['text'],fragment['start'])
                    self.assertEqual(result['confidence'],'AUTO_ALIGNED_HIGH')
                    self.assertEqual(result['start'],fragment['start']);self.assertEqual(result['end'],fragment['end'])
                    blocks=index.blocks([{**result,'text':fragment['text']}])
                    self.assertGreater(blocks[0]['end'],blocks[0]['start'])
                    self.assertLessEqual(blocks[0]['end'],d['duration'])
        self.assertEqual(sum(bool(i['notes']) for i in speech),3)

    def test_backend_exports_both_folders_and_resumes_without_new_cards(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);horizontal=root/'h.master';vertical=root/'v.master';horizontal.write_bytes(b'h');vertical.write_bytes(b'v')
            plan={'schemaVersion':1,'sources':{'horizontal':s.source_identity(horizontal),'vertical':s.source_identity(vertical)},'transcript':None,'aliases':{},
                  'items':[{'order':1,'type':'speech','id':'P01','text':'uno dos tres cuatro cinco','sourceIds':['C001'],'notes':[],
                            'matches':[{'text':'uno dos tres cuatro cinco','start':1,'role':'HOOK'}]},
                           {'order':2,'type':'black','text':'[Espacio Negro]','duration':2},
                           {'order':3,'type':'voiceover','text':'VO','duration':10}]}
            path=root/'plan.json';s.atomic_json(path,plan)
            def media(p):
                p=str(p)
                if Path(p).name=='v.master':return {'duration':30,'width':1080,'height':1920}
                return {'duration':30 if Path(p).name=='h.master' else 2.3,'width':1920,'height':1080}
            def render(project,recipe,*args):
                p=Path(recipe['comparisonFolder'])/s.comparison_filename(recipe,s.recipe_signature(recipe));p.write_bytes(b'encoded');return p
            def gap(stage,project,folder,item,source,orientation,*args):
                p=folder/f"{item['order']:03d}_{item['type']}_{orientation}.mp4";p.write_bytes(b'black')
                return {'path':str(p),'duration':item['duration'],'hasVoiceAudio':False}
            with patch.object(s,'media_info',side_effect=media),patch.object(s,'normalized_words',return_value=words('uno dos tres cuatro cinco')),patch.object(s,'export_one',side_effect=render) as exporter,patch.object(storyboard,'gap',side_effect=gap):
                result=s.dispatch({'op':'export_storyboard','projectPath':str(root),'storyboardPath':str(path)})
                self.assertEqual(len(result['completed']),6);self.assertFalse(result['failed'])
                self.assertEqual(exporter.call_count,2)
                result=s.dispatch({'op':'export_storyboard','projectPath':str(root),'storyboardPath':str(path)})
                self.assertEqual(exporter.call_count,2)
                self.assertEqual(len(s.load_db(root)['clips']),2)
                self.assertTrue((root/'HORIZONTALES').is_dir());self.assertTrue((root/'VERTICALES').is_dir())
                self.assertEqual(s.read_json(root/'EDICIONES/COLA_EXPORTACION.json')['status'],'finished')
                self.assertTrue(all(not c['textVerified'] and not c['boundariesReviewed'] for c in s.load_db(root)['clips']))
                plan['items'][0]['matches'][0]['text']='no existen estas palabras'
                s.atomic_json(path,plan)
                result=s.dispatch({'op':'export_storyboard','projectPath':str(root),'storyboardPath':str(path)})
                self.assertEqual(len(result['failed']),2)
                self.assertEqual(len(result['completed']),4)

if __name__=='__main__':unittest.main()
