(()=>{const key='feelody:analytics:v1';let allowed=false;try{allowed=localStorage.getItem(key)==='yes'}catch{}
const box=document.getElementById('analytics');if(box){box.checked=allowed;box.onchange=()=>{try{localStorage.setItem(key,box.checked?'yes':'no');document.getElementById('result').textContent='Preference saved.'}catch{box.checked=allowed;document.getElementById('result').textContent='Your browser did not save this preference.'}};return}
if(!allowed)return;for(const tpl of document.querySelectorAll('template[data-analytics]')){for(const src of tpl.content.querySelectorAll('script')){const s=document.createElement('script');for(const a of src.attributes)s.setAttribute(a.name,a.value);s.textContent=src.textContent;document.head.append(s)}}
})();
(async()=>{const el=id=>document.getElementById(id),form=el('prefs');if(!form)return;
const msg=el('prefStatus');const session=async()=>{const r=await fetch('/api/account/session',{cache:'no-store'});if(!r.ok)throw Error();return r.json()};
try{const s=await session();if(s.user&&!s.termsAccepted){msg.textContent='Complete account setup on the calendar to manage member preferences.';return}
el('scope').textContent=s.user?'These choices apply to your signed-in account.':'Guest recommendation preferences apply only to this browser.';
el('prefAI').checked=s.user?!!s.aiEnabled:localStorage.getItem('feelody:guestAI:v1')==='yes';el('memberLog').hidden=!s.user;
el('prefLog').checked=!!s.activityEnabled;el('prefLog').disabled=!s.activityAvailable&&!s.activityEnabled;
form.hidden=false;msg.textContent='';
form.onsubmit=async e=>{e.preventDefault();const btn=form.querySelector('button');btn.disabled=true;try{
if(s.user){const r=await fetch('/api/account/choices',{method:'POST',headers:{'Content-Type':'application/json','X-Feelody-Account':s.user},body:JSON.stringify({acceptRequired:false,allowAI:el('prefAI').checked,allowActivity:el('prefLog').checked})});if(!r.ok)throw Error()}
else{if((await session()).user)throw Error();localStorage.setItem('feelody:guestAI:v1',el('prefAI').checked?'yes':'no')}
msg.textContent='Preferences saved.'}catch{msg.textContent='Preferences were not saved. Reload and try again.'}finally{btn.disabled=false}};
}catch{msg.textContent='Could not load preferences. Please reload.'}})();