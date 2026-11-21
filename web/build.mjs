import {mkdir,copyFile,writeFile,rm,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const mode=process.env.FEELODY_WEB_MODE==='local'?'local':'llm';
const url=mode==='local'?(process.env.FEELODY_API_ORIGIN||'').trim():'';
if(url && (!/^https:\/\//.test(url)||new URL(url).origin!==url)) throw Error('FEELODY_API_ORIGIN must be an HTTPS origin without a trailing slash');
await rm('dist',{recursive:true,force:true});
await mkdir('dist');
for(const f of ['terms.html','privacy.html','activity.js','privacy-choice.js','index.html','study.html','app.js','account.js','account.css','style.css','cases.json','research.html','research.css','research.js','moods.js','ads.txt','favicon.svg','share.png','robots.txt','sitemap.xml','_routes.json','_headers']) await copyFile('web/'+f,'dist/'+f);
await writeFile('dist/config.json',JSON.stringify({mode,apiOrigin:url}));

for(const file of ['index.html','study.html','research.html','privacy.html']){
 let html=await readFile('dist/'+file,'utf8');
 for(const match of [...html.matchAll(/(?:src|href)="\.?\/([\w.-]+\.(?:css|js))(?:\?[^"]*)?"/g)]){
  const hash=createHash('sha256').update(await readFile('dist/'+match[1])).digest('hex').slice(0,12);
  html=html.replace(match[0],match[0].split('=')[0]+'="./'+match[1]+'?v='+hash+'"');
 }
 await writeFile('dist/'+file,html);
}
