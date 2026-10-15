import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RedisStore, type RedisApi } from './redis-store.ts';

function fixture(aborted = false, failure = false) {
  const calls: string[] = [];
  const expiration: Date[] = [];
  const api: RedisApi = {
    async get() { calls.push('read'); return 'reviewed-draft'; },
    async watch(...keys) {
      calls.push(`watch:${keys.join(',')}`);
      return {
        async multi() { calls.push('multi'); },
        async set(_key, _value, options) { calls.push('set'); expiration.push(options.expiration); },
        async del() { calls.push('del'); },
        async exec() { calls.push('exec'); if (failure) throw new Error('connection lost'); return aborted ? [] : ['OK', 1]; },
        async discard() { calls.push('discard'); },
      };
    },
  };
  return { storage: new RedisStore(api), calls, expiration };
}

test('Redis reservations watch every key before reads and apply fixed deadlines inside MULTI', async () => {
  const f = fixture();
  const result = await f.storage.atomic(['draft', 'daily'], values => {
    assert.equal(values.draft, 'reviewed-draft');
    return { writes: [{ key: 'daily', value: '1', expiresAt: 1800000000000 }, { key: 'draft', value: null }], result: 'reserved' };
  });
  assert.equal(result, 'reserved');
  assert.deepEqual(f.calls, ['watch:draft,daily', 'read', 'read', 'multi', 'set', 'del', 'exec']);
  assert.equal(f.expiration[0].getTime(), 1800000000000);
});

test('an aborted Redis transaction cannot authorize a publish', async () => {
  const f = fixture(true);
  await assert.rejects(f.storage.atomic(['draft'], () => ({
    writes: [{ key: 'draft', value: 'reserved', expiresAt: 1800000000000 }], result: 'authorized',
  })), /Another action/);
  assert.ok(f.calls.includes('discard'));
});

test('Redis transport errors fail closed instead of returning an authorized reservation', async () => {
  const f = fixture(false, true);
  await assert.rejects(f.storage.atomic(['draft'], () => ({
    writes: [{ key: 'draft', value: 'reserved', expiresAt: 1800000000000 }], result: 'authorized',
  })), /could not be verified/);
});

test('no Redis content can be written without a retention deadline', async () => {
  const f = fixture();
  await assert.rejects(f.storage.atomic(['draft'], () => ({
    writes: [{ key: 'draft', value: 'unbounded' }], result: 'authorized',
  })), /retention deadline/);
  assert.ok(!f.calls.includes('exec'));
});
