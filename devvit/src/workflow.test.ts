import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Workflow, WorkflowError, checkActor, eventPostId, settingText, keys, DRAFT_MS, HISTORY_MS, similar,
  type Actor, type Policy, type Source, type Storage, type Write } from './workflow.ts';

const actor: Actor = { userId: 't2_operator', username: 'saurabhimapro', subredditId: 't5_python', subredditName: 'learnpython', postId: 't3_abc' };
const policy: Policy = { mode: 'approved', community: 'learnpython', operator: 'saurabhimapro',
  permissionReference: 'offline-test-permission', communityPermission: 'offline-test-community',
  privacyContact: 'operator@example.invalid', privacyUrl: 'https://example.invalid/privacy', rulesReviewedOn: '2026-10-14' };
const initialTime = Date.parse('2026-10-14T12:00:00Z');

class MemoryStore implements Storage {
  values = new Map<string, { value: string; expiresAt: number }>();
  now = initialTime;
  tail: Promise<void> = Promise.resolve();
  async get(key: string) {
    const item = this.values.get(key);
    if (item && item.expiresAt <= this.now) { this.values.delete(key); return undefined; }
    return item?.value;
  }
  async atomic<T>(keys: string[], change: (values: Record<string, string | undefined>) => { writes: Write[]; result: T }): Promise<T> {
    let release!: () => void;
    const previous = this.tail;
    this.tail = new Promise<void>(resolve => { release = resolve; });
    await previous;
    try {
      const values: Record<string, string | undefined> = {};
      for (const key of keys) values[key] = await this.get(key);
      const update = change(values);
      for (const write of update.writes) {
        if (write.value === null) this.values.delete(write.key);
        else this.values.set(write.key, { value: write.value, expiresAt: write.expiresAt! });
      }
      return update.result;
    } finally { release(); }
  }
}

function fixture() {
  const storage = new MemoryStore();
  const sources = new Map<string, Source>();
  const makeSource = (id = 't3_abc'): Source => ({ id, community: 'learnpython', title: 'Python question', body: 'Question body',
    authorAvailable: true, removed: false, locked: false, archived: false, nsfw: false, quarantined: false, public: true });
  sources.set(actor.postId, makeSource());
  let reads = 0;
  const submissions: { postId: string; body: string }[] = [];
  let failSource = false, failSubmit = false;
  const workflow = new Workflow({ storage, now: () => storage.now,
    async source(id) { reads++; if (failSource || !sources.has(id)) throw new Error('offline'); return sources.get(id)!; },
    async submit(postId, body) { submissions.push({ postId, body }); if (failSubmit) throw new Error('timeout'); return 'https://www.reddit.com/r/learnpython/comments/abc/reply/'; },
  });
  return { storage, workflow, sources, submissions, makeSource, reads: () => reads,
    failSource: () => { failSource = true; }, failSubmit: () => { failSubmit = true; } };
}

test('write -> review -> explicit publish uses exactly the saved human text once', async () => {
  const f = fixture();
  const saved = await f.workflow.save(actor, policy, '  Answer with a concrete Python example.  ');
  assert.equal(f.submissions.length, 0);
  await f.workflow.review(actor, policy, saved.draft.token);
  const url = await f.workflow.publish(actor, policy, saved.draft.token, true);
  assert.ok(url.startsWith('https://www.reddit.com/'));
  assert.deepEqual(f.submissions, [{ postId: actor.postId, body: saved.draft.body }]);
  await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), WorkflowError);
  assert.equal(f.submissions.length, 1);
});

for (const [name, change] of Object.entries({ disabled: { mode: 'disabled' }, missingPermission: { permissionReference: '' },
  noCommunityPermission: { communityPermission: '' }, noContact: { privacyContact: '' }, noPrivacyUrl: { privacyUrl: '' },
  oldRules: { rulesReviewedOn: '2026-09-01' }, invalidDate: { rulesReviewedOn: '2026-02-30' } })) {
  test(`policy blocks ${name} before any Reddit read`, async () => {
    const f = fixture();
    await assert.rejects(f.workflow.save(actor, { ...policy, ...change }, 'A useful reply'), WorkflowError);
    assert.equal(f.reads(), 0);
  });
}

