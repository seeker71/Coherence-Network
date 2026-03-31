/**
 * Merly OAuth integration — device/browser flow for CLI.
 *
 * Stores Merly session in ~/.coherence-network/keys.json under "merly".
 * Token is a Bearer access_token used for DIF key management.
 *
 * Flow:
 *   1. POST /api/v2/auth/device/code → { device_code, user_code, verification_uri }
 *   2. User opens browser to verification_uri and enters user_code
 *   3. CLI polls POST /api/v2/auth/device/token until granted
 *   4. Store { access_token, refresh_token, expires_at } locally
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { execSync } from "node:child_process";

const CONFIG_DIR = join(homedir(), ".coherence-network");
const KEYS_PATH = join(CONFIG_DIR, "keys.json");

const MERLY_BASE = "https://coherency-network.merly-mentor.ai";
const POLL_INTERVAL_MS = 5000;
const MAX_POLL_ATTEMPTS = 60; // 5 min max

// ── Storage ────────────────────────────────────────────────────

function _readKeys() {
  try { return JSON.parse(readFileSync(KEYS_PATH, "utf-8")); }
  catch { return {}; }
}

function _writeKeys(data) {
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(KEYS_PATH, JSON.stringify(data, null, 2) + "\n", { mode: 0o600 });
}

export function getMerlySession() {
  const keys = _readKeys();
  return keys.merly || null;
}

export function setMerlySession(session) {
  const keys = _readKeys();
  keys.merly = session;
  _writeKeys(keys);
}

export function clearMerlySession() {
  const keys = _readKeys();
  delete keys.merly;
  _writeKeys(keys);
}

export function isLoggedIn() {
  const session = getMerlySession();
  if (!session || !session.access_token) return false;
  if (session.expires_at && Date.now() > session.expires_at) return false;
  return true;
}

// ── HTTP helpers ───────────────────────────────────────────────

async function merlyPost(path, body) {
  const resp = await fetch(`${MERLY_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  return { status: resp.status, data: await resp.json().catch(() => ({})) };
}

async function merlyGet(path, accessToken) {
  const resp = await fetch(`${MERLY_BASE}${path}`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    signal: AbortSignal.timeout(15000),
  });
  return { status: resp.status, data: await resp.json().catch(() => ({})) };
}

export async function merlyAuthedPost(path, body, accessToken) {
  const resp = await fetch(`${MERLY_BASE}${path}`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  return { status: resp.status, data: await resp.json().catch(() => ({})) };
}

// ── Device flow ────────────────────────────────────────────────

function openBrowser(url) {
  try {
    const platform = process.platform;
    if (platform === "darwin") execSync(`open "${url}"`);
    else if (platform === "win32") execSync(`start "" "${url}"`);
    else execSync(`xdg-open "${url}" 2>/dev/null || echo ""`);
  } catch {
    // Browser open failed — user will click the URL manually
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Interactive device flow login.
 * Returns { access_token, refresh_token, expires_at, identity } or null on failure.
 */
export async function loginDeviceFlow() {
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", C = "\x1b[36m";

  console.log(`\n${B}  MERLY LOGIN${R}`);
  console.log(`  ${"─".repeat(50)}`);

  // Step 1: Request device code
  const { status: codeStatus, data: codeData } = await merlyPost("/api/v2/auth/device/code", {
    client_id: "cc-cli",
    scope: "dif:manage dif:verify identity:read",
  });

  if (codeStatus !== 200) {
    // Fallback: if Merly doesn't support device flow, use direct browser login
    console.log(`  ${D}Device flow not available (${codeStatus}). Using browser login...${R}`);
    return loginBrowserFlow();
  }

  const { device_code, user_code, verification_uri, expires_in } = codeData;
  const verifyUrl = verification_uri || `${MERLY_BASE}/auth/device`;

  console.log(`  ${Y}1.${R} Open this URL in your browser:`);
  console.log(`     ${C}${verifyUrl}${R}`);
  console.log();
  console.log(`  ${Y}2.${R} Enter this code when prompted:`);
  console.log(`     ${B}${user_code}${R}`);
  console.log();

  openBrowser(verifyUrl);
  console.log(`  ${D}Waiting for authorization...${R}`);

  // Step 2: Poll for token
  for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
    await sleep(POLL_INTERVAL_MS);

    const { status, data } = await merlyPost("/api/v2/auth/device/token", {
      client_id: "cc-cli",
      device_code,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
    });

    if (status === 200 && data.access_token) {
      // Success — store and return
      const session = {
        access_token: data.access_token,
        refresh_token: data.refresh_token || null,
        expires_at: data.expires_in ? Date.now() + data.expires_in * 1000 : null,
        token_type: data.token_type || "Bearer",
        logged_in_at: new Date().toISOString(),
      };

      // Fetch identity
      const { status: meStatus, data: meData } = await merlyGet("/api/v2/dif/me", session.access_token);
      if (meStatus === 200) {
        session.identity = meData;
      }

      setMerlySession(session);

      console.log(`  ${G}✓${R} Logged in to Merly`);
      if (session.identity) {
        const id = session.identity;
        console.log(`  ${D}Identity: ${id.display_name || id.email || id.contributor_id || "unknown"}${R}`);
      }
      console.log();
      return session;
    }

    if (data.error === "authorization_pending") {
      process.stdout.write(`\r  ${D}Waiting... (${i + 1}/${MAX_POLL_ATTEMPTS})${R}`);
      continue;
    }

    if (data.error === "slow_down") {
      await sleep(5000); // Extra backoff
      continue;
    }

    if (data.error === "expired_token" || data.error === "access_denied") {
      console.log(`\n  \x1b[31m✗\x1b[0m ${data.error}: ${data.error_description || "Authorization denied or expired"}`);
      return null;
    }
  }

  console.log(`\n  \x1b[31m✗\x1b[0m Timed out waiting for authorization`);
  return null;
}

