/* Read-only saved audit evidence, never a run request. */
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8785/experimental#seed-query-context-1');
const card=page.locator('#seed-query-context-1');await card.locator('table').waitFor();
const content=await card.textContent();for(const phrase of ['Query-context sufficiency','No new labels','not observed target','No confidence interval','No live promotion'])assert.ok(content.includes(phrase));
assert.equal(await card.locator('table tr').count(),6);
const res=await page.request.get('http://127.0.0.1:8785/api/experimental');assert.equal(res.status(),200);
const r=(await res.json()).experiments.find(x=>x.id==='seed-query-context-1');
for(const key of ['real_steps','updates','network_forwards','imagined_transitions'])assert.equal(r.resources[key],0);
assert.equal(r.query_context.contexts,512);
await card.screenshot({path:'runs/seed-query-context-results.png'});
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:14,read_only:true}));
})().catch(e=>{console.error(e);process.exit(1)});
