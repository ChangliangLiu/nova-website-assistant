import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
const [input,origins]=process.argv.slice(2);
if(!input||!origins){console.error('Usage: node scripts/import-site.mjs <feed.json|https://site/assistant-content.json> <comma-separated allowed origins>');process.exit(1)}
let raw;if(input.startsWith('https://')){const r=await fetch(input,{redirect:'error',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Feed returned HTTP '+r.status);raw=await r.text();}else raw=await readFile(resolve(input),'utf8');
if(raw.length>180000)throw Error('Feed exceeds the 180 KB inline-dispatch limit; configure a retrieval adapter for larger sites.');
const feed=JSON.parse(raw);if(feed.version!==1||!/^[a-z][a-z0-9-]{0,39}$/.test(feed.siteId)||typeof feed.name!=='string'||!feed.name.trim()||feed.name.length>100||typeof feed.description!=='string'||feed.description.length>2000||!Array.isArray(feed.documents)||!feed.documents.length||feed.documents.length>100)throw Error('Invalid v1 site feed');
const base=new URL(feed.origin);if(!['https:','http:'].includes(base.protocol)||base.origin!==feed.origin||base.username||base.password)throw Error('Feed origin must be an origin without path or credentials');
if(feed.suggestions!==undefined&&(!Array.isArray(feed.suggestions)||feed.suggestions.length>5||feed.suggestions.some(s=>typeof s!=='string'||s.length>200)))throw Error('Invalid suggested questions');
const seen=new Set();for(const d of feed.documents){const u=new URL(d.url);if(u.origin!==base.origin||u.username||u.password||typeof d.id!=='string'||seen.has(d.id)||typeof d.title!=='string'||typeof d.content!=='string'||!d.content.trim()||d.content.length>15000||d.title.length>200||!Array.isArray(d.tags)||d.tags.some(t=>typeof t!=='string'||t.length>100))throw Error('Invalid or cross-origin document');seen.add(d.id)}
const allowedOrigins=origins.split(',').map(s=>s.trim());for(const o of allowedOrigins){const u=new URL(o);if(u.origin!==o||!(u.protocol==='https:'||(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname))))throw Error('Allowed origins require HTTPS (localhost HTTP allowed)')}
const target=new URL('../agent/knowledge/sites.json',import.meta.url);let sites={};try{sites=JSON.parse(await readFile(target,'utf8'))}catch(e){if(e.code!=='ENOENT')throw e}
const {documents, ...siteConfig}=feed;
sites[feed.siteId]={...siteConfig,allowedOrigins};await mkdir(new URL('../agent/knowledge/',import.meta.url),{recursive:true});await writeFile(target,JSON.stringify(sites,null,2)+'\n');console.log(`Registered ${feed.siteId}. Index the website and documents in Onyx separately. Restart the local agent or rebuild and deploy both the cloud agent and Worker.`);
