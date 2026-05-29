// generate-vision-bodymap.mjs — read the vision-kb concept frontmatter into a
// compact body-map the web bundles, so Kernel Space can render the substrate
// as a walkable constellation offline (no API round-trip). The concept files
// are the body's attestation; this is their structural shadow.
//
// Run:  node web/scripts/generate-vision-bodymap.mjs
// Out:  web/lib/form-kernel/vision-bodymap.json
//
// Regenerate when concepts are added / their geometry or cross-refs change.

import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const conceptsDir = join(here, "../../docs/vision-kb/concepts");
const outPath = join(here, "../lib/form-kernel/vision-bodymap.json");

function parse(md) {
  const m = md.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) return null;
  const [, fm, body] = m;
  const get = (k) => {
    const r = fm.match(new RegExp(`^\\s*${k}:\\s*(.+)$`, "m"));
    return r ? r[1].trim().replace(/^["']|["']$/g, "") : undefined;
  };
  const id = get("id");
  if (!id) return null;

  // title — first markdown heading in the body
  const title = (body.match(/^#\s+(.+)$/m)?.[1] ?? id).trim();

  // cross-refs — frontmatter list, else the `→ a, b, c` line(s) in body
  const refs = new Set();
  const fmList = fm.match(/cross_refs:\s*\n((?:\s*-\s*.+\n?)+)/);
  if (fmList) {
    for (const line of fmList[1].split("\n")) {
      const r = line.match(/-\s*([a-z0-9-]+)/i);
      if (r) refs.add(r[1]);
    }
  }
  for (const line of body.split("\n")) {
    if (line.startsWith("→")) {
      for (const tok of line.slice(1).split(",")) {
        const t = tok.trim();
        if (/^lc-[a-z0-9-]+$/.test(t)) refs.add(t);
      }
    }
  }

  return {
    id,
    title,
    hz: Number(get("hz")) || 0,
    status: get("status") ?? "seed",
    arity: get("arity") ?? "",
    form: get("form") ?? "",
    topology: get("topology") ?? "",
    polarity: get("polarity") ?? "",
    band: get("spectral_band") ?? "",
    crossRefs: [...refs].filter((r) => r !== id),
  };
}

const files = readdirSync(conceptsDir).filter((f) => f.endsWith(".md") && f.startsWith("lc-"));
const cells = [];
for (const f of files) {
  const cell = parse(readFileSync(join(conceptsDir, f), "utf8"));
  if (cell) cells.push(cell);
}
cells.sort((a, b) => a.id.localeCompare(b.id));

// prune cross-refs to concepts that exist in the map (keep the graph closed)
const ids = new Set(cells.map((c) => c.id));
for (const c of cells) c.crossRefs = c.crossRefs.filter((r) => ids.has(r));

const out = {
  _generated: "node web/scripts/generate-vision-bodymap.mjs",
  count: cells.length,
  cells,
};
writeFileSync(outPath, JSON.stringify(out, null, 0));
console.log(`vision-bodymap: ${cells.length} concepts → ${outPath}`);
