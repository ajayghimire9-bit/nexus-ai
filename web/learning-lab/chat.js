'use strict';
const $=id=>document.getElementById(id),node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
let sid=null,chat=null,busy=false,dirty=false,currentTitle='New conversation',lastEvidence=null,failed=null;
let paintedSession=null,painted=[];
const INDEX='nexus-seed-chat-saves-v1',ACTIVE='nexus-seed-chat-active-v1';

function switchView(viewName){
 for(const v of ['chat','master','labs','workbench']){
  const el=$('view-'+v);
  if(el)el.hidden=(v!==viewName);
 }
 for(const btn of document.querySelectorAll('[data-view]')){
  const active=btn.dataset.view===viewName;
  btn.classList.toggle('active',active);
  if(btn.getAttribute('role')==='tab')btn.setAttribute('aria-selected',String(active));
 }
}
for(const btn of document.querySelectorAll('[data-view]')){
 btn.onclick=()=>{switchView(btn.dataset.view);closeSidebar();};
}

function saved(){try{const x=JSON.parse(localStorage.getItem(INDEX)||'[]');return Array.isArray(x)?x.filter(v=>v&&/^[a-f0-9]{32}$/.test(v.session_id)&&/^[a-f0-9]{64}$/.test(v.hash)&&typeof v.title==='string').slice(0,32):[];}catch{return [];}}
function notice(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}
function controls(){for(const el of document.querySelectorAll('.copy-example,.turn-actions button,.memory-item,.suggestions button,.quick-strip button,#show-world')){el.disabled=busy;if(el.dataset.correctionRef)el.hidden=el.dataset.correctionRef!==chat?.context.last_teaching;}for(const id of ['new','save','restore'])$(id).disabled=busy; $('message').disabled=busy;$('send').disabled=busy||!$('message').value.trim();$('stop').hidden=!busy||!sid;$('thinking').hidden=!busy;$('composer-form').setAttribute('aria-busy',String(busy));}
async function api(request,session=sid){const r=await fetch('/api/seed',{method:'POST',headers:{'Content-Type':'application/json','X-Nexus-Request':'local-fixture'},body:JSON.stringify({session_id:session,request})});let d;try{d=await r.json();}catch{throw Error('The local server did not return a readable response. Your request may have finished; use Recover before trying another action.');}if(!r.ok)throw Error(d.error||'The request could not be completed.');return d;}
async function ensureSession(){if(!sid){const d=await api({op:'new'},null);sid=d.session_id;}return sid;}
function recordSave(receipt){const item={...receipt,title:currentTitle.slice(0,65),saved_at:new Date().toISOString()},rows=saved().filter(v=>v.session_id!==receipt.session_id);rows.unshift(item);try{localStorage.setItem(INDEX,JSON.stringify(rows.slice(0,32)));localStorage.setItem(ACTIVE,receipt.session_id);}catch{notice('Saved on the server, but browser storage is unavailable. Keep the session receipt in Evidence.',true);}dirty=false;$('save-state').textContent='Saved locally';lastEvidence={saved:receipt};renderSaves();}
function renderSaves(){const rows=saved();$('conversation-count').textContent=String(rows.length);$('conversations').replaceChildren();if(!rows.length)$('conversations').append(node('p','Saved conversations stay on this device.','side-empty'));for(const row of rows){const b=node('button',row.title,'conversation-link'+(row.session_id===sid?' current':''));b.title='Restore '+row.title;b.onclick=()=>{switchView('chat');restore(row);};$('conversations').append(b);}}
function worldGrid(target,world){if(!target)return;target.replaceChildren();for(let y=0;y<6;y++)for(let x=0;x<6;x++){const cell=node('div',undefined,'world-cell');const here=world.filter(o=>o.x===x&&o.y===y);cell.title=`(${x}, ${y})`+(here.length?': '+here.map(o=>o.id).join(', '):'');for(const o of here){const dot=node('span',undefined,'world-token '+o.color);dot.setAttribute('aria-label',`${o.id}, ${o.color} ${o.shape}, ${x}, ${y}`);cell.append(dot);}target.append(cell);}}
function renderState(state){if(!state)return;for(const a of document.querySelectorAll('a[href^="/labs#"]')){const lab=a.getAttribute('href').split('#')[1].split('@')[0];a.href='/labs#'+lab+'@'+sid;}const entries=state.shared_library.entries;$('memory-count').textContent=String(entries.length);$('memory').replaceChildren();if(!entries.length)$('memory').append(node('p','A new word. A useful little skill. What will you teach me first?','side-empty'));for(const e of entries){const b=node('button',undefined,'memory-item'),icon=node('span',e.schema==='predicate'?'Aa':'◇','memory-icon'),label=node('span',e.name);label.append(node('small',e.active_revision?'Verified on your check':e.candidate_count===1?'Needs a separate check':'Still learning'));b.append(icon,label,node('span',e.active_revision?'✓':'○','tick'));b.onclick=()=>{switchView('chat');send(`What does ${e.name} mean?`);};b.disabled=busy;$('memory').append(b);}worldGrid($('world-grid'),state.world);worldGrid($('large-world-grid'),state.world);const wText=state.world.map(o=>`${o.id}: ${o.color} ${o.shape} (${o.x}, ${o.y})`).join(' · ');$('world-objects').textContent=wText;if($('large-world-objects'))$('large-world-objects').textContent=wText;}
function evidence(data){lastEvidence=data;$('details-content').replaceChildren(node('pre',JSON.stringify(data,null,2)));$('details-dialog').showModal();}
function describe(program){if(!program)return 'Not verified yet';if(program.schema==='predicate')return program.literals.map(([,v,neg])=>(neg?'not ':'')+v).join(' and ');if(program.ops)return program.ops.length?program.ops.join(' → '):'Keep the input unchanged';return program.name?.replaceAll('_',' ')||'Supported program';}
function exampleRow(input,output){const row=node('div',undefined,'example-row');row.append(node('code',typeof input==='object'&&input?.color?`${input.size} ${input.color} ${input.shape}`:JSON.stringify(input)),node('span','→'),node('code',typeof output==='boolean'?(output?'Yes':'No'):JSON.stringify(output)));return row;}
function renderCard(card){const box=node('div',undefined,'inline-card'+(card.data?.source==='execution_backed'?' backed':card.data?.source==='model_generated'?' model-text':card.data?.source==='transformation_preview'?' preview':''));box.append(node('h3',card.title));const d=card.data;
 if(d?.source==='execution_backed'){box.append(node('p',d.response||(d.row_count+' rows written')));box.append(node('small','Execution-backed · source file unchanged · '+((d.output_path||'').split('/').pop()||'output')));if(Array.isArray(d.preview)){for(const row of d.preview.slice(0,5))box.append(node('pre',JSON.stringify(row)));}return box;}
 if(d?.source==='model_generated'){box.append(node('small','Model-generated text · not an executed action'));return box;}
 if(d?.source==='transformation_preview'){box.append(node('p',(d.operations||[]).join(' → ')));box.append(node('small','Preview only · '+d.input_file+' will not be overwritten'));return box;}
 if(d?.kind==='bounded_code'){box.append(node('pre',d.python),node('small','Bounded typed-program execution · supplied operators'));if(d.executed)box.append(exampleRow(d.input,d.output),node('small',d.instructions+' interpreter instructions'));return box;}
 if(Array.isArray(d)&&d.length&&typeof d[0]==='string'){for(const s of d){const b=node('button',s+' ↗','copy-example');b.onclick=()=>send(s);b.disabled=busy;box.append(b);}return box;}
 if(Array.isArray(d)&&d.length&&d[0]?.id){for(const o of d){const p=node('p',`${o.id} · ${o.size} ${o.color} ${o.shape} · (${o.x}, ${o.y})`);box.append(p);if(chat?.context.pending?.kind==='object'){const b=node('button','Choose '+o.id,'copy-example');b.onclick=()=>send(o.id);b.disabled=busy;box.append(b);}}}
 else if(d&&typeof d==='object'&&!Array.isArray(d)&&d.world){const grid=node('div',undefined,'world-grid');worldGrid(grid,d.world);box.append(grid);if(d.result?.reward!==undefined)box.append(node('p','Authored reward: '+Number(d.result.reward).toFixed(3)));}
 else if(d?.color&&d?.shape){const preview=node('div',undefined,'object-preview'),shape=node('span',undefined,'object-shape '+d.color+' '+d.shape);preview.append(shape,node('p',`${d.size} ${d.color} ${d.shape}`));box.append(preview);}
 else if(card.title==='Stored meaning'){box.append(node('p',describe(d.program)),node('small',d.program?'Verified on a separate authored check':`${d.candidates.length} interpretations still fit.`));}
 else if(d?.examples){for(const row of d.examples)box.append(exampleRow(row.input,row.output));if(d.candidate_count!==undefined)box.append(node('small',`${d.candidate_count} supported interpretation${d.candidate_count===1?'':'s'} fit.`));if(d.status)box.append(node('small',d.status==='accepted'?'Check passed.':'Check did not pass.'));}
 else if(card.title==='Executed verified skill'){box.append(exampleRow(d.input,d.output));}
 else if(d?.input_suggestion){box.append(node('p','Try a new input and supply its expected output.'),node('pre',JSON.stringify(d.input_suggestion)));}
 else if(Array.isArray(d)&&d.length&&d[0]?.schema){for(const entry of d)box.append(node('p',`${entry.name} · ${entry.active_revision?'verified':'still learning'}`));}
 else{box.append(node('pre',typeof d==='string'?d:JSON.stringify(d,null,2)));}
 if(typeof d==='string'&&(d.includes('->')||d.startsWith('['))){const b=node('button','Use this format ↗','copy-example');b.onclick=()=>{if(busy)return;$('message').value=d;resize();controls();$('message').focus();};box.append(b);}return box;}
