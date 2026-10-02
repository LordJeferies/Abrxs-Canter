/* UX 3.6: one workspace, three routes, no additional render/model services. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), studio=$('ac-studio'), shell=document.querySelector('.shell');
  document.body.classList.add('ux-app');
  const side=document.createElement('aside');side.className='ux-sidebar';
  side.innerHTML='<button class="ux-brand" id="ux-home"><span>AC</span><strong>Abrxs Canter<small>ESTUDIO · UX 3.6</small></strong></button><small class="ux-section">ESPACIO DE TRABAJO</small><button data-route="home">▦ Biblioteca</button><div class="ux-divider"></div><small id="ux-project">Selecciona un proyecto</small><nav aria-label="Flujo del proyecto"><button data-route="prepare"><i>01</i> Preparar</button><button data-route="create"><i>02</i> Crear</button><button data-route="review"><i>03</i> Revisar</button></nav><div class="ux-sidebar-bottom"><button id="ux-files">↗ Archivos del proyecto</button><small>Local · Originales intactos</small></div>';
  document.body.prepend(side);
  const iconNames={home:'folder-open',prepare:'clapperboard',create:'scissors',review:'layout-grid'};
  side.querySelectorAll('[data-route]').forEach(b=>{const svg=window.AbrxsIcons?.[iconNames[b.dataset.route]];if(svg){const label={home:'Biblioteca',prepare:'Preparar',create:'Crear',review:'Revisar'}[b.dataset.route];b.innerHTML=svg+'<span>'+label+'</span>';b.querySelector('svg').setAttribute('aria-hidden','true');}});
  shell.append(studio);
  const feedback=document.createElement('div');feedback.className='ux-feedback';shell.insertBefore(feedback,$('studioView'));feedback.append($('ac-message'),$('ac-progress'));
  const execution=document.createElement('details');execution.className='ux-execution';execution.innerHTML='<summary>Detalles de ejecución</summary>';execution.append($('progressPanel'));feedback.append(execution);
  const hero=document.querySelector('.welcome-hero');hero.innerHTML='<p class="eyebrow">TU BIBLIOTECA</p><h2>Proyectos</h2><p>Un espacio independiente para cada máster, sus transcripciones y sus clips.</p>';
  document.querySelector('.recent-projects-card h3').textContent='Recientes';
  document.querySelector('.new-project-card h3').textContent='Nuevo proyecto';
  const workspace=document.querySelector('#studioView .workspace'), preview=document.createElement('section');
  preview.className='ux-master panel';preview.innerHTML='<div class="ux-master-head"><span>MÁSTER ORIGINAL</span><small>Vista previa de la fuente</small></div><div class="ux-master-screen"><video id="ux-master-video" controls preload="metadata" playsinline hidden></video><div id="ux-master-empty"><strong>Tu historia empieza con un video</strong><p>Selecciona el máster. Si no tienes transcripción, la creamos aquí.</p><button id="ux-choose-video">Elegir video</button></div></div><div class="ux-flow"><span>1 · Video</span><span>2 · Texto y evidencia visual</span><span>3 · Clips revisables</span></div>';
  workspace.append(preview);$('ux-choose-video').onclick=()=>$('videoBtn').click();
  const setup=document.querySelector('.setup-panel'), context=document.querySelector('.ac-preparation');
  preview.after(context);
  const references=document.createElement('div');references.className='ux-references';references.innerHTML='<div><strong>Referencias del análisis</strong><button id="ux-refresh-evidence">Ver momentos analizados</button></div><div id="ux-evidence"></div><small id="ux-reference-label">Selecciona un momento para reproducir solo ese tramo del máster.</small>';context.append(references);
  let previewEnd=null;
  async function loadEvidence(){
    const videoPath=state.video,projectId=state.project?.id;if(!videoPath)return;
    const result=await window.AbrxsStudio.evidence();if(state.video!==videoPath||state.project?.id!==projectId)return;
    const list=$('ux-evidence');list.innerHTML='';
    if(!result.samples?.length){list.textContent=result.limitations||'Todavía no hay evidencia visual de este máster. Ejecuta Analizar visualmente.';return;}
    result.samples.slice(0,600).forEach(s=>{const b=document.createElement('button');b.textContent=preciseTime(s.time)+' · '+(s.faces?.length||0)+' rostros · '+(s.bodies?.length||0)+' cuerpos';b.onclick=()=>{const v=$('ux-master-video');v.pause();previewEnd=Number(s.time)+5;v.currentTime=Math.max(0,Number(s.time));$('ux-reference-label').textContent='Reproduciendo referencia '+preciseTime(s.time)+' → '+preciseTime(previewEnd)+' (hasta 5 s, sin modificar cortes).';v.play().catch(error);};list.append(b);});
  }
  $('ux-refresh-evidence').onclick=()=>loadEvidence().catch(error);
  $('ux-master-video').addEventListener('timeupdate',()=>{const v=$('ux-master-video');if(previewEnd!==null&&v.currentTime>=previewEnd){v.pause();previewEnd=null;}});
  const fullSource=document.createElement('button');fullSource.textContent='Ver máster completo';fullSource.onclick=()=>{previewEnd=null;$('ux-reference-label').textContent='Reproducción libre del máster.';};references.append(fullSource);
  const optional=document.createElement('details');optional.className='ux-optional';optional.innerHTML='<summary>Marca y estructura · opcional</summary><p>Contexto editorial para el paquete IA. Las propuestas locales usan reglas y palabras clave, no un modelo semántico.</p>';
  setup.insertBefore(optional,setup.querySelector('.options-grid'));
  ['brand','structure'].forEach(key=>optional.append(setup.querySelector('[data-key="'+key+'"]')));
  const advanced=document.createElement('details');advanced.className='ux-advanced panel';advanced.innerHTML='<summary>Herramientas de compatibilidad · cortes y resultados anteriores</summary>';
  $('studioView').append(advanced);
  ['.inventory-panel','#reviewPanel','#manualPanel'].forEach(sel=>advanced.append(document.querySelector(sel)));
  advanced.append(setup.querySelector('.mode-switch'),setup.querySelector('.options-grid'));
  const cuts=setup.querySelector('#editorialField');cuts.classList.remove('hidden');setup.insertBefore(cuts,setup.querySelector('.ux-optional'));cuts.querySelector('label').textContent='Cortes definidos · opcional';
  const flowHint=document.createElement('p');flowHint.className='ux-flow-hint';flowHint.textContent='Puedes cargar el video y los cortes juntos. Primero se prepara el texto; después se organizan fichas para revisar. No se exporta automáticamente.';setup.insertBefore(flowHint,$('startBtn'));
  const health=document.createElement('p');health.id='ux-health';health.className='ux-flow-hint';setup.insertBefore(health,$('startBtn'));
  const transcript=setup.querySelector('[data-key="transcript"] label');transcript.innerHTML='Transcripción existente <b>OPCIONAL</b>';
  document.querySelector('.setup-panel .panel-head h3').textContent='Fuentes del proyecto';
  document.querySelector('.ac-preparation h3').textContent='Análisis y contexto';
  document.querySelector('.ac-preparation p').textContent='Después de transcribir, detecta rostros, cuerpos y texto visible. Exporta el contexto para tu chat; no se sube el video.';
  $('ac-close').textContent='← Preparar';$('ac-library').textContent='← Fichas';
  $('ac-prepare-visual').onclick=()=>window.AbrxsStudio.prepare('visual').catch(error);
  $('ac-context-export').onclick=()=>window.AbrxsStudio.prepare('context').catch(error);
  let split=null, route='home',lastVideo=null, busyRoute=false;
  const error=e=>{const box=$('ac-message');box.textContent=String(e.message||e);window.AbrxsActivity?.add('Error',box.textContent,true);};
  function updateSource(){
    const video=$('ux-master-video'),empty=$('ux-master-empty');
    if(state.video!==lastVideo){previewEnd=null;$('ux-evidence').textContent='';$('ux-reference-label').textContent='Selecciona un momento para reproducir solo ese tramo del máster.';if(window.AbrxsMedia)window.AbrxsMedia.attach(video,state.video).catch(error);else{video.pause();video.removeAttribute('src');if(state.video)video.src=window.__TAURI__.core.convertFileSrc(state.video);video.load();}lastVideo=state.video;}
    video.hidden=!state.video;empty.hidden=!!state.video;
    $('ux-project').textContent=state.project?.name||'Selecciona un proyecto';
    side.querySelectorAll('nav button').forEach(b=>b.disabled=!state.project);
    $('ux-files').disabled=!state.project;
    const signature=[state.project?.id,state.video,state.transcript,state.outputResult,state.project?.lastOutput].join('|');
    if(state.video&&state.project&&health.dataset.source!==signature){health.dataset.source=signature;health.textContent='Comprobando fuente y transcripción…';window.__TAURI__.core.invoke('stage1_query',{request:{op:'source',projectPath:state.project.path,outputPath:state.outputResult||state.project.lastOutput,video:state.video,transcript:state.transcript}}).then(data=>{if(health.dataset.source!==signature)return;health.textContent=`Fuente accesible · ${data.media.width}×${data.media.height} · ${Math.round(data.media.duration/60)} min. `+(data.words?.length?`${data.words.length.toLocaleString('es')} palabras con tiempos cargadas; no hace falta repetir la transcripción.`:'Sin palabras con tiempos: prepara o importa la transcripción para verificar cortes.');}).catch(e=>{if(health.dataset.source===signature)health.textContent='Comprobación: '+String(e);});}
  }
  function routePaint(next){
    route=next;document.body.dataset.route=next;
    side.querySelectorAll('[data-route]').forEach(b=>{b.classList.toggle('active',b.dataset.route===next);if(b.dataset.route===next)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    if(next!=='prepare')$('ux-master-video').pause();
    updateSource();resizePanels();
  }
  function resizePanels(){
    const editor=$('ac-editor'),focus=studio.classList.contains('ac-focus-mode');
    if(editor.hidden||studio.hidden||focus){if(split){split.destroy();split=null;}return;}
    if(split||!window.Split)return;
    let sizes=[28,44,28];try{const saved=JSON.parse(localStorage.getItem('abrxs-ux-panels'));if(Array.isArray(saved)&&saved.length===3&&saved.every(n=>Number.isFinite(n)&&n>=15)&&Math.abs(saved.reduce((a,b)=>a+b,0)-100)<1)sizes=saved;}catch{}
    split=window.Split([editor.querySelector('.ac-transcript'),editor.querySelector('.ac-preview'),editor.querySelector('.ac-blocks')],{sizes,minSize:[180,240,200],gutterSize:8,onDragEnd:values=>{try{localStorage.setItem('abrxs-ux-panels',JSON.stringify(values));}catch{}}});
    editor.querySelectorAll('.gutter').forEach((g,i)=>{g.tabIndex=0;g.setAttribute('role','separator');g.setAttribute('aria-label','Ajustar ancho de panel');g.setAttribute('aria-orientation','vertical');g.onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const s=split.getSizes(),d=e.key==='ArrowLeft'?-2:2;s[i]+=d;s[i+1]-=d;if(s[i]>=18&&s[i+1]>=18)split.setSizes(s);};});
  }
  async function go(next){
    if(busyRoute)return;busyRoute=true;
    try{
      if(next==='home'){await showWelcome();if(state.project)return;routePaint('home');}
      else if(state.project){
        if(next==='prepare'){await window.AbrxsStudio.leave();setMode('prepare');routePaint('prepare');}
        else {if(next==='create')await window.AbrxsStudio.create();else await window.AbrxsStudio.review();routePaint(next);}
      }
    }catch(e){error(e);}finally{busyRoute=false;}
  }
  side.querySelectorAll('[data-route]').forEach(b=>b.onclick=()=>go(b.dataset.route));
  $('ux-home').onclick=()=>go('home');$('ux-files').onclick=()=>$('revealProjectBtn').click();
  const previousOpen=openProject;openProject=async function(project){await previousOpen(project);if(state.project?.id===project.id){setMode('prepare');routePaint('prepare');}};
  const previousPath=setPath;setPath=function(...args){const result=previousPath(...args);updateSource();if(args[0]==='editorial'&&state.mode==='prepare')$('startLabel').textContent=state.editorial?'Preparar y organizar cortes':'Crear transcripciones y paquete IA';return result;};
  const previousStartState=updateStartState;updateStartState=function(){previousStartState();if(window.AbrxsStudio.busy)$('startBtn').disabled=true;};
  const previousMode=setMode;setMode=function(...args){const result=previousMode(...args);cuts.classList.remove('hidden');if(state.mode==='prepare')$('startLabel').textContent=state.editorial?'Preparar y organizar cortes':'Crear transcripciones y paquete IA';return result;};
  const previousStart=startJob;let pendingCuts=null;
  startJob=async function(){pendingCuts=null;if(state.editorial){const options=await window.AbrxsBatch.plan(state.editorial);if(!options)return;setMode('prepare');if(state.transcript||state.outputResult||state.project?.lastOutput){await window.AbrxsStudio.importPrepared(state.editorial,options);return;}pendingCuts={path:state.editorial,projectId:state.project?.id,options};}if(state.running||window.AbrxsStudio.busy){window.AbrxsActivity?.add('Trabajo activo','Preparación en curso. Puedes revisar las fichas y añadir exportaciones a Procesos.');return;}window.AbrxsActivity?.add('Inicio',state.editorial?'Preparar máster y organizar cortes':'Preparar máster');await previousStart();};
  $('startBtn').onclick=startJob;
  const previousFinish=finishJob;finishJob=function(success,message){
    previousFinish(success,message);window.AbrxsActivity?.add(success?'Terminado':'Error',message||'Sin detalle recibido del motor',!success);
    if(!success){$('globalBar').parentElement.classList.remove('indeterminate');$('ac-message').textContent=message||'No se recibió detalle del error. Abre Actividad.';}
    const plan=pendingCuts;pendingCuts=null;
    if(success&&plan&&plan.projectId===state.project?.id&&state.outputResult){
      (async()=>{await persistProject(state.outputResult);await window.AbrxsStudio.importPrepared(plan.path,plan.options);})().catch(error);
    }
  };
  $('ac-close').onclick=()=>go('prepare');
  window.addEventListener('abrxs-route',e=>routePaint(e.detail));
  new MutationObserver(()=>{
    if(!studio.hidden)routePaint($('ac-editor').hidden?'review':'create');
    else if(state.project)routePaint('prepare');else routePaint('home');
  }).observe(studio,{attributes:true,attributeFilter:['hidden','class'],subtree:true});
  $('ux-master-video').onerror=()=>{const empty=$('ux-master-empty');empty.hidden=false;empty.querySelector('strong').textContent='Este video no pudo reproducirse';empty.querySelector('p').textContent='Comprueba el archivo o usa una copia compatible. El máster no se modifica.';};
  window.addEventListener('resize',()=>{if(split){split.destroy();split=null;}resizePanels();});
  routePaint('home');
  window.AbrxsProcesses?.mount();
})();
