/**
 * Renderer SDK — the public interface for building compatible asset renderers.
 *
 * Community developers implement the RendererProps interface and register
 * their component via registerRenderer(). The platform handles MIME type
 * lookup, dynamic loading, sandboxing, CC attribution, and storage
 * resolution — the renderer only has to display content and emit
 * lifecycle signals.
 *
 * See specs/asset-renderer-plugin.md (R7).
 */

import type { ComponentType } from "react";

/**
 * Props every renderer receives from the platform.
 *
 * - contentUrl: Arweave/IPFS URL to the raw content the renderer should display.
 * - metadata: format-specific metadata supplied at registration
 *   (e.g. vertex count for a GLTF, page count for a PDF).
 * - onReady: MUST be called within 5 seconds of mount. If the timeout
 *   elapses, the platform shows a download fallback (spec R10).
 * - onEngagement: periodic signal carrying seconds of active engagement.
 *   The platform uses this to scale the CC pool for attribution.
 */
export interface RendererProps {
  contentUrl: string;
  metadata: Record<string, unknown>;
  onReady: () => void;
  onEngagement: (seconds: number) => void;
}

/**
 * Config an SDK user provides when registering a renderer.
 *
 * - id: unique string like "gltf-viewer-v1".
 * - mimeTypes: what MIME types this renderer handles.
 * - component: the React component receiving RendererProps.
 */
export interface RendererConfig {
  id: string;
  mimeTypes: string[];
  component: ComponentType<RendererProps>;
}

/**
 * In-process registry of locally-registered renderers, keyed by MIME type.
 * Populated by registerRenderer() and consumed by findRendererForMime().
 *
 * This is the *client-side* cache for renderers that are either built into
 * the platform (markdown, image, pdf, html) or loaded at runtime from a
 * remote component_url. It does NOT replace the server-side registry at
 * POST /api/renderers/register — that's authoritative for attribution.
 */
const _registry: Map<string, RendererConfig> = new Map();

/**
 * Register a renderer. The platform calls this during built-in renderer
 * bootstrap and when loading a remote component_url. SDK users building
 * renderers in their own packages call this on module load.
 */
export function registerRenderer(config: RendererConfig): void {
  if (!config.id) {
    throw new Error("registerRenderer: id is required");
  }
  if (!config.mimeTypes || config.mimeTypes.length === 0) {
    throw new Error("registerRenderer: at least one mime type is required");
  }
  for (const mime of config.mimeTypes) {
    _registry.set(mime, config);
  }
}

/**
 * Find a locally-registered renderer for a MIME type. Returns undefined
 * if none is registered — the caller should fall back to remote lookup
 * via GET /api/renderers/for/{mime_type} or show a download surface.
 */
export function findRendererForMime(mimeType: string): RendererConfig | undefined {
  return _registry.get(mimeType);
}

/**
 * List all locally-registered renderers. Mostly for debugging and
 * introspection; the platform's authoritative list is server-side.
 */
export function listRegisteredRenderers(): RendererConfig[] {
  return Array.from(new Set(_registry.values()));
}

/**
 * Testing hook. Not part of the public API.
 */
export function _resetRegistryForTests(): void {
  _registry.clear();
}
