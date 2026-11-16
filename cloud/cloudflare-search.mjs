// Retrieve only from the instance configured on the server, never client input.
export async function searchCloudflare(query, site, env) {
 if(typeof query!=='string'||!query.trim()||query.length>2048)throw Error('Invalid query');
 if(!/^[a-f0-9]{32}$/.test(env.CF_ACCOUNT_ID||'')||!/^[a-z0-9][a-z0-9-]{0,27}$/.test(env.CF_AI_SEARCH_NAMESPACE||'')||!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(env.CF_AI_SEARCH_INSTANCE||'')||!env.CF_AI_SEARCH_TOKEN)throw Error('Search unavailable');
 const url=`https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/ai-search/namespaces/${env.CF_AI_SEARCH_NAMESPACE}/instances/${env.CF_AI_SEARCH_INSTANCE}/search`;
 const res=await fetch(url,{method:'POST',headers:{Authorization:`Bearer ${env.CF_AI_SEARCH_TOKEN}`,'Content-Type':'application/json'},body:JSON.stringify({query}),signal:AbortSignal.timeout(12000),redirect:'manual'});
 if(!res.ok)throw Error('Search unavailable');const d=await res.json();if(d.success!==true||!Array.isArray(d.result?.chunks))throw Error('Search unavailable');
 const passages=[],sources=[];for(const c of d.result.chunks.slice(0,8)){if(typeof c?.text!=='string')continue;const item=c.item||{},metadata=item.metadata||{};let url=metadata.url||metadata.source_url||item.key||'';try{let p=new URL(url);if(!['https:','http:'].includes(p.protocol)||p.username||p.password)url=''}catch{url=''}
 const p={title:String(metadata.title||item.key||'Document').slice(0,200),content:c.text.slice(0,15000),url,citationId:passages.length+1};passages.push(p);if(url)sources.push({id:String(p.citationId),title:p.title,url,excerpt:p.content.slice(0,240),citationId:p.citationId});}
 return {provider:'cloudflare',siteId:site.siteId,passages,sources};
}
