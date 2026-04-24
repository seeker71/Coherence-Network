/**
 * Translate commands — submit and inspect entity translations.
 *
 * Closes the spec gap in `multilingual-web` R8: any signed-in contributor
 * can submit a human translation; it becomes canonical immediately and
 * the prior canonical is preserved as superseded.
 *
 * Commands:
 *   coh translate submit <entity_type> <entity_id> --lang <lang> --file <path> [--title <t>] [--description <d>] [--from-lang <source>] [--by <author_id>] [--notes <notes>]
 *   coh translate history <entity_type> <entity_id> [--lang <lang>]
 *   coh translate list <entity_type> <entity_id>
 */

import { readFileSync } from "node:fs";

import { get, post } from "../api.mjs";

const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const CYAN = "\x1b[36m";
const MAGENTA = "\x1b[35m";
const RED = "\x1b[31m";

function parseKvFlags(args, flags) {
  const opts = {};
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if (flags[args[i]] && args[i + 1]) {
      opts[flags[args[i]]] = args[i + 1];
      i++;
      continue;
    }
    positional.push(args[i]);
  }
  return { opts, positional };
}

/** coh translate submit <entity_type> <entity_id> --lang de --file path [--title ...] [--description ...] */
async function submitTranslation(args) {
  const { opts, positional } = parseKvFlags(args, {
    "--lang": "lang",
    "-l": "lang",
    "--file": "file",
    "-f": "file",
    "--title": "title",
    "--description": "description",
    "--from-lang": "fromLang",
    "--by": "authorId",
    "--notes": "notes",
    "--type": "authorType",
  });
  const [entity_type, entity_id] = positional;
  if (!entity_type || !entity_id) {
    console.log(`${DIM}Usage:${RESET} coh translate submit <entity_type> <entity_id> --lang <lang> --file <path> [--title <t>] [--description <d>] [--from-lang <source>] [--by <author_id>]`);
    return;
  }
  if (!opts.lang) {
    console.log(`${RED}Error:${RESET} --lang required (de, es, id, en, …)`);
    return;
  }
  if (!opts.file) {
    console.log(`${RED}Error:${RESET} --file required (markdown path)`);
    return;
  }
  let content;
  try {
    content = readFileSync(opts.file, "utf8");
  } catch (e) {
    console.log(`${RED}Error:${RESET} could not read ${opts.file} — ${e.message}`);
    return;
  }
  const body = {
    entity_type,
    entity_id,
    lang: opts.lang,
    content_title: opts.title || "",
    content_description: opts.description || "",
    content_markdown: content,
    author_type: opts.authorType || "translation_human",
    author_id: opts.authorId || null,
    translated_from_lang: opts.fromLang || null,
    notes: opts.notes || null,
  };
  let resp;
  try {
    resp = await post("/translations", body);
  } catch (e) {
    console.log(`${RED}Submit failed:${RESET} ${e.message}`);
    return;
  }
  console.log(`${GREEN}✓${RESET} ${BOLD}translation canonical${RESET}`);
  console.log(`  ${DIM}id:${RESET}         ${resp.id}`);
  console.log(`  ${DIM}entity:${RESET}     ${resp.entity_type}/${resp.entity_id}`);
  console.log(`  ${DIM}lang:${RESET}       ${CYAN}${resp.lang}${RESET}`);
  console.log(`  ${DIM}author:${RESET}     ${resp.author_type}${resp.author_id ? " · " + resp.author_id : ""}`);
  console.log(`  ${DIM}hash:${RESET}       ${resp.content_hash.slice(0, 16)}…`);
  console.log(`  ${DIM}status:${RESET}     ${GREEN}${resp.status}${RESET}`);
}

/** coh translate history <entity_type> <entity_id> [--lang <lang>] */
async function showHistory(args) {
  const { opts, positional } = parseKvFlags(args, {
    "--lang": "lang",
    "-l": "lang",
  });
  const [entity_type, entity_id] = positional;
  if (!entity_type || !entity_id) {
    console.log(`${DIM}Usage:${RESET} coh translate history <entity_type> <entity_id> [--lang <lang>]`);
    return;
  }
  const qs = opts.lang ? `?lang=${encodeURIComponent(opts.lang)}` : "";
  let resp;
  try {
    resp = await get(`/translations/${encodeURIComponent(entity_type)}/${encodeURIComponent(entity_id)}${qs}`);
  } catch (e) {
    console.log(`${RED}Fetch failed:${RESET} ${e.message}`);
    return;
  }
  console.log(`${BOLD}${entity_type}/${entity_id}${RESET} — ${resp.total} view${resp.total === 1 ? "" : "s"}${opts.lang ? ` (lang=${opts.lang})` : ""}`);
  for (const v of resp.items) {
    const statusColor = v.status === "canonical" ? GREEN : DIM;
    const authorColor = v.author_type === "translation_human" ? MAGENTA : YELLOW;
    console.log(
      `  ${statusColor}${v.status.padEnd(10)}${RESET} ` +
      `${CYAN}${v.lang}${RESET} ` +
      `${authorColor}${v.author_type}${RESET}` +
      `${v.author_id ? " · " + v.author_id : ""}` +
      `  ${DIM}${v.content_hash.slice(0, 12)}${RESET}` +
      (v.content_title ? `  ${v.content_title}` : ""),
    );
  }
}

/** coh translate list <entity_type> <entity_id> — alias for history without lang filter */
async function listTranslations(args) {
  return showHistory(args);
}

export async function handleTranslate(args) {
  const sub = args[0];
  switch (sub) {
    case "submit":  return submitTranslation(args.slice(1));
    case "history": return showHistory(args.slice(1));
    case "list":    return listTranslations(args.slice(1));
    default:
      console.log(`${DIM}Usage:${RESET} coh translate <submit|history|list> …`);
      console.log(``);
      console.log(`  ${BOLD}coh translate submit${RESET} <entity_type> <entity_id> --lang <lang> --file <path> [--title <t>]`);
      console.log(`    Submit a translation. Supersedes prior canonical for (entity, lang); history preserved.`);
      console.log(``);
      console.log(`  ${BOLD}coh translate history${RESET} <entity_type> <entity_id> [--lang <lang>]`);
      console.log(`    List all views (canonical + superseded) for an entity, optionally filtered by language.`);
  }
}
