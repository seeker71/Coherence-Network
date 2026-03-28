/**
 * Coherence Network Discord bot (discord.js v14).
 * Slash: /cc-idea, /cc-status, /cc-stake — channels per active idea, embeds, reactions, question threads, pipeline feed poll.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  ChannelType,
  Client,
  EmbedBuilder,
  GatewayIntentBits,
  Partials,
  PermissionFlagsBits,
  REST,
  Routes,
  SlashCommandBuilder,
} from "discord.js";
import "dotenv/config";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, "..", "data");
const CHANNEL_MAP_PATH = path.join(DATA_DIR, "channel-map.json");
const SEEN_EVENTS_PATH = path.join(DATA_DIR, "seen-event-ids.json");

const API_BASE = (process.env.COHERENCE_API_BASE_URL || "https://api.coherencycoin.com").replace(/\/$/, "");
const GUILD_ID = process.env.DISCORD_GUILD_ID || "";
const CATEGORY_ID = process.env.DISCORD_IDEAS_CATEGORY_ID || null;
const FEED_CHANNEL_ID = process.env.DISCORD_PIPELINE_FEED_CHANNEL_ID || "";
const POLL_MS = Math.max(15000, parseInt(process.env.DISCORD_FEED_POLL_MS || "60000", 10));
const SYNC_MS = Math.max(60000, parseInt(process.env.DISCORD_CHANNEL_SYNC_MS || "300000", 10));

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function readJson(file, fallback) {
  try {
    const raw = fs.readFileSync(file, "utf8");
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function writeJson(file, obj) {
  ensureDataDir();
  fs.writeFileSync(file, JSON.stringify(obj, null, 2), "utf8");
}

function slugChannelName(ideaId) {
  const s = String(ideaId)
    .toLowerCase()
    .replace(/[^a-z0-9\-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return s || "idea-channel";
}

async function apiGet(path) {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status} ${await res.text()}`);
  return res.json();
}

async function apiPost(path, body) {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`POST ${url} -> ${res.status} ${text}`);
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

function ideaEmbed(idea) {
  const embed = new EmbedBuilder()
    .setTitle(idea.name || idea.id)
    .setDescription((idea.description || "").slice(0, 4000))
    .setColor(0x5865f2)
    .addFields(
      { name: "Stage", value: String(idea.stage || "?"), inline: true },
      { name: "ROI (CC)", value: String(idea.roi_cc ?? "?"), inline: true },
      { name: "Free energy", value: String(idea.free_energy_score ?? "?"), inline: true },
      { name: "Idea ID", value: `\`${idea.id}\``, inline: false },
    )
    .setFooter({ text: "Coherence Network · reaction vote · threads for open questions" });
  return embed;
}

function pipelineStatusEmbed(snapshot) {
  const ap = snapshot.agent_pipeline || {};
  const pipe = snapshot.pipeline || {};
  const running = Array.isArray(ap.running) ? ap.running.length : 0;
  const pending = Array.isArray(ap.pending) ? ap.pending.length : 0;
  return new EmbedBuilder()
    .setTitle("Pipeline health")
    .setColor(0x57f287)
    .setDescription(
      [
        `**Agent running:** ${running}`,
        `**Agent pending:** ${pending}`,
        `**Loop running:** ${pipe.running ?? "?"}`,
        `**Cycle count:** ${pipe.cycle_count ?? "?"}`,
        `**Tasks completed:** ${pipe.tasks_completed ?? "?"}`,
        `**Tasks failed:** ${pipe.tasks_failed ?? "?"}`,
      ].join("\n"),
    )
    .setTimestamp(new Date(snapshot.generated_at || Date.now()));
}

const commands = [
  new SlashCommandBuilder()
    .setName("cc-idea")
    .setDescription("Submit a new idea to the Coherence portfolio")
    .addStringOption((o) => o.setName("title").setDescription("Short title").setRequired(true))
    .addStringOption((o) => o.setName("description").setDescription("What to build").setRequired(true))
    .addNumberOption((o) => o.setName("potential_value").setDescription("Potential value").setRequired(true))
    .addNumberOption((o) => o.setName("estimated_cost").setDescription("Estimated cost (CC)").setRequired(true)),
  new SlashCommandBuilder().setName("cc-status").setDescription("Show agent pipeline and loop status"),
  new SlashCommandBuilder()
    .setName("cc-stake")
    .setDescription("Stake CC on an idea (links your Discord to contributor identity)")
    .addStringOption((o) => o.setName("idea_id").setDescription("Target idea id").setRequired(true))
    .addNumberOption((o) => o.setName("amount_cc").setDescription("CC amount").setRequired(true)),
].map((c) => c.toJSON());

async function registerSlashCommands(clientId, guildId, token) {
  const rest = new REST({ version: "10" }).setToken(token);
  if (guildId) {
    await rest.put(Routes.applicationGuildCommands(clientId, guildId), { body: commands });
  } else {
    await rest.put(Routes.applicationCommands(clientId), { body: commands });
  }
}

async function syncIdeaChannels(client) {
  if (!GUILD_ID || !CATEGORY_ID) return;
  const guild = await client.guilds.fetch(GUILD_ID);
  const data = await apiGet("/api/integrations/discord/ideas/active");
  const ideas = data.ideas || [];
  let map = readJson(CHANNEL_MAP_PATH, {});
  const category = await guild.channels.fetch(CATEGORY_ID);
  if (!category || category.type !== ChannelType.GuildCategory) return;

  for (const idea of ideas) {
    if (map[idea.id]) {
      const ch = guild.channels.cache.get(map[idea.id]);
      if (ch) continue;
    }
    const name = slugChannelName(idea.id);
    const existing = guild.channels.cache.find((c) => c.parentId === CATEGORY_ID && c.name === name);
    if (existing) {
      map[idea.id] = existing.id;
      continue;
    }
    const created = await guild.channels.create({
      name,
      type: ChannelType.GuildText,
      parent: CATEGORY_ID,
      permissionOverwrites: [
        { id: guild.id, deny: [PermissionFlagsBits.MentionEveryone] },
      ],
      reason: `Coherence idea channel for ${idea.id}`,
    });
    map[idea.id] = created.id;
    const main = await created.send({ embeds: [ideaEmbed(idea)] });
    await main.react("👍").catch(() => {});
    await main.react("👎").catch(() => {});

    const questions = idea.open_questions || [];
    for (const q of questions) {
      if (q.answer) continue;
      const qtext = (q.question || "").slice(0, 500);
      const qm = await created.send({ content: `**Open question** (${idea.id})\n${qtext}` });
      try {
        await qm.startThread({
          name: qtext.slice(0, 90) || "question",
          autoArchiveDuration: 1440,
          reason: "Open question thread",
        });
      } catch {
        /* thread create may fail if disabled */
      }
    }
  }
  writeJson(CHANNEL_MAP_PATH, map);
}

