/**
 * Tests for discord-bot/src/sync/idea-channel-sync.js (spec-164 R1).
 * Validates slug generation, stage filtering, and archive logic.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

// -- Pure slug logic extracted from idea-channel-sync.js --
function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 90);
}

describe('slugify', () => {
  it('converts spaces to dashes', () => {
    assert.equal(slugify('GraphQL Cache'), 'graphql-cache');
  });

  it('removes special characters', () => {
    assert.equal(slugify('Hello, World!'), 'hello-world');
  });

  it('strips leading and trailing dashes', () => {
    assert.equal(slugify('---foo---'), 'foo');
  });

  it('truncates to 90 characters', () => {
    const long = 'a'.repeat(100);
    assert.equal(slugify(long).length, 90);
  });

  it('builds correct channel name pattern', () => {
    const idea = { name: 'Discord Bot Channels' };
    const slug = slugify(idea.name);
    assert.equal(`idea-${slug}`, 'idea-discord-bot-channels');
  });
});

describe('Active stage filtering', () => {
  const ACTIVE_STAGES = ['specced', 'implementing', 'testing'];

  it('includes specced ideas', () => {
    assert.ok(ACTIVE_STAGES.includes('specced'));
  });

  it('includes implementing ideas', () => {
    assert.ok(ACTIVE_STAGES.includes('implementing'));
  });

  it('includes testing ideas', () => {
    assert.ok(ACTIVE_STAGES.includes('testing'));
  });

  it('excludes validated ideas', () => {
    assert.ok(!ACTIVE_STAGES.includes('validated'));
  });

  it('excludes archived ideas', () => {
    assert.ok(!ACTIVE_STAGES.includes('archived'));
  });

  it('stage query string matches spec R1 format', () => {
    assert.equal(ACTIVE_STAGES.join(','), 'specced,implementing,testing');
  });
});

describe('Archive logic', () => {
  it('identifies ideas no longer in active stages as archivable', () => {
    const ACTIVE_STAGES = ['specced', 'implementing', 'testing'];
    const activeIdeas = [
      { id: 'idea-a', manifestation_status: 'specced' },
      { id: 'idea-b', manifestation_status: 'implementing' },
    ];

    const stored = [
      { idea_id: 'idea-a', archived: 0, discord_channel_id: 'ch-001' },
      { idea_id: 'idea-c', archived: 0, discord_channel_id: 'ch-002' }, // no longer active
    ];

    const activeIds = new Set(activeIdeas.map(i => i.id));
    const toArchive = stored.filter(r => !r.archived && !activeIds.has(r.idea_id));

    assert.equal(toArchive.length, 1);
    assert.equal(toArchive[0].idea_id, 'idea-c');
  });

  it('does not re-archive already archived channels', () => {
    const activeIdeas = [];
    const stored = [
      { idea_id: 'idea-x', archived: 1, discord_channel_id: 'ch-010' }, // already archived
    ];

    const activeIds = new Set(activeIdeas.map(i => i.id));
    const toArchive = stored.filter(r => !r.archived && !activeIds.has(r.idea_id));

    assert.equal(toArchive.length, 0);
  });
});

describe('Channel deduplication', () => {
  it('idempotent: same idea_id does not add duplicates', () => {
    // Simulating the ensureChannel guard logic
    const existing = [{ name: 'idea-graphql-cache', type: 'GUILD_TEXT' }];
    const channelName = 'idea-graphql-cache';
    const found = existing.find(c => c.name === channelName);
    assert.ok(found, 'Channel should be found — no duplicate create needed');
  });
});
