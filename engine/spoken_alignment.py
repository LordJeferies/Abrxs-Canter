"""Word-timed alignment of oral editorial text, retaining every source timestamp.

Matching may normalize repeated text, spelled numbers and explicit project aliases.
The audio is never synthesized or normalized. This does not grant VERIFIED.
"""
import difflib
import math
from collections import defaultdict
import auto_compare


def canonical(text, aliases=None, collapse=False):
    aliases = aliases or {}
    values = [aliases.get(t,t) for t in auto_compare.tokens(text)]
    if collapse:
        for width in (3,2,1):
            i=0
            while i+2*width<=len(values):
                if values[i:i+width]==values[i+width:i+2*width]:
                    del values[i+width:i+2*width]
                else:
                    i+=1
        # A restarted short utterance ("es la es") remains audible in the source.
        if len(values)>3 and values[0]==values[2] and values[1] in {'la','el','eh'}:
            values=values[2:]
    return values


class SpokenIndex:
    def __init__(self, words, duration, aliases=None):
        self.words=[dict(w) for w in words]
        self.duration=duration
        self.aliases=aliases or {}
        self.tokens=[];self.refs=[];self.positions=defaultdict(list);self.repairs=[]
        for i,w in enumerate(self.words):
            start,end=w['start'],w['end']
            if not (math.isfinite(start) and math.isfinite(end) and 0<=start<=end<=duration):
                raise ValueError('Transcripción con tiempos inválidos')
            if start==end:
                w['end']=min(duration,start+.001)
                self.repairs.append({'wordIndex':i,'text':w['text'],'start':start,'originalEnd':end,'end':w['end']})
            for token in canonical(w['text'],self.aliases):
                self.positions[token].append(len(self.tokens));self.tokens.append(token);self.refs.append(i)

    def locate(self,text,hint=None):
        variants=[canonical(text,self.aliases,False),canonical(text,self.aliases,True)]
        results=[self._locate_query(query,hint) for query in variants]
        high=[r for r in results if r['confidence']=='AUTO_ALIGNED_HIGH']
        if high:
            return max(high,key=lambda r:(r['score'],-r['distance']))
        return results[0]

    def _locate_query(self,query,hint=None):
        if not query:
            return {'confidence':'UNRESOLVED','reason':'Texto vacío'}
        candidates=[]
        for start in self.positions.get(query[0],[]):
            if start and self.refs[start-1]==self.refs[start]:continue
            delta=max(4,len(query)//4)
            for size in range(max(1,len(query)-delta),len(query)+delta+1):
                stop=start+size
                if stop>len(self.tokens) or self.tokens[stop-1]!=query[-1]:continue
                if stop<len(self.tokens) and self.refs[stop]==self.refs[stop-1]:continue
                actual=self.tokens[start:stop]
                matcher=difflib.SequenceMatcher(None,query,actual,autojunk=False)
                score=matcher.ratio()
                matched=sum(m.size for m in matcher.get_matching_blocks())
                coverage=matched/len(query)
                boundary=min(3,len(query))
                head=sum(b.size for b in difflib.SequenceMatcher(None,query[:boundary],actual[:boundary],autojunk=False).get_matching_blocks())
                tail=sum(b.size for b in difflib.SequenceMatcher(None,query[-boundary:],actual[-boundary:],autojunk=False).get_matching_blocks())
                first,last=self.refs[start],self.refs[stop-1]
                a,b=self.words[first]['start'],self.words[last]['end']
                collapsed_times=any(r['wordIndex']>=first and r['wordIndex']<=last for r in self.repairs)
                if b<=a or b-a>max(12,len(query)*1.8) or (len(query)/(b-a)>14 and not collapsed_times):continue
                # Source-only stretches of unrelated dialogue must become separate cuts.
                extra=[]
                for op,i,j,k,l in matcher.get_opcodes():
                    if op=='insert':extra.extend(actual[k:l])
                unrelated=[t for t in extra if t not in query and t not in {'a','en','un','una','de','eh','el','la'}]
                high=(score>=.85 and coverage>=.85 and head>=min(2,boundary) and tail>=min(2,boundary) and not unrelated)
                if len(query)<5:high=score==1
                if score>=.65:
                    candidates.append({'start':a,'end':b,'score':score,'coverage':coverage,'high':high,
                        'firstIndex':first,'lastIndex':last,'distance':abs(a-hint) if hint is not None else 0,
                        'transcriptText':' '.join(w['text'] for w in self.words[first:last+1]),
                        'differences':[{'type':op,'requested':query[i:j],'transcript':actual[k:l]} for op,i,j,k,l in matcher.get_opcodes() if op!='equal']})
        unique={(c['start'],c['end']):c for c in candidates}
        ranked=sorted(unique.values(),key=lambda c:(-c['high'],-c['score'],c['distance']))
        if ranked and ranked[0]['high']:
            top=ranked[0]
            rivals=[c for c in ranked[1:] if c['high'] and c['score']>=top['score']-.015 and
                    abs(c['start']-top['start'])>1 and (hint is None or abs(c['distance']-top['distance'])<1)]
            if not rivals:
                return {**top,'confidence':'AUTO_ALIGNED_HIGH','method':'ORAL_TEXT_NORMALIZATION',
                    'timingConfidence':'COLLAPSED_WORD_TIMES' if any(top['firstIndex']<=r['wordIndex']<=top['lastIndex'] for r in self.repairs) else 'WORD_TIMED',
                    'zeroDurationRepairs':[r for r in self.repairs if top['firstIndex']<=r['wordIndex']<=top['lastIndex']]}
        return {'confidence':'UNRESOLVED','reason':'Coincidencia ausente, parcial o ambigua','candidates':ranked[:3]}

    def blocks(self,ranges,padding=.2):
        blocks=[]
        for n,r in enumerate(ranges):
            start=r['start'];end=r['end']
            # Margins cannot include the preceding or following spoken word.
            previous=self.words[r['firstIndex']-1]['end'] if r['firstIndex'] else 0
            start=max(0,previous,start-padding)
            following=self.words[r['lastIndex']+1]['start'] if r['lastIndex']+1<len(self.words) else self.duration
            end=min(self.duration,max(end,min(following,end+padding)))
            blocks.append({'uid':f'word-{n}','start':start,'end':end,'text':r['text'],'role':r.get('role','SECCION')})
        return blocks
