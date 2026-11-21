'use strict';
const $=id=>document.getElementById(id),node=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e};
const pad=n=>String(n).padStart(2,'0'),key=(y,m,d)=>y+'-'+pad(m+1)+'-'+pad(d);
const today=()=>{const t=new Date();return key(t.getFullYear(),t.getMonth(),t.getDate())};
const prefix='feelody/journal/v1/', labels=Object.keys(MOODS),hasMood=m=>Object.hasOwn(MOODS,m);
let month=new Date();month.setDate(1);let active=null,picked=null,manual=false,dirty=false,api='',busy=null,ready=false,legacy=false,provider=null,llmMode=true,llmConfigured=false,llmMessage='',llmTimingKey='';
// Public sample catalog; random selection is not an emotion model result.
const RANDOM_TRACKS=[{"title":"What's Love Got To Do With It","artist":"Tina Turner"},{"title":"The Glamorous Life","artist":"Sheila E."},{"title":"When You Close Your Eyes","artist":"Night Ranger"},{"title":"One More Chance/Stay With Me","artist":"The Notorious B.I.G."},{"title":"I Can Love You Like That","artist":"All-4-One"},{"title":"Hold Me, Thrill Me, Kiss Me, Kill Me","artist":"U2"},{"title":"Disco Inferno","artist":"50 Cent"},{"title":"Some Cut","artist":"Trillville Featuring Cutty"},{"title":"Switch","artist":"Will Smith"},{"title":"Someone Like You","artist":"Adele"},{"title":"It Will Rain","artist":"Bruno Mars"},{"title":"I Wanna Dance With Somebody (Who Loves Me)","artist":"Whitney Houston"},{"title":"Sicko Mode","artist":"Travis Scott"},{"title":"Nonstop","artist":"Drake"},{"title":"I Had Some Help","artist":"Post Malone Featuring Morgan Wallen"},{"title":"Beautiful Things","artist":"Benson Boone"},{"title":"Guess","artist":"Charli xcx Featuring Billie Eilish"}];
function randomSongs(){const pool=[...RANDOM_TRACKS];for(let i=pool.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]]}return pool.slice(0,3).map(s=>({...s}))}
function read(day){if(window.journalAccount?.user)return journalAccount.entries.get(day)||null;try{const v=JSON.parse(localStorage.getItem(prefix+day));return v&&typeof v.text==='string'&&hasMood(v.mood)?v:null}catch{return null}}
async function write(day,v){if(window.journalAccount?.user){try{document.querySelector('main').inert=true;await journalAccount.save(day,v);return true}catch{$("message").textContent="Could not save to your account. Please try again.";return false}finally{document.querySelector("main").inert=false}}try{localStorage.setItem(prefix+day,JSON.stringify(v));return true}catch{$('message').textContent='Could not save in this browser. Copy your entry before leaving.';return false}}
function face(m){const i=node('i','face '+m);i.style.setProperty('--c',MOODS[m].color);i.setAttribute('aria-hidden','true');return i}
function disc(){const i=node('div','disc');i.setAttribute('aria-hidden','true');return i}
function calendar(){
 const y=month.getFullYear(),m=month.getMonth(),start=new Date(y,m,1).getDay(),days=new Date(y,m+1,0).getDate();
 $('month').replaceChildren(node('span','',String(y)+' / '),document.createTextNode(month.toLocaleDateString('en-US',{month:'long'})));const grid=$('grid');grid.replaceChildren();let n=0;
 for(let i=0;i<start;i++)grid.append(node('span'));
 for(let d=1;d<=days;d++){
  const k=key(y,m,d),r=read(k),b=node('button','date'+(k===today()?' today':'')+(r?' filled':''));
  b.type='button';b.dataset.day=k;b.setAttribute('aria-label',k+(r?' '+MOODS[r.mood].name+' entry':' write an entry'));if(k===today())b.setAttribute('aria-current','date');
  if(r){n++;b.append(face(r.mood))}b.append(node('span','number',d));b.onclick=()=>openDay(k);grid.append(b)
 }
 $('count').textContent='Entries this month: '+n;$('sideNote').textContent=read(today())?'Revisit today’s entry and its soundtrack.':'One entry starts a playlist.';
}
function choose(m,isManual){
 picked=m;manual=isManual;for(const b of $('moods').children)b.setAttribute('aria-pressed',String(b.dataset.m===picked));
 $('suggestion').textContent=manual?'Your mood':picked?'Suggested from your entry. Change it if you like.':'Pick the closest mood.';
}
function viewSongs(r){
 $('otherSongs').hidden=!(llmMode&&r?.source==='llm'&&Array.isArray(r.songs)&&r.songs.length===3);

 const hasReflection=r?.source==='llm'&&typeof r.summary==='string'&&typeof r.empathy==='string';
 $('reflection').hidden=!hasReflection;
 $('summary').textContent=hasReflection?r.summary:'';
 $('empathy').textContent=hasReflection?r.empathy:'';

 const ok=r&&['model','random','llm'].includes(r.source)&&Array.isArray(r.songs)&&r.songs.length===3;$('music').hidden=!ok;$('cards').replaceChildren();if(!ok)return;
 $('source').textContent=r.source==='llm'?'Three songs for this entry':r.source==='random'?'Sample playlist':'Three tracks selected by lyric similarity';
  if(r.source==='llm'&&r.generated_at&&!Number.isNaN(Date.parse(r.generated_at))){
  $('source').textContent+=' · '+new Date(r.generated_at).toLocaleTimeString('en-US')+' generated';
 }
 for(const [i,s] of r.songs.entries()){
  const a=node('a','track'),u=new URL('https://www.youtube.com/results');u.searchParams.set('search_query',s.artist+' '+s.title+' official music');
  try{const provided=new URL(s.youtube_url);if(provided.origin==='https://www.youtube.com'&&provided.pathname==='/results'&&provided.searchParams.get('search_query')===u.searchParams.get('search_query'))a.href=provided.href;else a.href=u.href}catch{a.href=u.href}a.target='_blank';a.rel='noopener noreferrer';a.setAttribute('aria-label',s.artist+' '+s.title+' on YouTube (new tab)');
  a.append(disc(),node('small','','TRACK 0'+(i+1)),node('b','',s.title),node('span','',s.artist),node('u','','Find on YouTube ↗'));if(s.reason)a.append(node('p','reason','Why it fits · '+s.reason));$('cards').append(a);
 }
}
function note(){
 $('modelChoiceLabel').hidden=!llmMode;
 $('save').textContent=llmMode&&!$('modelChoice').checked?'Save entry':'Find my songs';
 if(active)$('modeNote').textContent=!ready?'Checking recommendations…':llmMode?
  (llmConfigured?'Save your entry here, or choose to send it for song recommendations.':llmMessage||'Recommendations are unavailable. Your entry can still be saved in this browser.'):
  api?'Your entry is saved in this browser and sent to the music model.':'Sample mode picks three tracks without analyzing the entry.';
 if(active&&window.journalAccount?.user)$('modeNote').textContent=$('modeNote').textContent.replaceAll('in this browser','to your account');
}
function openDay(day){
 $('modelChoice').checked=false;
 active=day;dirty=false;$('explain').checked=false;const r=read(day),[y,m,d]=day.split('-').map(Number);$('home').hidden=true;$('editor').hidden=false;
 $('dayTitle').textContent=new Date(y,m-1,d).toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'});$('diary').value=r?.text||'';$('message').textContent='';choose(r?.mood||null,!!r);$('remove').hidden=!r;if(!window.journalAccount?.user&&!llmMode&&r?.text&&(!Array.isArray(r.songs)||r.songs.length!==3)){r.source='random';r.songs=randomSongs();write(day,r)}viewSongs(r);note();$('dayTitle').focus();
}
function home(){if(dirty&&!window.confirm('Discard unsaved changes?'))return;busy?.abort();busy=null;$('save').disabled=!ready;dirty=false;const old=active;active=null;$('home').hidden=false;$('editor').hidden=true;calendar();$('grid').querySelector('[data-day="'+old+'"]')?.focus()}
$('back').onclick=home;$('prev').onclick=()=>{month.setMonth(month.getMonth()-1);calendar()};$('next').onclick=()=>{month.setMonth(month.getMonth()+1);calendar()};$('now').onclick=()=>{month=new Date();month.setDate(1);calendar()};$('write').onclick=()=>{month=new Date();month.setDate(1);openDay(today())};
for(const w of ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'])$('week').append(node('span','',w));
$('cover').append(disc());
function edited(){dirty=true;busy?.abort();$('message').textContent='';viewSongs(null)}
for(const m of labels){
 const it=node('span');it.append(face(m),document.createTextNode(MOODS[m].name));$('legend').append(it);
 const b=node('button','choice');b.dataset.m=m;b.append(face(m),document.createTextNode(MOODS[m].name));b.onclick=()=>{edited();choose(m,true)};$('moods').append(b)
}
$('diary').oninput=()=>{edited();if(!manual){
 const t=$('diary').value;let idx=-1,guess=null;for(const m of labels){for(const match of t.matchAll(new RegExp(MOODS[m].hint.source,'gi'))){if(match.index>idx){idx=match.index;guess=m}}}choose(guess,false);}
};
$('remove').onclick=async()=>{if(!window.confirm('Delete this entry and playlist?'))return;
 busy?.abort();try{if(window.journalAccount?.user)await journalAccount.remove(active);else localStorage.removeItem(prefix+active)}catch{$('message').textContent='Could not delete this entry.';return}dirty=false;home()};
function recentWaits(key){
 if(!key)return [];
 try{const value=JSON.parse(localStorage.getItem('feelody/timings/v1'));
  return value?.key===key&&Array.isArray(value.samples)?value.samples.filter(x=>Number.isFinite(x.seconds)&&x.seconds>0&&x.seconds<60&&Date.now()-x.at<86400000).slice(-5):[];
 }catch{return []}
}
function rememberWait(key,seconds){
 if(!key||!Number.isFinite(seconds)||seconds<=0)return;
 try{localStorage.setItem('feelody/timings/v1',JSON.stringify({key,samples:[...recentWaits(key),{seconds,at:Date.now()}].slice(-5)}))}catch{}
}
function startWait(ctrl,day){
 const started=performance.now(),panel=$('waiting'),samples=recentWaits(llmTimingKey).map(x=>Math.ceil(x.seconds));
 const elapsed=()=>Math.max(0,(performance.now()-started)/1000);
 panel.hidden=false;
 $('waitHistory').textContent=samples.length===0?'Your reflection and playlist will appear together.':
  samples.length===1?'Last time it took about '+samples[0]+'s. This time may differ.':
  'The last '+samples.length+' requests took '+Math.min(...samples)+'~'+Math.max(...samples)+'s. This time may differ.';
 const tick=()=>{if(busy!==ctrl||active!==day||ctrl.signal.aborted)return;
  $('waitElapsed').textContent=Math.floor(elapsed())+'s elapsed';
  $('waitTitle').textContent=elapsed()>=30?'Still finding your songs…':'Finding your songs';
 };
 tick();
 const interval=setInterval(tick,1000);
 const stop=()=>{clearInterval(interval);if(busy===ctrl)panel.hidden=true;ctrl.signal.removeEventListener('abort',stop)};
 ctrl.signal.addEventListener('abort',stop,{once:true});
 return {stop,elapsed};
}
$('modelChoice').onchange=note;
async function readPlaylistResponse(resp){
 const ref=(resp.headers.get('cf-ray')||'').replace(/[^a-zA-Z0-9-]/g,'').slice(0,40);
 const fail=()=>Error('Playlist unavailable (HTTP '+resp.status+(ref?', ref '+ref:'')+'). Please try again later.');
 if(!(resp.headers.get('content-type')||'').toLowerCase().includes('application/json'))throw fail();
 try{const value=await resp.json();if(!value||typeof value!=='object'||Array.isArray(value))throw fail();return value}catch{throw fail()}
}
async function saveWithLLM(day,text,mood,excluded=[]){
 if(!$('modelChoice').checked){
 if(excluded.length){$('message').textContent='Enable the recommendation option first.';return}
 const old=read(day);const entry=old?.text===text&&old.mood===mood?old:{text,mood,source:'none',songs:[]};
 if(await write(day,entry)){dirty=false;viewSongs(entry);$('remove').hidden=false;$('message').textContent='Entry saved without sending it for recommendations.'}return;
 }
 // A failed new request must not look like another successful copy of an old response.
 const r={text,mood,source:'none',songs:[]};
 if(!await write(day,r))return;
 dirty=false;$('remove').hidden=false;viewSongs(r);
 const ctrl=new AbortController();busy=ctrl;$('save').disabled=true;
 const waiting=startWait(ctrl,day);
 $('message').textContent='Entry saved. Finding songs for your mood…';
 const timer=setTimeout(()=>ctrl.abort(),55000);
 try{
  const resp=await fetch('/api/recommend',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','Accept':'application/json'},
   body:JSON.stringify({diary:text,mood,excluded_songs:excluded}),signal:ctrl.signal});
  const data=await readPlaylistResponse(resp);
  if(!resp.ok)throw Error(typeof data.message==='string'?data.message:'Could not get recommendations.');
  if(data.source!=='llm'||typeof data.summary!=='string'||typeof data.empathy!=='string'||
   !Array.isArray(data.songs)||data.songs.length!==3||data.songs.some(s=>['title','artist','reason'].some(k=>typeof s?.[k]!=='string')))throw Error('Could not read the response.');
  if(busy!==ctrl||dirty||active!==day||ctrl.signal.aborted)return;
  rememberWait(data.timing_key||llmTimingKey,waiting.elapsed());
  Object.assign(r,{source:'llm',summary:data.summary,empathy:data.empathy,
   request_id:data.request_id,generated_at:data.generated_at,
   songs:data.songs.map(({title,artist,reason,youtube_url})=>({title,artist,reason,youtube_url}))});
  if(await write(day,r)){viewSongs(r);$('message').textContent='Entry and soundtrack saved in '+waiting.elapsed().toFixed(1)+'s'}
 }catch(e){if(busy===ctrl&&!dirty&&active===day)$('message').textContent='Entry saved. '+(e.name==='AbortError'?'The request timed out. Please try again.':e.message)}
 finally{waiting.stop();clearTimeout(timer);if(busy===ctrl){busy=null;$('save').disabled=false}}
}
$('otherSongs').onclick=async()=>{
 const r=read(active),text=$('diary').value.trim();
 if(busy||!llmMode||!r||r.source!=='llm'||r.text!==text||dirty)return;
 await saveWithLLM(active,text,picked,r.songs.map(({title,artist})=>({title,artist})));
};
$('save').onclick=async()=>{
 const day=active,text=$('diary').value.trim(),m=picked;if(!day||busy||!ready)return;
 if(!text){$('message').textContent='Write at least one line.';$('diary').focus();return}
 if(!m){$('message').textContent='Pick a mood first.';$('moods').firstChild.focus();return}
 if(llmMode){await saveWithLLM(day,text,m);return}
 const r={text,mood:m,source:'random',songs:randomSongs()};
 const old=read(day);if(old?.source==='model'&&old.text===text&&Array.isArray(old.songs)&&old.songs.length===3){r.source='model';r.songs=old.songs}
 if(!await write(day,r))return;dirty=false;$('remove').hidden=false;viewSongs(r);
 if(!api){$('message').textContent=r.source==='model'?'Entry and existing playlist saved.':'Entry and playlist saved.';return}
 const ctrl=new AbortController();busy=ctrl;$('save').disabled=true;$('message').textContent='Entry saved. Finding your songs…';
 const timer=setTimeout(()=>ctrl.abort(),300000);
 const show=async(songs,terminal,reasonState)=>{
  if(!Array.isArray(songs)||songs.length!==3||songs.some(s=>typeof s?.title!=='string'||typeof s?.artist!=='string'))throw Error();
  if(busy!==ctrl||dirty||active!==day||ctrl.signal.aborted)return;
  r.source='model';r.songs=songs.map(({title,artist,reason})=>({title,artist,...(typeof reason==='string'?{reason}:{})}));
  if(await write(day,r)){viewSongs(r);$('message').textContent=!terminal?'Songs found. Writing the reasons…':
   ['disabled','limit','unavailable','insufficient'].includes(reasonState)?'Tracks saved. Reasons are unavailable this time.':'Entry and songs saved.'}
 };
 const post=async(path,body)=>{const v=await fetch(api+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:ctrl.signal});
  if(!v.ok)throw Error(String(v.status));return v.json()};
 try{
  if(legacy){await show((await post('/recommend',{diary:text})).songs,true);return}
  const job=await post('/jobs',{diary:text,explain:!!provider&&$('explain').checked});
  for(;;){
   const v=await fetch(api+'/jobs/'+encodeURIComponent(job.job_id),{headers:{Authorization:'Bearer '+job.access_token},cache:'no-store',signal:ctrl.signal});
   if(!v.ok)throw Error(String(v.status));const data=await v.json();
   if(busy!==ctrl||dirty||active!==day||ctrl.signal.aborted)return;
   if(data.status==='succeeded'){await show(data.songs,true,data.explanation_status);break}
   if(data.status==='explaining'){await show(data.songs,false)}
   else if(data.status==='queued'||data.status==='running'){$('message').textContent=data.status==='queued'?'Entry saved. Waiting for recommendations…':'Comparing your entry with lyrics…'}
   else throw Error();
   await new Promise(ok=>setTimeout(ok,1000));
  }
 }
 catch(e){if(busy===ctrl&&!dirty&&active===day)$('message').textContent=r.source==='random'?'Entry saved. Showing sample tracks this time.':'Showing your saved playlist. The new request did not finish.'}
 finally{clearTimeout(timer);if(busy===ctrl){busy=null;$('save').disabled=false}}
};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
window.addEventListener('storage',e=>{if(!active && (!e.key||e.key.startsWith(prefix)))calendar()});
$('save').disabled=true;calendar();
(async()=>{try{const r=await fetch('./config.json',{cache:'no-store'});if(r.ok){const c=await r.json();api=typeof c.apiOrigin==='string'?c.apiOrigin:'';llmMode=c.mode?c.mode==='llm':!api}}catch{}
 if(llmMode){
  try{const r=await fetch('/api/recommend',{cache:'no-store',signal:AbortSignal.timeout(8000)});if(r.ok){const c=await r.json();llmConfigured=c.configured===true;provider=c.provider;llmMessage=c.message||'';llmTimingKey=typeof c.timing_key==='string'?c.timing_key:''}}catch{}
 }else if(api){try{const r=await fetch(api+'/healthz',{signal:AbortSignal.timeout(8000)});if(r.ok){const h=await r.json();legacy=h.jobs!==true;provider=h.explanation_provider||null;if(provider){$('reasonProvider').textContent=provider;$('reasonOption').hidden=false}}}catch{}}ready=true;$('save').disabled=false;note()})();
