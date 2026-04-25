/**
 * Coherence Network Discord bot — entry point (spec-164).
 *
 * Wires together:
 * - Discord.js client with Gateway intents
 * - Slash command handler
 * - Idea channel sync loop (R1)
 * - Pipeline feed loop (R6)
 * - Reaction vote handler (R7)
 */

import 'dotenv/config';
import {
  Client,
  GatewayIntentBits,
  Collection,
  Events,
  Partials,
} from 'discord.js';

import * as ccStatus from './commands/cc-status.js';
import * as ccIdea from './commands/cc-idea.js';
import * as ccLink from './commands/cc-link.js';
import * as ccStake from './commands/cc-stake.js';

import { syncIdeaChannels } from './sync/idea-channel-sync.js';
import { pollPipelineFeed } from './sync/pipeline-feed.js';
import { handleReactionVote } from './lib/reactions.js';
import { channels } from './lib/db.js';
import log from './lib/logger.js';

// ── Client setup ──────────────────────────────────────────────────────────────

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.GuildMessageReactions,
    GatewayIntentBits.MessageContent,
  ],
  partials: [Partials.Message, Partials.Channel, Partials.Reaction],
});

// ── Command registry ──────────────────────────────────────────────────────────

client.commands = new Collection();
for (const cmd of [ccStatus, ccIdea, ccLink, ccStake]) {
  client.commands.set(cmd.data.name, cmd);
}

// ── Event: Ready ──────────────────────────────────────────────────────────────

client.once(Events.ClientReady, async (readyClient) => {
  log.info(`Logged in as ${readyClient.user.tag}`);

  // Initial sync
  await syncIdeaChannels(client).catch(err =>
    log.error('Initial idea sync failed', { error: err.message })
  );

  // Periodic idea channel sync
  const syncIntervalMin = parseInt(process.env.SYNC_INTERVAL_MIN ?? '5', 10);
  setInterval(
    () => syncIdeaChannels(client).catch(err => log.error('Sync loop error', { error: err.message })),
    syncIntervalMin * 60 * 1000
  );

  // Pipeline feed polling
  const feedChannelName = process.env.DISCORD_PIPELINE_CHANNEL ?? 'pipeline-feed';
  const guildId = process.env.DISCORD_GUILD_ID;
  if (guildId) {
    const guild = await client.guilds.fetch(guildId).catch(() => null);
    if (guild) {
      await guild.channels.fetch();
      const feedChannel = guild.channels.cache.find(c => c.name === feedChannelName);
      if (feedChannel) {
        const pollIntervalSec = parseInt(process.env.POLL_INTERVAL_SEC ?? '60', 10);
        setInterval(
          () => pollPipelineFeed(feedChannel).catch(err =>
            log.error('Pipeline feed error', { error: err.message })
          ),
          pollIntervalSec * 1000
        );
        log.info(`Pipeline feed polling every ${pollIntervalSec}s → #${feedChannelName}`);
      } else {
        log.warn(`#${feedChannelName} channel not found — pipeline feed disabled`);
      }
    }
  }
});

// ── Event: Slash commands ─────────────────────────────────────────────────────

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  const command = client.commands.get(interaction.commandName);
  if (!command) {
    log.warn(`Unknown command: ${interaction.commandName}`);
    return;
  }

  try {
    await command.execute(interaction);
  } catch (err) {
    log.error(`Command ${interaction.commandName} failed`, { error: err.message });
    const msg = { content: '❌ An error occurred executing this command.', ephemeral: true };
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp(msg).catch(() => null);
    } else {
      await interaction.reply(msg).catch(() => null);
    }
  }
});

// ── Event: Reactions (R7) ─────────────────────────────────────────────────────

client.on(Events.MessageReactionAdd, async (reaction, user) => {
  if (reaction.partial) {
    try { await reaction.fetch(); } catch { return; }
  }
  if (user.bot) return;

  // Find which idea this pinned message belongs to
  const allChannels = channels.getAll();
  const row = allChannels.find(r => r.discord_channel_id === reaction.message.channelId);
  if (!row) return;

  // Only handle reactions on pinned messages
  const pins = await reaction.message.channel.messages.fetchPinned().catch(() => new Map());
  if (!pins.has(reaction.message.id)) return;

  await handleReactionVote(reaction, user, row.idea_id);
});

// ── Start ─────────────────────────────────────────────────────────────────────

const TOKEN = process.env.DISCORD_TOKEN;
if (!TOKEN) {
  log.error('DISCORD_TOKEN is not set. Exiting.');
  process.exit(1);
}

client.login(TOKEN).catch(err => {
  log.error('Failed to login', { error: err.message });
  process.exit(1);
});
