/**
 * Reaction vote handler (spec-164 R7).
 * Maps Discord emoji reactions to API vote polarity values.
 */

import { voteOnQuestion } from './api.js';
import log from './logger.js';

const EMOJI_TO_POLARITY = {
  '👍': 'positive',
  '👎': 'negative',
  '🔥': 'excited',
};

/**
 * Handle a reaction add event on a pinned idea card.
 * @param {import('discord.js').MessageReaction} reaction
 * @param {import('discord.js').User} user
 * @param {string} ideaId
 */
export async function handleReactionVote(reaction, user, ideaId) {
  if (user.bot) return;
  const polarity = EMOJI_TO_POLARITY[reaction.emoji.name];
  if (!polarity) return;

  // The open_questions[0] is the primary question on the card
  const questionIndex = 0;
  const result = await voteOnQuestion(ideaId, questionIndex, {
    polarity,
    discord_user_id: user.id,
  });

  if (result.ok) {
    log.info(`Vote recorded: ${user.tag} → ${polarity} on ${ideaId}[${questionIndex}]`);
  } else if (result.status === 409) {
    // Duplicate vote — silently ignore per spec
    log.debug(`Duplicate vote ignored: ${user.tag} on ${ideaId}`);
  } else {
    log.warn(`Vote failed: ${result.status} for ${user.tag} on ${ideaId}`);
  }
}

export { EMOJI_TO_POLARITY };
