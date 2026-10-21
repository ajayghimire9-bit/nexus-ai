/* Read-only saved authored research, no collection endpoints. */
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8785/experimental#seed-inferred-investigation-1');
const card=page.locator('#seed-inferred-investigation-1');await card.locator('table').waitFor();
assert.equal(await card.locator('table tr').count(),6);const body=await card.textContent();
for(const phrase of ['Source-inferred investigation','Source model recovery: true','compiled_greedy','tree_greedy','Source model work','n=8 / df=7','not established learning-to-learn','No live promotion'])assert.ok(body.includes(phrase));
await card.screenshot({path:'runs/seed-inferred-investigation-results.png'});
const response=await page.request.get('http://127.0.0.1:8785/api/experimental');assert.equal(response.status(),200);
const state=await response.json(),r=state.experiments.find(x=>x.id==='seed-inferred-investigation-1');
assert.equal(r.resources.real_steps,12544);assert.equal(r.resources.network_forwards,0);
assert.equal(r.inferred_investigation.family_count,8);
await page.setViewportSize({width:390,height:844});
assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:15,read_only:true}));
})().catch(e=>{console.error(e);process.exit(1)});
