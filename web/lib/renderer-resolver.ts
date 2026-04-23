/**
 * Renderer resolver — given a MIME type, find the renderer to use.
 *
 * Resolution order (spec R3):
 *   1. Local client-side registry (built-in renderers + any loaded
 *      bundles already registered via registerRenderer()).
 *   2. Remote server registry at GET /api/renderers/for/{mime_type}
 *      — returns a descriptor with component_url; the caller
 *      dynamically imports the bundle.
 *   3. Null — the caller should show a download fallback.
 *
 * This module is pure resolution logic. The actual dynamic-import
 * loading of remote component_urls, the 5s onReady timeout (R10), and
 * the sandbox container (R8) live in the AssetRenderer wrapper
 * component, which consumes the descriptor returned from here.
 */

import { findRendererForMime, type RendererConfig } from "./renderer-sdk";

export type LocalRendererDescriptor = {
  source: "local";
  config: RendererConfig;
};

export type RemoteRendererDescriptor = {
  source: "remote";
  id: string;
  name: string;
  componentUrl: string;
  version: string;
};

export type RendererDescriptor = LocalRendererDescriptor | RemoteRendererDescriptor;

type RemoteRendererFetcher = (mimeType: string) => Promise<RemoteRendererDescriptor | null>;

/**
 * Default remote fetcher. Hits GET /api/renderers/for/{mime_type}
 * and returns a RemoteRendererDescriptor, or null on 404.
 */
async function defaultFetchRemoteRenderer(
  mimeType: string,
): Promise<RemoteRendererDescriptor | null> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";
  const url = `${apiBase}/api/renderers/for/${encodeURIComponent(mimeType)}`;
  try {
    const response = await fetch(url);
    if (response.status === 404) return null;
    if (!response.ok) return null;
    const data = await response.json();
    return {
      source: "remote",
      id: data.id,
      name: data.name,
      componentUrl: data.component_url,
      version: data.version,
    };
  } catch {
    return null;
  }
}

/**
 * Resolve a renderer for a given MIME type. Checks the local registry
 * first; falls back to the server registry. Returns null if neither
 * has a match (the caller should show a download surface per spec R3).
 *
 * The `fetcher` parameter is injectable for tests.
 */
export async function resolveRendererForMime(
  mimeType: string,
  fetcher: RemoteRendererFetcher = defaultFetchRemoteRenderer,
): Promise<RendererDescriptor | null> {
  const local = findRendererForMime(mimeType);
  if (local) {
    return { source: "local", config: local };
  }
  const remote = await fetcher(mimeType);
  return remote;
}
