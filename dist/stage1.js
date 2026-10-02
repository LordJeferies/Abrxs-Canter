/* Etapa uno: editor de recetas sin dependencias de IA ni render de preview. */
(() => {
  'use strict';
  const C=window.AbrxsEdit, api=window.__TAURI__.core, dialog=window.__TAURI__.dialog;
  const esc=s=>escapeHtml(String(s??'')), el=id=>document.getElementById(`ac-${id}`);
  const clone=C.clone;
  const ask=async text=>dialog.confirm?await dialog.confirm(text,{title:'Abrxs-Canter',kind:'warning'}):await window.confirm(text);
  const S={project:null,epoch:0,clips:[],selected:new Set(),view:'grid',clip:null,data:null,
    block:0,mode:'montage',scale:20,originStart:0,originSpan:30,history:[],future:[],
    anchor:null,focus:null,words:[],playing:false,playIndex:0,rangeEnd:null,drag:null,
    saveTimer:null,draftChain:Promise.resolve(),assets:null,busy:false,job:null,
    reviewing:false,sourceOnly:false,dirty:false,search:'',restoredDraft:null,saveChain:Promise.resolve(),assetMap:{},saving:false,
    workspace:{fragments:[],positions:{},view:'grid',visual:null},workspaceChain:Promise.resolve(),workspacePending:0,activeWord:-1,visualSamples:[]};
  const status={draft:'Borrador',review:'Por revisar',approved:'Aprobado'};
  const exported={pending:'Sin exportar',queued:'En cola',exported:'Exportado',outdated:'Exportación desactualizada',error:'Error'};
  const node=document.createElement('section');node.id='ac-studio';node.className='ac-studio';node.hidden=true;
  node.innerHTML=`
    <header class="ac-top"><button id="ac-close">← Preparar</button><strong>ABRXS · ESTUDIO</strong><small id="ac-project"></small><button id="ac-library">Revisar</button><button id="ac-new">Crear clip</button><button id="ac-focus">Enfoque</button></header>
    <div id="ac-message" class="ac-message" role="status" aria-live="polite"></div>
    <div id="ac-progress" class="ac-progress" hidden><progress id="ac-meter" max="100" value="0"></progress><span id="ac-job-detail"></span><small id="ac-eta">Estimando…</small><button id="ac-cancel">Cancelar</button></div>
    <div id="ac-library-tools" class="ac-toolbar"><div class="ac-actions"><button data-view="grid">Fichas</button><button data-view="list">Lista</button><button data-view="kanban">Kanban</button><button data-view="map">Mapa</button></div><input id="ac-filter" type="search" placeholder="Buscar clips…" aria-label="Buscar clips"><button id="ac-import">Importar cortes</button><button id="ac-select-all">Seleccionar visibles</button><button id="ac-export-many" class="ac-primary">Exportar seleccionados</button><details><summary>Más opciones</summary><label><input id="ac-sections" type="checkbox"> Secciones extra</label><button id="ac-cache">Limpiar caché</button></details></div>
    <div id="ac-cards" class="ac-grid"></div>
    <div id="ac-editor" class="ac-editor" hidden>
      <aside class="ac-transcript"><h3>Transcripción del máster</h3><input id="ac-search" type="search" placeholder="Buscar palabra o frase…" aria-label="Buscar transcripción"><div class="ac-actions"><button id="ac-add">+ Añadir selección</button><button id="ac-preview-selection">▶ Selección</button></div><small id="ac-selection">Selecciona palabras arrastrando o con Shift.</small><div id="ac-words" class="ac-words" tabindex="0"></div></aside>
      <main class="ac-preview"><small id="ac-preview-label">Preview desde el máster; no se ha renderizado.</small><div class="ac-video-space"><div id="ac-video-box" class="ac-video-box"><video id="ac-video" preload="metadata" playsinline></video></div></div><div class="ac-transport"><button id="ac-play">▶ Montaje</button><button id="ac-context-in">▶ Entrada</button><button id="ac-context-out">▶ Salida</button><button id="ac-join">▶ Unión</button><label>Contexto <select id="ac-context"><option>2</option><option selected>5</option><option>10</option></select> s</label><label>Velocidad <select id="ac-rate"><option>0.75</option><option selected>1</option><option>1.25</option><option>1.5</option><option>2</option></select></label></div><span id="ac-time" class="ac-time"></span><div id="ac-review-tools" class="ac-review-tools" hidden><button id="ac-prev">← Anterior</button><button id="ac-next">Siguiente →</button><button id="ac-approve">✓ Aprobar</button><button id="ac-final">Ver MP4 exportado</button><button id="ac-master">Volver al máster</button></div><small>El contexto no entra en la exportación. Los saltos del preview pueden tener pequeñas pausas.</small><div class="ac-actions"><button id="ac-assets">Generar miniaturas y onda de audio</button><button id="ac-relink">Relocalizar máster</button><button id="ac-add-range">+ Bloque desde cabezal</button></div></main>
      <aside class="ac-blocks"><input id="ac-title" class="ac-title" maxlength="100" aria-label="Título"><div class="ac-actions"><button id="ac-undo" title="Deshacer">↶</button><button id="ac-redo" title="Rehacer">↷</button><button id="ac-save">Guardar ficha</button><button id="ac-export" class="ac-primary">Exportar clip</button></div><small id="ac-saved"></small><label>Estado <select id="ac-status"><option value="draft">Borrador</option><option value="review">Por revisar</option><option value="approved">Aprobado</option></select></label><textarea id="ac-note" placeholder="Notas de revisión…" aria-label="Notas"></textarea><h3>Bloques del montaje</h3><div id="ac-blocks"></div><div id="ac-inspector" class="ac-inspector"><label>Entrada <input id="ac-in" type="number" min="0" step="0.001"></label><label>Salida <input id="ac-out" type="number" min="0" step="0.001"></label><div class="ac-actions"><button data-nudge="start:-0.2">Entrada −0.20</button><button data-nudge="start:0.2">Entrada +0.20</button><button data-nudge="end:-0.2">Salida −0.20</button><button data-nudge="end:0.2">Salida +0.20</button></div><div class="ac-actions"><button data-frame="start:-1">Entrada −1 frame</button><button data-frame="start:1">Entrada +1 frame</button><button data-frame="end:-1">Salida −1 frame</button><button data-frame="end:1">Salida +1 frame</button></div><div class="ac-actions"><button id="ac-split">Dividir en cabezal</button><button id="ac-merge">Unir siguiente</button><button id="ac-duplicate">Duplicar</button><button id="ac-remove">Quitar bloque</button></div><label><input id="ac-snap" type="checkbox"> Ajustar a palabras al soltar</label><label>Formato <select id="ac-aspect"><option value="original">Original</option><option>9:16</option><option>16:9</option><option>1:1</option></select></label><label>Encuadre <select id="ac-crop-mode"><option value="contain">Completo con bandas</option><option value="cover">Recortar para llenar</option></select></label><label>Horizontal <input id="ac-x" type="range" min="0" max="1" step="0.01" value="0.5"></label><label>Vertical <input id="ac-y" type="range" min="0" max="1" step="0.01" value="0.5"></label></div></aside>
    </div>
    <section id="ac-timeline" class="ac-timeline" hidden><div class="ac-timeline-top"><button id="ac-origin-mode">Origen</button><button id="ac-montage-mode">Montaje</button><button id="ac-fit">Ajustar vista</button><button id="ac-full">Todo el máster</button><span id="ac-duration"></span><label>Zoom <input id="ac-zoom" type="range" min="0" max="100" value="50"></label></div><div id="ac-scroll" class="ac-timeline-scroll"><div id="ac-track" class="ac-track"></div></div><p class="ac-timeline-help">Origen usa tiempos del máster; Montaje empieza en cero. Arrastra extremos, reproduce el contexto y guarda.</p></section>`;
  document.body.appendChild(node);
  const launch=document.createElement('div');launch.className='ac-launch';launch.innerHTML='<div><small>ESTUDIO EDITORIAL</small><strong>Preparar → Crear → Revisar</strong><p>Tu máster, contexto y clips conectados. Los originales no se modifican.</p></div><div class="ac-actions"><button id="ac-create-entry">Crear desde cero</button><button class="primary-btn compact" id="ac-launch">Revisar y mapa →</button></div>';
  $('studioView').insertBefore(launch,$('studioView').firstChild);
  const video=el('video');
  const layout=document.createElement('div');layout.className='ac-library-layout';el('cards').before(layout);layout.append(el('cards'));
  const dock=document.createElement('aside');dock.className='ac-library-preview';dock.hidden=true;
  dock.innerHTML='<small>VISOR · SIN RENDERIZAR</small><h3 id="ac-library-title">Selecciona una ficha</h3><video id="ac-library-video" controls playsinline preload="metadata"></video><div class="ac-actions"><button id="ac-library-play">▶ Reproducir secuencia</button><button id="ac-library-original">Desde máster</button><button id="ac-library-final">MP4 exportado</button></div><label>Posición del montaje<input id="ac-library-seek" type="range" min="0" step="0.01" value="0"></label><small id="ac-library-time"></small><p id="ac-library-state"></p><div id="ac-library-text"></div><div class="ac-actions"><button id="ac-library-edit">Editar ficha</button><button id="ac-library-export">Exportar ficha</button></div>';
  layout.append(dock);const libraryVideo=el('library-video');let previewId=null,previewIndex=0,previewEpoch=0,previewFinal=false;
  const floating=window.AbrxsFloatingPreview?.mount({dock,layout,toolbar:el('library-tools'),video:libraryVideo,getView:()=>S.view});
  function stopLibrary(clear=false){libraryVideo.pause();if(clear){previewEpoch++;previewId=null;libraryVideo.removeAttribute('src');libraryVideo.load();dock.hidden=true;el('library-title').textContent='Selecciona una ficha';el('library-state').textContent='';el('library-time').textContent='';el('library-text').innerHTML='';el('library-seek').value=0;layout.classList.remove('with-preview');floating?.reset();}}
  function previewClip(){return S.clips.find(c=>c.id===previewId);}
  function refreshPreview(){const c=previewClip();if(!c)return;el('library-title').textContent=c.title;el('library-state').textContent=(exported[c.exportState]||'Sin exportar')+' · '+(c.outputOrientation||c.format?.aspect||'Original');el('library-final').disabled=!c.export?.path;el('library-seek').disabled=previewFinal;el('library-seek').max=C.duration(c.blocks);el('library-text').innerHTML=c.blocks.map((b,i)=>`<button data-preview-block="${i}">${preciseTime(b.start)} → ${preciseTime(b.end)}</button><p>${esc(b.text)}</p>`).join('');dock.querySelectorAll('[data-preview-block]').forEach(b=>b.onclick=report(()=>previewLibrary(c,Number(b.dataset.previewBlock))));}
  async function previewLibrary(c,index=0,final=false){
    if(!c)return;stop();stopLibrary();const epoch=++previewEpoch,projectEpoch=S.epoch;
    const data=await query({op:'source',video:c.source.path,transcript:c.transcript});
    if(epoch!==previewEpoch||projectEpoch!==S.epoch)return;
    if(data.source.sampleHash!==c.source.sampleHash||data.source.size!==c.source.size)throw Error('El máster cambió. Relocaliza o verifica esta ficha antes de reproducirla.');
    previewId=c.id;previewIndex=Math.max(0,Math.min(index,c.blocks.length-1));previewFinal=final;if(floating)floating.show();else{layout.classList.add('with-preview');dock.hidden=false;}
    const restart=()=>{if(epoch!==previewEpoch||projectEpoch!==S.epoch)return;libraryVideo.pause();libraryVideo.currentTime=final?0:c.blocks[previewIndex]?.start||0;el('library-seek').value=final?0:c.blocks.slice(0,previewIndex).reduce((n,b)=>n+b.end-b.start,0);};
    libraryVideo.onloadedmetadata=restart;
    if(window.AbrxsMedia)await window.AbrxsMedia.attach(libraryVideo,final&&c.export?.path?c.export.path:c.source.path);else libraryVideo.src=api.convertFileSrc(final&&c.export?.path?c.export.path:c.source.path);
    if(epoch!==previewEpoch||projectEpoch!==S.epoch)return;
    if(libraryVideo.readyState>=1)restart();
    libraryVideo.style.aspectRatio=String(data.media.width/data.media.height);libraryVideo.style.objectFit=c.format?.mode==='cover'?'cover':'contain';libraryVideo.style.objectPosition=`${(c.format?.x??.5)*100}% ${(c.format?.y??.5)*100}%`;
    refreshPreview();el('library-time').textContent=final?'Archivo exportado':'Secuencia virtual del máster · no se genera un archivo';
  }
  libraryVideo.ontimeupdate=()=>{const c=previewClip();if(!c||previewFinal)return;const b=c.blocks[previewIndex];if(!b)return;const t=libraryVideo.currentTime,m=c.blocks.slice(0,previewIndex).reduce((n,b)=>n+b.end-b.start,0)+Math.max(0,Math.min(b.end-b.start,t-b.start));el('library-seek').value=m;el('library-time').textContent='Montaje '+preciseTime(m)+' / '+preciseTime(C.duration(c.blocks))+' · Máster '+preciseTime(t);if(!libraryVideo.paused&&t>=b.end){if(previewIndex+1<c.blocks.length){previewIndex++;libraryVideo.currentTime=c.blocks[previewIndex].start;}else{libraryVideo.pause();libraryVideo.currentTime=b.end;}}};
  libraryVideo.onplay=()=>{const c=previewClip();if(!c||previewFinal)return;const current=c.blocks[previewIndex];if(current&&libraryVideo.currentTime>=current.start&&libraryVideo.currentTime<current.end)return;const i=c.blocks.findIndex(b=>libraryVideo.currentTime>=b.start&&libraryVideo.currentTime<b.end);if(i<0){previewIndex=0;libraryVideo.currentTime=c.blocks[0].start;}else previewIndex=i;};
  libraryVideo.onseeking=()=>{const c=previewClip();if(!c||previewFinal||!c.blocks.length)return;const t=libraryVideo.currentTime,current=c.blocks[previewIndex];if(current&&t>=current.start&&t<current.end)return;const i=c.blocks.findIndex(b=>t>=b.start&&t<b.end);if(i>=0){previewIndex=i;return;}if(libraryVideo.paused&&t===c.blocks.at(-1).end)return;previewIndex=c.blocks.reduce((best,b,j)=>Math.abs(b.start-t)<Math.abs(c.blocks[best].start-t)?j:best,0);libraryVideo.currentTime=c.blocks[previewIndex].start;};
  libraryVideo.onended=()=>{const c=previewClip();if(c&&!previewFinal&&previewIndex+1<c.blocks.length){previewIndex++;libraryVideo.currentTime=c.blocks[previewIndex].start;libraryVideo.play().catch(e=>message(e.message));}};
  libraryVideo.onerror=()=>message('El visor no pudo abrir esta fuente. Revisa permisos, códec o ubicación.');
  el('library-play').onclick=report(async()=>{if(!previewClip())return;if(previewFinal)await previewLibrary(previewClip());await libraryVideo.play();});
  el('library-seek').oninput=()=>{const c=previewClip();if(!c||previewFinal)return;const hit=C.toSource(c.blocks,Number(el('library-seek').value));if(hit){previewIndex=hit.index;libraryVideo.currentTime=hit.time;}};
  el('library-original').onclick=report(()=>previewLibrary(previewClip()));el('library-final').onclick=report(()=>previewLibrary(previewClip(),0,true));
  el('library-edit').onclick=report(()=>openClip(previewClip()));el('library-export').onclick=report(()=>job({op:'export',ids:[previewId],sections:el('sections').checked}));
  const prepare=document.createElement('section');prepare.className='ac-preparation panel';prepare.innerHTML='<div><small>PREPARAR · RESULTADOS</small><h3>Contexto del proyecto</h3><p>Transcribe con el panel de fuentes. Después analiza el máster o exporta su contexto.</p></div><div class="ac-actions"><button id="ac-prepare-visual">Analizar visualmente</button><button id="ac-context-export">Exportar contexto TXT + JSON</button><button id="ac-project-files">Mostrar archivos</button></div><div id="ac-result-links" class="ac-actions"></div>';
  launch.after(prepare);
  el('words').before(Object.assign(document.createElement('div'),{className:'ac-pane-tabs',innerHTML:'<button data-pane="words">Texto</button><button data-pane="scenes">Visual</button><button data-pane="tray">Bandeja</button>'}));
  el('words').after(Object.assign(document.createElement('div'),{id:'ac-scenes',className:'ac-scenes',hidden:true}),Object.assign(document.createElement('div'),{id:'ac-tray',className:'ac-tray',hidden:true}));
  el('selection').after(Object.assign(document.createElement('div'),{className:'ac-actions',innerHTML:'<button id="ac-store">Guardar en bandeja</button><label><input id="ac-follow" type="checkbox" checked> Seguir reproducción</label>'}));
  el('blocks').before(Object.assign(document.createElement('details'),{innerHTML:'<summary>Sugerencias locales</summary><p>Por duración, frases y palabras clave. No es un análisis semántico de IA.</p><label>Palabras clave <input id="ac-keywords" placeholder="mesas, sillas…"></label><label>Duración objetivo <input id="ac-target-length" type="number" min="10" max="120" value="45"></label><button id="ac-suggest">Buscar propuestas</button><div id="ac-suggestions"></div>'}));
  el('video-box').insertAdjacentHTML('beforeend','<div id="ac-caption-preview" class="ac-caption-preview" hidden></div>');
  el('inspector').insertAdjacentHTML('beforeend',`<details class="ac-stage2"><summary>Captions y Vision · Etapa 2</summary><label>Captions <select id="ac-caption-mode"><option value="off">Desactivados</option><option value="sidecar">Archivos SRT + ASS</option><option value="burn">Incrustar en MP4</option></select></label><button id="ac-caption-style">Cargar estilo JSON</button><small id="ac-caption-style-name">Arial · blanco · inferior</small><hr><button id="ac-visual">Analizar visualmente el máster</button><button id="ac-visual-report" disabled>Abrir informe visual</button><small>Rostros, cuerpos y texto visible. No describe acciones ni identifica personas.</small><label>Seguimiento del bloque <select id="ac-track-mode"><option value="face">Rostro principal</option><option value="body">Cuerpo principal</option><option value="object">Objeto: rectángulo manual</option></select></label><label>Objeto x,y,ancho,alto <input id="ac-object-rect" value="0.35,0.20,0.30,0.60" aria-label="Rectángulo normalizado de objeto"></label><button id="ac-track-subject">Calcular seguimiento</button><button id="ac-disable-track">Quitar seguimiento</button><small id="ac-tracking-state">Sin seguimiento. Requiere formato no original y Recortar para llenar.</small></details>`);
  const defaultCaptionStyle={font:'Arial',size:48,color:'#FFFFFF',background:'#000000',position:'bottom',bold:true,box:false,words:6,margin:80,outline:2};
  let captionCues=[];
  function buildCaptionCues(){captionCues=[];let batch=[];const limit=S.clip?.captions?.style?.words||6;for(const w of C.virtualWords(S.words,S.clip?.blocks||[])){if(batch.length&&(w.start-batch.at(-1).end>.6||w.blockUid!==batch.at(-1).blockUid)){captionCues.push({start:batch[0].start,end:batch.at(-1).end,text:batch.map(w=>w.text).join(' ')});batch=[];}batch.push(w);if(batch.length>=limit||/[.!?]$/.test(w.text)){captionCues.push({start:batch[0].start,end:batch.at(-1).end,text:batch.map(w=>w.text).join(' ')});batch=[];}}if(batch.length)captionCues.push({start:batch[0].start,end:batch.at(-1).end,text:batch.map(w=>w.text).join(' ')});}
  function previewExtras(montage){
    const layer=el('caption-preview'),settings=S.clip?.captions;
    const cue=settings?.mode==='burn'&&!S.sourceOnly&&S.rangeEnd===null?captionCues.find(c=>c.start<=montage&&c.end>montage):null;
    layer.hidden=!cue;
    if(cue){const st={...defaultCaptionStyle,...settings.style};layer.textContent=cue.text;const width=S.clip.format.aspect==='original'?S.data.media.width:S.clip.format.aspect==='16:9'?1920:1080;const scale=el('video-box').clientWidth/width;Object.assign(layer.style,{fontFamily:st.font,fontSize:`${st.size*scale}px`,fontWeight:st.bold?'700':'400',color:st.color,background:st.box?st.background:'transparent',textShadow:st.box?'none':`0 1px ${Math.max(1,st.outline*scale)}px ${st.background}`,top:st.position==='bottom'?'auto':st.position==='center'?'50%':`${st.margin*scale}px`,bottom:st.position==='bottom'?`${st.margin*scale}px`:'auto',transform:st.position==='center'?'translateY(-50%)':'none'});}
    const track=S.clip?.tracking;
    const active=track?.points?.length&&S.clip.format.mode==='cover'&&track.format?.aspect===S.clip.format.aspect&&(!track.ranges||track.ranges.some(r=>r.uid===current()?.uid));
    if(!S.sourceOnly&&active){const points=track.points,t=video.currentTime;let a=points[0],b=a;for(const p of points){b=p;if(p.time>=t)break;a=p;}const f=Math.max(0,Math.min(1,(t-a.time)/Math.max(.0001,b.time-a.time)));video.style.objectPosition=`${(a.x+(b.x-a.x)*f)*100}% ${(a.y+(b.y-a.y)*f)*100}%`;}
    else if(!S.sourceOnly&&S.clip)video.style.objectPosition=`${S.clip.format.x*100}% ${S.clip.format.y*100}%`;
  }
  el('visual').title='Vision local: rostros, cuerpos y texto visible. No narra acciones.';
  el('track-subject').title='Seguimiento experimental: valida Vision y revisa el resultado antes de exportar.';
  const message=text=>{el('message').textContent=text||'';};
  const projectContext=()=>({projectPath:S.project.path,outputPath:state.outputResult||state.project?.lastOutput,video:state.video,transcript:state.transcript});
  const query=async payload=>{const epoch=S.epoch;const result=await api.invoke('stage1_query',{request:{...projectContext(),...payload}});if(epoch!==S.epoch)throw Error('El proyecto cambió; se descartó el resultado.');return result;};
  function report(fn){return async(...args)=>{try{await fn(...args);}catch(e){message(String(e));}};}
  const current=()=>S.clip?.blocks?.[S.block];
  const textFor=(start,end)=>S.words.filter(w=>w.end>start&&w.start<end).map(w=>w.text).join(' ');
  function stop(){S.playing=false;S.rangeEnd=null;video.pause();el('play').textContent='▶ Montaje';}
  function snapshot(){S.history.push(clone(S.clip));if(S.history.length>80)S.history.shift();S.future=[];}
  function changed(){S.dirty=true;el('saved').textContent='Borrador pendiente de guardar';scheduleDraft();update();}
  function edit(fn){if(!S.clip||S.busy||S.saving)return;stop();snapshot();fn();changed();}
  function scheduleDraft(){clearTimeout(S.saveTimer);const epoch=S.epoch;S.saveTimer=setTimeout(()=>{if(epoch===S.epoch)flushDraft().catch(e=>message(String(e)));},600);}
  function flushDraft(){
    clearTimeout(S.saveTimer);
    if(!S.project||!S.clip)return S.draftChain;
    const request={op:'draft',projectPath:S.project.path,draft:{schemaVersion:1,clip:clone(S.clip),history:clone(S.history),future:clone(S.future),updatedAt:Date.now()}};
    S.draftChain=S.draftChain.catch(()=>{}).then(()=>api.invoke('stage1_query',{request}));
    return S.draftChain;
  }
  async function syncLibrary(){const data=await query({op:S.busy||state.running?'library_snapshot':'library'});S.clips=data.clips||[];S.restoredDraft=data.draft;S.assetMap=Object.fromEntries((data.assets||[]).map(a=>[a.source.sampleHash,a]));S.workspace=await query({op:'studio_load'});S.view=S.workspace.view||'grid';renderLibrary();renderTray();if(data.queue?.status==='running'||data.queue?.status==='interrupted')message('Hay una cola activa o interrumpida. Las versiones anteriores se conservan.');}
  async function enter(){
    if(!state.project)return;
    if(S.project?.id!==state.project.id)reset(state.project);
    node.hidden=false;document.body.style.overflow='hidden';el('project').textContent=S.project.name;
    await syncLibrary();await showLibrary(false);
  }
  function reset(project=null){
    stopLibrary(true);
    clearTimeout(S.saveTimer);S.epoch++;stop();video.removeAttribute('src');video.load();
    Object.assign(S,{project,clips:[],selected:new Set(),clip:null,data:null,history:[],future:[],words:[],assets:null,assetMap:{},busy:false,job:null,restoredDraft:null,dirty:false,anchor:null,focus:null,search:'',workspace:{fragments:[],positions:{},view:'grid',visual:null},activeWord:-1,visualSamples:[]});
    node.classList.remove('ac-focus-mode');el('scenes').innerHTML='';el('suggestions').innerHTML='';el('result-links').innerHTML='';
    node.hidden=true;el('progress').hidden=true;el('cards').innerHTML='';el('filter').value='';el('words').innerHTML='';el('tray').innerHTML='';el('scenes').hidden=true;el('tray').hidden=true;el('words').hidden=false;document.body.style.overflow='';
  }
  const originalOpenProject=openProject;
  openProject=async function(project){if(S.busy||S.saving||state.running){alert('Cancela o espera al trabajo activo antes de cambiar de proyecto.');return;}await flushDraft();await S.workspaceChain;reset(project);return originalOpenProject(project);};
  const originalWelcome=showWelcome;
  showWelcome=async function(){if(S.busy||S.saving||state.running)return;await flushDraft();await S.workspaceChain;reset();return originalWelcome();};
  // Las referencias a funciones usadas en los botones antiguos se actualizan.
  $('backProjectsBtn').onclick=showWelcome;$('brandHome').onclick=showWelcome;
  async function showLibrary(save=true){if(save&&!S.busy&&!state.running)await flushDraft();stop();node.classList.remove('ac-focus-mode');el('editor').hidden=true;el('timeline').hidden=true;el('cards').hidden=false;el('library-tools').hidden=false;renderLibrary();window.dispatchEvent(new CustomEvent('abrxs-route',{detail:'review'}));}
  function filtered(){const search=C.token(el('filter').value);return S.clips.filter(c=>C.token(c.title+' '+(c.origin||'')+' '+(c.variant||'')).includes(search));}
  function card(c){const length=C.duration(c.blocks),thumbs=S.assetMap[c.source.sampleHash]?.thumbs||[],thumb=thumbs.length?thumbs.reduce((a,b)=>Math.abs(a.time-c.blocks[0].start)<Math.abs(b.time-c.blocks[0].start)?a:b):null;return `<article class="ac-card ${S.selected.has(c.id)?'selected':''}" data-id="${esc(c.id)}"><header><input type="checkbox" data-select="${esc(c.id)}" ${S.selected.has(c.id)?'checked':''} aria-label="Seleccionar ${esc(c.title)}"><div><h3>${esc(c.title)}</h3><small>${esc(c.variant||'MANUAL')} · ${length.toFixed(2)} s · ${c.blocks.length} bloques</small></div></header>${thumb?`<img src="${esc(api.convertFileSrc(thumb.path))}" alt="Fotograma aproximado del máster" loading="lazy">`:''}<div class="ac-badges"><span class="ac-badge">${status[c.status]||'Borrador'}</span><span class="ac-badge ${['outdated','error'].includes(c.exportState)?'warning':''}">${exported[c.exportState]||'Sin exportar'}</span></div><div class="ac-actions"><button data-review="${esc(c.id)}">▶ Revisar</button><button data-edit="${esc(c.id)}">Editar</button><button data-one-export="${esc(c.id)}">Exportar</button></div></article>`;}
  let mapPan=null;
  function renderLibrary(){
    layout.hidden=!el('editor').hidden;
    if(!el('editor').hidden)stopLibrary(true);
    if(floating)floating.sync(!!previewClip());else{dock.hidden=!previewClip();layout.classList.toggle('with-preview',!dock.hidden);}
    dock.querySelectorAll('.ac-viewer-body button,.ac-viewer-body input').forEach(n=>n.disabled=!previewClip());
    refreshPreview();
    mapPan?.destroy();mapPan=null;
    const list=filtered();el('cards').className=`ac-grid ${S.view==='list'?'ac-list':S.view==='kanban'?'ac-kanban':''}`;
    if(S.view==='map'){renderMap(list);bindCards();return;}
    el('cards').innerHTML=!list.length?'<div class="ac-empty"><strong>No hay fichas todavía.</strong><p>Prepara la transcripción del máster en el proyecto y después importa decisiones o crea un clip desde cero. Los videos exportados antiguos se recuperan cuando contienen rangos verificables.</p></div>':S.view==='kanban'?Object.entries(status).map(([key,label])=>`<section class="ac-column"><h3>${label}</h3>${list.filter(c=>c.status===key).map(card).join('')}</section>`).join(''):list.map(card).join('');
    bindCards();
  }
  function bindCards(){
    node.querySelectorAll('[data-select]').forEach(b=>b.onchange=()=>{b.checked?S.selected.add(b.dataset.select):S.selected.delete(b.dataset.select);renderLibrary();});
    node.querySelectorAll('[data-edit]').forEach(b=>b.onclick=report(()=>openClip(S.clips.find(c=>c.id===b.dataset.edit),false)));
    node.querySelectorAll('[data-review]').forEach(b=>b.onclick=report(()=>previewLibrary(S.clips.find(c=>c.id===b.dataset.review))));
    node.querySelectorAll('.ac-card[data-id]').forEach(card=>{card.onclick=report(e=>{if(e.target.closest('button,input,summary'))return;return previewLibrary(S.clips.find(c=>c.id===card.dataset.id));});});
    node.querySelectorAll('[data-one-export]').forEach(b=>b.onclick=report(()=>job({op:'export',ids:[b.dataset.oneExport],sections:el('sections').checked})));
    node.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===S.view)));
    el('export-many').disabled=!S.selected.size;
  }
  async function openClip(clip=null,reviewing=false){
    stopLibrary(true);
    if(S.busy||S.saving)throw Error('Espera o cancela el trabajo activo.');
    await flushDraft();stop();const epoch=S.epoch;
    let draft=null;
    if(!clip&&S.restoredDraft?.clip&&await ask('Hay un borrador recuperable. ¿Quieres abrirlo?'))draft=S.restoredDraft;
    const chosen=clip||draft?.clip;
    let data;
    try{data=await query({op:'source',video:chosen?.source?.path||state.video,transcript:chosen?.transcript||state.transcript});}
    catch(error){if(epoch!==S.epoch)return;message(`${error}\nSi el máster se movió, selecciona su nueva ubicación.`);if(chosen&&await ask('No se pudo cargar esta ficha. ¿Quieres seleccionar de nuevo el máster?')){S.clip=clone(chosen);if(await relink())return openClip(S.clip,reviewing);return;}throw error;}
    if(epoch!==S.epoch)return;
    S.data=data;S.words=data.words;S.assets=data.assets;S.block=0;S.anchor=null;S.focus=null;S.reviewing=reviewing;S.sourceOnly=false;S.dirty=false;S.activeWord=-1;
    S.clip=chosen?clone(chosen):{id:C.uid(),revision:0,title:'Nuevo clip',source:data.source,transcript:data.transcript,duration:data.media.duration,blocks:[],status:'draft',note:'',variant:'MANUAL',format:{aspect:'original',mode:'contain',x:.5,y:.5}};
    S.history=draft?.history||[];S.future=draft?.future||[];
    el('editor').hidden=false;el('timeline').hidden=false;el('cards').hidden=true;el('library-tools').hidden=true;
    layout.hidden=true;
    el('review-tools').hidden=!reviewing;if(window.AbrxsMedia)await window.AbrxsMedia.attach(video,data.source.path);else video.src=api.convertFileSrc(data.source.path);
    el('title').value=S.clip.title;el('note').value=S.clip.note||'';el('status').value=S.clip.status;
    S.mode='montage';el('zoom').value='50';el('scroll').scrollLeft=0;
    el('search').value='';renderWords();update();focusOrigin();fit();
    window.dispatchEvent(new CustomEvent('abrxs-route',{detail:'create'}));
    message(data.media.previewWarning?'Este codec puede no reproducirse en WebKit. Si falla, conserva el máster y utiliza una copia compatible.':!S.words.length?'Sin transcripción: puedes crear rangos desde el cabezal o volver al proyecto para transcribir.':'');
    if(chosen?.legacyExtras||chosen?.extras?.xrolls?.length||chosen?.extras?.voiceovers?.length)message('Esta ficha conserva extras editoriales. Al modificar el montaje, revisa sus ubicaciones; no se remapean automáticamente.');
  }
  async function relink(){if(!S.clip)throw Error('Selecciona una ficha primero.');const path=await dialog.open({multiple:false,filters:[{name:'Máster',extensions:['mp4','mov','m4v','mkv']}]});if(!path)return false;const data=await query({op:'relink',id:S.clip.id,video:path});S.clip.source=data.source;await syncLibrary();return true;}
  function renderWords(){el('words').innerHTML=S.words.map((w,i)=>`<span class="ac-word" data-word="${i}" title="${preciseTime(w.start)} → ${preciseTime(w.end)}">${esc(w.text)}</span>`).join(' ');}
  function wordSelection(){return S.anchor===null||S.focus===null?null:[Math.min(S.anchor,S.focus),Math.max(S.anchor,S.focus)];}
  function paintSelection(){const range=wordSelection();el('words').querySelectorAll('[data-word]').forEach(n=>n.classList.toggle('selected',!!range&&Number(n.dataset.word)>=range[0]&&Number(n.dataset.word)<=range[1]));el('selection').textContent=range?`${preciseTime(S.words[range[0]].start)} → ${preciseTime(S.words[range[1]].end)}`:'Selecciona palabras arrastrando o con Shift.';}
  function addSelection(){const r=wordSelection();if(!r)return;edit(()=>{const start=S.words[r[0]].start,end=S.words[r[1]].end;S.clip.blocks.push({uid:C.uid(),start,end,text:textFor(start,end),role:'SECCION'});S.block=S.clip.blocks.length-1;});}
  function update(){
    if(!S.clip)return;
    el('title').value=S.clip.title;el('note').value=S.clip.note||'';el('status').value=S.clip.status;
    el('undo').disabled=!S.history.length||S.busy;el('redo').disabled=!S.future.length||S.busy;
    el('save').disabled=S.busy||!S.clip.blocks.length;el('export').disabled=S.busy||!S.clip.blocks.length;
    el('blocks').innerHTML=S.clip.blocks.map((b,i)=>`<article class="ac-block ${i===S.block?'active':''}" data-block="${i}"><strong>${i+1} · ${esc(b.role||'SECCION')}</strong><p>${esc(b.text||'Rango manual')}</p><small class="ac-time">${preciseTime(b.start)} → ${preciseTime(b.end)}</small><div class="ac-actions"><button data-move="${i}:-1" aria-label="Subir bloque">↑</button><button data-move="${i}:1" aria-label="Bajar bloque">↓</button></div></article>`).join('');
    el('blocks').querySelectorAll('[data-block]').forEach(b=>b.onclick=e=>{if(e.target.closest('button'))return;selectBlock(Number(b.dataset.block));});
    el('blocks').querySelectorAll('[data-move]').forEach(b=>b.onclick=()=>{const [i,d]=b.dataset.move.split(':').map(Number),j=i+d;if(j<0||j>=S.clip.blocks.length)return;edit(()=>{[S.clip.blocks[i],S.clip.blocks[j]]=[S.clip.blocks[j],S.clip.blocks[i]];S.block=j;});});
    const b=current();el('inspector').hidden=!b;
    if(b){el('in').value=b.start.toFixed(3);el('out').value=b.end.toFixed(3);}
    const fmt=S.clip.format;el('aspect').value=fmt.aspect;el('crop-mode').value=fmt.mode;el('x').value=fmt.x;el('y').value=fmt.y;applyCrop();renderTimeline();
    el('caption-mode').value=S.clip.captions?.mode||'off';const cs=S.clip.captions?.style||defaultCaptionStyle;el('caption-style-name').textContent=`${cs.font} · ${cs.size} · ${cs.position}`;buildCaptionCues();el('visual-report').disabled=!S.clip.visualReport;el('tracking-state').textContent=S.clip.tracking?.points?.length?`${S.clip.tracking.points.length} puntos · ${S.clip.tracking.lost||0} muestras sin objetivo. Revisa antes de exportar.`:'Sin seguimiento.';
    el('final').disabled=!S.clip.export?.path;
  }
  async function selectBlock(i){stop();S.sourceOnly=false;S.block=i;await setMaster();seekVideo(current().start);focusOrigin();update();}
  function bounds(edge,value,history=true){const b=current();if(S.busy||S.saving||!b||!Number.isFinite(value))return;if(history)snapshot();stop();const min=.001;if(edge==='start')b.start=Math.max(0,Math.min(value,b.end-min));else b.end=Math.min(S.clip.duration,Math.max(value,b.start+min));b.text=textFor(b.start,b.end);S.dirty=true;scheduleDraft();update();}
  function applyCrop(){if(!S.data||!S.clip)return;const f=S.clip.format,m=S.data.media;const ratio=f.aspect==='original'?m.width/m.height:Number(f.aspect.split(':')[0])/Number(f.aspect.split(':')[1]);el('video-box').style.aspectRatio=String(ratio);el('video-box').style.width=ratio<1?'min(100%, 28vh)':'100%';video.style.objectFit=f.mode;video.style.objectPosition=`${f.x*100}% ${f.y*100}%`;}
  async function setMaster(){if(window.AbrxsMedia)await window.AbrxsMedia.attach(video,S.clip.source.path);else{const src=api.convertFileSrc(S.clip.source.path);if(video.getAttribute('src')!==src)video.src=src;}S.sourceOnly=false;applyCrop();}
  function seekVideo(time){if(video.readyState!==0){video.currentTime=time;return;}const clip=S.clip?.id;video.addEventListener('loadedmetadata',()=>{if(S.clip?.id===clip&&!S.sourceOnly)video.currentTime=time;},{once:true});}
  async function previewRange(start,end,label){stop();await setMaster();S.rangeEnd=Math.min(S.clip.duration,end);seekVideo(Math.max(0,start));el('preview-label').textContent=label;video.play().catch(e=>message(`No se puede reproducir: ${e.message}`));}
  async function playSequence(index=0){if(!S.clip?.blocks.length)return;if(S.playing){stop();return;}stop();await setMaster();S.playing=true;S.playIndex=index;S.block=index;seekVideo(S.clip.blocks[index].start);el('play').textContent='❚❚ Pausar';el('preview-label').textContent='Montaje virtual · tiempos del máster';update();video.play().catch(e=>{stop();message(e.message);});}
  function playbackTick(){
    if(!S.clip)return;
    if(S.sourceOnly){el('caption-preview').hidden=true;el('time').textContent=`MP4: ${preciseTime(video.currentTime)}`;return;}
    if(S.rangeEnd!==null&&video.currentTime>=S.rangeEnd){stop();}
    if(S.playing&&!video.seeking){const b=S.clip.blocks[S.playIndex];if(b&&video.currentTime>=b.end-.008){if(S.playIndex+1<S.clip.blocks.length){S.playIndex++;S.block=S.playIndex;video.currentTime=S.clip.blocks[S.playIndex].start;update();video.play().catch(()=>stop());}else{stop();video.currentTime=b.end;}}}
    if(!S.playing&&S.mode==='origin'){const index=S.clip.blocks.findIndex(b=>video.currentTime>=b.start&&video.currentTime<b.end);if(index>=0&&index!==S.block){S.block=index;update();return;}}
    const i=S.playing?S.playIndex:S.block,m=C.toMontage(S.clip.blocks,i,video.currentTime);
    previewExtras(m||0);
    const time=video.currentTime;let lo=0,hi=S.words.length-1,found=-1;
    while(lo<=hi){const mid=(lo+hi)>>1,w=S.words[mid];if(time<w.start)hi=mid-1;else if(time>=w.end)lo=mid+1;else{found=mid;break;}}
    if(found!==S.activeWord){el('words').querySelector('.current')?.classList.remove('current');S.activeWord=found;const word=el('words').querySelector(`[data-word="${found}"]`);if(word){word.classList.add('current');if(el('follow').checked&&!el('words').hidden&&!S.selecting)word.scrollIntoView({block:'nearest'});}}
    el('time').textContent=`Máster ${preciseTime(video.currentTime)} · Montaje ${preciseTime(m||0)} / ${preciseTime(C.duration(S.clip.blocks))}`;
    const head=el('track').querySelector('.ac-head');if(head){const t=S.mode==='origin'?video.currentTime-S.originStart:m||0;head.style.left=`${Math.max(0,t)*S.scale}px`;}
  }
  function frameLoop(){if(!video.requestVideoFrameCallback)return;video.requestVideoFrameCallback(()=>{playbackTick();frameLoop();});}frameLoop();video.ontimeupdate=playbackTick;
  video.onended=()=>{if(S.playing&&S.playIndex+1<S.clip.blocks.length){S.playIndex++;S.block=S.playIndex;video.currentTime=current().start;update();video.play().catch(()=>stop());}else stop();};
  video.onerror=()=>message('No se puede reproducir esta fuente. Revisa que exista y que su codec sea compatible con el visor de macOS.');
  video.onloadedmetadata=()=>{if(S.clip&&!S.sourceOnly&&!S.playing&&S.rangeEnd===null&&current()){video.currentTime=current().start;playbackTick();}};
  function focusOrigin(){const b=current();if(!b)return;const c=Number(el('context').value);S.originStart=Math.max(0,b.start-c);S.originSpan=Math.max(1,Math.min(S.clip.duration-S.originStart,b.end-b.start+2*c));if(S.mode==='origin')fit();}
  function fit(){const width=el('scroll').clientWidth||800;S.scale=Math.min(200,Math.max(.01,(width-30)/(S.mode==='origin'?S.originSpan:Math.max(1,C.duration(S.clip.blocks)))));renderTimeline();}
  function waveform(canvas,start,end){if(!S.assets?.peaks?.length){canvas.remove();return;}const count=Math.min(600,Math.max(20,Math.round(canvas.parentElement.clientWidth-16)));canvas.width=count;canvas.height=24;const ctx=canvas.getContext('2d');ctx.fillStyle='#c2cad3';for(let i=0;i<count;i++){const time=start+(end-start)*i/count,j=Math.min(S.assets.peaks.length-1,Math.max(0,Math.floor(time/S.assets.duration*S.assets.peaks.length))),height=Math.max(1,S.assets.peaks[j]*24);ctx.fillRect(i,(24-height)/2,1,height);}}
  function renderTimeline(){
    if(!S.clip)return;
    const total=S.mode==='origin'?S.originSpan:Math.max(1,C.duration(S.clip.blocks)),start=S.mode==='origin'?S.originStart:0,width=Math.max(el('scroll').clientWidth,total*S.scale);
    const step=[.1,.5,1,2,5,10,30,60,300,600,1800,3600].find(n=>n*S.scale>=70)||3600;
    let html='<div class="ac-ruler">';for(let t=Math.ceil(start/step)*step;t<=start+total;t+=step)html+=`<span class="ac-tick" style="left:${(t-start)*S.scale}px">${formatTime(t)}</span>`;html+='</div>';
    const b=current();if(S.mode==='origin'&&b){const c=Number(el('context').value),left=Math.max(0,b.start-c-start),right=Math.min(total,b.end+c-start);html+=`<div class="ac-window" style="left:${left*S.scale}px;width:${Math.max(0,right-left)*S.scale}px"></div>`;}
    let offset=0;
    S.clip.blocks.forEach((block,i)=>{const origin=S.mode==='origin',left=origin?block.start-start:offset,right=origin?block.end-start:offset+block.end-block.start;offset+=block.end-block.start;if(right<=0||left>=total)return;const visibleLeft=Math.max(0,left),visibleRight=Math.min(total,right);html+=`<div class="ac-range ${i===S.block?'active':''}" data-range="${i}" style="left:${visibleLeft*S.scale}px;width:${Math.max(2,(visibleRight-visibleLeft)*S.scale)}px"><span>${i+1} · ${esc(block.text||'Rango')}</span><canvas data-wave="${i}"></canvas>${left>=0?'<i class="ac-handle left" data-edge="start"></i>':''}${right<=total?'<i class="ac-handle right" data-edge="end"></i>':''}</div>`;});
    html+='<i class="ac-head"></i>';el('track').style.width=`${width}px`;el('track').innerHTML=html;
    if(S.assets?.thumbs?.length){el('track').querySelectorAll('[data-range]').forEach(n=>{const block=S.clip.blocks[Number(n.dataset.range)],strip=document.createElement('div');strip.className='ac-filmstrip';const count=Math.min(16,Math.max(1,Math.ceil(n.clientWidth/80)));for(let i=0;i<count;i++){const t=block.start+(block.end-block.start)*(i+.5)/count,thumb=S.assets.thumbs.reduce((a,b)=>Math.abs(a.time-t)<Math.abs(b.time-t)?a:b);const img=document.createElement('img');img.src=api.convertFileSrc(thumb.path);img.alt='';img.loading='lazy';strip.append(img);}n.prepend(strip);});}
    el('duration').textContent=`${S.mode==='origin'?'Máster':'Montaje'} · ${preciseTime(start)} → ${preciseTime(start+total)}`;
    el('origin-mode').setAttribute('aria-pressed',String(S.mode==='origin'));el('montage-mode').setAttribute('aria-pressed',String(S.mode==='montage'));
    el('track').querySelectorAll('[data-range]').forEach(n=>n.onclick=e=>{if(!e.target.closest('.ac-handle'))selectBlock(Number(n.dataset.range));});
    el('track').querySelectorAll('[data-wave]').forEach(n=>{const b=S.clip.blocks[Number(n.dataset.wave)];waveform(n,b.start,b.end);});
    el('track').querySelectorAll('.ac-handle').forEach(n=>n.onpointerdown=e=>{if(S.busy)return;e.preventDefault();e.stopPropagation();S.block=Number(n.parentElement.dataset.range);snapshot();stop();S.drag={edge:n.dataset.edge,x:e.clientX,value:current()[n.dataset.edge],scale:S.scale};});
    playbackTick();
  }
  async function save(){
    if(!S.clip||S.busy||S.saving)throw Error('Espera al trabajo activo.');
    S.clip.blocks=C.validate(S.clip.blocks,S.clip.duration);const epoch=S.epoch;
    const payload=clone(S.clip);
    S.saving=true;lock(true);
    try {
      const result=await query({op:'save',clip:payload});if(epoch!==S.epoch)return;
      S.clip=result;S.dirty=false;el('saved').textContent=`Ficha guardada · revisión ${result.revision}`;
      await flushDraft();await syncLibrary();return result;
    } finally {S.saving=false;lock(false);update();}
  }
  async function job(payload,dispatch=false){
    if(window.AbrxsProcesses&&!dispatch){window.AbrxsProcesses.enqueue(payload,projectContext(),state.project.id);return;}
    if(S.busy||state.running)throw Error('Ya hay un trabajo activo.');
    await flushDraft();const requestId=C.uid();S.busy=true;S.job={requestId,epoch:S.epoch,started:Date.now(),payload,result:null};
    el('progress').hidden=false;el('meter').value=0;el('job-detail').textContent='Preparando…';el('eta').textContent='Estimando…';el('cancel').disabled=false;
    lock(true);renderLibrary();updateStartState();
    try{await api.invoke('start_stage1_job',{request:{...projectContext(),...payload,requestId}});}catch(error){S.busy=false;S.job=null;el('progress').hidden=true;lock(false);updateStartState();throw error;}
  }
  function lock(value){node.querySelectorAll('button,input,select,textarea').forEach(n=>{if(!n.closest('#ac-library-tools,.ac-card,.ac-library-preview')&&!['ac-cancel','ac-library','ac-play','ac-context-in','ac-context-out','ac-rate','ac-context','ac-origin-mode','ac-montage-mode','ac-fit','ac-zoom'].includes(n.id))n.disabled=value;});}
  window.__TAURI__.event.listen('stage1-event',async({payload:p})=>{
    const job=S.job;if(!job||p.requestId!==job.requestId||job.epoch!==S.epoch)return;
    if(p.event==='result')job.result=p.data;
    if(p.event==='clip_start')el('job-detail').textContent=`${p.index}/${p.total} · ${p.title}`;
    if(p.event==='progress'||p.event==='clip_complete'){const value=Number(p.progress)||0;el('meter').value=value;const elapsed=(Date.now()-job.started)/1000;el('eta').textContent=p.etaSeconds!=null?`≈ ${formatTime(p.etaSeconds)} en esta sección`:value>2?`≈ ${formatTime(elapsed*(100/value-1))} restantes`:'Midiendo velocidad de codificación…';if(p.detail)el('job-detail').textContent=p.detail;}
    if(p.event==='clip_complete')await syncLibrary();
    if(p.event==='notice'||p.event==='clip_error')message(p.detail);
    if(p.event==='finished'){
      S.busy=false;S.job=null;lock(false);el('progress').hidden=true;updateStartState();
      try{if(job.payload.op==='assets'&&job.result){S.assets=job.result;renderTimeline();message('Miniaturas y onda listas. Se muestran en las fichas; son caché, no portadas exportadas.');showResult('Miniaturas · Mostrar en Finder',job.result.thumbs?.[0]?.path);}
        if(job.payload.op==='import')message((job.result?.warnings||[]).join('\n')||'Fichas importadas. Revísalas antes de exportar.');
        if(job.payload.op==='visual'&&job.result&&p.success){const result=job.result;if(S.clip&&job.payload.clipId&&S.clip.id===job.payload.clipId){edit(()=>{S.clip.visualReport=result.textPath;if(job.payload.mode!=='analysis'&&result.points?.length){const old=S.clip.tracking?.points||[],points=new Map([...old.filter(v=>v.time<job.payload.start||v.time>=job.payload.end),...result.points].map(v=>[v.time,v]));S.clip.tracking={points:[...points.values()].sort((a,b)=>a.time-b.time),ranges:[...(S.clip.tracking?.ranges||[]).filter(r=>r.uid!==job.payload.blockUid),{uid:job.payload.blockUid,start:job.payload.start,end:job.payload.end}],lost:result.lost,mode:job.payload.mode,format:result.format,sourceHash:result.source.sampleHash};}});if(S.clip.blocks.length)await save();}message(`Informe visual guardado. ${result.lost||0} muestras sin objetivo. ${result.points?.length?'Seguimiento aplicado a la ficha; revisa el preview.':'No se aplicó seguimiento.'}`);}
        if(job.payload.op==='export')message(job.result?.failed?.length?`Terminó con ${job.result.failed.length} fallo(s). Las exportaciones anteriores se conservaron.`:'Exportación terminada. Las versiones anteriores se conservaron.');
        if(job.payload.op==='visual'&&job.payload.mode==='analysis'&&job.result&&p.success){S.workspace.visual=job.result.path;await persistWorkspace();S.visualSamples=job.result.samples||[];renderScenes();showResult('Informe visual · Mostrar en Finder',job.result.textPath);}
        if(job.payload.op==='studio_context'&&p.success){showResult('Contexto TXT + JSON · Mostrar en Finder',job.result.path);message('Contexto guardado en CONTEXTO_IA: texto y evidencia visual disponible, sin subir ni copiar el video.');}
        if(job.payload.op==='studio_suggest'&&p.success){renderSuggestions(job.result.items||[]);message(job.result.limitations);}
        if(!p.success)message(p.detail||'Trabajo interrumpido. Puedes reintentar las fichas pendientes.');
        await syncLibrary();
        if(S.clip){const saved=S.clips.find(c=>c.id===S.clip.id);if(saved){S.clip.export=saved.export;S.clip.exportState=saved.exportState;}update();}
        if(job.payload.op==='import'&&p.success&&job.payload.exportAfterImport){const ids=job.result?.targetIds||[];if(ids.length)await jobExport(ids);else message('No hay fichas verificables para exportar. Revisa los avisos de importación.');}
      }catch(error){message(String(error));}finally{window.AbrxsProcesses?.finish(p.success&&!job.result?.failed?.length,p.detail||job.result?.failed?.map(f=>f.error).join('\n'));}
    }
  });
  el('launch').onclick=report(enter);
  el('close').onclick=report(async()=>{if(S.busy||S.saving)return;await flushDraft();await S.workspaceChain;stop();node.hidden=true;document.body.style.overflow='';});
  el('library').onclick=report(()=>showLibrary());el('new').onclick=report(()=>openClip());
  el('filter').oninput=renderLibrary;node.querySelectorAll('[data-view]').forEach(b=>b.onclick=report(async()=>{S.view=b.dataset.view;S.workspace.view=S.view;if(!S.busy&&!state.running)await persistWorkspace();renderLibrary();}));
  el('select-all').onclick=()=>{const list=filtered(),all=list.every(c=>S.selected.has(c.id));list.forEach(c=>all?S.selected.delete(c.id):S.selected.add(c.id));renderLibrary();};
  el('export-many').onclick=report(()=>job({op:'export',ids:[...S.selected],sections:el('sections').checked}));
  async function jobExport(ids){await job({op:'export',ids,sections:el('sections').checked});}
  el('import').onclick=report(async()=>{const path=await dialog.open({multiple:false,filters:[{name:'Decisiones',extensions:['json','html','htm','md','txt']}]});if(path){const plan=await window.AbrxsBatch.plan(path);if(plan)await job({op:'import',editorial:path,...plan});}});
    el('cache').onclick=report(async()=>{if(await ask('¿Eliminar solo la caché de esta etapa? Los originales, proyectos y exportaciones se conservan.')){await query({op:'clear_cache'});S.assets=null;message('Caché eliminada; puede regenerarse.');}});
  el('save').onclick=report(save);el('export').onclick=report(async()=>{const clip=await save();await job({op:'export',ids:[clip.id],sections:el('sections').checked});});
  el('title').onchange=()=>edit(()=>S.clip.title=el('title').value.trim()||'Nuevo clip');el('note').onchange=()=>edit(()=>S.clip.note=el('note').value);el('status').onchange=()=>edit(()=>S.clip.status=el('status').value);
  el('undo').onclick=()=>{if(!S.history.length)return;stop();S.future.push(clone(S.clip));const revision=S.clip.revision;S.clip=S.history.pop();S.clip.revision=revision;S.block=Math.min(S.block,S.clip.blocks.length-1);changed();};
  el('redo').onclick=()=>{if(!S.future.length)return;stop();S.history.push(clone(S.clip));const revision=S.clip.revision;S.clip=S.future.pop();S.clip.revision=revision;S.block=Math.min(S.block,S.clip.blocks.length-1);changed();};
  el('words').onpointerdown=async e=>{if(S.busy)return;const n=e.target.closest('[data-word]');if(!n)return;const i=Number(n.dataset.word);if(!e.shiftKey||S.anchor===null)S.anchor=i;S.focus=i;S.selecting=true;paintSelection();stop();const clipId=S.clip?.id;await setMaster();if(S.clip?.id!==clipId)return;const time=S.words[i].start;if(S.mode==='origin'){const context=Number(el('context').value)||5;S.originStart=Math.max(0,time-context);S.originSpan=Math.min(S.clip.duration-S.originStart,Math.max(10,context*2));fit();}seekVideo(time);playbackTick();};
  window.addEventListener('pointermove',e=>{if(node.hidden||S.busy)return;if(S.selecting){const n=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-word]');if(n&&el('words').contains(n)){S.focus=Number(n.dataset.word);paintSelection();}}if(S.drag){const d=S.drag;bounds(d.edge,d.value+(e.clientX-d.x)/d.scale,false);video.currentTime=current()[d.edge];}});
  window.addEventListener('pointerup',()=>{S.selecting=false;if(S.drag){if(el('snap').checked&&current()){const d=S.drag,points=S.words.map(w=>d.edge==='start'?w.start:w.end),value=current()[d.edge];if(points.length)bounds(d.edge,points.reduce((a,b)=>Math.abs(a-value)<Math.abs(b-value)?a:b),false);}S.drag=null;scheduleDraft();}});
  el('add').onclick=addSelection;el('preview-selection').onclick=()=>{const r=wordSelection();if(r)previewRange(S.words[r[0]].start,S.words[r[1]].end,'Selección del máster');};
  el('search').oninput=()=>{const text=C.token(el('search').value.trim()),tokens=text.split(/\s+/),words=S.words.map(w=>C.token(w.text).replace(/[^\p{L}\p{N}]/gu,'')),hits=new Set();if(text)for(let i=0;i<=words.length-tokens.length;i++)if(tokens.every((t,j)=>words[i+j].includes(t)))for(let j=0;j<tokens.length;j++)hits.add(i+j);el('words').querySelectorAll('[data-word]').forEach(n=>n.classList.toggle('hit',hits.has(Number(n.dataset.word))));el('words').querySelector('.hit')?.scrollIntoView({block:'center'});};
  el('play').onclick=()=>playSequence(0);el('rate').onchange=()=>video.playbackRate=Number(el('rate').value);
  el('context-in').onclick=()=>{const b=current();if(b)previewRange(b.start-Number(el('context').value),Math.min(b.end,b.start+Number(el('context').value)),'Contexto de entrada · zonas externas no incluidas');};
  el('context-out').onclick=()=>{const b=current();if(b)previewRange(Math.max(b.start,b.end-Number(el('context').value)),b.end+Number(el('context').value),'Contexto de salida · zonas externas no incluidas');};
  el('join').onclick=()=>{if(!current()||!S.clip.blocks[S.block+1])return;const index=S.block;playSequence(index);video.currentTime=Math.max(current().start,current().end-Number(el('context').value));};
  el('context').onchange=()=>{focusOrigin();renderTimeline();};
  el('in').onchange=()=>bounds('start',Number(el('in').value));el('out').onchange=()=>bounds('end',Number(el('out').value));
  node.querySelectorAll('[data-nudge]').forEach(n=>n.onclick=()=>{const [edge,delta]=n.dataset.nudge.split(':');if(current())bounds(edge,current()[edge]+Number(delta));});
  node.querySelectorAll('[data-frame]').forEach(n=>n.onclick=report(async()=>{const [edge,direction]=n.dataset.frame.split(':'),b=current();if(!b)return;const uid=b.uid;const result=await query({op:'frame',video:S.clip.source.path,at:b[edge],direction:Number(direction)});if(current()?.uid===uid)bounds(edge,result.time);}));
  el('split').onclick=report(()=>{const b=current(),t=video.currentTime;if(!b||S.sourceOnly||t<=b.start||t>=b.end)throw Error('Coloca el cabezal dentro del bloque sobre el máster.');edit(()=>S.clip.blocks.splice(S.block,1,{...b,end:t,text:textFor(b.start,t)},{...b,uid:C.uid(),start:t,text:textFor(t,b.end)}));});
  el('merge').onclick=report(()=>{const merged=C.merge(S.clip.blocks,S.block);edit(()=>S.clip.blocks=merged);});
  el('duplicate').onclick=()=>{if(current())edit(()=>S.clip.blocks.splice(S.block+1,0,{...clone(current()),uid:C.uid()}));};
  el('remove').onclick=()=>{if(current())edit(()=>{S.clip.blocks.splice(S.block,1);S.block=Math.max(0,Math.min(S.block,S.clip.blocks.length-1));});};
  el('add-range').onclick=()=>{if(S.sourceOnly){message('Vuelve al máster antes de crear un rango.');return;}edit(()=>{const start=Math.min(video.currentTime,S.clip.duration-.01),end=Math.min(S.clip.duration,start+5);S.clip.blocks.push({uid:C.uid(),start,end,text:textFor(start,end),role:'SECCION'});S.block=S.clip.blocks.length-1;});};
  for(const name of ['aspect','crop-mode','x','y'])el(name).onchange=()=>edit(()=>S.clip.format={aspect:el('aspect').value,mode:el('crop-mode').value,x:Number(el('x').value),y:Number(el('y').value)});
  el('origin-mode').onclick=()=>{S.mode='origin';focusOrigin();fit();};el('montage-mode').onclick=()=>{S.mode='montage';fit();};el('fit').onclick=fit;el('full').onclick=()=>{S.mode='origin';S.originStart=0;S.originSpan=S.clip.duration;fit();};
  el('zoom').oninput=()=>{const span=S.mode==='origin'?S.originSpan:Math.max(1,C.duration(S.clip.blocks)),fitScale=(el('scroll').clientWidth-30)/span;S.scale=Math.max(.01,fitScale*Math.pow(2,(Number(el('zoom').value)-50)/12));renderTimeline();};
  el('track').onclick=async e=>{if(e.target.closest('.ac-range')||!S.clip||S.busy)return;const x=e.clientX-el('track').getBoundingClientRect().left,time=S.mode==='origin'?Math.min(S.clip.duration,S.originStart+x/S.scale):null,hit=time===null?C.toSource(S.clip.blocks,x/S.scale):null,id=S.clip.id;stop();await setMaster();if(S.clip?.id!==id)return;if(time!==null)seekVideo(time);else if(hit){S.block=hit.index;seekVideo(hit.time);}playbackTick();};
  el('assets').onclick=report(()=>job({op:'assets',video:S.clip.source.path,transcript:S.clip.transcript}));el('relink').onclick=report(relink);
  el('caption-mode').onchange=()=>edit(()=>S.clip.captions={mode:el('caption-mode').value,style:S.clip.captions?.style||clone(defaultCaptionStyle)});
  el('caption-style').onclick=report(async()=>{const path=await dialog.open({multiple:false,filters:[{name:'Estilo captions JSON',extensions:['json']}]});if(!path)return;const result=await query({op:'caption_style',path});edit(()=>S.clip.captions={mode:S.clip.captions?.mode||'sidecar',style:result});});
  el('visual').onclick=report(async()=>{if(S.clip.blocks.length)await save();await job({op:'visual',clipId:S.clip.id,video:S.clip.source.path,transcript:S.clip.transcript,mode:'analysis',step:5,format:S.clip.format});});
  el('visual-report').onclick=report(()=>api.invoke('reveal_path',{path:S.clip.visualReport}));
  el('track-subject').onclick=report(async()=>{const b=current();if(!b||S.clip.format.aspect==='original'||S.clip.format.mode!=='cover')throw Error('Selecciona un bloque y un formato vertical/horizontal/cuadrado con Recortar para llenar.');if(S.clip.tracking?.format?.aspect&&S.clip.tracking.format.aspect!==S.clip.format.aspect)throw Error('Quita el seguimiento anterior antes de calcularlo para otro formato.');const rect=el('object-rect').value.split(',').map(Number);await save();await job({op:'visual',clipId:S.clip.id,blockUid:b.uid,video:S.clip.source.path,transcript:S.clip.transcript,mode:el('track-mode').value,rect,start:b.start,end:b.end,step:.5,format:S.clip.format});});
  el('disable-track').onclick=()=>edit(()=>S.clip.tracking=null);
  el('approve').onclick=report(async()=>{edit(()=>S.clip.status='approved');await save();});
  async function navigate(delta){await save();const index=S.clips.findIndex(c=>c.id===S.clip.id),target=S.clips[index+delta];if(target)await openClip(target,true);}
  el('prev').onclick=report(()=>navigate(-1));el('next').onclick=report(()=>navigate(1));
  el('final').onclick=report(async()=>{if(!S.clip.export?.path)return;stop();S.sourceOnly=true;if(window.AbrxsMedia)await window.AbrxsMedia.attach(video,S.clip.export.path);else video.src=api.convertFileSrc(S.clip.export.path);video.style.objectFit='contain';el('preview-label').textContent='MP4 exportado (puede ser una revisión anterior)';video.play().catch(e=>message(e.message));});el('master').onclick=report(async()=>{stop();await setMaster();seekVideo(current()?.start||0);el('preview-label').textContent='Máster original';});
  el('cancel').onclick=report(async()=>{el('cancel').disabled=true;await api.invoke('cancel_job');el('job-detail').textContent='Cancelando; conservando versiones anteriores…';});
  window.addEventListener('keydown',e=>{if(node.hidden)return;const typing=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);if(e.key==='Escape'&&!S.busy)el('close').click();if(e.code==='Space'&&!typing&&S.clip){e.preventDefault();S.playing?stop():playSequence(0);}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'&&!typing&&!S.busy){e.preventDefault();el(e.shiftKey?'redo':'undo').click();}});
  function persistWorkspace(){
    if(!S.project)return Promise.resolve();
    const request={op:'studio_save',projectPath:S.project.path,workspace:clone(S.workspace)};
    S.workspacePending++;
    S.workspaceChain=S.workspaceChain.catch(()=>{}).then(()=>api.invoke('stage1_query',{request})).finally(()=>S.workspacePending--);
    return S.workspaceChain;
  }
  function showResult(label,path){
    if(!path)return;const button=document.createElement('button');button.textContent=label;
    button.onclick=report(()=>api.invoke('show_in_finder',{path}));el('result-links').append(button);
    const inside=button.cloneNode(true);inside.onclick=button.onclick;el('message').append(document.createElement('br'),inside);
  }
  function renderTray(){
    const items=S.workspace.fragments.filter(f=>!S.clip||f.sourceHash===S.clip.source.sampleHash);
    el('tray').innerHTML=items.length?items.map(f=>`<article class="ac-fragment"><small>${preciseTime(f.start)} → ${preciseTime(f.end)}</small><p>${esc(f.text||'Fragmento manual')}</p><div class="ac-actions"><button data-tray-add="${esc(f.id)}">Añadir al montaje</button><button data-tray-play="${esc(f.id)}">Escuchar</button><button data-tray-remove="${esc(f.id)}">Quitar de bandeja</button></div></article>`).join(''):'<p class="ac-empty">Guarda una selección de texto o el bloque actual. La bandeja pertenece a este proyecto y cada fragmento conserva su máster.</p>';
    const find=id=>S.workspace.fragments.find(f=>f.id===id);
    el('tray').querySelectorAll('[data-tray-add]').forEach(b=>b.onclick=()=>{const f=find(b.dataset.trayAdd);if(!S.clip||f.sourceHash!==S.clip.source.sampleHash)return;edit(()=>{S.clip.blocks.push({uid:C.uid(),start:f.start,end:f.end,text:f.text,role:'SECCION'});S.block=S.clip.blocks.length-1;});});
    el('tray').querySelectorAll('[data-tray-play]').forEach(b=>b.onclick=()=>{const f=find(b.dataset.trayPlay);previewRange(f.start,f.end,'Fragmento de bandeja');});
    el('tray').querySelectorAll('[data-tray-remove]').forEach(b=>b.onclick=report(async()=>{S.workspace.fragments=S.workspace.fragments.filter(f=>f.id!==b.dataset.trayRemove);await persistWorkspace();renderTray();}));
  }
  function renderScenes(){
    el('scenes').innerHTML='<p>Fotogramas muestreados con detecciones locales. No identifica acciones, hablantes ni límites exactos de escenas.</p>'+S.visualSamples.map((s,i)=>`<article class="ac-fragment"><button data-scene="${i}">▶ ${preciseTime(s.time)}</button><p>${s.faces?.length||0} rostros · ${s.bodies?.length||0} cuerpos</p><p>${esc((s.text||[]).map(t=>t.text).join(' · ')||'Sin texto visible detectado')}</p></article>`).join('');
    if(!S.visualSamples.length)el('scenes').innerHTML+='<p>Analiza el máster desde Preparar o desde Vision en el inspector.</p>';
    el('scenes').querySelectorAll('[data-scene]').forEach(b=>b.onclick=()=>previewRange(S.visualSamples[Number(b.dataset.scene)].time,S.visualSamples[Number(b.dataset.scene)].time+5,'Muestra visual del máster'));
  }
  function renderSuggestions(items){
    el('suggestions').innerHTML=items.length?items.map((f,i)=>`<article class="ac-fragment"><small>${preciseTime(f.start)} → ${preciseTime(f.end)}</small><p>${esc(f.text.slice(0,240))}</p><small>${esc(f.reason)}</small><button data-suggestion="${i}">Guardar en bandeja</button></article>`).join(''):'<p>No hay propuestas. Necesitas una transcripción con timestamps.</p>';
    el('suggestions').querySelectorAll('[data-suggestion]').forEach(b=>b.onclick=report(async()=>{const f=items[Number(b.dataset.suggestion)];S.workspace.fragments.push({id:C.uid(),start:f.start,end:f.end,text:f.text,sourceHash:S.clip.source.sampleHash});await persistWorkspace();renderTray();b.disabled=true;b.textContent='Guardado';}));
  }
  function renderMap(list){
    el('cards').className='ac-map-shell';
    const visible=list.slice(0,150),nodes=[],edges=[],sources=new Map();
    visible.forEach((c,i)=>{
      const key='source-'+c.source.sampleHash;if(!sources.has(key)){sources.set(key,sources.size);nodes.push({key,x:24,y:24+sources.size*180,kind:'master',html:`<small>MÁSTER</small><h3>${esc(basename(c.source.path))}</h3><button data-path="${esc(c.source.path)}">Mostrar en Finder</button>`});}
      const y=24+i*350,id='clip-'+c.id;
      nodes.push({key:id,x:350,y,kind:'clip',html:card(c)});edges.push([key,id]);
      const transcript='text-'+c.id;
      nodes.push({key:transcript,x:700,y,kind:'text',html:`<small>TEXTO · TIEMPOS DEL MÁSTER</small><details><summary>${c.blocks.length} fragmentos · Ver transcripción</summary>${c.blocks.map(b=>`<p><button data-seek-clip="${esc(c.id)}" data-seek-time="${b.start}">${preciseTime(b.start)} → ${preciseTime(b.end)}</button><br>${esc(b.text||'Sin texto alineado')}</p>`).join('')}</details>`});edges.push([id,transcript]);
      const versions=[...(c.exportHistory||[]),...(c.export?[c.export]:[])];
      if(versions.length){const out='export-'+c.id;nodes.push({key:out,x:1040,y,kind:'export',html:`<small>ARCHIVOS EXPORTADOS</small><h3>${versions.length} versión(es)</h3>${versions.map(v=>`<p>Revisión ${v.revision||'—'}<br><button data-path="${esc(v.path)}">Mostrar MP4</button><button data-path="${esc(v.path.replace(/\.mp4$/i,'.txt'))}">TXT</button></p>`).join('')}<button data-export-play="${esc(c.id)}">▶ Último MP4</button>`});edges.push([id,out]);}
    });
    for(const n of nodes)Object.assign(n,S.workspace.positions[n.key]||{});
    const width=Math.max(1380,...nodes.map(n=>n.x+340)),height=Math.max(500,...nodes.map(n=>n.y+300));
    el('cards').innerHTML=`<div class="ac-map-controls"><strong>Mapa del proyecto</strong><span>Máster → clips → texto y exportaciones</span><button id="ac-map-order">Ordenar mapa</button><label>Zoom <input id="ac-map-zoom" type="range" min="50" max="125" value="100"></label><small>${list.length>150?'Se muestran los primeros 150 resultados; usa buscar para acotar.':'Arrastra la cabecera de un nodo. Abre un clip para reproducir: un solo visor activo.'}</small></div><div class="ac-map-viewport"><div id="ac-map-space" style="width:${width}px;height:${height}px"><svg id="ac-map-lines" width="${width}" height="${height}" aria-hidden="true"></svg>${nodes.map(n=>`<section class="ac-map-node ac-map-${n.kind}" data-node="${esc(n.key)}" style="left:${n.x}px;top:${n.y}px"><div class="ac-node-grip" tabindex="0" role="button" aria-label="Mover nodo con flechas" data-grip="${esc(n.key)}">⋮⋮ ${n.kind==='master'?'Máster':n.kind==='clip'?'Clip':n.kind==='text'?'Transcripción':'Exportaciones'}</div>${n.html}</section>`).join('')}</div></div>`;
    const lookup=new Map(nodes.map(n=>[n.key,n]));
    const draw=()=>{const w=Math.max(1380,...nodes.map(n=>n.x+340)),h=Math.max(500,...nodes.map(n=>n.y+350));el('map-space').style.width=w+'px';el('map-space').style.height=h+'px';el('map-lines').setAttribute('width',w);el('map-lines').setAttribute('height',h);el('map-lines').innerHTML=edges.map(([a,b])=>{const from=lookup.get(a),to=lookup.get(b);return `<path d="M ${from.x+290} ${from.y+70} C ${from.x+330} ${from.y+70}, ${to.x-40} ${to.y+70}, ${to.x} ${to.y+70}"/>`;}).join('');};draw();
    el('map-order').onclick=report(async()=>{S.workspace.positions={};await persistWorkspace();renderLibrary();});
    if(window.Panzoom){mapPan=window.Panzoom(el('map-space'),{minScale:.5,maxScale:1.25,excludeClass:'ac-map-node'});el('map-space').parentElement.addEventListener('wheel',e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();mapPan?.zoomWithWheel(e);}},{passive:false});}
    el('map-zoom').oninput=()=>{const z=Number(el('map-zoom').value)/100;if(mapPan)mapPan.zoom(z);else el('map-space').style.zoom=z;};
    el('cards').querySelectorAll('[data-grip]').forEach(grip=>{
      const n=nodes.find(n=>n.key===grip.dataset.grip),element=grip.parentElement;let drag=null;
      const move=(x,y)=>{n.x=Math.max(0,x);n.y=Math.max(0,y);element.style.left=n.x+'px';element.style.top=n.y+'px';draw();};
      grip.onpointerdown=e=>{if(S.busy)return;e.preventDefault();e.stopPropagation();const z=mapPan?.getScale()||Number(el('map-zoom').value)/100;drag={x:e.clientX,y:e.clientY,nx:n.x,ny:n.y,z};grip.setPointerCapture(e.pointerId);};
      grip.onpointermove=e=>{if(drag)move(drag.nx+(e.clientX-drag.x)/drag.z,drag.ny+(e.clientY-drag.y)/drag.z);};
      const savePosition=report(async()=>{S.workspace.positions[n.key]={x:n.x,y:n.y};await persistWorkspace();});
      grip.onpointerup=()=>{if(drag){drag=null;savePosition();}};grip.onpointercancel=()=>{drag=null;};
      grip.onkeydown=e=>{const shifts={ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]};if(shifts[e.key]&&!S.busy){e.preventDefault();move(n.x+shifts[e.key][0],n.y+shifts[e.key][1]);savePosition();}};
    });
    el('cards').querySelectorAll('[data-path]').forEach(b=>b.onclick=report(()=>api.invoke('show_in_finder',{path:b.dataset.path})));
    el('cards').querySelectorAll('[data-seek-clip]').forEach(b=>b.onclick=report(()=>{const c=S.clips.find(c=>c.id===b.dataset.seekClip);return previewLibrary(c,c.blocks.findIndex(block=>block.start===Number(b.dataset.seekTime)));}));
    el('cards').querySelectorAll('[data-export-play]').forEach(b=>b.onclick=report(()=>previewLibrary(S.clips.find(c=>c.id===b.dataset.exportPlay),0,true)));
  }
  el('store').onclick=report(async()=>{const r=wordSelection(),b=current();if(!r&&!b)throw Error('Selecciona texto o crea un bloque para guardar.');const start=r?S.words[r[0]].start:b.start,end=r?S.words[r[1]].end:b.end;S.workspace.fragments.push({id:C.uid(),start,end,text:textFor(start,end),sourceHash:S.clip.source.sampleHash});await persistWorkspace();renderTray();message('Fragmento guardado en la bandeja de este proyecto.');});
  node.querySelectorAll('[data-pane]').forEach(b=>b.onclick=report(async()=>{for(const name of ['words','scenes','tray'])el(name).hidden=name!==b.dataset.pane;if(b.dataset.pane==='tray')renderTray();if(b.dataset.pane==='scenes'){const result=await query({op:'studio_visual',video:S.clip.source.path});S.visualSamples=result.samples||[];renderScenes();}}));
  el('focus').onclick=()=>{node.classList.toggle('ac-focus-mode');el('focus').setAttribute('aria-pressed',String(node.classList.contains('ac-focus-mode')));};
  el('create-entry').onclick=report(async()=>{await enter();await openClip();});
  el('prepare-visual').onclick=report(async()=>{await enter();await job({op:'visual',video:state.video,transcript:state.transcript,mode:'analysis',step:5,format:{aspect:'original',mode:'contain',x:.5,y:.5}});});
  el('context-export').onclick=report(async()=>{await enter();await job({op:'studio_context',brand:state.brand,structure:state.structure});});
  el('project-files').onclick=report(()=>api.invoke('reveal_path',{path:state.project.path}));
  el('suggest').onclick=report(()=>job({op:'studio_suggest',video:S.clip.source.path,transcript:S.clip.transcript,seconds:Number(el('target-length').value),keywords:el('keywords').value}));
  $('openEditorBtn').onclick=report(async()=>{await enter();await openClip();});
  const originalRenderWords=renderWords;
  renderWords=function(){originalRenderWords();S.activeWord=-1;renderTray();};
  window.AbrxsStudio={
    async evidence(){if(!state.project||!state.video)return {samples:[]};return api.invoke('stage1_query',{request:{op:'studio_visual',projectPath:state.project.path,video:state.video}});},
    async importPrepared(editorial,plan={}){await enter();await job({op:'import',editorial,...plan});},
    async prepare(kind){if(!state.project||!state.video)throw Error('Selecciona primero el video máster.');if(S.project?.id!==state.project.id)reset(state.project);await syncLibrary();await job(kind==='visual'?{op:'visual',video:state.video,transcript:state.transcript,mode:'analysis',step:5,format:{aspect:'original',mode:'contain',x:.5,y:.5}}:{op:'studio_context',brand:state.brand,structure:state.structure});},
    async review(){await enter();},
    async create(){if(node.hidden)await enter();await openClip();},
    async leave(){if(S.busy||S.saving||state.running)throw Error('Espera o cancela el trabajo activo.');await flushDraft();await S.workspaceChain;stop();stopLibrary(true);node.hidden=true;document.body.style.overflow='';},
    get busy(){return S.busy||S.saving||state.running;}
  };
  window.addEventListener('beforeunload',e=>{if(S.dirty||S.busy||S.workspacePending){e.preventDefault();e.returnValue='';}});
  window.AbrxsProcesses?.register(async task=>{if(state.project?.id!==task.projectId)throw Error('Abre el proyecto de este proceso antes de continuar.');if(S.project?.id!==state.project.id)reset(state.project);await job(task.payload,true);});
  const exportActive=document.createElement('button');exportActive.textContent='Exportar activas pendientes';exportActive.id='ac-export-active';el('export-many').after(exportActive);exportActive.onclick=report(()=>jobExport(S.clips.filter(c=>c.status!=='draft'&&c.exportState!=='exported').map(c=>c.id)));
  const approveBounds=document.createElement('button');approveBounds.textContent='Confirmar límites revisados';el('save').after(approveBounds);approveBounds.onclick=report(async()=>{if(!S.clip||S.busy)return;if(await ask('¿Has reproducido y comprobado el inicio y el final de todos los bloques? Esto confirma revisión manual, no verificación automática del texto.')){edit(()=>{S.clip.boundariesReviewed=true;});await save();}});
})();
