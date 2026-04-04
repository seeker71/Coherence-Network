"use client";

/**
 * WorkspacePicker — tenant switcher for the site header.
 *
 * Reads the list of workspaces from `/api/workspaces`, shows the active
 * one (stored in the `coh_workspace` cookie) and lets users switch. On
 * change it writes the cookie, mirrors to localStorage for SSR-less
 * callers, and hard-reloads the page so server components re-render
 * with the new scope.
 */

import { useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";
import {
  DEFAULT_WORKSPACE_ID,
  WORKSPACE_COOKIE,
  WORKSPACE_STORAGE_KEY,
  normalizeWorkspaceId,
} from "@/lib/workspace";

type Workspace = {
  id: string;
  name: string;
  description?: string;
};

function setWorkspaceCookie(id: string) {
  // 1-year cookie, lax, scoped to path=/
  const maxAge = 60 * 60 * 24 * 365;
  document.cookie = `${WORKSPACE_COOKIE}=${encodeURIComponent(id)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
}

function readWorkspaceCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${WORKSPACE_COOKIE}=`));
  if (!match) return null;
  const raw = decodeURIComponent(match.split("=")[1] ?? "");
  return raw || null;
}

export function WorkspacePicker() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [active, setActive] = useState<string>(DEFAULT_WORKSPACE_ID);
  const [loading, setLoading] = useState(true);

  // Hydrate active workspace from cookie (falls back to localStorage)
  useEffect(() => {
    const fromCookie = readWorkspaceCookie();
    const fromStorage =
      typeof window !== "undefined"
        ? window.localStorage.getItem(WORKSPACE_STORAGE_KEY)
        : null;
    const current = normalizeWorkspaceId(fromCookie || fromStorage);
    setActive(current);
  }, []);

  // Fetch available workspaces
  useEffect(() => {
    const apiBase = getApiBase();
    const url = `${apiBase}/api/workspaces`;
    fetch(url, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: unknown) => {
        if (Array.isArray(data)) {
          setWorkspaces(
            data
              .filter((ws): ws is Workspace => Boolean(ws) && typeof ws === "object" && "id" in ws && "name" in ws)
              .map((ws) => ({ id: String(ws.id), name: String(ws.name), description: ws.description }))
          );
        }
      })
      .catch(() => {
        // Swallow — picker will just show the default.
      })
      .finally(() => setLoading(false));
  }, []);

  function onSelect(id: string) {
    const normalized = normalizeWorkspaceId(id);
    setActive(normalized);
    setWorkspaceCookie(normalized);
    try {
      window.localStorage.setItem(WORKSPACE_STORAGE_KEY, normalized);
    } catch {
      // ignore storage errors
    }
    // Reload so server components pick up the new scope.
    window.location.reload();
  }

  // Hide the picker when only the default workspace exists and we haven't
  // finished loading, to avoid flicker. Still render the default label so
  // users know the concept exists.
  const hasChoices = workspaces.length > 1;
  const activeName =
    workspaces.find((w) => w.id === active)?.name ||
    (active === DEFAULT_WORKSPACE_ID ? "Coherence Network" : active);

  if (!hasChoices && !loading) {
    return (
      <span
        className="hidden md:inline-flex items-center rounded-lg border border-border/30 px-2.5 py-1 text-xs text-muted-foreground"
        title={`Active workspace: ${activeName}`}
      >
        {activeName}
      </span>
    );
  }

  return (
    <label className="hidden md:inline-flex items-center" title="Active workspace">
      <span className="sr-only">Active workspace</span>
      <select
        value={active}
        onChange={(e) => onSelect(e.target.value)}
        disabled={loading}
        className="rounded-lg border border-border/50 bg-background/80 px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 focus:ring-offset-background disabled:opacity-50"
        aria-label="Active workspace"
      >
        {workspaces.length === 0 ? (
          <option value={active}>{activeName}</option>
        ) : (
          workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name}
            </option>
          ))
        )}
      </select>
    </label>
  );
}