function render(){if(!chat)return;$('welcome').hidden=chat.messages.length>0;if($('composer-help')&&chat.context?.workspace){const file=chat.context.workspace.selected_file;const model=chat.local_runtime?.available?'Local model attached.':'Local model not attached; file tools still work.';$('composer-help').textContent=(file?'Selected file: '+file.split('/').pop()+'. ':'')+model+' Execution-backed results are labeled. Enter to send · Shift + Enter for a new line';}if(paintedSession!==sid||painted.some((id,i)=>chat.messages[i]?.id!==id)){$('messages').replaceChildren();painted=[];paintedSession=sid;}for(const turn of chat.messages){if(painted.includes(turn.id))continue;const u=node('article',undefined,'message user');u.append(node('p',turn.user,'bubble message-body'));const a=node('article',undefined,'message assistant '+turn.status),bubble=node('div',undefined,'bubble');bubble.append(node('p','NEXUS SEED','speaker'),node('p',turn.assistant,'message-body'));for(const card of turn.cards)bubble.append(renderCard(card));const actions=node('div',undefined,'turn-actions'),details=node('button','View evidence');details.onclick=()=>evidence({evidence_refs:turn.evidence_refs,dialogue_context:turn.context,state:chat.state.architecture,costs:chat.state.costs});actions.append(details);if(turn.context.pending&&turn.context.active_name){const b=node('button','Correct teaching');b.dataset.correctionRef=turn.context.last_teaching;b.onclick=()=>{if(b.dataset.correctionRef===chat.context.last_teaching)send('Correct my previous example.');};b.disabled=busy;actions.append(b);}bubble.append(actions);a.append(node('span','✦','avatar'),bubble);$('messages').append(u,a);painted.push(turn.id);}renderState(chat.state);renderSaves();$('save-state').textContent=dirty?'Unsaved changes':chat.messages.length?'Saved locally':'New conversation';if(chat.stopped)notice('Paused. Say “resume” before teaching or moving objects.');}
function scrollEnd(){requestAnimationFrame(()=>{$('chat-scroll').scrollTo({top:$('chat-scroll').scrollHeight,behavior:'instant'});});}
function resize(){const el=$('message');el.style.height='auto';el.style.height=Math.min(150,el.scrollHeight)+'px';}
async function create(){if(busy)return;busy=true;controls();try{if(sid&&dirty)await saveCurrent();const d=await api({op:'new'},null);sid=d.session_id;chat=(await api({op:'chat_view'})).response.chat;dirty=false;currentTitle='New conversation';failed=null;notice('');switchView('chat');render();$('message').value='';resize();$('chat-scroll').scrollTop=0;closeSidebar();}catch(e){notice(e.message,true);}finally{busy=false;controls();$('message').focus();}}
async function saveCurrent(){if(!sid)return;notice('');const d=await api({op:'save'});recordSave(d.response.saved);if(!$('notice').classList.contains('error'))notice('Conversation saved locally.');}
async function restore(row){if(busy)return;busy=true;controls();try{if(sid&&dirty)await saveCurrent();const d=await api({op:'load',saved_id:row.session_id,expected_hash:row.hash},null);sid=d.session_id;currentTitle=row.title;chat=(await api({op:'chat_view'})).response.chat;dirty=false;failed=null;try{localStorage.setItem(ACTIVE,sid);}catch{}render();notice('Conversation restored. No requests were sent again.');$('restore-dialog').close();closeSidebar();scrollEnd();}catch(e){notice('Could not restore: '+e.message,true);}finally{busy=false;controls();}}
async function send(text,requestId){if(busy||!text.trim())return;switchView('chat');busy=true;controls();notice('');failed={id:requestId||crypto.randomUUID().replaceAll('-',''),text};try{await ensureSession();const id=failed.id;const d=await api({op:'chat_send',text,id});sid=d.session_id;chat=d.response.chat;dirty=true;if(chat.messages.length===1)currentTitle=text.slice(0,65);$('message').value='';resize();render();if(d.response.saved)recordSave(d.response.saved);if(d.response.notification&&!$('notice').classList.contains('error'))notice(d.response.notification);failed=null;lastEvidence={...lastEvidence,resources:d.response.resources,context:chat.context,architecture:chat.state.architecture};scrollEnd();}catch(e){notice('Couldn’t finish: '+e.message,true);const b=node('button','Recover response','quiet-button');b.onclick=()=>send(failed.text,failed.id);$('notice').append(document.createTextNode(' '),b);}finally{busy=false;controls();renderState(chat?.state);$('message').focus();}}
function closeSidebar(){document.body.classList.remove('sidebar-open');$('toggle-sidebar').setAttribute('aria-expanded',String(matchMedia('(min-width:861px)').matches&&!document.body.classList.contains('sidebar-collapsed')));}
$('composer-form').onsubmit=e=>{e.preventDefault();send($('message').value);};$('message').oninput=()=>{resize();controls();};$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send(e.currentTarget.value);}};
$('new').onclick=create;$('save').onclick=async()=>{if(busy)return;busy=true;controls();try{await saveCurrent();}catch(e){notice('Could not save: '+e.message,true);}finally{busy=false;controls();}};
$('restore').onclick=()=>{$('restore-list').replaceChildren();const rows=saved();if(!rows.length)$('restore-list').append(node('p','No saved conversations on this device yet. Choose Save to keep this one.'));for(const row of rows){const b=node('button',row.title+' · '+new Date(row.saved_at).toLocaleDateString(),'conversation-link');b.onclick=()=>restore(row);$('restore-list').append(b);}$('restore-dialog').showModal();};
$('structure-view').onclick=async()=>{try{if(!sid)throw Error('Start a conversation first.');const d=await api({op:'structure_inspect'});evidence(d.response);}catch(e){notice(e.message,true);}};
$('evidence').onclick=()=>evidence(lastEvidence||{scope:'Local authored teaching and finite checked programs',scientific:false,learning_to_learn_established:false});$('close-details').onclick=()=>$('details-dialog').close();$('close-restore').onclick=()=>$('restore-dialog').close();
for(const d of [$('details-dialog'),$('restore-dialog')])d.addEventListener('click',e=>{if(e.target===d&&e.offsetX>=d.clientWidth)d.close();});
$('toggle-sidebar').onclick=()=>{if(matchMedia('(max-width:860px)').matches){const opened=document.body.classList.toggle('sidebar-open');$('toggle-sidebar').setAttribute('aria-expanded',String(opened));if(opened)$('new').focus();}else{const closed=document.body.classList.toggle('sidebar-collapsed');$('toggle-sidebar').setAttribute('aria-expanded',String(!closed));}};
$('backdrop').hidden=false;$('backdrop').onclick=()=>{closeSidebar();$('toggle-sidebar').focus();};document.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.body.classList.contains('sidebar-open')){closeSidebar();$('toggle-sidebar').focus();}if(e.key==='Tab'&&document.body.classList.contains('sidebar-open')){const els=[...$('sidebar').querySelectorAll('button:not(:disabled),a,summary')].filter(el=>el.getClientRects().length),first=els[0],last=els.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
$('stop').onclick=async()=>{if(!sid)return;try{await api({op:'stop'});notice('Stop requested. Completed actions are not undone. Say “resume” to continue.');}catch(e){notice(e.message,true);}};
$('show-world').onclick=()=>{closeSidebar();send('Show the world.');};for(const b of document.querySelectorAll('[data-prompt]'))b.onclick=()=>send(b.dataset.prompt);
document.addEventListener('visibilitychange',async()=>{if(document.visibilityState==='visible'&&sid&&!busy){try{const currentSid=sid;const d=await api({op:'chat_view'});if(!busy&&sid===currentSid&&d.response.chat.messages.length>=(chat?.messages.length||0)){chat=d.response.chat;render();controls();}}catch(e){notice(e.message,true);}}});
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});

