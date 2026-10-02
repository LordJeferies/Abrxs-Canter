const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const {parseHTML}=require('../.build-cache/ui-tests/node_modules/linkedom');
const {window}=parseHTML('<html><body><button id="outside">Importar</button></body></html>');
const store=new Map();Object.assign(window,{console,state:{project:{path:'/project/a'}},basename:p=>p.split('/').pop(),localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},__TAURI__:{dialog:{open:async()=>'/master.mp4'}}});
Object.defineProperty(window.HTMLSelectElement.prototype,'value',{get(){return this._value||this.querySelector('option')?.value||'';},set(v){this._value=v;}});
vm.runInContext(fs.readFileSync('dist/batch.js','utf8'),vm.createContext(window));
const $=id=>window.document.getElementById('batch-'+id);
(async()=>{
 let result=window.AbrxsBatch.plan('/decisions.json');$('cancel').onclick();assert.equal(await result,null);
 result=window.AbrxsBatch.plan('/decisions.json');$('accept').onclick();assert.equal((await result).exportAfterImport,false);
 result=window.AbrxsBatch.plan('/decisions.json');$('dual').checked=true;$('horizontal').value='/h.mp4';$('vertical').value='/v.mp4';$('action').value='export';$('accept').onclick();assert($('error').textContent.includes('Confirma'));$('synced').checked=true;$('accept').onclick();const p=await result;assert.equal(p.masters.length,2);assert(p.exportAfterImport);assert(p.sameTimelineConfirmed);
 window.state.project.path='/project/b';result=window.AbrxsBatch.plan('/decisions.json');assert.equal($('horizontal').value,'');$('cancel').onclick();await result;
 console.log('Batch DOM: cancel, cards-only default, explicit export, synchronization and project-specific preferences OK.');
})().catch(e=>{console.error(e);process.exitCode=1;});
