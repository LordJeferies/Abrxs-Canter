'use strict';
const CACHE='abrxs-review-shell-v5',base=new URL('./',self.location.href),sessions=new Map();
const shell=['./','index.html','style.css?v=5','core.js?v=5','drive.js?v=5','app.js?v=5','studio.js?v=5','manifest.webmanifest','icon.svg'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(shell.map(p=>new URL(p,base).href))).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('abrxs-review-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('message',e=>{
 const d=e.data||{},port=e.ports[0],client=e.source;
 if(!client?.id||!port)return;
 if(d.op==='auth'&&typeof d.token==='string'&&d.token.length<10000&&typeof d.session==='string'&&Number.isFinite(d.expires)){
   for(const[k,v]of sessions)if(v.client===client.id||v.expires<Date.now())sessions.delete(k);
   sessions.set(d.session,{client:client.id,token:d.token,expires:d.expires,files:new Map()});port.postMessage({ok:true});return;
 }
 const s=sessions.get(d.session);
 if(!s||s.client!==client.id){port.postMessage({error:'Sesión no autorizada.'});return;}
 if(d.op==='logout'){sessions.delete(d.session);port.postMessage({ok:true});return;}
 if(d.op==='allow'&&/^[\w-]+$/.test(d.id)&&/^(video\/[\w.+-]+|image\/(jpeg|png|webp|gif|avif))$/.test(d.mime)){s.files.set(d.id,d.mime);port.postMessage({ok:true});return;}
 port.postMessage({error:'Petición inválida.'});
});
async function media(request,clientId,url){
 const parts=url.pathname.slice(base.pathname.length).split('/'),s=sessions.get(parts[1]),id=parts[2];
 const error=async(status,message)=>{const client=await self.clients.get(s?.client||clientId);client?.postMessage({op:'media-error',message});return new Response(message,{status,headers:{'Cache-Control':'no-store'}});};
 // Safari media requests can omit clientId. Only accept the unguessable,
 // short-lived session URL while its authorized owner is still in this app.
 let ownerValid=false;
 if(s&&!clientId&&/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(parts[1])){const owner=await self.clients.get(s.client);if(owner?.url){const u=new URL(owner.url);ownerValid=u.origin===base.origin&&u.pathname.startsWith(base.pathname);}}
 if(!s||(s.client!==clientId&&!ownerValid)||s.expires<Date.now()||!s.files.has(id))return error(401,'Sesión caducada o video no autorizado. Vuelve a conectar Drive y selecciona el video.');
 const range=request.headers.get('Range');if(range&&!/^bytes=\d*-\d*$/.test(range))return error(416,'Intervalo de video inválido.');
 try{
   const headers={Authorization:'Bearer '+s.token};if(range)headers.Range=range;
   const upstream=await fetch('https://www.googleapis.com/drive/v3/files/'+encodeURIComponent(id)+'?alt=media',{method:request.method,headers,cache:'no-store',referrerPolicy:'no-referrer',signal:request.signal});
   if(!upstream.ok)return error(upstream.status,'Drive '+upstream.status+'. Revisa sesión y permiso de descarga.');
   const h=new Headers({'Content-Type':s.files.get(id),'Cache-Control':'no-store','Accept-Ranges':'bytes'});
   for(const key of ['Content-Length','Content-Range'])if(upstream.headers.has(key))h.set(key,upstream.headers.get(key));
   return new Response(request.method==='HEAD'?null:upstream.body,{status:upstream.status,headers:h});
 }catch(e){if(e.name==='AbortError')return new Response(null,{status:499,headers:{'Cache-Control':'no-store'}});return error(502,'No se pudo leer Drive. Comprueba conexión o usa el visor online de Google.');}
}
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);if(u.origin!==base.origin||!u.pathname.startsWith(base.pathname))return;
 if(u.pathname.startsWith(base.pathname+'__drive_media__/')){if(['GET','HEAD'].includes(e.request.method))e.respondWith(media(e.request,e.clientId,u));return;}
 // Only our explicit public app shell is cached. Never videos, tokens or API responses.
 if(e.request.method==='GET'&&shell.some(p=>new URL(p,base).href===u.href))e.respondWith(fetch(e.request,{cache:'no-cache'}).then(async r=>{if(r.ok){const cache=await caches.open(CACHE);await cache.put(e.request,r.clone());}return r;}).catch(()=>caches.match(e.request)));
});
