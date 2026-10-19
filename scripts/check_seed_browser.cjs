/* Real Chrome UI + Python server restart. Authored development QA only. */
const {chromium}=require(process.env.NEXUS_PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises');const os=require('node:os');const path=require('node:path');
const root=path.resolve(__dirname,'..');const port=Number(process.env.NEXUS_SEED_QA_PORT||8879);const base=`http://127.0.0.1:${port}`;
let child=null;
function start(directory){return new Promise((resolve,reject)=>{child=spawn(process.env.PYTHON||'python3',['-I','-S',path.join(root,'scripts/run_learning_lab.py'),'--allow-seed','--seed-directory',directory,'--port',String(port),'--max-runtime-s','120'],{cwd:root});let text='';child.stdout.on('data',v=>{text+=v;if(text.includes('NEXUS Learning Lab:'))resolve();});child.once('error',reject);child.once('exit',c=>{if(!text.includes('NEXUS Learning Lab:'))reject(Error('Server failed '+c));});});}
async function stop(){if(child){const c=child;child=null;await new Promise(resolve=>{c.once('exit',resolve);c.kill();});}}
(async()=>{const directory=await fs.mkdtemp(path.join(os.tmpdir(),'nexus-seed-qa-'));const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1280,height:1050}});const errors=[],external=[],checks=[];let teacherAnswers=0,actions=0;page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{if(new URL(route.request().url()).origin!==base){external.push(route.request().url());return route.abort();}return route.continue();});
 async function idle(){await page.waitForFunction(()=>!busy);}
 async function click(id){await idle();await page.click('#'+id);await idle();}
 async function last(){return JSON.parse(await page.locator('#trace').textContent());}
 try{await start(directory);await page.goto(base+'/seed');await idle();checks.push('real_gui_connected_to_engine');
 const word='v'+require('node:crypto').randomBytes(4).toString('hex');await page.fill('#word',word);await page.fill('#message',`move ${word} left`);await page.press('#message','Enter');await idle();if((await last()).response_type!=='unknown_concept')throw Error('Unknown meaning expected');checks.push('unknown_invented_word_requires_teaching');
 await page.selectOption('#example','o4');await click('positive');teacherAnswers++;
 for(let i=0;i<8;i++){const x=await last();const q=x.result.question;if(!q||q.status!=='question')break;const yes=q.object.color==='blue'&&q.object.size==='small';await click(yes?'answerYes':'answerNo');teacherAnswers++;}
 checks.push('real_example_labels_and_disagreement_questions');
 await click('scene1');await page.fill('#message',`move ${word} left then move o1 down`);await page.press('#message','Enter');await idle();let x=await last();if(x.response_type!=='acted'||x.result.trace.length!==2)throw Error('Transfer command failed '+JSON.stringify(x));actions+=2;checks.push('new_scene_and_composed_command_executed');
 await click('save');const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('nexus-seed-saved')));
 const before=await fs.readFile(path.join(directory,saved.session_id,'revision-0000.json'),'utf8');
 await stop();await start(directory);await page.reload();await idle();await click('load');x=await last();if(!x.state.concepts.find(c=>c.word===word))throw Error('Restart lost concept');
 await page.fill('#message',`move ${word} left`);await page.press('#message','Enter');await idle();if((await last()).response_type!=='acted')throw Error('Restart behavior failed');actions++;checks.push('save_process_restart_resume_and_actual_behavior');
 await click('correct');x=await last();teacherAnswers++;if(!['learned','contradiction'].includes(x.response_type))throw Error('Correction failed');const newEvidence=x.state.evidence.at(-1);if(!newEvidence.supersedes)throw Error('Correction lacks dependency');await click('save');if(await fs.readFile(path.join(directory,saved.session_id,'revision-0000.json'),'utf8')!==before)throw Error('Historical snapshot rewritten');checks.push('correction_appends_history_and_preserves_first_snapshot');
 await click('stop');await page.fill('#message','move o1 right');await page.press('#message','Enter');await idle();if((await last()).response_type!=='stopped')throw Error('Stop failed');await click('resume');
 await page.fill('#message','execute shell commands');await page.press('#message','Enter');await idle();if((await last()).response_type!=='unsupported')throw Error('Unsupported language accepted');checks.push('stop_resume_and_unsupported_request');
 await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2))throw Error('Mobile horizontal overflow');await page.screenshot({path:path.join(root,'runs/seed-mobile-qa.png'),fullPage:true});checks.push('mobile_layout_no_horizontal_overflow');
 await page.goto(base);await page.locator('#recordStatus').filter({hasText:'execution'}).waitFor();checks.push('historical_replay_still_read_only');
 if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));
 console.log(JSON.stringify({kind:'real_headless_chrome_seed_qa',browser:browser.version(),checks,page_errors:errors,external_requests:external,teacher_answers:teacherAnswers,sandbox_actions:actions,scientific_interactions:0,neural_work:0,session_directory:'temporary_not_tracked'},null,2));
 }finally{await stop();await browser.close();await fs.rm(directory,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
