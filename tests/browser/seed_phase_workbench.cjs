/* Authored workflow fixtures only; no scientific runner or neural fitting. */
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1400,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8785/foundation');await page.waitForFunction(()=>document.querySelector('#phases').children.length===7);
await page.locator('#graph-submit').click();await page.waitForFunction(()=>document.querySelector('#graph-result').textContent.includes('object'));
await page.locator('#graph-operation').selectOption('install');await page.locator('#graph-submit').click();await page.waitForFunction(()=>document.querySelector('#graph-result').textContent.includes('mechanisms'));
await page.locator('#graph-operation').selectOption('plan');await page.locator('#graph-submit').click();await page.waitForFunction(()=>document.querySelector('#graph-result').textContent.includes('planned'));
await page.locator('#operation').selectOption('expression_propose');await page.locator('#advanced').click();await page.waitForFunction(()=>document.querySelector('#advancedResult').textContent.includes('stored_node_savings'));
await page.locator('#operation').selectOption('expression_review');await page.locator('#advanced').click();await page.waitForFunction(()=>document.querySelector('#advancedResult').textContent.includes('"accepted": true'));
const reviewed=JSON.parse(await page.locator('#advancedResult').textContent());
await page.locator('#alias-phrase').fill('count distinct items');await page.locator('#alias-skill').fill(reviewed.candidate.name);await page.locator('#teach-alias').click();await page.waitForFunction(()=>document.querySelector('#alias-result').textContent.includes('"expression": true'));
await page.locator('#program').fill(JSON.stringify({op:'call',name:reviewed.candidate.name,value:{op:'var',name:'x'}}));await page.locator('#inputs').fill('{"x":[3,1,3]}');await page.locator('#execute').click();await page.waitForFunction(()=>document.querySelector('#execution').textContent.includes('"value": 2'));
await page.locator('#generate-lessons').click();await page.waitForFunction(()=>document.querySelector('#lessons').children.length===4);
const lesson=page.locator('#lessons section').first();const data=JSON.parse(await lesson.locator('pre').first().textContent());let answer=data.inputs.x.slice();const ops=[];let t=data.program;while(t.op==='skill'){ops.unshift(...t.program.ops);t=t.value;}for(const op of ops){if(op==='unique')answer=[...new Set(answer)];else if(op==='sort')answer.sort((a,b)=>a-b);else if(op==='even')answer=answer.filter(v=>v%2===0);else if(op==='increment')answer=answer.map(v=>v+1);else if(op==='reverse')answer.reverse();}
await lesson.locator('textarea').fill(JSON.stringify(answer));await lesson.locator('button').click();await page.waitForFunction(()=>document.querySelector('#curriculum-progress').textContent.includes('"completed": 1'));
await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#advancedResult').textContent.includes('"hash"'));
const memory=JSON.parse(await page.locator('#memory').textContent());await page.locator('#load').click();await page.waitForTimeout(100);assert.deepEqual(JSON.parse(await page.locator('#memory').textContent()).active_expressions,memory.active_expressions);
await page.screenshot({path:'runs/seed-phase-workbench.png',fullPage:true});const shared=await page.evaluate(()=>sid);
await page.goto('http://127.0.0.1:8785/chat#session='+shared);await page.waitForFunction(()=>!document.querySelector('#message').disabled);assert.equal(await page.evaluate(()=>sid),shared);
async function send(text){const n=await page.locator('.message.user').count();await page.locator('#message').fill(text);await page.locator('#message').press('Enter');await page.waitForFunction(n=>document.querySelectorAll('.message.user').length===n+1&&!document.querySelector('#message').disabled,n);}
for(const t of ['Teach you a skill from examples.','reverse','[3,1,2,1] -> [1,2,1,3]','[4,0,4,2] -> [2,4,0,4]','Teach phrase "turn the numbers around" as reverse','Run phrase "turn the numbers around" on [1,2,3]'])await send(t);
assert.ok((await page.locator('#messages').textContent()).includes('3,\n    2,\n    1'));
await send('Run phrase "count distinct items" on [5,5,1]');assert.ok((await page.locator('.message.assistant').last().textContent()).includes('"value": 2'));
await page.evaluate(()=>{speechSynthesis.getVoices=()=>[{localService:false,lang:'en-US'}];speechSynthesis.speak=()=>{throw Error('Remote voice must not run')};});await page.locator('#speak').click();await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('No remote speech service'));
await page.screenshot({path:'runs/seed-phase-chat.png',fullPage:true});assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:20,scientific_execution:false}));
})().catch(e=>{console.error(e);process.exit(1)});
