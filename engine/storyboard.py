"""Canter storyboard export: one word-aligned paragraph or timed gap per file."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from spoken_alignment import SpokenIndex


def fingerprint(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def gap(stage,root,folder,item,media,orientation,position,total,cache,progress_offset=0):
    duration=stage.finite(item['duration'])
    if not 0<duration<=600:raise ValueError('Duración de negro inválida')
    key=fingerprint([duration,media['width'],media['height'],30,'silent-h264-v1'])
    label='NEGRO_2s' if item['type']=='black' else item['text'].replace(' ','_')+'_RESERVA_10s'
    final=folder/f'{position:03d}_{label}_{orientation}_{key[:12]}.mp4'
    reused=final.is_file()
    if not reused:
        original=cache.get(key)
        if original and original.is_file():
            os.link(original,final);reused=True
        else:
            partial=final.with_suffix('.partial.mp4')
            try:
                for codec in ('h264_videotoolbox','libx264'):
                    args=[stage.command('ffmpeg'),'-v','error','-y','-f','lavfi','-i',f"color=c=black:s={media['width']}x{media['height']}:r=30",'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',str(duration),'-map','0:v:0','-map','1:a:0','-c:v',codec,'-b:v','40M','-pix_fmt','yuv420p']
                    if codec=='h264_videotoolbox':args+=['-allow_sw','1']
                    args+=['-c:a','aac','-b:a','192k','-movflags','+faststart',str(partial)]
                    try:
                        stage.render_section(args,duration,label,position-1+progress_offset,total,0,1);break
                    except RuntimeError:
                        if codec=='libx264':raise
                check=stage.media_info(partial)
                if abs(check['duration']-duration)>.1:raise ValueError('Duración del negro incorrecta')
                os.replace(partial,final)
            finally:partial.unlink(missing_ok=True)
    cache[key]=final
    return {'path':str(final),'signature':key,'reused':reused,'duration':duration,'kind':item['type'],
            'hasVoiceAudio':False,'voiceStatus':'PENDING_AUDIO' if item['type']=='voiceover' else None}


def export(req,stage):
    root=stage.root_for(req)
    plan=stage.read_json(req['storyboardPath'])
    if plan.get('schemaVersion')!=1 or not isinstance(plan.get('items'),list):raise ValueError('Storyboard no compatible')
    padding=stage.finite(req.get('padding',.2))
    if not 0<=padding<=2:raise ValueError('Margen inválido')
    sources=plan['sources']
    if set(sources)!={'horizontal','vertical'}:raise ValueError('Se requieren los dos masters')
    media={}
    for orientation,source in sources.items():
        if not stage.same_source(source,stage.source_identity(source['path'])):raise ValueError('El master cambió')
        media[orientation]=stage.media_info(source['path'])
        if (media[orientation]['height']>media[orientation]['width']) != (orientation=='vertical'):raise ValueError('Orientación de master incorrecta')
    if abs(media['horizontal']['duration']-media['vertical']['duration'])>.1:raise ValueError('Masters con líneas temporales distintas')
    words=stage.normalized_words(plan['transcript'])
    if not words:raise ValueError('Se requiere transcripción existente palabra por palabra')
    index=SpokenIndex(words,media['horizontal']['duration'],plan.get('aliases'))
    items=plan['items']
    if [i['order'] for i in items]!=list(range(1,len(items)+1)):raise ValueError('Orden de storyboard incompleto')
    # Re-align from textual fragments. Prepared timestamps are search hints only.
    aligned={};alignment_errors={}
    for item in items:
        if item['type']=='speech':
            found=[]
            for fragment in item['matches']:
                r=index.locate(fragment['text'],fragment.get('start'))
                if r['confidence']!='AUTO_ALIGNED_HIGH':
                    alignment_errors[item['id']]=f"{item['id']}: texto no localizado con confianza suficiente"
                    break
                found.append({**r,'text':fragment['text'],'role':fragment.get('role','SECCION')})
            aligned[item['id']]=found
        elif item['type'] not in {'black','voiceover'}:raise ValueError('Elemento de storyboard desconocido')
    db=stage.load_db(root)
    known={}
    for candidate_root in [root,*map(Path,req.get('reuseProjects',[]))]:
        for c in stage.load_db(candidate_root)['clips']:
            for e in [c.get('export') or {},*c.get('exportHistory',[]),*c.get('comparisonExports',[])]:
                if e.get('signature') and Path(e.get('path','')).is_file():known.setdefault(e['signature'],e)
    report={'schemaVersion':1,'mode':'WORD_ALIGNED_STORYBOARD','manualVerification':False,'status':'running',
            'paragraphCount':len(aligned),'blackCount':sum(i['type']=='black' for i in items),'voCount':sum(i['type']=='voiceover' for i in items),
            'sources':sources,'transcript':plan['transcript'],'paddingSeconds':padding,'items':[], 'completed':[],'failed':[],
            'notes':['One file per user paragraph. JSON subclip IDs retained.','VO files are silent black reservations: no voice audio supplied.',
                     'Zero-duration transcript words receive a recorded 1 ms technical repair; this is not audio verification.',
                     'User authorized omitting the unlocated para / mucha gente / pero.','Both consecutive black markers in the user text are preserved.']}
    def publish():
        stage.atomic_json(root/'REPORTE_ALINEACION.json',report)
        stage.atomic_json(root/'EDICIONES/COLA_EXPORTACION.json',{'mode':'storyboard','status':report['status'],
            'completed':report['completed'],'failed':report['failed'],'reportPath':str(root/'REPORTE_ALINEACION.json')})
    cache={}
    try:
        for orientation_number,orientation in enumerate(('horizontal','vertical')):
            folder=root/('HORIZONTALES' if orientation=='horizontal' else 'VERTICALES');folder.mkdir(parents=True,exist_ok=True)
            for item in items:
                entry={'order':item['order'],'type':item['type'],'orientation':orientation,'text':item['text'],'id':item.get('id'),
                       'sourceIds':item.get('sourceIds',[]),'notes':item.get('notes',[]),'files':[],'errors':[]}
                report['items'].append(entry)
                stage.event('clip_start',id=f"{orientation}-{item['order']}",title=orientation+' · '+(item.get('id') or item['text']),index=orientation_number*len(items)+item['order'],total=len(items)*2)
                try:
                    if item['type']!='speech':
                        result=gap(stage,root,folder,item,media[orientation],orientation,item['order'],len(items)*2,cache,orientation_number*len(items))
                    else:
                        if item['id'] in alignment_errors:raise ValueError(alignment_errors[item['id']])
                        ranges=aligned[item['id']]
                        blocks=stage.validate_blocks(index.blocks(ranges,padding),media[orientation]['duration'])
                        uid=fingerprint(['storyboard',item['id'],sources[orientation]['sampleHash'],item['text']])[:24]
                        c={'id':uid,'origin':item['id'],'revision':1,'title':f"{item['order']:03d} · {item['id']} · {orientation}",
                           'source':sources[orientation],'transcript':plan['transcript'],'duration':media[orientation]['duration'],'blocks':blocks,
                           'variant':'WORD_ALIGNED','status':'review','note':'\n'.join(item.get('notes',[])),'textVerified':False,'boundariesReviewed':False,
                           'format':{'aspect':'original','mode':'contain','x':.5,'y':.5},'outputOrientation':orientation,
                           'editorialOrder':item['order'],'wordAlignment':ranges,'sourceEditorialIds':item['sourceIds']}
                        signature=stage.recipe_signature(c)
                        recipe={**copy.deepcopy(c),'comparisonVariant':True,'comparisonOrder':item['order'],'comparisonFolder':str(folder)}
                        final=folder/stage.comparison_filename(recipe,signature)
                        previous=known.get(signature)
                        reused=False
                        expected=sum(b['end']-b['start'] for b in blocks)
                        if previous:
                            try:reused=abs(stage.media_info(previous['path'])['duration']-expected)<=max(.3,len(blocks)*.08)
                            except Exception:pass
                        if reused:
                            if not final.exists():
                                try:os.link(previous['path'],final)
                                except OSError:shutil.copy2(previous['path'],final)
                            stage.atomic_json(final.with_suffix('.json'),{'recipe':recipe,'signature':signature,'reusedFrom':previous['path'],'manualVerification':False,'words':stage.virtual_words(words,blocks)})
                        else:
                            final=stage.export_one(root,recipe,orientation_number*len(items)+item['order']-1,len(items)*2)
                        result={'path':str(final),'signature':signature,'reused':reused,'duration':expected,'blocks':blocks,'kind':'WORD_ALIGNED'}
                        entry['alignment']=ranges
                        c['export']={**result,'revision':1,'createdAt':time.time()};stage.mark_export(c)
                        latest=stage.load_db(root)
                        existing=next((v for v in latest['clips'] if v['id']==uid),None)
                        if existing:
                            # Preserve user edits and only attach the resulting automatic export.
                            existing.setdefault('storyboardExports',[])
                            if not any(v['path']==result['path'] for v in existing['storyboardExports']):existing['storyboardExports'].append(result)
                        else:latest['clips'].append(c)
                        stage.atomic_json(stage.db_path(root),latest)
                        known[signature]=result
                    entry['files'].append(result);report['completed'].append(f"{orientation}-{item['order']}")
                    stage.event('clip_complete',id=f"{orientation}-{item['order']}",path=result['path'],progress=100*len(report['completed'])/(len(items)*2))
                except Exception as exc:
                    entry['errors'].append(str(exc));report['failed'].append({'id':f"{orientation}-{item['order']}",'error':str(exc)})
                publish()
        report['status']='finished'
    finally:
        if report['status']=='running':report['status']='interrupted'
        publish()
    return report
