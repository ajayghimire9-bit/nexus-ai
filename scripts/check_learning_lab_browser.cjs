/* Real Chromium QA; recorded data only, no fixture POST or simulator calls. */
const {chromium} = require(process.env.NEXUS_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:8766';
  if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base)) throw Error('Loopback URL only');
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:1000}});
  const errors = []; page.on('pageerror',e=>errors.push(e.message));
  const checks = [];
  try {
    await page.goto(base,{waitUntil:'networkidle',timeout:20000});
    await page.locator('#recordStatus').filter({hasText:'execution'}).waitFor();
    await page.locator('#operatorStatus').filter({hasText:'execution'}).waitFor();
    checks.push('both_verified_captures_loaded');
    await page.selectOption('#family','acrobot');
    if (await page.locator('#case option').count() !== 8) throw Error('Control family filter');
    await page.selectOption('#case','7');
    await page.locator('#tick').fill('150');await page.locator('#tick').dispatchEvent('input');
    if (!(await page.locator('#step').innerText()).includes('158')) throw Error('Recorded control decision');
    checks.push('control_filter_and_trajectory_scrub');
    await page.selectOption('#operatorFamily','acrobot');
    if (await page.locator('#operatorCase option').count() !== 8) throw Error('Operator family filter');
    await page.selectOption('#operatorCase','7');
    await page.locator('summary').click();
    if (!(await page.locator('#operatorTraining').innerText()).includes('rank_blend')) throw Error('Training evidence');
    if (!(await page.locator('#operatorDecision').innerText()).includes('training_mean_kind')) throw Error('Choice detail');
    await page.locator('#operatorTick').fill('199');await page.locator('#operatorTick').dispatchEvent('input');
    const step = JSON.parse(await page.locator('#operatorStep').innerText());
    if (step.episode_step !== 199 || !step.parent || !step.switch || !step.rank_blend) throw Error('Recorded operator paths');
    checks.push('operator_filter_training_choice_parent_comparison_and_trajectory');
    const recorded=await page.evaluate(async()=> (await fetch('/api/operators')).json());
    const failure=recorded.cases.find(c=>c.harmful_change);
    if (!failure) throw Error('Expected recorded failure case');
    await page.selectOption('#operatorFamily',failure.family);
    const familyCases=recorded.cases.filter(c=>c.family===failure.family);
    await page.selectOption('#operatorCase',String(familyCases.findIndex(c=>c.bundle===failure.bundle&&c.episode===failure.episode)));
    if (!(await page.locator('#operatorFailure').innerText()).includes('Failure on this query')) throw Error('Missing failure disclosure');
    checks.push('recorded_harmful_change_disclosed');
    if (!await page.locator('#run').isDisabled()) throw Error('Unexpected fixture permission');
    checks.push('live_execution_disabled');
    if (errors.length) throw Error(errors.join('; '));
    const screenshot=process.env.NEXUS_LAB_SCREENSHOT;
    if(screenshot) await page.screenshot({path:screenshot,fullPage:true});
    console.log(JSON.stringify({kind:'real_browser_recorded_replay_qa',browser:browser.version(),checks,page_errors:errors,
      screenshot:screenshot||null,new_environment_interactions:0,model_inference:0},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
