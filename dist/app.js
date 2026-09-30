const { invoke, convertFileSrc } = window.__TAURI__.core;
const { open } = window.__TAURI__.dialog;
const { listen } = window.__TAURI__.event;

const state = {
  project: null, projects: [], mode: 'prepare', editorial: null, video: null,
  transcript: null, brand: null, structure: null, output: null, pieces: [],
  running: false, startedAt: null, pieceStartedAt: null, currentPiece: 0,
  totalPieces: 0, outputResult: null, timer: null, reviews: { videos: {} },
  selectedVideo: null, reviewStatus: 'pending', phrases: [], manualSegments: [],
  editorOutput: null, editorData: null, editorBlocks: [], selectedBlock: -1,
  selectionAnchor: null, selectionFocus: null, selectingWords: false,
  editorHistory: [], editorFuture: [], editorActiveBlock: -1, editorPlaying: false,
  previewRangeEnd: null, timelineZoom: 28, editorSaveTimer: null,
  searchHits: [], searchHitIndex: -1, timelineDrag: null
};

const $ = id => document.getElementById(id);
const refs = { editorial: $('editorialPath'), video: $('videoPath'), transcript: $('transcriptPath'), brand: $('brandPath'), structure: $('structurePath') };
const defaults = { editorial: 'HTML, JSON, Markdown o TXT', video: 'Video original del episodio', transcript: 'Si falta, se genera con MLX Whisper', brand: 'Voz, audiencia, límites y objetivos', structure: 'Reglas y formatos que debe proponer la IA' };
const basename = path => path?.split('/').filter(Boolean).pop() || '';
const escapeHtml = value => { const d = document.createElement('div'); d.textContent = value ?? ''; return d.innerHTML; };

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return 'Calculando…';
  const s = Math.round(seconds), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}:${String(m).padStart(2,'0')}:${String(r).padStart(2,'0')}` : `${String(m).padStart(2,'0')}:${String(r).padStart(2,'0')}`;
}
function formatDate(epoch) { return epoch ? new Date(epoch * 1000).toLocaleString('es', { dateStyle:'medium', timeStyle:'short' }) : 'Sin actividad'; }
function setStatus(kind, label) { const el = $('appStatus'); el.className = `status ${kind}`; el.querySelector('span').textContent = label; }
function projectSettings() { return { mode: state.mode, editorial: state.editorial, video: state.video, transcript: state.transcript, brand: state.brand, structure: state.structure, exportMode: $('exportMode').value, exportXrolls: $('xrollToggle').checked }; }
async function persistProject(lastOutput = null) {
  if (!state.project) return;
  state.project = await invoke('update_project', { id: state.project.id, lastOutput, settings: projectSettings() });
}

async function loadProjects() {
  try { state.projects = await invoke('list_projects'); renderProjects(); }
  catch (error) { $('recentProjects').innerHTML = `<div class="project-loading error-copy">${escapeHtml(String(error))}</div>`; }
}
function renderProjects() {
  if (!state.projects.length) {
    $('recentProjects').innerHTML = '<div class="no-projects"><strong>Aún no hay proyectos</strong><span>Los que crees aparecerán aquí automáticamente.</span></div>';
    return;
  }
  $('recentProjects').innerHTML = state.projects.map(project => `
    <div class="project-card" data-id="${escapeHtml(project.id)}">
      <button class="project-open" type="button"><i>▶</i><span><strong>${escapeHtml(project.name)}</strong><small>${escapeHtml(formatDate(project.updatedAt))}</small><em>${project.lastOutput ? 'Listo para revisar' : 'En preparación'}</em></span></button>
      <button class="project-forget" type="button" title="Quitar de esta lista">×</button>
    </div>`).join('');
  document.querySelectorAll('.project-card').forEach(card => {
    const project = state.projects.find(item => item.id === card.dataset.id);
    card.querySelector('.project-open').onclick = () => openProject(project);
    card.querySelector('.project-forget').onclick = async event => { event.stopPropagation(); await invoke('forget_project', { id: project.id }); await loadProjects(); };
  });
}

async function createProject() {
  const name = $('projectNameInput').value.trim(); if (!name) return;
  const parent = await open({ directory:true, multiple:false, title:'Dónde guardar el nuevo proyecto' }); if (!parent) return;
  try { setStatus('running','Creando'); const project = await invoke('create_project', { name, parent }); await openProject(project); setStatus('idle','Listo'); }
  catch (error) { setStatus('error','Error'); alert(String(error)); }
}
async function browseProject() {
  const path = await open({ directory:true, multiple:false, title:'Selecciona una carpeta de abrxs-Canter' }); if (!path) return;
  try { const project = await invoke('register_project', { path }); await openProject(project); }
  catch (error) { alert(String(error)); }
}
function resetProjectWorkspace() {
  state.pieces=[]; state.totalPieces=0; state.outputResult=null; state.selectedVideo=null; state.reviews={videos:{}};
  state.editorOutput=null; state.editorData=null; state.editorBlocks=[]; state.selectedBlock=-1; state.editorHistory=[]; state.editorFuture=[];
  $('pieceList').innerHTML=''; $('pieceCount').textContent='0'; $('inventorySummary').classList.add('hidden'); $('inventorySummary').innerHTML=''; $('inventoryEmpty').classList.remove('hidden'); $('editorialRecovery').classList.add('hidden');
  $('reviewPanel').classList.add('hidden'); $('reviewList').innerHTML=''; $('reviewControls').classList.add('hidden'); $('reviewPlayer').pause(); $('reviewPlayer').removeAttribute('src'); $('reviewPlayer').load();
  $('manualPanel').classList.add('hidden'); $('progressPanel').classList.add('hidden'); $('openOutputBtn').classList.add('hidden'); $('logOutput').textContent='';
  $('editorVideo').pause(); $('editorVideo').removeAttribute('src'); $('editorVideo').load(); $('emptyEditorVideo').classList.remove('hidden'); $('editorView').classList.add('hidden'); document.body.style.overflow='';
}
async function openProject(project) {
  resetProjectWorkspace();
  state.project = project; state.output = project.path; state.outputResult = project.lastOutput || null;
  $('welcomeView').classList.add('hidden'); $('studioView').classList.remove('hidden');
  $('activeProjectName').textContent = project.name; $('activeProjectPath').textContent = project.path; $('activeProjectPath').title = project.path;
  const settings = project.settings || {};
  for (const key of Object.keys(refs)) setPath(key, settings[key] || null, false);
  setMode(settings.mode === 'cut' ? 'cut' : 'prepare', false);
  if (settings.exportMode) $('exportMode').value = settings.exportMode;
  if (typeof settings.exportXrolls === 'boolean') $('xrollToggle').checked = settings.exportXrolls;
  if (state.editorial && state.mode === 'cut') await inspectEditorial();
  if (project.lastOutput) { await loadReviewLibrary(project.lastOutput); await loadManualEditor(project.lastOutput); }
  $('projectNameInput').value=''; $('createProjectBtn').disabled=true;
  setStatus('idle','Proyecto abierto'); updateStartState(); window.scrollTo({ top:0, behavior:'smooth' });
}
async function showWelcome() {
  if (state.running) return;
  $('studioView').classList.add('hidden'); $('welcomeView').classList.remove('hidden'); state.project = null;
  $('reviewPlayer').pause(); await loadProjects(); setStatus('idle','Listo'); window.scrollTo({ top:0, behavior:'smooth' });
}

function setPath(key, path, persist = true) {
  state[key] = path || null; refs[key].textContent = path ? basename(path) : defaults[key]; refs[key].title = path || '';
  refs[key].closest('.file-field').classList.toggle('filled', !!path); updateStartState();
  if (persist && state.project) persistProject().catch(() => {});
}
function updateStartState() { $('startBtn').disabled = state.running || !(state.project && state.video && (state.mode === 'prepare' || (state.editorial && state.pieces.length))); }
function setMode(mode, persist = true) {
  if (state.running) return; state.mode = mode;
  $('prepareMode').classList.toggle('active', mode === 'prepare'); $('cutMode').classList.toggle('active', mode === 'cut'); $('editorialField').classList.toggle('hidden', mode === 'prepare');
  $('startLabel').textContent = mode === 'prepare' ? 'Crear transcripciones y paquete IA' : 'Analizar, cortar y exportar';
  if (mode === 'prepare') { $('inventoryEmpty').querySelector('strong').textContent = 'Primero prepara el máster'; $('inventoryEmpty').querySelector('span:last-child').textContent = 'abrxs-Canter generará dos transcripciones y una carpeta lista para llevar a una IA.'; }
  else if (!state.editorial) { $('inventoryEmpty').querySelector('strong').textContent = 'Esperando decisiones de corte'; $('inventoryEmpty').querySelector('span:last-child').textContent = 'Selecciona el JSON, HTML, MD o TXT devuelto por la IA.'; }
  updateStartState(); if (persist && state.project) persistProject().catch(() => {});
}
async function choose(key, options) { const selected = await open(options); if (!selected) return; if(key==='editorial'){state.pieces=[];updateStartState();} setPath(key, selected); if (key === 'editorial') await inspectEditorial(); }

async function inspectEditorial() {
  $('inventoryEmpty').classList.add('hidden'); $('editorialRecovery').classList.add('hidden'); $('inventorySummary').classList.remove('hidden'); $('inventorySummary').innerHTML = '<span>Analizando estructura editorial…</span>'; $('pieceList').innerHTML = '';
  try { const data = await invoke('inspect_editorial', { editorial:state.editorial }); state.pieces = data.pieces || []; state.totalPieces = state.pieces.length; $('pieceCount').textContent = state.pieces.length; $('inventorySummary').innerHTML = `<span><b>${data.actionable}</b> videos</span><span><b>${data.omitted}</b> omitidos</span>`; $('editorialRecovery').classList.toggle('hidden',data.actionable>0); renderPieces(); updateStartState(); }
  catch (error) { state.pieces=[]; $('pieceCount').textContent='0'; $('inventorySummary').innerHTML = `<span class="error-copy">No se pudo leer: ${escapeHtml(String(error))}</span>`; $('editorialRecovery').classList.remove('hidden'); updateStartState(); }
}
function renderPieces() { $('pieceList').innerHTML = state.pieces.map((p,i) => `<div class="piece-item" data-piece="${escapeHtml(p.id)}"><div class="piece-num">${String(i+1).padStart(2,'0')}</div><div class="piece-info"><strong>${escapeHtml(p.id)} · ${escapeHtml(p.title)}</strong><span>${escapeHtml(p.kind)} · ${p.segments} secciones</span></div><div class="piece-meta">${p.xrolls} XR<br>${p.voiceovers} VO</div></div>`).join(''); }
async function createEditorialTemplate(){if(!state.project)return;try{const path=await invoke('create_editorial_template',{projectPath:state.project.path});await invoke('reveal_path',{path});setStatus('success','Plantilla creada');}catch(error){alert(String(error));}}

function statusLabel(status) { return ({approved:'Aprobado',changes:'Corregir',rejected:'Descartado',pending:'Pendiente'})[status] || 'Pendiente'; }
async function loadReviewLibrary(outputPath, selectPath = null) {
  const videos = await invoke('list_project_videos', { path:outputPath });
  state.reviews = await invoke('load_reviews', { projectPath:state.project.path });
  if (!videos.length) { $('reviewPanel').classList.add('hidden'); return; }
  $('reviewPanel').classList.remove('hidden'); $('reviewCount').textContent = videos.length;
  $('reviewList').innerHTML = videos.map(path => { const review = state.reviews.videos?.[path] || {}; const status = review.status || 'pending'; return `<button class="review-item status-${status}" type="button" data-path="${escapeHtml(path)}"><i>▶</i><span><strong>${escapeHtml(basename(path))}</strong><small>${statusLabel(status)}</small></span></button>`; }).join('');
  document.querySelectorAll('.review-item').forEach(button => button.onclick = () => selectReviewVideo(button.dataset.path));
  if (selectPath && videos.includes(selectPath)) selectReviewVideo(selectPath); else if (!state.selectedVideo || !videos.includes(state.selectedVideo)) selectReviewVideo(videos[0]);
}
function selectReviewVideo(path) {
  state.selectedVideo = path; const review = state.reviews.videos?.[path] || {}; state.reviewStatus = review.status || 'pending';
  document.querySelectorAll('.review-item').forEach(item => item.classList.toggle('active', item.dataset.path === path));
  $('reviewPlayer').src = convertFileSrc(path); $('reviewTitle').textContent = basename(path); $('reviewNote').value = review.note || ''; $('reviewControls').classList.remove('hidden'); $('trimStart').value = '0.000'; $('trimEnd').value = '';
  document.querySelectorAll('.review-status button').forEach(button => button.classList.toggle('active', button.dataset.status === state.reviewStatus));
}
async function saveCurrentReview() {
  if (!state.selectedVideo) return;
  state.reviews = await invoke('save_review', { projectPath:state.project.path, videoPath:state.selectedVideo, status:state.reviewStatus, note:$('reviewNote').value });
  await loadReviewLibrary(state.outputResult || state.project.lastOutput, state.selectedVideo); setStatus('success','Revisión guardada');
}
async function exportTrim() {
  if (!state.selectedVideo) return; const start = Number($('trimStart').value), end = Number($('trimEnd').value);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) { alert('Marca una entrada y una salida válidas.'); return; }
  const button = $('exportTrimBtn'); button.disabled = true; button.querySelector('span').textContent = 'Exportando…'; setStatus('running','Recortando');
  try { const created = await invoke('trim_video', { source:state.selectedVideo, start, end }); await loadReviewLibrary(state.outputResult || state.project.lastOutput, created); setStatus('success','Copia ajustada lista'); }
  catch (error) { setStatus('error','Error'); alert(String(error)); }
  finally { button.disabled = false; button.querySelector('span').textContent = 'Exportar copia ajustada'; }
}

function preciseTime(seconds) {
  const total = Number(seconds) || 0, h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = (total % 60).toFixed(3).padStart(6,'0');
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${s}`;
}
async function loadManualEditor(outputPath) {
  try {
    await invoke('load_editor_data', { outputPath });
    state.editorOutput = outputPath; $('manualPanel').classList.remove('hidden');
  } catch (_) { $('manualPanel').classList.add('hidden'); }
}

