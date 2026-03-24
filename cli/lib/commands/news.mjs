/**
 * News commands: news, news trending, news sources, news resonance
 */

import { get, post } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
}

export async function showNewsFeed() {
  const data = await get("/api/news/feed");
  const items = Array.isArray(data) ? data : data?.items || data?.articles;
  if (!items || !Array.isArray(items)) {
    console.log("Could not fetch news feed.");
    return;
  }
  if (items.length === 0) {
    console.log("No news items.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  NEWS FEED\x1b[0m (${items.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const item of items) {
    const title = truncate(item.title || item.headline || "?", 55);
    const source = item.source ? `\x1b[2m${truncate(item.source, 15)}\x1b[0m` : "";
    console.log(`  ${title}  ${source}`);
  }
  console.log();
}

export async function showTrending() {
  const data = await get("/api/news/trending");
  const items = Array.isArray(data) ? data : data?.trending || data?.items;
  if (!items || !Array.isArray(items)) {
    console.log("Could not fetch trending news.");
    return;
  }
  if (items.length === 0) {
    console.log("Nothing trending right now.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  TRENDING\x1b[0m (${items.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const item of items) {
    const title = truncate(item.title || item.headline || "?", 55);
    console.log(`  \x1b[33m~\x1b[0m ${title}`);
  }
  console.log();
}

export async function showSources() {
  const data = await get("/api/news/sources");
  const sources = Array.isArray(data) ? data : data?.sources;
  if (!sources || !Array.isArray(sources)) {
    console.log("Could not fetch news sources.");
    return;
  }
  if (sources.length === 0) {
    console.log("No news sources configured.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  NEWS SOURCES\x1b[0m (${sources.length})`);
  console.log(`  ${"─".repeat(60)}`);
  for (const s of sources) {
    const name = truncate(s.name || s.url || "?", 30);
    const url = s.url ? `\x1b[2m${truncate(s.url, 40)}\x1b[0m` : "";
    console.log(`  ${name.padEnd(32)} ${url}`);
  }
  console.log();
}

export async function addSource(args) {
  const url = args[0];
  const name = args.slice(1).join(" ");
  if (!url || !name) {
    console.log("Usage: cc news source add <url> <name>");
    return;
  }
  const result = await post("/api/news/sources", { url, name });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Source added: ${result.name || name}`);
  } else {
    console.log("Failed to add source.");
  }
}

export async function showNewsResonance(args) {
  const contributor = args[0];
  const path = contributor
    ? `/api/news/resonance/${encodeURIComponent(contributor)}`
    : "/api/news/resonance";
  const data = await get(path);
  if (!data) {
    console.log("Could not fetch news resonance.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  NEWS RESONANCE\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (Array.isArray(data)) {
    for (const item of data.slice(0, 15)) {
      const name = item.title || item.topic || item.id || "?";
      const score = item.score != null ? `\x1b[32m${item.score.toFixed(2)}\x1b[0m` : "";
      console.log(`  ${truncate(name, 45).padEnd(47)} ${score}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}
