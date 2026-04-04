/**
 * Workspace scope — server-only helpers.
 *
 * Next.js server components read the active workspace from the
 * `coh_workspace` cookie so they can scope their API fetches to a
 * specific tenant before rendering.
 */

import { cookies } from "next/headers";
import {
  DEFAULT_WORKSPACE_ID,
  WORKSPACE_COOKIE,
  normalizeWorkspaceId,
} from "./workspace";

/** Read the active workspace from the request cookies. */
export async function getActiveWorkspaceFromCookie(): Promise<string> {
  const store = await cookies();
  const raw = store.get(WORKSPACE_COOKIE)?.value ?? null;
  return normalizeWorkspaceId(raw);
}

export { DEFAULT_WORKSPACE_ID };
