export const words=s=>(String(s).toLowerCase().match(/[a-z0-9]+/g)||[]).filter(t=>!new Set(['a','an','and','are','as','at','be','by','can','do','does','for','from','how','i','in','is','it','me','my','of','on','or','our','the','this','to','we','what','which','with','you','your','please','tell','about']).has(t)).map(t=>({refunds:'refund',returns:'return',skis:'ski',boots:'boot',bindings:'binding',beginners:'beginner',goggles:'goggle',mountains:'mountain',shipping:'shipping',cheapest:'budget',cheap:'budget'}[t]||t));
export function searchSite(query,site){
 if(typeof query!=='string'||!query.trim()||query.length>2048)throw Error('Enter a question between 1 and 2,048 characters.');
 const terms=[...new Set(words(query))];const docs=site.documents;const tokenized=docs.map(d=>words(d.title+' '+d.content+' '+d.tags.join(' ')));const avg=tokenized.reduce((s,t)=>s+t.length,0)/docs.length;
 const ranked=docs.map((d,i)=>{let score=0;for(const term of terms){const tf=tokenized[i].filter(t=>t===term).length;if(!tf)continue;const df=tokenized.filter(ts=>ts.includes(term)).length;const idf=Math.log(1+(docs.length-df+.5)/(df+.5));score+=idf*tf*2.2/(tf+1.2*(.25+.75*tokenized[i].length/avg));if(words(d.title).includes(term))score+=idf*1.5;if(d.tags.some(t=>words(t).includes(term)))score+=idf*.5;}return{d,score}}).filter(r=>r.score>0).sort((a,b)=>b.score-a.score).slice(0,3);
 const passages=ranked.map(({d},i)=>({title:d.title,content:d.content,url:d.url,citationId:i+1}));
 const sources=passages.map(p=>({id:String(p.citationId),title:p.title,url:p.url,excerpt:p.content.slice(0,240),citationId:p.citationId}));
 return {provider:'website',siteId:site.siteId,passages,sources};
}
