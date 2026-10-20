/* Actual local HTTP/UI engineering checks, no scientific outcomes. */
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1400,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(process.argv[2]||'http://127.0.0.1:8785/foundation');
await page.waitForFunction(()=>document.querySelector('#stage').options.length===6);
await page.locator('#stage').selectOption('4');await page.locator('#exercise').click();await page.waitForFunction(()=>document.querySelector('#lesson').textContent.includes('"passed": true'));
await page.locator('#execute').click();await page.waitForFunction(()=>document.querySelector('#execution').textContent.includes('"instructions"'));assert.deepEqual(JSON.parse(await page.locator('#execution').textContent()).value,[1,3]);
await page.locator('#ingest').click();await page.waitForFunction(()=>document.querySelector('#memory').textContent.includes('key matches lock'));
await page.locator('#retrieve').click();await page.waitForFunction(()=>document.querySelector('#knowledge').textContent.startsWith('['));
await page.locator('#advanced').click();await page.waitForFunction(()=>document.querySelector('#advancedResult').textContent.includes('"candidates"'));
await page.locator('#operation').selectOption('review');await page.locator('#advanced').click();await page.waitForFunction(()=>document.querySelector('#advancedResult').textContent.includes('"accepted": true'));
const before=JSON.parse(await page.locator('#memory').textContent());assert.ok(before.active_macro);
await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#advancedResult').textContent.includes('"hash"'));
await page.locator('#load').click();await page.waitForTimeout(150);assert.deepEqual(JSON.parse(await page.locator('#memory').textContent()),before);
await page.locator('#operation').selectOption('rollback');await page.locator('#advanced').click();await page.waitForFunction(()=>JSON.parse(document.querySelector('#memory').textContent).active_macro===null);
await page.screenshot({path:'runs/seed-foundation-gui.png',fullPage:true});assert.deepEqual(errors,[]);
await browser.close();console.log(JSON.stringify({passed:true,checks:9,scientific:false,scientific_interactions:0,neural_calls:0}));
})().catch(e=>{console.error(e);process.exit(1)});
