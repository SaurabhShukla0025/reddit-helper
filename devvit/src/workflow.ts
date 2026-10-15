import { createHash, randomUUID } from 'node:crypto';

export const DRAFT_MS = 60 * 60 * 1000;
export const HISTORY_MS = 7 * 24 * 60 * 60 * 1000;
export const DAILY_LIMIT = 3;

export class WorkflowError extends Error {}
export type Actor = { userId: string; username: string; subredditId: string; subredditName: string; postId: string };
export type Policy = {
  mode: string; community: string; operator: string; permissionReference: string;
  communityPermission: string; privacyContact: string; privacyUrl: string; rulesReviewedOn: string;
};

export function settingText(value: unknown): string {
  if (typeof value === 'string') return value;
  // Devvit returns a single-choice setting as a one-element string array.
  if (Array.isArray(value) && value.length === 1 && typeof value[0] === 'string') return value[0];
  return '';
}
export type Source = {
  id: string; community: string; title: string; body: string; authorAvailable: boolean;
  removed: boolean; nsfw: boolean; quarantined: boolean; locked: boolean; archived: boolean; public: boolean;
};
export type Draft = { token: string; postId: string; body: string; sourceHash: string; expiresAt: number };
export type Receipt = {
  token: string; postId: string; body: string; sourceHash: string;
  status: 'uncertain' | 'posted'; createdAt: number; url?: string;
};
export type Write = { key: string; value: string | null; expiresAt?: number };
export interface Storage {
  get(key: string): Promise<string | undefined>;
  atomic<T>(keys: string[], change: (values: Record<string, string | undefined>) => { writes: Write[]; result: T }): Promise<T>;
}
export interface Dependencies {
  storage: Storage;
  source(postId: string): Promise<Source>;
  submit(postId: string, body: string): Promise<string>;
  now(): number;
}

export function checkActor(actor: Actor, policy: Policy, now: number): void {
  if (!actor.userId || !actor.subredditId || !/^t3_[a-z0-9]+$/.test(actor.postId))
    throw new WorkflowError('Sign in and open this action on a post.');
  if (actor.username.toLowerCase() !== policy.operator.toLowerCase())
    throw new WorkflowError('This personal app is available only to its configured operator.');
  if (actor.subredditName.toLowerCase() !== policy.community.toLowerCase())
    throw new WorkflowError('This community is outside the configured scope.');
  if (!['playtest', 'approved'].includes(policy.mode) || !policy.permissionReference || !policy.communityPermission)
    throw new WorkflowError('The app is disabled until its permitted use and community scope are recorded.');
  if (!policy.privacyContact || !/^https:\/\//.test(policy.privacyUrl))
    throw new WorkflowError('Configure the public privacy notice and deletion contact first.');
  const reviewed = Date.parse(policy.rulesReviewedOn + 'T00:00:00Z');
  const today = Date.parse(new Date(now).toISOString().slice(0, 10) + 'T00:00:00Z');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(policy.rulesReviewedOn) || !Number.isFinite(reviewed)
      || new Date(reviewed).toISOString().slice(0, 10) !== policy.rulesReviewedOn
      || reviewed > today || today - reviewed > 30 * 86400000)
    throw new WorkflowError('Review the current community rules and record the date.');
}

export function hash(source: Source): string {
  return createHash('sha256').update(source.title + '\0' + source.body).digest('hex');
}

export function eligible(source: Source, actor: Actor): boolean {
  return source.id === actor.postId && source.community.toLowerCase() === actor.subredditName.toLowerCase()
    && source.authorAvailable && source.public && !source.removed && !source.nsfw && !source.quarantined
    && !['[deleted]', '[removed]'].includes(source.body.trim());
}

function clean(body: unknown): string {
  if (typeof body !== 'string' || !body.trim() || body.trim().length > 10000)
    throw new WorkflowError('Write a reply containing 1–10,000 characters.');
  return body.trim();
}

