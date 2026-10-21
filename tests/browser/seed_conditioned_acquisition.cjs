/* Saved evidence only. No scientific-run requests. */
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8785/experimental#seed-conditioned-acquisition-1');
const card=page.locator('#seed-conditioned-acquisition-1');await card.locator('table').waitFor();
assert.equal(await card.locator('table tr').count(),11);const text=await card.textContent();
for(const phrase of ['Fresh query-conditioned acquisition','Strong model-based advantage','blind_capacity','source_prior','uniform_expectation','n=8 / df=7','Learning-to-learn remains unestablished'])assert.ok(text.includes(phrase));
const res=await page.request.get('http://127.0.0.1:8785/api/experimental');assert.equal(res.status(),200);
const row=(await res.json()).experiments.find(x=>x.id==='seed-conditioned-acquisition-1');
assert.equal(row.resources.real_steps,2048);assert.equal(row.resources.updates,24);assert.equal(row.resources.network_forwards,0);
await card.screenshot({path:'runs/seed-conditioned-acquisition-results.png'});
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:14,read_only:true}));
})().catch(e=>{console.error(e);process.exit(1)});
