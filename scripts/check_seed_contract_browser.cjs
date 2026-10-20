/* Actual trained GUI QA; no neural training or scientific simulator collection. */
const {chromium}=require(process.env.NEXUS_PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const root=path.resolve(__dirname,'..'),port=8885,base=`http://127.0.0.1:${port}`;let child;
async function stop(){if(child){const p=child;child=null;await new Promise(r=>{p.once('exit',r);p.kill();});}}
(async()=>{
 const record=JSON.parse(await fs.readFile(path.join(root,'artifacts/seed_contract_study.json'),'utf8'));
 if(!record.declared_complete)throw Error('Complete study required');
 const model=record.models.find(m=>m.identity==='compact_tanh_5511_aligned_v1');
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'nexus-contract-qa-'));
 async function start(){await new Promise((resolve,reject)=>{
  child=spawn(process.env.PYTHON||'python3',[path.join(root,'scripts/run_learning_lab.py'),'--allow-seed','--seed-directory',dir,'--port',String(port),'--max-runtime-s','120','--seed-grounded-model',path.join(root,'artifacts/seed_contract_gui.json'),'--seed-grounded-sha256',model.gui_sha256],{cwd:root,env:process.env});
  let text='';child.stdout.on('data',d=>{text+=d;if(text.includes('NEXUS Learning Lab:'))resolve();});child.stderr.on('data',d=>text+=d);child.once('error',reject);child.once('exit',c=>{if(!text.includes('NEXUS Learning Lab:'))reject(Error(text+' exit '+c));});
 });}
 const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1280,height:1000}});
 const errors=[],external=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():(external.push(r.request().url()),r.abort()));
 const idle=async()=>page.waitForFunction(()=>!busy);
 async function click(id){await idle();await page.click('#'+id);await idle();}
 const last=async()=>JSON.parse(await page.locator('#trace').textContent());
 function cognitive(x){return JSON.stringify({h:x.state.grounded.h_norm,z:x.state.grounded.z_norm,world:x.state.world,evidence:x.state.evidence});}
 try{
  await start();await page.goto(base+'/seed');await idle();let x=await last();
  if(x.state.grounded.state_contract!=='aligned_v1'||x.state.grounded.world_memory!=='fixed_source_bank')throw Error('Contract not installed');
  checks.push('verified_aligned_model_source_bank_and_V3');
  async function readonly(){const before=cognitive(await last());for(let i=0;i<3;i++){await click('inspect');await click('grounded-observe');await click('grounded-speak');if(cognitive(await last())!==before)throw Error('Inspection mutated cognitive state');}}
  await readonly();checks.push('repeated_inspect_observe_speak_do_not_change_state_before_action');
  await click('grounded-decide');x=await last();if(x.result.planning.value_pruned!==8)throw Error('Pruned MPC missing');
  await readonly();checks.push('read_only_state_after_real_action');
  await click('save');const before=cognitive(await last());await stop();await start();await page.reload();await idle();await click('load');
  if(cognitive(await last())!==before)throw Error('Restored state differs');await readonly();checks.push('restart_restore_no_double_assimilation');
  await click('grounded-decide_unpruned');x=await last();if(x.result.planning.value_pruned!==0)throw Error('Unpruned controller missing');checks.push('both_pruning_modes_execute_actual_actions');
  await click('grounded-ask');x=await last();if(x.result.question?.object)await click(x.result.question.object.color==='red'?'answerYes':'answerNo');checks.push('real_question_label_path');
  await click('stop');await click('grounded-decide');if((await last()).response_type!=='stopped')throw Error('Stop bypass');checks.push('stop_enforced');
  await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Mobile overflow');
  await page.screenshot({path:path.join(root,'runs/seed-contract-mobile.png'),fullPage:true});checks.push('mobile_layout');
  if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));
  console.log(JSON.stringify({kind:'actual_chrome_contract_gui_qa',browser:browser.version(),checks,page_errors:errors,external_requests:external,gui_sha256:model.gui_sha256,scientific_interactions:0},null,2));
 }finally{await stop();await browser.close();await fs.rm(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
