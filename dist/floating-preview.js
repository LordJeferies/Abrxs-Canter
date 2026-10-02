/* One existing video element, docked in List or floating over Map/Kanban. */
(() => {
  'use strict';
  window.AbrxsFloatingPreview={mount({dock,layout,toolbar,video,getView}){
    let dismissed=false,collapsed=false,preference=null,drag=null;
    const header=document.createElement('header');header.className='ac-viewer-header';
    const grip=document.createElement('button');grip.type='button';grip.className='ac-viewer-grip';grip.textContent='⋮⋮ Visor';grip.title='Arrastra para mover. Con foco, usa las flechas.';grip.setAttribute('aria-label','Mover ventana del visor');
    const body=document.createElement('div');body.className='ac-viewer-body';while(dock.firstChild)body.append(dock.firstChild);
    const make=(label,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=fn;return b;};
    const float=make('Acoplar',()=>{preference=!isFloating();sync(!reopen.disabled);});
    const fold=make('Plegar',()=>{collapsed=!collapsed;if(collapsed)video.pause();paintFold();});
    const close=make('Cerrar',()=>{dismissed=true;video.pause();sync(!reopen.disabled);});
    header.append(grip,float,fold,close);dock.append(header,body);dock.setAttribute('aria-label','Visor de la ficha seleccionada');
    const reopen=make('Mostrar visor',()=>{dismissed=false;collapsed=false;paintFold();sync(true);grip.focus?.();});reopen.id='ac-show-viewer';reopen.disabled=true;toolbar.append(reopen);
    const isFloating=()=>preference===null?['map','kanban'].includes(getView()):preference;
    function paintFold(){body.hidden=collapsed;dock.classList.toggle('is-collapsed',collapsed);fold.textContent=collapsed?'Desplegar':'Plegar';fold.setAttribute('aria-expanded',String(!collapsed));}
    function sync(available){reopen.disabled=!available;const visible=available&&!dismissed,floating=isFloating();dock.hidden=!visible;dock.classList.toggle('is-floating',floating);layout.classList.toggle('floating-preview',floating&&visible);layout.classList.toggle('with-preview',!floating&&visible);float.textContent=floating?'Acoplar':'Flotar';grip.title=floating?'Arrastra para mover. Con foco, usa las flechas.':'Pulsa Flotar para mover el visor.';reopen.textContent=visible?'Visor abierto':'Mostrar visor';reopen.setAttribute('aria-expanded',String(visible));paintFold();if(visible&&floating)clamp();}
    function position(x,y){const rect=dock.getBoundingClientRect();dock.style.left=Math.max(8,Math.min(x,window.innerWidth-rect.width-8))+'px';dock.style.top=Math.max(8,Math.min(y,window.innerHeight-rect.height-8))+'px';dock.style.right='auto';dock.style.bottom='auto';}
    function clamp(){if(dock.style.left){const r=dock.getBoundingClientRect();position(r.left,r.top);}}
    grip.onpointerdown=e=>{if(!isFloating()||e.button!==0)return;const r=dock.getBoundingClientRect();drag={id:e.pointerId,x:e.clientX,y:e.clientY,left:r.left,top:r.top};grip.setPointerCapture?.(e.pointerId);e.preventDefault();};
    grip.onpointermove=e=>{if(drag&&drag.id===e.pointerId)position(drag.left+e.clientX-drag.x,drag.top+e.clientY-drag.y);};
    grip.onpointerup=grip.onpointercancel=()=>{drag=null;};
    grip.onkeydown=e=>{if(!isFloating()||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();const r=dock.getBoundingClientRect(),step=e.shiftKey?40:10;position(r.left+(e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0),r.top+(e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0));};
    dock.addEventListener('keydown',e=>{if(e.key==='Escape'){dismissed=true;video.pause();sync(!reopen.disabled);reopen.focus?.();e.stopPropagation();}});
    window.addEventListener('resize',clamp);
    return {sync,show(){dismissed=false;collapsed=false;sync(true);},reset(){dismissed=false;collapsed=false;preference=null;drag=null;for(const p of ['left','top','right','bottom','width','height'])dock.style.removeProperty(p);sync(false);}};
  }};
})();
