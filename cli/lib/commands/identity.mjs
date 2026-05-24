/**
 * Identity commands: show, link, unlink, lookup, setup
 */

import { get, post, del } from "../api.mjs";
import {
  getContributorId,
  getContributorSource,
  saveConfig,
  parseContributorId,
} from "../config.mjs";
import { ensureIdentity } from "../identity.mjs";

export async function showIdentity() {
  const rawId = getContributorId();
  const id = parseContributorId(rawId);
  const source = getContributorSource();
  if (!id) {
    if (rawId) {
      console.log("Configured identity is invalid.");
    }
    console.log("No identity configured.");
    console.log("  Fix: coh identity set <your_id>");
    return;
  }
  const data = await get(`/api/identity/${encodeURIComponent(id)}`);

  console.log();
  console.log(`\x1b[1m  ${id}\x1b[0m`);
  console.log(`  ${"─".repeat(40)}`);
  console.log(`  Source:  ${source}`);

  if (!data || !Array.isArray(data) || data.length === 0) {
    console.log("  No linked accounts.");
  } else {
    for (const rec of data) {
      const dot = rec.verified ? "\x1b[32m●\x1b[0m" : "\x1b[33m○\x1b[0m";
      console.log(`  ${dot} ${rec.provider.padEnd(14)} ${rec.provider_id}`);
    }
  }
  console.log();
  console.log("  Link more: coh identity link <provider> <id>");
  console.log();
}

