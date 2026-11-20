(async function(){
 const el=id=>document.getElementById(id), dlg=el('accountDialog'),main=el('main'),status=el('accountStatus');
 let client, uid=null, authReady=false;
 const entries=new Map(), help=el('accountHelp'),account=el('account');
 const check=r=>{if(r.error)throw r.error;return r.data};
 const state=window.journalAccount={get user(){return uid},entries,
 async save(day,v){const id=uid;check(await client.from('diary_entries').upsert({user_id:id,day,entry:v}));if(id!==uid)throw Error();entries.set(day,v)},
 async remove(day){const id=uid;check(await client.from('diary_entries').delete().eq('user_id',id).eq('day',day));entries.delete(day)}
 };
 async function fetchEntries(){const fresh=new Map();let last;
 for(;;){let q=client.from('diary_entries').select('day,entry').eq('user_id',uid).order('day').limit(100);if(last)q=q.gt('day',last);
 const rows=check(await q);for(const r of rows)fresh.set(r.day,r.entry);if(!rows.length)break;last=rows.at(-1).day}
 entries.clear();for(const [k,v] of fresh)entries.set(k,v);calendar()}
 const close=()=>dlg.close();el('closeAccount').onclick=el('guestContinue').onclick=close;
 dlg.onclick=e=>{if(e.target===dlg){const r=dlg.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close()}};
 account.onclick=()=>dlg.showModal();
 const providerButtons=[...dlg.querySelectorAll('[data-provider]')];
 const enable=v=>providerButtons.forEach(b=>b.disabled=!v);
 enable(false);main.inert=true;
 for(const b of providerButtons)b.onclick=async()=>{if(dirty&&!confirm('저장하지 않은 수정 내용을 닫고 로그인할까요?'))return;
 enable(false);try{check(await client.auth.signInWithOAuth({provider:b.dataset.provider,options:{redirectTo:location.origin+'/'}}))}catch{status.textContent='로그인을 시작하지 못했어요. 다시 시도해 주세요.';enable(true)}};
 el('logout').onclick=async()=>{if(dirty&&!confirm('저장하지 않은 내용을 닫고 로그아웃할까요?'))return;try{check(await client.auth.signOut({scope:'local'}));dirty=false;location.replace(location.pathname)}catch{status.textContent='로그아웃하지 못했어요. 다시 시도해 주세요.'}};
 el('importGuest').onclick=async e=>{if(!uid||!confirm('이 기기의 비회원 일기를 내 계정에 복사할까요? 같은 날짜의 계정 기록은 유지되며 원본은 이 기기에 남아요.'))return;
 const btn=e.currentTarget;btn.disabled=true;try{const rows=[];for(const k of Object.keys(localStorage)){if(!k.startsWith(prefix))continue;
 const day=k.slice(prefix.length);if(!/^\d{4}-\d{2}-\d{2}$/.test(day))continue;const entry=JSON.parse(localStorage.getItem(k));if(typeof entry?.text==='string'&&hasMood(entry.mood))rows.push({day,entry,user_id:uid})}
 for(let i=0;i<rows.length;i+=50)check(await client.from('diary_entries').upsert(rows.slice(i,i+50),{ignoreDuplicates:true,onConflict:'user_id,day'}));
 await fetchEntries();status.textContent=rows.length?'가져왔어요. 기존 계정 기록은 그대로예요.':'가져올 비회원 기록이 없어요.'}catch{status.textContent='가져오기를 완료하지 못했어요. 다시 시도해 주세요.'}finally{btn.disabled=false}};
 try{const cfg=await (await fetch('./config.json',{cache:'no-store'})).json();
 if(!cfg.supabaseUrl||!cfg.supabaseKey){status.textContent='계정 연결을 준비하고 있어요. 지금은 로그인 없이 이용할 수 있어요.';return}
 const {createClient}=await import('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.49.8/+esm');
 client=createClient(cfg.supabaseUrl,cfg.supabaseKey,{auth:{flowType:'pkce'}});
 const session=check(await client.auth.getSession()).session;uid=session?.user.id||null;
 client.auth.onAuthStateChange((_event,s)=>{if((s?.user.id||null)!==uid){entries.clear();busy?.abort();main.hidden=true;dirty=false;location.replace(location.pathname)}});
 if(uid){account.textContent='내 계정';el('accountTitle').textContent='내 마음 기록';help.textContent='일기와 추천곡을 이 계정에 보관해요.';
 el('providers').hidden=true;el('memberActions').hidden=false;el('guestContinue').textContent='달력으로';await fetchEntries()}
 authReady=true;enable(true)
 }catch{status.textContent='계정 연결을 확인하지 못했어요. 잠시 후 새로고침해 주세요.';if(uid)dlg.showModal()}
 finally{main.inert=!!uid&&!authReady}
})();
