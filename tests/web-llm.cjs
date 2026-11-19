const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
async function run(fail){
 class El{constructor(){this.children=[];this.dataset={};this.style={setProperty(){}};this.value='';this.hidden=false}append(...n){this.children.push(...n)}replaceChildren(...n){this.children=n}setAttribute(){}focus(){}querySelector(){return null}}
 const els={},store=new Map(),requests=[];
 const document={getElementById:k=>els[k]??=new El(),createElement:()=>new El(),createTextNode:t=>t};
 const songs=[1,2,3].map(i=>({title:'곡'+i,artist:'가수',reason:'감정을 읽은 설명'}));
 const fetch=async(url,opts={})=>{
  requests.push([url,opts]);let data,code=200;
  if(url.endsWith('config.json'))data={mode:'llm',apiOrigin:''};
  else if(!opts.method)data={configured:!fail,provider:'openai',message:'설정 필요'};
  else{assert.equal(url,'/api/recommend');code=fail?503:200;data=fail?{message:'API 설정 확인'}:{source:'llm',summary:'<b>요약</b>',empathy:'공감하는 문장',songs}}
  return {ok:code<300,status:code,json:async()=>data}
 };
 const ctx=vm.createContext({document,fetch,window:{addEventListener(){}},localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},AbortController,AbortSignal,URL,Date,setTimeout,clearTimeout});
 for(const p of ['moods','app'])vm.runInContext(fs.readFileSync('web/'+p+'.js','utf8'),ctx);
 await new Promise(ok=>setImmediate(ok));els.write.onclick();els.diary.value='오늘 좋은 일이 있었다.';els.moods.children[0].onclick();
 await els.save.onclick();
 const entry=JSON.parse([...store.values()][0]);assert.equal(entry.text,els.diary.value);
 assert.equal(requests.filter(([,v])=>v.method==='POST').length,1);
 if(fail){assert.match(els.message.textContent,/일기는 저장/);assert.equal(entry.songs.length,0);assert.equal(els.music.hidden,true)}
 else{assert.equal(entry.source,'llm');assert.equal(entry.songs.length,3);assert.equal(els.summary.textContent,'<b>요약</b>');assert.equal(els.empathy.textContent,entry.empathy);assert.equal(els.cards.children.length,3);
  els.write.onclick();assert.equal(els.summary.textContent,entry.summary);assert.equal(els.cards.children.length,3);
  const count=requests.length;els.diary.value='수정한 일기';els.diary.oninput();assert.equal(els.reflection.hidden,true);assert.equal(requests.length,count)}
}
(async()=>{await run(false);await run(true);console.log('LLM UI: summary, empathy, 3 reasons, persistence, edits and errors OK')})().catch(e=>{console.error(e);process.exitCode=1})
