const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const code=fs.readFileSync('web/account.js','utf8');
for(const [label,user,avatarUrl] of [['guest',null,null],['photo','member','https://lh3.googleusercontent.com/image'],['no photo','member',null]]){
 test(label,async()=>{
 const nodes=new Map();function el(id){if(!nodes.has(id))nodes.set(id,{children:[],dataset:{},classList:{add(v){this.value=v}},querySelectorAll(){return []},setAttribute(k,v){this[k]=v},append(x){this.children.push(x);x.remove=()=>this.children.pop()}});return nodes.get(id)}
 await vm.runInNewContext(code,{document:{getElementById:el,createElement:()=>({})},window:{addEventListener(){}},AbortSignal,URL,location:{href:'https://feelody.shop/'},calendar(){},fetch:async url=>({ok:true,json:async()=>url.endsWith('/session')?{configured:true,user,avatarUrl}:[]})});
 const button=el('account');if(!user){assert.equal(button.classList.value,undefined);return}
 assert.equal(button.classList.value,'signed-in');assert.match(button.innerHTML,/<svg/);assert.equal(button['aria-label'],'Open account menu');
 if(avatarUrl){assert.equal(button.children[0].src,avatarUrl);button.children[0].onerror();assert.equal(button.children.length,0)}
 });
}
