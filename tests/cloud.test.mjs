import test from 'node:test';import assert from 'node:assert/strict';import {handle} from '../cloud/worker.mjs';
const url='https://nova-website-assistant.example';const site={site:'alpine',parentOrigin:'https://alpine-outfitters-demo.pages.dev'};
const env={ASSETS:{fetch:async()=>new Response('asset')},PCC_API_KEY:'test',SESSION_IP_LIMITER:{limit:async()=>({success:true})},SESSION_TOTAL_LIMITER:{limit:async()=>({success:true})}};
const post=(body,origin=url)=>new Request(url+'/api/widget/session',{method:'POST',headers:{origin,'cf-connecting-ip':'192.0.2.1'},body:JSON.stringify(body)});
test('registered site configuration and origin validation',async()=>{
 assert.equal((await handle(new Request(url+'/api/widget/config?'+new URLSearchParams(site)),env)).status,200);
 assert.equal((await handle(post(site,'https://evil.example'),env)).status,403);
 assert.equal((await handle(post({...site,parentOrigin:'https://evil.example'}),env)).status,403);
});
test('session fails closed without rate limit and enforces throttling',async()=>{
 assert.equal((await handle(post(site),{...env,SESSION_IP_LIMITER:undefined})).status,503);
 assert.equal((await handle(post(site),{...env,SESSION_IP_LIMITER:{limit:async()=>({success:false})}})).status,429);
});
test('session-start credentials stay server side',async()=>{
 const original=globalThis.fetch;globalThis.fetch=async(url,opts)=>{assert.match(opts.headers.Authorization,/^Bearer /);assert.equal(JSON.parse(opts.body).body.site,'alpine');return Response.json({dailyRoom:'https://example.daily.co/room',dailyToken:'visitor-token'})};
 try{const r=await handle(post(site),env);assert.equal(r.status,200);const v=await r.json();assert.equal(v.dailyToken,'visitor-token');assert.ok(!JSON.stringify(v).includes('test'))}finally{globalThis.fetch=original}
});
test('phone option is published only for its configured site and valid number',async()=>{
 const config=new Request(url+'/api/widget/config?'+new URLSearchParams(site));
 const number='+14255550100';
 const shown=await (await handle(config,{...env,PHONE_SITE_ID:'alpine',PHONE_NUMBER:number})).json();
 assert.equal(shown.phoneNumber,number);
 const wrongSite=await (await handle(config,{...env,PHONE_SITE_ID:'other',PHONE_NUMBER:number})).json();
 assert.equal(wrongSite.phoneNumber,null);
 const invalid=await (await handle(config,{...env,PHONE_SITE_ID:'alpine',PHONE_NUMBER:'not a phone number'})).json();
 assert.equal(invalid.phoneNumber,null);
});
test('pre-conversation search uses the registered website snapshot by default',async()=>{
 const request=new Request(url+'/api/widget/search',{method:'POST',headers:{origin:url},body:JSON.stringify({...site,query:'return policy'})});
 const response=await handle(request,env);assert.equal(response.status,200);
 const result=await response.json();assert.equal(result.provider,'website');
 assert.ok(result.sources.some(s=>s.url.includes('/guides/returns/')));
});

test('Cloudflare search uses server-configured instance and returns document content',async()=>{
 const {searchCloudflare}=await import('../cloud/cloudflare-search.mjs');
 const previous=globalThis.fetch;let seen;
 globalThis.fetch=async (url,options)=>{seen={url,options};return Response.json({success:true,result:{chunks:[{text:'A useful passage',item:{key:'guide.pdf'}}]}})};
 try{let env={CF_ACCOUNT_ID:'a'.repeat(32),CF_AI_SEARCH_NAMESPACE:'default',CF_AI_SEARCH_INSTANCE:'shop',CF_AI_SEARCH_TOKEN:'private-token'};let result=await searchCloudflare('question',{siteId:'alpine'},env);assert.match(seen.url,/instances\/shop\/search$/);assert.equal(result.passages[0].content,'A useful passage');assert.equal(result.sources.length,0);assert.equal(JSON.stringify(result).includes('private-token'),false)}finally{globalThis.fetch=previous}
});

test('widget search uses Cloudflare when configured',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async()=>Response.json({success:true,result:{chunks:[{text:'Cloudflare guide',item:{key:'guide.pdf'}}]}});
 try{
  const request=new Request(url+'/api/widget/search',{method:'POST',headers:{origin:url},body:JSON.stringify({...site,query:'guide'})});
  const config={...env,NOVA_SEARCH_PROVIDER:'cloudflare',CF_ACCOUNT_ID:'a'.repeat(32),CF_AI_SEARCH_NAMESPACE:'default',CF_AI_SEARCH_INSTANCE:'shop',CF_AI_SEARCH_TOKEN:'private-token'};
  const response=await handle(request,config);assert.equal(response.status,200);
  const result=await response.json();assert.equal(result.provider,'cloudflare');assert.equal(result.passages[0].content,'Cloudflare guide');
 }finally{globalThis.fetch=original}
});
