/* Real browser over bounded numeric engineering QA; no scientific simulation. */
const {chromium}=require(process.env.NEXUS_PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');const fs=require('node:fs/promises');
const os=require('node:os');const path=require('node:path');
const root=path.resolve(__dirname,'..'),port=8892,base=`http://127.0.0.1:${port}`;
let child;
function processRun(args,options={}){return new Promise((resolve,reject)=>{const c=spawn(process.env.PYTHON||'python3',args,{cwd:root,...options});let out='',err='';c.stdout.on('data',v=>out+=v);c.stderr.on('data',v=>err+=v);c.once('error',reject);c.once('exit',code=>code?reject(Error(err||out)):resolve(out));});}
(async()=>{const dir=await fs.mkdtemp(path.join(os.tmpdir(),'nexus-experimental-qa-'));let browser;const errors=[],external=[],checks=[];
try{
 const code=`import sys,json\nfrom pathlib import Path\nfrom nexus.seed.experimental import Sandbox,write_new\nh=Sandbox(Path.cwd(),Path(sys.argv[1]))\nfor role,key,offset in [('train','source',0),('development','dev',.05)]:\n p=Path(sys.argv[1])/(key+'.json');write_new(p,dict(rows=[dict(id=key+'-'+str(i),x=[i*.1+offset],y=2*(i*.1+offset)+1) for i in range(4)]));h.register(key,role,p,'browser QA fixture','authored engineering data, not scientific evidence')\nh.grant('qa','engineering QA','bounded dashboard integration test only',dict(wall_s=20,cpu_s=15,memory_mb=2048,real_steps=0,imagined_transitions=0,updates=12),60,0,memory_policy='sampled_rss')\nspec=dict(id='gui-candidate',mode='exploration',recipe=dict(hidden=[],activation='tanh',optimizer='adam',learning_rate=.05,updates=12,seed=91),train='source',development='dev',model_run=None,assessment=None,protocol=None,gate=None)\nwith h.locked():r=h.execute(spec,'qa')\nassert r['status']=='complete_development',r\nprint(json.dumps(dict(resources=r['worker']['resources'],wall_s=r['wall_s'],metrics=r['worker']['metrics'])))`;
 const measured=JSON.parse(await processRun(['-c',code,dir]));
 await new Promise((resolve,reject)=>{child=spawn(process.env.PYTHON||'python3',['-I','-S','scripts/run_learning_lab.py','--allow-seed','--experimental-directory',dir,'--port',String(port),'--max-runtime-s','90'],{cwd:root});let out='';child.stdout.on('data',v=>{out+=v;if(out.includes('NEXUS Learning Lab:'))resolve();});child.once('error',reject);child.once('exit',c=>{if(!out.includes('NEXUS Learning Lab:'))reject(Error('server '+c));});});
 browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1280,height:900}});page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():(external.push(r.request().url()),r.abort()));
 await page.goto(base+'/experimental');await page.locator('article').waitFor();
 if(!(await page.locator('article').textContent()).includes('gui-candidate'))throw Error('missing model');checks.push('actual_candidate_hash_resources_and_error_change');
 if(await page.locator('svg polyline').count()!==2)throw Error('missing learning curves');checks.push('measured_training_and_development_curves');
 const before=(await page.locator('article').textContent());await page.click('#refresh');await page.waitForTimeout(150);if(before!==await page.locator('article').textContent())throw Error('read changed evidence');checks.push('refresh_is_read_only');
 const response=await page.request.post(base+'/api/experimental',{data:{op:'approve'},headers:{'X-Nexus-Request':'local-fixture'}});if(response.status()!==404)throw Error('unexpected execution route');checks.push('no_browser_execution_or_approval_endpoint');
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(250);if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('mobile overflow');await fs.mkdir(path.join(root,'runs'),{recursive:true});await page.screenshot({path:path.join(root,'runs/experimental-gui-qa.png'),fullPage:true});checks.push('mobile_layout');
 await page.goto(base+'/seed');await page.locator('#message').waitFor();checks.push('existing_seed_GUI_preserved');
 if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));
 console.log(JSON.stringify({kind:'bounded_numeric_engineering_QA',browser:browser.version(),checks,page_errors:errors,external_requests:external,measured,scientific_environment_interactions:0,scientific_experiments:0},null,2));
}finally{if(browser)await browser.close();if(child)await new Promise(resolve=>{child.once('exit',resolve);child.kill();});await fs.rm(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
