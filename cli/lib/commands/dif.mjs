/**
 * DIF commands — cc dif verify, cc dif key, cc dif config, etc.
 */

import { readFileSync } from "node:fs";
import {
  getDifConfig, setDifConfig, getDifKey, setDifKey,
  difFetch, difVerify,
} from "../dif.mjs";

// ── Formatting helpers ──────────────────────────────────────────────

const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
const G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m", C = "\x1b[36m";

function hr() { console.log(`  ${"─".repeat(60)}`); }

function errorMsg(status, data, retryAfter) {
  if (status === 401) console.log(`  ${RED}✗${R} 401 Unauthorized — API key invalid or missing`);
  else if (status === 403) console.log(`  ${RED}✗${R} 403 Forbidden — insufficient permissions`);
  else if (status === 409) console.log(`  ${RED}✗${R} 409 Conflict — ${typeof data === "object" ? JSON.stringify(data) : data}`);
  else if (status === 429) {
    const retry = retryAfter ? ` (retry after ${retryAfter}s)` : "";
    console.log(`  ${RED}✗${R} 429 Rate limited${retry}`);
  }
  else if (status >= 500) console.log(`  ${RED}✗${R} ${status} Server error`);
  else console.log(`  ${RED}✗${R} ${status} ${typeof data === "string" ? data : JSON.stringify(data)}`);
}

// ── cc dif config ───────────────────────────────────────────────────

export function showConfig() {
  const cfg = getDifConfig();
  const key = getDifKey();
  console.log(`\n${B}  DIF CONFIGURATION${R}`);
  hr();
  console.log(`  Base URL:       ${cfg.base_url}`);
  console.log(`  Response mode:  ${cfg.response_mode}`);
  console.log(`  Sensitivity:    ${cfg.sensitivity}`);
  console.log(`  Selected key:   ${cfg.selected_key_id || D + "(none)" + R}`);
  console.log(`  API key:        ${key.api_key ? G + "configured" + R : D + "not set" + R}`);
  if (key.key_id) console.log(`  Key ID:         ${key.key_id}`);
  if (key.expires_at) console.log(`  Expires:        ${key.expires_at}`);
  console.log();
}

export function setBaseUrl(args) {
  const url = args[0];
  if (!url) { console.log("Usage: cc dif config set-base-url <url>"); return; }
  setDifConfig({ base_url: url });
  console.log(`  ${G}✓${R} Base URL set to ${url}`);
}

// ── cc dif whoami ───────────────────────────────────────────────────

export async function whoami() {
  const { status, data } = await difFetch("GET", "/api/v2/dif/me");
  if (status !== 200) { errorMsg(status, data); return; }
  console.log(`\n${B}  DIF IDENTITY${R}`);
  hr();
  if (typeof data === "object") {
    for (const [k, v] of Object.entries(data)) {
      console.log(`  ${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`);
    }
  } else {
    console.log(`  ${data}`);
  }
  console.log();
}

// ── cc dif key ──────────────────────────────────────────────────────

export async function keyList() {
  const { status, data } = await difFetch("GET", "/api/v2/dif/me/api-keys");
  if (status !== 200) { errorMsg(status, data); return; }
  const keys = Array.isArray(data) ? data : (data.keys || data.items || [data]);
  console.log(`\n${B}  DIF API KEYS${R} (${keys.length})`);
  hr();
  for (const k of keys) {
    const active = k.active !== false && !k.revoked;
    const dot = active ? `${G}●${R}` : `${RED}○${R}`;
    console.log(`  ${dot} ${k.id || k.key_id || "?"}  ${D}${k.name || ""}${R}  ${k.preview || ""}`);
    if (k.expires_at) console.log(`    expires: ${k.expires_at}`);
  }
  console.log();
}

export async function keyCreate(args) {
  const name = args.join(" ") || "cc-cli";
  const { status, data, headers } = await difFetch("POST", "/api/v2/dif/me/api-keys", { name });
  if (status !== 200 && status !== 201) { errorMsg(status, data, headers?.get("retry-after")); return; }

  const keyValue = data.api_key || data.key || data.secret || "";
  const keyId = data.id || data.key_id || "";
  const preview = data.preview || (keyValue ? keyValue.slice(0, 8) + "..." : "");

  if (keyValue) {
    setDifKey({ api_key: keyValue, key_id: keyId, created_at: new Date().toISOString(), expires_at: data.expires_at || "" });
    setDifConfig({ selected_key_id: keyId, selected_key_preview: preview });
  }

  console.log(`  ${G}✓${R} Key created: ${keyId}`);
  if (keyValue) console.log(`  ${Y}Secret (shown once):${R} ${keyValue}`);
  console.log(`  Saved to ~/.coherence-network/keys.json`);
}

export async function keyRevoke(args) {
  const keyId = args[0];
  if (!keyId) { console.log("Usage: cc dif key revoke <key-id>"); return; }
  const { status, data } = await difFetch("DELETE", `/api/v2/dif/me/api-keys/${keyId}`);
  if (status !== 200 && status !== 204) { errorMsg(status, data); return; }
  console.log(`  ${G}✓${R} Key ${keyId} revoked`);
}

export async function keyRotate(args) {
  const keyId = args[0];
  if (!keyId) { console.log("Usage: cc dif key rotate <key-id>"); return; }
  const { status, data } = await difFetch("POST", `/api/v2/dif/me/api-keys/${keyId}/rotate`);
  if (status !== 200) { errorMsg(status, data); return; }

  const newKey = data.api_key || data.key || data.secret || "";
  if (newKey) {
    setDifKey({ api_key: newKey, key_id: keyId, created_at: new Date().toISOString() });
  }
  console.log(`  ${G}✓${R} Key ${keyId} rotated`);
  if (newKey) console.log(`  ${Y}New secret (shown once):${R} ${newKey}`);
}

export async function keyUpdate(args) {
  const keyId = args[0];
  if (!keyId) { console.log("Usage: cc dif key update <key-id> [--name ...] [--expires ...]"); return; }
  const body = {};
  for (let i = 1; i < args.length; i++) {
    if (args[i] === "--name" && args[i + 1]) body.name = args[++i];
    if (args[i] === "--expires" && args[i + 1]) body.expires_at = args[++i];
  }
  const { status, data } = await difFetch("PATCH", `/api/v2/dif/me/api-keys/${keyId}`, body);
  if (status !== 200) { errorMsg(status, data); return; }
  console.log(`  ${G}✓${R} Key ${keyId} updated`);
}

export async function keyUse(args) {
  const keyId = args[0];
  if (!keyId) { console.log("Usage: cc dif key use <key-id>"); return; }
  setDifConfig({ selected_key_id: keyId });
  console.log(`  ${G}✓${R} Selected key: ${keyId}`);
}

export function keyShow() {
  const key = getDifKey();
  if (!key.api_key) { console.log(`  ${D}No DIF key configured${R}`); return; }
  console.log(`  Key ID:    ${key.key_id || "?"}`);
  console.log(`  Preview:   ${key.api_key.slice(0, 12)}...`);
  console.log(`  Created:   ${key.created_at || "?"}`);
  console.log(`  Expires:   ${key.expires_at || "never"}`);
}

// ── cc dif usage / limits / funding ─────────────────────────────────

export async function showUsage(args) {
  const days = args.find(a => a.startsWith("--days"))?.split("=")[1] || "30";
  const { status, data } = await difFetch("GET", `/api/v2/dif/me/usage?days=${days}`);
  if (status !== 200) { errorMsg(status, data); return; }
  console.log(`\n${B}  DIF USAGE${R} (${days} days)`);
  hr();
  if (typeof data === "object") {
    for (const [k, v] of Object.entries(data)) {
      console.log(`  ${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`);
    }
  }
  console.log();
}

export async function showLimits() {
  const { status, data } = await difFetch("GET", "/api/v2/dif/me/limits");
  if (status !== 200) { errorMsg(status, data); return; }
  console.log(`\n${B}  DIF LIMITS${R}`);
  hr();
  if (typeof data === "object") {
    for (const [k, v] of Object.entries(data)) {
      console.log(`  ${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`);
    }
  }
  console.log();
}

export async function showFunding() {
  const { status, data } = await difFetch("GET", "/api/v2/dif/me/funding");
  if (status !== 200) { errorMsg(status, data); return; }
  console.log(`\n${B}  DIF FUNDING${R}`);
  hr();
  if (typeof data === "object") {
    for (const [k, v] of Object.entries(data)) {
      console.log(`  ${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`);
    }
  }
  console.log();
}

// ── cc dif verify ───────────────────────────────────────────────────

export async function verify(args) {
  let language = "", code = "", filePath = "", jsonMode = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--language" && args[i + 1]) language = args[++i];
    else if (args[i] === "--code" && args[i + 1]) code = args[++i];
    else if (args[i] === "--file" && args[i + 1]) filePath = args[++i];
    else if (args[i] === "--json") jsonMode = true;
  }

  if (!language) { console.log("Usage: cc dif verify --language <lang> --code <code> | --file <path>"); return; }
  if (filePath) {
    try { code = readFileSync(filePath, "utf-8"); }
    catch (e) { console.log(`  ${RED}✗${R} Cannot read file: ${filePath}`); return; }
  }
  if (!code) { console.log("  Provide --code or --file"); return; }

  const { status, data, latency, headers } = await difVerify(language, code);

  if (jsonMode) {
    console.log(JSON.stringify({ status, latency_ms: latency, ...data }, null, 2));
    return;
  }

  if (status !== 200) {
    errorMsg(status, data, headers?.get("retry-after"));
    return;
  }

  const scores = data.scores || {};
  const stream = data.stream || data.base_stream || "?";
  const verdict = data.verdict || "?";
  const trust = data.trust_signal || "?";

  console.log(`\n${B}  DIF VERIFY${R}`);
  hr();
  console.log(`  Status:       ${G}${status}${R}`);
  console.log(`  Stream:       ${stream === "anomaly" ? RED : stream === "clean" ? G : Y}${stream}${R}`);
  console.log(`  Verdict:      ${verdict}`);
  console.log(`  Trust:        ${trust}`);
  console.log(`  Latency:      ${latency}ms`);
  if (scores.verification != null) console.log(`  Verification: ${scores.verification}`);
  if (scores.semantic_support != null) console.log(`  Semantic:     ${scores.semantic_support}`);
  if (scores.structural_cost != null) console.log(`  Structural:   ${scores.structural_cost}`);
  if (data.snippet_loc != null) console.log(`  LOC:          ${data.snippet_loc}`);
  if (data.language) console.log(`  Language:     ${data.language}`);

  const tags = data.tags || [];
  if (tags.length) console.log(`  Tags:         ${D}${tags.join(", ")}${R}`);
  console.log();
}

