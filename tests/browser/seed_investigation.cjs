/* Bounded UI fixtures. Optional saved evidence assertion, never launches studies. */
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1400,height:950}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8785/chat');await page.waitForFunction(()=>!document.querySelector('#message').disabled);
await page.locator('[data-prompt^="Write code"]').click();await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('interpreter instructions'));
assert.ok((await page.locator('#messages').textContent()).includes('[1,2,3]'));
assert.ok((await page.locator('#messages').textContent()).includes('def transform(x)'));
await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent==='Saved locally');
await page.reload();await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('def transform(x)'));
assert.equal(await page.locator('.message.user').count(),1);
await page.screenshot({path:'runs/seed-investigation-chat.png',fullPage:true});
await page.locator('#evidence').click();await page.locator('#investigation-results').click();
if(process.argv.includes('--results')){
 await page.waitForFunction(()=>document.querySelector('#details-content').textContent.includes('Investigation transfer:'));
 await page.goto('http://127.0.0.1:8785/experimental#seed-investigation-transfer-1');await page.locator('#seed-investigation-transfer-1 table').waitFor();
 assert.equal(await page.locator('#seed-investigation-transfer-1 table tr').count(),6);
 await page.locator('#seed-investigation-transfer-1').screenshot({path:'runs/seed-investigation-results.png'});
}else await page.waitForFunction(()=>document.querySelector('#details-content').textContent.includes('has not completed'));
assert.deepEqual(errors,[]);await browser.close();console.log(JSON.stringify({passed:true,checks:process.argv.includes('--results')?8:6,scientific_execution:false}));
})().catch(e=>{console.error(e);process.exit(1)});
