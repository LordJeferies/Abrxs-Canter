/* Funciones puras compartidas por el editor y sus pruebas. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AbrxsEdit = api;
})(globalThis, function () {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  const uid = () => globalThis.crypto?.randomUUID?.() || `b-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const duration = blocks => blocks.reduce((sum, b) => sum + b.end - b.start, 0);
  function validate(blocks, sourceDuration) {
    if (!Number.isFinite(sourceDuration) || sourceDuration <= 0) throw Error('Duración de fuente no válida.');
    if (!Array.isArray(blocks) || !blocks.length) throw Error('Añade al menos un bloque.');
    const ids = new Set();
    return blocks.map(b => {
      const start = Number(b.start), end = Number(b.end);
      if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || end > sourceDuration + .001) throw Error('Bloque vacío o fuera del máster.');
      let id = b.uid || uid();
      if (ids.has(id)) id = uid();
      ids.add(id);
      return {...b, uid:id, start, end:Math.min(end, sourceDuration)};
    });
  }
  function toSource(blocks, t) {
    if (!Number.isFinite(t) || t < 0 || !blocks.length) return null;
    let offset = 0;
    for (let i=0; i<blocks.length; i++) {
      const b=blocks[i], length=b.end-b.start;
      if (t < offset+length || (i===blocks.length-1 && t<=offset+length)) return {index:i, uid:b.uid, time:b.start+t-offset};
      offset+=length;
    }
    return null;
  }
  function toMontage(blocks, index, sourceTime) {
    if (!blocks[index] || !Number.isFinite(sourceTime)) return null;
    const b=blocks[index];
    return duration(blocks.slice(0,index))+Math.max(0,Math.min(b.end-b.start, sourceTime-b.start));
  }
  function virtualWords(words, blocks) {
    let offset=0; const result=[];
    for (const b of blocks) {
      for (const w of words) {
        if (w.end<=b.start || w.start>=b.end) continue;
        result.push({...w, sourceStart:w.start, sourceEnd:w.end, blockUid:b.uid,
          start:offset+Math.max(0,w.start-b.start), end:offset+Math.min(b.end-b.start,w.end-b.start)});
      }
      offset+=b.end-b.start;
    }
    return result;
  }
  function merge(blocks, i) {
    const a=blocks[i], b=blocks[i+1];
    // Solo unir rangos exactamente consecutivos en orden de origen.
    if (!a || !b || Math.abs(a.end-b.start)>.001) throw Error('Solo se pueden unir bloques consecutivos en el máster. Los demás ya se concatenan al exportar.');
    const result=clone(blocks);
    result.splice(i,2,{...a,end:b.end,text:`${a.text||''} ${b.text||''}`.trim()});
    return result;
  }
  function cropBox(width,height,aspect,x=.5,y=.5) {
    if (aspect==='original') return {x:0,y:0,width,height};
    const [a,b]=aspect.split(':').map(Number), ratio=a/b;
    const w=width/height>ratio?Math.floor(height*ratio/2)*2:Math.floor(width/2)*2;
    const h=width/height>ratio?Math.floor(height/2)*2:Math.floor(width/ratio/2)*2;
    return {x:Math.floor((width-w)*Math.max(0,Math.min(1,x))/2)*2,
      y:Math.floor((height-h)*Math.max(0,Math.min(1,y))/2)*2,width:w,height:h};
  }
  function token(value) { return String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(); }
  return {clone,uid,duration,validate,toSource,toMontage,virtualWords,merge,cropBox,token};
});
