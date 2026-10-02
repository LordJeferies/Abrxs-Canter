/* Prueba de DOM e interacciones, sin screenshots ni videos del usuario.
   Requiere Playwright disponible y CHROME_EXECUTABLE apuntando a Chrome local. */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const assert=require('assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:900}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.setContent(fs.readFileSync(path.join(root,'dist/index.html'),'utf8').replace(/<script[^>]*src[^>]*><\/script>/g,''));
    for(const file of ['styles.css','stage1.css','studio.css'])await page.addStyleTag({content:fs.readFileSync(path.join(root,'dist',file),'utf8')});
    await page.evaluate(()=>{
      window.confirm=()=>false;
      window.savedWorkspace={fragments:[],positions:{},view:'grid',visual:null};
      const source={path:'/synthetic/master.mp4',sampleHash:'abc',size:100};
      window.fixture={id:'clip1',revision:1,title:'Clip de prueba',source,duration:60,blocks:[{uid:'a',start:1,end:5,text:'Hola mundo',role:'SECCION'}],status:'draft',format:{aspect:'original',mode:'contain',x:.5,y:.5}};
      window.__TAURI__={core:{convertFileSrc:()=>'',invoke:async(name,args)=>{
        if(name==='list_projects')return [];
        if(name==='stage1_query'){
          const r=args.request;
          if(r.op==='library')return {clips:r.projectPath==='/project/one'?[window.fixture]:[],assets:[],draft:null};
          if(r.op==='studio_load')return window.savedWorkspace;
          if(r.op==='studio_save'){window.savedWorkspace=r.workspace;return r.workspace;}
          if(r.op==='source')return {source,media:{duration:60,width:1920,height:1080},words:[{text:'Hola',start:1,end:2},{text:'mundo',start:2,end:3}],assets:null};
          if(r.op==='draft')return {saved:true};
          if(r.op==='studio_visual')return {samples:[]};
        }
        return {};
      }},dialog:{open:async()=>null},event:{listen:async()=>()=>{}}};
    });
    for(const file of ['app.js','stage1-core.js','stage1.js'])await page.addScriptTag({content:fs.readFileSync(path.join(root,'dist',file),'utf8')});
    await page.evaluate(()=>{state.project={id:'one',path:'/project/one',name:'Proyecto uno'};state.video='/synthetic/master.mp4';document.getElementById('welcomeView').classList.add('hidden');document.getElementById('studioView').classList.remove('hidden');});
    await page.click('#ac-launch');await page.waitForSelector('[data-edit="clip1"]');
    await page.click('[data-view="map"]');await page.waitForSelector('.ac-map-node');
    assert.equal(await page.locator('.ac-map-node').count(),3);
    await page.click('[data-edit="clip1"]');await page.waitForSelector('#ac-editor:not([hidden])');
    assert.equal(await page.locator('#ac-cards').isVisible(),false);
    await page.locator('[data-word="0"]').dispatchEvent('pointerdown',{button:0});
    await page.mouse.up();await page.click('#ac-store');
    assert.equal(await page.evaluate(()=>window.savedWorkspace.fragments.length),1);
    await page.click('[data-pane="tray"]');assert.equal(await page.locator('[data-tray-add]').count(),1);
    await page.click('#ac-focus');assert.equal(await page.locator('.ac-transcript').isVisible(),false);
    await page.click('#ac-focus');await page.click('#ac-library');
    await page.click('#ac-close');
    await page.evaluate(()=>{state.project={id:'two',path:'/project/two',name:'Proyecto dos'};window.savedWorkspace={fragments:[],positions:{},view:'grid',visual:null};});
    await page.click('#ac-launch');assert.equal(await page.locator('[data-edit="clip1"]').count(),0);
    assert.deepEqual(errors,[]);
    console.log('OK: inicialización UI, mapa, bandeja, enfoque, paneles ocultos y aislamiento entre proyectos. Sin screenshots.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
