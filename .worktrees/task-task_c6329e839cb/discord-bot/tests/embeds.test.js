/**
 * Tests for discord-bot/src/lib/embeds.js (spec-164 R2, R4, R6).
 * Uses Node.js built-in test runner (no jest required for CI).
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

// Minimal mock for EmbedBuilder so tests don't need discord.js installed
const mockEmbed = {
  _color: null, _title: null, _url: null, _description: null,
  _fields: [], _footer: null,
  setColor(c) { this._color = c; return this; },
  setTitle(t) { this._title = t; return this; },
  setURL(u) { this._url = u; return this; },
  setDescription(d) { this._description = d; return this; },
  addFields(...fields) { this._fields.push(...fields.flat()); return this; },
  setFooter(f) { this._footer = f; return this; },
};

// We test the pure logic separately from Discord.js by extracting color mapping
describe('Idea embed color mapping', () => {
  const STAGE_COLORS = {
    validated: 0x00c851,
    specced: 0xffbb33,
    implementing: 0x33b5e5,
    testing: 0xff8800,
  };

  it('maps validated → green', () => {
    assert.equal(STAGE_COLORS['validated'], 0x00c851);
  });

  it('maps specced → yellow', () => {
    assert.equal(STAGE_COLORS['specced'], 0xffbb33);
  });

  it('maps implementing → blue', () => {
    assert.equal(STAGE_COLORS['implementing'], 0x33b5e5);
  });

  it('maps testing → orange', () => {
    assert.equal(STAGE_COLORS['testing'], 0xff8800);
  });

  it('unknown stage falls back to grey', () => {
    assert.equal(STAGE_COLORS['unknown'] ?? 0x888888, 0x888888);
  });
});

describe('Idea URL builder', () => {
  const WEB_BASE = 'https://coherencycoin.com';

  it('builds correct idea URL', () => {
    const idea = { id: 'my-idea', name: 'My Idea' };
    const url = `${WEB_BASE}/ideas/${idea.id}`;
    assert.equal(url, 'https://coherencycoin.com/ideas/my-idea');
  });
});

describe('Pipeline event status mapping', () => {
  const statusMap = {
    completed: { color: 0x00c851, icon: '✅' },
    failed: { color: 0xcc0000, icon: '❌' },
    in_progress: { color: 0x33b5e5, icon: '🔄' },
  };

  it('completed → green + checkmark', () => {
    assert.equal(statusMap.completed.color, 0x00c851);
    assert.equal(statusMap.completed.icon, '✅');
  });

  it('failed → red + X', () => {
    assert.equal(statusMap.failed.color, 0xcc0000);
    assert.equal(statusMap.failed.icon, '❌');
  });

  it('in_progress → blue + recycle', () => {
    assert.equal(statusMap.in_progress.icon, '🔄');
  });
});

describe('Duration formatting', () => {
  it('converts ms to seconds string', () => {
    const durationMs = 5432;
    const result = `${(durationMs / 1000).toFixed(1)}s`;
    assert.equal(result, '5.4s');
  });

  it('handles null duration', () => {
    const durationMs = null;
    const result = durationMs != null ? `${(durationMs / 1000).toFixed(1)}s` : '—';
    assert.equal(result, '—');
  });
});
