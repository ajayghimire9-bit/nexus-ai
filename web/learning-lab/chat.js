'use strict';
const $=id=>document.getElementById(id),node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
let sid=null,chat=null,busy=false,dirty=false,currentTitle='New conversation',lastEvidence=null,failed=null,attachment=null;
let paintedSession=null,painted=[];
const INDEX='nexus-seed-chat-saves-v2',ACTIVE='nexus-seed-chat-active-v2';
function saved(){try{const x=JSON.parse(localStorage.getItem(INDEX)||'[]');return Array.isArray(x)?x.filter(v=>v&&/^[a-f0-9]{32}$/.test(v.session_id)&&/^[a-f0-9]{64}$/.test(v.hash)&&typeof v.title==='string').slice(0,32):[];}catch{return [];}}
function notice(message,error=false){$('notice').replaceChildren();$('notice').append(document.createTextNode(message));$('notice').classList.toggle('error',error);}
function controls(){
 $('message').disabled=busy;$('send').disabled=busy||!$('message').value.trim();
 $('stop').hidden=!busy||!sid;$('thinking').hidden=!busy;
 $('composer-form').setAttribute('aria-busy',String(busy));
 for(const id of ['new','save','rename','delete-chat'])$(id).disabled=busy;
}
async function api(request,session=sid){
 const r=await fetch('/api/seed',{method:'POST',headers:{'Content-Type':'application/json','X-Nexus-Request':'local-fixture'},body:JSON.stringify({session_id:session,request})});
 let d;try{d=await r.json();}catch{throw Error('The local server did not return a readable response. Use Recover before trying another action.');}
 if(!r.ok)throw Error(d.error||'The request could not be completed.');
 return d;
}
async function ensureSession(){if(!sid){const d=await api({op:'new'},null);sid=d.session_id;}return sid;}
function recordSave(receipt){
 const item={...receipt,title:currentTitle.slice(0,65),saved_at:new Date().toISOString()};
 const rows=saved().filter(v=>v.session_id!==receipt.session_id);rows.unshift(item);
 try{localStorage.setItem(INDEX,JSON.stringify(rows.slice(0,32)));localStorage.setItem(ACTIVE,receipt.session_id);}catch{notice('Saved on the server, but browser storage is unavailable.',true);}
 dirty=false;$('save-state').textContent='Saved locally';renderSaves();
}
function renderSaves(){
 const rows=saved();$('conversation-count').textContent=String(rows.length);
 $('conversations').replaceChildren();
 if(!rows.length)$('conversations').append(node('p','Saved conversations stay on this device.','side-empty'));
 for(const row of rows){
  const wrap=node('div',undefined,'conversation-row');
  const b=node('button',row.title,'conversation-link'+(row.session_id===sid?' current':''));
  b.onclick=()=>restore(row);
  const del=node('button','✕','row-action');del.setAttribute('aria-label','Delete conversation');
  del.onclick=e=>{e.stopPropagation();removeConversation(row);};
  wrap.append(b,del);$('conversations').append(wrap);
 }
}
function markdown(text){
 const root=document.createElement('div');root.className='message-body';
 const chunks=(text||'').split(/```/);
 chunks.forEach((chunk,i)=>{
  if(i%2){
   const nl=chunk.indexOf('\n');const lang=nl===-1?'':chunk.slice(0,nl);const code=nl===-1?chunk:chunk.slice(nl+1);
   const wrap=node('div',undefined,'code-wrap');const pre=document.createElement('pre');const el=document.createElement('code');
   el.textContent=code;pre.append(el);
   const copy=node('button','Copy','copy-code');copy.type='button';
   copy.onclick=async()=>{try{await navigator.clipboard.writeText(code);copy.textContent='Copied';setTimeout(()=>{copy.textContent='Copy';},1200);}catch{copy.textContent='Unavailable';}};
   wrap.append(pre,copy);root.append(wrap);
  }else{
   const p=document.createElement('p');
   const parts=chunk.split(/(\[[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\])/);
   for(const part of parts){
    const cite=part.match(/^\[([A-Za-z0-9][A-Za-z0-9_.:-]{0,63})\]$/);
    if(cite){const btn=node('button',part,'citation');btn.type='button';btn.onclick=()=>previewDoc(cite[1]);p.append(btn);}
    else p.append(document.createTextNode(part));
   }
   root.append(p);
  }
 });
 return root;
}
function isInternalCard(card){
 const t=card.title||'';
 const d=card.data||{};
 return /master|cognitive trace|15-component|compute_tier|benchmark|suite/i.test(t)
  || d.compute_tier || d.exchange_kind || d.meta_operation;
}
function statusChip(turn){
 const cards=turn.cards||[];
 const coding=cards.find(c=>c.data&& (c.data.public_tests_passed===true || c.data.public_tests_passed===false));
 const executed=cards.some(c=>c.data&&c.data.executed) || /verified mathematical result|public tests passed/i.test(turn.assistant||'');
 const model=cards.some(c=>c.data&&c.data.source==='model_generated');
 let label=null;
 if(turn.status==='error')label='Failed';
 else if(turn.status==='clarification')label='Needs clarification';
 else if(coding&&coding.data.public_tests_passed)label='Tests passed';
 else if(executed)label='Executed';
 else if(turn.context?.workspace?.last_user_status)label=turn.context.workspace.last_user_status;
 else if(model)label='Draft';
 else label='Draft';
 const chip=node('span',label,'status-chip'+(label==='Failed'?' failed':label==='Tests passed'?' passed':label==='Needs clarification'?' clarify':''));
 return chip;
}
function renderCard(card){
 const d=card.data||{};
 if(isInternalCard(card))return node('div');
 const box=node('div',undefined,'inline-card'+(d.source==='execution_backed'||d.executed?' backed':d.source==='model_generated'?' model-text':''));
 box.append(node('h3',card.title));
 if(d.source==='vault_retrieval'||d.source==='structured_render'||card.title==='Source preview'){
  const facts=d.facts||[];
  for(const fact of facts){
   const b=node('button',(fact.title||fact.doc_id)+' ['+fact.doc_id+']','citation');
   b.type='button';b.onclick=()=>previewDoc(fact.doc_id);box.append(b);
   box.append(node('p',fact.content||''));
  }
  box.append(node('small',d.model_generated?'Model-generated explanation · not an executed action':'Stored source · current SQLite row'));
  return box;
 }
 if(d.source==='python_sandbox'||card.title==='Public-test outcome'){
  box.append(node('p',(d.public_tests_passed?'Public tests passed':'Public tests did not all pass')+(d.complete_correctness===false?' · not complete correctness':'')));
  if(d.result)box.append(node('pre',JSON.stringify(d.result,null,2)));
  return box;
 }
 if(d.code){const pre=document.createElement('pre');pre.textContent=d.code;box.append(pre);box.append(node('small','Not executed unless a later card says so'));return box;}
 if(typeof d==='string')box.append(node('p',d));
 else box.append(node('pre',JSON.stringify(d,null,2)));
 return box;
}
function renderKnowledge(knowledge){
 const docs=knowledge?.documents||[],caps=knowledge?.capsules||[],procs=knowledge?.procedures||[];
 $('knowledge-count').textContent=String(docs.length+caps.length+procs.length);
 const fill=(id,rows,label,kind)=>{
  const host=$(id);host.replaceChildren();
  if(!rows.length)return;
  host.append(node('p',label,'side-heading'));
  for(const row of rows){
   const item=node('div',undefined,'knowledge-item');
   const name=row.title||row.term||row.name||row.doc_id||row.id;
   const open=node('button',name);open.onclick=()=>{if(row.doc_id)previewDoc(row.doc_id);};
   const del=node('button','Delete','row-action');
   del.onclick=()=>deleteKnowledge(kind,row.doc_id||row.term||row.id);
   item.append(open,del);host.append(item);
  }
 };
 fill('knowledge-docs',docs,'Documents','document');
 fill('knowledge-capsules',caps,'Bindings','capsule');
 fill('knowledge-procedures',procs,'Procedures','procedure');
}
function render(){
 if(!chat)return;
 $('welcome').hidden=chat.messages.length>0;
 $('workspace-title').textContent=currentTitle;
 if(paintedSession!==sid||painted.some((id,i)=>chat.messages[i]?.id!==id)){$('messages').replaceChildren();painted=[];paintedSession=sid;}
 for(const turn of chat.messages){
  if(painted.includes(turn.id))continue;
  const u=node('article',undefined,'message user');u.append(node('p',turn.user,'bubble message-body'));
  const a=node('article',undefined,'message assistant '+turn.status),bubble=node('div',undefined,'bubble');
  bubble.append(node('p','NEXUS Seed','speaker'),statusChip(turn),markdown(turn.assistant));
  for(const card of turn.cards){const el=renderCard(card);if(el.childNodes.length)bubble.append(el);}
  const actions=node('div',undefined,'turn-actions'),details=node('button','Inspector');
  details.onclick=()=>evidence({evidence_refs:turn.evidence_refs,context:turn.context,inspector:chat.inspector,resources:lastEvidence?.resources});
  actions.append(details);bubble.append(actions);
  a.append(node('span','✦','avatar'),bubble);
  $('messages').append(u,a);painted.push(turn.id);
 }
 renderSaves();renderKnowledge(chat.knowledge);
 $('save-state').textContent=dirty?'Unsaved changes':chat.messages.length?'Saved locally':'New conversation';
 const help=[];
 if(chat.context?.workspace?.selected_file)help.push('File: '+chat.context.workspace.selected_file.split('/').pop());
 if(chat.context?.workspace?.selected_document_id)help.push('Document ['+chat.context.workspace.selected_document_id+']');
 help.push(chat.local_runtime?.available?'Local model attached.':'Local model not attached.');
 help.push('Enter to send · Shift + Enter for a new line');
 $('composer-help').textContent=help.join(' ');
 if(chat.recovery?.missing?.length)notice('A selected resource is missing: '+chat.recovery.missing.map(m=>m.recovery).join(' '),true);
 if(chat.stopped)notice('Paused. Say “resume” before continuing.');
}
function scrollEnd(){requestAnimationFrame(()=>{$('chat-scroll').scrollTo({top:$('chat-scroll').scrollHeight,behavior:'instant'});});}
function resize(){const el=$('message');el.style.height='auto';el.style.height=Math.min(180,el.scrollHeight)+'px';}
function evidence(data){lastEvidence=data;$('details-content').replaceChildren(node('pre',JSON.stringify(data,null,2)));$('details-dialog').showModal();}
async function previewDoc(docId){
 try{const d=await api({op:'knowledge_preview',doc_id:docId});const doc=d.response.document;
  $('preview-content').replaceChildren(node('h3',doc.title+' ['+doc.doc_id+']'),node('p','Hash '+doc.source_hash),node('pre',doc.content));
  $('preview-dialog').showModal();
 }catch(e){notice(e.message,true);}
}
async function create(){
 if(busy)return;busy=true;controls();
 try{if(sid&&dirty)await saveCurrent();const d=await api({op:'new'},null);sid=d.session_id;
  chat=(await api({op:'chat_view'})).response.chat;dirty=false;currentTitle='New conversation';failed=null;attachment=null;paintAttach();notice('');
  render();$('message').value='';resize();$('chat-scroll').scrollTop=0;closeSidebar();
 }catch(e){notice(e.message,true);}finally{busy=false;controls();$('message').focus();}
}
async function saveCurrent(){if(!sid)return;notice('');const d=await api({op:'save'});recordSave(d.response.saved);if(!$('notice').classList.contains('error'))notice('Conversation saved locally.');}
async function restore(row){
 if(busy)return;busy=true;controls();
 try{if(sid&&dirty)await saveCurrent();const d=await api({op:'load',saved_id:row.session_id,expected_hash:row.hash},null);
  sid=d.session_id;currentTitle=row.title;chat=(await api({op:'chat_view'})).response.chat;dirty=false;failed=null;
  try{localStorage.setItem(ACTIVE,sid);}catch{}render();notice('Conversation restored. No requests were sent again.');closeSidebar();scrollEnd();
 }catch(e){notice('Could not restore: '+e.message,true);}finally{busy=false;controls();}
}
async function removeConversation(row){
 try{if(row.session_id===sid)await api({op:'conversation_delete'});}catch{}
 const rows=saved().filter(v=>v.session_id!==row.session_id);
 try{localStorage.setItem(INDEX,JSON.stringify(rows));if(localStorage.getItem(ACTIVE)===row.session_id)localStorage.removeItem(ACTIVE);}catch{}
 if(row.session_id===sid)await create();else renderSaves();
}
function paintAttach(){
 const chip=$('attach-chip');
 if(!attachment){chip.hidden=true;chip.replaceChildren();return;}
 chip.hidden=false;chip.replaceChildren();
 chip.append(document.createTextNode('Attached '+attachment.name+' as content, not as an instruction. '));
 const clear=node('button','Remove');clear.onclick=()=>{attachment=null;paintAttach();};chip.append(clear);
}
async function send(text,requestId){
 if(busy||!text.trim())return;busy=true;controls();notice('');
 failed={id:requestId||crypto.randomUUID().replaceAll('-',''),text};
 try{
  await ensureSession();
  const payload={op:'chat_send',text,id:failed.id};
  if(attachment)payload.attachment=attachment;
  const d=await api(payload);sid=d.session_id;chat=d.response.chat;dirty=true;
  if(chat.messages.length===1)currentTitle=text.slice(0,65);
  $('message').value='';resize();attachment=null;paintAttach();render();
  if(d.response.saved)recordSave(d.response.saved);
  lastEvidence={inspector:chat.inspector,resources:d.response.resources,context:chat.context};
  failed=null;scrollEnd();
 }catch(e){
  notice('Couldn’t finish: '+e.message,true);
  const b=node('button','Recover response','quiet-button');b.onclick=()=>send(failed.text,failed.id);
  $('notice').append(document.createTextNode(' '),b);
 }finally{busy=false;controls();$('message').focus();}
}
async function deleteKnowledge(kind,id){
 if(!id)return;
 try{await ensureSession();const d=await api({op:'knowledge_delete',kind,id});chat={...chat,knowledge:d.response.knowledge};renderKnowledge(chat.knowledge);}
 catch(e){notice(e.message,true);}
}
function closeSidebar(){document.body.classList.remove('sidebar-open');$('toggle-sidebar').setAttribute('aria-expanded',String(matchMedia('(min-width:861px)').matches&&!document.body.classList.contains('sidebar-collapsed')));}
$('composer-form').onsubmit=e=>{e.preventDefault();send($('message').value);};
$('message').oninput=()=>{resize();controls();};
$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send(e.currentTarget.value);}};
$('new').onclick=create;
$('save').onclick=async()=>{if(busy)return;busy=true;controls();try{await saveCurrent();}catch(e){notice('Could not save: '+e.message,true);}finally{busy=false;controls();}};
$('rename').onclick=async()=>{
 const title=prompt('Conversation name',currentTitle);if(!title||!title.trim())return;
 currentTitle=title.trim().slice(0,80);$('workspace-title').textContent=currentTitle;
 try{await ensureSession();await api({op:'conversation_rename',title:currentTitle});if(sid){const rows=saved().map(r=>r.session_id===sid?{...r,title:currentTitle}:r);localStorage.setItem(INDEX,JSON.stringify(rows));}renderSaves();}
 catch(e){notice(e.message,true);}
};
$('delete-chat').onclick=async()=>{if(!sid||!confirm('Delete this conversation from the local workspace?'))return;await removeConversation({session_id:sid,hash:'0'.repeat(64),title:currentTitle});};
$('evidence').onclick=()=>evidence(lastEvidence||chat?.inspector||{learning_to_learn_established:false});
$('close-details').onclick=()=>$('details-dialog').close();
$('close-preview').onclick=()=>$('preview-dialog').close();
$('toggle-sidebar').onclick=()=>{
 if(matchMedia('(max-width:860px)').matches){const opened=document.body.classList.toggle('sidebar-open');$('toggle-sidebar').setAttribute('aria-expanded',String(opened));}
 else{const closed=document.body.classList.toggle('sidebar-collapsed');$('toggle-sidebar').setAttribute('aria-expanded',String(!closed));}
};
$('backdrop').hidden=false;$('backdrop').onclick=()=>{closeSidebar();$('toggle-sidebar').focus();};
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'&&document.body.classList.contains('sidebar-open')){closeSidebar();$('toggle-sidebar').focus();}
});
$('stop').onclick=async()=>{if(!sid)return;try{await api({op:'stop'});notice('Stop requested. Work already finished is kept. Generation or execution that had not completed was cancelled.');}catch(e){notice(e.message,true);}};
$('attach-input').onchange=async e=>{
 const file=e.target.files&&e.target.files[0];e.target.value='';
 if(!file)return;
 if(file.size>48000){notice('That file is larger than the local attachment limit (48 KB).',true);return;}
 const content=await file.text();
 const kind=/\.(py|ts|js)$/i.test(file.name)?'code':'document';
 attachment={kind,name:file.name,content};
 paintAttach();
};
for(const b of document.querySelectorAll('[data-prompt]'))b.onclick=()=>send(b.dataset.prompt);
document.addEventListener('visibilitychange',async()=>{
 if(document.visibilityState==='visible'&&sid&&!busy){
  try{const currentSid=sid;const d=await api({op:'chat_view'});if(!busy&&sid===currentSid){chat=d.response.chat;render();controls();}}
  catch(e){notice(e.message,true);}
 }
});
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
(async()=>{
 controls();renderSaves();closeSidebar();
 let active;try{active=localStorage.getItem(ACTIVE);}catch{}
 const previous=saved().find(r=>r.session_id===active);
 if(previous)await restore(previous);else await create();
})();
