const {parseHTML}=require('../.build-cache/ui-tests/node_modules/linkedom');
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),{randomUUID}=require('crypto');
const {window}=parseHTML('<body><aside class="ux-sidebar"><nav></nav></aside></body>');
const listeners={},stored={},runs=[];let cancelled=0,pump;
Object.assign(window,{console,structuredClone,setTimeout,clearTimeout,setInterval:fn=>(pump=fn),state:{project:{id:'one',name:'Uno'},running:false},AbrxsStudio:{busy:false},localStorage:{getItem:k=>stored[k]||null,setItem:(k,v)=>stored[k]=v}});
window.__TAURI__={event:{listen:(key,fn)=>listeners[key]=fn},core:{invoke:async()=>{cancelled++;}}};
vm.runInContext(fs.readFileSync('dist/processes.js','utf8'),vm.createContext(window));
const q=window.AbrxsProcesses,tick=()=>new Promise(resolve=>setTimeout(resolve,10));
(async()=>{
 q.mount();assert.ok(window.document.getElementById('processOpen'));
 q.register(async task=>runs.push(task));
 q.enqueue({op:'export',ids:['a']},{video:'/a.mp4'},'one');await tick();
 q.enqueue({op:'export',ids:['b']},{video:'/b.mp4'},'one');await tick();assert.equal(runs.length,1);
 q.finish(true);await tick();assert.equal(runs.length,2);assert.equal(runs[1].payload.video,'/b.mp4');
 q.show();const cancel=window.document.querySelector('[data-action="cancel"]');cancel.dispatchEvent(new window.Event('click',{bubbles:true}));await tick();assert.equal(cancelled,1);
 q.finish(false,'Cancelado');await tick();assert.ok(stored['abrxs-processes-v1'].includes('cancelled'));
 q.enqueue({op:'import'},{},'other');await tick();assert.equal(runs.length,2);
 console.log('PASS: serial queue, context snapshots, cancel confirmation, persistence and project isolation.');
})().catch(e=>{console.error(e);process.exitCode=1;});