test('other operator, wrong community and logged-out context are rejected before reads', async () => {
  const f = fixture();
  for (const change of [{ username: 'someoneelse' }, { subredditName: 'other' }, { userId: '' }])
    await assert.rejects(f.workflow.save({ ...actor, ...change }, policy, 'Answer'), WorkflowError);
  assert.equal(f.reads(), 0);
});

for (const confirmed of [false, undefined, 'true', 1]) {
  test(`publication refuses non-boolean confirmation ${String(confirmed)}`, async () => {
    const f = fixture(), saved = await f.workflow.save(actor, policy, 'Human answer');
    await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, confirmed), WorkflowError);
    assert.equal(f.submissions.length, 0);
  });
}

test('spoofed token and context cannot select another post or user', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
  await assert.rejects(f.workflow.publish(actor, policy, 'forged', true), WorkflowError);
  await assert.rejects(f.workflow.publish({ ...actor, postId: 't3_other' }, policy, saved.draft.token, true), WorkflowError);
  await assert.rejects(f.workflow.publish({ ...actor, username: 'other' }, policy, saved.draft.token, true), WorkflowError);
  assert.equal(f.submissions.length, 0);
});

test('editing invalidates the previously reviewed token', async () => {
  const f = fixture(), old = await f.workflow.save(actor, policy, 'First answer');
  const edited = await f.workflow.save(actor, policy, 'Edited answer');
  await assert.rejects(f.workflow.publish(actor, policy, old.draft.token, true), WorkflowError);
  await f.workflow.publish(actor, policy, edited.draft.token, true);
  assert.equal(f.submissions[0].body, 'Edited answer');
});

for (const change of [{ removed: true }, { authorAvailable: false }, { nsfw: true }, { quarantined: true },
  { public: false }, { body: '[deleted]' }, { community: 'other' }, { body: 'Edited question' }]) {
  test(`changed/unavailable source is not published ${JSON.stringify(change)}`, async () => {
    const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
    Object.assign(f.sources.get(actor.postId)!, change);
    await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), WorkflowError);
    assert.equal(f.submissions.length, 0);
    assert.equal(await f.storage.get(keys(actor, f.storage.now).draft), undefined);
  });
}

test('locked and archived sources are blocked', async () => {
  for (const change of [{ locked: true }, { archived: true }]) {
    const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
    Object.assign(f.sources.get(actor.postId)!, change);
    await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), WorkflowError);
    assert.equal(f.submissions.length, 0);
  }
});

test('verification errors preserve data but block use', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
  f.failSource();
  await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), WorkflowError);
  assert.ok(await f.storage.get(keys(actor, f.storage.now).draft));
  assert.equal(f.submissions.length, 0);
});

test('expired drafts are neither displayed nor published', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
  f.storage.now += DRAFT_MS;
  await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), WorkflowError);
  assert.equal(f.submissions.length, 0);
});

test('concurrent confirmations submit only once', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
  const results = await Promise.allSettled([f.workflow.publish(actor, policy, saved.draft.token, true),
    f.workflow.publish(actor, policy, saved.draft.token, true)]);
  assert.equal(results.filter(result => result.status === 'fulfilled').length, 1);
  assert.equal(f.submissions.length, 1);
});

test('uncertain outcomes consume a daily attempt and cannot be re-drafted', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
  f.failSubmit();
  await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), /uncertain/);
  await assert.rejects(f.workflow.save(actor, policy, 'Another answer'), /already attempted/);
  await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), WorkflowError);
  assert.equal(await f.storage.get(keys(actor, f.storage.now).day), '1');
  assert.equal(f.submissions.length, 1);
});

test('daily cap persists across instances and is not reset by deleting content', async () => {
  const f = fixture();
  for (const [index, text] of ['Use a dictionary to map the keys.', 'Catch the exception using a try block.', 'Create a generator for the sequence.', 'Choose an appropriate integer data type.'].entries()) {
    const person = { ...actor, postId: `t3_post${index}` };
    f.sources.set(person.postId, f.makeSource(person.postId));
    const saved = await f.workflow.save(person, policy, text);
    if (index < 3) await f.workflow.publish(person, policy, saved.draft.token, true);
    else await assert.rejects(f.workflow.publish(person, policy, saved.draft.token, true), /daily/);
    await f.workflow.deleteData(person, true);
  }
  assert.equal(f.submissions.length, 3);
  assert.equal(await f.storage.get(keys(actor, f.storage.now).day), '3');
});