// 15-Component Master Hub interactive handlers
if($('run-general-suite'))$('run-general-suite').onclick=async()=>{
 try{
  await ensureSession();
  const d=await api({op:'master_general_suite',args:{}});
  const res=d.response.result,ltl=res.learning_to_learn_benchmark;
  const banner=$('suite-banner');
  banner.hidden=false;
  banner.textContent=`✓ Bounded multi-reasoner integration suite (${res.domains_verified}/6 domains) · Bounded exact-motif program-prior reuse demo (engineering demonstration of within-family search-prior reuse: ${ltl.search_evaluations_reduction_pct}% reduction, ${ltl.mean_cold_start_evaluations} → ${ltl.mean_meta_learned_evaluations} evaluations) · Gate: ${ltl.acceptance_gate.decision.toUpperCase()}`;
  $('memory-gate-output').textContent=JSON.stringify(res,null,2);
 }catch(e){$('suite-banner').hidden=false;$('suite-banner').textContent='Error: '+e.message;}
};
if($('refresh-master'))$('refresh-master').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_inspect',args:{}});$('memory-gate-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('memory-gate-output').textContent=e.message;}
};
if($('run-grounding'))$('run-grounding').onclick=async()=>{
 try{
  await ensureSession();
  const text=$('ground-input').value.trim();
  const g=await api({op:'master_ground',args:{modality:'language',text}});
  const b=await api({op:'master_belief_state',args:{text}});
  $('ground-output').textContent=JSON.stringify({grounded_observation:g.response.result,belief_state_summary:{current_goal:b.response.result.current_goal,active_concepts_count:b.response.result.active_concepts.length,available_skills_count:b.response.result.available_skills.length,resource_budget:b.response.result.resource_budget}},null,2);
 }catch(e){$('ground-output').textContent=e.message;}
};
for(const btn of document.querySelectorAll('.reason-btn')){
 btn.onclick=async()=>{
  try{
   await ensureSession();
   const k=btn.dataset.rkind;
   let req;
   if(k==='relational')req={task_type:'relational',payload:{relations:[{relation:'north',subject:'A',object:'B'},{relation:'north',subject:'B',object:'C'}],query_subject:'A',query_object:'C'}};
   else if(k==='csp')req={task_type:'constraint',payload:{variables:{TaskA:[1,2,3],TaskB:[1,2,3],TaskC:[1,2,3]},constraints:[{kind:'all_different',vars:['TaskA','TaskB','TaskC']},{kind:'less_than',a:'TaskA',b:'TaskB'},{kind:'less_than',a:'TaskB',b:'TaskC'}]}};
   else if(k==='math')req={task_type:'math',payload:{expression:'3*x + 7 = 22',variable:'x'}};
   else if(k==='causal')req={task_type:'causal',payload:{variable_x:'InterventionX',variable_y:'OutcomeY',interventional_data:[{do_X:1,Y:0.92},{do_X:1,Y:0.88},{do_X:0,Y:0.08}]}};
   else if(k==='analogical')req={task_type:'analogical',payload:{source_domain:{domain:'list_domain',operation:'reverse_order'},target_domain:{domain:'movement_domain',sequence:[{direction:'right',steps:2},{direction:'up',steps:1}],invert_directions:true}}};
   else req={task_type:'active_investigation',payload:{hypotheses:['h1','h2','h3','h4'],candidate_probes:[{id:'balanced_probe',cost:1.0,predictions:{h1:true,h2:true,h3:false,h4:false}},{id:'skewed_probe',cost:1.0,predictions:{h1:true,h2:false,h3:false,h4:false}}]}};
   const d=await api({op:'master_reason',args:req});
   $('reason-output').textContent=JSON.stringify(d.response.result,null,2);
  }catch(e){$('reason-output').textContent=e.message;}
 };
}
if($('run-world-low'))$('run-world-low').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_hybrid_world',args:{state:{objects:[{id:'o1',x:1,y:2}]},action:{kind:'grid_move',object:'o1',direction:'right',steps:2,neural_residual:[0.03,-0.01]}}});$('world-meta-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('world-meta-output').textContent=e.message;}
};
if($('run-world-high'))$('run-world-high').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_hybrid_world',args:{state:{objects:[{id:'o1',x:1,y:2}]},action:{kind:'grid_move',object:'o1',direction:'right',steps:2,neural_predicted_x:0.0,neural_predicted_y:5.0}}});$('world-meta-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('world-meta-output').textContent=e.message;}
};
if($('run-meta-score'))$('run-meta-score').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_meta_control',args:{text:'If A is north of B and B is north of C, where is A relative to C?'}});$('world-meta-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('world-meta-output').textContent=e.message;}
};
if($('run-code-synth'))$('run-code-synth').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_code',args:{sub_op:'synthesize',specification:'Write code to sort and remove duplicates',mode:'compose_programs',unit_tests:[{input:[3,1,3,2],output:[1,2,3]}]}});$('code-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('code-output').textContent=e.message;}
};
if($('run-code-debug'))$('run-code-debug').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_code',args:{sub_op:'debug',broken_code:'def transform(x)\n    x = sorted(x)',unit_tests:[{input:[3,1,2],output:[1,2,3]}]}});$('code-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('code-output').textContent=e.message;}
};
if($('run-learn-immediate'))$('run-learn-immediate').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_learn',args:{timescale:'immediate',name:'scarlet',definition:'bright red',verified:true}});$('memory-gate-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('memory-gate-output').textContent=e.message;}
};
if($('run-consolidate'))$('run-consolidate').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_learn',args:{timescale:'long_term',adapter_name:'grounding_adapter_v1',new_task_scores:[0.89,0.91,0.90,0.92],baseline_scores:[0.75,0.76,0.74,0.75],retention_scores:[0.99,1.0,0.99,1.0],transfer_scores:[0.82,0.83,0.81,0.82],compute_cost_ms:15.0}});$('memory-gate-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('memory-gate-output').textContent=e.message;}
};
if($('run-inspect-memory'))$('run-inspect-memory').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_inspect',args:{}});$('memory-gate-output').textContent=JSON.stringify(d.response.result.memory,null,2);}catch(e){$('memory-gate-output').textContent=e.message;}
};
if($('run-acquire'))$('run-acquire').onclick=async()=>{
 try{await ensureSession();await api({op:'master_acquire',args:{kind:'table',table_name:'astronomy',rows:[{subject:'Earth',predicate:'orbits',object:'Sun'},{subject:'Mars',predicate:'orbits',object:'Sun'}]}});const r=await api({op:'master_acquire',args:{kind:'sparse_retrieve',query:'What orbits Sun?'}});$('acquire-compute-output').textContent=JSON.stringify(r.response.result,null,2);}catch(e){$('acquire-compute-output').textContent=e.message;}
};
if($('run-compute-tier'))$('run-compute-tier').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'master_compute',args:{operation:'simulate',surprise:0.25,weights:[-0.45,-0.12,0.0,0.28,0.62],bits:8}});$('acquire-compute-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('acquire-compute-output').textContent=e.message;}
};

