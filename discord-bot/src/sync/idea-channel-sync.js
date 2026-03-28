/**
 * Active idea channel sync loop (spec-164 R1).
 * Creates/updates #idea-<slug> channels, archives old ones,
 * pins embeds, adds vote reactions, and creates question threads (R8).
 */

import { ChannelType, PermissionFlagsBits } from 'discord.js';
import { getIdeas } from '../lib/api.js';
import { buildIdeaEmbed } from '../lib/embeds.js';
import { channels, threads } from '../lib/db.js';
import { EMOJI_TO_POLARITY } from '../lib/reactions.js';
import log from '../lib/logger.js';

const ACTIVE_STAGES = ['specced', 'implementing', 'testing'];
const MAX_ACTIVE_CHANNELS = 50;
const CHANNEL_CREATE_DELAY_MS = 1_000; // Rate limit mitigation
const MAX_THREADS_PER_CHANNEL = 20;

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 90);
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

/**
 * Ensure required categories exist in the guild.
 */
async function ensureCategory(guild, name) {
  const existing = guild.channels.cache.find(
    c => c.type === ChannelType.GuildCategory && c.name === name
  );
  if (existing) return existing;
  return guild.channels.create({ name, type: ChannelType.GuildCategory });
}

/**
 * Get or create a named text channel inside a category.
 */
async function ensureChannel(guild, channelName, category, description = '') {
  const existing = guild.channels.cache.find(
    c => c.type === ChannelType.GuildText && c.name === channelName
  );
  if (existing) return { channel: existing, created: false };

  const channel = await guild.channels.create({
    name: channelName,
    type: ChannelType.GuildText,
    parent: category.id,
    topic: description.slice(0, 1024),
  });
  return { channel, created: true };
}

/**
 * Pin (or update) the idea embed in the channel.
 * Returns the pinned message.
 */
async function upsertPinnedEmbed(channel, idea) {
  const embed = buildIdeaEmbed(idea);
  const pins = await channel.messages.fetchPinned();
  const existing = pins.find(m => m.author.id === channel.client.user.id);

  if (existing) {
    await existing.edit({ embeds: [embed] });
    return existing;
  }

  const msg = await channel.send({ embeds: [embed] });
  await msg.pin();
  for (const emoji of Object.keys(EMOJI_TO_POLARITY)) {
    await msg.react(emoji);
  }
  return msg;
}

/**
 * Auto-create threads for open questions (R8).
 */
async function syncQuestionThreads(channel, idea) {
  const questions = idea.open_questions ?? [];
  const cap = Math.min(questions.length, MAX_THREADS_PER_CHANNEL);

  for (let i = 0; i < cap; i++) {
    const q = questions[i];
    const existing = threads.get(idea.id, i);

    if (existing?.answered) continue; // Already archived

    const threadName = `❓ ${(q.question ?? 'Open question').slice(0, 80)}`;

    if (!existing) {
      try {
        const thread = await channel.threads.create({
          name: threadName,
          autoArchiveDuration: 10080, // 1 week
          reason: `Open question #${i} for idea ${idea.id}`,
        });
        await thread.send(
          `**${q.question ?? 'Open question'}**\n\n` +
          `Estimated cost: ${q.estimated_cost ?? '?'} · Value to whole: ${q.value_to_whole ?? '?'}`
        );
        threads.set(idea.id, i, thread.id);
        log.info(`Created thread for ${idea.id}[${i}]`, { threadId: thread.id });
      } catch (err) {
        log.warn(`Could not create thread for ${idea.id}[${i}]`, { error: err.message });
      }
    } else if (q.answer && !existing.answered) {
      // Archive the thread with the answer
      try {
        const thread = await channel.client.channels.fetch(existing.thread_id);
        if (thread) {
          await thread.send(`✅ Answered: ${q.answer}`);
          await thread.setArchived(true);
        }
        threads.markAnswered(idea.id, i);
        log.info(`Archived answered thread ${idea.id}[${i}]`);
      } catch (err) {
        log.warn(`Could not archive thread ${idea.id}[${i}]`, { error: err.message });
      }
    }
  }
}

/**
 * Main sync function — run on startup and every SYNC_INTERVAL_MIN minutes.
 * @param {import('discord.js').Client} client
 */
export async function syncIdeaChannels(client) {
  const guildId = process.env.DISCORD_GUILD_ID;
  if (!guildId) { log.warn('DISCORD_GUILD_ID not set — skipping sync'); return; }

  const guild = await client.guilds.fetch(guildId);
  await guild.channels.fetch(); // Populate cache

  const activeCategoryName = process.env.DISCORD_ACTIVE_CATEGORY ?? 'Active Ideas';
  const archiveCategoryName = process.env.DISCORD_ARCHIVE_CATEGORY ?? 'Archived Ideas';

  const [activeCategory, archiveCategory] = await Promise.all([
    ensureCategory(guild, activeCategoryName),
    ensureCategory(guild, archiveCategoryName),
  ]);

  // Fetch active ideas from API
  const res = await getIdeas({ limit: MAX_ACTIVE_CHANNELS });
  if (!res.ok) {
    log.error('Failed to fetch ideas for sync', { status: res.status });
    return;
  }

  const allIdeas = res.data?.ideas ?? res.data ?? [];
  const activeIdeas = allIdeas.filter(i => ACTIVE_STAGES.includes(i.manifestation_status));
  log.info(`Syncing ${activeIdeas.length} active ideas`);

  // Create/update channels for active ideas
  for (const idea of activeIdeas) {
    const slug = slugify(idea.name ?? idea.id);
    const channelName = `idea-${slug}`;

    try {
      const { channel, created } = await ensureChannel(
        guild, channelName, activeCategory,
        (idea.description ?? '').slice(0, 200)
      );
      channels.set(idea.id, channel.id, guild.id);

      await upsertPinnedEmbed(channel, idea);
      await syncQuestionThreads(channel, idea);

      if (created) {
        log.info(`Created channel ${channelName} for idea ${idea.id}`);
        await sleep(CHANNEL_CREATE_DELAY_MS);
      }
    } catch (err) {
      log.error(`Error syncing channel for idea ${idea.id}`, { error: err.message });
    }
  }

  // Archive channels for ideas no longer in active stages
  const stored = channels.getAll();
  const activeIds = new Set(activeIdeas.map(i => i.id));

  for (const row of stored) {
    if (row.archived) continue;
    if (!activeIds.has(row.idea_id)) {
      try {
        const ch = guild.channels.cache.get(row.discord_channel_id);
        if (ch) {
          await ch.setParent(archiveCategory.id);
          await ch.permissionOverwrites.edit(guild.roles.everyone, {
            [PermissionFlagsBits.SendMessages]: false,
          });
        }
        channels.archive(row.idea_id);
        log.info(`Archived channel for inactive idea ${row.idea_id}`);
      } catch (err) {
        log.warn(`Could not archive channel for ${row.idea_id}`, { error: err.message });
      }
    }
  }
}
