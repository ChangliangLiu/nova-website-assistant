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
