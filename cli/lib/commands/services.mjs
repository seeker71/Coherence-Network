/**
 * Services commands: services, service, services health, services deps
 */

import { get } from "../api.mjs";

/** Truncate at word boundary, append "..." if needed */
function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  const trimmed = str.slice(0, len - 3);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > len * 0.4 ? trimmed.slice(0, lastSpace) : trimmed) + "...";
}

export async function listServices() {
  const raw = await get("/api/services");
  const data = Array.isArray(raw) ? raw : raw?.services;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch services.");
    return;
  }
  if (data.length === 0) {
    console.log("No services found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  SERVICES\x1b[0m (${data.length})`);
  console.log(`  ${"─".repeat(68)}`);
  for (const s of data) {
    const name = truncate(s.name || s.id, 28).padEnd(30);
    const status = (s.status || "?").toLowerCase();
    const dot = status === "healthy" || status === "up" ? "\x1b[32m●\x1b[0m"
      : status === "degraded" ? "\x1b[33m●\x1b[0m"
      : "\x1b[31m●\x1b[0m";
    const ver = s.version ? `\x1b[2mv${s.version}\x1b[0m`.padEnd(20) : "\x1b[2m-\x1b[0m".padEnd(20);
    const caps = s.capabilities ? `${Array.isArray(s.capabilities) ? s.capabilities.length : 0} caps` : "";
    console.log(`  ${dot} ${name} ${ver} ${caps}`);
  }
  console.log();
}

export async function showService(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc service <id>");
    return;
  }
  const data = await get(`/api/services/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Service '${id}' not found.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  ${data.name || data.id}\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.id) console.log(`  ID:          ${data.id}`);
  if (data.status) console.log(`  Status:      ${data.status}`);
  if (data.version) console.log(`  Version:     ${data.version}`);
  if (data.url) console.log(`  URL:         ${data.url}`);
  if (data.uptime) console.log(`  Uptime:      ${data.uptime}`);
  console.log();
}

export async function showServicesHealth() {
  const data = await get("/api/services/health");
  if (!data) {
    console.log("Could not fetch services health.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  SERVICES HEALTH\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (Array.isArray(data)) {
    for (const s of data) {
      const name = truncate(s.name || s.id, 25);
      const status = s.status || s.health || "?";
      const dot = status === "healthy" || status === "up" ? "\x1b[32m●\x1b[0m" : "\x1b[31m●\x1b[0m";
      console.log(`  ${dot} ${name.padEnd(27)} ${status}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}

export async function showServicesDeps() {
  const data = await get("/api/services/dependencies");
  if (!data) {
    console.log("Could not fetch service dependencies.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  SERVICE DEPENDENCIES\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (Array.isArray(data)) {
    for (const d of data) {
      const from = truncate(d.from || d.service || "?", 20);
      const to = truncate(d.to || d.depends_on || "?", 20);
      console.log(`  ${from.padEnd(22)} \x1b[2m→\x1b[0m ${to}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}
