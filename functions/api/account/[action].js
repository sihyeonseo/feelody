// Pages Functions adapter for Supabase Auth PKCE and PostgREST (user JWT + RLS).
const root='/api/account/', cookieName=k=>'__Host-feelody-'+k;
const b64=buf=>btoa(String.fromCharCode(...new Uint8Array(buf))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
const dayOK=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
function avatar(user){
 const profiles=[user?.user_metadata,...(user?.identities||[]).map(i=>i.identity_data)];
 for(const p of profiles)for(const value of [p?.avatar_url,p?.picture]){
  if(typeof value!=='string')continue;
  try{const u=new URL(value);if(!['https:','http:'].includes(u.protocol)||u.username||u.password||u.port)continue;
   if(!/(^|\.)(googleusercontent\.com)$/.test(u.hostname))continue;
   u.protocol='https:';return u.href}catch{}
 }
 return null;
}
export function returnPath(value,origin){
 try{const u=new URL(value||'/',origin);
 if(u.origin===origin&&u.pathname==='/admin')return '/admin';
 if(u.origin===origin&&['/','/index','/index.html','/research','/research.html','/study','/study.html'].includes(u.pathname))return u.pathname+u.search+u.hash}catch{}
 return '/';
}
export const onRequest=ctx=>handleAccount(ctx);
export async function handleAccount(ctx,adminHandler){
 const {request:req,env,params}=ctx;
 const url=new URL(req.url),origin=url.origin,action=params.action;
 const headers=new Headers({'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'});
 const json=(data,status=200)=>{headers.set('Content-Type','application/json');return new Response(JSON.stringify(data),{status,headers})};
 const go=path=>{headers.set('Location',path);return new Response(null,{status:303,headers})};
 const set=(k,v,age)=>headers.append('Set-Cookie',cookieName(k)+'='+encodeURIComponent(v)+'; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age='+age);
 const get=k=>{const part=(req.headers.get('cookie')||'').split(';').map(x=>x.trim()).find(x=>x.startsWith(cookieName(k)+'='));return part?decodeURIComponent(part.slice(part.indexOf('=')+1)):''};
 const base=(env.SUPABASE_URL||'').replace(/\/$/,'');const key=env.SUPABASE_PUBLISHABLE_KEY;
 const clear=()=>{set('access','',0);set('refresh','',0)};
 const put=s=>{if(!s.access_token||!s.refresh_token)throw Error();set('access',s.access_token,Math.max(60,Number(s.expires_in)||3600));set('refresh',s.refresh_token,60*60*24*30)};
 const remote=(path,options={})=>fetch(base+path,{...options,headers:{apikey:key,'Content-Type':'application/json',...options.headers}});
 const writer=env.FEELODY_ACTIVITY_WRITER||'';
 const activity=(token,action,screen='')=>remote('/rest/v1/rpc/feelody_activity',{method:'POST',signal:AbortSignal.timeout(2500),headers:{Authorization:'Bearer '+token,'X-Feelody-Writer':writer},body:JSON.stringify({action,screen})});
 const record=async(token,event)=>{if(writer.length>=32)try{await activity(token,event)}catch{}};
 try{
 if(!adminHandler&&req.method!==(action==='callback'||action==='session'?'GET':'POST'))return json({},405);
 if(req.method==='POST'&&req.headers.get('Origin')!==origin)return json({},403);
 if(!base||!key)return action==='session'?json({configured:false,user:null}):json({},503);
 if(!adminHandler&&action==='start'){
 const {provider,next}=await req.json();if(provider!=='google')return json({},400);
 const verifier=b64(crypto.getRandomValues(new Uint8Array(48)));
 const to=new URL(base+'/auth/v1/authorize');
 to.search=new URLSearchParams({provider,prompt:'select_account',redirect_to:origin+root+'callback',code_challenge:b64(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))),code_challenge_method:'s256'});
 const path=returnPath(next,origin);if(path.length>1500)return json({},400);
 set('pkce',verifier,600);set('next',path,600);return json({url:to.href});
 }
 if(!adminHandler&&action==='callback'){
 const next=returnPath(get('next'),origin),verifier=get('pkce'),code=url.searchParams.get('code');
 set('pkce','',0);set('next','',0);
 if(verifier&&code){try{const r=await remote('/auth/v1/token?grant_type=pkce',{method:'POST',body:JSON.stringify({auth_code:code,code_verifier:verifier})});if(r.ok){const session=await r.json();put(session);if(writer.length>=32){const log=record(session.access_token,'login');if(ctx.waitUntil)ctx.waitUntil(log);else await log}return go(next)}}catch{}}
 const back=new URL(next,origin);back.searchParams.set('login','failed');return go(back.pathname+back.search+back.hash)
 }
 if(!adminHandler&&!['session','entries','save','remove','import','logout','withdraw','choices','visit'].includes(action))return json({},404);
 if(!adminHandler&&action==='visit'&&writer.length<32)return json({});
 let access=get('access'),refresh=get('refresh');const bearer=()=>({Authorization:'Bearer '+access});
 let user=null;
 if(access){const r=await remote('/auth/v1/user',{headers:bearer()});if(r.ok)user=await r.json();else if(![401,403].includes(r.status))return json({},503)}
 if(!user&&refresh){const r=await remote('/auth/v1/token?grant_type=refresh_token',{method:'POST',body:JSON.stringify({refresh_token:refresh})});if(r.ok){const s=await r.json();put(s);access=s.access_token;user=s.user}else if(r.status===400||r.status===401){clear()}else return json({},503)}
 if(adminHandler){
  if(!user?.id)return go('/admin/login');
  const role=await remote('/rest/v1/profiles?select=role,terms_accepted_at&id=eq.'+encodeURIComponent(user.id),{headers:bearer()});
  if(!role.ok)return json({},503);
  const adminProfile=(await role.json())[0];if(adminProfile&&!adminProfile.terms_accepted_at)return go('/?after=admin');
  if(adminProfile?.role!=='Admin')return new Response('관리자 권한이 있는 계정만 접근할 수 있습니다.',{status:403,headers});
  return await adminHandler({headers,remote,bearer,go});
 }
 if(action==='session'&&user?.id){
 const r=await remote('/rest/v1/profiles?select=id,terms_accepted_at,ai_opt_in_at,activity_opt_in_at&id=eq.'+encodeURIComponent(user.id),{headers:bearer()});
 if(!r.ok)return json({},503);
 const profile=(await r.json())[0];if(!profile){clear();return json({configured:true,user:null,withdrawn:true})}
 return json({configured:true,user:user.id,avatarUrl:avatar(user),termsAccepted:!!profile.terms_accepted_at,aiEnabled:!!profile.ai_opt_in_at,activityEnabled:!!profile.activity_opt_in_at,activityAvailable:writer.length>=32});
 }
 if(action==='session')return json({configured:true,user:user?.id||null,avatarUrl:user?.id?avatar(user):null});
 if(action==='logout'){if(user){const r=await remote('/auth/v1/logout?scope=local',{method:'POST',headers:bearer()});if(!r.ok)return json({},503);await record(access,'logout')}clear();return json({})}
 if(action==='visit'){
 if(!user?.id||writer.length<32)return json({});
 const b=await req.json();if(!['calendar','entry','research','study'].includes(b.screen))return json({},400);
 const r=await activity(access,'visit',b.screen);return json({},r.ok?200:503)
 }
 if(!user?.id||req.headers.get('X-Feelody-Account')!==user.id)return json({},401);
 if(action==='choices'){
 const b=await req.json();if(!['acceptRequired','allowAI','allowActivity'].every(k=>typeof b[k]==='boolean'))return json({},400);
 const r=await remote('/rest/v1/rpc/feelody_save_choices',{method:'POST',headers:{...bearer(),'X-Feelody-Writer':writer},body:JSON.stringify({accept_required:b.acceptRequired,allow_ai:b.allowAI,allow_activity:b.allowActivity})});
 return json({},r.ok?200:r.status)
 }
 if(action==='withdraw'){
 const r=await remote('/rest/v1/rpc/feelody_withdraw',{method:'POST',headers:bearer(),body:'{}'});
 if(r.status===409 && (await r.json()).message==='last_admin')return json({code:'last_admin'},409);
 if(!r.ok)return json({},r.status);
 clear();return json({withdrawn:true});
 }
 const body=await req.json(), query=new URLSearchParams({user_id:'eq.'+user.id});
 let method='GET',payload,prefer;
 if(action==='entries'){query.set('select','day,entry');query.set('order','day.asc');query.set('limit','100');if(body.last){if(!dayOK(body.last))return json({},400);query.set('day','gt.'+body.last)}}
 else if(action==='remove'){if(!dayOK(body.day))return json({},400);method='DELETE';query.set('day','eq.'+body.day)}
 else{const rows=action==='save'?[body]:body.rows;if(!Array.isArray(rows)||!rows.length||rows.length>50||rows.some(r=>!dayOK(r?.day)||typeof r.entry?.text!=='string'||r.entry.text.length>4000||typeof r.entry.mood!=='string'))return json({},400);
 query.delete('user_id');query.set('on_conflict','user_id,day');method='POST';prefer='resolution='+(action==='import'?'ignore':'merge')+'-duplicates';payload=JSON.stringify(rows.map(r=>({user_id:user.id,day:r.day,entry:r.entry})))}
 const r=await remote('/rest/v1/diary_entries?'+query,{method,headers:{...bearer(),...(prefer?{Prefer:prefer}:{})},body:payload});
 return r.ok?json(action==='entries'?await r.json():{}):json({},r.status);
 }catch{return json({},503)}
}
