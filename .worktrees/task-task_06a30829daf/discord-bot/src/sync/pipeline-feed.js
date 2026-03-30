/**
 * Pipeline event feed loop (spec-164 R6).
 * Polls GET /api/tasks every POLL_INTERVAL_SEC seconds and posts
 * new completions/failures to #pipeline-feed.
 */

import { getTasks } from '../lib/api.js';
import { buildPipelineEventEmbed } from '../lib/embeds.js';
import log from '../lib/logger.js';

let lastSeenTimestamp = new Date(Date.now() - 5 * 60_000).toISOString(); // Look back 5 min on start

/**
 * Fetch new pipeline events and post them to #pipeline-feed.
 * @param {import('discord.js').TextChannel} feedChannel
 */
export async function pollPipelineFeed(feedChannel) {
  try {
    const res = await getTasks({
      status: 'completed,failed',
      updated_after: lastSeenTimestamp,
      limit: 20,
    });

    if (!res.ok) {
      log.warn('Pipeline feed poll failed', { status: res.status });
      return;
    }

    const tasks = Array.isArray(res.data) ? res.data : (res.data?.tasks ?? []);
    if (tasks.length === 0) return;

    // Sort oldest-first so feed reads chronologically
    tasks.sort((a, b) => new Date(a.updated_at ?? 0) - new Date(b.updated_at ?? 0));

    for (const task of tasks) {
      const embed = buildPipelineEventEmbed(task);
      await feedChannel.send({ embeds: [embed] });
      log.debug(`Posted pipeline event for task ${task.id ?? task.task_id}`);
    }

    // Advance watermark to latest seen
    const latest = tasks[tasks.length - 1];
    if (latest.updated_at) {
      lastSeenTimestamp = new Date(new Date(latest.updated_at).getTime() + 1).toISOString();
    }
  } catch (err) {
    log.error('Pipeline feed poll error', { error: err.message });
  }
}
