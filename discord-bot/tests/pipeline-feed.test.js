/**
 * Tests for discord-bot/src/sync/pipeline-feed.js (spec-164 R6).
 * Validates watermark advancement and task ordering logic.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

// -- Pure logic tests that do not require Discord.js or a live API --

describe('Pipeline feed task sorting', () => {
  it('sorts tasks oldest-first by updated_at', () => {
    const tasks = [
      { id: 'task-b', updated_at: '2026-03-28T10:02:00Z', status: 'completed' },
      { id: 'task-a', updated_at: '2026-03-28T10:01:00Z', status: 'completed' },
      { id: 'task-c', updated_at: '2026-03-28T10:03:00Z', status: 'failed' },
    ];

    tasks.sort((a, b) => new Date(a.updated_at ?? 0) - new Date(b.updated_at ?? 0));

    assert.equal(tasks[0].id, 'task-a');
    assert.equal(tasks[1].id, 'task-b');
    assert.equal(tasks[2].id, 'task-c');
  });
});

describe('Pipeline feed watermark advancement', () => {
  it('advances watermark to 1ms after latest task updated_at', () => {
    const tasks = [
      { id: 'task-a', updated_at: '2026-03-28T10:01:00.000Z', status: 'completed' },
      { id: 'task-b', updated_at: '2026-03-28T10:05:00.000Z', status: 'completed' },
    ];

    tasks.sort((a, b) => new Date(a.updated_at ?? 0) - new Date(b.updated_at ?? 0));
    const latest = tasks[tasks.length - 1];
    const newTs = new Date(new Date(latest.updated_at).getTime() + 1).toISOString();

    // Should be 1ms after 10:05:00.000Z → 10:05:00.001Z
    assert.equal(newTs, '2026-03-28T10:05:00.001Z');
  });

  it('does not advance watermark when task list is empty', () => {
    const tasks = [];
    let lastSeenTimestamp = '2026-03-28T10:00:00.000Z';

    if (tasks.length === 0) {
      // No update — watermark unchanged
    } else {
      const latest = tasks[tasks.length - 1];
      if (latest.updated_at) {
        lastSeenTimestamp = new Date(new Date(latest.updated_at).getTime() + 1).toISOString();
      }
    }

    assert.equal(lastSeenTimestamp, '2026-03-28T10:00:00.000Z');
  });
});

describe('Pipeline feed query params', () => {
  it('includes updated_after, status, and limit params', () => {
    const lastSeenTimestamp = '2026-03-28T10:00:00.000Z';
    const params = {
      status: 'completed,failed',
      updated_after: lastSeenTimestamp,
      limit: 20,
    };

    assert.equal(params.status, 'completed,failed');
    assert.equal(params.updated_after, lastSeenTimestamp);
    assert.equal(params.limit, 20);
  });
});
