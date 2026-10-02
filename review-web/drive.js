/* OAuth token flow based on Google Workspace browser-samples/drive/quickstart.
 * https://github.com/googleworkspace/browser-samples (Apache-2.0).
 * Google Identity Services is loaded remotely ONLY when the user requests it.
 */
(function(){
 'use strict';
 let token='',expires=0,worker=null,session='',fallbackAbort=null,authClient=null,loginPending=false,authEpoch=0,canWrite=false;
 const scope='https://www.googleapis.com/auth/drive.readonly';
 const report=(message)=>window.dispatchEvent(new CustomEvent('drive-status',{detail:message}));
 async function load(){
   if(window.google?.accounts?.oauth2)return;
   if(location.protocol==='file:')throw Error('Abre la página mediante localhost o GitHub Pages, no como archivo HTML.');
   if(document.getElementById('google-gis'))throw Error('Google está cargando. Espera unos segundos y vuelve a pulsar.');
   await new Promise((resolve,reject)=>{
     const s=document.createElement('script');s.id='google-gis';s.src='https://accounts.google.com/gsi/client';s.async=true;
     const timeout=setTimeout(()=>{s.remove();reject(Error('Google no respondió. Revisa la conexión y los bloqueadores.'));},15000);
     s.onload=()=>{clearTimeout(timeout);resolve();};s.onerror=()=>{clearTimeout(timeout);s.remove();reject(Error('No se pudo cargar el inicio de sesión de Google.'));};document.head.append(s);
   });
 }
 function readyToken(){if(!token||Date.now()>expires)throw Error('La sesión de Drive ha caducado o no está conectada. Pulsa Iniciar sesión en Drive.');return token;}
 function connect(clientId,write=false){
   if(!/^[\w.-]+\.apps\.googleusercontent\.com$/.test(clientId))throw Error('Introduce el ID OAuth web público, no una clave ni un secreto.');
   if(!window.google?.accounts?.oauth2)throw Error('Pulsa primero Preparar inicio de sesión.');
   if(loginPending)throw Error('Ya hay una ventana de inicio de sesión pendiente.');
   loginPending=true;const epoch=++authEpoch;
   return new Promise((resolve,reject)=>{
     const requestedScope=scope+(write?' https://www.googleapis.com/auth/drive.file':'');
     authClient=google.accounts.oauth2.initTokenClient({client_id:clientId,scope:requestedScope,
       callback:async response=>{loginPending=false;if(epoch!==authEpoch)return reject(Error('Inicio de sesión cancelado.'));
         if(response.error)return reject(Error('Google rechazó la conexión: '+response.error));
         if(!google.accounts.oauth2.hasGrantedAllScopes(response,scope))return reject(Error('No se concedió lectura de Drive.'));
         token=response.access_token;expires=Date.now()+Math.max(0,Number(response.expires_in)-60)*1000;
         canWrite=write&&google.accounts.oauth2.hasGrantedAllScopes(response,'https://www.googleapis.com/auth/drive.file');
         try{await syncWorker();resolve();}catch(e){report('Drive conectado; reproducción por streaming no disponible. '+e.message);resolve();}
       },error_callback:response=>{loginPending=false;reject(Error('Ventana de Google: '+response.type+'. Abre en Safari si la PWA bloquea el inicio.'));}});
     try{authClient.requestAccessToken({prompt:'consent'});}catch(e){loginPending=false;reject(e);}
   });
 }
 async function api(path,params={}){
   const u=new URL('https://www.googleapis.com/drive/v3/'+path);for(const [k,v]of Object.entries(params))u.searchParams.set(k,v);
   const r=await fetch(u,{headers:{Authorization:'Bearer '+readyToken()},cache:'no-store',referrerPolicy:'no-referrer'});
   if(!r.ok){if(r.status===401)throw Error('Sesión caducada. Vuelve a conectar Drive.');throw Error('Drive '+r.status+': revisa permisos, cuotas y que Drive API esté habilitada.');}return r.json();
 }
 function folderId(value){const s=String(value).trim();if(!s)return 'root';const m=s.match(/\/folders\/([\w-]+)/);const id=m?m[1]:s;if(!/^[\w-]+$/.test(id))throw Error('Pega un enlace de carpeta de Drive o su ID.');return id;}
 async function list(value){
   const id=folderId(value),files=[];let pageToken='';
   do{const data=await api('files',{q:"'"+id+"' in parents and trashed = false and (mimeType contains 'video/' or mimeType contains 'image/' or mimeType = 'text/plain' or mimeType = 'application/json' or mimeType = 'application/vnd.google-apps.folder')",fields:'nextPageToken,files(id,name,mimeType,size,parents,resourceKey,videoMediaMetadata(durationMillis,width,height),capabilities(canDownload,canAddChildren))',orderBy:'folder,name',pageSize:'100',supportsAllDrives:'true',includeItemsFromAllDrives:'true',...(pageToken?{pageToken}:{})});files.push(...(data.files||[]));pageToken=data.nextPageToken;if(files.length>=2000){report('Se muestran hasta 2000 archivos. Abre una subcarpeta para ver más.');break;}}while(pageToken);
   return files;
 }
 function message(payload){return new Promise((resolve,reject)=>{
   if(!worker)return reject(Error('No hay reproductor de streaming disponible.'));
   const ch=new MessageChannel(),timer=setTimeout(()=>reject(Error('El reproductor no respondió. Recarga la página.')),5000);
   ch.port1.onmessage=e=>{clearTimeout(timer);ch.port1.close();e.data?.ok?resolve(e.data):reject(Error(e.data?.error||'Error de reproducción.'));};worker.postMessage(payload,[ch.port2]);
 });}
 async function syncWorker(){
   if(!('serviceWorker' in navigator))throw Error('Este navegador no admite el reproductor privado.');
   await navigator.serviceWorker.register('./sw.js');const registration=await navigator.serviceWorker.ready;worker=registration.active;
   if(!navigator.serviceWorker.controller)await new Promise((resolve,reject)=>{const t=setTimeout(()=>{navigator.serviceWorker.removeEventListener('controllerchange',change);reject(Error('Recarga una vez para activar el reproductor.'));},4000);function change(){clearTimeout(t);resolve();}navigator.serviceWorker.addEventListener('controllerchange',change,{once:true});});
   session=crypto.randomUUID();await message({op:'auth',session,token:readyToken(),expires});
 }
 async function media(file){
   // Re-authorize even if iOS discarded the worker's in-memory session.
   readyToken();await syncWorker();
   await message({op:'allow',session,id:file.id,mime:file.mimeType});return new URL('__drive_media__/'+session+'/'+encodeURIComponent(file.id),location.href).href;
 }
 async function blob(file){
   if(!file.size||Number(file.size)>150*1024*1024)throw Error('Carga completa limitada a clips de hasta 150 MB. Usa el streaming o descarga el video con Drive y ábrelo como archivo local.');
   fallbackAbort?.abort();const controller=new AbortController();fallbackAbort=controller;
   const timer=setTimeout(()=>controller.abort(),45000);
   try{
     const r=await fetch('https://www.googleapis.com/drive/v3/files/'+encodeURIComponent(file.id)+'?alt=media',{headers:{Authorization:'Bearer '+readyToken()},signal:controller.signal,cache:'no-store',referrerPolicy:'no-referrer'});
     if(!r.ok)throw Error('No se pudo descargar: Drive '+r.status);
     const data=await r.blob();if(!data.size)throw Error('Drive devolvió un archivo vacío.');
     if(data.size>150*1024*1024)throw Error('El archivo supera el límite de 150 MB.');
     return URL.createObjectURL(data);
   }catch(e){if(e.name==='AbortError'&&fallbackAbort===controller)throw Error('La carga se interrumpió o agotó su tiempo. Reintenta o abre en Drive.');throw e;}
   finally{clearTimeout(timer);if(fallbackAbort===controller)fallbackAbort=null;}
 }
 function cancelMedia(){const previous=fallbackAbort;fallbackAbort=null;previous?.abort();}
 async function disconnect(){
   ++authEpoch;loginPending=false;canWrite=false;fallbackAbort?.abort();const previous=token;token='';expires=0;
   if(worker&&session)try{await message({op:'logout',session});}catch(e){report(e.message);}session='';
   if(previous&&window.google?.accounts?.oauth2)google.accounts.oauth2.revoke(previous,()=>{});
 }
 async function text(file){if(Number(file.size)>20*1024*1024)throw Error('Archivo de información mayor de 20 MB.');const r=await fetch('https://www.googleapis.com/drive/v3/files/'+encodeURIComponent(file.id)+'?alt=media',{headers:{Authorization:'Bearer '+readyToken()},cache:'no-store'});if(!r.ok)throw Error('No se pudo leer la información: Drive '+r.status);const raw=await r.text();if(raw.length>20*1024*1024)throw Error('Información demasiado grande.');return raw;}
 async function uploadText(parent,name,text){if(!canWrite)throw Error('Autoriza Guardar revisiones en Drive primero.');const boundary='abrxs-'+crypto.randomUUID(),metadata={name,mimeType:'text/plain',parents:[folderId(parent)]};const body='--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+JSON.stringify(metadata)+'\r\n--'+boundary+'\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'+text+'\r\n--'+boundary+'--';const r=await fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true&fields=id,name,parents,webViewLink',{method:'POST',headers:{Authorization:'Bearer '+readyToken(),'Content-Type':'multipart/related; boundary='+boundary},body});if(!r.ok)throw Error('Drive '+r.status+': necesitas permiso para añadir archivos a esa carpeta y autorizarla a la aplicación. El TXT puede descargarse; no se modificó ningún original.');return r.json();}
 window.AbrxsDrive={load,connect,list,media,blob,disconnect,text,uploadText,cancelMedia};
 if('serviceWorker' in navigator)navigator.serviceWorker.addEventListener('message',e=>{if(e.data?.op==='media-error')report('Reproducción: '+e.data.message);});
})();
