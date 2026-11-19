const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
async function run(fail,cancel=false){
 class El{constructor(){this.children=[];this.dataset={};this.style={setProperty(){}};this.value='';this.hidden=false}append(...n){this.children.push(...n)}replaceChildren(...n){this.children=n}setAttribute(){}focus(){}querySelector(){return null}}
 const els={},store=new Map(),requests=[],intervals=new Set();let clock=0,release,forceFailure=false;
 const document={getElementById:k=>els[k]??=new El(),createElement:()=>new El(),createTextNode:t=>t};
 const songs=[1,2,3].map(i=>({title:'곡'+i,artist:'가수',reason:'감정을 읽은 설명'}));
 const fetch=async(url,opts={})=>{
  requests.push([url,opts]);let data,code=200;
  if(url.endsWith('config.json'))data={mode:'llm',apiOrigin:''};
  else if(!opts.method)data={configured:!fail,provider:'openai',message:'설정 필요',timing_key:'openai:fixture:default:v1'};
  else{await new Promise(ok=>release=ok);assert.equal(url,'/api/recommend');code=(fail||forceFailure)?503:200;
   const body=JSON.parse(opts.body), offset=body.excluded_songs?.length?3:body.diary==='수정한 일기'?6:0;
   const selected=songs.map((s,i)=>({...s,title:'곡'+(i+1+offset),youtube_url:'https://www.youtube.com/results?search_query='+encodeURIComponent(s.artist+' 곡'+(i+1+offset)+' 공식 음악')}));
   data=code!==200?{message:'API 설정 확인'}:{source:'llm',summary:'<b>요약</b>',empathy:'공감하는 문장',songs:selected,request_id:'request-'+requests.length,generated_at:'2026-11-19T12:00:00Z'}}
  return {ok:code<300,status:code,json:async()=>data}
 };
 const ctx=vm.createContext({document,fetch,window:{addEventListener(){}},localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},AbortController,AbortSignal,URL,Date,setTimeout,clearTimeout,performance:{now:()=>clock},setInterval:fn=>{intervals.add(fn);return fn},clearInterval:fn=>intervals.delete(fn)});
 for(const p of ['moods','app'])vm.runInContext(fs.readFileSync('web/'+p+'.js','utf8'),ctx);
 await new Promise(ok=>setImmediate(ok));els.write.onclick();els.diary.value='오늘 좋은 일이 있었다.';els.moods.children[0].onclick();
 const pending=els.save.onclick();
 assert.equal(els.waiting.hidden,false);assert.equal(els.waitElapsed.textContent,'0초 경과');
 clock=8000;for(const tick of intervals)tick();assert.equal(els.waitElapsed.textContent,'8초 경과');
 clock=31000;for(const tick of intervals)tick();assert.match(els.waitTitle.textContent,/늦어/);
 if(cancel){els.diary.value='수정';els.diary.oninput();assert.equal(els.waiting.hidden,true)}
 release();await pending;
 assert.equal(intervals.size,0);assert.equal(els.waiting.hidden,true);
 if(cancel){assert.equal(els.reflection.hidden,true);return}

 const entry=JSON.parse([...store.values()][0]);assert.equal(entry.text,els.diary.value);
 assert.equal(requests.filter(([,v])=>v.method==='POST').length,1);
 if(fail){assert.match(els.message.textContent,/일기는 저장/);assert.equal(entry.songs.length,0);assert.equal(els.music.hidden,true)}
 else{assert.equal(entry.source,'llm');assert.equal(entry.songs.length,3);assert.equal(els.summary.textContent,'<b>요약</b>');assert.equal(els.empathy.textContent,entry.empathy);assert.equal(els.cards.children.length,3);
  const history=JSON.parse(store.get('feelody/timings/v1'));assert.equal(history.samples[0].seconds,31);
  const next=els.save.onclick();assert.equal(els.music.hidden,true);assert.equal(els.reflection.hidden,true);assert.match(els.waitHistory.textContent,/이전 추천은 약 31초/);release();await next;
  els.write.onclick();assert.equal(els.summary.textContent,entry.summary);assert.equal(els.cards.children.length,3);
  const reroll=els.otherSongs.onclick();assert.equal(els.music.hidden,true);
  assert.equal(JSON.parse(requests.at(-1)[1].body).excluded_songs.length,3);
  release();await reroll;
  assert.equal(JSON.parse([...store.values()][0]).songs[0].title,'곡4');
  assert.equal(new URL(els.cards.children[0].href).searchParams.get('search_query'),'가수 곡4 공식 음악');
  const count=requests.length;els.diary.value='수정한 일기';els.diary.oninput();assert.equal(els.reflection.hidden,true);assert.equal(requests.length,count);
  const different=els.save.onclick();assert.equal(JSON.parse(requests.at(-1)[1].body).diary,'수정한 일기');
  assert.equal(JSON.parse(requests.at(-1)[1].body).excluded_songs.length,0);release();await different;
  assert.equal(JSON.parse([...store.values()][0]).songs[0].title,'곡7');
  assert.equal(new URL(els.cards.children[0].href).searchParams.get('search_query'),'가수 곡7 공식 음악');
  forceFailure=true;const broken=els.save.onclick();assert.equal(els.music.hidden,true);release();await broken;
  assert.equal(els.music.hidden,true);assert.equal(els.reflection.hidden,true);assert.equal(JSON.parse([...store.values()][0]).songs.length,0);
  assert.equal(JSON.parse([...store.values()][0]).text,'수정한 일기');
 }
}
(async()=>{await run(false);await run(true);await run(false,true);console.log('LLM UI: summary, empathy, 3 reasons, persistence, edits and errors OK')})().catch(e=>{console.error(e);process.exitCode=1})