// View 3: Labs & 6x6 World handlers
for(const btn of document.querySelectorAll('.world-move-btn')){
 btn.onclick=async()=>{
  await send(btn.dataset.cmd);
  switchView('labs');
  if($('lab-state-output'))$('lab-state-output').textContent=JSON.stringify(chat?.messages.at(-1),null,2);
 };
}
for(const btn of document.querySelectorAll('.lab-jump-btn')){
 btn.onclick=()=>send(btn.dataset.prompt);
}

// View 4: Phase 1-7 Workbench & Scientific Ledger handlers
if($('load-workbench'))$('load-workbench').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'foundation_workbench',args:{}});$('workbench-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('workbench-output').textContent=e.message;}
};
if($('load-symbiotic'))$('load-symbiotic').onclick=async()=>{
 try{await ensureSession();const d=await api({op:'workbench_inspect',args:{}});$('workbench-output').textContent=JSON.stringify(d.response.result,null,2);}catch(e){$('workbench-output').textContent=e.message;}
};
if($('issue-curriculum'))$('issue-curriculum').onclick=()=>{send('Generate lessons');};
if($('load-ledger'))$('load-ledger').onclick=async()=>{
 try{const r=await fetch('/api/experimental',{cache:'no-store'});const d=await r.json();$('workbench-output').textContent=JSON.stringify({ledger:d.ledger,experiment_count:d.experiments?.length||0,latest_experiments:(d.experiments||[]).slice(-5)},null,2);}catch(e){$('workbench-output').textContent=e.message;}
};

