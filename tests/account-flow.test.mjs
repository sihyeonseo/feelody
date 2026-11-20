import test from 'node:test';
import assert from 'node:assert/strict';
import {onRequest} from '../functions/api/account/[action].js';
const origin='https://feelody.shop',env={SUPABASE_URL:'https://example.supabase.co',SUPABASE_PUBLISHABLE_KEY:'example'};
function request(action,{body,cookie='',query='',headers={}}={}){return onRequest({env,params:{action},request:new Request(origin+'/api/account/'+action+query,{method:body?'POST':'GET',headers:{Origin:origin,Cookie:cookie,...headers},body:body?JSON.stringify(body):undefined})})}
test('Both providers return to the same editor through server PKCE',async t=>{
 for(const provider of ['google','kakao']){
 const next='/index.html?day=2026-11-20&view=diary#playlist',start=await request('start',{body:{provider,next}});assert.equal(start.status,200);
 const target=new URL((await start.json()).url);assert.equal(target.searchParams.get('provider'),provider);assert.equal(target.searchParams.get('redirect_to'),origin+'/api/account/callback');
 const cookies=start.headers.getSetCookie();assert.ok(cookies.every(c=>c.includes('HttpOnly')&&c.includes('Secure')));
 const jar=cookies.map(c=>c.split(';')[0]).join('; ');
 const stub=t.mock.method(globalThis,'fetch',async (url,opts)=>{assert.match(url,/grant_type=pkce/);const v=JSON.parse(opts.body);assert.equal(v.auth_code,'test');const digest=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(v.code_verifier))).toString('base64url');assert.equal(digest,target.searchParams.get('code_challenge'));return Response.json({access_token:'access',refresh_token:'refresh'})});
 const cb=await request('callback',{cookie:jar,query:'?code=test'});assert.equal(cb.status,303);assert.equal(cb.headers.get('Location'),next);assert.ok(cb.headers.getSetCookie().some(x=>x.startsWith('__Host-feelody-access=')));stub.mock.restore()}
});
test('guest, cancel, unsafe next and account mismatch',async t=>{
 assert.equal((await (await request('session')).json()).user,null);
 const start=await request('start',{body:{provider:'google',next:'https://elsewhere.example/'}});
 const denied=await request('callback',{cookie:start.headers.getSetCookie().map(c=>c.split(';')[0]).join('; '),query:'?error=access_denied'});
 assert.equal(denied.headers.get('Location'),'/?login=failed');
 assert.equal((await request('start',{body:{provider:'apple'}})).status,400);
 assert.equal((await request('start',{body:{provider:'google'},headers:{Origin:'https://elsewhere.example'}})).status,403);
 t.mock.method(globalThis,'fetch',async url=>{assert.match(url,/\/user$/);return Response.json({id:'new-account'})});
 assert.equal((await request('entries',{cookie:'__Host-feelody-access=ok',body:{},headers:{'X-Feelody-Account':'old-account'}})).status,401);
});
