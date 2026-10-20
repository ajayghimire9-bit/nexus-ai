/* Read-only scientific evidence plus bounded-workbench presentation checks. */
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1400,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8785/experimental#seed-investigation-replication-1');const card=page.locator('#seed-investigation-replication-1');await card.locator('table').waitFor();
assert.equal(await card.locator('table tr').count(),6);const body=await card.textContent();
assert.ok(body.includes('FAILED'));assert.ok(body.includes('n=3 / df=2'));assert.ok(body.includes('Three independent source-trained trees'));
for(const id of ['995001','995002','995003'])assert.ok(body.includes(id));
await card.screenshot({path:'runs/seed-investigation-replication-results.png'});
await page.goto('http://127.0.0.1:8785/chat');await page.waitForFunction(()=>!document.querySelector('#message').disabled);await page.locator('#evidence').click();await page.locator('#investigation-results').click();
await page.waitForFunction(()=>document.querySelector('#details-content').textContent.includes('3 independently source-trained trees'));
assert.ok((await page.locator('#details-content a').getAttribute('href')).endsWith('seed-investigation-replication-1'));
await page.goto('http://127.0.0.1:8785/foundation');await page.waitForFunction(()=>document.querySelector('#phases').children.length===7);await page.screenshot({path:'runs/seed-phase-overview.png'});
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:12,scientific_execution:false}));
})().catch(e=>{console.error(e);process.exit(1)});