// ── cc dif smoke ────────────────────────────────────────────────────

export async function smoke() {
  console.log(`\n${B}  DIF SMOKE TEST${R}`);
  hr();

  const cfg = getDifConfig();
  const key = getDifKey();
  console.log(`  Base URL:  ${cfg.base_url}`);
  console.log(`  API Key:   ${key.api_key ? G + "configured" + R : Y + "anonymous" + R}`);
  console.log();

  // 1. Anonymous verify
  console.log(`  ${D}1. Anonymous verify (C: int main)...${R}`);
  const { status: s1, data: d1, latency: l1 } = await difVerify("c", 'int main(){return 0;}');
  if (s1 === 200) {
    console.log(`  ${G}✓${R} ${s1} — stream=${d1.stream || "?"} verification=${d1.scores?.verification ?? "?"} ${D}${l1}ms${R}`);
  } else {
    console.log(`  ${RED}✗${R} ${s1}`);
  }

  // 2. Multi-language
  console.log(`  ${D}2. Python verify...${R}`);
  const { status: s2, data: d2, latency: l2 } = await difVerify("python", 'print("hello")');
  if (s2 === 200) {
    console.log(`  ${G}✓${R} ${s2} — stream=${d2.stream || "?"} ${D}${l2}ms${R}`);
  } else {
    console.log(`  ${RED}✗${R} ${s2}`);
  }

  // 3. Key management (if key configured)
  if (key.api_key) {
    console.log(`  ${D}3. Key identity check...${R}`);
    const { status: s3 } = await difFetch("GET", "/api/v2/dif/me");
    console.log(`  ${s3 === 200 ? G + "✓" : RED + "✗"}${R} whoami: ${s3}`);

    console.log(`  ${D}4. Usage check...${R}`);
    const { status: s4 } = await difFetch("GET", "/api/v2/dif/me/usage");
    console.log(`  ${s4 === 200 ? G + "✓" : RED + "✗"}${R} usage: ${s4}`);
  } else {
    console.log(`  ${D}3-4. Skipped (no API key)${R}`);
  }

  console.log();
  console.log(`  ${G}Smoke test complete${R}`);
  console.log();
}


