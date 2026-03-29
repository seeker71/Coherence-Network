/**
 * Thin REST client for the Coherence Network API.
 * All bot reads/writes go through this module — no direct DB access.
 */

import fetch from 'node-fetch';

const BASE = process.env.COHERENCE_API_BASE ?? 'https://api.coherencycoin.com';
const TIMEOUT_MS = 10_000;

async function request(method, path, body = undefined) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = text; }
    return { ok: res.ok, status: res.status, data };
  } finally {
    clearTimeout(timer);
  }
}

/** GET /api/health */
export async function getHealth() {
  return request('GET', '/api/health');
}

/**
 * GET /api/ideas
 * @param {Object} params - query params e.g. { stage: 'specced,implementing,testing', limit: 100 }
 */
export async function getIdeas(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request('GET', `/api/ideas${qs ? `?${qs}` : ''}`);
}

/** GET /api/ideas/:id */
export async function getIdea(id) {
  return request('GET', `/api/ideas/${id}`);
}

/** GET /api/contributors/:id */
export async function getContributor(id) {
  return request('GET', `/api/contributors/${id}`);
}

/**
 * POST /api/ideas
 * @param {{ name: string, description: string, potential_value?: number }} payload
 */
export async function createIdea(payload) {
  return request('POST', '/api/ideas', payload);
}

/**
 * POST /api/investments
 * @param {{ idea_id: string, amount_cc: number, rationale?: string, contributor_id: string }} payload
 */
export async function createInvestment(payload) {
  return request('POST', '/api/investments', payload);
}

/**
 * GET /api/tasks
 * @param {Object} params - e.g. { status: 'completed,failed', limit: 20, updated_after: isoString }
 */
export async function getTasks(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request('GET', `/api/tasks${qs ? `?${qs}` : ''}`);
}

/**
 * POST /api/ideas/:ideaId/questions/:questionIndex/vote
 * @param {string} ideaId
 * @param {number} questionIndex
 * @param {{ polarity: 'positive'|'negative'|'excited', discord_user_id: string }} body
 */
export async function voteOnQuestion(ideaId, questionIndex, body) {
  return request('POST', `/api/ideas/${ideaId}/questions/${questionIndex}/vote`, body);
}