/**
 * Fallback: browser-based login with localhost callback.
 * Opens Merly login page, starts a local HTTP server to catch the callback.
 */
async function loginBrowserFlow() {
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", C = "\x1b[36m";
  const { createServer } = await import("node:http");
  const { URL } = await import("node:url");

  const PORT = 19847; // High port unlikely to conflict
  const REDIRECT_URI = `http://localhost:${PORT}/callback`;
  const LOGIN_URL = `${MERLY_BASE}/auth/login?redirect_uri=${encodeURIComponent(REDIRECT_URI)}&client_id=cc-cli&scope=dif:manage+dif:verify+identity:read`;

  console.log(`  Opening browser for login...`);
  console.log(`  ${C}${LOGIN_URL}${R}`);
  console.log();

  openBrowser(LOGIN_URL);

  return new Promise((resolve) => {
    const timeout = setTimeout(() => {
      server.close();
      console.log(`  \x1b[31m✗\x1b[0m Timed out waiting for callback`);
      resolve(null);
    }, 300000); // 5 min

    const server = createServer(async (req, res) => {
      const url = new URL(req.url, `http://localhost:${PORT}`);

      if (url.pathname === "/callback") {
        const code = url.searchParams.get("code");
        const token = url.searchParams.get("access_token");
        const error = url.searchParams.get("error");

        if (error) {
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end("<h2>Login failed</h2><p>You can close this tab.</p>");
          clearTimeout(timeout);
          server.close();
          resolve(null);
          return;
        }

        let accessToken = token;

        // If we got a code, exchange it for a token
        if (code && !accessToken) {
          const { status, data } = await merlyPost("/api/v2/auth/token", {
            grant_type: "authorization_code",
            code,
            redirect_uri: REDIRECT_URI,
            client_id: "cc-cli",
          });
          if (status === 200 && data.access_token) {
            accessToken = data.access_token;
          }
        }

        if (accessToken) {
          const session = {
            access_token: accessToken,
            refresh_token: null,
            expires_at: null,
            token_type: "Bearer",
            logged_in_at: new Date().toISOString(),
          };

          // Fetch identity
          const { status: meStatus, data: meData } = await merlyGet("/api/v2/dif/me", accessToken);
          if (meStatus === 200) {
            session.identity = meData;
          }

          setMerlySession(session);

          res.writeHead(200, { "Content-Type": "text/html" });
          res.end("<h2>Logged in!</h2><p>You can close this tab and return to your terminal.</p>");

          console.log(`  ${G}✓${R} Logged in to Merly`);
          if (session.identity) {
            const id = session.identity;
            console.log(`  ${D}Identity: ${id.display_name || id.email || id.contributor_id || "unknown"}${R}`);
          }
          console.log();

          clearTimeout(timeout);
          server.close();
          resolve(session);
        } else {
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end("<h2>Login failed</h2><p>No token received. You can close this tab.</p>");
          clearTimeout(timeout);
          server.close();
          resolve(null);
        }
      }
    });

    server.listen(PORT, () => {
      console.log(`  ${D}Listening on localhost:${PORT} for callback...${R}`);
    });
  });
}

/**
 * Refresh the access token using the refresh token.
 */
export async function refreshToken() {
  const session = getMerlySession();
  if (!session?.refresh_token) return null;

  const { status, data } = await merlyPost("/api/v2/auth/token", {
    grant_type: "refresh_token",
    refresh_token: session.refresh_token,
    client_id: "cc-cli",
  });

  if (status === 200 && data.access_token) {
    const updated = {
      ...session,
      access_token: data.access_token,
      refresh_token: data.refresh_token || session.refresh_token,
      expires_at: data.expires_in ? Date.now() + data.expires_in * 1000 : session.expires_at,
    };
    setMerlySession(updated);
    return updated;
  }

  return null;
}

/**
 * Get a valid access token — refresh if needed.
 */
export async function getAccessToken() {
  const session = getMerlySession();
  if (!session?.access_token) return null;

  // Check expiry — refresh if within 5 minutes
  if (session.expires_at && Date.now() > session.expires_at - 300000) {
    const refreshed = await refreshToken();
    if (refreshed) return refreshed.access_token;
    return null; // Refresh failed — need re-login
  }

  return session.access_token;
}

/**
 * Get identity from Merly using current session.
 */
export async function getIdentity() {
  const token = await getAccessToken();
  if (!token) return null;

  const { status, data } = await merlyGet("/api/v2/dif/me", token);
  if (status === 200) return data;
  return null;
}
