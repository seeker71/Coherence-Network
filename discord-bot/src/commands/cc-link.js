/**
 * /cc-link slash command (spec-167).
 * Links a Discord user to a Coherence Network contributor ID for attribution.
 *
 * Usage: /cc-link contributor_id:<string>
 *
 * After linking, /cc-idea and /cc-stake will automatically use the mapped
 * contributor_id for API calls (idea submission, investments).
 */

import { SlashCommandBuilder } from 'discord.js';
import { contributors } from '../lib/db.js';
import { getContributor } from '../lib/api.js';
import log from '../lib/logger.js';

export const data = new SlashCommandBuilder()
  .setName('cc-link')
  .setDescription('Link your Discord account to your Coherence Network contributor ID')
  .addStringOption(opt =>
    opt
      .setName('contributor_id')
      .setDescription('Your contributor ID (e.g. "alice" or a UUID)')
      .setRequired(true)
  );

export async function execute(interaction) {
  const contributorId = interaction.options.getString('contributor_id').trim();

  if (!contributorId || contributorId.length < 1) {
    await interaction.reply({
      content: '❌ `contributor_id` cannot be empty.',
      ephemeral: true,
    });
    return;
  }

  // Defer reply as API check might take time
  await interaction.deferReply({ ephemeral: true });

  try {
    const { ok, data } = await getContributor(contributorId);
    if (!ok) {
      await interaction.editReply({
        content: `❌ Contributor \`${contributorId}\` not found in the network. Use a valid name or UUID from \`/api/contributors\`.`,
      });
      return;
    }

    const existing = contributors.getContributorId(interaction.user.id);
    contributors.link(interaction.user.id, contributorId);

    if (existing && existing !== contributorId) {
      await interaction.editReply({
        content: `🔄 Updated: your Discord account is now mapped to contributor \`${contributorId}\` (was \`${existing}\`).`,
      });
    } else if (existing === contributorId) {
      await interaction.editReply({
        content: `✅ Already linked: your Discord account is mapped to contributor \`${contributorId}\`.`,
      });
    } else {
      await interaction.editReply({
        content: `✅ Linked! Your Discord account is now mapped to contributor \`${contributorId}\`.\nYou can now use \`/cc-idea\` and \`/cc-stake\` with automatic attribution.`,
      });
    }

    log.info(`/cc-link: ${interaction.user.tag} → contributor ${contributorId}`);
  } catch (err) {
    log.error(`/cc-link error: ${err.message}`);
    await interaction.editReply({
      content: '❌ Failed to validate contributor ID due to an internal error. Please try again later.',
    });
  }
}
