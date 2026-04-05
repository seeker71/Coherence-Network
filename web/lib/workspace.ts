/**
 * Workspace scope — tenant identity for the web UI.
 *
 * The active workspace is stored in a cookie (`coh_workspace`) so server
 * components can read it at render time and scope their API fetches.
 * Client-side mirrors into localStorage for SSR-less pages. The default
 * is always "coherence-network" — pages that don't care about workspaces
 * can ignore this module entirely.
 */

export const DEFAULT_WORKSPACE_ID = "coherence-network";
export const WORKSPACE_COOKIE = "coh_workspace";
export const WORKSPACE_STORAGE_KEY = "coh_workspace";

const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;

export function normalizeWorkspaceId(value: string | null | undefined): string {
  if (!value) return DEFAULT_WORKSPACE_ID;
  const trimmed = value.trim().toLowerCase();
  if (!SLUG_RE.test(trimmed)) return DEFAULT_WORKSPACE_ID;
  return trimmed;
}

export function isDefaultWorkspace(id: string | null | undefined): boolean {
  return normalizeWorkspaceId(id) === DEFAULT_WORKSPACE_ID;
}

/** Append workspace_id to a URL only when it differs from the default. */
export function withWorkspaceScope(
  url: string,
  workspaceId: string | null | undefined,
): string {
  const ws = normalizeWorkspaceId(workspaceId);
  if (ws === DEFAULT_WORKSPACE_ID) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}workspace_id=${encodeURIComponent(ws)}`;
}

/** Read the active workspace from the cookie (client-side). */
export function readActiveWorkspaceFromCookie(): string {
  if (typeof document === "undefined") return DEFAULT_WORKSPACE_ID;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${WORKSPACE_COOKIE}=`));
  if (!match) return DEFAULT_WORKSPACE_ID;
  const raw = decodeURIComponent(match.split("=")[1] ?? "");
  return normalizeWorkspaceId(raw);
}
