import {handleAccount} from '../api/account/[action].js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths=['/admin','/admin/members','/admin/plans'];
function page(headers,title,body,section,status=200){
 headers.set('Content-Type','text/html; charset=utf-8');headers.set('X-Robots-Tag','noindex, nofollow');headers.set('X-Frame-Options','DENY');
 headers.set('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
 const nav=section?'<aside><b>Feelody / Admin</b><nav>'+paths.map((p,i)=>'<a '+(p===section?'aria-current="page" ':'')+'href="'+p+'">'+['Overview','Members','Pricing plans'][i]+'</a>').join('')+'</nav><button id="logout">Sign out</button></aside>':'';
 return new Response('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+' | Feelody Admin</title><style>*{box-sizing:border-box}body{margin:0;background:#f6f7f4;color:#23352d;font:16px/1.55 system-ui}.shell{min-height:100vh;display:grid;grid-template-columns:210px minmax(0,1fr)}aside{padding:28px 18px;background:#203d32;color:white}nav{display:grid;gap:8px;margin:32px 0}nav a{padding:8px;color:inherit;text-decoration:none}nav a[aria-current]{background:#38604d;border-radius:6px}main{padding:clamp(18px,5vw,60px);max-width:1100px}section,form,.card{background:white;padding:20px;border:1px solid #d7dfd9;border-radius:10px;margin:12px 0}h1{margin:0 0 18px}label{display:inline-grid;margin:6px;gap:3px}button,input{font:inherit;padding:7px;border:1px solid #aebdb3;border-radius:6px}button{cursor:pointer}a{color:#285a44}.login{min-height:100vh;display:grid;place-items:center}.login main{width:min(420px,100%)}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}.scroll{overflow:auto}@media(max-width:680px){.shell{display:block}aside{padding:14px}nav{display:flex;flex-wrap:wrap;margin:8px 0}}</style><div class="'+(section?'shell':'login')+'">'+nav+'<main><h1>'+esc(title)+'</h1>'+body+'</main></div><script src="/admin/ui.js" defer></script></html>',{headers,status});
}
const input=(p={})=>'<form method="post" action="/admin/plans">'+(p.id?'<input type="hidden" name="id" value="'+esc(p.id)+'">':'')+'<label>Plan name<input required maxlength="80" name="name" value="'+esc(p.name)+'"></label><label>Monthly price (USD)<input required type="number" min="0" max="999999.99" step=".01" name="price" value="'+(p.id?(p.monthly_usd_cents/100).toFixed(2):'0.00')+'"></label><label><span><input type="checkbox" name="active" '+(p.active?'checked':'')+'> Active</span></label><button>'+(p.id?'Save changes':'Create plan')+'</button></form>';
const js=`const sign=document.querySelector('#signin'),out=document.querySelector('#logout');async function auth(action,body){const r=await fetch('/api/account/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error();return r.json()}if(sign)sign.onclick=async()=>{try{sign.disabled=true;location.assign((await auth('start',{provider:'google',next:'/admin'})).url)}catch{sign.disabled=false;sign.textContent='Try Google sign-in again'}};if(out)out.onclick=async()=>{try{await auth('logout',{});location.replace('/admin/login')}catch{out.textContent='Retry sign out'}};window.addEventListener('pageshow',e=>{if(e.persisted)location.reload()});`;
export async function onRequest(ctx){
 const {request}=ctx,u=new URL(request.url),path=u.pathname.replace(/\/$/,'');
 const headers=new Headers({'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'});
 if(path==='/admin/ui.js'&&request.method==='GET'){headers.set('Content-Type','text/javascript');return new Response(js,{headers})}
 if(path==='/admin/login'&&request.method==='GET')return page(headers,'Admin sign-in','<section><p>Use your authorized Google account.</p><button id="signin">Continue with Google</button></section>');
 if(!paths.includes(path))return new Response('Not found',{status:404,headers});
 if(request.method!=='GET'&&!(request.method==='POST'&&path==='/admin/plans'))return new Response(null,{status:405,headers});
 return handleAccount({...ctx,params:{action:'admin-console'}},async({headers,remote,bearer,go})=>{
 const render=(title,body,status=200)=>page(headers,title,body,path,status);
 const db=(endpoint,opts={})=>remote('/rest/v1/'+endpoint,{...opts,headers:{...bearer(),...opts.headers}});
 const err=()=>render('Unavailable','<p>Could not load admin data. Check the database migration and try again.</p>',503);
 if(request.method==='POST'){
 const f=await request.formData(),id=f.get('id'),name=String(f.get('name')||'').trim(),price=String(f.get('price')||'');
 if((id&&!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(id))||!name||name.length>80||!/^\d{1,6}(?:\.\d{1,2})?$/.test(price))return render('Invalid plan','<p>Check the name and monthly price.</p>',400);
 const res=await db('pricing_plans'+(id?'?id=eq.'+id:''),{method:id?'PATCH':'POST',headers:{Prefer:'return=representation'},body:JSON.stringify({name,monthly_usd_cents:Math.round(Number(price)*100),active:f.get('active')==='on'})});
 if(res.status===409)return render('Name already in use','<p>Choose another plan name.</p>',409);
 if(!res.ok)return err();if(!(await res.json()).length)return render('Plan not found','',404);return go(path);
 }
 const num=Number(u.searchParams.get('page')||1);
 if(!Number.isInteger(num)||num<1||num>100000)return render('Invalid page','',400);
 async function members(){const r=await db('rpc/feelody_admin_members',{method:'POST',body:JSON.stringify({page_no:num})});if(!r.ok)throw Error();return r.json()}
 async function plans(){const r=await db('pricing_plans?select=id,name,monthly_usd_cents,active&order=name');if(!r.ok)throw Error();return r.json()}
 try{
 if(path===paths[0]){const [m,p]=await Promise.all([members(),plans()]);return render('Overview','<section><h2>Members</h2><p>'+esc(m.total)+' accounts · '+esc(m.admins)+' administrators</p><a href="/admin/members">View members</a></section><section><h2>Pricing plans</h2><p>'+p.filter(x=>x.active).length+' active plans</p><a href="/admin/plans">Manage plans</a></section>')}
 if(path===paths[1]){const m=await members();return render('Members','<p>'+esc(m.total)+' accounts</p><section class="scroll"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Joined</th></tr></thead><tbody>'+m.members.map(x=>'<tr>'+[x.full_name,x.email,x.role,x.created_at?.slice(0,10)].map(v=>'<td>'+esc(v??'—')+'</td>').join('')+'</tr>').join('')+'</tbody></table></section>'+(num>1?'<a href="?page='+(num-1)+'">Previous</a> ':'')+(num*25<m.total?'<a href="?page='+(num+1)+'">Next</a>':''))}
 const p=await plans();return render('Pricing plans','<p>Plan settings only. Saving a price does not charge a customer.</p><h2>New plan</h2>'+input()+'<h2>Existing plans</h2>'+(p.map(input).join('')||'<p>No plans yet.</p>'))
 }catch{return err()}
 });
}
