/**
 * Onboarding commands: onboarding register, onboarding session, onboarding upgrade
 */

import { get, post } from "../api.mjs";

/** Register a new contributor (Trust-on-First-Use) */
export async function onboardingRegister(args) {
  let handle = null;
  let email = null;
  let hintGithub = null;
  let hintWallet = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--handle" && args[i + 1]) handle = args[++i];
    else if (args[i] === "--email" && args[i + 1]) email = args[++i];
    else if (args[i] === "--hint-github" && args[i + 1]) hintGithub = args[++i];
    else if (args[i] === "--hint-wallet" && args[i + 1]) hintWallet = args[++i];
  }

  if (!handle) {
    console.log("Usage: coh onboarding register --handle <name> [--email e] [--hint-github gh] [--hint-wallet addr]");
    return;
  }

  const body = { handle };
  if (email) body.email = email;
  if (hintGithub) body.hint_github = hintGithub;
  if (hintWallet) body.hint_wallet = hintWallet;

  const result = await post("/api/onboarding/register", body);
  if (!result) return;

  console.log(`\x1b[1m  REGISTERED\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Contributor ID: ${result.contributor_id}`);
  console.log(`  Handle:         ${result.handle}`);
  console.log(`  Trust Level:    ${result.trust_level}`);
  console.log(`  Session Token:  ${result.session_token}`);
  console.log(`  Save this token securely for API access.`);
  if (result.roi_signals) {
    console.log(`  ROI Signals:    Registrations: ${result.roi_signals.handle_registrations}`);
  }
  console.log();
}

/** Get contributor profile from session token */
export async function onboardingSession(args) {
  let token = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--token" && args[i + 1]) token = args[++i];
  }

  if (!token) {
    console.log("Usage: coh onboarding session --token <token>");
    return;
  }

  try {
    const { getHubUrl, getApiKey } = await import("../lib/config.mjs");
    const base = getHubUrl().replace(/\/$/, "");
    const headers = { "Content-Type": "application/json" };
    const key = getApiKey();
    if (key) headers["X-API-Key"] = key;
    headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${base}/api/onboarding/session`, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(12000),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      console.error(`\x1b[2m  ${res.status}: ${err.detail || "request failed"}\x1b[0m`);
      return;
    }

    const data = await res.json();
    console.log(`\x1b[1m  SESSION\x1b[0m`);
    console.log(`  ${"─".repeat(50)}`);
    console.log(`  Contributor ID: ${data.contributor_id}`);
    console.log(`  Handle:         ${data.handle}`);
    console.log(`  Trust Level:    ${data.trust_level}`);
    console.log(`  Created:        ${new Date(data.created).toLocaleString()}`);
    if (data.email) console.log(`  Email:          ${data.email}`);
    if (data.hint_github) console.log(`  GitHub Hint:    ${data.hint_github}`);
    if (data.hint_wallet) console.log(`  Wallet Hint:    ${data.hint_wallet}`);
    console.log();
  } catch (err) {
    console.error(`\x1b[2m  network error: ${err.message}\x1b[0m`);
  }
}

/** Upgrade trust level to verified (stub) */
export async function onboardingUpgrade() {
  const result = await post("/api/onboarding/upgrade", {});
  if (!result) return;

  if (result.detail) {
    console.log(`  ${result.detail}`);
    console.log(`  Full OAuth flow coming in Spec 169.`);
    return;
  }

  console.log(`\x1b[1m  UPGRADED\x1b[0m`);
  console.log(`  Trust Level: ${result.trust_level}`);
  console.log();
}
