/* UX 3.6.2: layout only. Keep editing and export in the existing engine. */
(()=>{
  const $=id=>document.getElementById(id),studio=$('ac-studio');
  const inspector=$('ac-inspector'),blocks=$('ac-blocks');
  const precision=document.createElement('details');precision.className='ac-precision';precision.innerHTML='<summary>Más ajustes · precisión y formato</summary>';
  [...inspector.children].slice(2).forEach(n=>precision.append(n));inspector.append(precision);
  blocks.before(inspector);
  $('ac-in').closest('label').firstChild.textContent='Inicio del bloque · máster ';
  $('ac-out').closest('label').firstChild.textContent='Final del bloque · máster ';
  $('ac-montage-mode').textContent='Secuencia de clips';$('ac-origin-mode').textContent='Detalle del máster';$('ac-full').textContent='Máster completo';$('ac-fit').textContent='Ver todo';
  const help=studio.querySelector('.ac-timeline-help');help.textContent='Selecciona un bloque para editarlo. Ordena con ↑ ↓. Arrastra sus extremos o ajusta Inicio y Final. El original no cambia.';
  const tools=document.createElement('div');tools.className='ac-actions ac-simple-tools';
  for(const[id,label]of [['ac-play','▶ Reproducir montaje'],['ac-undo','↶ Deshacer'],['ac-split','Dividir aquí']]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>$ (id).click();tools.append(b);}
  $('ac-timeline').querySelector('.ac-timeline-top').before(tools);
  studio.addEventListener('error',e=>{
    const img=e.target;if(img.tagName!=='IMG')return;
    if(img.closest('.ac-filmstrip')){img.remove();return;}
    if(img.closest('.ac-card')){const fallback=document.createElement('div');fallback.className='ac-thumb-placeholder';fallback.textContent='Miniatura no disponible · regénérala desde el editor';img.replaceWith(fallback);}
  },true);
  const subtitle=document.querySelector('.ux-brand small');if(subtitle)subtitle.textContent='ESTUDIO · 3.8';
  document.title='Abrxs-Canter · Estudio 3.8.1';document.querySelectorAll('.topbar .brand p,footer>span:first-child').forEach(n=>n.textContent='Abrxs-Canter · Estudio 3.8.1');
  const option=document.querySelector('#batch-method option[value="preferred"]');if(option)option.textContent='Una ficha por corte · preferir texto verificado';
})();
