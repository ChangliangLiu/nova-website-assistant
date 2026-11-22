import sites from '../agent/knowledge/sites.json' with { type: 'json' };
import {searchSite} from './site-knowledge.mjs';
import {searchCloudflare} from './cloudflare-search.mjs';
import {searchOnyx} from './onyx-search.mjs';
const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
function siteFor(id,origin){const s=Object.hasOwn(sites,id)?sites[id]:null;return s?.allowedOrigins?.includes(origin)?s:null}
export async function handle(request,env){
 const u=new URL(request.url);
 if(u.pathname==='/widget.js')return env.ASSETS.fetch(request);
 if(u.pathname.startsWith('/assets/'))return env.ASSETS.fetch(new Request(new URL(u.pathname.slice('/assets'.length),u),request));
 if(u.pathname==='/embed'){
  const site=siteFor(u.searchParams.get('site'),u.searchParams.get('parentOrigin'));if(!site)return new Response('Website not registered.',{status:403});
  const r=await env.ASSETS.fetch(new Request(new URL('/embed',u),request));if(!r.ok)return new Response('Widget assets unavailable.',{status:503});const html=await r.text();
  return new Response(html.replace('<script type="module"','<script>globalThis.NOVA_CLOUD=true</script><script type="module"'),{headers:{'Content-Type':'text/html; charset=utf-8','Content-Security-Policy':"frame-ancestors 'self' "+site.allowedOrigins.join(' '),'Cache-Control':'no-store'}});
 }
 if(u.pathname==='/api/widget/config' && request.method==='GET'){
  const s=siteFor(u.searchParams.get('site'),u.searchParams.get('parentOrigin'));if(!s)return json({detail:'Website not registered.'},403);
  const phoneNumber=env.PHONE_SITE_ID===s.siteId&&/^\+[1-9]\d{7,14}$/.test(env.PHONE_NUMBER||'')?env.PHONE_NUMBER:null;
  return json({name:s.name,documentCount:s.documents.length,ready:!!env.PCC_API_KEY,prompts:s.suggestions||[],phoneNumber,preconnect:s.preconnect===true});
 }
 if(!['/api/widget/session','/api/widget/search'].includes(u.pathname)||request.method!=='POST')return env.ASSETS.fetch(request);
 if(request.headers.get('origin')!==u.origin)return json({detail:'Invalid origin'},403);
 let body;try{const raw=await request.text();if(raw.length>10000)return json({detail:'Request too large'},413);body=JSON.parse(raw)}catch{return json({detail:'Invalid request'},400)}
 const s=siteFor(body?.site,body?.parentOrigin);if(!s)return json({detail:'Website not registered.'},403);
 if(u.pathname.endsWith('/search')){try{return json(await (env.NOVA_SEARCH_PROVIDER==='onyx'?searchOnyx(body.query,s,env):env.NOVA_SEARCH_PROVIDER==='cloudflare'?searchCloudflare(body.query,s,env):searchSite(body.query,s)))}catch{return json({detail:'Search unavailable or invalid query.'},503)}}
 if(!env.PCC_API_KEY||!env.SESSION_IP_LIMITER||!env.SESSION_TOTAL_LIMITER)return json({detail:'Conversation service unavailable.'},503);
 const ip=request.headers.get('cf-connecting-ip');if(!ip)return json({detail:'Conversation service unavailable.'},503);
 const [a,b]=await Promise.all([env.SESSION_IP_LIMITER.limit({key:ip}),env.SESSION_TOTAL_LIMITER.limit({key:'sessions'})]);if(!a.success||!b.success)return json({detail:'Too many conversations. Try again shortly.'},429);
 let page='';try{if(new URL(body.pageUrl).origin===s.origin)page=body.pageUrl.slice(0,2048)}catch{}
 let response;try{response=await fetch('https://api.pipecat.daily.co/v1/public/'+encodeURIComponent(env.PCC_AGENT_NAME||'nova-website-assistant')+'/start',{method:'POST',headers:{'Authorization':'Bearer '+env.PCC_API_KEY,'Content-Type':'application/json'},body:JSON.stringify({createDailyRoom:true,body:{site:s.siteId,parentOrigin:body.parentOrigin,pageUrl:page}}),signal:AbortSignal.timeout(30000)})}catch{return json({detail:'Could not reach Pipecat Cloud.'},502)}
 if(!response.ok)return json({detail:'Could not start the Pipecat conversation. Please try again.'},502);
 const data=await response.json();if(!data.dailyRoom||!data.dailyToken)return json({detail:'Pipecat returned incomplete session details.'},502);
 return json({dailyRoom:data.dailyRoom,dailyToken:data.dailyToken});
}
export default {fetch:handle};
