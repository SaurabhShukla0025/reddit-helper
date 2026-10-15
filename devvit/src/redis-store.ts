import { redis } from '@devvit/web/server';
import { WorkflowError, type Storage, type Write } from './workflow.ts';

export interface RedisApi {
  get(key: string): Promise<string | undefined>;
  watch(...keys: string[]): Promise<{
    multi(): Promise<void>;
    set(key: string, value: string, options: { expiration: Date }): Promise<unknown>;
    del(key: string): Promise<unknown>;
    exec(): Promise<unknown[]>;
    discard(): Promise<unknown>;
  }>;
}

export class RedisStore implements Storage {
  readonly client: RedisApi;
  constructor(client: RedisApi = redis) { this.client = client; }
  async get(key: string): Promise<string | undefined> { return this.client.get(key); }

  async atomic<T>(keys: string[], change: (values: Record<string, string | undefined>) => { writes: Write[]; result: T }): Promise<T> {
    const transaction = await this.client.watch(...keys);
    try {
      const values: Record<string, string | undefined> = {};
      for (const key of keys) values[key] = await this.client.get(key);
      const update = change(values);
      await transaction.multi();
      for (const write of update.writes) {
        if (write.value === null) await transaction.del(write.key);
        else {
          if (!write.expiresAt) throw new WorkflowError('Storage retention deadline is missing.');
          await transaction.set(write.key, write.value, { expiration: new Date(write.expiresAt) });
        }
      }
      const result: unknown[] = await transaction.exec();
      if (result.length !== update.writes.length)
        throw new WorkflowError('Another action changed this draft. Reopen the workflow before continuing.');
      return update.result;
    } catch (error) {
      try { await transaction.discard(); } catch { /* Transaction may already be completed. */ }
      if (error instanceof WorkflowError) throw error;
      throw new WorkflowError('Local storage could not be verified. The action was stopped.');
    }
  }
}
