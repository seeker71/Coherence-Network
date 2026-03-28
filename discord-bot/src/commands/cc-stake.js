/**
 * /cc-stake slash command (spec-164 R5).
 * Invests CC in an idea with a confirmation prompt.
 */

import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';
import { getIdea, createInvestment } from '../lib/api.js';
import { buildStakeConfirmEmbed, buildStakeSuccessEmbed } from '../lib/embeds.js';
import { contributors } from '../lib/db.js';
import log from '../lib/logger.js';

const CONFIRM_TIMEOUT_MS = 30_000;

export const data = new SlashCommandBuilder()
  .setName('cc-stake')
  .setDescription('Invest CC in a Coherence Network idea')
  .addStringOption(opt =>
    opt.setName('idea_id').setDescription('Idea ID to stake on').setRequired(true)
  )
  .addNumberOption(opt =>
    opt.setName('amount').setDescription('CC amount to stake').setRequired(true).setMinValue(1)
  )
  .addStringOption(opt =>
    opt.setName('rationale').setDescription('Why are you staking?').setRequired(false)
  );

export async function execute(interaction) {
  const ideaId = interaction.options.getString('idea_id');
  const amount = interaction.options.getNumber('amount');
  const rationale = interaction.options.getString('rationale');

  await interaction.deferReply({ ephemeral: true });

  // Fetch idea details
  const ideaRes = await getIdea(ideaId);
  if (!ideaRes.ok || !ideaRes.data) {
    await interaction.editReply({ content: `❌ Idea \`${ideaId}\` not found.` });
    return;
  }
  const idea = ideaRes.data;

  // Show confirmation prompt
  const confirmEmbed = buildStakeConfirmEmbed(idea, amount);
  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId('stake_confirm').setLabel('✅ Confirm').setStyle(ButtonStyle.Success),
    new ButtonBuilder().setCustomId('stake_cancel').setLabel('❌ Cancel').setStyle(ButtonStyle.Danger),
  );

  const reply = await interaction.editReply({ embeds: [confirmEmbed], components: [row] });

  try {
    const btnInteraction = await reply.awaitMessageComponent({
      filter: i => i.user.id === interaction.user.id,
      time: CONFIRM_TIMEOUT_MS,
    });

    if (btnInteraction.customId === 'stake_cancel') {
      await btnInteraction.update({ content: 'Stake cancelled.', embeds: [], components: [] });
      return;
    }

    // Execute the investment
    const contributorId = contributors.getContributorId(interaction.user.id) ?? interaction.user.id;
    const investRes = await createInvestment({
      idea_id: ideaId,
      amount_cc: amount,
      ...(rationale ? { rationale } : {}),
      contributor_id: contributorId,
    });

    if (!investRes.ok) {
      const detail = investRes.data?.detail ?? JSON.stringify(investRes.data);
      await btnInteraction.update({ content: `❌ Stake failed: ${detail}`, embeds: [], components: [] });
      return;
    }

    const successEmbed = buildStakeSuccessEmbed(idea, amount, investRes.data);

    // Post public confirmation to #bot-commands
    const commandsChannelName = process.env.DISCORD_COMMANDS_CHANNEL ?? 'bot-commands';
    const publicChannel = interaction.guild.channels.cache.find(c => c.name === commandsChannelName);
    if (publicChannel) {
      await publicChannel.send({
        content: `💎 <@${interaction.user.id}> staked **${amount} CC** on **${idea.name}**`,
        embeds: [successEmbed],
      });
    }

    await btnInteraction.update({ embeds: [successEmbed], components: [] });
    log.info(`Stake executed: ${amount} CC on ${ideaId} by ${interaction.user.tag}`);
  } catch (err) {
    if (err.code === 'InteractionCollectorError') {
      await interaction.editReply({ content: '⏰ Confirmation timed out.', embeds: [], components: [] });
    } else {
      log.error('/cc-stake error', { error: err.message });
      await interaction.editReply({ content: '❌ Unexpected error processing stake.', embeds: [], components: [] });
    }
  }
}
