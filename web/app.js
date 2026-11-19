'use strict';
const $=id=>document.getElementById(id),node=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e};
const pad=n=>String(n).padStart(2,'0'),key=(y,m,d)=>y+'-'+pad(m+1)+'-'+pad(d);
const today=()=>{const t=new Date();return key(t.getFullYear(),t.getMonth(),t.getDate())};
const prefix='feelody/journal/v1/', labels=Object.keys(MOODS),hasMood=m=>Object.hasOwn(MOODS,m);
let month=new Date();month.setDate(1);let active=null,picked=null,manual=false,dirty=false,api='',busy=null,ready=false,legacy=false,provider=null,llmMode=true,llmConfigured=false,llmMessage='',llmTimingKey='';
// Public sample catalog; random selection is not an emotion model result.
const RANDOM_TRACKS=[{"title":"내일이 오면 (Feat. 기리보이, BIG Naughty (서동현))","artist":"릴보이 (lIlBOI)"},{"title":"N분의1 (Feat. 다이나믹듀오)","artist":"넉살, 한해, RYNO (라이노), 조우찬"},{"title":"구해주오","artist":"CB Mass"},{"title":"Ordinary People","artist":"SG 워너비"},{"title":"정이라고 하자 (Feat. 10CM)","artist":"BIG Naughty (서동현)"},{"title":"CREDIT (Feat. 염따, 기리보이, Zion.T)","artist":"릴보이 (lIlBOI)"},{"title":"The Time Goes On","artist":"BewhY (비와이)"},{"title":"환희","artist":"싸이 (PSY)"},{"title":"겁 (Feat. 태양)","artist":"MINO (송민호)"},{"title":"좋아보여 (Feat. 검정치마)","artist":"버벌진트"},{"title":"회상 (Feat. 백지영)","artist":"리쌍"},{"title":"EASY","artist":"LE SSERAFIM (르세라핌)"},{"title":"그리고 그후","artist":"프리스타일"},{"title":"기다렸다 가","artist":"다이나믹 듀오, 첸 (CHEN)"},{"title":"친구","artist":"방탄소년단"},{"title":"One Love","artist":"원타임"},{"title":"슬피 우는 새 (Feat. 이수영)","artist":"아웃사이더"},{"title":"Wash Away (Feat. 에일리)","artist":"긱스 (Geeks)"},{"title":"바코드 (Prod. GroovyRoom)","artist":"김하온 (HAON), 빈첸"},{"title":"남자기 때문에","artist":"드렁큰 타이거"},{"title":"죽일 놈 (Guilty)","artist":"다이나믹 듀오"},{"title":"연애소설 (Feat. 아이유)","artist":"에픽하이 (EPIK HIGH)"},{"title":"빌었어","artist":"창모 (CHANGMO)"},{"title":"곰인형 (Feat. 해금)","artist":"린"},{"title":"내 생애 가장 행복한 시간 (Feat. 허각)","artist":"MC몽"},{"title":"당신의 밤 (Feat. 오혁)","artist":"황광희 X 개코"},{"title":"시간을 찾아서 (Feat. 이적)","artist":"김진표"},{"title":"너에게 닿기를","artist":"10CM"},{"title":"180˚ (Feat. 인태 & Supasize)","artist":"MC몽"},{"title":"마이동풍","artist":"배치기"},{"title":"우연 (우울한 우연)","artist":"베이비 복스"},{"title":"끝","artist":"싸이 (PSY)"},{"title":"그땐 그땐 그땐","artist":"Supreme Team, 영준"},{"title":"A Real Man","artist":"스윙스, 에일리(Ailee)"},{"title":"Forever (Prod. By GRAY)","artist":"BewhY (비와이)"},{"title":"UPT Paradoxxx","artist":"업타운"},{"title":"스물셋","artist":"아이유"},{"title":"Memories... (Smiling Tears)","artist":"윤미래"},{"title":"flex (Prod. By 기리보이)","artist":"기리보이, 키드밀리 (Kid Milli), NO:EL, 스윙스"},{"title":"Summer Hate (Feat. 비)","artist":"지코 (ZICO)"},{"title":"Hot Summer","artist":"f(x)"},{"title":"치맛바람 (Chi Mat Ba Ram)","artist":"브레이브걸스"},{"title":"땡땡땡","artist":"Supreme Team"}];
function randomSongs(){const pool=[...RANDOM_TRACKS];for(let i=pool.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]]}return pool.slice(0,3).map(s=>({...s}))}
function read(day){try{const v=JSON.parse(localStorage.getItem(prefix+day));return v&&typeof v.text==='string'&&hasMood(v.mood)?v:null}catch{return null}}
function write(day,v){try{localStorage.setItem(prefix+day,JSON.stringify(v));return true}catch{$('message').textContent='브라우저에 저장할 수 없어요. 일기를 복사해 보관하거나 저장 공간을 확인해 주세요.';return false}}
function face(m){const i=node('i','face '+m);i.style.setProperty('--c',MOODS[m].color);i.setAttribute('aria-hidden','true');return i}
function disc(){const i=node('div','disc');i.setAttribute('aria-hidden','true');return i}
function calendar(){
 const y=month.getFullYear(),m=month.getMonth(),start=new Date(y,m,1).getDay(),days=new Date(y,m+1,0).getDate();
 $('month').replaceChildren(node('span','',String(y)+' / '),document.createTextNode((m+1)+'월'));const grid=$('grid');grid.replaceChildren();let n=0;
 for(let i=0;i<start;i++)grid.append(node('span'));
 for(let d=1;d<=days;d++){
  const k=key(y,m,d),r=read(k),b=node('button','date'+(k===today()?' today':'')+(r?' filled':''));
  b.type='button';b.dataset.day=k;b.setAttribute('aria-label',k+(r?' '+MOODS[r.mood].name+' 기록':' 일기 쓰기'));if(k===today())b.setAttribute('aria-current','date');
  if(r){n++;b.append(face(r.mood))}b.append(node('span','number',d));b.onclick=()=>openDay(k);grid.append(b)
 }
 $('count').textContent='●　이달의 기록 '+n+'일';$('sideNote').textContent=read(today())?'오늘 남긴 마음과 세 곡을 다시 만나보세요.':'한 줄의 일기에서 시작하는 작은 플레이리스트.';
}
function choose(m,isManual){
 picked=m;manual=isManual;for(const b of $('moods').children)b.setAttribute('aria-pressed',String(b.dataset.m===picked));
 $('suggestion').textContent=manual?'선택한 기분':picked?'일기 표현에서 제안했어요. 바꿔도 좋아요.':'가장 가까운 기분을 골라 주세요.';
}
function viewSongs(r){
 $('otherSongs').hidden=!(llmMode&&r?.source==='llm'&&Array.isArray(r.songs)&&r.songs.length===3);

 const hasReflection=r?.source==='llm'&&typeof r.summary==='string'&&typeof r.empathy==='string';
 $('reflection').hidden=!hasReflection;
 $('summary').textContent=hasReflection?r.summary:'';
 $('empathy').textContent=hasReflection?r.empathy:'';

 const ok=r&&['model','random','llm'].includes(r.source)&&Array.isArray(r.songs)&&r.songs.length===3;$('music').hidden=!ok;$('cards').replaceChildren();if(!ok)return;
 $('source').textContent=r.source==='llm'?'AI가 일기를 읽고 고른 세 곡 · 곡명과 이유는 부정확할 수 있어요':r.source==='random'?'오늘의 추천곡':'일기와 가사를 비교한 모델 추천';
  if(r.source==='llm'&&r.generated_at&&!Number.isNaN(Date.parse(r.generated_at))){
  $('source').textContent+=' · '+new Date(r.generated_at).toLocaleTimeString('ko-KR')+' 생성';
 }
 for(const [i,s] of r.songs.entries()){
  const a=node('a','track'),u=new URL('https://www.youtube.com/results');u.searchParams.set('search_query',s.artist+' '+s.title+' 공식 음악');
  try{const provided=new URL(s.youtube_url);if(provided.origin==='https://www.youtube.com'&&provided.pathname==='/results'&&provided.searchParams.get('search_query')===u.searchParams.get('search_query'))a.href=provided.href;else a.href=u.href}catch{a.href=u.href}a.target='_blank';a.rel='noopener noreferrer';a.setAttribute('aria-label',s.artist+' '+s.title+' YouTube 검색, 새 탭');
  a.append(disc(),node('small','','TRACK 0'+(i+1)),node('b','',s.title),node('span','',s.artist),node('u','','YouTube에서 찾기 ↗'));if(s.reason)a.append(node('p','reason','AI가 읽은 감정 · '+s.reason));$('cards').append(a);
 }
}
function note(){
 $('save').textContent=llmMode?'저장하고 AI 추천받기 ↗':'저장하고 세 곡 추천받기 ↗';
 if(active)$('modeNote').textContent=!ready?'추천 설정 확인 중…':llmMode?
  (llmConfigured?'AI 추천을 누르면 일기와 선택한 기분이 '+(provider==='gemini'?'Google Gemini':'OpenAI')+'에 전달돼요. 요약과 공감, 세 곡의 추천 이유를 함께 받아요.':llmMessage||'AI 추천 설정을 확인하지 못했어요. 일기는 저장할 수 있어요.'):
  api?'저장하면 입력한 일기를 모델 서버로 보내 세 곡을 찾습니다.':'현재는 일기 분석 없이 등록된 곡 목록에서 세 곡을 골라드려요.';
}
function openDay(day){
 active=day;dirty=false;$('explain').checked=false;const r=read(day),[y,m,d]=day.split('-').map(Number);$('home').hidden=true;$('editor').hidden=false;
 $('dayTitle').textContent=m+'월 '+d+'일 '+['일','월','화','수','목','금','토'][new Date(y,m-1,d).getDay()]+'요일';$('diary').value=r?.text||'';$('message').textContent='';choose(r?.mood||null,!!r);$('remove').hidden=!r;if(!llmMode&&r?.text&&(!Array.isArray(r.songs)||r.songs.length!==3)){r.source='random';r.songs=randomSongs();write(day,r)}viewSongs(r);note();$('dayTitle').focus();
}
function home(){if(dirty&&!window.confirm('저장하지 않은 수정 내용을 닫을까요?'))return;busy?.abort();busy=null;$('save').disabled=!ready;dirty=false;const old=active;active=null;$('home').hidden=false;$('editor').hidden=true;calendar();$('grid').querySelector('[data-day="'+old+'"]')?.focus()}
$('back').onclick=home;$('prev').onclick=()=>{month.setMonth(month.getMonth()-1);calendar()};$('next').onclick=()=>{month.setMonth(month.getMonth()+1);calendar()};$('now').onclick=()=>{month=new Date();month.setDate(1);calendar()};$('write').onclick=()=>{month=new Date();month.setDate(1);openDay(today())};
for(const w of ['일','월','화','수','목','금','토'])$('week').append(node('span','',w));
$('cover').append(disc());
function edited(){dirty=true;busy?.abort();$('message').textContent='';viewSongs(null)}
for(const m of labels){
 const it=node('span');it.append(face(m),document.createTextNode(MOODS[m].name));$('legend').append(it);
 const b=node('button','choice');b.dataset.m=m;b.append(face(m),document.createTextNode(MOODS[m].name));b.onclick=()=>{edited();choose(m,true)};$('moods').append(b)
}
$('diary').oninput=()=>{edited();if(!manual){
 const t=$('diary').value;let idx=-1,guess=null;for(const m of labels){for(const match of t.matchAll(new RegExp(MOODS[m].hint.source,'g'))){if(match.index>idx){idx=match.index;guess=m}}}choose(guess,false);}
};
$('remove').onclick=()=>{if(!window.confirm('이 날짜의 일기와 플레이리스트를 삭제할까요?'))return;
 try{localStorage.removeItem(prefix+active)}catch{$('message').textContent='기록을 삭제하지 못했습니다.';return}dirty=false;home()};
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
 $('waitHistory').textContent=samples.length===0?'완료되면 요약과 세 곡을 함께 보여드려요.':
  samples.length===1?'이전 추천은 약 '+samples[0]+'초 걸렸어요. 이번에는 달라질 수 있어요.':
  '최근 '+samples.length+'회는 '+Math.min(...samples)+'~'+Math.max(...samples)+'초 걸렸어요. 이번에는 달라질 수 있어요.';
 const tick=()=>{if(busy!==ctrl||active!==day||ctrl.signal.aborted)return;
  $('waitElapsed').textContent=Math.floor(elapsed())+'초 경과';
  $('waitTitle').textContent=elapsed()>=30?'응답이 조금 늦어지고 있어요':'AI의 답장을 기다리고 있어요';
 };
 tick();
 const interval=setInterval(tick,1000);
 const stop=()=>{clearInterval(interval);if(busy===ctrl)panel.hidden=true;ctrl.signal.removeEventListener('abort',stop)};
 ctrl.signal.addEventListener('abort',stop,{once:true});
 return {stop,elapsed};
}
async function saveWithLLM(day,text,mood,excluded=[]){
 // A failed new request must not look like another successful copy of an old response.
 const r={text,mood,source:'none',songs:[]};
 if(!write(day,r))return;
 dirty=false;$('remove').hidden=false;viewSongs(r);
 const ctrl=new AbortController();busy=ctrl;$('save').disabled=true;
 const waiting=startWait(ctrl,day);
 $('message').textContent='일기를 저장했어요. AI가 마음을 읽고 세 곡을 고르고 있어요…';
 const timer=setTimeout(()=>ctrl.abort(),55000);
 try{
  const resp=await fetch('/api/recommend',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({diary:text,mood,excluded_songs:excluded}),signal:ctrl.signal});
  const data=await resp.json();
  if(!resp.ok)throw Error(typeof data.message==='string'?data.message:'AI 추천을 받지 못했어요.');
  if(data.source!=='llm'||typeof data.summary!=='string'||typeof data.empathy!=='string'||
   !Array.isArray(data.songs)||data.songs.length!==3||data.songs.some(s=>['title','artist','reason'].some(k=>typeof s?.[k]!=='string')))throw Error('AI 응답을 확인하지 못했어요.');
  if(busy!==ctrl||dirty||active!==day||ctrl.signal.aborted)return;
  rememberWait(data.timing_key||llmTimingKey,waiting.elapsed());
  Object.assign(r,{source:'llm',summary:data.summary,empathy:data.empathy,
   request_id:data.request_id,generated_at:data.generated_at,
   songs:data.songs.map(({title,artist,reason,youtube_url})=>({title,artist,reason,youtube_url}))});
  if(write(day,r)){viewSongs(r);$('message').textContent='일기와 AI의 답장, 추천곡을 저장했어요. · '+waiting.elapsed().toFixed(1)+'초 소요'}
 }catch(e){if(busy===ctrl&&!dirty&&active===day)$('message').textContent='일기는 저장됐어요. '+(e.name==='AbortError'?'응답이 늦어져 중단했어요. 잠시 후 다시 시도해 주세요.':e.message)}
 finally{waiting.stop();clearTimeout(timer);if(busy===ctrl){busy=null;$('save').disabled=false}}
}
$('otherSongs').onclick=async()=>{
 const r=read(active),text=$('diary').value.trim();
 if(busy||!llmMode||!r||r.source!=='llm'||r.text!==text||dirty)return;
 await saveWithLLM(active,text,picked,r.songs.map(({title,artist})=>({title,artist})));
};
$('save').onclick=async()=>{
 const day=active,text=$('diary').value.trim(),m=picked;if(!day||busy||!ready)return;
 if(!text){$('message').textContent='일기를 한 줄 이상 적어 주세요.';$('diary').focus();return}
 if(!m){$('message').textContent='달력에 남길 기분을 골라 주세요.';$('moods').firstChild.focus();return}
 if(llmMode){await saveWithLLM(day,text,m);return}
 const r={text,mood:m,source:'random',songs:randomSongs()};
 const old=read(day);if(old?.source==='model'&&old.text===text&&Array.isArray(old.songs)&&old.songs.length===3){r.source='model';r.songs=old.songs}
 if(!write(day,r))return;dirty=false;$('remove').hidden=false;viewSongs(r);
 if(!api){$('message').textContent=r.source==='model'?'일기와 기존 모델 추천 세 곡을 저장했어요.':'일기와 추천곡 세 곡을 저장했어요.';return}
 const ctrl=new AbortController();busy=ctrl;$('save').disabled=true;$('message').textContent='일기를 저장했어요. 어울리는 세 곡을 찾고 있어요…';
 const timer=setTimeout(()=>ctrl.abort(),300000);
 const show=(songs,terminal,reasonState)=>{
  if(!Array.isArray(songs)||songs.length!==3||songs.some(s=>typeof s?.title!=='string'||typeof s?.artist!=='string'))throw Error();
  if(busy!==ctrl||dirty||active!==day||ctrl.signal.aborted)return;
  r.source='model';r.songs=songs.map(({title,artist,reason})=>({title,artist,...(typeof reason==='string'?{reason}:{})}));
  if(write(day,r)){viewSongs(r);$('message').textContent=!terminal?'세 곡을 찾았어요. 추천 이유를 작성하고 있어요…':
   ['disabled','limit','unavailable','insufficient'].includes(reasonState)?'세 곡을 저장했어요. 이번에는 추천 이유를 제공할 수 없어요.':'일기와 세 곡을 저장했어요.'}
 };
 const post=async(path,body)=>{const v=await fetch(api+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:ctrl.signal});
  if(!v.ok)throw Error(String(v.status));return v.json()};
 try{
  if(legacy){show((await post('/recommend',{diary:text})).songs,true);return}
  const job=await post('/jobs',{diary:text,explain:!!provider&&$('explain').checked});
  for(;;){
   const v=await fetch(api+'/jobs/'+encodeURIComponent(job.job_id),{headers:{Authorization:'Bearer '+job.access_token},cache:'no-store',signal:ctrl.signal});
   if(!v.ok)throw Error(String(v.status));const data=await v.json();
   if(busy!==ctrl||dirty||active!==day||ctrl.signal.aborted)return;
   if(data.status==='succeeded'){show(data.songs,true,data.explanation_status);break}
   if(data.status==='explaining'){show(data.songs,false)}
   else if(data.status==='queued'||data.status==='running'){$('message').textContent=data.status==='queued'?'일기를 저장했어요. 추천 순서를 기다리고 있어요…':'일기와 가사를 비교하고 있어요…'}
   else throw Error();
   await new Promise(ok=>setTimeout(ok,1000));
  }
 }
 catch(e){if(busy===ctrl&&!dirty&&active===day)$('message').textContent=r.source==='random'?'일기는 저장됐어요. 이번에는 등록된 목록에서 고른 추천곡을 보여드려요.':'저장된 모델 추천 세 곡을 표시했어요. 새 요청의 완료를 확인하지 못했어요.'}
 finally{clearTimeout(timer);if(busy===ctrl){busy=null;$('save').disabled=false}}
};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
window.addEventListener('storage',e=>{if(!active && (!e.key||e.key.startsWith(prefix)))calendar()});
$('save').disabled=true;calendar();
(async()=>{try{const r=await fetch('./config.json',{cache:'no-store'});if(r.ok){const c=await r.json();api=typeof c.apiOrigin==='string'?c.apiOrigin:'';llmMode=c.mode?c.mode==='llm':!api}}catch{}
 if(llmMode){
  try{const r=await fetch('/api/recommend',{cache:'no-store',signal:AbortSignal.timeout(8000)});if(r.ok){const c=await r.json();llmConfigured=c.configured===true;provider=c.provider;llmMessage=c.message||'';llmTimingKey=typeof c.timing_key==='string'?c.timing_key:''}}catch{}
 }else if(api){try{const r=await fetch(api+'/healthz',{signal:AbortSignal.timeout(8000)});if(r.ok){const h=await r.json();legacy=h.jobs!==true;provider=h.explanation_provider||null;if(provider){$('reasonProvider').textContent=provider;$('reasonOption').hidden=false}}}catch{}}ready=true;$('save').disabled=false;note()})();