const editorWords = () => state.editorData?.words || [];
const clipDuration = block => Math.max(0, Number(block.end) - Number(block.start));
const sequenceDuration = () => state.editorBlocks.reduce((sum, block) => sum + clipDuration(block), 0);
const newBlockId = () => globalThis.crypto?.randomUUID?.() || `block-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const cloneBlocks = blocks => JSON.parse(JSON.stringify(blocks));
const normalizeSearch = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();

function selectedWordRange() {
  if (state.selectionAnchor === null || state.selectionFocus === null) return null;
  return [Math.min(state.selectionAnchor, state.selectionFocus), Math.max(state.selectionAnchor, state.selectionFocus)];
}
function wordsInRange(start, end) { return editorWords().filter(word => Number(word.end) >= start && Number(word.start) <= end); }
function textForRange(start, end) { return wordsInRange(start, end).map(word => word.text).join(' ').replace(/\s+([,.;:!?])/g, '$1').trim(); }
function editorBlock(source, label = 'TRANSCRIPCIÓN') {
  const start = Math.max(0, Number(source.start) || 0), end = Math.max(start + .05, Number(source.end) || start + .05);
  return { uid:newBlockId(), role:source.role || 'SECCION', label, start, end, text:String(source.text || textForRange(start,end)).trim() };
}
function pushEditorHistory() {
  state.editorHistory.push(cloneBlocks(state.editorBlocks));
  if (state.editorHistory.length > 80) state.editorHistory.shift();
  state.editorFuture = []; updateHistoryButtons();
}
function updateHistoryButtons() { $('undoEditorBtn').disabled=!state.editorHistory.length; $('redoEditorBtn').disabled=!state.editorFuture.length; }
function undoEditor() {
  if (!state.editorHistory.length) return;
  state.editorFuture.push(cloneBlocks(state.editorBlocks)); state.editorBlocks=state.editorHistory.pop();
  state.selectedBlock=Math.min(state.selectedBlock,state.editorBlocks.length-1); renderEditorAssembly(); scheduleDraftSave(); updateHistoryButtons();
}
function redoEditor() {
  if (!state.editorFuture.length) return;
  state.editorHistory.push(cloneBlocks(state.editorBlocks)); state.editorBlocks=state.editorFuture.pop();
  state.selectedBlock=Math.min(state.selectedBlock,state.editorBlocks.length-1); renderEditorAssembly(); scheduleDraftSave(); updateHistoryButtons();
}

async function openTimelineEditor() {
  const outputPath = state.editorOutput || state.outputResult || state.project?.lastOutput;
  if (!outputPath) { alert('Primero prepara el video para generar su transcripción palabra por palabra.'); return; }
  try {
    setStatus('running','Abriendo editor');
    state.editorData = await invoke('load_editor_data', { outputPath });
    state.editorOutput = outputPath; state.video = state.editorData.video; state.transcript = state.editorData.transcriptPath;
    state.editorBlocks=[]; state.selectedBlock=-1; state.editorHistory=[]; state.editorFuture=[]; clearWordSelection();
    const draft = await invoke('load_editor_draft', { projectPath:state.project.path });
    if (draft?.video === state.editorData.video && Array.isArray(draft.blocks)) {
      state.editorBlocks = draft.blocks.map(item => ({...editorBlock(item,item.label||'BORRADOR'),uid:item.uid||newBlockId()}));
      $('editorTitle').value = draft.title || 'Nuevo clip';
    } else $('editorTitle').value = 'Nuevo clip';
    $('editorView').classList.remove('hidden'); document.body.style.overflow='hidden';
    const video=$('editorVideo'); video.src=convertFileSrc(state.editorData.video); video.playbackRate=Number($('playbackRate').value);
    $('sourceBadge').textContent=basename(state.editorData.video).toLocaleUpperCase();
    renderTranscriptWords(); renderSuggestedPhrases(); renderEditorAssembly(); updateHistoryButtons();
    setStatus('idle','Editor abierto');
  } catch (error) { setStatus('error','Error'); alert(String(error)); }
}
async function closeTimelineEditor() {
  $('editorVideo').pause(); state.editorPlaying=false; state.previewRangeEnd=null;
  await saveEditorDraft().catch(()=>{}); $('editorView').classList.add('hidden'); document.body.style.overflow='';
  setStatus('idle','Proyecto abierto');
}

function renderTranscriptWords() {
  const words=editorWords(); $('wordCount').textContent=`${words.length.toLocaleString()} palabras`;
  $('transcriptWords').innerHTML=words.map((word,index)=>`<span class="transcript-word" data-word="${index}" title="${preciseTime(word.start)} — ${preciseTime(word.end)}">${escapeHtml(word.text)}</span>`).join(' ');
  $('searchResultLabel').textContent='Arrastra desde la primera hasta la última palabra para seleccionar.';
}
function updateWordSelection() {
  document.querySelectorAll('.transcript-word.selected').forEach(el=>el.classList.remove('selected'));
  const range=selectedWordRange();
  if (!range) { $('selectionDuration').textContent='Sin selección'; $('addSelectionBtn').disabled=true; $('previewSelectionBtn').disabled=true; return; }
  for(let i=range[0];i<=range[1];i++) document.querySelector(`.transcript-word[data-word="${i}"]`)?.classList.add('selected');
  const words=editorWords(), start=Number(words[range[0]]?.start)||0, end=Number(words[range[1]]?.end)||start;
  $('selectionDuration').textContent=`${preciseTime(start)} → ${preciseTime(end)} · ${(end-start).toFixed(2)} s`;
  $('addSelectionBtn').disabled=false; $('previewSelectionBtn').disabled=false;
}
function clearWordSelection() { state.selectionAnchor=null; state.selectionFocus=null; updateWordSelection(); }
function selectWord(index, extend=false) {
  if (!extend || state.selectionAnchor===null) state.selectionAnchor=index;
  state.selectionFocus=index; updateWordSelection();
}
function addSelectedWords() {
  const range=selectedWordRange(); if(!range)return; const words=editorWords();
  pushEditorHistory(); const selected=words.slice(range[0],range[1]+1);
  state.editorBlocks.push(editorBlock({start:selected[0].start,end:selected.at(-1).end,text:selected.map(w=>w.text).join(' ')}));
  state.selectedBlock=state.editorBlocks.length-1; renderEditorAssembly(); scheduleDraftSave();
}
function previewSelection() {
  const range=selectedWordRange(); if(!range)return; const words=editorWords(), video=$('editorVideo');
  state.editorPlaying=false; state.previewRangeEnd=Number(words[range[1]].end); video.currentTime=Math.max(0,Number(words[range[0]].start)-.05); video.play();
  $('previewModeLabel').textContent='Previsualizando selección original'; $('editorPlayBtn').textContent='❚❚';
}
function searchTranscript() {
  const query=normalizeSearch($('wordSearch').value.trim());
  document.querySelectorAll('.transcript-word.search-hit,.transcript-word.search-current').forEach(el=>el.classList.remove('search-hit','search-current'));
  state.searchHits=[]; state.searchHitIndex=-1;
  if(!query){$('searchResultLabel').textContent='Arrastra desde la primera hasta la última palabra para seleccionar.';return;}
  const tokens=query.split(/\s+/).filter(Boolean), words=editorWords().map(w=>normalizeSearch(w.text).replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu,''));
  for(let i=0;i<=words.length-tokens.length;i++) if(tokens.every((token,j)=>words[i+j].includes(token))) state.searchHits.push([i,i+tokens.length-1]);
  state.searchHits.slice(0,500).forEach(range=>{for(let i=range[0];i<=range[1];i++)document.querySelector(`.transcript-word[data-word="${i}"]`)?.classList.add('search-hit');});
  $('searchResultLabel').textContent=state.searchHits.length?`${state.searchHits.length} coincidencia${state.searchHits.length===1?'':'s'} · Enter para ir a la siguiente`:'No se encontraron coincidencias.';
  if(state.searchHits.length) goToNextSearchHit();
}
function goToNextSearchHit() {
  if(!state.searchHits.length)return; state.searchHitIndex=(state.searchHitIndex+1)%state.searchHits.length;
  document.querySelectorAll('.transcript-word.search-current').forEach(el=>el.classList.remove('search-current'));
  const range=state.searchHits[state.searchHitIndex]; for(let i=range[0];i<=range[1];i++)document.querySelector(`.transcript-word[data-word="${i}"]`)?.classList.add('search-current');
  document.querySelector(`.transcript-word[data-word="${range[0]}"]`)?.scrollIntoView({block:'center',behavior:'smooth'});
}

function renderSuggestedPhrases() {
  const phrases=(state.editorData?.phrases||[]).slice(0,150);
  $('suggestedPhrases').innerHTML=phrases.map((item,index)=>`<button class="suggested-phrase" type="button" data-phrase="${index}"><small>${preciseTime(item.start)} · ${(Number(item.end)-Number(item.start)).toFixed(1)} s</small><span>${escapeHtml(item.text)}</span></button>`).join('');
  document.querySelectorAll('.suggested-phrase').forEach(button=>button.onclick=()=>{pushEditorHistory();state.editorBlocks.push(editorBlock(phrases[Number(button.dataset.phrase)],'FRASE'));state.selectedBlock=state.editorBlocks.length-1;renderEditorAssembly();scheduleDraftSave();});
}

function renderEditorAssembly() {
  renderEditorSequence(); renderBlockInspector(); renderTimeline();
  $('editorBlockCount').textContent=String(state.editorBlocks.length); $('sequenceDuration').textContent=preciseTime(sequenceDuration());
  $('applyEditorBtn').disabled=!state.editorBlocks.length||!$('editorTitle').value.trim(); updateHistoryButtons();
}
function renderEditorSequence() {
  if(!state.editorBlocks.length){$('editorSequence').innerHTML='<div class="editor-empty"><b>Tu clip empieza aquí</b><span>Selecciona texto o una frase para crear el primer bloque.</span></div>';return;}
  $('editorSequence').innerHTML=state.editorBlocks.map((block,index)=>`<article class="editor-block ${index===state.selectedBlock?'active':''}" data-block="${index}"><div class="editor-block-number">${index+1}</div><div class="editor-block-copy"><span>${escapeHtml(block.text||'Sección sin texto')}</span><small>${preciseTime(block.start)} → ${preciseTime(block.end)} · ${clipDuration(block).toFixed(2)} s</small></div><div class="block-move"><button data-move="up" title="Mover arriba">↑</button><button data-move="down" title="Mover abajo">↓</button></div></article>`).join('');
  document.querySelectorAll('.editor-block').forEach(card=>card.onclick=event=>{if(event.target.closest('[data-move]'))return;selectEditorBlock(Number(card.dataset.block),true);});
  document.querySelectorAll('[data-move]').forEach(button=>button.onclick=event=>{event.stopPropagation();const index=Number(button.closest('.editor-block').dataset.block),next=button.dataset.move==='up'?index-1:index+1;if(next<0||next>=state.editorBlocks.length)return;pushEditorHistory();[state.editorBlocks[index],state.editorBlocks[next]]=[state.editorBlocks[next],state.editorBlocks[index]];state.selectedBlock=next;renderEditorAssembly();scheduleDraftSave();});
}
function renderBlockInspector() {
  const block=state.editorBlocks[state.selectedBlock]; $('blockInspector').classList.toggle('hidden',!block); if(!block)return;
  $('blockStart').value=Number(block.start).toFixed(3); $('blockEnd').value=Number(block.end).toFixed(3);
}
function selectEditorBlock(index, seek=false) {
  if(index<0||index>=state.editorBlocks.length)return; state.selectedBlock=index; state.editorActiveBlock=index; renderEditorAssembly();
  if(seek){const video=$('editorVideo');state.editorPlaying=false;state.previewRangeEnd=null;video.pause();video.currentTime=state.editorBlocks[index].start;$('previewModeLabel').textContent=`Bloque ${index+1} sobre el máster`;}
}
function deleteSelectedBlock(){if(state.selectedBlock<0)return;pushEditorHistory();state.editorBlocks.splice(state.selectedBlock,1);state.selectedBlock=Math.min(state.selectedBlock,state.editorBlocks.length-1);renderEditorAssembly();scheduleDraftSave();}
function updateSelectedBlock(edge,value,withHistory=true){const block=state.editorBlocks[state.selectedBlock];if(!block)return;const duration=Number($('editorVideo').duration)||Number(state.editorData?.media?.duration)||Infinity;if(withHistory)pushEditorHistory();if(edge==='start')block.start=Math.max(0,Math.min(Number(value),block.end-.05));else block.end=Math.min(duration,Math.max(Number(value),block.start+.05));block.text=textForRange(block.start,block.end)||block.text;renderEditorAssembly();scheduleDraftSave();}
function splitSelectedBlock(){const index=state.selectedBlock,block=state.editorBlocks[index],at=Number($('editorVideo').currentTime);if(!block||at<=block.start+.05||at>=block.end-.05){alert('Coloca el cabezal dentro del bloque que quieres dividir.');return;}pushEditorHistory();const left=editorBlock({start:block.start,end:at,text:textForRange(block.start,at)},block.label),right=editorBlock({start:at,end:block.end,text:textForRange(at,block.end)},block.label);state.editorBlocks.splice(index,1,left,right);state.selectedBlock=index+1;renderEditorAssembly();scheduleDraftSave();}
function mergeSelectedBlock(){let index=state.selectedBlock;if(index<0||state.editorBlocks.length<2)return;if(index===state.editorBlocks.length-1)index--;const a=state.editorBlocks[index],b=state.editorBlocks[index+1],gap=Math.max(a.start,b.start)-Math.min(a.end,b.end);if(Math.abs(a.end-b.start)>1&&Math.abs(b.end-a.start)>1&&gap>1){alert('Esos bloques vienen de lugares distintos del máster. Ya quedarán unidos en el video final sin incluir el material intermedio.');return;}pushEditorHistory();const merged=editorBlock({start:Math.min(a.start,b.start),end:Math.max(a.end,b.end),text:`${a.text} ${b.text}`},'UNIDO');state.editorBlocks.splice(index,2,merged);state.selectedBlock=index;renderEditorAssembly();scheduleDraftSave();}
function polishBlocks(){if(state.editorBlocks.length<2)return;pushEditorHistory();const polished=[];for(const block of state.editorBlocks){const previous=polished.at(-1);if(previous&&block.start>=previous.start&&block.start-previous.end>=-.15&&block.start-previous.end<=1){previous.end=Math.max(previous.end,block.end);previous.text=`${previous.text} ${block.text}`.trim();previous.label='PULIDO';}else polished.push({...block});}state.editorBlocks=polished;state.selectedBlock=Math.min(Math.max(0,state.selectedBlock),polished.length-1);renderEditorAssembly();scheduleDraftSave();}

function timelineXFor(index,sourceTime=null){let x=0;for(let i=0;i<index;i++)x+=clipDuration(state.editorBlocks[i])*state.timelineZoom+4;if(index>=0&&sourceTime!==null){const block=state.editorBlocks[index];x+=Math.max(0,Math.min(clipDuration(block),sourceTime-block.start))*state.timelineZoom;}return x;}
function renderTimeline() {
  const total=sequenceDuration(),viewportWidth=$('timelineViewport').clientWidth||800,width=Math.max(viewportWidth-2,total*state.timelineZoom+Math.max(0,state.editorBlocks.length-1)*4);
  $('timelineCanvas').style.width=`${width}px`;
  const tickEvery=state.timelineZoom<15?10:state.timelineZoom<35?5:2,ticks=[];for(let t=0;t<=Math.max(total,1);t+=tickEvery)ticks.push(`<span class="ruler-tick" style="left:${t*state.timelineZoom}px">${formatTime(t)}</span>`);$('timelineRuler').innerHTML=ticks.join('');
  $('timelineTrack').innerHTML=state.editorBlocks.map((block,index)=>`<div class="timeline-clip ${index===state.selectedBlock?'active':''}" data-timeline-block="${index}" style="width:${Math.max(42,clipDuration(block)*state.timelineZoom)}px"><i class="trim-handle left" data-edge="start"></i><span>${index+1}. ${escapeHtml(block.text)}</span><b class="timeline-wave"></b><i class="trim-handle right" data-edge="end"></i></div>`).join('');
  document.querySelectorAll('.timeline-clip').forEach(clip=>clip.onclick=event=>{if(event.target.closest('.trim-handle'))return;selectEditorBlock(Number(clip.dataset.timelineBlock),true);});
  document.querySelectorAll('.trim-handle').forEach(handle=>handle.onpointerdown=event=>beginTimelineDrag(event,Number(handle.closest('.timeline-clip').dataset.timelineBlock),handle.dataset.edge));
  updateTimelinePlayhead();
}
function beginTimelineDrag(event,index,edge){event.preventDefault();event.stopPropagation();pushEditorHistory();const block=state.editorBlocks[index];state.selectedBlock=index;state.timelineDrag={index,edge,startX:event.clientX,original:Number(block[edge])};document.body.classList.add('dragging-timeline');renderEditorSequence();renderBlockInspector();}
function moveTimelineDrag(event){const drag=state.timelineDrag;if(!drag)return;const block=state.editorBlocks[drag.index];if(!block)return;const delta=(event.clientX-drag.startX)/state.timelineZoom,duration=Number($('editorVideo').duration)||Number(state.editorData?.media?.duration)||Infinity;if(drag.edge==='start')block.start=Math.max(0,Math.min(drag.original+delta,block.end-.05));else block.end=Math.min(duration,Math.max(drag.original+delta,block.start+.05));block.text=textForRange(block.start,block.end)||block.text;$('editorVideo').currentTime=block[drag.edge];renderEditorAssembly();}
function endTimelineDrag(){if(!state.timelineDrag)return;state.timelineDrag=null;document.body.classList.remove('dragging-timeline');scheduleDraftSave();}
function fitTimeline(){const total=Math.max(sequenceDuration(),1),available=Math.max(280,$('timelineViewport').clientWidth-20);state.timelineZoom=Math.max(8,Math.min(80,available/total));$('timelineZoom').value=state.timelineZoom;renderTimeline();}
function seekOutputAt(clientX){const viewport=$('timelineViewport'),x=clientX-viewport.getBoundingClientRect().left+viewport.scrollLeft;let cursor=0;for(let i=0;i<state.editorBlocks.length;i++){const block=state.editorBlocks[i],width=clipDuration(block)*state.timelineZoom;if(x<=cursor+width){selectEditorBlock(i,false);$('editorVideo').currentTime=block.start+Math.max(0,x-cursor)/state.timelineZoom;updateTimelinePlayhead();return;}cursor+=width+4;}}
function updateTimelinePlayhead(){const index=state.editorActiveBlock>=0?state.editorActiveBlock:state.selectedBlock;if(index<0){$('timelinePlayhead').style.left='0px';return;}$('timelinePlayhead').style.left=`${timelineXFor(index,$('editorVideo').currentTime)}px`;}

function playEditorSequence(index=null){if(!state.editorBlocks.length)return;const video=$('editorVideo');if(state.editorPlaying){state.editorPlaying=false;video.pause();$('editorPlayBtn').textContent='▶';return;}state.previewRangeEnd=null;state.editorActiveBlock=index??(state.selectedBlock>=0?state.selectedBlock:0);const block=state.editorBlocks[state.editorActiveBlock];if(video.currentTime<block.start||video.currentTime>=block.end)video.currentTime=block.start;state.selectedBlock=state.editorActiveBlock;state.editorPlaying=true;$('previewModeLabel').textContent='Vista previa de la secuencia';$('editorPlayBtn').textContent='❚❚';renderEditorAssembly();video.play();}
function jumpEditorBlock(delta){if(!state.editorBlocks.length)return;const base=state.editorActiveBlock>=0?state.editorActiveBlock:(state.selectedBlock>=0?state.selectedBlock:0),next=Math.max(0,Math.min(state.editorBlocks.length-1,base+delta));state.editorActiveBlock=next;selectEditorBlock(next,true);}
function handleEditorTimeUpdate(){const video=$('editorVideo');$('editorTime').textContent=`${preciseTime(video.currentTime)} / ${preciseTime(video.duration||0)}`;if(state.previewRangeEnd!==null&&video.currentTime>=state.previewRangeEnd){video.pause();state.previewRangeEnd=null;$('editorPlayBtn').textContent='▶';$('previewModeLabel').textContent='Vista previa sin procesar';}if(state.editorPlaying){const block=state.editorBlocks[state.editorActiveBlock];if(block&&video.currentTime>=block.end-.025){if(state.editorActiveBlock<state.editorBlocks.length-1){state.editorActiveBlock++;state.selectedBlock=state.editorActiveBlock;video.currentTime=state.editorBlocks[state.editorActiveBlock].start;renderEditorAssembly();video.play();}else{state.editorPlaying=false;video.pause();video.currentTime=block.end;$('editorPlayBtn').textContent='▶';$('previewModeLabel').textContent='Secuencia terminada';}}}updateTimelinePlayhead();}

function scheduleDraftSave(){clearTimeout(state.editorSaveTimer);$('editorSaveState').textContent='Cambios sin guardar';$('editorSaveState').className='editor-save-state saving';state.editorSaveTimer=setTimeout(()=>saveEditorDraft().catch(()=>{}),550);}
async function saveEditorDraft(){if(!state.project||!state.editorData)return;clearTimeout(state.editorSaveTimer);$('editorSaveState').textContent='Guardando…';$('editorSaveState').className='editor-save-state saving';try{await invoke('save_editor_draft',{projectPath:state.project.path,title:$('editorTitle').value||'Nuevo clip',videoPath:state.editorData.video,transcriptPath:state.editorData.transcriptPath,blocks:state.editorBlocks});$('editorSaveState').textContent='Guardado local';$('editorSaveState').className='editor-save-state';}catch(error){$('editorSaveState').textContent='No se pudo guardar';$('editorSaveState').className='editor-save-state error';throw error;}}
async function applyEditorAndExport(){if(!state.editorBlocks.length)return;const title=$('editorTitle').value.trim()||'Nuevo clip';$('applyEditorBtn').disabled=true;$('applyEditorBtn').textContent='Preparando…';try{await saveEditorDraft();const editorial=await invoke('save_manual_editorial',{projectPath:state.project.path,title,segments:state.editorBlocks});setPath('editorial',editorial,false);setPath('video',state.editorData.video,false);setPath('transcript',state.editorData.transcriptPath,false);setMode('cut',false);await persistProject();await inspectEditorial();await closeTimelineEditor();await startJob();}catch(error){alert(String(error));}finally{$('applyEditorBtn').innerHTML='Aplicar y exportar <b>→</b>';updateStartState();renderEditorAssembly();}}

function logLine(line) { const pre = $('logOutput'); pre.textContent += line + '\n'; if (pre.textContent.length > 50000) pre.textContent = pre.textContent.slice(-40000); pre.scrollTop = pre.scrollHeight; }
function setBar(id,value) { $(id).style.width = `${Math.max(0,Math.min(100,value))}%`; }
function updateClock() { if (state.startedAt) $('elapsedMetric').textContent = formatTime((Date.now()-state.startedAt)/1000); }
function resetPieceClasses(activeId) { document.querySelectorAll('.piece-item').forEach(el => { if (el.classList.contains('active') && el.dataset.piece !== activeId) { el.classList.remove('active'); el.classList.add('done'); } if (el.dataset.piece === activeId) el.classList.add('active'); }); }
function handleProgress(data) {
  switch(data.event) {
    case 'backend_detected': { const mlx=data.mlx_whisper?.available?'MLX Whisper':null, cpp=data.whisper_cpp?.available?(data.whisper_cpp?.ready?'whisper.cpp listo':'whisper.cpp sin modelo'):null; logLine(`Motores detectados: ${[mlx,cpp].filter(Boolean).join(' · ')||'ninguno'}`); break; }
    case 'preflight_complete': $('progressTitle').textContent='Máster verificado'; $('progressDetail').textContent=`${data.width||'?'}×${data.height||'?'} · ${formatTime(data.duration)}${data.low_space_warning?' · poco espacio libre':''}`; if(data.low_space_warning)logLine('Aviso: conviene liberar espacio antes de una exportación grande.'); break;
    case 'project_detected': state.totalPieces=data.total_pieces; $('progressTitle').textContent='Proyecto analizado'; $('progressDetail').textContent=`${data.total_pieces} videos listos`; break;
    case 'transcript_start': $('progressTitle').textContent=data.mode==='existing'?'Leyendo transcripción':'Generando transcripción word-level'; $('progressDetail').textContent=data.detail; $('globalBar').parentElement.classList.add('indeterminate'); $('currentTitle').textContent='Transcripción del máster'; $('currentStage').textContent=data.detail; break;

    // ABRXS_TRANSCRIPT_PROGRESS_V34
    case 'transcript_progress': {
      const p = Math.max(
        0,
        Math.min(
          100,
          Number(data.progress || 0)
        )
      );

      $('globalBar')
        .parentElement
        .classList
        .remove('indeterminate');

      $('globalBar').style.width =
        `${p}%`;

      $('progressTitle').textContent =
        `Transcripción ${p}%`;

      let detail = `${p}% completado`;

      if (
        data.eta_seconds !== null
        && data.eta_seconds !== undefined
      ) {
        const seconds =
          Math.max(
            0,
            Math.round(
              Number(data.eta_seconds)
            )
          );

        const minutes =
          Math.floor(seconds / 60);

        const rest =
          seconds % 60;

        detail +=
          ` · restante aprox. `
          + `${minutes}:`
          + `${String(rest).padStart(2,'0')}`;
      }

      $('progressDetail').textContent =
        detail;

      $('currentStage').textContent =
        detail;

      break;
    }

    case 'transcript_complete': $('globalBar').parentElement.classList.remove('indeterminate'); $('progressDetail').textContent=`${data.word_count.toLocaleString()} palabras alineadas`; break;
    case 'piece_start': state.currentPiece=data.current; state.totalPieces=data.total; state.pieceStartedAt=Date.now(); $('currentIndex').textContent=String(data.current).padStart(2,'0'); $('currentTitle').textContent=`${data.piece_id} · ${data.title}`; $('currentStage').textContent=`${data.segments} secciones · ${data.xrolls} X-rolls · ${data.voiceovers} voiceovers`; $('pieceMetric').textContent=`${data.current} / ${data.total}`; $('piecePercent').textContent='0%'; setBar('pieceBar',0); resetPieceClasses(data.piece_id); break;
    case 'piece_progress': { const fraction=data.total?data.completed/data.total:0, percent=Math.round(fraction*100); $('currentStage').textContent=data.detail; $('piecePercent').textContent=`${percent}%`; setBar('pieceBar',percent); $('pieceTasks').textContent=`${data.completed} de ${data.total} tareas`; const pieceElapsed=(Date.now()-state.pieceStartedAt)/1000; $('pieceEta').textContent=fraction>0?`Faltan aprox. ${formatTime(pieceElapsed/fraction-pieceElapsed)}`:'Estimando…'; const overall=state.totalPieces?((state.currentPiece-1)+fraction)/state.totalPieces:0; const overallPercent=Math.round(overall*100); setBar('globalBar',overallPercent); $('globalPercent').textContent=`${overallPercent}%`; const elapsed=(Date.now()-state.startedAt)/1000; $('etaMetric').textContent=overall>.01?formatTime(elapsed/overall-elapsed):'Calculando…'; break; }
    case 'piece_complete': document.querySelector(`.piece-item[data-piece="${CSS.escape(data.piece_id)}"]`)?.classList.add('done'); break;
    case 'job_complete': state.outputResult=data.output; setBar('globalBar',100); $('globalPercent').textContent='100%'; $('etaMetric').textContent='Terminado'; $('progressTitle').textContent='Proyecto terminado'; $('progressDetail').textContent=data.total_pieces?`${data.total_pieces} videos procesados`:'Transcripciones y paquete para IA listos'; $('openOutputBtn').classList.remove('hidden'); persistProject(data.output).then(() => { if(data.total_pieces) loadReviewLibrary(data.output); loadManualEditor(data.output); }); break;
  }
}
async function startJob() {
  state.running=true; state.startedAt=Date.now(); state.outputResult=null; $('startBtn').disabled=true; $('progressPanel').classList.remove('hidden'); $('openOutputBtn').classList.add('hidden'); $('cancelBtn').classList.remove('hidden'); $('logOutput').textContent=''; setStatus('running','Procesando'); $('progressPanel').scrollIntoView({behavior:'smooth',block:'start'}); state.timer=setInterval(updateClock,1000); updateClock(); await persistProject();
  try { await invoke('start_job',{config:{editorial:state.editorial,video:state.video,transcript:state.transcript,output:state.output,brand:state.brand,structure:state.structure,mode:state.mode,export_mode:$('exportMode').value,export_xrolls:$('xrollToggle').checked}}); }
  catch(error) { finishJob(false,String(error)); }
}
function finishJob(success,message='') { state.running=false; clearInterval(state.timer); updateStartState(); $('cancelBtn').classList.add('hidden'); setStatus(success?'success':'error',success?'Terminado':'Error'); if(!success){$('progressTitle').textContent='El proceso se detuvo';$('progressDetail').textContent=message||'Revisa el registro';} }

$('projectNameInput').oninput = () => $('createProjectBtn').disabled = !$('projectNameInput').value.trim();
$('projectNameInput').onkeydown = event => { if (event.key === 'Enter' && !$('createProjectBtn').disabled) createProject(); };
$('createProjectBtn').onclick=createProject; $('browseProjectBtn').onclick=browseProject; $('backProjectsBtn').onclick=showWelcome; $('brandHome').onclick=showWelcome;
$('revealProjectBtn').onclick=()=>state.project&&invoke('reveal_path',{path:state.project.path});
$('prepareMode').onclick=()=>setMode('prepare'); $('cutMode').onclick=()=>setMode('cut');
$('editorialBtn').onclick=()=>choose('editorial',{multiple:false,filters:[{name:'Editorial',extensions:['html','htm','json','md','txt']}]});
$('videoBtn').onclick=()=>choose('video',{multiple:false,filters:[{name:'Video',extensions:['mp4','mov','m4v','mkv']}]});
$('transcriptBtn').onclick=()=>choose('transcript',{multiple:false,filters:[{name:'Transcript',extensions:['json','tsv','csv','txt']}]});
$('brandBtn').onclick=()=>choose('brand',{multiple:false,filters:[{name:'Marca',extensions:['md','txt','json']}]});
$('structureBtn').onclick=()=>choose('structure',{multiple:false,filters:[{name:'Estructura',extensions:['md','txt','json']}]});
$('exportMode').onchange=()=>persistProject().catch(()=>{}); $('xrollToggle').onchange=()=>persistProject().catch(()=>{}); $('startBtn').onclick=startJob;
$('cancelBtn').onclick=async()=>{await invoke('cancel_job');$('progressDetail').textContent='Cancelando proceso…';}; $('openOutputBtn').onclick=()=>state.outputResult&&invoke('reveal_path',{path:state.outputResult});
$('resetBtn').onclick=()=>{if(state.running)return;for(const key of Object.keys(refs))setPath(key,null,false);state.pieces=[];$('pieceList').innerHTML='';$('pieceCount').textContent='0';$('inventorySummary').classList.add('hidden');$('inventoryEmpty').classList.remove('hidden');persistProject().catch(()=>{});};
$('createTemplateBtn').onclick=createEditorialTemplate;
document.querySelectorAll('.review-status button').forEach(button=>button.onclick=()=>{state.reviewStatus=button.dataset.status;document.querySelectorAll('.review-status button').forEach(item=>item.classList.toggle('active',item===button));});
$('saveReviewBtn').onclick=saveCurrentReview; $('reviewPlayer').onloadedmetadata=()=>{$('trimEnd').value=Number($('reviewPlayer').duration||0).toFixed(3);}; $('setInBtn').onclick=()=>{$('trimStart').value=$('reviewPlayer').currentTime.toFixed(3);}; $('setOutBtn').onclick=()=>{$('trimEnd').value=$('reviewPlayer').currentTime.toFixed(3);}; $('exportTrimBtn').onclick=exportTrim;
$('openEditorBtn').onclick=openTimelineEditor; $('closeEditorBtn').onclick=closeTimelineEditor; $('applyEditorBtn').onclick=applyEditorAndExport;
$('undoEditorBtn').onclick=undoEditor; $('redoEditorBtn').onclick=redoEditor; $('addSelectionBtn').onclick=addSelectedWords; $('previewSelectionBtn').onclick=previewSelection;
$('wordSearch').oninput=searchTranscript; $('wordSearch').onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();goToNextSearchHit();}}; $('clearWordSearch').onclick=()=>{$('wordSearch').value='';searchTranscript();$('wordSearch').focus();};
$('transcriptWords').onpointerdown=event=>{const word=event.target.closest?.('.transcript-word');if(!word)return;state.selectingWords=true;selectWord(Number(word.dataset.word),event.shiftKey);};
$('transcriptWords').onpointermove=event=>{if(!state.selectingWords)return;const word=document.elementFromPoint(event.clientX,event.clientY)?.closest?.('.transcript-word');if(word){state.selectionFocus=Number(word.dataset.word);updateWordSelection();}};
window.addEventListener('pointerup',()=>{state.selectingWords=false;endTimelineDrag();}); window.addEventListener('pointermove',moveTimelineDrag);
$('editorTitle').oninput=()=>{renderEditorAssembly();scheduleDraftSave();}; $('editorPlayBtn').onclick=()=>playEditorSequence(); $('previousBlockBtn').onclick=()=>jumpEditorBlock(-1); $('nextBlockBtn').onclick=()=>jumpEditorBlock(1);
$('playbackRate').onchange=()=>{$('editorVideo').playbackRate=Number($('playbackRate').value);}; $('editorVideo').ontimeupdate=handleEditorTimeUpdate; $('editorVideo').onloadedmetadata=()=>{$('emptyEditorVideo').classList.add('hidden');fitTimeline();handleEditorTimeUpdate();};
$('deleteBlockBtn').onclick=deleteSelectedBlock; $('splitBlockBtn').onclick=splitSelectedBlock; $('mergeBlockBtn').onclick=mergeSelectedBlock; $('polishBlocksBtn').onclick=polishBlocks;
$('blockStart').onchange=()=>updateSelectedBlock('start',Number($('blockStart').value)); $('blockEnd').onchange=()=>updateSelectedBlock('end',Number($('blockEnd').value));
document.querySelectorAll('.nudge-grid button').forEach(button=>button.onclick=()=>{const block=state.editorBlocks[state.selectedBlock];if(!block)return;updateSelectedBlock(button.dataset.edge,Number(block[button.dataset.edge])+Number(button.dataset.delta));});
$('timelineZoom').oninput=()=>{state.timelineZoom=Number($('timelineZoom').value);renderTimeline();}; $('fitTimelineBtn').onclick=fitTimeline; $('timelineViewport').onclick=event=>{if(!event.target.closest('.timeline-clip'))seekOutputAt(event.clientX);};
window.addEventListener('keydown',event=>{if($('editorView').classList.contains('hidden'))return;if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='z'){event.preventDefault();event.shiftKey?redoEditor():undoEditor();}if(event.code==='Space'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)){event.preventDefault();playEditorSequence();}if(event.key==='Escape')closeTimelineEditor();});
listen('progress-event',event=>handleProgress(event.payload)); listen('backend-line',event=>logLine(event.payload)); listen('job-finished',event=>finishJob(event.payload.success,event.payload.message));
loadProjects();
