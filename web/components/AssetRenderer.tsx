"use client";

/**
 * AssetRenderer — the binding between the resolver, the render session,
 * and React lifecycle. Given an asset descriptor, it:
 *
 *   1. Resolves the right renderer for the MIME type (local → remote → null)
 *   2. Creates a render session with a 5s onReady timeout (spec R10)
 *   3. Renders the local renderer component directly, OR shows a notice
 *      for remote bundles (dynamic-import bootstrap is a follow-up), OR
 *      shows a download fallback
 *   4. Tracks engagement and POSTs /api/render-events on unmount
 *
 * See specs/asset-renderer-plugin.md (R3, R4 client, R8, R10).
 */

import { useEffect, useMemo, useRef, useState } from "react";

import {
  resolveRendererForMime,
  type RendererDescriptor,
} from "../lib/renderer-resolver";
import { createRenderSession, postRenderEvent, type RenderSession } from "../lib/render-session";

export interface AssetRendererProps {
  assetId: string;
  mimeType: string;
  contentUrl: string;
  readerId: string;
  metadata?: Record<string, unknown>;
  /** API base URL for posting render events. Empty string → same origin. */
  apiBase?: string;
}

export function AssetRenderer({
  assetId,
  mimeType,
  contentUrl,
  readerId,
  metadata = {},
  apiBase = "",
}: AssetRendererProps) {
  const [descriptor, setDescriptor] = useState<RendererDescriptor | null | "pending">("pending");
  const [timedOut, setTimedOut] = useState(false);
  const sessionRef = useRef<RenderSession | null>(null);

  useEffect(() => {
    let cancelled = false;
    resolveRendererForMime(mimeType).then((result) => {
      if (!cancelled) setDescriptor(result);
    });
    return () => {
      cancelled = true;
    };
  }, [mimeType]);

  // Derive renderer id for session tracking. For remote descriptors we have
  // an id from the server registry; for local, from the config; for null,
  // we still track the render as an attempt with a placeholder id.
  const rendererId = useMemo(() => {
    if (descriptor === "pending" || descriptor === null) return "none";
    if (descriptor.source === "local") return descriptor.config.id;
    return descriptor.id;
  }, [descriptor]);

  useEffect(() => {
    if (descriptor === "pending") return;
    const session = createRenderSession({
      assetId,
      rendererId,
      readerId,
      onTimeout: () => setTimedOut(true),
    });
    sessionRef.current = session;
    return () => {
      if (sessionRef.current) {
        const payload = sessionRef.current.getEventPayload();
        sessionRef.current.dispose();
        sessionRef.current = null;
        if (descriptor !== null) {
          // Fire-and-forget; we don't surface POST failures in the UI.
          void postRenderEvent(payload, apiBase);
        }
      }
    };
  }, [assetId, rendererId, readerId, descriptor, apiBase]);

  if (descriptor === "pending") {
    return <div className="asset-renderer asset-renderer--loading">Resolving renderer…</div>;
  }

  if (descriptor === null) {
    return (
      <div className="asset-renderer asset-renderer--fallback">
        <p>No renderer available for <code>{mimeType}</code>.</p>
        <p>
          <a href={contentUrl} download>
            Download content
          </a>
        </p>
      </div>
    );
  }

  if (timedOut) {
    return (
      <div className="asset-renderer asset-renderer--timeout">
        <p>This content is taking longer than 5 seconds to render.</p>
        <p>
          <a href={contentUrl} download>
            Download content
          </a>
        </p>
      </div>
    );
  }

  if (descriptor.source === "local") {
    const RendererComponent = descriptor.config.component;
    return (
      <RendererComponent
        contentUrl={contentUrl}
        metadata={metadata}
        onReady={() => sessionRef.current?.markReady()}
        onEngagement={(seconds) => sessionRef.current?.trackEngagement(seconds)}
      />
    );
  }

  // Remote descriptor — the spec calls for dynamic import of the component_url.
  // That's a security-sensitive bootstrap that deserves its own spec slice
  // (bundle signing, sandbox isolation strategy, CSP). Until then we show a
  // transparent notice with the component_url so operators can see what's
  // pending.
  return (
    <div className="asset-renderer asset-renderer--remote-pending">
      <p>
        A community renderer is registered for <code>{mimeType}</code> but
        dynamic loading of remote bundles is not yet enabled.
      </p>
      <p>
        Renderer: <code>{descriptor.name}</code> · version <code>{descriptor.version}</code>
      </p>
      <p>
        <a href={descriptor.componentUrl} target="_blank" rel="noopener noreferrer">
          View bundle
        </a>{" · "}
        <a href={contentUrl} download>
          Download content
        </a>
      </p>
    </div>
  );
}
