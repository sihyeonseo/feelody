import {handleAccount} from '../api/account/[action].js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths=['/admin','/admin/members','/admin/plans'];
function page(headers,title,body,section,status=200){
 headers.set('Content-Type','text/html; charset=utf-8');headers.set('X-Robots-Tag','noindex, nofollow');headers.set('X-Frame-Options','DENY');
 headers.set('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
 const nav=section?'<aside><b>Feelody 관리자</b><nav>'+paths.map((p,i)=>'<a '+(p===section?'aria-current="page" ':'')+'href="'+p+'">'+['대시보드','회원 관리','요금제 관리'][i]+'</a>').join('')+'</nav><button id="logout">로그아웃</button></aside>':'';
 return new Response('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+' | Feelody 관리자</title><style>*{box-sizing:border-box}body{margin:0;background:#f6f7f4;color:#23352d;font:16px/1.55 system-ui}.shell{min-height:100vh;display:grid;grid-template-columns:210px minmax(0,1fr)}aside{padding:28px 18px;background:#203d32;color:white}nav{display:grid;gap:8px;margin:32px 0}nav a{padding:8px;color:inherit;text-decoration:none}nav a[aria-current]{background:#38604d;border-radius:6px}main{padding:clamp(18px,5vw,60px);max-width:1100px}section,form,.card{background:white;padding:20px;border:1px solid #d7dfd9;border-radius:10px;margin:12px 0}h1{margin:0 0 18px}label{display:inline-grid;margin:6px;gap:3px}button,input{font:inherit;padding:7px;border:1px solid #aebdb3;border-radius:6px}button{cursor:pointer}a{color:#285a44}.login{min-height:100vh;display:grid;place-items:center}.login main{width:min(420px,100%)}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}.scroll{overflow:auto}@media(max-width:680px){.shell{display:block}aside{padding:14px}nav{display:flex;flex-wrap:wrap;margin:8px 0}}</style><div class="'+(section?'shell':'login')+'">'+nav+'<main><h1>'+esc(title)+'</h1>'+body+'</main></div><script src="/admin/ui.js" defer></script></html>',{headers,status});
}
const input=(p={})=>'<form method="post" action="/admin/plans">'+(p.id?'<input type="hidden" name="id" value="'+esc(p.id)+'">':'')+'<label>요금제 이름<input required maxlength="80" name="name" value="'+esc(p.name)+'"></label><label>월 요금(미국 달러)<input required type="number" min="0" max="999999.99" step=".01" name="price" value="'+(p.id?(p.monthly_usd_cents/100).toFixed(2):'0.00')+'"></label><label><span><input type="checkbox" name="active" '+(p.active?'checked':'')+'> 사용 중</span></label><button>'+(p.id?'변경 사항 저장':'요금제 만들기')+'</button></form>';
const js=`const sign=document.querySelector('#signin'),out=document.querySelector('#logout');async function auth(action,body){const r=await fetch('/api/account/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error();return r.json()}if(sign)sign.onclick=async()=>{try{sign.disabled=true;location.assign((await auth('start',{provider:'google',next:'/admin'})).url)}catch{sign.disabled=false;sign.textContent='Google 로그인 다시 시도'}};if(out)out.onclick=async()=>{try{await auth('logout',{});location.replace('/admin/login')}catch{out.textContent='로그아웃 다시 시도'}};window.addEventListener('pageshow',e=>{if(e.persisted)location.reload()});`;
export async function onRequest(ctx){
 const {request}=ctx,u=new URL(request.url),path=u.pathname.replace(/\/$/,'');
 const headers=new Headers({'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'});
 if(path==='/admin/ui.js'&&request.method==='GET'){headers.set('Content-Type','text/javascript');return new Response(js,{headers})}
 if(path==='/admin/login'&&request.method==='GET')return page(headers,'관리자 로그인','<section><p>관리자 권한이 있는 Google 계정으로 로그인하세요.</p><button id="signin">Google 계정으로 로그인</button></section>');
 if(!paths.includes(path))return new Response('페이지를 찾을 수 없습니다.',{status:404,headers});
 if(request.method!=='GET'&&!(request.method==='POST'&&path==='/admin/plans'))return new Response(null,{status:405,headers});
 return handleAccount({...ctx,params:{action:'admin-console'}},async({headers,remote,bearer,go})=>{
 const render=(title,body,status=200)=>page(headers,title,body,path,status);
 const db=(endpoint,opts={})=>remote('/rest/v1/'+endpoint,{...opts,headers:{...bearer(),...opts.headers}});
 const err=()=>render('관리자 데이터를 불러올 수 없습니다','<p>데이터베이스 설정을 확인한 뒤 다시 시도하세요.</p>',503);
 if(request.method==='POST'){
 const f=await request.formData(),id=f.get('id'),name=String(f.get('name')||'').trim(),price=String(f.get('price')||'');
 if((id&&!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(id))||!name||name.length>80||!/^\d{1,6}(?:\.\d{1,2})?$/.test(price))return render('요금제 정보를 확인해 주세요','<p>요금제 이름과 월 요금을 확인하세요.</p>',400);
 const res=await db('pricing_plans'+(id?'?id=eq.'+id:''),{method:id?'PATCH':'POST',headers:{Prefer:'return=representation'},body:JSON.stringify({name,monthly_usd_cents:Math.round(Number(price)*100),active:f.get('active')==='on'})});
 if(res.status===409)return render('이미 사용 중인 이름입니다','<p>다른 요금제 이름을 입력하세요.</p>',409);
 if(!res.ok)return err();if(!(await res.json()).length)return render('요금제를 찾을 수 없습니다','',404);return go(path);
 }
 const num=Number(u.searchParams.get('page')||1);
 if(!Number.isInteger(num)||num<1||num>100000)return render('페이지 번호를 확인해 주세요','',400);
 async function members(){const r=await db('rpc/feelody_admin_members',{method:'POST',body:JSON.stringify({page_no:num})});if(!r.ok)throw Error();return r.json()}
 async function plans(){const r=await db('pricing_plans?select=id,name,monthly_usd_cents,active&order=name');if(!r.ok)throw Error();return r.json()}
 try{
 if(path===paths[0]){const [m,p]=await Promise.all([members(),plans()]);return render('대시보드','<section><h2>회원 관리</h2><p>'+esc(m.total)+'명 · 관리자 '+esc(m.admins)+'명</p><a href="/admin/members">회원 목록 보기</a></section><section><h2>요금제 관리</h2><p>'+p.filter(x=>x.active).length+'개 사용 중</p><a href="/admin/plans">요금제 관리하기</a></section>')}
 if(path===paths[1]){const m=await members();return render('회원 관리','<p>'+esc(m.total)+'명</p><section class="scroll"><table><thead><tr><th>이름</th><th>이메일</th><th>권한</th><th>가입일</th></tr></thead><tbody>'+m.members.map(x=>'<tr>'+[x.full_name,x.email,x.role==='Admin'?'관리자':x.role==='User'?'일반 회원':'미지정',x.created_at?.slice(0,10)].map(v=>'<td>'+esc(v??'—')+'</td>').join('')+'</tr>').join('')+'</tbody></table></section>'+(num>1?'<a href="?page='+(num-1)+'">이전</a> ':'')+(num*25<m.total?'<a href="?page='+(num+1)+'">다음</a>':''))}
 const p=await plans();return render('요금제 관리','<p>요금을 저장해도 회원에게 실제로 청구되지 않습니다.</p><h2>새 요금제</h2>'+input()+'<h2>등록된 요금제</h2>'+(p.map(input).join('')||'<p>아직 등록된 요금제가 없습니다.</p>'))
 }catch{return err()}
 });
}