export function similar(a: string, b: string): boolean {
  const normalize = (text: string) => text.toLowerCase().replace(/\s+/g, ' ').trim();
  a = normalize(a); b = normalize(b);
  if (a === b) return true;
  if (Math.min(a.length, b.length) < 20) return false;
  // Character bigram Dice score catches lightly edited repetitive replies.
  const grams = (text: string) => {
    const counts = new Map<string, number>();
    for (let i = 0; i < text.length - 1; i++) {
      const gram = text.slice(i, i + 2);
      counts.set(gram, (counts.get(gram) ?? 0) + 1);
    }
    return counts;
  };
  const aa = grams(a), bb = grams(b);
  let shared = 0;
  for (const [gram, count] of aa) shared += Math.min(count, bb.get(gram) ?? 0);
  return 2 * shared / (a.length + b.length - 2) >= 0.9;
}

export function eventPostId(input: { postId?: unknown; post?: { id?: unknown } }): string | undefined {
  const value = input.postId ?? input.post?.id;
  return typeof value === 'string' && /^t3_[a-z0-9]+$/.test(value) ? value : undefined;
}

export function keys(actor: Actor, now: number) {
  const scope = `helper:${actor.subredditId}`;
  return {
    // This app has exactly one authorized operator. Fixed installation keys also
    // let Reddit deletion events purge the source without looking up its author.
    draft: `${scope}:operator:draft`, history: `${scope}:operator:history`,
    day: `${scope}:attempts:${new Date(now).toISOString().slice(0, 10)}`,
  };
}

function history(raw: string | undefined, now: number): Receipt[] {
  const parsed = raw ? JSON.parse(raw) as Receipt[] : [];
  if (!Array.isArray(parsed)) throw new WorkflowError('Stored history is unavailable. Publishing is blocked.');
  return parsed.filter(item => item.createdAt + HISTORY_MS > now);
}

function historyWrite(key: string, items: Receipt[]): Write {
  // Expire the entire small history at the EARLIEST record's deadline, so a later
  // publication cannot extend retention of earlier content. Early deletion is fine.
  return items.length
    ? { key, value: JSON.stringify(items), expiresAt: Math.min(...items.map(item => item.createdAt + HISTORY_MS)) }
    : { key, value: null };
}

export class Workflow {
  readonly deps: Dependencies;
  constructor(deps: Dependencies) { this.deps = deps; }

  async readSource(actor: Actor): Promise<Source> {
    let source: Source;
    try { source = await this.deps.source(actor.postId); }
    catch { throw new WorkflowError('Could not verify this post. Nothing will be displayed or published.'); }
    if (!eligible(source, actor)) {
      await this.deleteData(actor);
      throw new WorkflowError('The post is unavailable or outside scope. Its local reply data was deleted.');
    }
    return source;
  }

  async save(actor: Actor, policy: Policy, body: unknown): Promise<{ draft: Draft; source: Source }> {
    checkActor(actor, policy, this.deps.now());
    const text = clean(body);
    const source = await this.readSource(actor);
    if (source.locked || source.archived) throw new WorkflowError('This post cannot receive replies.');
    const now = this.deps.now(), key = keys(actor, now);
    const draft: Draft = { token: randomUUID(), postId: actor.postId, body: text, sourceHash: hash(source), expiresAt: now + DRAFT_MS };
    await this.deps.storage.atomic([key.draft, key.history], values => {
      const previous = history(values[key.history], now);
      if (previous.some(item => item.postId === actor.postId))
        throw new WorkflowError('A reply was already attempted here. Check Reddit before taking further action.');
      return { writes: [{ key: key.draft, value: JSON.stringify(draft), expiresAt: draft.expiresAt }], result: undefined };
    });
    return { draft, source };
  }

