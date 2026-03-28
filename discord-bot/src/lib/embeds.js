/**
 * Discord embed builders for Coherence Network bot.
 * All embeds follow spec-164 R2 formatting requirements.
 */

import { EmbedBuilder } from 'discord.js';

const STAGE_COLORS = {
  validated: 0x00c851,
  specced: 0xffbb33,
  implementing: 0x33b5e5,
  testing: 0xff8800,
};

const WEB_BASE = 'https://coherencycoin.com';

/**
 * Build the rich idea card embed (R2).
 * @param {Object} idea - idea object from the API
 * @returns {EmbedBuilder}
 */
export function buildIdeaEmbed(idea) {
  const color = STAGE_COLORS[idea.manifestation_status] ?? 0x888888;
  const url = `${WEB_BASE}/ideas/${idea.id}`;
  const description = (idea.description ?? '').slice(0, 300);

  const embed = new EmbedBuilder()
    .setColor(color)
    .setTitle(idea.name ?? idea.id)
    .setURL(url)
    .setDescription(description || '\u200B')
    .addFields(
      { name: 'Stage', value: idea.manifestation_status ?? 'unknown', inline: true },
      { name: 'Coherence', value: String(idea.coherence_score?.toFixed(3) ?? '—'), inline: true },
      { name: 'Free Energy', value: String(idea.free_energy_score?.toFixed(3) ?? '—'), inline: true },
      { name: 'Potential Value (CC)', value: String(idea.potential_value ?? '—'), inline: true },
      { name: 'Actual Value (CC)', value: String(idea.actual_value ?? '—'), inline: true },
    )
    .setFooter({ text: `idea-id: ${idea.id} · Last updated: ${idea.updated_at ?? new Date().toISOString()}` });

  return embed;
}

/**
 * Build the /cc-status health embed (R4).
 * @param {Object} health - response from GET /api/health
 * @returns {EmbedBuilder}
 */
export function buildHealthEmbed(health) {
  const isOk = health.status === 'ok';
  const color = isOk ? 0x00c851 : 0xcc0000;

  const embed = new EmbedBuilder()
    .setColor(color)
    .setTitle('Pipeline Health')
    .addFields(
      { name: 'Status', value: health.status ?? 'unknown', inline: true },
      { name: 'Version', value: health.version ?? '—', inline: true },
      { name: 'Uptime', value: health.uptime_human ?? '—', inline: true },
      { name: 'Schema', value: health.schema_ok ? '✅ ok' : '❌ error', inline: true },
      { name: 'Integrity', value: health.integrity ?? '—', inline: true },
    )
    .setFooter({ text: `Checked at ${new Date().toISOString()}` });

  return embed;
}

/**
 * Build the pipeline feed task event embed (R6).
 * @param {Object} task - task object from the API
 * @returns {EmbedBuilder}
 */
export function buildPipelineEventEmbed(task) {
  const statusMap = {
    completed: { color: 0x00c851, icon: '✅' },
    failed: { color: 0xcc0000, icon: '❌' },
    in_progress: { color: 0x33b5e5, icon: '🔄' },
  };
  const s = statusMap[task.status] ?? { color: 0x888888, icon: '⬜' };

  const durationSec = task.duration_ms != null ? `${(task.duration_ms / 1000).toFixed(1)}s` : '—';

  const embed = new EmbedBuilder()
    .setColor(s.color)
    .setTitle(`${s.icon} Task ${task.status}: ${task.task_type ?? task.type ?? 'unknown'}`)
    .addFields(
      { name: 'Task ID', value: String(task.id ?? task.task_id ?? '—'), inline: true },
      { name: 'Idea', value: String(task.idea_id ?? task.idea_name ?? '—'), inline: true },
      { name: 'Node', value: String(task.node_id ?? task.runner ?? '—'), inline: true },
      { name: 'Duration', value: durationSec, inline: true },
      { name: 'CC Earned', value: String(task.cc_earned ?? task.credits_earned ?? '—'), inline: true },
    )
    .setFooter({ text: new Date().toISOString() });

  return embed;
}

/**
 * Build the /cc-stake confirmation embed.
 * @param {Object} idea
 * @param {number} amount
 * @returns {EmbedBuilder}
 */
export function buildStakeConfirmEmbed(idea, amount) {
  return new EmbedBuilder()
    .setColor(0xffbb33)
    .setTitle(`Confirm: Stake ${amount} CC in "${idea.name}"`)
    .setDescription(`Idea ID: \`${idea.id}\`\nPotential value: ${idea.potential_value ?? '?'} CC\n\nReact ✅ to confirm or ❌ to cancel.`)
    .setFooter({ text: 'Expires in 30 seconds' });
}

/**
 * Build the investment success embed.
 */
export function buildStakeSuccessEmbed(idea, amount, investment) {
  return new EmbedBuilder()
    .setColor(0x00c851)
    .setTitle(`✅ Staked ${amount} CC in "${idea.name}"`)
    .addFields(
      { name: 'Investment ID', value: String(investment.id ?? investment.investment_id ?? '—'), inline: true },
      { name: 'Potential Value', value: String(idea.potential_value ?? '—'), inline: true },
    )
    .setFooter({ text: new Date().toISOString() });
}
