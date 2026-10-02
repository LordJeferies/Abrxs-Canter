(()=>{
  const epochs=new WeakMap(),paths=new WeakMap();
  async function attach(video,path){if(paths.get(video)===path&&video.getAttribute('src'))return;paths.set(video,path);const epoch=(epochs.get(video)||0)+1;epochs.set(video,epoch);video.pause();video.removeAttribute('src');video.load();if(!path)return;try{const url=await window.__TAURI__.core.invoke('media_source',{path});if(epochs.get(video)!==epoch)return;video.src=url;video.load();}catch(error){if(epochs.get(video)===epoch){paths.delete(video);window.AbrxsActivity?.add('Reproductor',String(error),true);throw error;}}}
  window.AbrxsMedia={attach};
})();
