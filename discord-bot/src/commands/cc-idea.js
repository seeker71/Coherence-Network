/**
 * /cc-idea slash command (spec-164 R3).
 * Submits a new idea to the Coherence Network API from Discord.
 */

import { SlashCommandBuilder, ChannelType } from 'discord.js';
import { createIdea } from '../lib/api.js';
import { buildIdeaEmbed } from '../lib/embeds.js';
import { rateLimits, contributors } from '../lib/db.js';
import log from '../lib/logger.js';

const RATE_LIMIT_MS = 10 * 60 * 1000; // 10 minutes

export const data = new SlashCommandBuilder()
  .setName('cc-idea')
  .setDescription('Submit a new idea to the Coherence Network')
  .addStringOption(opt =>
    opt.setName('name').setDescription('Idea name').setRequired(true)
  )
  .addStringOption(opt =>
    opt.setName('description').setDescription('What problem does this solve?').setRequired(true)
  )
  .addNumberOption(opt =>
    opt.setName('potential_value').setDescription('Estimated CC value').setRequired(false)
  );

export async function execute(interaction) {
  const rateLimitKey = `cc-idea:${interaction.user.id}`;

  if (rateLimits.isLimited(rateLimitKey)) {
    const remaining = rateLimits.remainingSeconds(rateLimitKey);
    await interaction.reply({
      content: `⏳ Rate limit: wait ${Math.ceil(remaining / 60)} minute(s) before submitting another idea.`,
      ephemeral: true,
    });
    return;
  }

  await interaction.deferReply();

  const name = interaction.options.getString('name');
  const description = interaction.options.getString('description');
  const potentialValue = interaction.options.getNumber('potential_value');

  const contributorId = contributors.getContributorId(interaction.user.id);

  const payload = {
    name,
    description,
    interfaces: ['discord'],
    ...(potentialValue != null ? { potential_value: potentialValue } : {}),
    ...(contributorId ? { contributor_id: contributorId } : {}),
  };

  try {
    const res = await createIdea(payload);

    if (!res.ok) {
      const detail = res.data?.detail ?? JSON.stringify(res.data);
      await interaction.editReply({ content: `❌ Failed to submit idea: ${detail}`, ephemeral: true });
      return;
    }

    const idea = res.data;
    rateLimits.set(rateLimitKey, RATE_LIMIT_MS);

    // Post the idea card to #idea-submissions
    const submissionsChannelName = process.env.DISCORD_SUBMISSIONS_CHANNEL ?? 'idea-submissions';
    const guild = interaction.guild;
    const submissionsChannel = guild.channels.cache.find(c => c.name === submissionsChannelName);

    const embed = buildIdeaEmbed(idea);

    if (submissionsChannel) {
      await submissionsChannel.send({ embeds: [embed] });
    }

    await interaction.editReply({
      content: `✅ Idea submitted! ID: \`${idea.id}\`\nCheck <#${submissionsChannel?.id ?? submissionsChannelName}> for the card.`,
      embeds: [embed],
    });

    // DM the user
    try {
      await interaction.user.send(
        `🎉 Idea submitted! **${idea.name}** · ID: \`${idea.id}\`\n+5 CC for submission`
      );
    } catch {
      // DMs disabled — not critical
    }

    log.info(`Idea submitted via Discord: ${idea.id} by ${interaction.user.tag}`);
  } catch (err) {
    log.error('/cc-idea error', { error: err.message });
    await interaction.editReply({ content: '❌ Unexpected error submitting idea.' });
  }
}
