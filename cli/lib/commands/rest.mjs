/**
 * Universal API access — `cc rest` reaches any HTTP route on the configured hub.
 *
 *   cc rest coverage              — canonical route manifest + accessibility proof
 *   cc rest GET /api/health
 *   cc rest POST /api/foo --body '{"a":1}'
 *   cc rest PATCH /api/agent/tasks/x --body '{"status":"running"}'
 *   cc rest GET /api/ideas -H "X-Custom: 1"
 */

import { getApiBase, request, get } from "../api.mjs";

const METHODS = new Set(["GET", "POST", "PATCH", "PUT", "DELETE", "HEAD"]);

function parseRestArgs(argv) {
  const headers = {};
  let body = undefined;
  const positional = [];
  const query = {};

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--body" || a === "-d") {
      body = argv[++i] ?? "";
      continue;
    }
    if (a === "--header" || a === "-H") {
      const raw = argv[++i] || "";
      const idx = raw.indexOf(":");
      if (idx > 0) {
        const k = raw.slice(0, idx).trim();
        const v = raw.slice(idx + 1).trim();
        headers[k] = v;
      }
      continue;
    }
    if (a === "--query" || a === "-q") {
      const raw = argv[++i] || "";
      const eq = raw.indexOf("=");
      if (eq > 0) {
        query[raw.slice(0, eq).trim()] = raw.slice(eq + 1).trim();
      }
      continue;
    }
    if (a === "--json") {
      positional.push(a);
      continue;
    }
    if (a.startsWith("-")) {
      positional.push(a);
      continue;
    }
    positional.push(a);
  }

  let jsonMode = false;
  const pos = positional.filter((p) => {
    if (p === "--json") {
      jsonMode = true;
      return false;
    }
    return true;
  });

  if (body !== undefined && typeof body === "string" && body.length) {
    try {
      body = JSON.parse(body);
    } catch {
      /* keep as string for non-JSON servers */
    }
  }

  return { method: pos[0], path: pos[1], rest: pos.slice(2), headers, body, query, jsonMode };
}

export async function showRestCoverage() {
  const base = getApiBase();
  const data = await get("/api/inventory/routes/canonical");
  if (!data || typeof data !== "object") {
    console.error("Could not fetch /api/inventory/routes/canonical — check COHERENCE_API_URL and API key.");
    process.exitCode = 1;
    return;
  }

  const routes = Array.isArray(data.api_routes) ? data.api_routes : [];
  const count = routes.length;
  const version = data.version ?? "?";
  const milestone = data.milestone ?? "?";
  const generated = data.generated_at ?? "?";

  const proof = {
    hub: base,
    canonical_api_route_count: count,
    registry_version: String(version),
    milestone: String(milestone),
    generated_at: String(generated),
    proof:
      "Every path in api_routes can be invoked via: cc rest <METHOD> <path> [--body JSON] [-H 'Name: value']. "
      + "First-class `cc` subcommands remain recommended for common workflows.",
  };

  console.log(JSON.stringify(proof, null, 2));
  console.log();
  console.log(
    `\x1b[2m${count} canonical API routes · registry v${version} · ` +
      "full terminal access = `cc rest` + manifest above\x1b[0m",
  );
}

export async function handleRest(argv) {
  const sub = argv[0];
  if (sub === "coverage" || sub === "manifest") {
    const jsonOnly = argv.includes("--json");
    if (jsonOnly) {
      const data = await get("/api/inventory/routes/canonical");
      console.log(JSON.stringify(data ?? { error: "fetch_failed" }, null, 2));
      if (!data) process.exitCode = 1;
      return;
    }
    return showRestCoverage();
  }

  const { method, path, headers, body, query, jsonMode } = parseRestArgs(argv);
  if (!method || !path) {
    console.log(`
\x1b[1mcc rest\x1b[0m — call any API path on the configured hub

\x1b[1mUsage:\x1b[0m
  cc rest coverage              Show canonical route count + accessibility proof
  cc rest GET /api/health
  cc rest POST /api/path --body '{"key":"value"}'
  cc rest PATCH /api/resource/x --body '{"a":1}' -H "X-Custom: yes"
  cc rest GET /api/ideas -q limit=5

\x1b[1mEnv vars:\x1b[0m COHERENCE_API_URL, COHERENCE_API_KEY, COHERENCE_TIMEOUT_MS
\x1b[1mFlags:\x1b[0m --api-url <url>, --api-key <key>, --timeout <ms>, --workspace <id>
\x1b[1mConfig:\x1b[0m ~/.coherence-network/config.json, ~/.coherence-network/keys.json
`);
    return;
  }

  const m = method.toUpperCase();
  if (!METHODS.has(m)) {
    console.error(`Unsupported HTTP method: ${method} (use GET POST PATCH PUT DELETE HEAD)`);
    process.exitCode = 1;
    return;
  }

  let reqPath = path;
  if (!reqPath.startsWith("/")) {
    reqPath = `/${reqPath}`;
  }

  const res = await request(m, reqPath, {
    params: Object.keys(query).length ? query : undefined,
    body: m === "GET" || m === "HEAD" ? undefined : body,
    headers,
  });

  if (jsonMode && res.json != null) {
    console.log(JSON.stringify(res.json, null, 2));
  } else if (res.json != null) {
    console.log(JSON.stringify(res.json, null, 2));
  } else {
    console.log(res.text || "");
  }

  if (!res.ok) {
    console.error(`\x1b[33mHTTP ${res.status}\x1b[0m ${reqPath}`);
    process.exitCode = 1;
  }
}
