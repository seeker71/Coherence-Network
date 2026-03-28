/**
 * Tests for discord-bot/src/commands/cc-link.js (spec-167).
 * Uses a temporary directory for each test run — no Discord.js required.
 */

import assert from 'node:assert/strict';
import { describe, it, before, after } from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

let tmpDir;
let dbModule;

before(async () => {
  tmpDir = mkdtempSync(path.join(tmpdir(), 'coherence-cc-link-test-'));
  process.env.DATA_DIR = tmpDir;
  dbModule = await import('../src/lib/db.js');
});

after(() => {
  rmSync(tmpDir, { recursive: true, force: true });
});

// --- Unit tests for the contributors DB layer used by /cc-link ---

describe('/cc-link: contributor linking via DB', () => {
  it('returns null before any link is established', () => {
    const { contributors } = dbModule;
    assert.equal(contributors.getContributorId('discord-user-not-linked'), null);
  });

  it('stores a new Discord → contributor mapping', () => {
    const { contributors } = dbModule;
    contributors.link('discord-link-user-1', 'contrib-alice');
    assert.equal(contributors.getContributorId('discord-link-user-1'), 'contrib-alice');
  });

  it('overwrites an existing mapping when called again', () => {
    const { contributors } = dbModule;
    contributors.link('discord-link-user-2', 'contrib-old');
    contributors.link('discord-link-user-2', 'contrib-new');
    assert.equal(contributors.getContributorId('discord-link-user-2'), 'contrib-new');
  });

  it('multiple users can link to different contributors', () => {
    const { contributors } = dbModule;
    contributors.link('discord-link-user-3', 'contrib-bob');
    contributors.link('discord-link-user-4', 'contrib-carol');
    assert.equal(contributors.getContributorId('discord-link-user-3'), 'contrib-bob');
    assert.equal(contributors.getContributorId('discord-link-user-4'), 'contrib-carol');
  });

  it('multiple users can map to the same contributor', () => {
    const { contributors } = dbModule;
    contributors.link('discord-link-user-5', 'contrib-dave');
    contributors.link('discord-link-user-6', 'contrib-dave');
    assert.equal(contributors.getContributorId('discord-link-user-5'), 'contrib-dave');
    assert.equal(contributors.getContributorId('discord-link-user-6'), 'contrib-dave');
  });
});

// --- Tests for /cc-link command logic (simulating interaction object) ---

describe('/cc-link command execute', () => {
  it('command data is named cc-link', async () => {
    const cmd = await import('../src/commands/cc-link.js');
    assert.equal(cmd.data.name, 'cc-link');
  });

  it('command has contributor_id option', async () => {
    const cmd = await import('../src/commands/cc-link.js');
    const json = cmd.data.toJSON();
    const opt = json.options.find(o => o.name === 'contributor_id');
    assert.ok(opt, 'contributor_id option must exist');
    assert.equal(opt.required, true);
  });

  it('execute replies ephemeral on new link', async () => {
    const { contributors } = dbModule;
    const cmd = await import('../src/commands/cc-link.js');

    const replies = [];
    const interaction = {
      user: { id: 'exec-user-001', tag: 'TestUser#0001' },
      options: { getString: (name) => name === 'contributor_id' ? 'contrib-exec-001' : null },
      reply: async (opts) => { replies.push(opts); },
    };

    await cmd.execute(interaction);

    assert.equal(replies.length, 1);
    assert.equal(replies[0].ephemeral, true);
    assert.ok(replies[0].content.includes('contrib-exec-001'));
    assert.equal(contributors.getContributorId('exec-user-001'), 'contrib-exec-001');
  });

  it('execute shows "already linked" message when same id is re-linked', async () => {
    const cmd = await import('../src/commands/cc-link.js');

    const replies = [];
    const interaction = {
      user: { id: 'exec-user-002', tag: 'TestUser#0002' },
      options: { getString: (name) => name === 'contributor_id' ? 'contrib-same' : null },
      reply: async (opts) => { replies.push(opts); },
    };

    await cmd.execute(interaction); // first link
    replies.length = 0;
    await cmd.execute(interaction); // same link

    assert.ok(replies[0].content.toLowerCase().includes('already linked'));
  });

  it('execute shows "updated" message when contributor_id changes', async () => {
    const cmd = await import('../src/commands/cc-link.js');

    const replies = [];
    let callCount = 0;
    const interaction = {
      user: { id: 'exec-user-003', tag: 'TestUser#0003' },
      options: {
        getString: (name) => {
          if (name !== 'contributor_id') return null;
          return callCount === 0 ? 'contrib-before' : 'contrib-after';
        },
      },
      reply: async (opts) => { replies.push(opts); },
    };

    callCount = 0;
    await cmd.execute(interaction); // first link = contrib-before
    callCount = 1;
    replies.length = 0;
    await cmd.execute(interaction); // updated to contrib-after

    assert.ok(replies[0].content.toLowerCase().includes('updated'));
    assert.ok(replies[0].content.includes('contrib-after'));
  });
});
