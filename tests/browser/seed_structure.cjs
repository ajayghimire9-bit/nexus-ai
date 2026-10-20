/* Authored GUI contract fixtures. No simulator, neural training or new study. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.argv[2]||'http://127.0.0.1:8785/chat');
 await page.locator('#message').fill('Hello');await page.locator('#message').press('Enter');
 await page.waitForFunction(()=>document.querySelectorAll('.message.assistant').length>0);
 await page.locator('#evidence').click();await page.locator('#structure-view').click();
 await page.waitForFunction(()=>document.querySelector('#details-content').textContent.includes('library_sha256'));
 assert.match(await page.locator('#details-content').textContent(),/"experimental": true/);
 await page.locator('#close-details').click();
 const info=await page.evaluate(async()=>{
  const call=async request=>{const d=await api(request);if(!d.response)throw Error('Missing response');return d.response;};
  const baseline=await call({op:'export'});
  await call({op:'structure_reset',episode:'gui-source'});
  await call({op:'structure_observe',observation:{entities:[{id:'object',type:'item',attributes:{flag:false,ready:null}}],relations:[],events:[{code:1,entity:'object',time:0}],time:1,source:'sensor'}});
  const one=await call({op:'structure_inspect'}),two=await call({op:'structure_inspect'});
  if(JSON.stringify(one)!==JSON.stringify(two))throw Error('Inspection changed state');
  const saved=await call({op:'save'});
  const wire=await api({op:'load',saved_id:saved.saved.session_id,expected_hash:saved.saved.hash},null);
  const restored=await api({op:'structure_inspect'},wire.session_id);
  const after=await call({op:'export'});
  return {restored:restored.response,original:one,before:baseline.export.data.world,after:after.export.data.world};
 });
 assert.deepEqual(info.restored,info.original);assert.deepEqual(info.before,info.after);
 await page.goto('http://127.0.0.1:8785/experimental');
 await page.waitForFunction(()=>document.querySelector('#seed-executable-world-1')?.textContent.includes('source_feature_screen_passed'));
 assert.match(await page.locator('#seed-executable-world-1').textContent(),/22925/);
 await page.locator('#seed-executable-world-1').scrollIntoViewIfNeeded();
 await page.screenshot({path:'runs/seed-structure-gui.png'});
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({passed:true,checks:7,scientific_execution:false,new_simulator_steps:0,new_neural_calls:0}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
