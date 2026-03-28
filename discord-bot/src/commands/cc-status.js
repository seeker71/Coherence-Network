/**
 * /cc-status slash command (spec-164 R4).
 * Shows pipeline health from GET /api/health.
 */

import { SlashCommandBuilder, PermissionFlagsBits } from 'discord.js';
import { getHealth, getTasks } from '../lib/api.js';
import { buildHealthEmbed } from '../lib/embeds.js';
import log from '../lib/logger.js';

export const data = new SlashCommandBuilder()
  .setName('cc-status')
  .setDescription('Display Coherence Network pipeline health')
  .addBooleanOption(opt =>
    opt.setName('verbose').setDescription('Include 10 recent task completions').setRequired(false)
  );

export async function execute(interaction) {
  await interaction.deferReply();

  try {
    const healthRes = await getHealth();
    if (!healthRes.ok) {
      await interaction.editReply({ content: `❌ API unreachable (HTTP ${healthRes.status})` });
      return;
    }

    const embed = buildHealthEmbed(healthRes.data);
    const embeds = [embed];

    const verbose = interaction.options.getBoolean('verbose') ?? false;
    if (verbose) {
      const tasksRes = await getTasks({ limit: 10, sort: 'updated_desc' });
      if (tasksRes.ok) {
        const tasks = Array.isArray(tasksRes.data) ? tasksRes.data : (tasksRes.data?.tasks ?? []);
        if (tasks.length > 0) {
          const lines = tasks.map(t => `• \`${t.id ?? t.task_id}\` ${t.task_type ?? t.type} — ${t.status}`);
          embed.addFields({ name: 'Recent Tasks', value: lines.join('\n').slice(0, 1024) });
        }
      }
    }

    await interaction.editReply({ embeds });
  } catch (err) {
    log.error('/cc-status error', { error: err.message });
    await interaction.editReply({ content: '❌ Unexpected error fetching pipeline status.' });
  }
}
