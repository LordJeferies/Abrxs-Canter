import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import auto_compare as a
import stage1 as s


def words(text, start=1):
    return [{'text':t,'start':start+i*.3,'end':start+i*.3+.25} for i,t in enumerate(text.split())]


def clip(text='uno dos tres cuatro cinco',start=1,end=2.45):
    return {'id':'x','origin':'C01','title':'Test','revision':1,'source':{'path':'fake','size':1,'sampleHash':'x'},
            'format':{},'alignment':[{'id':'s','order':1,'text':text,'start':start,'end':end}], 'blocks':[]}


class ComparisonTests(unittest.TestCase):
    def test_matched_compares_each_endpoint(self):
        index=a.WordIndex(words('uno dos tres cuatro cinco'),20)
        self.assertEqual(a.compare(clip(),index)['variants'],['MATCHED'])
        r=a.compare(clip(start=1.19,end=2.64),index)
        self.assertEqual(r['variants'],['EDITORIAL','WORD_ALIGNED'])
        self.assertEqual(r['differences'][0]['durationMs'],0)
        self.assertEqual(r['differences'][0]['startMs'],-190)

    def test_repetitions_need_unique_temporal_context(self):
        index=a.WordIndex(words('uno dos tres cuatro cinco',1)+words('uno dos tres cuatro cinco',10),30)
        self.assertEqual(index.locate('uno dos tres cuatro cinco',9)['start'],10)
        self.assertNotEqual(index.locate('uno dos tres cuatro cinco')['confidence'],a.HIGH)

    def test_omissions_are_discontinuous_in_one_recipe(self):
        index=a.WordIndex(words('uno dos tres cuatro cinco ruido extra final de la frase aqui'),30)
        r=a.compare(clip('uno dos tres cuatro cinco [...] final de la frase aqui'),index)
        self.assertEqual(len(r['editorial']),1)
        self.assertEqual(len(r['wordAligned']),2)
        self.assertEqual(r['variants'],['EDITORIAL','WORD_ALIGNED'])
        self.assertGreater(r['wordAligned'][1]['start'],r['wordAligned'][0]['end'])

    def test_retry_uses_next_omission_fragment_as_context(self):
        index=a.WordIndex(words('frase repetida',1)+words('frase repetida siguiente contexto',100),200)
        found=index.locate('frase repetida',following='siguiente contexto')
        self.assertEqual(found['confidence'],a.HIGH)
        self.assertEqual(found['start'],100)
        self.assertEqual(found['attempts'],[1,2])

    def test_approximate_hint_retries_global(self):
        index=a.WordIndex(words('uno dos tres cuatro cinco',100),200)
        found=index.locate('uno dos tres cuatro cinco',1)
        self.assertEqual(found['confidence'],a.HIGH)
        self.assertEqual(found['attempts'],[1,2])

    def test_incomplete_or_ambiguous_does_not_fabricate(self):
        index=a.WordIndex(words('uno dos tres cuatro cinco'),20)
        r=a.compare(clip('palabras ausentes tres cuatro cinco'),index)
        self.assertEqual(r['variants'],['EDITORIAL'])
        self.assertEqual(r['wordAligned'],[])
        self.assertNotEqual(r['confidence'],a.HIGH)

    def test_invalid_editorial_and_text_only(self):
        index=a.WordIndex(words('uno dos tres cuatro cinco'),20)
        for start,end in ((-1,3),(1,99),(None,None),(float('nan'),2)):
            r=a.compare(clip(start=start,end=end),index)
            self.assertEqual(r['variants'],['WORD_ALIGNED'])
        self.assertEqual(a.compare(clip('',None,None),index)['variants'],[])

    def test_margin_does_not_include_next_dialogue(self):
        index=a.WordIndex(words('uno dos tres cuatro cinco posterior'),20)
        r=a.compare(clip(),index)
        b=a.export_blocks(r['wordAligned'],index,.2,True)[0]
        self.assertEqual(b['end'],2.5)
        self.assertEqual(r['wordAligned'][0]['end'],2.45)
        self.assertAlmostEqual(a.export_blocks(r['editorial'],index,.2)[0]['end'],2.65)

    def test_anomalous_duration_and_backwards_word_times(self):
        data=words('uno dos tres cuatro cinco'); data[-1]['end']=19
        self.assertNotEqual(a.WordIndex(data,20).locate('uno dos tres cuatro cinco',1)['confidence'],a.HIGH)
        data=words('uno dos tres cuatro cinco'); data[2]['end']=8
        self.assertNotEqual(a.WordIndex(data,20).locate('uno dos tres cuatro cinco',1)['confidence'],a.HIGH)

    @unittest.skipUnless((Path(__file__).parent/'fixtures/pocaterra_66.json').is_file(), "Requiere fixtures privadas locales; no se publican transcripciones.")
    def test_pocaterra_66_real_editorial_and_transcript(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/pocaterra_66.json').read_text())
        self.assertEqual(len(fixture['clips']),66)
        index=a.WordIndex(fixture['words'],fixture['duration'])
        counts={}
        for c in fixture['clips']:
            before=copy.deepcopy(c)
            r=a.compare(c,index)
            self.assertEqual(before,c)
            self.assertIn('EDITORIAL',r['variants'] if r['status']!='MATCHED' else ['EDITORIAL'])
            if r['wordAligned']:
                self.assertEqual(r['confidence'],a.HIGH)
                self.assertTrue(all(d['confidence']==a.HIGH for d in r['segments']))
            counts[r['status']]=counts.get(r['status'],0)+1
        self.assertEqual(counts,{'DIFFERENT':44,'MATCHED':2,'ALIGNMENT_UNRESOLVED':20})

    def test_selected_subset_keeps_intro_order_and_one_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            x=clip();x['source']=s.source_identity(__file__)
            y=copy.deepcopy(x);y.update(id='y',origin='C02');y['alignment'][0].update(start=10,end=11.45)
            intro=copy.deepcopy(x);intro.update(id='intro',origin='INTRO');intro['alignment']=[{**y['alignment'][0],'order':1},{**x['alignment'][0],'order':2}]
            s.atomic_json(s.db_path(Path(tmp)),{'schemaVersion':1,'clips':[x,y,intro]})
            with patch.object(s,'normalized_words',return_value=words('uno dos tres cuatro cinco')+words('uno dos tres cuatro cinco',10)),patch.object(s,'media_info',return_value={'duration':20}):
                r=s.export_clips({'projectPath':tmp,'ids':['x'],'exportMode':'compare_auto','dryRun':True})
            self.assertTrue(r['introOrderVerified'])
            self.assertEqual(r['clips'][0]['order'],2)
            self.assertEqual(Path(r['reportPath']).parent.name,'COMPARACION_AUTOMATICA')
            recipe={**x,'variant':'MATCHED','comparisonOrder':2,'blocks':[{'role':'HOOK'}]}
            self.assertTrue(s.comparison_filename(recipe,'abcdef').startswith('002_C01_'))

    def test_variant_failure_does_not_cancel_alternative_or_next_piece(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=clip(start=1.5,end=3);c['source']=s.source_identity(__file__)
            other=copy.deepcopy(c);other['id']='y';other['origin']='C02'
            s.atomic_json(s.db_path(Path(tmp)),{'schemaVersion':1,'clips':[c,other]})
            output=Path(tmp)/'result.mp4';output.write_bytes(b'test')
            variants=[]
            def render(root,recipe,*args):
                variants.append((recipe['id'],recipe['variant']))
                if recipe['id']=='x' and recipe['variant']=='EDITORIAL':
                    raise RuntimeError('fallo individual')
                return output
            with patch.object(s,'normalized_words',return_value=words('uno dos tres cuatro cinco')),patch.object(s,'media_info',return_value={'duration':20}),patch.object(s,'export_one',side_effect=render):
                r=s.export_clips({'projectPath':tmp,'ids':['x','y'],'exportMode':'compare_auto'})
            self.assertEqual(variants,[('x','EDITORIAL'),('x','WORD_ALIGNED'),('y','EDITORIAL'),('y','WORD_ALIGNED')])
            self.assertEqual([e['id'] for e in r['failed']],['x'])
            self.assertEqual(r['completed'],['y'])

    def test_ffmpeg_na_initial_progress_does_not_abort_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable=Path(tmp)/'fake-ffmpeg'
            executable.write_text('#!/usr/bin/env python3\nimport time\nprint("out_time_us=N/A\\nprogress=continue",flush=True)\ntime.sleep(.1)\nprint("out_time_us=1000000\\nprogress=end",flush=True)\ntime.sleep(.1)\n')
            executable.chmod(0o755)
            with patch.object(s,'event') as events:
                s.render_section([str(executable)],1,'clip',0,1,0,1)
            self.assertTrue(events.called)
            self.assertIsNone(s.ACTIVE_PROCESS)

    def test_automatic_import_is_idempotent_and_dry_run_is_read_only(self):
        import abraxas_local as engine
        with tempfile.TemporaryDirectory() as tmp:
            data={'words':words('uno dos tres cuatro cinco'),'media':{'duration':20},'source':{'sampleHash':'abc'},'transcript':None}
            piece=engine.Piece('C01','Test',segments=[engine.Segment('s',1,'uno dos tres cuatro cinco',start=None,end=None)])
            req={'projectPath':tmp,'_dryRun':True}
            a.import_pieces(req,s,engine,data,[piece])
            self.assertFalse(s.db_path(Path(tmp)).exists())
            req.pop('_dryRun')
            first=a.import_pieces(req,s,engine,data,[piece])
            second=a.import_pieces(req,s,engine,data,[piece])
            self.assertEqual(first['targetIds'],second['targetIds'])
            self.assertEqual(len(second['clips']),1)
            self.assertFalse(second['clips'][0]['textVerified'])
            self.assertEqual(second['clips'][0]['variant'],'AUTO_COMPARISON')
            self.assertTrue(second['clips'][0]['blocks'])

    def test_batch_continues_after_error_and_reuses_without_duplicate_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); good=clip();good['source']=s.source_identity(__file__)
            bad={**copy.deepcopy(good),'id':'bad','source':{'path':'/missing','size':1,'sampleHash':'bad'}}
            s.atomic_json(s.db_path(root),{'schemaVersion':1,'clips':[bad,good]})
            req={'projectPath':tmp,'ids':['bad','x'],'exportMode':'compare_auto'}
            output=root/'existing.mp4';output.write_bytes(b'fixture')
            def render(*args): return output
            with patch.object(s,'normalized_words',return_value=words('uno dos tres cuatro cinco')),patch.object(s,'media_info',return_value={'duration':2.45-1}),patch.object(s,'export_one',side_effect=render) as renderer:
                # Source duration must be distinct from output duration.
                s.media_info.side_effect=lambda p: {'duration':1.85 if str(p)==str(output) else 20}
                first=s.export_clips(req)
                self.assertEqual([f['id'] for f in first['failed']],['bad'])
                self.assertEqual(first['completed'],['x'])
                renderer.assert_called_once()
                second=s.export_clips(req)
                renderer.assert_called_once()
                self.assertTrue(second['clips'][1]['files'][0]['reused'])
                self.assertEqual(len(s.load_db(root)['clips']),2)
                self.assertNotIn('textVerified',s.load_db(root)['clips'][1])
                self.assertTrue((root/'VIDEOS/COMPARACION_AUTOMATICA/COMPARACION_CORTES.json').exists())
                self.assertEqual(s.read_json(root/'EDICIONES/COLA_EXPORTACION.json')['status'],'finished')

if __name__=='__main__': unittest.main()
