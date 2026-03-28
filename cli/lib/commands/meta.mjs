/**
 * meta — system self-discovery commands
 *
 * cc meta endpoints   — list all API endpoints as concept nodes
 * cc meta modules     — list all code modules with spec/idea links
 * cc meta             — summary overview
 */

import { get } from "../api.mjs";

const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m";
const G = "\x1b[32m", Y = "\x1b[33m", C = "\x1b[36m", M = "\x1b[35m";

function methodColor(method) {
  switch (method) {
    case "GET":    return "\x1b[32m";
    case "POST":   return "\x1b[33m";
    case "PUT":    return "\x1b[34m";
    case "PATCH":  return "\x1b[35m";
    case "DELETE": return "\x1b[31m";
    default:       return "\x1b[2m";
  }
}

export async function showMetaSummary() {
  const data = await get("/api/meta/summary");
  if (!data) {
    console.log("Could not fetch meta summary.");
    return;
  }
  const pct = (data.spec_coverage * 100).toFixed(1);
  const coverageColor = data.spec_coverage >= 0.5 ? G : data.spec_coverage >= 0.25 ? Y : "\x1b[31m";

  console.log();
  console.log(`${B}  SYSTEM SELF-MAP${R}`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  Endpoints:    ${B}${data.endpoint_count}${R}`);
  console.log(`  Modules:      ${B}${data.module_count}${R}`);
  console.log(`  Traced:       ${B}${data.traced_count}${R} endpoints linked to spec/idea`);
  console.log(`  Coverage:     ${coverageColor}${pct}%${R} of endpoints have traceability`);
  console.log();
  console.log(`  ${D}Use 'cc meta endpoints' or 'cc meta modules' for details${R}`);
  console.log();
}

export async function showMetaEndpoints(args) {
  const data = await get("/api/meta/endpoints");
  if (!data || !Array.isArray(data.endpoints)) {
    console.log("Could not fetch endpoints.");
    return;
  }

  const filter = (args[0] || "").toLowerCase();
  const endpoints = filter
    ? data.endpoints.filter(e =>
        e.path.toLowerCase().includes(filter) ||
        e.tags.some(t => t.toLowerCase().includes(filter)) ||
        (e.spec_id || "").includes(filter) ||
        (e.idea_id || "").toLowerCase().includes(filter)
      )
    : data.endpoints;

  console.log();
  console.log(`${B}  ENDPOINTS${R} (${endpoints.length}${filter ? " filtered" : ""} / ${data.total} total)`);
  console.log(`  ${"─".repeat(80)}`);

  for (const ep of endpoints) {
    const mc = methodColor(ep.method);
    const method = `${mc}${ep.method.padEnd(6)}${R}`;
    const path = ep.path.padEnd(45);
    const spec = ep.spec_id ? `${C}spec-${ep.spec_id}${R}` : "";
    const idea = ep.idea_id ? `${M}${ep.idea_id}${R}` : "";
    const tags = ep.tags.length ? `${D}[${ep.tags.join(",")}]${R}` : "";
    const links = [spec, idea].filter(Boolean).join(" ");
    console.log(`  ${method} ${path} ${links} ${tags}`);
    if (ep.summary) {
      console.log(`         ${D}${ep.summary.slice(0, 72)}${R}`);
    }
  }
  console.log();
}

export async function showMetaModules(args) {
  const data = await get("/api/meta/modules");
  if (!data || !Array.isArray(data.modules)) {
    console.log("Could not fetch modules.");
    return;
  }

  const filter = (args[0] || "").toLowerCase();
  const modules = filter
    ? data.modules.filter(m =>
        m.name.toLowerCase().includes(filter) ||
        m.module_type.includes(filter) ||
        m.spec_ids.some(s => s.includes(filter)) ||
        m.idea_ids.some(i => i.toLowerCase().includes(filter))
      )
    : data.modules;

  console.log();
  console.log(`${B}  MODULES${R} (${modules.length}${filter ? " filtered" : ""} / ${data.total} total)`);
  console.log(`  ${"─".repeat(80)}`);

  const typeColor = (t) => {
    switch (t) {
      case "router":     return G;
      case "service":    return C;
      case "model":      return Y;
      case "middleware": return M;
      default:           return D;
    }
  };

  for (const mod of modules) {
    const tc = typeColor(mod.module_type);
    const type = `${tc}${mod.module_type.padEnd(10)}${R}`;
    const name = mod.name.padEnd(30);
    const eps = mod.endpoint_count > 0 ? `${mod.endpoint_count} ep` : "   ";
    const spec = mod.spec_ids.length ? `${C}spec:${mod.spec_ids.join(",")}${R}` : "";
    const idea = mod.idea_ids.length ? `${M}idea:${mod.idea_ids[0]}${mod.idea_ids.length > 1 ? `+${mod.idea_ids.length - 1}` : ""}${R}` : "";
    const links = [spec, idea].filter(Boolean).join(" ");
    console.log(`  ${type} ${name} ${D}${eps}${R}  ${links}`);
  }
  console.log();
}
