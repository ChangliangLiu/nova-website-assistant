import test from 'node:test';
import assert from 'node:assert/strict';
import {SessionPreparation} from '../web/preconnect.js';

test('prepares once and hands the session to the connect action', async () => {
  let calls=0;
  const preparation=new SessionPreparation(async (data,signal)=>{calls++;assert.equal(signal.aborted,false);return data},1000);
  preparation.start({dailyRoom:'room'}); preparation.start({dailyRoom:'other'});
  assert.deepEqual(await preparation.take(),{dailyRoom:'room'});
  assert.equal(preparation.take(),null); assert.equal(calls,1);
});

test('discarding preparation aborts the pending request', async () => {
  let signal;
  const preparation=new SessionPreparation(async (_,s)=>{signal=s;return new Promise(resolve=>s.addEventListener('abort',()=>resolve(null)))},1000);
  preparation.start({}); await Promise.resolve(); preparation.cancel();
  assert.equal(signal.aborted,true); assert.equal(preparation.take(),null);
});

test('unused sessions expire and are not reused', async () => {
  const preparation=new SessionPreparation(async ()=>({dailyRoom:'room'}),5);
  preparation.start({}); await new Promise(resolve=>setTimeout(resolve,15));
  assert.equal(preparation.take(),null);
});