async function pollPipelineFeed(client) {
  if (!FEED_CHANNEL_ID) return;
  const snap = await apiGet("/api/integrations/discord/snapshot?runtime_event_limit=50");
  const events = snap.runtime_events || [];
  let seen = readJson(SEEN_EVENTS_PATH, []);
  if (!Array.isArray(seen)) seen = [];
  const channel = await client.channels.fetch(FEED_CHANNEL_ID);
  if (!channel || !channel.isTextBased()) return;

  if (seen.length === 0) {
    const seed = events.map((e) => e.id).filter(Boolean);
    writeJson(SEEN_EVENTS_PATH, seed.slice(-500));
    return;
  }

  const seenSet = new Set(seen);
  const fresh = events.filter((e) => e.id && !seenSet.has(e.id));
  for (const ev of fresh.slice().reverse()) {
    const embed = new EmbedBuilder()
      .setTitle(ev.endpoint || "Runtime")
      .setColor(0xeb459e)
      .addFields(
        { name: "Method", value: String(ev.method || "?"), inline: true },
        { name: "Status", value: String(ev.status_code ?? "?"), inline: true },
        { name: "ms", value: String(ev.runtime_ms ?? "?"), inline: true },
      )
      .setFooter({ text: ev.id ? `id: ${ev.id}` : "Coherence" });
    await channel.send({ embeds: [embed] }).catch(() => {});
    seenSet.add(ev.id);
  }
  seen = [...seenSet].slice(-500);
  writeJson(SEEN_EVENTS_PATH, seen);
}

