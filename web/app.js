'use strict';
const $=id=>document.getElementById(id),node=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e};
const pad=n=>String(n).padStart(2,'0'),key=(y,m,d)=>y+'-'+pad(m+1)+'-'+pad(d);
const today=()=>{const t=new Date();return key(t.getFullYear(),t.getMonth(),t.getDate())};
const prefix='feelody/journal/v1/', labels=Object.keys(MOODS),hasMood=m=>Object.hasOwn(MOODS,m);
let month=new Date();month.setDate(1);let active=null,picked=null,manual=false,dirty=false,api='',busy=null,ready=false,legacy=false,provider=null;
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
 const ok=r&&r.source==='model'&&Array.isArray(r.songs)&&r.songs.length===3;$('music').hidden=!ok;$('cards').replaceChildren();if(!ok)return;
 $('source').textContent='일기와 가사를 비교한 모델 추천';
 for(const [i,s] of r.songs.entries()){
  const a=node('a','track'),u=new URL('https://www.youtube.com/results');u.searchParams.set('search_query',s.artist+' '+s.title+' 공식 음악');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.setAttribute('aria-label',s.artist+' '+s.title+' YouTube 검색, 새 탭');
  a.append(disc(),node('small','','TRACK 0'+(i+1)),node('b','',s.title),node('span','',s.artist),node('u','','YouTube에서 찾기 ↗'));if(s.reason)a.append(node('p','reason','AI가 읽은 감정 · '+s.reason));$('cards').append(a);
 }
}
function note(){$('save').textContent=api?'저장하고 세 곡 추천받기 ↗':'일기 저장';if(active)$('modeNote').textContent=!ready?'추천 설정 확인 중…':api?'저장하면 입력한 일기를 모델 서버로 보내 세 곡을 찾습니다.':'모델 서버가 연결되지 않아 지금은 일기만 저장할 수 있어요.'}
function openDay(day){
 active=day;dirty=false;$('explain').checked=false;const r=read(day),[y,m,d]=day.split('-').map(Number);$('home').hidden=true;$('editor').hidden=false;
 $('dayTitle').textContent=m+'월 '+d+'일 '+['일','월','화','수','목','금','토'][new Date(y,m-1,d).getDay()]+'요일';$('diary').value=r?.text||'';$('message').textContent='';choose(r?.mood||null,!!r);$('remove').hidden=!r;viewSongs(r);note();$('dayTitle').focus();
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
$('save').onclick=async()=>{
 const day=active,text=$('diary').value.trim(),m=picked;if(!day||busy||!ready)return;
 if(!text){$('message').textContent='일기를 한 줄 이상 적어 주세요.';$('diary').focus();return}
 if(!m){$('message').textContent='달력에 남길 기분을 골라 주세요.';$('moods').firstChild.focus();return}
 const r={text,mood:m,source:api?'model':'none',songs:[]};
 const old=read(day);if(old?.source==='model'&&old.text===text&&Array.isArray(old.songs)&&old.songs.length===3){r.source='model';r.songs=old.songs}
 if(!write(day,r))return;dirty=false;$('remove').hidden=false;viewSongs(r);
 if(!api){$('message').textContent='일기를 저장했어요. 새 모델 추천은 생성되지 않았습니다.';return}
 const ctrl=new AbortController();busy=ctrl;$('save').disabled=true;$('message').textContent='일기를 저장했어요. 어울리는 세 곡을 찾고 있어요…';
 const timer=setTimeout(()=>ctrl.abort(),300000);
 const show=(songs,terminal,reasonState)=>{
  if(!Array.isArray(songs)||songs.length!==3||songs.some(s=>typeof s?.title!=='string'||typeof s?.artist!=='string'))throw Error();
  if(busy!==ctrl||dirty||active!==day||ctrl.signal.aborted)return;
  r.songs=songs.map(({title,artist,reason})=>({title,artist,...(typeof reason==='string'?{reason}:{})}));
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
 catch(e){if(busy===ctrl&&!dirty&&active===day)$('message').textContent=e.message==='429'?'일기는 저장됐어요. 대기열이 가득해 잠시 후 다시 시도해 주세요.':r.songs.length===3?'저장된 세 곡을 표시했어요. 새 요청의 완료를 확인하지 못했어요.':'일기는 저장됐어요. 추천을 받지 못했으니 다시 시도해 주세요.'}
 finally{clearTimeout(timer);if(busy===ctrl){busy=null;$('save').disabled=false}}
};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
window.addEventListener('storage',e=>{if(!active && (!e.key||e.key.startsWith(prefix)))calendar()});
$('save').disabled=true;calendar();
(async()=>{try{const r=await fetch('./config.json');if(r.ok){const c=await r.json();api=typeof c.apiOrigin==='string'?c.apiOrigin:''}}catch{}
 if(api){try{const r=await fetch(api+'/healthz',{signal:AbortSignal.timeout(8000)});if(r.ok){const h=await r.json();legacy=h.jobs!==true;provider=h.explanation_provider||null;if(provider){$('reasonProvider').textContent=provider;$('reasonOption').hidden=false}}}catch{}}ready=true;$('save').disabled=false;note()})();
