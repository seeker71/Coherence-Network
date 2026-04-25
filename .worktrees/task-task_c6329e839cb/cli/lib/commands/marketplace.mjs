/**
 * Marketplace commands: marketplace publish, marketplace browse, marketplace fork
 */

import { get, post } from "../api.mjs";

/** Publish an idea to the cross-instance marketplace */
export async function marketplacePublish(args) {
  const ideaId = args[0];
  if (!ideaId) {
    console.log("Usage: coh marketplace publish <idea-id> [--tags tag1,tag2] [--author \"Name\"]");
    return;
  }
  const body = { idea_id: ideaId };
  // Parse optional flags
  for (let i = 1; i < args.length; i++) {
    if (args[i] === "--tags" && args[i + 1]) body.tags = args[++i].split(",").map(t => t.trim());
    else if (args[i] === "--author" && args[i + 1]) body.author_display_name = args[++i];
    else if (args[i] === "--visibility" && args[i + 1]) body.visibility = args[++i];
  }

  const result = await post("/api/marketplace/publish", body);
  if (!result) return;

  console.log(`\x1b[1m  MARKETPLACE PUBLISH\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  ID:          ${result.id}`);
  console.log(`  Idea:        ${result.idea_title}`);
  console.log(`  Author:      ${result.author_display_name}`);
  console.log(`  Confidence:  ${(result.confidence * 100).toFixed(1)}%`);
  console.log(`  Visibility:  ${result.visibility}`);
  console.log();
}

/** Browse marketplace listings */
export async function marketplaceBrowse(args) {
  const params = { page: 1, page_size: 20, sort: "recent" };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--page" && args[i + 1]) params.page = parseInt(args[++i]) || 1;
    else if (args[i] === "--page-size" && args[i + 1]) params.page_size = parseInt(args[++i]) || 20;
    else if (args[i] === "--sort" && args[i + 1]) params.sort = args[++i];
    else if (args[i] === "--search" && args[i + 1]) params.search = args[++i];
    else if (args[i] === "--tags" && args[i + 1]) params.tags = args[++i];
    else if (args[i] === "--min-confidence" && args[i + 1]) params.min_confidence = parseFloat(args[++i]);
  }

  const data = await get("/api/marketplace/browse", params);
  if (!data) return;

  if (!data.listings || data.listings.length === 0) {
    console.log("No marketplace listings found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  MARKETPLACE\x1b[0m (${data.listings.length} of ${data.total})`);
  console.log(`  ${"─".repeat(68)}`);
  for (const l of data.listings) {
    const title = (l.idea_title || "").slice(0, 40).padEnd(42);
    const author = (l.author_display_name || "").slice(0, 16).padEnd(18);
    const conf = `${(l.confidence * 100).toFixed(0)}%`.padStart(4);
    const forks = `${l.fork_count} forks`.padStart(10);
    console.log(`  ${title} ${author} ${conf} ${forks}`);
  }
  console.log();
}

/** Fork a marketplace listing */
export async function marketplaceFork(args) {
  const listingId = args[0];
  if (!listingId) {
    console.log("Usage: coh marketplace fork <listing-id> <forker-id> [--notes \"why\"]");
    return;
  }
  const forkerId = args[1];
  if (!forkerId) {
    console.log("Usage: coh marketplace fork <listing-id> <forker-id> [--notes \"why\"]");
    return;
  }
  const body = { forker_id: forkerId, notes: "" };
  for (let i = 2; i < args.length; i++) {
    if (args[i] === "--notes" && args[i + 1]) body.notes = args[++i];
  }

  const result = await post(`/api/marketplace/fork/${listingId}`, body);
  if (!result) return;

  console.log(`\x1b[1m  FORKED\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Local ID:          ${result.local_idea_id}`);
  console.log(`  Original Listing:  ${result.marketplace_listing_id}`);
  console.log(`  Value Lineage:     ${result.value_lineage_link_id}`);
  console.log();
}