async function main() {
  const token = process.env.DISCORD_BOT_TOKEN;
  const clientId = process.env.DISCORD_CLIENT_ID;
  if (!token || !clientId) {
    console.error("Set DISCORD_BOT_TOKEN and DISCORD_CLIENT_ID");
    process.exit(1);
  }

  await registerSlashCommands(clientId, GUILD_ID, token);

  const client = new Client({
    intents: [
      GatewayIntentBits.Guilds,
      GatewayIntentBits.GuildMessages,
      GatewayIntentBits.MessageContent,
      GatewayIntentBits.GuildMessageReactions,
    ],
    partials: [Partials.Message, Partials.Channel, Partials.Reaction],
  });

  client.once("ready", async () => {
    console.log(`Logged in as ${client.user.tag}`);
    await syncIdeaChannels(client).catch((e) => console.error("syncIdeaChannels", e));
    setInterval(() => syncIdeaChannels(client).catch(console.error), SYNC_MS);
    setInterval(() => pollPipelineFeed(client).catch(console.error), POLL_MS);
  });

  client.on("interactionCreate", async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    try {
      if (interaction.commandName === "cc-status") {
        const snap = await apiGet("/api/integrations/discord/snapshot?runtime_event_limit=5");
        await interaction.reply({ embeds: [pipelineStatusEmbed(snap)], ephemeral: false });
        return;
      }
      if (interaction.commandName === "cc-idea") {
        const title = interaction.options.getString("title", true);
        const description = interaction.options.getString("description", true);
        const potential = interaction.options.getNumber("potential_value", true);
        const cost = interaction.options.getNumber("estimated_cost", true);
        const id = `discord-${interaction.user.id}-${Date.now()}`.replace(/[^a-zA-Z0-9\-_]/g, "-").slice(0, 120);
        const body = {
          id,
          name: title,
          description,
          potential_value: potential,
          estimated_cost: cost,
          confidence: 0.5,
          interfaces: [],
          open_questions: [],
        };
        const created = await apiPost("/api/ideas", body);
        const embed = ideaEmbed({
          id: created.id || id,
          name: created.name || title,
          description: created.description || description,
          stage: created.stage || "none",
          roi_cc: created.roi_cc ?? 0,
          free_energy_score: created.free_energy_score ?? 0,
        });
        await interaction.reply({ content: "Idea created.", embeds: [embed], ephemeral: false });
        return;
      }
      if (interaction.commandName === "cc-stake") {
        const ideaId = interaction.options.getString("idea_id", true);
        const amount = interaction.options.getNumber("amount_cc", true);
        const providerId = interaction.user.id;
        const result = await apiPost(`/api/ideas/${encodeURIComponent(ideaId)}/stake`, {
          provider: "discord",
          provider_id: providerId,
          amount_cc: amount,
          rationale: "Discord /cc-stake",
        });
        const embed = new EmbedBuilder()
          .setTitle("Stake recorded")
          .setDescription(`\`\`\`json\n${JSON.stringify(result, null, 2).slice(0, 3500)}\`\`\``);
        await interaction.reply({ embeds: [embed], ephemeral: true });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (interaction.deferred || interaction.replied) {
        await interaction.followUp({ content: `Error: ${msg}`, ephemeral: true });
      } else {
        await interaction.reply({ content: `Error: ${msg}`, ephemeral: true });
      }
    }
  });

  await client.login(token);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
