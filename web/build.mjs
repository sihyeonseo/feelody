import {mkdir,copyFile,writeFile,rm} from 'node:fs/promises';
const mode=process.env.FEELODY_WEB_MODE==='local'?'local':'llm';
const url=mode==='local'?(process.env.FEELODY_API_ORIGIN||'').trim():'';
if(url && (!/^https:\/\//.test(url)||new URL(url).origin!==url)) throw Error('FEELODY_API_ORIGIN must be an HTTPS origin without a trailing slash');
await rm('dist',{recursive:true,force:true});
await mkdir('dist');
for(const f of ['index.html','study.html','app.js','style.css','cases.json','research.html','research.css','research.js','moods.js','ads.txt','favicon.svg','share.png','robots.txt','sitemap.xml']) await copyFile('web/'+f,'dist/'+f);
await writeFile('dist/config.json',JSON.stringify({mode,apiOrigin:url}));
