'use strict';
const el=id=>document.getElementById(id);
let rows=[],origin='',mode='sample',method='rerank',job=null;
const get=async file=>{const r=await fetch(file);if(!r.ok)throw Error();return r.json()};
function tracks(songs){
 el('tracks').replaceChildren(...songs.map(s=>{
  const li=document.createElement('li'),d=document.createElement('div'),title=document.createElement('b'),sub=document.createElement('span');
  title.textContent=s.title;sub.textContent=s.artist+' · 검색 '+s.searchRank+'위'+(s.grade!=null?' · 사람 평가 '+s.grade+'/3':'');
  d.append(title,sub);li.append(d);return li;
 }));
}
function render(){
 for(const id of ['live','sample','search','rerank'])el(id).setAttribute('aria-pressed',String(id===mode||id===method));
 const sample=mode==='sample';el('samples').hidden=!sample;el('entry').hidden=sample;el('methods').hidden=!sample;
 el('title').textContent='추천 플레이리스트';tracks([]);
 if(sample){const r=rows[Number(el('cases').value)||0];if(!r)return;
 el('status').textContent=r.id+' · '+r.theme+' · 저장된 실험 결과';tracks(r[method]);}
 else {el('submit').disabled=!origin;el('diary').disabled=!origin;
 el('hint').textContent=origin?'추천을 누르면 입력한 일기가 연결된 모델 서버로 전송됩니다.':'현재는 예시를 볼 수 있습니다. 새 일기 추천은 모델 서버가 연결되면 열립니다.';
 el('status').textContent='새 일기의 추천 결과가 여기에 표시됩니다.';}
}
for(const id of ['sample','live'])el(id).onclick=()=>{job?.abort();mode=id;render()};
for(const id of ['search','rerank'])el(id).onclick=()=>{method=id;render()};
el('cases').onchange=render;
el('entry').onsubmit=async event=>{
 event.preventDefault();const diary=el('diary').value.trim();if(!origin||!diary||job)return;
 const ctrl=new AbortController();job=ctrl;const timer=setTimeout(()=>ctrl.abort(),120000);
 el('submit').disabled=true;tracks([]);el('status').textContent='가사 후보를 찾고 30곡을 다시 비교하고 있습니다…';
 try{const r=await fetch(origin+'/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({diary}),signal:ctrl.signal});
 if(!r.ok)throw Error(r.status===429?'다른 일기를 처리 중입니다. 잠시 후 다시 시도해 주세요.':'모델 서버에서 추천을 받지 못했습니다.');
 const data=await r.json();if(!Array.isArray(data.songs)||data.songs.length!==3)throw Error('서버 응답을 확인해 주세요.');
 if(mode==='live'&&!ctrl.signal.aborted){tracks(data.songs);el('status').textContent='내 일기 · 실시간 추천';}}
 catch(e){if(mode==='live')el('status').textContent=ctrl.signal.aborted?'요청이 중단되었습니다. 다시 시도할 수 있습니다.':e.message;}
 finally{clearTimeout(timer);job=null;if(mode==='live')el('submit').disabled=!origin;}
};
(async()=>{try{const [cases,cfg]=await Promise.all([get('./cases.json'),get('./config.json')]);rows=cases;origin=cfg.apiOrigin;
 rows.forEach((r,i)=>el('cases').add(new Option(r.theme,String(i))));el('cases').value=String(rows.findIndex(r=>r.id==='AIREF_030'));render();}
 catch{el('status').textContent='예시 데이터를 불러오지 못했습니다. 페이지를 새로고침해 주세요.';}})();
