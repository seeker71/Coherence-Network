/**
 * cc update — universal update for all agent surfaces
 *
 * Updates: CLI, MCP server, OpenClaw skill, and agent config files
 * (.claude/settings.json, .cursorrules, .windsurfrules, AGENTS.md)
 */

import { execSync } from "node:child_process";
import { existsSync, writeFileSync, readFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { get } from "../api.mjs";

const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";
const DIM = "\x1b[2m";
const BOLD = "\x1b[1m";
const RESET = "\x1b[0m";

function run(cmd, opts = {}) {
  try {
    return execSync(cmd, { encoding: "utf-8", timeout: 30000, stdio: "pipe", ...opts }).trim();
  } catch {
    return null;
  }
}

function npmVersion(pkg) {
  return run(`npm view ${pkg} version`);
}

function localVersion(pkg) {
  return run(`npm list -g ${pkg} --depth=0 --json 2>/dev/null | node -e "const d=require('fs').readFileSync('/dev/stdin','utf8'); try{console.log(JSON.parse(d).dependencies['${pkg}'].version)}catch{console.log('?')}"`);
}

export async function update(args) {
  console.log(`${BOLD}  COHERENCE NETWORK UPDATE${RESET}`);
  console.log(`  ${"─".repeat(50)}`);
  console.log();

  let updated = 0;
  let skipped = 0;
  let failed = 0;

  // 1. CLI
  updated += await updateCli();

  // 2. MCP Server
  updated += await updateMcp();

  // 3. OpenClaw skill
  updated += await updateOpenClawSkill();

  // 4. Agent config files
  updated += await updateAgentConfigs();

  console.log();
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  ${GREEN}✓${RESET} ${updated} updated  ${DIM}${skipped} skipped  ${failed ? RED + failed + " failed" + RESET : ""}${RESET}`);
}

async function updateCli() {
  process.stdout.write(`  CLI (coherence-cli)... `);
  const local = localVersion("coherence-cli") || "?";
  const latest = npmVersion("coherence-cli");

  if (!latest) {
    console.log(`${RED}✗${RESET} could not check npm`);
    return 0;
  }

  if (local === latest) {
    console.log(`${GREEN}✓${RESET} v${local} ${DIM}(up to date)${RESET}`);
    return 0;
  }

  console.log(`${YELLOW}↑${RESET} v${local} → v${latest}`);
  const result = run("npm i -g coherence-cli@latest 2>&1");
  if (result !== null) {
    console.log(`    ${GREEN}✓${RESET} Updated to v${latest}`);
    return 1;
  } else {
    console.log(`    ${RED}✗${RESET} npm install failed`);
    return 0;
  }
}

async function updateMcp() {
  process.stdout.write(`  MCP (coherence-mcp-server)... `);
  const local = localVersion("coherence-mcp-server") || "?";
  const latest = npmVersion("coherence-mcp-server");

  if (!latest) {
    console.log(`${RED}✗${RESET} could not check npm`);
    return 0;
  }

  if (local === latest) {
    console.log(`${GREEN}✓${RESET} v${local} ${DIM}(up to date)${RESET}`);
    return 0;
  }

  if (local === "?") {
    // Not installed — install it
    console.log(`${YELLOW}+${RESET} not installed, installing v${latest}`);
  } else {
    console.log(`${YELLOW}↑${RESET} v${local} → v${latest}`);
  }

  const result = run("npm i -g coherence-mcp-server@latest 2>&1");
  if (result !== null) {
    console.log(`    ${GREEN}✓${RESET} Installed v${latest}`);
    return 1;
  } else {
    console.log(`    ${RED}✗${RESET} npm install failed`);
    return 0;
  }
}

async function updateOpenClawSkill() {
  process.stdout.write(`  OpenClaw skill... `);

  const skillDir = join(homedir(), ".openclaw", "workspace", "skills", "coherence-network");
  if (!existsSync(skillDir)) {
    console.log(`${DIM}not installed (no ~/.openclaw)${RESET}`);
    return 0;
  }

  // Try clawhub install
  const result = run("npx clawhub install coherence-network 2>&1");
  if (result !== null && !result.includes("Error")) {
    console.log(`${GREEN}✓${RESET} updated from ClawHub`);
    return 1;
  }

  // Fallback: fetch SKILL.md from GitHub raw
  try {
    const resp = await fetch("https://raw.githubusercontent.com/seeker71/Coherence-Network/main/skills/coherence-network/SKILL.md");
    if (resp.ok) {
      const content = await resp.text();
      writeFileSync(join(skillDir, "SKILL.md"), content);
      console.log(`${GREEN}✓${RESET} updated from GitHub`);
      return 1;
    }
  } catch {}

  console.log(`${YELLOW}~${RESET} could not update (ClawHub + GitHub both failed)`);
  return 0;
}

async function updateAgentConfigs() {
  let count = 0;

  // Fetch latest skill content for agent configs
  let skillContent;
  try {
    const resp = await fetch("https://raw.githubusercontent.com/seeker71/Coherence-Network/main/skills/coherence-network/SKILL.md");
    if (resp.ok) skillContent = await resp.text();
  } catch {}

  if (!skillContent) {
    // Try local
    const localPath = join(homedir(), ".openclaw", "workspace", "skills", "coherence-network", "SKILL.md");
    if (existsSync(localPath)) {
      skillContent = readFileSync(localPath, "utf-8");
    }
  }

  const agentInstructions = skillContent
    ? `# Coherence Network\n\nThis project uses the Coherence Network. Run \`cc status\` to check health.\nRun \`cc inbox\` to check messages. Run \`cc help\` for all commands.\n\nFull documentation: https://api.coherencycoin.com/docs\nCLI: npm i -g coherence-cli\nMCP: npx coherence-mcp-server\n`
    : null;

  // Claude Code: .claude/settings.json MCP config
  count += updateClaudeCode();

  // Cursor: .cursor/mcp.json + .cursorrules
  count += updateCursor(agentInstructions);

  // Windsurf: .windsurfrules
  count += updateWindsurf(agentInstructions);

  // Codex: AGENTS.md
  count += updateCodex(agentInstructions);

  return count;
}

function updateClaudeCode() {
  process.stdout.write(`  Claude Code (MCP config)... `);

  // Check for project .claude dir or user .claude dir
  const dirs = [
    join(process.cwd(), ".claude"),
    join(homedir(), ".claude"),
  ];

  for (const dir of dirs) {
    if (!existsSync(dir)) continue;

    const settingsPath = join(dir, "settings.json");
    let settings = {};
    if (existsSync(settingsPath)) {
      try { settings = JSON.parse(readFileSync(settingsPath, "utf-8")); } catch {}
    }

    if (!settings.mcpServers) settings.mcpServers = {};

    if (settings.mcpServers["coherence-network"]) {
      console.log(`${GREEN}✓${RESET} already configured ${DIM}(${settingsPath})${RESET}`);
      return 0;
    }

    settings.mcpServers["coherence-network"] = {
      command: "npx",
      args: ["coherence-mcp-server"],
      env: { COHERENCE_API_URL: "https://api.coherencycoin.com" },
    };

    writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log(`${GREEN}✓${RESET} added MCP server to ${DIM}${settingsPath}${RESET}`);
    return 1;
  }

  console.log(`${DIM}no .claude directory found${RESET}`);
  return 0;
}

function updateCursor(instructions) {
  process.stdout.write(`  Cursor... `);

  const cursorDir = join(process.cwd(), ".cursor");
  if (!existsSync(cursorDir)) {
    // Check if cursor is even installed
    if (!run("which cursor")) {
      console.log(`${DIM}not installed${RESET}`);
      return 0;
    }
    mkdirSync(cursorDir, { recursive: true });
  }

  let count = 0;

  // MCP config
  const mcpPath = join(cursorDir, "mcp.json");
  let mcpConfig = {};
  if (existsSync(mcpPath)) {
    try { mcpConfig = JSON.parse(readFileSync(mcpPath, "utf-8")); } catch {}
  }

  if (!mcpConfig.mcpServers) mcpConfig.mcpServers = {};
  if (!mcpConfig.mcpServers["coherence-network"]) {
    mcpConfig.mcpServers["coherence-network"] = {
      command: "npx",
      args: ["coherence-mcp-server"],
    };
    writeFileSync(mcpPath, JSON.stringify(mcpConfig, null, 2));
    console.log(`${GREEN}✓${RESET} MCP added`);
    count++;
  }

  // .cursorrules
  if (instructions) {
    const rulesPath = join(process.cwd(), ".cursorrules");
    if (!existsSync(rulesPath) || !readFileSync(rulesPath, "utf-8").includes("coherence")) {
      const existing = existsSync(rulesPath) ? readFileSync(rulesPath, "utf-8") + "\n\n" : "";
      writeFileSync(rulesPath, existing + instructions);
      if (count === 0) process.stdout.write(`  Cursor... `);
      console.log(`${GREEN}✓${RESET} rules updated`);
      count++;
    } else if (count === 0) {
      console.log(`${GREEN}✓${RESET} ${DIM}already configured${RESET}`);
    }
  } else if (count === 0) {
    console.log(`${GREEN}✓${RESET} ${DIM}already configured${RESET}`);
  }

  return count;
}

function updateWindsurf(instructions) {
  process.stdout.write(`  Windsurf... `);

  if (!run("which windsurf")) {
    console.log(`${DIM}not installed${RESET}`);
    return 0;
  }

  if (!instructions) {
    console.log(`${DIM}no skill content available${RESET}`);
    return 0;
  }

  const rulesPath = join(process.cwd(), ".windsurfrules");
  if (existsSync(rulesPath) && readFileSync(rulesPath, "utf-8").includes("coherence")) {
    console.log(`${GREEN}✓${RESET} ${DIM}already configured${RESET}`);
    return 0;
  }

  const existing = existsSync(rulesPath) ? readFileSync(rulesPath, "utf-8") + "\n\n" : "";
  writeFileSync(rulesPath, existing + instructions);
  console.log(`${GREEN}✓${RESET} rules updated`);
  return 1;
}

function updateCodex(instructions) {
  process.stdout.write(`  Codex... `);

  if (!run("which codex")) {
    console.log(`${DIM}not installed${RESET}`);
    return 0;
  }

  if (!instructions) {
    console.log(`${DIM}no skill content available${RESET}`);
    return 0;
  }

  const agentsPath = join(process.cwd(), "AGENTS.md");
  if (existsSync(agentsPath) && readFileSync(agentsPath, "utf-8").includes("coherence")) {
    console.log(`${GREEN}✓${RESET} ${DIM}already configured${RESET}`);
    return 0;
  }

  const existing = existsSync(agentsPath) ? readFileSync(agentsPath, "utf-8") + "\n\n" : "";
  writeFileSync(agentsPath, existing + instructions);
  console.log(`${GREEN}✓${RESET} AGENTS.md updated`);
  return 1;
}
