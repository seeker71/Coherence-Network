/**
 * Render session — tracks lifecycle of one asset render.
 *
 * Covers spec R10 (5s onReady timeout) and the engagement → CC pool
 * pipeline. Pure logic, no React — the AssetRenderer component
 * instantiates a session and wires its callbacks to React lifecycle.
 *
 * Usage:
 *   const session = createRenderSession({
 *     assetId: "asset:abc",
 *     rendererId: "builtin-markdown-v1",
 *     readerId: "contributor:charlie",
 *     onTimeout: () => setShowFallback(true),
 *   });
 *   // inside renderer: session.markReady()
 *   // every N seconds while visible: session.trackEngagement(seconds)
 *   // on unmount: POST session.getEventPayload()
 */

export interface RenderSessionOptions {
  assetId: string;
  rendererId: string;
  readerId: string;
  /** Milliseconds to wait for markReady() before firing onTimeout. Default 5000 per spec R10. */
  timeoutMs?: number;
  /** Fires if markReady() is not called within timeoutMs. */
  onTimeout?: () => void;
  /** Injectable clock for tests. Defaults to Date.now. */
  now?: () => number;
  /** Injectable setTimeout for tests. Defaults to globalThis.setTimeout. */
  setTimeoutFn?: typeof setTimeout;
  /** Injectable clearTimeout for tests. Defaults to globalThis.clearTimeout. */
  clearTimeoutFn?: typeof clearTimeout;
}

export interface RenderEventPayload {
  asset_id: string;
  renderer_id: string;
  reader_id: string;
  duration_ms: number;
}

export interface RenderSession {
  markReady(): void;
  trackEngagement(seconds: number): void;
  getEventPayload(): RenderEventPayload;
  isReady(): boolean;
  hasTimedOut(): boolean;
  dispose(): void;
}

const DEFAULT_TIMEOUT_MS = 5000;

export function createRenderSession(options: RenderSessionOptions): RenderSession {
  const now = options.now ?? Date.now;
  const setTimeoutFn = options.setTimeoutFn ?? setTimeout;
  const clearTimeoutFn = options.clearTimeoutFn ?? clearTimeout;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  const startedAt = now();
  let ready = false;
  let timedOut = false;
  let engagementSeconds = 0;
  let disposed = false;

  const timer = setTimeoutFn(() => {
    if (!ready && !disposed) {
      timedOut = true;
      options.onTimeout?.();
    }
  }, timeoutMs);

  return {
    markReady() {
      if (disposed) return;
      ready = true;
      clearTimeoutFn(timer);
    },
    trackEngagement(seconds: number) {
      if (disposed) return;
      engagementSeconds = Math.max(engagementSeconds, seconds);
    },
    getEventPayload(): RenderEventPayload {
      // Prefer engagement-reported seconds when available; fall back to wall time.
      const wallMs = now() - startedAt;
      const engagementMs = engagementSeconds * 1000;
      const durationMs = engagementMs > 0 ? engagementMs : wallMs;
      return {
        asset_id: options.assetId,
        renderer_id: options.rendererId,
        reader_id: options.readerId,
        duration_ms: Math.max(0, Math.floor(durationMs)),
      };
    },
    isReady() {
      return ready;
    },
    hasTimedOut() {
      return timedOut;
    },
    dispose() {
      disposed = true;
      clearTimeoutFn(timer);
    },
  };
}

/**
 * POST a render event payload to /api/render-events.
 *
 * The caller (AssetRenderer component on unmount) invokes this with
 * the payload returned by session.getEventPayload(). Returns the
 * attributed RenderEvent on success, or null on transport failure —
 * a failed log is not a user-facing error; the content was still seen.
 */
export async function postRenderEvent(
  payload: RenderEventPayload,
  apiBase: string = "",
): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(`${apiBase}/api/render-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}
