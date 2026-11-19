import test from 'node:test';
import assert from 'node:assert/strict';
import handler, {normalize,providerConfig} from '../api/recommend.mjs';

const fixture={summary:'작은 성취가 있었던 하루',empathy:'차근차근 해낸 자신을 격려해도 좋겠어요.',
 songs:[1,2,3].map(i=>({title:'노래'+i,artist:'가수',reason:'성취의 기쁨에 어울리는 곡이에요.',youtube_url:'https://bad.example/'}))};
let seq=0;
function req(body={diary:'기쁜 하루',mood:'joy'},method='POST'){
 return {method,body,headers:{'content-type':'application/json',host:'feelody.example',origin:'https://feelody.example','x-forwarded-for':'test-'+ ++seq}};
}
function response(){return {headers:{},setHeader(k,v){this.headers[k]=v},status(n){this.code=n;return this},json(v){this.value=v;return this}}}
async function call(r){const res=response();await handler(r,res);return res}
test('Vercel LLM handler contracts without real provider calls',async()=>{
 const saved={...process.env},fetchOriginal=globalThis.fetch;let calls=[];
 try{
  delete process.env.OPENAI_API_KEY;delete process.env.GEMINI_API_KEY;delete process.env.FEELODY_LLM_MODEL;
  delete process.env.FEELODY_LLM_REASONING_EFFORT;delete process.env.FEELODY_LLM_PROVIDER;delete process.env.FEELODY_LLM_ENABLED;
  globalThis.fetch=async(url,opts)=>{calls.push({url,opts});return {ok:true,json:async()=>({choices:[{finish_reason:'stop',message:{content:JSON.stringify(fixture)}}]})}};
  assert.equal((await call(req(null,'GET'))).value.configured,false);
  assert.equal((await call(req())).code,503);assert.equal(calls.length,0);
  process.env.OPENAI_API_KEY='test-secret-do-not-publish';
  assert.equal(providerConfig().model,'gpt-4.1-mini');
  const status=await call(req(null,'GET'));assert.equal(status.value.configured,true);assert.equal(calls.length,0);
  const result=await call(req());assert.equal(result.code,200);assert.equal(result.headers['Cache-Control'],'no-store');
  assert.equal(result.value.songs.length,3);assert.ok(result.value.timing.provider_ms>=0);assert.ok(result.value.timing.server_ms>=result.value.timing.provider_ms);assert.ok(result.value.timing_key.includes('gpt-4.1-mini'));assert.equal(result.value.summary,fixture.summary);
  assert.equal(new URL(result.value.songs[0].youtube_url).hostname,'www.youtube.com');
  assert.ok(!JSON.stringify(result.value).includes('test-secret'));
  assert.equal(JSON.parse(calls[0].opts.body).store,false);
  assert.equal((await call(req({diary:' '.repeat(8)}))).code,422);
  assert.equal((await call(req({diary:'x'.repeat(4001)}))).code,422);
  assert.equal((await call(req(null,'DELETE'))).code,405);
  const foreign=req();foreign.headers.origin='https://other.example';
  assert.equal((await call(foreign)).code,403);
  assert.throws(()=>normalize({...fixture,songs:[fixture.songs[0],fixture.songs[0],fixture.songs[1]]}));
  globalThis.fetch=async()=>({ok:true,json:async()=>({choices:[{finish_reason:'stop',message:{content:'invalid JSON with sensitive data'}}]})});
  const bad=await call(req());assert.equal(bad.code,502);assert.ok(!JSON.stringify(bad.value).includes('sensitive'));
  globalThis.fetch=async()=>({ok:false,status:401});
  assert.equal((await call(req())).code,502);
  globalThis.fetch=async()=>{throw Object.assign(Error('provider timeout'),{name:'TimeoutError'})};
  assert.equal((await call(req())).code,504);
  process.env.FEELODY_LLM_PROVIDER='gemini';process.env.GEMINI_API_KEY='another-fixture-key';
  assert.equal((await call(req())).code,503); // requires explicit model instead of outdated defaults
  process.env.FEELODY_LLM_MODEL='fixture-gemini';process.env.FEELODY_LLM_REASONING_EFFORT='medium';
  globalThis.fetch=async(url,opts)=>{assert.ok(url.startsWith('https://generativelanguage.googleapis.com/'));assert.equal(JSON.parse(opts.body).model,'fixture-gemini');assert.equal(JSON.parse(opts.body).reasoning_effort,'medium');return {ok:true,json:async()=>({choices:[{finish_reason:'stop',message:{content:JSON.stringify(fixture)}}]})}};
  assert.equal((await call(req())).code,200);
  const same=req();for(let i=0;i<5;i++)assert.equal((await call(same)).code,200);
  assert.equal((await call(same)).code,429);
  process.env.FEELODY_LLM_ENABLED='0';assert.equal((await call(req())).code,503);
 }finally{
  globalThis.fetch=fetchOriginal;for(const k of Object.keys(process.env))if(!(k in saved))delete process.env[k];Object.assign(process.env,saved);
 }
});
