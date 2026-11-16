import {PipecatClient} from '@pipecat-ai/client-js';
import {SmallWebRTCTransport} from '@pipecat-ai/small-webrtc-transport';
import {DailyTransport} from '@pipecat-ai/daily-transport';
import {connectClient} from './connection.js';
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const site = params.get('site') || '', parentOrigin = params.get('parentOrigin') || '';
let pageUrl = '', client = null, connected = false, config = null, connecting = false;
let botMessage = null;
const post = (type, extra={}) => { if(parentOrigin) parent.postMessage({channel:'avatar-assistant',type,...extra}, parentOrigin); };
function error(message) { $('error').hidden=!message; $('error').textContent=message || ''; }
function message(role,text,sources=[]) {
  $('welcome')?.remove();
  const item=document.createElement('div'); item.className='ne-message '+role;
  const label=document.createElement('small'); label.textContent=role==='user'?'YOU':role==='source'?'SOURCES':'NOVA'; item.append(label);
  if(text){const p=document.createElement('p');p.textContent=text;item.append(p);}
  for(const source of sources){try{const url=new URL(source.url);if(!['https:','http:'].includes(url.protocol))continue;const a=document.createElement('a');a.href=url.href;a.target='_blank';a.rel='noreferrer';a.textContent=source.title+' ↗';item.append(a)}catch{}}
  $('transcript').append(item);item.scrollIntoView({block:'nearest'});return item;
}
function reset(){ $('phone').hidden=!config?.phoneNumber;connected=false;connecting=false;client=null;$('connect').textContent='▷ Connect live avatar';$('connect').disabled=!config?.ready;$('status').textContent='Avatar preview';$('avatar').srcObject=null;$('audio').srcObject=null;$('avatar').classList.add('ne-hidden');$('preview').hidden=false;$('footer').textContent=config?.documentCount ? `${config.documentCount} source pages` : 'Knowledge sources connected';post('microphone',{enabled:false}); }
async function connect(){
 if(connecting){const c=client;reset();void c?.disconnect().catch(()=>{});return;}
 if(connected){const c=client;reset();await c?.disconnect();return;}
 connecting=true;error('');$('phone').hidden=true;$('connect').disabled=false;$('connect').textContent='End conversation';$('status').textContent='Connecting…';
 const cloud=globalThis.NOVA_CLOUD === true;
 const current=new PipecatClient({transport:cloud?new DailyTransport():new SmallWebRTCTransport({iceServers:[{urls:'stun:stun.l.google.com:19302'}]}),enableMic:true,enableCam:false,callbacks:{
  onTrackStarted(track,participant){if(participant?.local)return;if(track.kind==='video'){$('avatar').srcObject=new MediaStream([track]);$('avatar').classList.remove('ne-hidden');$('preview').hidden=true}else if(track.kind==='audio'){$('audio').srcObject=new MediaStream([track]);$('audio').play().catch(()=>error('Your browser blocked audio playback.'))}},
  onDisconnected(){if(client===current)reset()},
  onError(e){error(e?.data?.error||e?.data?.message||'The live connection needs attention.')},
  onUserInput(data){if(data.final && data.input_type==='transcription' && data.text)message('user',data.text)},
  onBotLlmStarted(){botMessage=null},
  onBotOutput(data){if(!data.text || data.output_type==='word')return;if(!botMessage)botMessage=message('assistant','');let p=botMessage.querySelector('p');if(!p){p=document.createElement('p');botMessage.append(p)}p.textContent+=data.text},
  onServerMessage(data){if(data?.type==='sources' && data.sources?.length)message('source','Website sources',data.sources)}
 }});
 client=current;
 try{await connectClient(current,{cloud,requestData:{site,parentOrigin,pageUrl},isCurrent:()=>client===current});if(client!==current)return;connected=true;connecting=false;$('connect').disabled=false;$('connect').textContent='End conversation';$('status').textContent='Live avatar';$('footer').textContent='Microphone on · sent to Zoom';post('microphone',{enabled:true})}
 catch(e){if(client===current){reset();void current.disconnect().catch(()=>{});error(e?.message||'Could not connect to the avatar.')}}
}
async function ask(text){text=text.trim();if(!text)return;error('');$('query').value='';message('user',text);
 try{if(connected){await client.sendText(text)}else{const r=await fetch('/api/widget/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site,parentOrigin,query:text})});const d=await r.json();if(!r.ok)throw Error(d.detail||'Search failed');message('assistant',d.passages.length?'Here are relevant passages from the available knowledge. Connect the live avatar to talk them through.':'I could not find this in the available knowledge.',d.sources);for(const p of d.passages.slice(0,2))message('excerpt',p.content,[p])}}
 catch(e){error(e.message||'Could not send your question.')}
}
$('connect').onclick=()=>void connect();$('minimize').onclick=()=>post('close');$('form').onsubmit=e=>{e.preventDefault();void ask($('query').value)};
window.addEventListener('message',e=>{if(e.source!==parent||e.origin!==parentOrigin||e.data?.channel!=='avatar-assistant')return;if(e.data.type==='context'&&typeof e.data.url==='string')pageUrl=e.data.url;if(e.data.type==='ask'&&typeof e.data.text==='string')void ask(e.data.text.slice(0,2000));if(e.data.type==='destroy'){const c=client;reset();void c?.disconnect().catch(()=>{})}});
fetch('/api/widget/config?'+new URLSearchParams({site,parentOrigin})).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.detail||'Site unavailable');config=d;if(/^\+[1-9]\d{7,14}$/.test(d.phoneNumber||'')){$('phone').href='tel:'+d.phoneNumber;$('phone').textContent='Call '+d.phoneNumber;$('phone').hidden=false}else{config.phoneNumber=null}$('site-name').textContent=d.name;$('footer').textContent=d.documentCount ? `${d.documentCount} source pages` : 'Knowledge sources connected';$('connect').disabled=!d.ready;for(const p of d.prompts){const b=document.createElement('button');b.textContent=p+' ↗';b.onclick=()=>void ask(p);$('prompts').append(b)}}).catch(e=>{error(e.message);$('connect').disabled=true});
post('ready');
