import test from 'node:test';
import assert from 'node:assert/strict';
import {connectClient} from '../web/connection.js';

test('microphone initializes before the cloud session starts', async () => {
  const calls = [];
  const client = {
    async initDevices() { calls.push('devices'); },
    async startBot(params) { calls.push(params.endpoint); return {room: 'test'}; },
    async connect(params) { assert.deepEqual(params, {room: 'test'}); calls.push('connect'); },
    async disconnect() { calls.push('disconnect'); }
  };
  await connectClient(client, {cloud: true, requestData: {}, isCurrent: () => true});
  assert.deepEqual(calls, ['devices', '/api/widget/session', 'connect']);
});

test('a cancelled permission prompt cannot start a later cloud session', async () => {
  let finishPermission, active = true, starts = 0, disconnects = 0;
  const client = {
    initDevices: () => new Promise(resolve => { finishPermission = resolve; }),
    async startBot() { starts++; },
    async disconnect() { disconnects++; }
  };
  const pending = connectClient(client, {cloud: true, requestData: {}, isCurrent: () => active});
  active = false;
  finishPermission();
  await pending;
  assert.equal(starts, 0);
  assert.equal(disconnects, 1);
});

test('a permission prompt that never finishes times out', async () => {
  const client = {initDevices: () => new Promise(() => {})};
  await assert.rejects(connectClient(client, {cloud: true, requestData: {}, isCurrent: () => true, timeoutMs: 10}), /timed out/);
});

test('connect uses a prepared session only after microphone initialization', async () => {
  const calls = [];
  const client = {
    async initDevices() { calls.push('devices'); },
    async startBot() { throw Error('should reuse prepared session'); },
    async connect(params) { assert.deepEqual(params, {dailyRoom:'room', dailyToken:'token'}); calls.push('connect'); },
    async disconnect() { calls.push('disconnect'); }
  };
  await connectClient(client, {cloud:true, requestData:{}, isCurrent:()=>true,
    prepared:Promise.resolve({dailyRoom:'room', dailyToken:'token'})});
  assert.deepEqual(calls, ['devices', 'connect']);
});

test('a failed preparation falls back to the normal session start', async () => {
  let starts = 0;
  const client = {async initDevices(){}, async startBot(){starts++;return {room:'fallback'}},
    async connect(params){assert.equal(params.room,'fallback')}, async disconnect(){}};
  await connectClient(client, {cloud:true, requestData:{}, isCurrent:()=>true, prepared:Promise.resolve(null)});
  assert.equal(starts, 1);
});

test('cancelling during microphone permission never joins a prepared session', async () => {
  let finish, active = true, connects = 0, disconnects = 0;
  const client = {initDevices:()=>new Promise(resolve=>{finish=resolve}), async connect(){connects++},
    async disconnect(){disconnects++}};
  const pending=connectClient(client,{cloud:true,requestData:{},isCurrent:()=>active,prepared:Promise.resolve({room:'test'})});
  active=false; finish(); await pending;
  assert.equal(connects,0); assert.equal(disconnects,1);
});