test('exact and substantially similar text is blocked', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Use a dictionary to map each key to its value.');
  await f.workflow.publish(actor, policy, saved.draft.token, true);
  const other = { ...actor, postId: 't3_other' };
  f.sources.set(other.postId, f.makeSource(other.postId));
  const next = await f.workflow.save(other, policy, 'Use a dictionary to map each key to its value!');
  await assert.rejects(f.workflow.publish(other, policy, next.draft.token, true), /repetitive/);
  assert.equal(f.submissions.length, 1);
  assert.equal(similar('yes', 'no'), false);
});

test('retention never extends earlier records when another reply is published', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Use a dictionary to map the values.');
  await f.workflow.publish(actor, policy, saved.draft.token, true);
  f.storage.now += 86400000;
  const other = { ...actor, postId: 't3_other' };
  f.sources.set(other.postId, f.makeSource(other.postId));
  const next = await f.workflow.save(other, policy, 'Raise a specific exception when input is invalid.');
  await f.workflow.publish(other, policy, next.draft.token, true);
  f.storage.now = initialTime + HISTORY_MS;
  assert.equal(await f.storage.get(keys(actor, f.storage.now).history), undefined);
});

test('local per-post deletion removes drafts/history without publishing or resetting counters', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
  await f.workflow.publish(actor, policy, saved.draft.token, true);
  await f.workflow.deleteData(actor);
  assert.equal(await f.storage.get(keys(actor, f.storage.now).history), undefined);
  assert.equal(await f.storage.get(keys(actor, f.storage.now).day), '1');
});

test('source deletion event can purge storage without a source-author lookup', async () => {
  const f = fixture();
  await f.workflow.save(actor, policy, 'Answer');
  const reads = f.reads();
  await f.workflow.deleteData({ ...actor, userId: 'source-change-trigger' });
  assert.equal(f.reads(), reads);
  assert.equal(await f.storage.get(keys(actor, f.storage.now).draft), undefined);
});

test('empty and oversized replies never reach Reddit', async () => {
  const f = fixture();
  for (const value of ['', '  ', 'x'.repeat(10001), null, 123])
    await assert.rejects(f.workflow.save(actor, policy, value), WorkflowError);
  assert.equal(f.reads(), 0);
});

test('future-dated rules are invalid', () => {
  assert.throws(() => checkActor(actor, { ...policy, rulesReviewedOn: '2026-10-15' }, initialTime), WorkflowError);
});

test('single-choice settings work with native Devvit selection arrays', () => {
  assert.equal(settingText(['playtest']), 'playtest');
  assert.equal(settingText('playtest'), 'playtest');
  assert.equal(settingText(['playtest', 'approved']), '');
  assert.equal(settingText(undefined), '');
  assert.equal(settingText(false), '');
  checkActor(actor, { ...policy, mode: settingText(['playtest']) }, initialTime);
});

test('deletion and edit events use their actual distinct SDK payload shapes', () => {
  assert.equal(eventPostId({ postId: 't3_delete' }), 't3_delete');
  assert.equal(eventPostId({ post: { id: 't3_edit' } }), 't3_edit');
  assert.equal(eventPostId({ post: { id: 'malformed' } }), undefined);
  assert.equal(eventPostId({}), undefined);
});

test('a source edit during reservation is caught before the network submission', async () => {
  const f = fixture(), saved = await f.workflow.save(actor, policy, 'Answer');
  const original = f.storage.atomic.bind(f.storage);
  f.storage.atomic = async (keys, change) => {
    const result = await original(keys, change);
    if (keys.some(key => key.includes(':attempts:'))) f.sources.get(actor.postId)!.body = 'Changed while reserving';
    return result;
  };
  await assert.rejects(f.workflow.publish(actor, policy, saved.draft.token, true), /changed before/);
  assert.equal(f.submissions.length, 0);
});
