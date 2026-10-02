/* Review workspace: browsing is separate from the selected review queue. */
(function(){
 'use strict';
 const W=window.AbrxsWeb,D=window.AbrxsDrive,C=window.AbrxsReview,$=id=>document.getElementById(id);
 if(!W)return;
 const media=f=>/^(video|image)\//.test(f.mimeType||'');
 const run=fn=>async()=>{try{await fn();}catch(e){W.say(e.message,true);}};
 function button(text,fn){const b=document.createElement('button');b.textContent=text;b.onclick=run(fn);return b;}
 const dialog=document.createElement('dialog');dialog.className='file-explorer';
 const top=document.createElement('div');top.className='section-head';const title=document.createElement('h2');title.textContent='Explorar carpetas de Drive';top.append(title,button('Cerrar',()=>dialog.close()));
 const tools=document.querySelector('.browser-tools'),files=$('files'),actions=document.createElement('div');actions.className='row';
 const queue=document.createElement('div');queue.className='review-queue';
 const launch=button('Explorar Drive · añadir a revisión',()=>{dialog.showModal();drawExplorer();});
 tools.before(launch,queue);dialog.append(top,tools,actions,files);document.body.append(dialog);
 let chosen=new Set();
 const enriched=f=>({...f,parentFolder:W.trail.at(-1),folderPath:W.trail.map(t=>t.name).join(' / ')});
 function drawQueue(){queue.replaceChildren();const list=W.project.reviewFiles||[];if(!list.length){const p=document.createElement('p');p.textContent='Añade videos o imágenes desde el explorador. Esta será tu lista de revisión.';queue.append(p);}
 for(const [i,f]of list.entries()){const row=document.createElement('div');row.className='queue-item';row.append(button((W.current?.id===f.id?'● ':'')+f.name,()=>W.select(f)),button('↑',()=>{if(i){[list[i-1],list[i]]=[list[i],list[i-1]];W.save();drawQueue();}}),button('×',()=>{list.splice(i,1);W.save();drawQueue();}));queue.append(row);}}
 function drawExplorer(){chosen.clear();actions.replaceChildren(button('Seleccionar todos los videos',()=>selectAll(f=>f.mimeType?.startsWith('video/'))),button('Seleccionar videos e imágenes',()=>selectAll(media)),button('Añadir selección a revisión',()=>{const list=W.project.reviewFiles||=[];for(const f of W.files.filter(f=>chosen.has(f.id)&&media(f)))if(!list.some(x=>x.id===f.id))list.push(enriched(f));W.save();drawQueue();dialog.close();}));
 for(const [i,f]of W.files.filter(f=>f.name.toLocaleLowerCase().includes($('file-search').value.trim().toLocaleLowerCase())).entries()){const card=files.children[i];if(!card)continue;if(media(f)){const check=document.createElement('input');check.type='checkbox';check.setAttribute('aria-label','Seleccionar '+f.name);check.onclick=e=>e.stopPropagation();check.onchange=()=>check.checked?chosen.add(f.id):chosen.delete(f.id);card.prepend(check);}else if(f.mimeType!=='application/vnd.google-apps.folder'){card.onclick=run(async()=>{const raw=await D.text(f);W.loadTranscript(raw);W.say('Información con tiempos cargada. Comprueba que corresponde al máster.');dialog.close();});}}
 }
 function selectAll(predicate){chosen=new Set(W.files.filter(predicate).map(f=>f.id));for(const input of files.querySelectorAll('input[type=checkbox]')){const name=input.getAttribute('aria-label').slice(12);input.checked=W.files.some(f=>f.name===name&&chosen.has(f.id));}}
 window.addEventListener('review-folder',drawExplorer);window.addEventListener('review-project',drawQueue);$('file-search').addEventListener('input',drawExplorer);window.addEventListener('review-file',e=>{drawQueue();if(dialog.open)drawExplorer();const m=e.detail?.videoMediaMetadata;setRatio(m?.width,m?.height);sync();});
 // The composer sits below the picture, never over Google's cross-origin iframe.
 const player=$('player'),composer=document.createElement('div');composer.className='review-composer';
 const surface=document.createElement('div');surface.id='review-surface';surface.className='review-surface';$('viewer-empty').before(surface);
 for(const id of ['viewer-empty','drive-player','player','review-photo']){const item=$(id);if(item)surface.append(item);}
 function setRatio(width,height){surface.style.aspectRatio=Number(width)>0&&Number(height)>0?String(Number(width)/Number(height)):'16 / 9';}
 const textLabel=$('note-text').parentElement,save=$('add-note'),timeFields=document.querySelector('#notes .time-row');
 const sliderRow=document.createElement('div');sliderRow.className='time-row';const sliders=[];
 for(const [id,label]of [['note-start','Desde'],['note-end','Hasta']]){const box=document.createElement('label');box.textContent=label+' · arrastra para ajustar';const s=document.createElement('input');s.type='range';s.min='0';s.max='0';s.step='.01';s.disabled=true;s.oninput=()=>{$(id).value=C.stamp(Number(s.value));if(id==='note-start'&&Number(sliders[1].value)<Number(s.value)){$('note-end').value=C.stamp(Number(s.value));sliders[1].value=s.value;}};box.append(s);sliderRow.append(box);sliders.push(s);}
 const status=document.createElement('p');status.className='muted';status.textContent='Tiempos manuales: escribe Desde y Hasta según el contador del video. Pausar o escribir no cambia estos campos.';
 composer.append(timeFields,sliderRow,textLabel,status,save);document.querySelector('.player-panel').after(composer);
 function sync(){const duration=!player.hidden&&Number.isFinite(player.duration)?player.duration:Number(W.current?.videoMediaMetadata?.durationMillis)/1000;sliders.forEach((s,i)=>{s.disabled=!(duration>0);s.max=duration>0?duration:0;try{s.value=C.seconds($(i?'note-end':'note-start').value);}catch{}});}
 player.addEventListener('loadedmetadata',()=>{setRatio(player.videoWidth,player.videoHeight);sync();});player.addEventListener('emptied',()=>{setRatio();sync();});
 $('review-photo')?.addEventListener('load',()=>setRatio($('review-photo').naturalWidth,$('review-photo').naturalHeight));
 for(const id of ['note-start','note-end'])$(id).addEventListener('change',sync);
 const panel=document.querySelector('.player-panel');
 function expanded(value){panel.classList.toggle('expanded-player',value);document.body.classList.toggle('review-fullscreen-fallback',value);fullscreen.textContent=value?'Cerrar vista ampliada':'Pantalla completa';fullscreen.setAttribute('aria-expanded',String(value));}
 const fullscreen=button('Pantalla completa',async()=>{
   if(document.fullscreenElement){await document.exitFullscreen();return;}
   if(panel.classList.contains('expanded-player')){expanded(false);return;}
   // On iPhone use the actual native video fullscreen, not a tall stretched iframe.
   try{
     if(!player.hidden&&player.webkitEnterFullscreen&&player.readyState>=1){player.webkitEnterFullscreen();return;}
     if(surface.requestFullscreen){await surface.requestFullscreen();return;}
   }catch(e){W.say('Este navegador no permitió pantalla completa.');}
   if(!$('drive-player').hidden){
     W.say('Para pantalla completa en este iPhone, pulsa Abrir en Drive. El visor integrado no se amplía artificialmente.');
     $('open-drive').focus();return;
   }
   expanded(true);W.say('Vista ampliada. No es pantalla completa nativa; puedes cerrarla con el mismo botón.');
 });fullscreen.id='review-fullscreen';document.querySelector('.viewer-modes').append(fullscreen);
 document.addEventListener('fullscreenchange',()=>{fullscreen.textContent=document.fullscreenElement?'Salir de pantalla completa':'Pantalla completa';});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')expanded(false);});
 const exports=document.createElement('div');exports.className='row';exports.append(button('Copiar revisión con enlaces',async()=>{await navigator.clipboard.writeText(W.notesText());W.say('Revisión copiada con nombres, enlaces y tiempos.');}),button('Autorizar guardado en Drive',async()=>{await D.connect($('client-id').value.trim(),true);W.say('Permiso solicitado. Ahora pulsa Subir TXT. La carpeta también debe permitir añadir archivos y estar autorizada a la aplicación.');}),button('Subir TXT a las carpetas de origen',async()=>{const groups=new Map();for(const n of W.project.notes){if(!n.folderId)throw Error('Hay notas sin carpeta de Drive. Descarga el TXT o elimina esas notas de esta entrega.');const a=groups.get(n.folderId)||[];a.push(n);groups.set(n.folderId,a);}if(!groups.size)throw Error('No hay notas para subir.');if(!confirm('Se creará un TXT nuevo en '+groups.size+' carpeta(s). No se modifica ningún video ni imagen. ¿Continuar?'))return;const name='REVISION_ABRXS_'+new Date().toISOString().replace(/[:.]/g,'-')+'.txt';for(const [folder,notes]of groups){await D.uploadText(folder,name,W.notesText(notes));W.say('TXT guardado en https://drive.google.com/drive/folders/'+folder);} }));$('notes').append(exports);
 drawQueue();sync();
})();
