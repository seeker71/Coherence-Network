/**
 * Content commands — edit entity views through the attributed API path.
 *
 *   coh content set <entity_type> <entity_id> --lang en --file ./view.md --title "Title"
 */

import { readFileSync } from "node:fs";

import { get, post } from "../api.mjs";
import { getContributorId } from "../config.mjs";

const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const CYAN = "\x1b[36m";

function parseFlags(args) {
  const opts = {};
  const positional = [];
  const flagMap = {
    "--lang": "lang",
    "-l": "lang",
    "--file": "file",
    "-f": "file",
    "--title": "title",
    "--description": "description",
    "--by": "authorId",
    "--type": "authorType",
    "--from-lang": "fromLang",
    "--from-hash": "fromHash",
    "--notes": "notes",
  };

  for (let i = 0; i < args.length; i++) {
    const mapped = flagMap[args[i]];
    if (mapped && args[i + 1]) {
      opts[mapped] = args[++i];
      continue;
    }
    positional.push(args[i]);
  }
  return { opts, positional };
}

function usage() {
  console.log(`${DIM}Usage:${RESET} coh content set <entity_type> <entity_id> --lang <lang> --file <path> [--title <t>] [--description <d>] [--by <contributor_id>]`);
  console.log(`       coh content views <entity_type> <entity_id>`);
}

async function setContent(args) {
  const { opts, positional } = parseFlags(args);
  const [entityType, entityId] = positional;
  if (!entityType || !entityId || !opts.lang || !opts.file) {
    usage();
    return;
  }

  const authorId = opts.authorId || getContributorId();
  if (!authorId) {
    console.log(`${RED}Error:${RESET} set an identity first with ${BOLD}coh identity set <id>${RESET}, or pass --by <contributor_id>.`);
    return;
  }

  let markdown;
  try {
    markdown = readFileSync(opts.file, "utf8");
  } catch (error) {
    console.log(`${RED}Error:${RESET} could not read ${opts.file} - ${error.message}`);
    return;
  }

  const authorType = opts.authorType || (
    opts.fromLang && opts.fromHash ? "translation_human" : "original_human"
  );
  const body = {
    lang: opts.lang,
    content_title: opts.title || "",
    content_description: opts.description || "",
    content_markdown: markdown,
    author_type: authorType,
    author_id: authorId,
    translated_from_lang: opts.fromLang || null,
    translated_from_hash: opts.fromHash || null,
    notes: opts.notes || null,
  };

  const result = await post(
    `/api/entity-views/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    body,
  );
  if (!result) {
    console.log(`${RED}Failed${RESET} to write content view.`);
    return;
  }

  console.log(`${GREEN}✓${RESET} ${BOLD}content view canonical${RESET}`);
  console.log(`  ${DIM}entity:${RESET}      ${entityType}/${entityId}`);
  console.log(`  ${DIM}lang:${RESET}        ${CYAN}${result.lang}${RESET}`);
  console.log(`  ${DIM}view:${RESET}        ${result.id}`);
  console.log(`  ${DIM}hash:${RESET}        ${result.content_hash.slice(0, 16)}...`);
  if (result.source_contribution_id) {
    console.log(`  ${DIM}attribution:${RESET} ${GREEN}${result.source_contribution_id}${RESET}`);
  }
}

async function listViews(args) {
  const [entityType, entityId] = args;
  if (!entityType || !entityId) {
    usage();
    return;
  }
  const result = await get(
    `/api/entity-views/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
  );
  if (!result) {
    console.log(`${RED}Could not fetch views.${RESET}`);
    return;
  }
  console.log(`${BOLD}${result.entity_type}/${result.entity_id}${RESET}`);
  console.log(`  ${DIM}anchor:${RESET} ${result.anchor_lang || "none"}`);
  for (const view of result.views || []) {
    console.log(
      `  ${CYAN}${view.lang}${RESET} ` +
      `${view.is_anchor ? GREEN + "anchor" + RESET : DIM + "view" + RESET} ` +
      `${view.stale ? "stale " : ""}` +
      `${DIM}${String(view.content_hash || "").slice(0, 12)}${RESET}`,
    );
  }
}

export async function handleContent(args) {
  const sub = args[0];
  switch (sub) {
    case "set":
      return setContent(args.slice(1));
    case "views":
    case "list":
      return listViews(args.slice(1));
    default:
      return usage();
  }
}
