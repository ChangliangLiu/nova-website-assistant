// Retrieve only from the administrator-configured Onyx document set.
export async function searchOnyx(query, site, env) {
 if(typeof query!=='string'||!query.trim()||query.length>2048)throw Error('Invalid query');
 if(!env.ONYX_API_KEY||typeof env.ONYX_DOCUMENT_SET!=='string'||!env.ONYX_DOCUMENT_SET.trim())throw Error('Search unavailable');
 const origin=new URL(env.ONYX_URL||'https://cloud.onyx.app');
 if((origin.protocol!=='https:'&&!(origin.protocol==='http:'&&['localhost','127.0.0.1','[::1]'].includes(origin.hostname)))||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw Error('Invalid Onyx URL');
 const response=await fetch(new URL('/api/search/send-search-message',origin),{method:'POST',headers:{Authorization:`Bearer ${env.ONYX_API_KEY}`,'Content-Type':'application/json'},body:JSON.stringify({search_query:query,filters:{document_set:[env.ONYX_DOCUMENT_SET.trim()]},run_query_expansion:false,num_hits:8,include_content:true,stream:false}),signal:AbortSignal.timeout(12000),redirect:'manual'});
 if(!response.ok)throw Error('Search unavailable');
 const data=await response.json();if(data.error||!Array.isArray(data.search_docs))throw Error('Search unavailable');
 const passages=[],sources=[];
 for(const item of data.search_docs.slice(0,8)){
  if(!item||typeof item!=='object')continue;
  const content=item.content||item.blurb;if(typeof content!=='string'||!content.trim())continue;
  const title=String(item.semantic_identifier||item.title||'Document').slice(0,200);
  let url=item.link||'';try{const p=new URL(url);if(!['https:','http:'].includes(p.protocol)||p.username||p.password)url=''}catch{url=''}
  const p={title,content:content.slice(0,15000),url,citationId:passages.length+1};passages.push(p);
  if(url)sources.push({id:String(p.citationId),title,url,excerpt:p.content.slice(0,240),citationId:p.citationId});
 }
 return {provider:'onyx',siteId:site.siteId,passages,sources};
}
