import assert from 'node:assert/strict';
import test from 'node:test';
import {onRequest} from '../functions/admin/[[path]].js';
const origin='https://feelody.shop',env={SUPABASE_URL:'https://test.supabase.co',SUPABASE_PUBLISHABLE_KEY:'public'};
function run(path,opts={}){return onRequest({env,request:new Request(origin+path,opts),params:{}})}
test('login has no navigation; protected pages require a verified administrator',async t=>{
 const login=await run('/admin/login');assert.doesNotMatch(await login.text(),/<nav>|Music lab/);
 for(const path of ['/admin','/admin/members','/admin/plans']){const r=await run(path);assert.equal(r.status,303);assert.equal(r.headers.get('location'),'/admin/login')}
 const headers={Cookie:'__Host-feelody-access=session'};let role='User',verified=false;const urls=[];
 t.mock.method(globalThis,'fetch',async(url,opts)=>{urls.push(url);assert.equal(opts.headers.Authorization,'Bearer session');
 if(url.endsWith('/auth/v1/user'))return Response.json({id:'user',user_metadata:{role:'Admin'}});
 if(url.endsWith('/feelody_admin_verified'))return Response.json(verified);if(url.endsWith('/feelody_admin_confirm_mail'))return Response.json(false);if(url.includes('/profiles?'))return Response.json([{role,terms_accepted_at:"2026-11-01"}]);if(url.includes('/rpc/'))return Response.json({total:1,admins:1,members:[{full_name:'<b>X</b>'}]});
 if(url.includes('/pricing_plans'))return Response.json([]);throw Error()});
 for(const path of ['/admin','/admin/members','/admin/plans'])assert.equal((await run(path,{headers})).status,403);
 assert.equal((await run('/admin/plans',{method:'POST',headers:{...headers,Origin:origin},body:new URLSearchParams({name:'No',price:'1'})})).status,403);
 assert.ok(!urls.some(x=>x.includes('/rpc/')||x.includes('pricing_plans')));
 role='Admin';assert.equal((await run('/admin/plans',{method:'POST',headers:{...headers,Origin:'https://other.example'}})).status,403);
 for(const p of ['/admin','/admin/members','/admin/plans'])assert.equal((await run(p,{headers})).headers.get('location'),'/admin/verify');
 const verifyPage=await (await run('/admin/verify',{headers})).text();
 assert.match(verifyPage,/data-auto-send/);assert.doesNotMatch(verifyPage,/type="email"/);
 const sent=await run('/admin/verify',{method:'POST',headers:{...headers,Origin:origin}});
 assert.match(await sent.text(),/메일함을 확인/);assert.ok(urls.some(url=>url.endsWith('/feelody_admin_send_mail')));
 assert.equal((await run('/admin/plans',{method:'POST',headers:{...headers,Origin:origin},body:new URLSearchParams({name:'test',price:'1'})})).status,403);
 assert.equal((await run('/admin/confirm',{method:'POST',headers:{...headers,Origin:origin},body:JSON.stringify({token:'0'.repeat(64)})})).status,403);
 verified=true;
 const r=await run('/admin',{headers});assert.equal(r.status,200);assert.match(r.headers.get('Cache-Control'),/no-store/);const html=await r.text();assert.match(html,/<aside>/);assert.doesNotMatch(html,/Music lab|Mood calendar|googletagmanager/);
 assert.match(await (await run('/admin/members',{headers})).text(),/&lt;b&gt;X/);
 role=null;assert.equal((await run('/admin',{headers})).status,403)
});
