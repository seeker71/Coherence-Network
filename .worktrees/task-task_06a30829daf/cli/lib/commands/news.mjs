/**
 * News commands: news, news trending, news sources, news resonance
 */

import { get, post } from "../api.mjs";

/** Truncate at word boundary, append "..." if needed */
function truncate(str, len) {
  if (!str) return "";
  if (str.length <= len) return str;
  const trimmed = str.slice(0, len - 3);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > len * 0.4 ? trimmed.slice(0, lastSpace) : trimmed) + "...";
}

/** Format relative time from ISO string */
function timeAgo(isoStr) {
  if (!isoStr) return "";
  const min = Math.floor((Date.now() - new Date(isoStr).getTime()) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  if (min < 1440) return `${Math.floor(min / 60)}h ago`;
  return `${Math.floor(min / 1440)}d ago`;
}

export async function showNewsFeed(args) {
  const limit = (args && parseInt(args[0])) || 10;
  const data = await get("/api/news/feed");
  const allItems = Array.isArray(data) ? data : data?.items || data?.articles;
  if (!allItems || !Array.isArray(allItems)) {
    console.log("Could not fetch news feed.");
    return;
  }
  const items = allItems.slice(0, limit);
  if (items.length === 0) {
    console.log("No news items.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  NEWS FEED\x1b[0m (showing ${items.length} of ${allItems.length})`);
  console.log(`  ${"─".repeat(74)}`);
  for (const item of items) {
    const title = truncate(item.title || item.headline || "?", 50).padEnd(52);
    const source = item.source ? truncate(item.source, 12).padStart(12) : "";
    const ago = timeAgo(item.published_at || item.created_at || item.timestamp);
    console.log(`  ${title} \x1b[2m${source.padStart(12)}\x1b[0m  \x1b[2m${ago}\x1b[0m`);
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