// ── cc dif key ensure ──────────────────────────────────────────────

export async function keyEnsure() {
  const { getMerlySession, getAccessToken, merlyAuthedPost } = await import("../merly_auth.mjs");
  const { difFetch } = await import("../dif.mjs");

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log(`\n${B}  DIF KEY ENSURE${R}`);
  console.log(`  ${"─".repeat(50)}`);

  // Step 1: Check Merly login
  const token = await getAccessToken();
  if (!token) {
    console.log(`  ${RED}✗${R} Not logged into Merly. Run: cc login merly`);
    return;
  }
  console.log(`  ${G}✓${R} Merly session active`);

  // Step 2: Check for existing DIF key locally
  const { getDifKey } = await import("../dif.mjs");
  const localKey = getDifKey();
  if (localKey.api_key) {
    // Verify it still works
    const { status } = await difFetch("GET", "/api/v2/dif/me");
    if (status === 200) {
      console.log(`  ${G}✓${R} DIF key active: ${localKey.api_key.slice(0, 12)}...`);
      console.log(`  ${D}Key ID: ${localKey.key_id || "?"}${R}`);
      console.log();
      return;
    }
    console.log(`  ${Y}!${R} Local DIF key expired or invalid — requesting new one`);
  }

  // Step 3: Check for existing keys on Merly
  const { status: listStatus, data: listData } = await difFetch("GET", "/api/v2/dif/me/api-keys", null, { bearer: token });
  if (listStatus === 200) {
    const keys = Array.isArray(listData) ? listData : (listData.keys || listData.items || []);
    const active = keys.filter(k => k.active !== false && !k.revoked);
    if (active.length > 0) {
      // Use the most recent active key
      const key = active[0];
      console.log(`  ${G}✓${R} Found existing active DIF key on Merly: ${key.id || key.key_id}`);
      // We can't recover the secret — need to create a new one
      if (key.preview || key.key_prefix) {
        console.log(`  ${D}Preview: ${key.preview || key.key_prefix}${R}`);
      }
      console.log(`  ${Y}!${R} Cannot recover key secret — creating a new one`);
    }
  }

  // Step 4: Create new DIF key via Merly
  const { status: createStatus, data: createData } = await merlyAuthedPost(
    "/api/v2/dif/me/api-keys",
    { name: "cc-cli" },
    token,
  );

  if (createStatus !== 200 && createStatus !== 201) {
    console.log(`  ${RED}✗${R} Failed to create DIF key: ${createStatus}`);
    if (typeof createData === "object") console.log(`  ${D}${JSON.stringify(createData)}${R}`);
    return;
  }

  const newKey = createData.api_key || createData.key || createData.secret || "";
  const keyId = createData.id || createData.key_id || "";

  if (!newKey) {
    console.log(`  ${RED}✗${R} Merly returned no key value. Response: ${JSON.stringify(createData).slice(0, 200)}`);
    return;
  }

  // Step 5: Store locally
  const { setDifKey, setDifConfig } = await import("../dif.mjs");
  setDifKey({
    api_key: newKey,
    key_id: keyId,
    created_at: new Date().toISOString(),
    source: "merly",
  });
  setDifConfig({
    selected_key_id: keyId,
    selected_key_preview: newKey.slice(0, 8) + "...",
  });

  console.log(`  ${G}✓${R} DIF key created and stored`);
  console.log(`  ${D}Key ID: ${keyId}${R}`);
  console.log(`  ${Y}Secret (stored locally):${R} ${newKey.slice(0, 12)}...`);
  console.log();
}