(async()=>{controls();renderSaves();closeSidebar();const linked=new URLSearchParams(location.hash.slice(1)).get('session');if(linked&&/^[a-f0-9]{32}$/.test(linked)){try{const d=await api({op:'chat_view'},linked);sid=linked;chat=d.response.chat;currentTitle=chat.messages[0]?.user.slice(0,65)||'Shared foundation session';render();controls();return;}catch{notice('That active session is unavailable. Use its saved receipt to restore it.');}}let active;try{active=localStorage.getItem(ACTIVE);}catch{}const previous=saved().find(r=>r.session_id===active);if(previous)await restore(previous);else await create();})();

$('foundation-open').onclick=()=>{switchView('workbench');$('details-dialog').close();$('load-workbench')?.click();};

$('investigation-results').onclick=async()=>{try{const response=await fetch('/api/experimental',{cache:'no-store'});if(!response.ok)throw Error('Evidence unavailable');const data=await response.json();const row=data.experiments.filter(x=>x.investigation_transfer).at(-1);if(!row){$('details-content').replaceChildren(node('p','This comparison has not completed. No results are claimed.'));return;}const s=row.investigation_transfer;$('details-content').replaceChildren(node('h3','Investigation transfer: '+s.screen.toUpperCase()),node('p',s.independent_trees?s.independent_trees+' independently source-trained trees; exploratory development; no live promotion.':'Fresh authored source-development tasks; one frozen library. No live promotion.'));for(const [m,v]of Object.entries(s.means))$('details-content').append(node('p',m+': '+v.questions.toFixed(3)+' questions · '+(100*v.accuracy['2']).toFixed(1)+'% accuracy after two questions'));const link=node('a','All controls, intervals and resource use ↗');link.href='/experimental#'+row.id;$('details-content').append(link);}catch(e){$('details-content').replaceChildren(node('p',e.message));}};

$('speak').onclick=()=>{const text=chat?.messages.at(-1)?.assistant;if(!text){notice('Send a message first.');return;}if(!window.speechSynthesis){notice('Local read-aloud is unavailable in this browser.');return;}const voice=speechSynthesis.getVoices().find(v=>v.localService&&v.lang.startsWith('en'));if(!voice){notice('No installed local English voice is available. No remote speech service was used.');return;}speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.voice=voice;speechSynthesis.speak(utterance);};
