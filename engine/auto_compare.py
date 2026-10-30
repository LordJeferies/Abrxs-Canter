"""Conservative textual comparison. Never grants manual verification or transcribes."""
from __future__ import annotations
import copy
import difflib
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
import re
import unicodedata

HIGH = 'AUTO_ALIGNED_HIGH'
MEDIUM = 'AUTO_ALIGNED_MEDIUM'
UNRESOLVED = 'UNRESOLVED'
ALGORITHM = 'dual-v1'


def tokens(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    return re.findall(r'[^\W_]+', text, re.UNICODE)


class WordIndex:
    def __init__(self, words, duration):
        self.words, self.ts, self.refs, self.positions = words, [], [], {}
        self.duration = duration
        for i, w in enumerate(words):
            if not (math.isfinite(w['start']) and math.isfinite(w['end']) and 0 <= w['start'] < w['end'] <= duration):
                continue
            for t in tokens(w.get('text', w.get('word', ''))):
                self.positions.setdefault(t, []).append(len(self.ts))
                self.ts.append(t)
                self.refs.append(i)

    def locate(self, text, hint=None, after=None, following=None):
        q = tokens(text)
        if not q:
            return {'confidence': UNRESOLVED, 'reason': 'Texto vacío', 'attempts': []}
        # Full query is context; both endpoints must match exactly, even on retry.
        candidates = []
        starts = self.positions.get(q[0], [])
        for pass_no, radius in ((1, 30), (2, float('inf'))):
            for a in starts:
                first = self.words[self.refs[a]]
                if after is not None and first['start'] < after - .001:
                    continue
                if hint is not None and abs(first['start'] - hint) > radius:
                    continue
                lengths = [len(q)] if pass_no == 1 else range(max(1, len(q)-max(2, len(q)//8)), len(q)+max(3, len(q)//8)+1)
                for n in lengths:
                    b = a+n-1
                    if b >= len(self.ts) or self.ts[b] != q[-1]:
                        continue
                    # Never cut part of a multi-token word/timestamp.
                    if a and self.refs[a-1] == self.refs[a] or b+1 < len(self.ts) and self.refs[b+1] == self.refs[b]:
                        continue
                    actual = self.ts[a:b+1]
                    score = difflib.SequenceMatcher(None, q, actual, autojunk=False).ratio()
                    last = self.words[self.refs[b]]
                    span = last['end']-first['start']
                    sequence = self.words[self.refs[a]:self.refs[b]+1]
                    ordered = all(x['start'] <= y['start'] and x['end'] <= y['end'] for x,y in zip(sequence,sequence[1:]))
                    # Reject pathological pauses or impossible reading rates.
                    if not ordered or span <= 0 or span > max(12, len(q)*1.8) or len(q)/span > 12:
                        continue
                    boundary = min(3, len(q))
                    anchored = q[:boundary] == actual[:boundary] and q[-boundary:] == actual[-boundary:]
                    high = score >= .96 and anchored and (len(q) >= 5 or score == 1)
                    if score >= .75:
                        candidates.append({'start': first['start'], 'end': last['end'], 'score': score,
                            'high': high, 'distance': abs(first['start']-hint) if hint is not None else 0,
                            'firstWord': first['text'], 'lastWord': last['text'], 'lastIndex': self.refs[b], 'pass': pass_no})
            unique = {(c['start'], c['end']): c for c in candidates}
            context = tokens(following or '') if pass_no == 2 else []
            for candidate in unique.values():
                candidate['contextMatch'] = False
                if context:
                    end_index = candidate['lastIndex']
                    for j in self.positions.get(context[0],[]):
                        if self.refs[j] > end_index and self.words[self.refs[j]]['start']-candidate['end'] <= 60 and self.ts[j:j+len(context)] == context:
                            candidate['contextMatch'] = True
                            break
            ranked = sorted(unique.values(), key=lambda c: (-c['high'], -c['score'], -c['contextMatch'], c['distance']))
            if ranked and ranked[0]['high']:
                best = ranked[0]
                rivals = [c for c in ranked[1:] if c['score'] >= best['score']-.015 and c['high'] and
                          c['contextMatch']==best['contextMatch'] and (hint is None or abs(c['distance']-best['distance']) < 1)]
                if not rivals:
                    return {**best, 'confidence': HIGH, 'attempts': list(range(1,pass_no+1))}
            # Second pass searches the whole master with the complete query.
        return {'confidence': MEDIUM if candidates else UNRESOLVED,
                'reason': 'Correspondencia parcial o repetida sin contexto suficiente' if candidates else 'Texto no localizado con extremos fiables',
                'attempts': [1, 2], 'candidates': ranked[:3] if candidates else []}


def compare(clip, index, tolerance=.15):
    segments = clip.get('alignment') or clip.get('editorialSegments')
    if not segments:
        # Edited padded blocks cannot prove the original imported intervals.
        return {'id': clip.get('origin', clip['id']), 'title': clip['title'], 'status': 'ALIGNMENT_UNRESOLVED',
                'confidence': UNRESOLVED, 'editorial': [], 'wordAligned': [], 'segments': [],
                'warnings': ['Sin referencia editorial original; no se deducen tiempos de bloques editados.'], 'variants': []}
    editorial, aligned, details, warnings = [], [], [], []
    complete = True
    for seg in sorted(segments, key=lambda s: s.get('order', 0)):
        start, end = seg.get('start'), seg.get('end')
        valid = isinstance(start,(float,int)) and isinstance(end,(float,int)) and math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= index.duration
        if valid:
            word_count = len(tokens(seg.get('text','')))
            if end-start > max(12,word_count*1.8) or end-start < .08 or word_count/(end-start) > 12:
                warnings.append(f"{seg.get('id','')}: duración editorial anómala respecto al texto; se conserva la referencia original")
            editorial.append({'start': start, 'end': end, 'text': seg.get('text',''), 'role': seg.get('role','SECCION')})
        else:
            warnings.append(f"{seg.get('id','')}: intervalo editorial ausente o fuera del máster")
        parts = re.split(r'\[\s*(?:\.{3}|…)\s*\]', seg.get('text',''))
        after = None
        for part_no,part in enumerate(parts):
            result = index.locate(part, start, after, parts[part_no+1] if part_no+1<len(parts) else None)
            details.append({'segmentId': seg.get('id'), 'text': part, **result})
            if result['confidence'] != HIGH:
                complete = False
                continue
            after = result['end']
            aligned.append({'start':result['start'], 'end':result['end'], 'text':part, 'role':seg.get('role','SECCION'), 'lastIndex':result['lastIndex'], 'segmentId':seg.get('id')})
    if not complete or not details:
        aligned = []  # Never export a partial interpretation of a clip.
    editorial_valid = len(editorial) == len(segments)
    if not editorial_valid:
        editorial = []
    delta = []
    if editorial and aligned:
        for seg,e in zip(sorted(segments,key=lambda s:s.get('order',0)),editorial):
            fragments = [a for a in aligned if a['segmentId']==seg.get('id')]
            a = {'start':fragments[0]['start'], 'end':fragments[-1]['end']}
            delta.append({'startMs': round((a['start']-e['start'])*1000,3), 'endMs':round((a['end']-e['end'])*1000,3),
                          'durationMs':round((sum(f['end']-f['start'] for f in fragments)-(e['end']-e['start']))*1000,3)})
    matched = bool(editorial and aligned and len(editorial)==len(aligned) and all(abs(d['startMs']) <= tolerance*1000 and abs(d['endMs']) <= tolerance*1000 for d in delta))
    status = 'MATCHED' if matched else 'DIFFERENT' if aligned and editorial else 'ALIGNMENT_UNRESOLVED' if not aligned else 'DIFFERENT'
    variants = ['MATCHED'] if matched else (['EDITORIAL'] if editorial else []) + (['WORD_ALIGNED'] if aligned else [])
    confidence = HIGH if aligned else MEDIUM if any(d['confidence']==MEDIUM for d in details) else UNRESOLVED
    return {'id':clip.get('origin',clip['id']), 'title':clip['title'], 'editorialText':'\n'.join(s.get('text','') for s in segments),
            'editorial':editorial, 'editorialOriginal':copy.deepcopy(segments), 'wordAligned':aligned, 'differences':delta,
            'confidence':confidence, 'status':status, 'segments':details, 'variants':variants, 'warnings':warnings,
            'omittedVariants':([{'variant':'WORD_ALIGNED','reason':'No alcanza confianza alta después del segundo intento'}] if not aligned else []) + ([{'variant':'EDITORIAL','reason':'Sin intervalos editoriales completos y válidos'}] if not editorial else []),
            'editorialDurationSeconds':sum(r['end']-r['start'] for r in editorial),
            'wordAlignedDurationSeconds':sum(r['end']-r['start'] for r in aligned)}


def export_blocks(ranges, index, padding, aligned=False, offset=0):
    blocks = []
    for i,r in enumerate(ranges):
        start, end = max(0,r['start']+offset-padding), min(index.duration,r['end']+offset+padding)
        if aligned:
            # Keep requested margin only while it does not include later dialogue.
            next_words = index.words[r['lastIndex']+1:]
            if next_words:
                end = min(end, max(r['end']+offset, next_words[0]['start']+offset))
        if start < 0 or end > index.duration or end <= start:
            raise ValueError('Límite de exportación inválido')
        blocks.append({'uid':f'auto-{i}', 'start':start, 'end':end, 'text':r['text'], 'role':r['role']})
    return blocks


def run(req, stage):
    root = stage.root_for(req)
    tolerance, padding = stage.finite(req.get('tolerance',.15)), stage.finite(req.get('padding',.2))
    if not 0 <= tolerance <= 2 or not 0 <= padding <= 2:
        raise ValueError('Tolerancia y margen deben estar entre 0 y 2 segundos')
    db = stage.load_db(root)
    requested = set(req.get('ids', []))
    selected = [c for c in db['clips'] if c['id'] in requested]
    # Old imports may contain two variants of the same editorial clip: one comparison per format/source.
    grouped = {}
    for c in selected:
        key = json.dumps([c.get('origin',c['id']),c['source']['sampleHash'],c.get('outputOrientation'),c.get('format'),c.get('alignment')],sort_keys=True)
        grouped.setdefault(key,c)
    report = {'schemaVersion':1, 'algorithm':ALGORITHM, 'toleranceSeconds':tolerance, 'paddingSeconds':padding,
              'manualVerification':False, 'status':'running', 'mode':'compare_auto', 'clips':[], 'completed':[], 'failed':[], 'verification':'Text alignment only; no direct audio or manual verification'}
    folder_name = req.get('comparisonFolderName', 'POCATERRA_66_CORTES' if (root/'VIDEOS'/'POCATERRA_66_CORTES').is_dir() else 'COMPARACION_AUTOMATICA')
    if not isinstance(folder_name,str) or not re.fullmatch(r'[\w -]{1,100}',folder_name):
        raise ValueError('Nombre de carpeta de comparación inválido')
    folder = root/'VIDEOS'/folder_name
    report_path = folder/'COMPARACION_CORTES.json'
    report['reportPath']=str(report_path)
    report['outputFolder']=str(folder)
    def publish_report():
        stage.atomic_json(report_path,report)
        if not req.get('dryRun'):
            stage.atomic_json(root/'EDICIONES'/'COLA_EXPORTACION.json',{
                'requestId':stage.REQUEST_ID, 'ids':list(dict.fromkeys(req.get('ids',[]))),
                'mode':'compare_auto', 'status':report['status'], 'completed':report['completed'],
                'failed':report['failed'], 'reportPath':str(report_path)})
    indices = {}
    narrative_order = {}
    for c in db['clips']:
        if len(c.get('alignment',[]))==1:
            narrative_order.setdefault(c.get('origin',c['id']),len(narrative_order)+1)
    intro_order_verified = False
    for intro in db['clips']:
        segments = intro.get('alignment',[])
        if len(segments)<2:
            continue
        mapping = {}
        for position,segment in enumerate(sorted(segments,key=lambda s:s.get('order',0)),1):
            hits = {c.get('origin',c['id']) for c in db['clips'] if c['source']['sampleHash']==intro['source']['sampleHash'] and
                    len(c.get('alignment',[]))==1 and all(c['alignment'][0].get(k)==segment.get(k) for k in ('text','start','end'))}
            if len(hits)!=1:
                break
            mapping[next(iter(hits))]=position
        if len(mapping)==len(segments):
            narrative_order.update(mapping)
            intro_order_verified=True
    report['introOrderVerified']=intro_order_verified
    for c in grouped.values():
        narrative_order.setdefault(c.get('origin',c['id']),len(narrative_order)+1)
    for missing in sorted(requested-{c['id'] for c in selected}):
        report['clips'].append({'id':missing,'status':'ALIGNMENT_UNRESOLVED','confidence':UNRESOLVED,'files':[],'errors':['Ficha no encontrada']})
        report['failed'].append({'id':missing,'error':'Ficha no encontrada'})
    try:
        for number,c in enumerate(grouped.values()):
            row = {'id':c.get('origin',c['id']), 'title':c['title'], 'clipId':c['id'], 'order':narrative_order.get(c.get('origin',c['id']),c.get('editorialOrder',number+1)), 'orientation':c.get('outputOrientation'), 'files':[], 'errors':[]}
            report['clips'].append(row)
            try:
                stage.event('clip_start', id=c['id'],title=c['title'],index=number+1,total=len(grouped))
                if not stage.same_source(c['source'],stage.source_identity(c['source']['path'])):
                    raise ValueError('El master cambió; transcripción no validada para esta fuente')
                duration = stage.media_info(c['source']['path'])['duration']
                key = (c.get('transcript'),duration)
                if key not in indices:
                    indices[key] = WordIndex(stage.normalized_words(c.get('transcript')),duration)
                index = indices[key]
                result = compare(c,index,tolerance)
                row.update(result)
                offset = float(c.get('sourceOffset',0))
                if offset:
                    raise ValueError('Comparación con desfase entre masters requiere transcripción del master seleccionado')
                previous = c.get('comparisonExports',[])
                for variant in result['variants']:
                    try:
                        ranges = result['editorial'] if variant=='EDITORIAL' else result['wordAligned']
                        recipe = {**copy.deepcopy(c), 'variant':variant, 'blocks':export_blocks(ranges,index,padding,variant!='EDITORIAL'),
                                  'comparisonVariant':True, 'comparisonOrder':row['order'], 'textVerified':False, 'boundariesReviewed':False}
                        signature = stage.recipe_signature(recipe)
                        if variant!='EDITORIAL' and any(b['end'] < min(index.duration,r['end']+padding)-.001 for b,r in zip(recipe['blocks'],ranges)):
                            row['warnings'].append(f'{variant}: margen final reducido para excluir la siguiente palabra')
                        destination = folder
                        recipe['comparisonFolder'] = str(destination)
                        saved = next((e for e in previous if e['signature']==signature and Path(e['path']).is_file()),None)
                        # Reuse valid strict-mode exports too; verify the MP4 before trusting a sidecar.
                        if saved is None:
                            for other in db['clips']:
                                for e in [other.get('export') or {},*other.get('exportHistory',[])]:
                                    if e.get('signature')==signature and Path(e.get('path','')).is_file():
                                        saved=e; break
                        reused = False
                        if saved:
                            expected = sum(b['end']-b['start'] for b in recipe['blocks'])
                            try:
                                reused = abs(stage.media_info(saved['path'])['duration']-expected) <= max(.3,len(recipe['blocks'])*.08)
                            except Exception:
                                reused = False
                        if req.get('dryRun'):
                            row['files'].append({'variant':variant,'decision':'REUSE' if reused else 'EXPORT','signature':signature,'blocks':recipe['blocks']})
                            continue
                        if not reused:
                            path = stage.export_one(root,recipe,number,len(grouped))
                            saved = {'path':str(path),'signature':signature}
                        if reused:
                            destination.mkdir(parents=True,exist_ok=True)
                            original = Path(saved['path'])
                            target = destination/stage.comparison_filename(recipe,signature)
                            if original.resolve()!=target.resolve():
                                if not target.exists():
                                    try:
                                        os.link(original,target)
                                    except OSError:
                                        shutil.copy2(original,target)
                                for suffix in ('.srt','.ass'):
                                    sidecar=original.with_suffix(suffix)
                                    if sidecar.is_file() and not target.with_suffix(suffix).exists():
                                        shutil.copy2(sidecar,target.with_suffix(suffix))
                                stage.atomic_json(target.with_suffix('.json'),{'recipe':recipe,'signature':signature,'reusedFrom':str(original),
                                    'manualVerification':False,'words':stage.virtual_words(index.words,recipe['blocks'])})
                                target.with_suffix('.txt').write_text('ABRXS-CANTER · COMPARACIÓN AUTOMÁTICA\n'+json.dumps({'variant':variant,'manualVerification':False,'blocks':recipe['blocks']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                                saved={**saved,'path':str(target)}
                        entry = {**saved,'variant':variant,'reused':reused,'blocks':recipe['blocks']}
                        row['files'].append(entry)
                        latest = stage.load_db(root)
                        for target in latest['clips']:
                            if target['id']==c['id']:
                                exports = target.setdefault('comparisonExports',[])
                                if not any(e.get('path')==entry['path'] and e.get('variant')==variant for e in exports):
                                    exports.append({k:v for k,v in entry.items() if k!='blocks'})
                        stage.atomic_json(stage.db_path(root),latest)
                    except Exception as exc:
                        row['errors'].append(f'{variant}: {exc}')
                if not result['variants']:
                    row['errors'].append('No hay ninguna referencia exportable')
                if row['errors']:
                    report['failed'].append({'id':c['id'],'error':'; '.join(row['errors'])})
                else:
                    report['completed'].append(c['id'])
            except Exception as exc:
                row['errors'].append(str(exc)); report['failed'].append({'id':c['id'],'error':str(exc)})
            publish_report()
        report['clips'].sort(key=lambda c:(c.get('order',0),c.get('orientation') or ''))
        report['status'] = 'finished'
    finally:
        if report['status']=='running':
            report['status']='interrupted'
        publish_report()
    return report


def import_pieces(req, stage, engine, data, pieces):
    """One card per editorial piece/source. No alignment approval is granted on import."""
    import dataclasses
    root = stage.root_for(req)
    db = stage.load_db(root)
    target_ids, warnings = [], []
    index = WordIndex(data['words'],data['media']['duration'])
    orientation = req.get('_masterOrientation','')
    for order,piece in enumerate(pieces,1):
        if not piece.selected or piece.kind.lower() not in {'video','intro','vertical','horizontal','clip','reel'}:
            continue
        if req.get('_pieceIds') is not None and piece.id not in req['_pieceIds']:
            continue
        segments = [dataclasses.asdict(s) for s in piece.segments]
        def editorial_identity(items):
            return [{k:s.get(k) for k in ('id','order','role','text','start','end')} for s in items]
        existing = next((c for c in db['clips'] if c.get('origin')==piece.id and
                         c['source']['sampleHash']==data['source']['sampleHash'] and
                         c.get('outputOrientation','')==orientation and
                         editorial_identity(c.get('alignment',[]))==editorial_identity(segments)),None)
        if existing:
            target_ids.append(existing['id']); continue
        uid = hashlib.sha256(json.dumps([data['source']['sampleHash'],piece.id,orientation,editorial_identity(segments)],sort_keys=True).encode()).hexdigest()[:24]
        c = {'id':uid,'revision':1,'title':piece.title,'origin':piece.id,'variant':'AUTO_COMPARISON',
             'source':data['source'],'transcript':data['transcript'],'duration':index.duration,'blocks':[],
             'status':'review','note':'','textVerified':False,'alignment':segments,'editorialOrder':order,
             'format':{'aspect':'original','mode':'contain','x':.5,'y':.5}}
        if orientation:
            c['outputOrientation']=orientation; c['sourceOffset']=float(req.get('_masterOffset',0))
            c['title']+=' · '+orientation.title()
        result = compare(c,index)
        ranges = result['editorial'] or result['wordAligned']
        if ranges:
            c['blocks']=export_blocks(ranges,index,.2,not result['editorial'])
        else:
            warnings.append(f'{piece.id}: sin límites exportables; el lote registrará el motivo.')
        stage.mark_export(c)
        db['clips'].append(c);target_ids.append(uid)
    if not req.get('_dryRun'):
        stage.atomic_json(stage.db_path(root),db)
    return {'clips':db['clips'],'targetIds':target_ids,'warnings':warnings}
