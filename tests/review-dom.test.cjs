/* Synthetic DOM only: does not claim Safari, Drive or video decoding QA. */
const {parseHTML}=require('../.build-cache/ui-tests/node_modules/linkedom');
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {window}=parseHTML(fs.readFileSync('review-web/index.html','utf8'));
const stored=new Map(),downloads=[];
Object.assign(window,{console,setTimeout:()=>0,clearTimeout:()=>{},URL,Blob,confirm:()=>true,location:{protocol:'http:',href:'http://localhost:8765/'},localStorage:{getItem:k=>stored.get(k)||null,setItem:(k,v)=>stored.set(k,v)},AbrxsDrive:{load:async()=>{},connect:async()=>{},disconnect:async()=>{},list:async()=>[]}});
Object.defineProperty(window.HTMLSelectElement.prototype,'value',{get(){return this._value||this.querySelector('option')?.value||'';},set(v){this._value=v;}});
const video=window.document.getElementById('player');Object.assign(video,{pause:()=>{},load:()=>{},play:async()=>{},duration:60,currentTime:12});
window.HTMLElement.prototype.click=function(){if(this.tagName==='A')downloads.push(this.download);};
const context=vm.createContext(window);vm.runInContext(fs.readFileSync('review-web/core.js','utf8'),context);vm.runInContext(fs.readFileSync('review-web/app.js','utf8'),context);
const $=id=>window.document.getElementById(id);
(async()=>{
 assert.equal($('project-name').value,'Proyecto nuevo');
 await $('transcript').onchange({target:{files:[{size:100,text:async()=>'{"words":[{"start":10,"end":11,"word":"Hola"},{"start":11,"end":12,"word":"mundo"}]}'}]}});
 $('master-name').value='master.mp4';$('master-name').onchange();
 await $('words').children[0].onclick();await $('words').children[1].onclick();await $('add-block').onclick();
 const p=JSON.parse(stored.get('abrxs-review-project-v1'));
 assert.equal(p.clips.length,1);assert.equal(p.clips[0].blocks[0].start,10);assert.equal(p.clips[0].blocks[0].end,12);assert.equal(p.clips[0].blocks[0].text,'Hola mundo');assert.equal($('timeline').children.length,1);
 await $('editorial-txt').onclick();assert(downloads.includes('DECISIONES_ABRXS.txt'));
 await $('new-clip').onclick();assert.equal(JSON.parse(stored.get('abrxs-review-project-v1')).clips.length,2);
 $('note-text').value='Ajustar cierre';await $('add-note').onclick();assert($('notice').textContent.includes('Selecciona el archivo'));
 await $('local-video').onchange({target:{files:[Object.assign(new Blob(['synthetic'],{type:'video/mp4'}),{name:'master.mp4',lastModified:1})]}});
 $('mark-now').onclick();await $('add-note').onclick();assert.equal(JSON.parse(stored.get('abrxs-review-project-v1')).notes.length,1);
 $('new-project').onclick();assert.equal(JSON.parse(stored.get('abrxs-review-project-v1')).notes.length,0);assert.equal(video.getAttribute('src'),null);
 window.AbrxsDrive.list=async folder=>folder==='sub'?[{id:'private-video',name:'clip.mp4',mimeType:'video/mp4',size:200000000,videoMediaMetadata:{durationMillis:'90000'},capabilities:{canDownload:false}}]:[{id:'sub',name:'Entregas',mimeType:'application/vnd.google-apps.folder'}];
 await $('root').onclick();await $('files').children[0].onclick();assert.equal($('folder-back').disabled,false);
 await $('files').children[0].onclick();assert.equal($('drive-player').getAttribute('src'),'https://drive.google.com/file/d/private-video/preview');assert.equal(video.getAttribute('src'),null);assert.equal(video.hidden,true);assert.equal($('mark-now').disabled,false);assert.equal($('download-video').hidden,true);assert.equal($('range-play').hidden,true);
 $('note-start').value='00:00:10.000';$('note-end').value='00:00:12.000';$('note-text').value='Cortar pausa';await $('add-note').onclick();const note=JSON.parse(stored.get('abrxs-review-project-v1')).notes[0];assert.equal(note.timeEntry,'manual');assert.equal(note.sourceKey,'drive:private-video');
 $('file-search').value='inexistente';$('file-search').oninput();assert($('files').textContent.includes('Sin resultados'));
 await $('folder-refresh').onclick();assert.equal($('folder-back').disabled,false);await $('folder-back').onclick();assert($('files').textContent.includes('Entregas'));
 await $('disconnect').onclick();assert.equal($('drive-player').getAttribute('src'),null);assert.equal($('folder-back').disabled,true);
 // Selecting even a small clip never downloads it. Native mode is explicit.
 let mediaCalls=0,blobCalls=0;
 window.AbrxsDrive.media=async()=>{mediaCalls++;return '/stream';};
 window.AbrxsDrive.blob=async()=>{blobCalls++;return 'blob:synthetic';};
 const small={id:'small',name:'short.mp4',mimeType:'video/mp4',size:'20000000',videoMediaMetadata:{durationMillis:'60000'}};
 await window.AbrxsWeb.select(small);assert.equal(blobCalls,0);assert.equal(video.hidden,true);
 await $('drive-precision').onclick();assert.equal(blobCalls,1);assert.equal(mediaCalls,0);assert.equal($('drive-player').getAttribute('src'),null);assert.equal(video.hidden,false);
 // linkedom doesn't reflect video.src; mirror browser attribute reflection.
 video.setAttribute('src',video.src);
 video.currentTime=42;video.dispatchEvent(new window.Event('loadedmetadata'));assert.equal(video.currentTime,0);
 video.dispatchEvent(new window.Event('canplay'));assert($('media-status').textContent.includes('Listo'));
 await window.AbrxsWeb.select(small);await $('drive-precision').onclick();assert.equal(blobCalls,2);video.setAttribute('src',video.src);video.currentTime=18;video.dispatchEvent(new window.Event('loadedmetadata'));assert.equal(video.currentTime,0);
 // Switching to Google while a previous native load is pending cannot restore it.
 let finish;window.AbrxsDrive.blob=()=>new Promise(resolve=>finish=resolve);
 const pending=$('drive-precision').onclick();await $('drive-online').onclick();finish('blob:stale');await pending;assert.equal(video.getAttribute('src'),null);assert.equal(video.hidden,true);
 await window.AbrxsWeb.select({...small,id:'large',size:'9000000000'});assert.equal(blobCalls,2);assert($('drive-player').getAttribute('src').includes('/large/preview'));
 window.AbrxsDrive.media=async()=>{throw Error('Sesión caducada');};await $('drive-precision').onclick();assert($('media-status').textContent.includes('Sesión caducada'));
 console.log('Review DOM: transcript selection, cards, timeline, TXT download, timed note and project isolation OK.');
})().catch(e=>{console.error(e);process.exitCode=1;});
