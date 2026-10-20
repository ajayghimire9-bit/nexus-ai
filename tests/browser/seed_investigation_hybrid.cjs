/* Saved result GUI only. Cannot launch an experiment. */
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1400,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8785/chat');await page.waitForFunction(()=>!document.querySelector('#message').disabled);
await page.locator('#evidence').click();await page.locator('#investigation-results').click();
await page.waitForFunction(()=>document.querySelector('#details-content').textContent.includes('tree_greedy'));
assert.ok((await page.locator('#details-content a').getAttribute('href')).endsWith('seed-investigation-hybrid-1'));
await page.goto('http://127.0.0.1:8785/experimental#seed-investigation-hybrid-1');const card=page.locator('#seed-investigation-hybrid-1');await card.locator('table').waitFor();
assert.equal(await card.locator('table tr').count(),6);
for(const name of ['tree_fixed','tree_greedy','greedy','fixed_order','no_library'])assert.ok((await card.textContent()).includes(name));
assert.ok((await card.textContent()).includes('total including source'));
assert.ok((await card.textContent()).includes('five-question tail'));
assert.ok((await card.textContent()).includes('equal-rule'));
await card.screenshot({path:'runs/seed-investigation-hybrid-results.png'});
assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:11,scientific_execution:false}));
})().catch(e=>{console.error(e);process.exit(1)});
