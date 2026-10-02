/* Read-only activity viewer. Never executes commands or sends logs externally. */
(() => {
  'use strict';
  const key='abrxs-activity-v1',limit=600;
  let rows=[],scheduled=null;try{rows=JSON.parse(localStorage.getItem(key)||'[]');if(!Array.isArray(rows))rows=[];rows=rows.slice(-limit);}catch{}
  const panel=document.createElement('section');panel.id='activityPanel';panel.hidden=true;panel.setAttribute('aria-label','Registro de actividad');
  panel.innerHTML='<header><strong>Actividad del programa</strong><button id="activityCancel" hidden>Cancelar trabajo</button><button id="activityCopy">Copiar diagnóstico</button><button id="activityClose" aria-label="Cerrar registro">×</button></header><p>Salida real del motor y errores. Solo lectura: no ejecuta comandos. Se conserva un historial local limitado.</p><pre id="activityText" tabindex="0"></pre>';
  const button=document.createElement('button');button.id='activityToggle';button.textContent='Actividad';button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','activityPanel');
  document.body.append(panel,button);
  const pre=panel.querySelector('pre');
  function render(){pre.textContent=rows.map(r=>r.text).join('\n');pre.scrollTop=pre.scrollHeight;button.textContent=rows.at(-1)?.error?'Actividad · error':'Actividad';try{panel.querySelector('#activityCancel').hidden=!(state.running||window.AbrxsStudio?.busy);}catch{}}
  function show(value=true){panel.hidden=!value;button.setAttribute('aria-expanded',String(value));if(value)render();}
  function project(){try{return state.project?.name||'Inicio';}catch{return 'Inicio';}}
  function add(kind,text,error=false){
    const value=String(text??'').slice(-12000);if(!value)return;
    rows.push({text:'['+new Date().toLocaleTimeString('es')+'] ['+project()+'] '+kind+' · '+value,error});rows=rows.slice(-limit);render();
    while(rows.length>1&&rows.reduce((n,r)=>n+r.text.length,0)>300000)rows.shift();
    clearTimeout(scheduled);scheduled=setTimeout(()=>{try{localStorage.setItem(key,JSON.stringify(rows));}catch{}},500);
    if(error)show();
  }
  button.onclick=()=>show(panel.hidden);panel.querySelector('#activityClose').onclick=()=>show(false);
  panel.querySelector('#activityCancel').onclick=async()=>{try{await window.__TAURI__.core.invoke('cancel_job');add('Cancelación','Solicitada; esperando que el motor termine. No se inicia otro trabajo todavía.');}catch(e){add('Cancelación',e,true);}};
  panel.querySelector('#activityCopy').textContent='Copiar resumen (máx. 4.000 caracteres)';
  panel.querySelector('#activityCopy').onclick=async()=>{const recent=rows.filter(r=>r.error||!/ · (frame=|size=|Stream|Metadata|encoder|handler_name)/.test(r.text)).slice(-20);try{await navigator.clipboard.writeText('Abrxs-Canter · diagnóstico breve\n'+recent.map(r=>r.text).join('\n').slice(-3900));}catch{pre.textContent=recent.map(r=>r.text).join('\n').slice(-3900);const range=document.createRange();range.selectNodeContents(pre);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);}};
  window.AbrxsActivity={add,show};
  window.addEventListener('error',e=>add('Interfaz',e.message,true));
  window.addEventListener('unhandledrejection',e=>add('Interfaz',e.reason?.message||e.reason,true));
  const listen=window.__TAURI__?.event?.listen;
  if(listen)for(const event of ['backend-line','progress-event','job-finished','stage1-event']){
    listen(event,({payload:p})=>{
      if(typeof p==='string')add('Motor',p,/^ERROR:|Traceback|Error:/i.test(p.trim()));
      else if(p){
        if(p.event==='result')return;
        const error=p.success===false||p.event==='clip_error';
        const detail=p.detail||p.message||JSON.stringify(p);
        add(p.event||event,detail,error);
      }
    }).catch(e=>add('Registro',e,true));
  }
  add('Sistema','Registro disponible. No se descargan modelos ni se inicia procesamiento al abrirlo.');
})();