// ── cc dif key status ──────────────────────────────────────────────

export async function keyStatus() {
  const { getMerlySession, isLoggedIn } = await import("../merly_auth.mjs");
  const { getDifKey, getDifConfig } = await import("../dif.mjs");

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log(`\n${B}  DIF KEY STATUS${R}`);
  console.log(`  ${"─".repeat(50)}`);

  // Merly session
  const loggedIn = isLoggedIn();
  const session = getMerlySession();
  console.log(`  Merly auth:    ${loggedIn ? G + "active" + R : RED + "not logged in" + R}`);
  if (session?.identity) {
    const id = session.identity;
    console.log(`  Merly identity: ${id.display_name || id.email || id.contributor_id || "?"}`);
  }
  if (session?.logged_in_at) {
    console.log(`  Logged in:     ${D}${session.logged_in_at}${R}`);
  }

  // DIF key
  const key = getDifKey();
  const cfg = getDifConfig();
  const hasKey = !!key.api_key;
  console.log(`  DIF key:       ${hasKey ? G + "configured" + R : Y + "not set" + R}`);
  if (hasKey) {
    console.log(`  Key ID:        ${key.key_id || "?"}`);
    console.log(`  Preview:       ${key.api_key.slice(0, 12)}...`);
    console.log(`  Source:        ${key.source || "manual"}`);
    if (key.created_at) console.log(`  Created:       ${D}${key.created_at}${R}`);
  }

  console.log(`  DIF base URL:  ${cfg.base_url}`);

  // Verify key works
  if (hasKey) {
    try {
      const { difFetch } = await import("../dif.mjs");
      const { status } = await difFetch("GET", "/api/v2/dif/me");
      console.log(`  Key valid:     ${status === 200 ? G + "yes" + R : RED + "no (" + status + ")" + R}`);
    } catch {
      console.log(`  Key valid:     ${RED}unreachable${R}`);
    }
  }

  console.log();
}


// ── cc dif feedback ────────────────────────────────────────────────

export async function showFeedback(args) {
  const { get } = await import("../api.mjs");
  const data = await get("/api/graph/dif/feedback/stats");
  if (!data) { console.log("  Could not fetch DIF feedback stats"); return; }

  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", RED = "\x1b[31m";

  console.log(`\n${B}  DIF FEEDBACK STATS${R}`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Total verifications: ${data.total || 0}`);
  console.log(`  True positives:      ${G}${data.true_positives || 0}${R}`);
  console.log(`  False positives:     ${Y}${data.false_positives || 0}${R}`);
  console.log(`  True negatives:      ${G}${data.true_negatives || 0}${R}`);
  console.log(`  FP rate:             ${data.false_positive_rate || 0}`);
  console.log(`  Accuracy:            ${data.accuracy || 0}`);
  if (data.by_language) {
    console.log(`  By language:         ${JSON.stringify(data.by_language)}`);
  }
  if (data.by_trust_signal) {
    console.log(`  By trust signal:     ${JSON.stringify(data.by_trust_signal)}`);
  }
  console.log();
}
