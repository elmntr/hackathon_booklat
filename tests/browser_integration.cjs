// Real HTTP APIs with a synthetic microphone and recognizer events. No learner audio is used.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.env.BOOKLAT_TEST_URL||'http://127.0.0.1:8765';
const runId=Date.now(),learner='Integration learner '+runId,notesTitle='Integration notes '+runId;
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1366,height:768},reducedMotion:'reduce'});
  const page=await context.newPage(),errors=[],external=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(!r.url().startsWith(base)&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))external.push(r.url());});
  await page.route('**/api/engines',route=>route.fulfill({json:{vosk:{en:{loaded:true},tl:{loaded:true}},whisper:{loaded:true,model:'test',device:'cpu',compute_type:'int8'}}}));
  await page.addInitScript(()=>{
    navigator.mediaDevices.getUserMedia=async()=>{
      const ctx=new AudioContext(),oscillator=ctx.createOscillator(),mute=ctx.createGain(),destination=ctx.createMediaStreamDestination();
      mute.gain.value=0;oscillator.connect(mute);mute.connect(destination);oscillator.start();await ctx.resume();return destination.stream;
    };
    class FixtureSocket {
      static OPEN=1;
      constructor(url){this.readyState=1;window.fixtureSocketUrl=String(url);setTimeout(()=>this.onopen?.({}),5);setTimeout(()=>this.onmessage?.({data:JSON.stringify({type:'ready',streaming:true})}),40);}
      send(data){if(typeof data==='string'&&JSON.parse(data).type==='stop')setTimeout(()=>this.onmessage?.({data:JSON.stringify({type:'done',marks:session.marks,first_t:0,last_t:.8})}),15);}
      close(){this.readyState=3;}
    }
    window.WebSocket=FixtureSocket;
  });
  try{
    await page.goto(base);await page.waitForFunction(()=>passages.length>0);
    assert(await page.locator('#landing-screen').isVisible());assert(!(await page.locator('#setup-screen').isVisible()));
    for(const size of [{width:1280,height:720},{width:1366,height:768},{width:360,height:800}]){
      await page.setViewportSize(size);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    }
    await page.locator('#open-app').click();assert(!(await page.locator('#landing-screen').isVisible()));
    await page.locator('#learner').fill(learner);
    // Seed a longer library and history in isolated storage, then exercise the actual scroll/search UI.
    let fixturePassage;
    for(let i=0;i<7;i++){
      const response=await page.request.post(base+'/api/passages',{data:{title:`Search fixture ${runId} ${i}`,text:'Mina reads',language:'en'}});fixturePassage=await response.json();
      await page.request.post(base+'/api/score',{data:{session_id:`scroll-${runId}-${i}`,learner:`Scroll fixture ${runId}`,passage_id:fixturePassage.id,engine:'vosk',marks:[{status:'correct',repeats:0},{status:'correct',repeats:0}],first_t:0,last_t:1,save:true}});
    }
    await page.evaluate(async()=>{passages=await api('/api/passages');populatePassages();await recent();});
    assert(await page.evaluate(()=>document.getElementById('passage-list').scrollHeight>document.getElementById('passage-list').clientHeight));
    await page.locator('#passage-search').fill(`Search fixture ${runId} 5`);assert.equal(await page.locator('#passage-list [role="option"]').count(),1);
    await page.locator('#passage-list [role="option"]').click();assert((await page.locator('#preview-heading').textContent()).endsWith('5'));
    await page.locator('#expand-preview').click();assert(await page.locator('#large-passage-body #preview').isVisible());await page.locator('#close-passage').click();assert(await page.locator('.preview #preview').isVisible());
    await page.locator('#clear-passage-search').click();await page.locator('#passage-search').fill('no matching fixture');assert(await page.locator('#passage-empty').isVisible());await page.locator('#clear-passage-search').click();
    for(const size of [{width:1280,height:720},{width:1366,height:768},{width:360,height:800}]){
      await page.setViewportSize(size);await page.waitForTimeout(100);
      assert(await page.evaluate(()=>{const v=document.getElementById('history-viewport'),r=document.querySelectorAll('#recent-body tr');return v.scrollHeight>v.clientHeight&&r[3].getBoundingClientRect().bottom<=v.getBoundingClientRect().bottom+1&&r[4].getBoundingClientRect().top>=v.getBoundingClientRect().bottom-24;}));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    }

    await page.locator('#open-settings').click();await page.locator('#mic-check').click();await page.waitForFunction(()=>document.getElementById('mic-level-label').textContent.includes('Quiet'));
    await page.waitForTimeout(1100);assert((await page.locator('#mic-check').textContent()).includes('Stop'));
    await page.locator('#mic-check').click();await page.waitForFunction(()=>!micChecking);assert.equal(await page.locator('#mic-level').getAttribute('aria-valuenow'),'0');
    await page.locator('#close-settings').click();await page.locator('#library summary').click();
    await page.locator('#import-file').setInputFiles({name:notesTitle+'.txt',mimeType:'text/plain',buffer:Buffer.from('Mina has a garden')});
    await page.waitForFunction(()=>document.getElementById('import-text').value==='Mina has a garden');
    await page.locator('#save-passage').click();await page.waitForFunction(title=>passages.some(p=>p.title===title),notesTitle);
    await page.locator('#open-settings').click();await page.locator('#validation-mode').selectOption('auto_finish');await page.locator('#finish-delay').selectOption('1');await page.locator('#close-settings').click();
    await page.locator('#start').click();await page.waitForFunction(()=>screen==='reading'&&startedAt!==null);
    await page.evaluate(async()=>{const marks=session.marks.map((m,i)=>({...m,status:'correct',heard:session.passage.tokens[i],t0:i*.2,t1:(i+1)*.2}));await handleEvent({type:'update',marks,changed_marks:marks,pointer:4,provisional:[],final:true,latency_ms:1});});
    await page.waitForFunction(()=>screen==='results'&&session.saved&&session.audioSaved);
    assert.equal(await page.locator('#results-passage .w').count(),4);
    assert.equal(await page.locator('#results-passage .correct').count(),4);
    assert((await page.locator('#completion-message').textContent()).includes('automatically'));
    assert(await page.locator('#recording-controls').isVisible());
    for(const size of [{width:1280,height:720},{width:1366,height:768},{width:360,height:800}]){
      await page.setViewportSize(size);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    }
    await page.locator('#reviewed-miscues').fill('1');await page.locator('#comprehension-correct').fill('3');await page.locator('#comprehension-total').fill('5');
    await page.locator('#grading-form button').click();await page.waitForFunction(()=>session.grading?.comprehension_pct===60);
    const id=await page.evaluate(()=>session.id),stored=await (await page.request.get(base+'/api/results/'+id)).json();
    assert.equal(stored.reading.grading.philiri_word_score_pct,75);assert.equal(stored.recordings.length,1);
    const report=await (await page.request.get(base+'/api/results/'+id+'/report.html')).text();assert(report.includes('59–79%'));assert(report.includes('Integration learner'));
    await page.locator('#results-passage .w').first().click();await page.locator('#editor [data-status="substitution"]').click();
    await page.waitForFunction(()=>session.grading?.substitutions===1);
    await page.locator('#review-filter').selectOption('substitution');assert.equal(await page.locator('#results-passage .w:visible').count(),1);
    assert((await page.locator('#results-passage').textContent()).includes('Heard: Mina'));
    await page.locator('#review-filter').selectOption('all');await page.locator('#new-reading').click();
    await page.locator('#history-query').fill(learner);await page.locator('#history-search-form button').click();
    await page.waitForFunction(()=>document.querySelectorAll('#recent-body tr').length===1);
    await page.locator('#recent-body button').click();await page.waitForFunction(()=>screen==='results');
    assert.equal(await page.locator('#results-passage .w').count(),4);assert(await page.locator('#recording-controls').isVisible());
    await page.locator('#results-passage .w').first().click();await page.locator('#play-word').click();
    await page.waitForFunction(()=>document.getElementById('recording-player').currentTime>0);
    await page.locator('#delete-recording').click();await page.waitForFunction(()=>session.recordings.length===0);
    assert.equal((await (await page.request.get(base+'/api/results/'+id)).json()).recordings.length,0);
    await page.locator('#new-reading').click();await page.locator('#open-settings').click();await page.locator('#validation-mode').selectOption('after_pause');await page.locator('#close-settings').click();await page.locator('#start').click();
    await page.waitForFunction(()=>screen==='reading'&&startedAt!==null);
    await page.evaluate(async()=>{const marks=session.marks.slice(0,2).map((m,i)=>({...m,status:'correct',heard:session.passage.tokens[i],t0:i*.2,t1:(i+1)*.2}));await handleEvent({type:'update',marks,changed_marks:marks,pointer:2,provisional:[0,1],final:false,latency_ms:1});});
    assert.equal(await page.locator('#reading-passage .correct').count(),0);assert.equal(await page.locator('#reading-passage .read-highlight').count(),2);
    await page.evaluate(async()=>{const marks=session.marks.map(m=>({...m}));await handleEvent({type:'update',marks,changed_marks:marks,pointer:2,provisional:[],final:true,latency_ms:1});});
    assert.equal(await page.locator('#reading-passage .correct').count(),2);
    await page.locator('#expand-reading').click();assert(await page.locator('#passage-dialog').isVisible());assert(await page.locator('#large-passage-body #reading-passage').isVisible());
    await page.locator('#reading-passage .w').first().click();await page.locator('#editor [data-status="correct"]').click();
    await page.keyboard.press('Escape');assert(await page.locator('#passage-dialog').isVisible());await page.keyboard.press('Escape');assert(!(await page.locator('#passage-dialog').isVisible()));
    assert(await page.locator('#reading-screen #reading-passage').isVisible());
    await page.reload();await page.locator('#open-app').click();assert(await page.locator('#draft-banner').isVisible());
    await page.locator('#draft-resume').click();await page.waitForFunction(()=>screen==='reading'&&startedAt!==null);
    assert((await page.evaluate(()=>window.fixtureSocketUrl)).includes('start_index=2'));
    await page.locator('#expand-reading').click();await page.locator('#overlay-stop').click();await page.waitForFunction(()=>screen==='results');
    assert.equal(await page.locator('#results-passage .w').count(),4);
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log('Browser integration passed: landing, responsive layouts, microphone check, import, auto finish, marks, grading/report, voice/history, edit/filter, deletion, pause mode, draft resume, searchable four-row lists, settings and live passage overlays.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