  async review(actor: Actor, policy: Policy, token: unknown): Promise<{ draft: Draft; source: Source }> {
    checkActor(actor, policy, this.deps.now());
    const key = keys(actor, this.deps.now());
    const raw = await this.deps.storage.get(key.draft);
    const draft = raw ? JSON.parse(raw) as Draft : undefined;
    if (!draft || draft.token !== token || draft.postId !== actor.postId || draft.expiresAt <= this.deps.now())
      throw new WorkflowError('This draft expired or changed. Open Write reply again.');
    const source = await this.readSource(actor);
    if (hash(source) !== draft.sourceHash) {
      await this.deleteData(actor);
      throw new WorkflowError('The source changed. Write and review a fresh reply.');
    }
    if (source.locked || source.archived) throw new WorkflowError('This post cannot receive replies.');
    return { draft, source };
  }

  async publish(actor: Actor, policy: Policy, token: unknown, confirmed: unknown): Promise<string> {
    if (confirmed !== true) throw new WorkflowError('Explicit confirmation is required. Nothing was published.');
    const { draft } = await this.review(actor, policy, token);
    const now = this.deps.now(), key = keys(actor, now);
    const receipt: Receipt = { token: draft.token, postId: actor.postId, body: draft.body, sourceHash: draft.sourceHash, status: 'uncertain', createdAt: now };
    await this.deps.storage.atomic([key.draft, key.history, key.day], values => {
      const current = values[key.draft] ? JSON.parse(values[key.draft]!) as Draft : undefined;
      if (!current || current.token !== draft.token || current.expiresAt <= this.deps.now())
        throw new WorkflowError('The draft changed or was already submitted.');
      const attempts = Number(values[key.day] ?? '0');
      if (!Number.isInteger(attempts) || attempts < 0 || attempts >= DAILY_LIMIT)
        throw new WorkflowError('The daily publishing attempt limit has been reached (UTC).');
      const previous = history(values[key.history], now);
      if (previous.some(item => item.postId === actor.postId || similar(item.body, draft.body)))
        throw new WorkflowError('This reply is repetitive or was already attempted. Publishing is blocked.');
      return { writes: [
        { key: key.draft, value: null },
        historyWrite(key.history, [...previous, receipt]),
        { key: key.day, value: String(attempts + 1), expiresAt: Date.parse(new Date(now).toISOString().slice(0, 10)) + 2 * 86400000 },
      ], result: undefined };
    });
    let url: string;
    const latest = await this.readSource(actor);
    if (hash(latest) !== draft.sourceHash || latest.locked || latest.archived) {
      await this.deleteData(actor);
      throw new WorkflowError('The source changed before publication. Nothing was published; the attempt still counts.');
    }
    try { url = await this.deps.submit(actor.postId, draft.body); }
    catch { throw new WorkflowError('The submission outcome is uncertain. Check Reddit; do not retry blindly.'); }
    try {
      await this.deps.storage.atomic([key.history], values => {
        const previous = history(values[key.history], this.deps.now());
        return { writes: [historyWrite(key.history, previous.map(item => item.token === receipt.token ? { ...item, status: 'posted', url } : item))], result: undefined };
      });
    } catch {
      throw new WorkflowError('Reddit accepted the reply, but local receipt storage failed. Check Reddit; do not retry.');
    }
    return url;
  }

  async deleteData(actor: Actor, all = false): Promise<void> {
    if (!actor.userId || !actor.subredditId) throw new WorkflowError('Sign in to delete your local data.');
    const now = this.deps.now(), key = keys(actor, now);
    await this.deps.storage.atomic([key.draft, key.history], values => {
      const draft = values[key.draft] ? JSON.parse(values[key.draft]!) as Draft : undefined;
      const previous = history(values[key.history], now).filter(item => !all && item.postId !== actor.postId);
      const writes = [historyWrite(key.history, previous)];
      if (all || draft?.postId === actor.postId) writes.push({ key: key.draft, value: null });
      return { writes, result: undefined };
    });
  }
}
