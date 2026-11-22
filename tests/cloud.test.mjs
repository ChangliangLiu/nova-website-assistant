import test from 'node:test';import assert from 'node:assert/strict';import {handle} from '../cloud/worker.mjs';
const url='https://nova-website-assistant.example';const site={site:'alpine',parentOrigin:'https://alpine-outfitters-demo.pages.dev'};
const env={ASSETS:{fetch:async()=>new Response('asset')},PCC_API_KEY:'test',SESSION_IP_LIMITER:{limit:async()=>({success:true})},SESSION_TOTAL_LIMITER:{limit:async()=>({success:true})}};
const post=(body,origin=url)=>new Request(url+'/api/widget/session',{method:'POST',headers:{origin,'cf-connecting-ip':'192.0.2.1'},body:JSON.stringify(body)});
test('registered site configuration and origin validation',async()=>{
 const config=await handle(new Request(url+'/api/widget/config?'+new URLSearchParams(site)),env);
 assert.equal(config.status,200);assert.equal((await config.json()).preconnect,true);
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
test('Onyx search enforces the configured document set and preserves safe sources',async()=>{
 const original=globalThis.fetch;let body;
 globalThis.fetch=async(url,opts)=>{assert.equal(url.pathname,'/api/search/send-search-message');body=JSON.parse(opts.body);return Response.json({search_docs:[{semantic_identifier:'Returns',content:'Return within 30 days.',link:'https://shop.example/returns'},{semantic_identifier:'Bad',content:'Example',link:'javascript:alert(1)'}],error:null})};
 try{
  const request=new Request(url+'/api/widget/search',{method:'POST',headers:{origin:url},body:JSON.stringify({...site,query:'return policy',document_set:'private'})});
  const response=await handle(request,{...env,ONYX_API_KEY:'private-token',ONYX_DOCUMENT_SET:'Alpine Public'});
  assert.equal(response.status,200);const result=await response.json();
  assert.deepEqual(body.filters,{document_set:['Alpine Public']});assert.equal(result.provider,'onyx');
  assert.equal(result.sources[0].url,'https://shop.example/returns');assert.equal(result.passages[1].url,'');
  assert.equal(JSON.stringify(result).includes('private-token'),false);
 }finally{globalThis.fetch=original}
});

test('Onyx search fails closed without a configured document set',async()=>{
 const request=new Request(url+'/api/widget/search',{method:'POST',headers:{origin:url},body:JSON.stringify({...site,query:'return policy'})});
 const response=await handle(request,{...env,ONYX_API_KEY:'private-token'});
 assert.equal(response.status,503);
});
