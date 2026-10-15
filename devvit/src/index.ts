import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { context, createServer, getServerPort, reddit } from '@devvit/web/server';
import { SettingsDefinition, type Settings } from '@devvit/protos/types/devvit/plugin/settings/v1alpha/settings.js';
import { getDevvitConfig } from '@devvit/shared-types/server/get-devvit-config.js';
import { installationPolicy } from './configuration.ts';
import type { UiResponse } from '@devvit/web/shared';
import { RedisStore } from './redis-store.ts';
import { Workflow, WorkflowError, checkActor, eventPostId, type Actor, type Policy, type Draft, type Source } from './workflow.ts';

const app = new Hono();
const workflow = new Workflow({
  storage: new RedisStore(), now: Date.now,
  async source(postId) {
    const post = await reddit.getPostById(postId as `t3_${string}`);
    const community = await reddit.getSubredditByName(context.subredditName);
    return {
      id: post.id, community: post.subredditName, title: post.title, body: post.body ?? '',
      authorAvailable: !!post.authorId && !!post.authorName && !['[deleted]', '[removed]'].includes(post.authorName),
      removed: post.removed || post.spam || !!post.removedByCategory,
      nsfw: post.nsfw, quarantined: post.quarantined, locked: post.locked, archived: post.archived,
      public: community.type === 'public',
    };
  },
  async submit(postId, body) {
    const comment = await reddit.submitComment({ id: postId as `t3_${string}`, text: body, runAs: 'APP' });
    return `https://www.reddit.com${comment.permalink}`;
  },
});

function actor(): Actor {
  return { userId: context.userId ?? '', username: context.username ?? '',
    subredditId: context.subredditId, subredditName: context.subredditName, postId: context.postId ?? '' };
}

async function configuration(): Promise<Policy> {
  const response = await getDevvitConfig().use<Settings>(SettingsDefinition).GetSettings({}, context.metadata);
  return installationPolicy(response.installationSettings?.settings);
}

function writeForm(source: Source, initial = ''): UiResponse {
  return { showForm: { name: 'writeReply', form: {
    title: 'Write your reply', description: `r/${source.community}: ${source.title}\n\n${source.body.slice(0, 5000)}`,
    acceptLabel: 'Review reply', cancelLabel: 'Cancel', fields: [
      { name: 'reply', label: 'Your human-written reply', type: 'paragraph', required: true, defaultValue: initial },
    ],
  } } };
}

function reviewForm(draft: Draft, source: Source, policy: Policy): UiResponse {
  return { showForm: { name: 'reviewReply', form: {
    title: 'Review before publishing',
    description: `r/${source.community}: ${source.title}\n\n${draft.body}\n\nPublishing creates ONE comment from the Contribution Helper app account. Check accuracy and the current community rules. Privacy: ${policy.privacyUrl}`,
    acceptLabel: 'Continue', cancelLabel: 'Cancel', fields: [
      { name: 'token', label: 'Draft reference', type: 'string', defaultValue: draft.token, disabled: true },
      { name: 'action', label: 'Choose an action', type: 'select', required: true,
        options: [{ label: 'Publish this one reply', value: 'publish' }, { label: 'Edit reply', value: 'edit' }, { label: 'Discard reply', value: 'discard' }],
        defaultValue: ['edit'] },
      { name: 'confirmed', label: 'I checked accuracy and community rules, and authorize publishing this exact reply as the app account', type: 'boolean', defaultValue: false },
    ],
  } } };
}

app.post('/internal/menu/write', async c => {
  const person = actor(), policy = await configuration();
  try { checkActor(person, policy, Date.now()); }
  catch (error) {
    if (error instanceof WorkflowError && person.username.toLowerCase() === 'saurabhimapro')
      throw new WorkflowError(`${error.message} App ${context.appVersion}; mode: ${policy.mode || 'missing'}.`);
    throw error;
  }
  const source = await workflow.readSource(person);
  if (source.locked || source.archived) throw new WorkflowError('This post cannot receive replies.');
  return c.json<UiResponse>(writeForm(source));
});

app.post('/internal/form/write', async c => {
  const input = await c.req.json<Record<string, unknown>>();
  const policy = await configuration();
  const { draft, source } = await workflow.save(actor(), policy, input.reply);
  return c.json<UiResponse>(reviewForm(draft, source, policy));
});

app.post('/internal/form/review', async c => {
  const input = await c.req.json<Record<string, unknown>>();
  const choice = Array.isArray(input.action) ? input.action[0] : input.action;
  const person = actor(), policy = await configuration();
  if (choice === 'publish') {
    const url = await workflow.publish(person, policy, input.token, input.confirmed);
    return c.json<UiResponse>({ showToast: `Reply published. ${url}` });
  }
  const { draft, source } = await workflow.review(person, policy, input.token);
  if (choice === 'edit') return c.json<UiResponse>(writeForm(source, draft.body));
  if (choice === 'discard') {
    await workflow.deleteData(person);
    return c.json<UiResponse>({ showToast: 'Local draft discarded. Nothing was published.' });
  }
  throw new WorkflowError('Choose Edit, Discard or Publish.');
});

// Deletion stays available when publishing is disabled or approval is revoked.
app.post('/internal/menu/delete', async c => {
  const person = actor();
  if (!person.userId || person.username.toLowerCase() !== 'saurabhimapro')
    throw new WorkflowError('Only the configured operator can delete this personal app data.');
  await workflow.deleteData(person);
  return c.json<UiResponse>({ showToast: 'Local reply data for this post was deleted. Published comments and daily limits are unchanged.' });
});

app.post('/internal/menu/delete-all', async c => {
  const person = actor();
  if (!person.userId || person.username.toLowerCase() !== 'saurabhimapro')
    throw new WorkflowError('Only the configured operator can delete this personal app data.');
  await workflow.deleteData(person, true);
  return c.json<UiResponse>({ showToast: 'All local reply data was deleted. Published comments and daily limits are unchanged.' });
});

app.post('/internal/triggers/source-change', async c => {
  const input = await c.req.json<{ postId?: unknown; post?: { id?: unknown } }>();
  const postId = eventPostId(input);
  if (!postId)
    return c.json({ status: 'ignored' });
  // Reddit-owned trigger routes. No Reddit read/write calls or author data needed.
  await workflow.deleteData({ ...actor(), userId: 'source-change-trigger', postId });
  return c.json({ status: 'deleted' });
});

app.onError((error, c) => c.json<UiResponse>({ showToast: error instanceof WorkflowError
  ? error.message : 'The action could not be verified. Nothing further was attempted; check Reddit before retrying a publication.' }));
app.notFound(c => c.json({ error: 'Not found' }, 404));

serve({ fetch: app.fetch, createServer, port: getServerPort() });
