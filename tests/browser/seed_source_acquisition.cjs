/* Saved evidence only; does not start a scientific run or live learning. */
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8785/experimental#seed-source-acquisition-1');
const card=page.locator('#seed-source-acquisition-1');await card.locator('table').waitFor();
assert.equal(await card.locator('table tr').count(),9);const content=await card.textContent();
for(const phrase of ['Source-trained question acquisition','Strong model-based advantage','source_prior','uniform_expectation','Budget 8 is secondary','n=8 / df=7','No live promotion'])assert.ok(content.includes(phrase));
const res=await page.request.get('http://127.0.0.1:8785/api/experimental');assert.equal(res.status(),200);
const r=(await res.json()).experiments.find(x=>x.id==='seed-source-acquisition-1');
assert.equal(r.resources.real_steps,3072);assert.equal(r.resources.fitted_ridge_models,8);assert.equal(r.resources.network_forwards,0);
assert.equal(r.source_acquisition.parameter_count_per_selector,10);
await card.screenshot({path:'runs/seed-source-acquisition-results.png'});
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:15,read_only:true}));
})().catch(e=>{console.error(e);process.exit(1)});
