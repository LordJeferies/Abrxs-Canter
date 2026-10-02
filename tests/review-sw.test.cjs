const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const events={},requests=[],errors=[];let cached=[];
const context={URL,Map,Headers,Response,Date,fetch:async(url,opt)=>{requests.push({url,opt});return new Response('data',{status:206,headers:{'Content-Range':'bytes 0-3/20','Content-Length':'4'}});},caches:{open:async()=>({addAll:async urls=>{cached=urls;}}),match:()=>{}},self:{location:{href:'https://example.org/review/sw.js'},clients:{claim:async()=>{},get:async()=>({url:'https://example.org/review/index.html',postMessage:m=>errors.push(m)})},skipWaiting:async()=>{},addEventListener:(name,fn)=>events[name]=fn}};
vm.runInNewContext(fs.readFileSync(require.resolve('../review-web/sw.js'),'utf8'),context);
function message(data,client='tab1'){let result;events.message({data,source:{id:client},ports:[{postMessage:x=>result=x}]});return result;}
async function request(session,client='tab1',range='bytes=0-3'){let promise;events.fetch({clientId:client,request:new Request('https://example.org/review/__drive_media__/'+session+'/file1',{headers:{Range:range}}),respondWith:p=>promise=p});return promise;}
(async()=>{
 await new Promise((resolve,reject)=>events.install({waitUntil:p=>p.then(resolve,reject)}));
 assert(cached.every(u=>!u.includes('__drive_media__')));
 assert(message({op:'auth',session:'s1',token:'private-test-token',expires:Date.now()+60000}).ok);
 assert(message({op:'allow',session:'s1',id:'file1',mime:'video/mp4'}).ok);
 const r=await request('s1');assert.equal(r.status,206);assert.equal(r.headers.get('Content-Range'),'bytes 0-3/20');assert.equal(r.headers.get('Cache-Control'),'no-store');
 assert.equal(requests[0].opt.headers.Range,'bytes=0-3');assert.equal(requests[0].opt.headers.Authorization,'Bearer private-test-token');assert(!requests[0].url.includes('token'));
 assert.equal((await request('s1','other-tab')).status,401);
 assert.equal((await request('s1','tab1','bytes=0-3,10-20')).status,416);
 assert(!message({op:'allow',session:'s1',id:'../unsafe',mime:'video/mp4'}).ok);
 assert(message({op:'logout',session:'s1'}).ok);assert.equal((await request('s1')).status,401);
 const sid='acdb1234-1234-1234-1234-123456789abc';assert(message({op:'auth',session:sid,token:'test',expires:Date.now()+60000}).ok);assert(message({op:'allow',session:sid,id:'file1',mime:'video/mp4'}).ok);
 assert.equal((await request(sid,'')).status,206);assert.equal((await request(sid,'other-tab')).status,401);
 context.self.clients.get=async()=>({url:'https://example.org/other-app/',postMessage:()=>{}});assert.equal((await request(sid,'')).status,401);
 context.fetch=async()=>{const e=new Error('cancelled');e.name='AbortError';throw e;};const before=errors.length;assert.equal((await request(sid,'tab1')).status,499);assert.equal(errors.length,before);
 console.log('Review SW: Range forwarding, memory-only auth, client isolation, logout and no media cache OK.');
})().catch(e=>{console.error(e);process.exitCode=1;});
