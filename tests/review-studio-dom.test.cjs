/* Lightweight DOM checks; not a Safari/Drive media compatibility test. */
const {parseHTML}=require('../.build-cache/ui-tests/node_modules/linkedom');
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {window}=parseHTML(fs.readFileSync('review-web/index.html','utf8')),stored=new Map();
Object.assign(window,{console,setTimeout:()=>0,clearTimeout:()=>{},URL,Blob,confirm:()=>true,location:{protocol:'http:',href:'http://localhost/'},localStorage:{getItem:k=>stored.get(k)||null,setItem:(k,v)=>stored.set(k,v)},AbrxsDrive:{list:async()=>[{id:'video1',name:'video.mp4',mimeType:'video/mp4',parents:['folder1']},{id:'photo1',name:'photo.png',mimeType:'image/png',parents:['folder1']}],media:async()=>'/synthetic',text:async()=>'{"words":[{"start":0,"end":1,"word":"Hola"}]}',connect:async()=>{},uploadText:async()=>({id:'note'})}});
Object.defineProperty(window.HTMLSelectElement.prototype,'value',{get(){return this._value||this.querySelector('option')?.value||'';},set(v){this._value=v;}});
window.HTMLElement.prototype.showModal=function(){this.open=true;};window.HTMLElement.prototype.close=function(){this.open=false;};
const player=window.document.getElementById('player');Object.assign(player,{duration:60,currentTime:12,load:()=>{},play:async()=>{},pause(){this.dispatchEvent(new window.Event('pause'));}});
const ctx=vm.createContext(window);for(const file of ['core','app','studio'])vm.runInContext(fs.readFileSync('review-web/'+file+'.js','utf8'),ctx);
const $=id=>window.document.getElementById(id),find=text=>[...window.document.querySelectorAll('button')].find(b=>b.textContent===text);
(async()=>{
 $('folder').value='folder1';await $('browse').onclick();
 await find('Seleccionar videos e imágenes').onclick();await find('Añadir selección a revisión').onclick();assert.equal(window.AbrxsWeb.project.reviewFiles.length,2);assert.equal(window.document.querySelectorAll('.queue-item').length,2);
 await window.AbrxsWeb.select(window.AbrxsWeb.project.reviewFiles[1]);assert.equal($('review-photo').hidden,false);assert.equal(player.hidden,true);
 $('note-text').value='Corregir esta imagen';await $('add-note').onclick();const note=window.AbrxsWeb.project.notes[0];assert.equal(note.driveId,'photo1');assert.equal(note.folderId,'folder1');assert(window.AbrxsWeb.notesText().includes('https://drive.google.com/file/d/photo1/view'));
 await $('local-video').onchange({target:{files:[Object.assign(new Blob(['synthetic']),{name:'local.mp4',lastModified:1})]}});player.dispatchEvent(new window.Event('loadedmetadata'));
 $('note-start').value='00:00:05.000';$('note-end').value='00:00:08.000';player.currentTime=9;player.pause();assert.equal($('note-start').value,'00:00:05.000');assert.equal($('note-end').value,'00:00:08.000');
 let autoPaused=false;player.pause=()=>{autoPaused=true;};player.currentTime=14;$('note-text').dispatchEvent(new window.Event('focus'));assert.equal(autoPaused,false);assert.equal($('note-start').value,'00:00:05.000');assert.equal($('note-end').value,'00:00:08.000');
 $('note-text').value='Corrección manual';await $('add-note').onclick();assert.equal(window.AbrxsWeb.project.notes.at(-1).timeEntry,'manual');
 assert.equal(find('Desde ahora hasta la siguiente pausa'),undefined);assert.equal(player.parentElement.id,'review-surface');assert.notEqual(window.document.querySelector('.review-composer').parentElement.className,'player-panel');
 await $('review-fullscreen').onclick();assert.equal(window.document.querySelector('.player-panel').classList.contains('expanded-player'),true);await $('review-fullscreen').onclick();assert.equal(window.document.querySelector('.player-panel').classList.contains('expanded-player'),false);
 await window.AbrxsWeb.select(window.AbrxsWeb.project.reviewFiles[0]);await $('review-fullscreen').onclick();assert.equal(window.document.querySelector('.player-panel').classList.contains('expanded-player'),false);assert($('notice').textContent.includes('Abrir en Drive'));
 await $('local-video').onchange({target:{files:[Object.assign(new Blob(['synthetic']),{name:'local.mp4',lastModified:1})]}});
 let nativeFullscreen=0;player.readyState=1;player.webkitEnterFullscreen=()=>nativeFullscreen++;await $('review-fullscreen').onclick();assert.equal(nativeFullscreen,1);assert.equal(window.document.querySelector('.player-panel').classList.contains('expanded-player'),false);
 $('new-project').onclick();assert.equal(window.document.querySelectorAll('.queue-item').length,0);
 console.log('PASS: media queue, image identity, manual notes unchanged on pause/focus, isolated viewer, fullscreen fallback, project isolation.');
})().catch(e=>{console.error(e);process.exitCode=1;});
