/**
 * SQLite database helpers for bot state persistence.
 * Stores Discord channel IDs for ideas to prevent duplicates (R1).
 */

import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const DATA_DIR = process.env.DATA_DIR ?? './data';
fs.mkdirSync(DATA_DIR, { recursive: true });

const channelsDb = new Database(path.join(DATA_DIR, 'channels.db'));
const contributorsDb = new Database(path.join(DATA_DIR, 'contributors.db'));

// Initialize channels table
channelsDb.exec(`
  CREATE TABLE IF NOT EXISTS idea_channels (
    idea_id TEXT PRIMARY KEY,
    discord_channel_id TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived INTEGER NOT NULL DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS question_threads (
    idea_id TEXT NOT NULL,
    question_idx INTEGER NOT NULL,
    thread_id TEXT NOT NULL,
    answered INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (idea_id, question_idx)
  );

  CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT PRIMARY KEY,
    expires_at TEXT NOT NULL
  );
`);

// Initialize contributors mapping table
contributorsDb.exec(`
  CREATE TABLE IF NOT EXISTS discord_contributors (
    discord_user_id TEXT PRIMARY KEY,
    contributor_id TEXT NOT NULL,
    linked_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

export const channels = {
  get(ideaId) {
    return channelsDb.prepare('SELECT * FROM idea_channels WHERE idea_id = ?').get(ideaId);
  },
  set(ideaId, discordChannelId, guildId) {
    channelsDb.prepare(
      'INSERT OR REPLACE INTO idea_channels (idea_id, discord_channel_id, guild_id) VALUES (?,?,?)'
    ).run(ideaId, discordChannelId, guildId);
  },
  archive(ideaId) {
    channelsDb.prepare('UPDATE idea_channels SET archived=1 WHERE idea_id=?').run(ideaId);
  },
  getAll() {
    return channelsDb.prepare('SELECT * FROM idea_channels').all();
  },
};

export const threads = {
  get(ideaId, questionIdx) {
    return channelsDb.prepare('SELECT * FROM question_threads WHERE idea_id=? AND question_idx=?').get(ideaId, questionIdx);
  },
  set(ideaId, questionIdx, threadId) {
    channelsDb.prepare(
      'INSERT OR REPLACE INTO question_threads (idea_id, question_idx, thread_id) VALUES (?,?,?)'
    ).run(ideaId, questionIdx, threadId);
  },
  markAnswered(ideaId, questionIdx) {
    channelsDb.prepare('UPDATE question_threads SET answered=1 WHERE idea_id=? AND question_idx=?').run(ideaId, questionIdx);
  },
};

export const rateLimits = {
  isLimited(key) {
    const row = channelsDb.prepare('SELECT expires_at FROM rate_limits WHERE key=?').get(key);
    if (!row) return false;
    return new Date(row.expires_at) > new Date();
  },
  set(key, durationMs) {
    const expiresAt = new Date(Date.now() + durationMs).toISOString();
    channelsDb.prepare('INSERT OR REPLACE INTO rate_limits (key, expires_at) VALUES (?,?)').run(key, expiresAt);
  },
  remainingSeconds(key) {
    const row = channelsDb.prepare('SELECT expires_at FROM rate_limits WHERE key=?').get(key);
    if (!row) return 0;
    return Math.max(0, Math.ceil((new Date(row.expires_at) - new Date()) / 1000));
  },
};

export const contributors = {
  getContributorId(discordUserId) {
    const row = contributorsDb.prepare('SELECT contributor_id FROM discord_contributors WHERE discord_user_id=?').get(discordUserId);
    return row?.contributor_id ?? null;
  },
  link(discordUserId, contributorId) {
    contributorsDb.prepare(
      'INSERT OR REPLACE INTO discord_contributors (discord_user_id, contributor_id) VALUES (?,?)'
    ).run(discordUserId, contributorId);
  },
};
