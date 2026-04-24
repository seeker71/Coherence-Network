/**
 * Shared --json output helpers for coh commands.
 *
 * Before this module, each command re-invented its own JSON handling:
 *   - ops.mjs did `args.includes("--json")`
 *   - rest.mjs  walked its parser looking for "--json"
 *   - dif.mjs   had a parallel while-loop
 *   - ontology.mjs had yet another parser
 * Commands that never gained --json support (ideas, specs, contributors,
 * tasks, governance, etc.) were invisible to jq pipelines and CI scripts.
 *
 * This module provides one place for:
 *
 *   - hasJsonFlag(args)         — boolean check, consumes the flag
 *   - stripJsonFlag(args)       — returns `args` with `--json` removed
 *   - printJson(data)           — pretty-prints JSON to stdout
 *   - printJsonError(message)   — prints {error: message} and sets exit 1
 *   - emit(data, {json, human}) — shared dispatch helper: in JSON mode
 *                                  prints data; in human mode runs `human(data)`
 *
 * All functions honor the precedence:
 *   explicit flag > stdout non-TTY (piped to jq/less) > default human mode
 *
 * Auto-detecting non-TTY means `coh ideas | jq '.[0]'` just works without
 * the user having to remember `--json`.
 */

const JSON_FLAG = "--json";
const NO_JSON_FLAG = "--no-json";

/**
 * Returns true if the user wants JSON output for this invocation.
 * Precedence:
 *   1. `--no-json`     → force human mode (even on a pipe)
 *   2. `--json`        → force JSON mode
 *   3. stdout is non-TTY → JSON mode (pipeable by default)
 *   4. otherwise       → human mode
 */
export function hasJsonFlag(args) {
  const list = Array.isArray(args) ? args : [];
  if (list.includes(NO_JSON_FLAG)) return false;
  if (list.includes(JSON_FLAG)) return true;
  // Auto-detect: non-interactive stdout means the user is piping somewhere.
  if (!process.stdout.isTTY) return true;
  return false;
}

/**
 * Returns a new array with `--json` and `--no-json` removed. Use this
 * to pass a clean argv down to the existing positional-argument parsers
 * without having to teach each one about the flag.
 */
export function stripJsonFlag(args) {
  const list = Array.isArray(args) ? args : [];
  return list.filter((a) => a !== JSON_FLAG && a !== NO_JSON_FLAG);
}

/** Pretty-print `data` to stdout. Called by commands in JSON mode. */
export function printJson(data) {
  // null/undefined → null (not an empty line) so `jq` can still parse.
  process.stdout.write(JSON.stringify(data ?? null, null, 2) + "\n");
}

/**
 * Emit a JSON error envelope and set process.exitCode = 1.
 * Shape: { error: "..." [, code: "..."] [, status: 500] }
 */
export function printJsonError(message, { code, status } = {}) {
  const envelope = { error: String(message || "unknown_error") };
  if (code) envelope.code = String(code);
  if (status != null) envelope.status = Number(status);
  process.stdout.write(JSON.stringify(envelope, null, 2) + "\n");
  process.exitCode = 1;
}

/**
 * Shared dispatch helper. Commands call:
 *
 *   return emit(data, args, (d) => { ...existing table output... });
 *
 * and get --json / --no-json support for free. In JSON mode prints
 * `data`; in human mode calls `human(data)`. If `data` is null/undefined,
 * emits an error envelope or lets the human callback handle it (usually
 * printing a "Could not fetch" message).
 */
export function emit(data, args, human) {
  if (hasJsonFlag(args)) {
    if (data == null) {
      printJsonError("fetch_failed");
      return;
    }
    printJson(data);
    return;
  }
  if (typeof human === "function") human(data);
}
