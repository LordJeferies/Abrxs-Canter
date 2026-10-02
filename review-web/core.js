/* Abrxs Review: time and editorial interchange. No network or dependencies. */
(function(root){
  'use strict';
  function seconds(value){
    if(typeof value==='number' && Number.isFinite(value) && value>=0) return value;
    const s=String(value??'').trim().replace(',','.');
    if(!/^\d+(?::\d{1,2}){0,2}(?:\.\d+)?$/.test(s)) throw Error('Tiempo inválido: '+s);
    const p=s.split(':').map(Number);
    if(p.length>1 && p.slice(1).some(n=>n>=60)) throw Error('Minutos o segundos fuera de rango: '+s);
    return p.reduce((a,n)=>a*60+n,0);
  }
  function stamp(n){
    n=Math.round(seconds(n)*1000);
    return [Math.floor(n/3600000),Math.floor(n/60000)%60,Math.floor(n/1000)%60].map(x=>String(x).padStart(2,'0')).join(':')+'.'+String(n%1000).padStart(3,'0');
  }
  function unit(row){
    const start=seconds(row.start??row.start_time), end=seconds(row.end??row.end_time);
    if(end<=start) throw Error('Un fragmento termina antes de empezar.');
    const text=String(row.word??row.text??'').trim();
    if(!text) throw Error('Hay un fragmento sin texto.');
    return {start,end,text};
  }
  function transcript(raw){
    let rows=[], granularity='frase';
    const text=String(raw).replace(/^\uFEFF/,'').trim();
    if(text.startsWith('{')||(text.startsWith('[')&&!/^\[\s*\d+(?::\d{1,2}){1,2}/.test(text))){
      const data=JSON.parse(text);
      if(Array.isArray(data.words)){ rows=data.words; granularity='palabra'; }
      else if(Array.isArray(data.segments)){
        if(data.segments.length && data.segments.every(x=>Array.isArray(x.words)&&x.words.length)){ rows=data.segments.flatMap(x=>x.words);granularity='palabra'; }
        else rows=data.segments;
      } else if(Array.isArray(data)) { rows=data;granularity=data.every(x=>x.word!=null)?'palabra':'frase'; }
      else throw Error('El JSON necesita words o segments con start, end y texto.');
    } else {
      // SRT/VTT or one-line [start --> end] text. Timing is never invented.
      const pattern=/(\d+(?::\d{1,2}){1,2}[.,]\d+|\d+(?::\d{1,2}){1,2})\s*-->\s*(\d+(?::\d{1,2}){1,2}[.,]\d+|\d+(?::\d{1,2}){1,2})\]?[^\S\n]*(?:\n)?([^]*?)(?=\n\s*\n|\n(?:\[)?\d+(?::\d{1,2}){1,2}[.,]?\d*\s*-->|$)/g;
      let m; while((m=pattern.exec(text))) rows.push({start:m[1],end:m[2],text:m[3].replace(/<[^>]*>/g,'').trim()});
    }
    if(!rows.length) throw Error('No hay tiempos utilizables. Importa JSON words/segments, SRT, VTT o TXT [00:00:10.000 --> 00:00:15.000] texto. Un TXT sin tiempos no permite cortes precisos.');
    const units=rows.map(unit);
    for(let i=1;i<units.length;i++) if(units[i].start<units[i-1].start) throw Error('La transcripción no está ordenada por tiempo.');
    return {units,granularity};
  }
  function editorial(project){
    const clips=project.clips.filter(c=>c.blocks.length).map((c,i)=>({id:'WEB_'+c.id,title:c.title||'Clip '+(i+1),type:'video',selected:true,segments:c.blocks.map((b,j)=>({...unit(b),id:c.id+'_'+j,order:j+1,role:b.role||'BODY'})),voiceovers:[],xrolls:[]}));
    if(!clips.length) throw Error('Añade al menos un bloque a una ficha.');
    return {clips,format:'abrxs-editorial-v1',source:project.source,project:project.name,timebase:'source-seconds',notice:'Seleccionar el mismo máster en la app de Mac. El importador actual puede añadir 0.2 s de margen.'};
  }
  function validateProject(p){
    if(!p||p.format!=='abrxs-review-project-v1'||!Array.isArray(p.clips)||!Array.isArray(p.notes)||!Array.isArray(p.units)) throw Error('No es una copia de proyecto Abrxs Review.');
    if(p.clips.length>500||p.units.length>200000||p.notes.length>10000) throw Error('Proyecto demasiado grande.');
    if(p.reviewFiles!==undefined){if(!Array.isArray(p.reviewFiles)||p.reviewFiles.length>2000)throw Error('Lista de revisión inválida.');p.reviewFiles=p.reviewFiles.filter(f=>f&&typeof f.id==='string'&&/^[\w-]+$/.test(f.id)&&typeof f.name==='string'&&/^(video|image)\//.test(f.mimeType||''));}
    p.units=p.units.map(unit);
    p.clips=p.clips.map(c=>{if(!Array.isArray(c.blocks)) throw Error('Ficha inválida.');return {id:String(c.id),title:String(c.title||'Clip'),blocks:c.blocks.map(b=>({...unit(b),role:String(b.role||'BODY')}))};});
    p.notes=p.notes.map(n=>({...n,start:seconds(n.start),end:seconds(n.end),text:String(n.text||''),source:String(n.source||'')}));
    return p;
  }
  root.AbrxsReview={seconds,stamp,unit,transcript,editorial,validateProject};
  if(typeof module!=='undefined') module.exports=root.AbrxsReview;
})(typeof globalThis!=='undefined'?globalThis:this);
