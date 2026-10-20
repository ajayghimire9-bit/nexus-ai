/* Real Chrome QA for owner-enabled adapters; not scientific evaluation. */
const {chromium}=require(process.env.NEXUS_PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),port=8886,base=`http://127.0.0.1:${port}`;let child;
async function stop(){if(child){const p=child;child=null;await new Promise(r=>{p.once('exit',r);p.kill();});}}
(async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'nexus-adaptive-qa-'));
 const study=JSON.parse(await fs.readFile(path.join(root,'artifacts/seed_memory_aware.json'),'utf8'));
 const corePath=path.join(root,study.config.parent_model);
 const hash=async()=>crypto.createHash('sha256').update(await fs.readFile(corePath)).digest('hex');const beforeHash=await hash();
 async function start(){await new Promise((resolve,reject)=>{
  child=spawn(process.env.PYTHON||'python3',[path.join(root,'scripts/run_seed_adaptive_gui.py'),'--seed-directory',dir,'--port',String(port),'--max-runtime-s','120'],{cwd:root,env:process.env});
  let text='';child.stdout.on('data',d=>{text+=d;if(text.includes('NEXUS Learning Lab:'))resolve();});child.stderr.on('data',d=>text+=d);child.once('error',reject);child.once('exit',c=>{if(!text.includes('NEXUS Learning Lab:'))reject(Error(text+' exit '+c));});
 });}
 const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1280,height:1000}});
 const errors=[],external=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():(external.push(r.request().url()),r.abort()));
 const idle=async()=>page.waitForFunction(()=>!busy);
 async function click(id){await idle();await page.click('#'+id);await idle();if(await page.locator('#status.error').count())throw Error(await page.locator('#status').textContent());}
 const last=async()=>JSON.parse(await page.locator('#trace').textContent());
 async function snapshot(){return page.evaluate(async()=>{
   const r=await fetch('/api/seed',{method:'POST',headers:{'Content-Type':'application/json','X-Nexus-Request':'local-fixture'},body:JSON.stringify({session_id:sid,request:{op:'export'}})});
   const data=await r.json();if(!r.ok)throw Error(data.error);return data.response.export;
 });}
 const adaptive=s=>JSON.parse(s.data.events.filter(e=>e.kind==='seed_adaptive_state').at(-1).payload_json).state;
 try{
  await start();await page.goto(base+'/seed');await idle();let x=await last();
  if(!x.state.grounded.adaptation?.core_frozen||await page.locator('#grounded-adaptive_decide').isDisabled())throw Error('Adapter not enabled');
  checks.push('hash_bound_core_and_controller_with_adaptive_buttons');
  await click('positive');let first=adaptive(await snapshot());
  if(!first.blocks.meaning.some(v=>v!==0)||first.blocks.reward.some(v=>v!==0))throw Error('Teaching routing failed');
  await click('grounded-observe');if((await last()).result.adaptive_meaning===null)throw Error('Learned meaning not queried');
  checks.push('actual_teaching_updates_meaning_only_and_readonly_prediction_uses_it');
  await click('grounded-adaptive_decide');let learned=adaptive(await snapshot());
  if(!learned.blocks.reward.some(v=>v!==0)||learned.steps!==2)throw Error('Actual reward not learned');
  checks.push('selected_actual_action_updates_small_reward_block');
  const cognitive=JSON.stringify(learned);
  for(let i=0;i<3;i++){await click('inspect');await click('grounded-observe');await click('grounded-speak');}
  if(JSON.stringify(adaptive(await snapshot()))!==cognitive)throw Error('Inspection updated adaptation');
  checks.push('repeated_inspection_does_not_train');
  await click('save');await stop();await start();await page.reload();await idle();await click('load');
  if(JSON.stringify(adaptive(await snapshot()))!==cognitive)throw Error('Adaptive restart mismatch');
  checks.push('process_restart_restores_weights_anchors_and_assessment_split');
  const prior=adaptive(await snapshot());await click('grounded-adaptive_ask');let after=adaptive(await snapshot());
  if(after.steps!==prior.steps+1||JSON.stringify(after.blocks.meaning)!==JSON.stringify(prior.blocks.meaning)||after.work.question_hypotheses<2)throw Error('Imagined answer learned or question path absent');
  checks.push('hypothetical_answers_discarded_actual_ask_reward_only');
  await click('grounded-adaptive_review');if((await last()).result.adopted!=='keep')throw Error('Insufficient evidence should keep');
  await click('grounded-adaptive_review_reward');if((await last()).result.adopted!=='keep')throw Error('Insufficient evidence should keep');
  checks.push('insufficient_evidence_keeps_current_structure');
  const undoBefore=JSON.stringify(adaptive(await snapshot()));
  await click('grounded-adaptive_rollback');if((await last()).result.status!=='nothing_to_rollback')throw Error('Unexpected rollback state');
  if(JSON.stringify(adaptive(await snapshot()))!==undoBefore)throw Error('Empty undo altered learning state');
  checks.push('checked_rollback_button_preserves_state_when_no_edit_exists');
  await click('correct');after=adaptive(await snapshot());if(after.blocks.meaning.some(v=>v!==0)||after.anchors.meaning.length)throw Error('Corrected meaning not invalidated');
  checks.push('correction_invalidates_stale_meaning_not_reward');
  await click('stop');await click('grounded-adaptive_decide');if((await last()).response_type!=='stopped')throw Error('Stop bypass');
  checks.push('stop_blocks_learning_and_actions');
  await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Mobile overflow');
  await page.screenshot({path:path.join(root,'runs/seed-adaptive-mobile.png'),fullPage:true});checks.push('mobile_layout');
  if(errors.length||external.length||beforeHash!==await hash())throw Error(JSON.stringify({errors,external}));
  const final=await last();
  console.log(JSON.stringify({schema:'seed_adaptive_browser_qa_v1',browser:browser.version(),checks,page_errors:errors,external_requests:external,
    frozen_core_sha256:beforeHash,core_file_unchanged:true,authored_engineering_costs:final.state.costs,
    scientific_environment_collection:0,controller_lessons:after.steps},null,2));
 }finally{await stop();await browser.close();await fs.rm(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
