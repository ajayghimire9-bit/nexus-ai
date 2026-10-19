/* Actual Chrome plus trained local model. Authored UI QA, not a science trial. */
const {chromium}=require(process.env.NEXUS_PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const root=path.resolve(__dirname,'..'),port=8883,base=`http://127.0.0.1:${port}`;
let child=null;
async function stop(){if(child){const p=child;child=null;await new Promise(r=>{p.once('exit',r);p.kill();});}}
(async()=>{
 const receipt=JSON.parse(await fs.readFile(path.join(root,'artifacts/seed_grounded_pilot.json'),'utf8'));
 const model=receipt.models.find(m=>m.recipe==='compact_tanh');
 if(!receipt.declared_complete||!model)throw Error('Complete fixed deployment model required');
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nexus-grounded-qa-'));
 async function start(){await new Promise((resolve,reject)=>{
  child=spawn(process.env.PYTHON||'python3',[path.join(root,'scripts/run_learning_lab.py'),'--allow-seed','--seed-directory',directory,'--port',String(port),'--max-runtime-s','120','--seed-grounded-model',model.checkpoint,'--seed-grounded-sha256',model.sha256],{cwd:root,env:process.env});
  let output='';child.stdout.on('data',d=>{output+=d;if(output.includes('NEXUS Learning Lab:'))resolve();});child.stderr.on('data',d=>{output+=d;});child.once('error',reject);child.once('exit',c=>{if(!output.includes('NEXUS Learning Lab:'))reject(Error(output+' exit '+c));});
 });}
 const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1280,height:1000}});
 const errors=[],external=[],checks=[];let authoredRequests=0;page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():(external.push(r.request().url()),r.abort()));
 async function idle(){await page.waitForFunction(()=>!busy);}
 async function click(id){await idle();await page.click('#'+id);await idle();}
 async function last(){return JSON.parse(await page.locator('#trace').textContent());}
 try{
  await start();await page.goto(base+'/seed');await idle();
  if(!(await last()).state.grounded)throw Error('Model not connected');checks.push('verified_trained_model_connected');
  await click('grounded-observe');authoredRequests++;let x=await last();
  if(x.response_type!=='observed'||x.result.modalities.length!==3)throw Error('Multimodal observation failed');checks.push('real_multimodal_observation_and_canvas');
  await click('grounded-store');authoredRequests++;x=await last();
  if(x.text!=='blocked'||x.result.result.concept.status!=='needs_evidence')throw Error('False storage claim');checks.push('insufficient_concept_evidence_rejected_honestly');
  await click('grounded-ask');authoredRequests++;x=await last();if(!x.result.question?.object)throw Error('No question card');
  await click('answerYes');if(!(await last()).state.evidence.length)throw Error('No actual label');checks.push('neural_action_question_and_real_human_label_path');
  await click('grounded-speak');authoredRequests++;x=await last();if(typeof x.result.generated_candidate!=='string'||x.result.candidate_verified!==false)throw Error('Language candidate hidden');checks.push('actual_local_decoder_candidate_and_factual_template');
  await click('grounded-decide');authoredRequests++;x=await last();if(x.response_type!=='acted'||x.result.planning.value_pruned!==8)throw Error('Latent MPC did not run');checks.push('real_latent_mpc_scoring_and_action');
  await click('save');const before=(await last()).state.grounded;
  await stop();await start();await page.reload();await idle();await click('load');x=await last();
  if(x.state.grounded.h_norm!==before.h_norm||x.state.grounded.z_norm!==before.z_norm)throw Error('Recurrent restart mismatch');checks.push('python_restart_restores_h_z_and_evidence');
  await click('stop');await click('grounded-decide');if((await last()).response_type!=='stopped')throw Error('Stop bypass');checks.push('stop_blocks_neural_planning');
  await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Mobile overflow');
  await page.screenshot({path:path.join(root,'runs/seed-grounded-mobile.png'),fullPage:true});checks.push('mobile_gui');
  if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));
  console.log(JSON.stringify({kind:'trained_grounded_real_chrome_qa',browser:browser.version(),checks,authored_requests:authoredRequests,page_errors:errors,external_requests:external,checkpoint_sha256:model.sha256,scientific_environment_steps:0},null,2));
 }finally{await stop();await browser.close();await fs.rm(directory,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
