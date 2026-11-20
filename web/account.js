(async function(){
 const el=id=>document.getElementById(id), dlg=el('accountDialog'),main=el('main'),status=el('accountStatus');
 let uid=null, authReady=false;
 const entries=new Map(), help=el('accountHelp'),account=el('account');
 async function call(action,body){
 const r=await fetch('/api/account/'+action,{method:body?'POST':'GET',cache:'no-store',signal:['session','start'].includes(action)?AbortSignal.timeout(10000):undefined,headers:{'Content-Type':'application/json','X-Feelody-Account':uid||''},body:body?JSON.stringify(body):undefined});
 if(r.status===401){entries.clear();main.hidden=true;dirty=false;location.reload()}if(!r.ok)throw Object.assign(Error(),{status:r.status});return r.json()}
 window.journalAccount={get user(){return uid},entries,
 async save(day,entry){await call('save',{day,entry});entries.set(day,entry)},
 async remove(day){await call('remove',{day});entries.delete(day)}
 };
 async function fetchEntries(){const fresh=new Map();let last;
 for(;;){const rows=await call('entries',{last});for(const r of rows)fresh.set(r.day,r.entry);if(rows.length<100)break;last=rows.at(-1).day}
 entries.clear();for(const [k,v] of fresh)entries.set(k,v);calendar()}
 const close=()=>dlg.close();el('closeAccount').onclick=el('guestContinue').onclick=close;
 dlg.onclick=e=>{if(e.target===dlg){const r=dlg.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close()}};
 account.onclick=()=>dlg.showModal();
 const providerButtons=[...dlg.querySelectorAll('[data-provider]')];
 const enable=v=>providerButtons.forEach(b=>b.disabled=!v);
 let starting=false;main.inert=true;
 for(const b of providerButtons)b.onclick=async()=>{if(starting)return;if(dirty&&!confirm('저장하지 않은 수정 내용을 닫고 로그인할까요?'))return;
 starting=true;enable(false);status.textContent='로그인 화면을 여는 중이에요…';try{const next=new URL(location.href);if(active)next.searchParams.set('day',active);next.searchParams.delete('login');const result=await call('start',{provider:b.dataset.provider,next:next.pathname+next.search+next.hash});if(typeof result.url!=='string')throw Error();dirty=false;location.assign(result.url)}catch(e){starting=false;status.textContent=e.status===503?'로그인 서버를 사용할 수 없어요. 잠시 후 다시 눌러 주세요.':e.status===404||e instanceof SyntaxError?'로그인 API를 찾지 못했어요. 사이트 배포 상태를 확인해 주세요.':'연결하지 못했어요. 로그인 버튼을 다시 눌러 주세요.';enable(true)}};
 el('logout').onclick=async()=>{if(dirty&&!confirm('저장하지 않은 내용을 닫고 로그아웃할까요?'))return;try{await call('logout',{});dirty=false;location.replace(location.pathname)}catch{status.textContent='로그아웃하지 못했어요. 다시 시도해 주세요.'}};
 el('importGuest').onclick=async e=>{if(!uid||!confirm('이 기기의 비회원 일기를 내 계정에 복사할까요? 같은 날짜의 계정 기록은 유지되며 원본은 이 기기에 남아요.'))return;
 const btn=e.currentTarget;btn.disabled=true;try{const rows=[];for(const k of Object.keys(localStorage)){if(!k.startsWith(prefix))continue;
 const day=k.slice(prefix.length);if(!/^\d{4}-\d{2}-\d{2}$/.test(day))continue;const entry=JSON.parse(localStorage.getItem(k));if(typeof entry?.text==='string'&&hasMood(entry.mood))rows.push({day,entry,user_id:uid})}
 for(let i=0;i<rows.length;i+=50)await call('import',{rows:rows.slice(i,i+50)});
 await fetchEntries();status.textContent=rows.length?'가져왔어요. 기존 계정 기록은 그대로예요.':'가져올 비회원 기록이 없어요.'}catch{status.textContent='가져오기를 완료하지 못했어요. 다시 시도해 주세요.'}finally{btn.disabled=false}};
 try{const session=await call('session');if(!session.configured){if(!starting)status.textContent='계정 연결을 준비하고 있어요. 지금은 로그인 없이 이용할 수 있어요.';return}
 uid=session.user;
 window.addEventListener('pageshow',e=>{if(e.persisted)location.reload()});
 window.addEventListener('focus',async()=>{try{if((await call('session')).user!==uid){entries.clear();main.hidden=true;dirty=false;location.reload()}}catch{}});
 if(uid){account.classList.add('signed-in');account.setAttribute('aria-label','내 계정 열기');account.title='내 계정';account.replaceChildren();
 if(session.avatarUrl){const img=document.createElement('img');img.alt='';img.referrerPolicy='no-referrer';img.onerror=()=>img.remove();img.src=session.avatarUrl;account.append(img)}
 el('accountTitle').textContent='내 마음 기록';help.textContent='일기와 추천곡을 이 계정에 보관해요.';
 el('providers').hidden=true;el('memberActions').hidden=false;el('guestContinue').textContent='달력으로';await fetchEntries()}
 authReady=true;
 const current=new URL(location.href),day=current.searchParams.get('day');
 if(/^\d{4}-\d{2}-\d{2}$/.test(day||'')){month=new Date(day+'T12:00:00');month.setDate(1);openDay(day)}
 if(current.searchParams.get('login')==='failed'){status.textContent='로그인을 완료하지 못했어요. 다시 시도하거나 비회원으로 계속 이용하세요.';dlg.showModal();current.searchParams.delete('login');history.replaceState(null,'',current)}
 }catch{status.textContent='계정 연결을 확인하지 못했어요. 잠시 후 새로고침해 주세요.';if(uid)dlg.showModal()}
 finally{main.inert=!!uid&&!authReady}
})();
