'use strict';
const el=id=>document.getElementById(id);
let rows=[],origin='',mode='sample',method='rerank',job=null;
const get=async file=>{const r=await fetch(file);if(!r.ok)throw Error();return r.json()};
function tracks(songs){
 el('tracks').replaceChildren(...songs.map(s=>{
  const li=document.createElement('li'),d=document.createElement('div'),title=document.createElement('b'),sub=document.createElement('span');
  title.textContent=s.title;sub.textContent=s.artist+' · Search rank #'+s.searchRank+''+(s.grade!=null?' · Reviewer score '+s.grade+'/3':'');
  d.append(title,sub);li.append(d);return li;
 }));
}
function render(){
 for(const id of ['live','sample','search','rerank'])el(id).setAttribute('aria-pressed',String(id===mode||id===method));
 const sample=mode==='sample';el('samples').hidden=!sample;el('entry').hidden=sample;el('methods').hidden=!sample;
 el('title').textContent='Recommended tracks';tracks([]);
 if(sample){const r=rows[Number(el('cases').value)||0];if(!r)return;
 el('status').textContent=r.id+' · '+r.theme+' · Archived run';tracks(r[method]);}
 else {el('submit').disabled=!origin;el('diary').disabled=!origin;
 el('hint').textContent=origin?'Your entry will be sent to the research model server.':'Browse the examples. Live research is available when the model server is connected.';
 el('status').textContent='Results for your entry will appear here.';}
}
for(const id of ['sample','live'])el(id).onclick=()=>{job?.abort();mode=id;render()};
for(const id of ['search','rerank'])el(id).onclick=()=>{method=id;render()};
el('cases').onchange=render;
el('entry').onsubmit=async event=>{
 event.preventDefault();const diary=el('diary').value.trim();if(!origin||!diary||job)return;
 const ctrl=new AbortController();job=ctrl;const timer=setTimeout(()=>ctrl.abort(),120000);
 el('submit').disabled=true;tracks([]);el('status').textContent='Finding lyric matches and comparing 30 candidates…';
 try{const r=await fetch(origin+'/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({diary}),signal:ctrl.signal});
 if(!r.ok)throw Error(r.status===429?'Another entry is being processed. Try again shortly.':'Could not reach the research model.');
 const data=await r.json();if(!Array.isArray(data.songs)||data.songs.length!==3)throw Error('Could not read the model response.');
 if(mode==='live'&&!ctrl.signal.aborted){tracks(data.songs);el('status').textContent='Your entry · Live results';}}
 catch(e){if(mode==='live')el('status').textContent=ctrl.signal.aborted?'Request stopped. You can try again.':e.message;}
 finally{clearTimeout(timer);job=null;if(mode==='live')el('submit').disabled=!origin;}
};
(async()=>{try{const [cases,cfg]=await Promise.all([get('./cases.json'),get('./config.json')]);rows=cases;origin=cfg.apiOrigin;
 rows.forEach((r,i)=>el('cases').add(new Option(r.theme,String(i))));el('cases').value=String(rows.findIndex(r=>r.id==='AIREF_030'));render();}
 catch{el('status').textContent='Could not load the examples. Please refresh.';}})();
