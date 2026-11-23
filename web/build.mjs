import {mkdir,copyFile,writeFile,rm,readFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const mode=process.env.FEELODY_WEB_MODE==='local'?'local':'llm';
const url=mode==='local'?(process.env.FEELODY_API_ORIGIN||'').trim():'';
if(url && (!/^https:\/\//.test(url)||new URL(url).origin!==url)) throw Error('FEELODY_API_ORIGIN must be an HTTPS origin without a trailing slash');
await rm('dist',{recursive:true,force:true});
await mkdir('dist');
for(const f of ['listening-notes.html','terms.html','privacy.html','activity.js','privacy-choice.js','index.html','study.html','app.js','account.js','account.css','style.css','cases.json','research.html','research.css','research.js','moods.js','ads.txt','favicon.svg','share.png','robots.txt','sitemap.xml','_routes.json','_headers']) await copyFile('web/'+f,'dist/'+f);
await writeFile('dist/config.json',JSON.stringify({mode,apiOrigin:url}));

for(const file of ['listening-notes.html','index.html','study.html','research.html','privacy.html']){
 let html=await readFile('dist/'+file,'utf8');
 for(const match of [...html.matchAll(/(?:src|href)="\.?\/([\w.-]+\.(?:css|js))(?:\?[^"]*)?"/g)]){
  const hash=createHash('sha256').update(await readFile('dist/'+match[1])).digest('hex').slice(0,12);
  html=html.replace(match[0],match[0].split('=')[0]+'="./'+match[1]+'?v='+hash+'"');
 }
 await writeFile('dist/'+file,html);
}

const articlePages = new Set(['study.html','listening-notes.html']);
for (const file of await readdir('dist')) {
 if (!file.endsWith('.html')) continue;
 const html = await readFile('dist/'+file,'utf8');
 const loaders = html.match(/<script\b[^>]*\bsrc=["']https:\/\/pagead2\.googlesyndication\.com\/pagead\/js\/adsbygoogle\.js\?[^"']+["'][^>]*>/gi)||[];
 if (loaders.length !== Number(articlePages.has(file))) throw Error('Unexpected AdSense placement: '+file);
}
