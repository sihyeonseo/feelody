// Exercise the calendar controller and network contract without a browser or model.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
async function run(fail){
 class El{constructor(){this.children=[];this.dataset={};this.style={setProperty(){}};this.value='';this.hidden=false}append(...n){this.children.push(...n)}replaceChildren(...n){this.children=n}setAttribute(){}focus(){}querySelector(){return null}}
 const els={},store=new Map(),requests=[];let polls=0;
 const document={getElementById:k=>els[k]??=new El(),createElement:()=>new El(),createTextNode:t=>t};
 const songs=[1,2,3].map(i=>({title:'곡'+i,artist:'가수',reason:'감정을 읽은 설명'}));
 const fetch=async(url,opts={})=>{
  requests.push([url,opts]);let data,code=200;
  if(url.endsWith('config.json'))data={apiOrigin:'.'};
  else if(url.endsWith('/healthz'))data={jobs:true,explanation_provider:'gemini'};
  else if(url.endsWith('/jobs')){data={job_id:'abc',access_token:'secret'};code=fail?429:202}
  else {assert.equal(opts.headers.Authorization,'Bearer secret');data=++polls===1?{status:'queued'}:{status:'succeeded',songs,explanation_status:'generated'}}
  return {ok:code<300,status:code,json:async()=>data}
 };
 const ctx=vm.createContext({document,fetch,window:{addEventListener(){}},localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},AbortController,AbortSignal,URL,Date,
 setTimeout:(fn,ms)=>setTimeout(fn,ms===1000?0:ms),clearTimeout});
 for(const p of ['moods','app'])vm.runInContext(fs.readFileSync('web/'+p+'.js','utf8'),ctx);
 await new Promise(ok=>setImmediate(ok));els.write.onclick();els.diary.value='오늘 좋은 일이 있었다.';els.moods.children[0].onclick();els.explain.checked=true;
 await els.save.onclick();
 assert.equal(JSON.parse(requests.find(([url])=>url.endsWith('/jobs'))[1].body).explain,true);
 const entry=JSON.parse([...store.values()][0]);assert.equal(entry.text,els.diary.value);
 if(fail){assert.match(els.message.textContent,/가득/);assert.equal(entry.songs.length,0)}
 else{assert.equal(entry.songs.length,3);assert.equal(entry.songs[0].reason,songs[0].reason);assert.equal(els.cards.children.length,3);assert.ok(!JSON.stringify(entry).includes('secret'))}
}
(async()=>{await run(false);await run(true);console.log('Calendar job success and queue-full flows OK')})().catch(e=>{console.error(e);process.exitCode=1})
