const {chromium}=require('/home/justin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');
const server=require('child_process').spawn('.venv/bin/python',['-m','uvicorn','server.main:app','--host','127.0.0.1','--port','8876'],{env:{...process.env,BOOKLAT_SKIP_MODEL:'1',BOOKLAT_DB_PATH:'/tmp/booklat-demo-export/demo.sqlite3',BOOKLAT_RESULTS_PATH:'/tmp/booklat-demo-export/legacy.csv'},stdio:'ignore'});
process.on('exit',()=>server.kill());
(async()=>{
await new Promise(r=>setTimeout(r,1500));
const browser=await chromium.launch({executablePath:'/opt/brave-bin/brave',headless:true,args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1,reducedMotion:'reduce'});
page.on('pageerror',e=>console.error(e.message));
await page.route('**/api/engines',r=>r.fulfill({json:{vosk:{en:{loaded:true},tl:{loaded:true}},whisper:{loaded:true}}}));
await page.addInitScript(()=>{
 navigator.mediaDevices.getUserMedia=async()=>{const c=new AudioContext(),o=c.createOscillator(),g=c.createGain(),d=c.createMediaStreamDestination();g.gain.value=0;o.connect(g);g.connect(d);o.start();await c.resume();return d.stream;};
 class MockSocket{static OPEN=1;constructor(){this.readyState=1;setTimeout(()=>this.onopen?.({}),5);setTimeout(()=>this.onmessage?.({data:JSON.stringify({type:'ready',streaming:true})}),50);}send(d){if(typeof d==='string'&&JSON.parse(d).type==='stop')setTimeout(()=>this.onmessage?.({data:JSON.stringify({type:'done',marks:session.marks,first_t:0,last_t:32})}),20);}close(){this.readyState=3;}}
 window.WebSocket=MockSocket;
});
const shot=async(name)=>{await page.waitForTimeout(160);await page.screenshot({path:`demo/assets/${name}.png`});console.log(name);};
await page.goto('http://127.0.0.1:8876');await page.waitForFunction(()=>passages.length>0);
await shot('landing');
await page.locator('#open-app').click();await page.locator('#learner').fill('Alex · Demo learner');await shot('setup');
await page.locator('#passage-search').fill('Ang');await shot('language');await page.evaluate(()=>selectPassage('en-g3-1'));
await page.locator('#library summary').click();await page.locator('#import-title').fill('Our class reading');await page.locator('#import-text').fill('Every morning, Mina opens a book. She reads with her teacher, one page at a time. Today, she shares her favourite story with the class.');await page.locator('#library').scrollIntoViewIfNeeded();await shot('import');await page.locator('#library summary').click();await page.evaluate(()=>scrollTo(0,0));
await page.locator('#open-settings').click();await page.locator('#validation-mode').selectOption('live');await page.locator('#record-voice').uncheck();await page.locator('#close-settings').click();
await page.locator('#start').click();await page.waitForFunction(()=>screen==='reading'&&startedAt!==null);
await shot('read00');
for(let n of [8,17,26,36,48]){
 await page.evaluate(async n=>{const marks=session.marks.map((m,i)=>i<n?({...m,status:i===4?'substitution':i===20?'omission':'correct',heard:i===4?'yard':session.passage.tokens[i],t0:i*.66,t1:(i+1)*.66}):m);await handleEvent({type:'update',marks,changed_marks:marks,pointer:Math.min(n,marks.length),provisional:[],final:true,latency_ms:40});$('timer').textContent='00:'+String(Math.round(n*.66)).padStart(2,'0');},n);
 await shot('read'+n);
 if(n===17){await page.locator('#expand-reading').click();await shot('expanded');await page.locator('#close-passage').click();}
}
await page.locator('#stop').click();await page.waitForFunction(()=>screen==='results'&&session.saved);await page.evaluate(()=>scrollTo(0,0));await shot('results');
await page.locator('#results-passage').scrollIntoViewIfNeeded();await page.locator('#results-passage .w').nth(4).click();await shot('editor');await page.locator('#editor [data-status="correct"]').click();await page.waitForTimeout(500);await shot('corrected');await page.evaluate(()=>scrollTo(0,0));await shot('final-results');
await page.locator('#comprehension-correct').fill('4');await page.locator('#comprehension-total').fill('5');await page.locator('#grading-form button').click();await page.waitForFunction(()=>session.grading?.comprehension_pct===80);await page.locator('.grading-panel').scrollIntoViewIfNeeded();await shot('grading');
await page.evaluate(()=>scrollTo(0,0));await page.locator('#new-reading').click();await page.waitForTimeout(250);await page.locator('#history-query').scrollIntoViewIfNeeded();await shot('history');
fs.writeFileSync('demo/source/mock-session.json',JSON.stringify({note:'Synthetic recognizer events. No learner audio or personal data. Scores computed by real Booklat API.'},null,2));
await browser.close();server.kill();
})().catch(e=>{console.error(e);process.exit(1)});
