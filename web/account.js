(async function(){
 const el=id=>document.getElementById(id), dlg=el('accountDialog'),main=el('main'),status=el('accountStatus');
 let uid=null, authReady=false, ai=false;
 const entries=new Map(), help=el('accountHelp'),account=el('account');
 async function call(action,body){
 const r=await fetch('/api/account/'+action,{method:body?'POST':'GET',cache:'no-store',signal:['session','start'].includes(action)?AbortSignal.timeout(10000):undefined,headers:{'Content-Type':'application/json','X-Feelody-Account':uid||''},body:body?JSON.stringify(body):undefined});
 if(r.status===401){entries.clear();main.hidden=true;dirty=false;location.reload()}if(!r.ok){const error=action==='withdraw'?await r.json().catch(()=>({})):{};throw Object.assign(Error(),{status:r.status,code:error.code})}return r.json()}
 window.journalAccount={get user(){return uid},get allowsAI(){if(uid)return ai;if(!authReady)return false;try{return localStorage.getItem('feelody:guestAI:v1')==='yes'}catch{return false}},entries,
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
 for(const b of providerButtons)b.onclick=async()=>{if(starting)return;if(dirty&&!confirm('Discard unsaved changes and sign in?'))return;
 starting=true;enable(false);status.textContent='Opening Google sign-in…';try{const next=new URL(location.href);if(active)next.searchParams.set('day',active);next.searchParams.delete('login');const result=await call('start',{provider:b.dataset.provider,next:next.pathname+next.search+next.hash});if(typeof result.url!=='string')throw Error();dirty=false;location.assign(result.url)}catch(e){starting=false;status.textContent=e.status===503?'Sign-in is unavailable. Please try again shortly.':e.status===404||e instanceof SyntaxError?'Could not reach the sign-in endpoint. Please reload and try again.':'Could not connect. Try signing in again.';enable(true)}};
 el('logout').onclick=async()=>{if(dirty&&!confirm('Discard unsaved changes and sign out?'))return;try{await call('logout',{});dirty=false;location.replace(location.pathname)}catch{status.textContent='Could not sign out. Please try again.'}};
 if(el('withdraw'))el('withdraw').onclick=async e=>{if(!uid||!confirm('Close your Feelody account? Access ends immediately. After 24 hours, a task runs every minute to permanently erase your Feelody account, profile, entries and saved recommendations from the live database. Optional member activity is cleared on closure. Guest entries on this device stay.'))return;
 const btn=e.currentTarget;btn.disabled=true;try{await call('withdraw',{});entries.clear();dirty=false;location.replace(location.pathname)}catch(error){status.textContent=error.code==='last_admin'?'You are the last administrator. Assign another administrator before closing your account.':'Could not confirm account closure. Refresh to check your account.';btn.disabled=false}};
 el('importGuest').onclick=async e=>{if(!uid||!confirm('Copy guest entries to your account? Existing dates will be kept and the originals will stay on this device.'))return;
 const btn=e.currentTarget;btn.disabled=true;try{const rows=[];for(const k of Object.keys(localStorage)){if(!k.startsWith(prefix))continue;
 const day=k.slice(prefix.length);if(!/^\d{4}-\d{2}-\d{2}$/.test(day))continue;const entry=JSON.parse(localStorage.getItem(k));if(typeof entry?.text==='string'&&hasMood(entry.mood))rows.push({day,entry,user_id:uid})}
 for(let i=0;i<rows.length;i+=50)await call('import',{rows:rows.slice(i,i+50)});
 await fetchEntries();status.textContent=rows.length?'Entries imported. Existing account entries were kept.':'No guest entries to import.'}catch{status.textContent='Import did not finish. Please try again.'}finally{btn.disabled=false}};
 try{const session=await call('session');if(!session.configured){authReady=true;note();if(!starting)status.textContent='Sign-in is not configured yet. You can keep writing as a guest.';return}
 uid=session.user;if(session.withdrawn){status.textContent='This account is closed. You can still write as a guest.';dlg.showModal()}
 window.addEventListener('pageshow',e=>{if(e.persisted)location.reload()});
 window.addEventListener('focus',async()=>{try{const fresh=await call('session');if(fresh.user===uid&&uid){ai=!!fresh.aiEnabled;note()}if(fresh.user!==uid){entries.clear();main.hidden=true;dirty=false;location.reload()}}catch{}});
 if(uid){
 if(!session.termsAccepted){
 main.hidden=true;const modal=el('onboarding'),form=el('termsForm'),msg=el('consentMessage');
 modal.oncancel=e=>e.preventDefault();el('allowActivity').checked=!!session.activityEnabled;el('allowAI').checked=!!session.aiEnabled;
 el('allowActivity').disabled=!session.activityAvailable&&!session.activityEnabled;
 el('decline').onclick=async()=>{try{await call('logout',{});location.replace('/')}catch{msg.textContent='Could not sign out. Try again.'}};
 form.onsubmit=async e=>{e.preventDefault();const btn=form.querySelector('[type="submit"]');btn.disabled=true;
 try{await call('choices',{acceptRequired:el('acceptRequired').checked,allowAI:el('allowAI').checked,allowActivity:el('allowActivity').checked});location.replace(new URL(location.href).searchParams.get('after')==='admin'?'/admin':location.pathname+location.search)}
 catch{btn.disabled=false;msg.textContent='Could not save your choices. Please try again.'}};
 modal.showModal();return;
 }
 ai=!!session.aiEnabled;account.classList.add('signed-in');account.setAttribute('aria-label','Open account menu');account.title='Account';account.innerHTML='<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="8" r="3.4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>';
 if(session.avatarUrl){const img=document.createElement('img');img.alt='';img.referrerPolicy='no-referrer';img.onerror=()=>img.remove();img.src=session.avatarUrl;account.append(img)}
 el('accountTitle').textContent='My journal';help.textContent='Your entries and playlists are saved to this account.';
 el('providers').hidden=true;el('memberActions').hidden=false;if(el('accountFooter'))el('accountFooter').hidden=false;el('guestContinue').textContent='Back to calendar';await fetchEntries()}
 authReady=true;note();
 const current=new URL(location.href),day=current.searchParams.get('day');
 if(/^\d{4}-\d{2}-\d{2}$/.test(day||'')){month=new Date(day+'T12:00:00');month.setDate(1);openDay(day)}
 if(current.searchParams.get('login')==='failed'){status.textContent='Sign-in did not finish. Try again or continue as a guest.';dlg.showModal();current.searchParams.delete('login');history.replaceState(null,'',current)}
 }catch{status.textContent='Could not load your account. Please refresh and try again.';if(uid)dlg.showModal()}
 finally{main.classList.remove('checking-account');main.inert=!!uid&&!authReady}
})();
