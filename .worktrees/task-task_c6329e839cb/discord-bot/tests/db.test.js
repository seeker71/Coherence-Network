/**
 * Tests for discord-bot/src/lib/db.js (spec-164 R1 idempotency, R3 rate limiting).
 * Uses a temporary directory for each test run.
 */

import assert from 'node:assert/strict';
import { describe, it, before, after } from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

let tmpDir;
let dbModule;

before(async () => {
  tmpDir = mkdtempSync(path.join(tmpdir(), 'coherence-bot-test-'));
  process.env.DATA_DIR = tmpDir;
  // Dynamic import to pick up DATA_DIR env var
  dbModule = await import('../src/lib/db.js');
});

after(() => {
  rmSync(tmpDir, { recursive: true, force: true });
});

describe('channels db', () => {
  it('stores and retrieves a channel mapping', () => {
    const { channels } = dbModule;
    channels.set('idea-alpha', 'discord-ch-111', 'guild-001');
    const row = channels.get('idea-alpha');
    assert.equal(row.idea_id, 'idea-alpha');
    assert.equal(row.discord_channel_id, 'discord-ch-111');
    assert.equal(row.guild_id, 'guild-001');
    assert.equal(row.archived, 0);
  });

  it('upsert does not duplicate on second set', () => {
    const { channels } = dbModule;
    channels.set('idea-beta', 'discord-ch-222', 'guild-001');
    channels.set('idea-beta', 'discord-ch-222', 'guild-001'); // duplicate
    const all = channels.getAll().filter(r => r.idea_id === 'idea-beta');
    assert.equal(all.length, 1);
  });

  it('archive marks the channel as archived', () => {
    const { channels } = dbModule;
    channels.set('idea-gamma', 'discord-ch-333', 'guild-001');
    channels.archive('idea-gamma');
    const row = channels.get('idea-gamma');
    assert.equal(row.archived, 1);
  });

  it('getAll returns all stored channels', () => {
    const { channels } = dbModule;
    channels.set('idea-delta', 'discord-ch-444', 'guild-001');
    const all = channels.getAll();
    assert.ok(all.length >= 4); // alpha, beta, gamma, delta
  });
});

describe('rate limits', () => {
  it('is not limited when no entry exists', () => {
    const { rateLimits } = dbModule;
    assert.equal(rateLimits.isLimited('user:999:cc-idea'), false);
  });

  it('is limited after set with future expiry', () => {
    const { rateLimits } = dbModule;
    rateLimits.set('user:111:cc-idea', 60_000); // 60s from now
    assert.equal(rateLimits.isLimited('user:111:cc-idea'), true);
  });

  it('reports remaining seconds > 0 when limited', () => {
    const { rateLimits } = dbModule;
    rateLimits.set('user:222:cc-idea', 60_000);
    const remaining = rateLimits.remainingSeconds('user:222:cc-idea');
    assert.ok(remaining > 0 && remaining <= 60);
  });

  it('is not limited after expiry passes', async () => {
    const { rateLimits } = dbModule;
    rateLimits.set('user:333:cc-idea', 1); // expires in 1ms
    await new Promise(r => setTimeout(r, 10));
    assert.equal(rateLimits.isLimited('user:333:cc-idea'), false);
  });
});

describe('contributors mapping', () => {
  it('returns null for unknown Discord user', () => {
    const { contributors } = dbModule;
    assert.equal(contributors.getContributorId('unknown-user'), null);
  });

  it('links and retrieves a contributor', () => {
    const { contributors } = dbModule;
    contributors.link('discord-user-abc', 'contributor-xyz');
    assert.equal(contributors.getContributorId('discord-user-abc'), 'contributor-xyz');
  });

  it('overwrite link updates the contributor id', () => {
    const { contributors } = dbModule;
    contributors.link('discord-user-def', 'contrib-old');
    contributors.link('discord-user-def', 'contrib-new');
    assert.equal(contributors.getContributorId('discord-user-def'), 'contrib-new');
  });
});

describe('question threads', () => {
  it('returns undefined for unknown thread', () => {
    const { threads } = dbModule;
    assert.equal(threads.get('unknown-idea', 0), undefined);
  });

  it('stores and retrieves a thread', () => {
    const { threads } = dbModule;
    threads.set('idea-thread-test', 0, 'thread-id-001');
    const row = threads.get('idea-thread-test', 0);
    assert.equal(row.thread_id, 'thread-id-001');
    assert.equal(row.answered, 0);
  });

  it('marks a thread as answered', () => {
    const { threads } = dbModule;
    threads.set('idea-thread-test', 1, 'thread-id-002');
    threads.markAnswered('idea-thread-test', 1);
    const row = threads.get('idea-thread-test', 1);
    assert.equal(row.answered, 1);
  });
});
