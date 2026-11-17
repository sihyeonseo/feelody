import {mkdir,copyFile,writeFile,rm} from 'node:fs/promises';
const url=(process.env.FEELODY_API_ORIGIN||'').trim();
if(url && (!/^https:\/\//.test(url)||new URL(url).origin!==url)) throw Error('FEELODY_API_ORIGIN must be an HTTPS origin without a trailing slash');
await rm('dist',{recursive:true,force:true});
await mkdir('dist');
for(const f of ['index.html','app.js','style.css','cases.json']) await copyFile('web/'+f,'dist/'+f);
await writeFile('dist/config.json',JSON.stringify({apiOrigin:url}));