export async function linkIdentity(args) {
  const [provider, ...rest] = args;
  const providerId = rest.join(" ");
  if (!provider || !providerId) {
    console.log("Usage: coh identity link <provider> <id>");
    console.log("Providers: github, x, discord, telegram, ethereum, bitcoin, solana, email, gitlab, linkedin, ...");
    return;
  }
  const contributor = await ensureIdentity();
  const result = await post("/api/identity/link", {
    contributor_id: contributor,
    provider,
    provider_id: providerId,
    display_name: providerId,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Linked ${provider}:${providerId}`);
  } else {
    console.log("Link failed.");
  }
}

export async function unlinkIdentity(args) {
  const provider = args[0];
  if (!provider) {
    console.log("Usage: coh identity unlink <provider>");
    return;
  }
  const contributor = parseContributorId(getContributorId());
  if (!contributor) {
    console.log("No identity configured.");
    return;
  }
  const ok = await del(`/api/identity/${encodeURIComponent(contributor)}/${provider}`);
  if (ok) {
    console.log(`\x1b[32m✓\x1b[0m Unlinked ${provider}`);
  } else {
    console.log("Unlink failed or not found.");
  }
}

export async function lookupIdentity(args) {
  const [provider, providerId] = args;
  if (!provider || !providerId) {
    console.log("Usage: coh identity lookup <provider> <id>");
    return;
  }
  const data = await get(`/api/identity/lookup/${encodeURIComponent(provider)}/${encodeURIComponent(providerId)}`);
  if (data) {
    console.log(`\x1b[32m✓\x1b[0m ${provider}:${providerId} → contributor: ${data.contributor_id}`);
  } else {
    console.log(`No contributor found for ${provider}:${providerId}`);
  }
}

export async function setIdentity(args) {
  if (args.length !== 1) {
    console.error("Usage: coh identity set <contributor_id>");
    process.exitCode = 1;
    return;
  }
  const id = parseContributorId(args[0]);
  if (!id) {
    console.error(
      "Error: invalid contributor_id — use only letters, numbers, hyphens, underscores, periods (max 64 chars)",
    );
    process.exitCode = 1;
    return;
  }
  saveConfig({ contributor_id: id });
  console.log(`\x1b[32m✓\x1b[0m Identity set to: ${id}`);
}

export async function setupIdentity() {
  // Force re-run onboarding
  await ensureIdentity();
}

/**
 * Cross-instance pubkey claim — identity by cryptographic possession.
 *
 * The contributor proves they hold the private half of an ed25519 keypair
 * by signing a canonical payload with it. The instance verifies the
 * signature and links the pubkey to the contributor — no central
 * registry, no instance permission, just verifiable possession.
 *
 * Usage:
 *   coh identity claim --pubkey <hex> --signature <hex> --issued-at <iso>
 *   coh identity claim --pubkey <hex> --signature <hex> --issued-at <iso> \
 *                      --rotates-from <old-hex> --rotation-signature <hex> \
 *                      --rotation-issued-at <iso>
 */
export async function claimPubkey(args) {
  const opts = parseFlags(args);
  if (!opts.pubkey || !opts.signature) {
    console.log("Usage: coh identity claim --pubkey <hex> --signature <hex> [--issued-at <iso>]");
    console.log("       [--rotates-from <old-hex> --rotation-signature <hex> --rotation-issued-at <iso>]");
    console.log();
    console.log("The signature is over canonical JSON of:");
    console.log("  { contributor_id, public_key_hex, issued_at }");
    console.log("signed with the private half of the new pubkey.");
    return;
  }
  const contributor = await ensureIdentity();
  const issuedAt = opts["issued-at"] || new Date().toISOString();
  const claimPayload = {
    contributor_id: contributor,
    public_key_hex: opts.pubkey,
    issued_at: issuedAt,
  };
  const body = {
    contributor_id: contributor,
    public_key_hex: opts.pubkey,
    claim_signature: opts.signature,
    claim_payload: claimPayload,
  };
  if (opts["rotates-from"]) {
    if (!opts["rotation-signature"]) {
      console.log("Rotation requires --rotation-signature signed by the OLD pubkey.");
      return;
    }
    const rotationIssuedAt = opts["rotation-issued-at"] || issuedAt;
    body.rotation_payload = {
      contributor_id: contributor,
      public_key_hex: opts.pubkey,
      issued_at: rotationIssuedAt,
      rotates_from: opts["rotates-from"],
    };
    body.rotation_signature = opts["rotation-signature"];
  }
  const result = await post("/api/identity/claim", body);
  if (!result) {
    console.log("Claim failed.");
    return;
  }
  if (result.rotated) {
    console.log(`\x1b[32m✓\x1b[0m Pubkey rotated for ${contributor}`);
  } else if (result.idempotent) {
    console.log(`\x1b[32m✓\x1b[0m Pubkey already claimed for ${contributor} (idempotent)`);
  } else {
    console.log(`\x1b[32m✓\x1b[0m Pubkey claimed for ${contributor}`);
  }
  console.log(`  pubkey: ${result.public_key_hex}`);
}

/**
 * List known cross-instance aliases for the current contributor.
 */
export async function showAliases() {
  const contributor = parseContributorId(getContributorId());
  if (!contributor) {
    console.log("No identity configured.");
    return;
  }
  const data = await get(`/api/federation/identity/aliases/${encodeURIComponent(contributor)}`);
  if (!data) {
    console.log("Could not load aliases.");
    return;
  }
  const aliases = data.aliases || [];
  console.log();
  console.log(`\x1b[1m  Cross-instance aliases for ${contributor}\x1b[0m`);
  console.log(`  ${"─".repeat(40)}`);
  if (aliases.length === 0) {
    console.log("  No cross-instance aliases recognized yet.");
  } else {
    for (const a of aliases) {
      const dot = a.signature_verified ? "\x1b[32m●\x1b[0m" : "\x1b[33m○\x1b[0m";
      console.log(`  ${dot} ${a.peer_instance_id.padEnd(24)} ${a.peer_contributor_id}`);
    }
  }
  console.log();
}

function parseFlags(args) {
  const opts = {};
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = args[i + 1];
      if (next === undefined || next.startsWith("--")) {
        opts[key] = true;
      } else {
        opts[key] = next;
        i++;
      }
    }
  }
  return opts;
}
