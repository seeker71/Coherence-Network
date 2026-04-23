/**
 * Built-in renderers — shipped with the platform for common MIME types.
 *
 * Per spec R6: text/markdown, image/jpeg, image/png, text/html,
 * application/pdf. These have no external component_url — they are
 * internal React components that implement the RendererProps contract.
 *
 * The SDK bootstrap should call `registerBuiltinRenderers()` on web
 * startup so the client-side registry is populated before any asset
 * page tries to resolve a renderer.
 *
 * See specs/asset-renderer-plugin.md (R6).
 */

import { useEffect, useRef } from "react";

import { registerRenderer, type RendererProps } from "./renderer-sdk";

/**
 * Emit onEngagement every 5 seconds while mounted. The platform uses
 * this signal to scale the CC pool attributed for the render.
 */
function useEngagementTick(onEngagement: (seconds: number) => void) {
  const startRef = useRef<number>(Date.now());
  useEffect(() => {
    startRef.current = Date.now();
    const interval = setInterval(() => {
      const seconds = Math.floor((Date.now() - startRef.current) / 1000);
      onEngagement(seconds);
    }, 5000);
    return () => clearInterval(interval);
  }, [onEngagement]);
}

/**
 * text/markdown — simple preformatted display. The richer web path is
 * StoryContent.tsx (concept/story renderer); this is the MIME-dispatch
 * fallback for assets registered as text/markdown without a concept
 * layer.
 */
export function MarkdownRenderer({ contentUrl, metadata, onReady, onEngagement }: RendererProps) {
  useEngagementTick(onEngagement);
  useEffect(() => {
    onReady();
  }, [onReady]);
  return (
    <div className="asset-renderer asset-renderer--markdown" data-mime="text/markdown">
      <iframe
        src={contentUrl}
        title={(metadata.title as string) || "markdown content"}
        sandbox=""
        className="w-full min-h-[60vh] border-0"
      />
    </div>
  );
}

/**
 * image/jpeg and image/png — basic image viewer.
 */
export function ImageRenderer({ contentUrl, metadata, onReady, onEngagement }: RendererProps) {
  useEngagementTick(onEngagement);
  return (
    <div className="asset-renderer asset-renderer--image" data-mime="image">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={contentUrl}
        alt={(metadata.alt as string) || ""}
        onLoad={onReady}
        className="max-w-full h-auto"
      />
    </div>
  );
}

/**
 * text/html — article renderer, sandboxed in an iframe with no
 * access to parent DOM, cookies, or scripts (spec R8).
 */
export function HtmlRenderer({ contentUrl, metadata, onReady, onEngagement }: RendererProps) {
  useEngagementTick(onEngagement);
  return (
    <div className="asset-renderer asset-renderer--html" data-mime="text/html">
      <iframe
        src={contentUrl}
        title={(metadata.title as string) || "html content"}
        sandbox="allow-same-origin"
        onLoad={onReady}
        className="w-full min-h-[60vh] border-0"
      />
    </div>
  );
}

/**
 * application/pdf — basic PDF viewer using the browser's native
 * object tag. Sandbox is inherent (browsers don't execute PDF JS
 * unless explicitly allowed).
 */
export function PdfRenderer({ contentUrl, metadata, onReady, onEngagement }: RendererProps) {
  useEngagementTick(onEngagement);
  useEffect(() => {
    // <object> doesn't fire a reliable onLoad; signal ready after mount.
    onReady();
  }, [onReady]);
  return (
    <div className="asset-renderer asset-renderer--pdf" data-mime="application/pdf">
      <object
        data={contentUrl}
        type="application/pdf"
        aria-label={(metadata.title as string) || "pdf document"}
        className="w-full min-h-[80vh]"
      >
        <a href={contentUrl}>Download PDF</a>
      </object>
    </div>
  );
}

/**
 * Register all built-in renderers with the SDK registry. Idempotent —
 * safe to call multiple times. The platform should call this once at
 * web startup.
 */
export function registerBuiltinRenderers(): void {
  registerRenderer({
    id: "builtin-markdown-v1",
    mimeTypes: ["text/markdown"],
    component: MarkdownRenderer,
  });
  registerRenderer({
    id: "builtin-image-v1",
    mimeTypes: ["image/jpeg", "image/png", "image/webp", "image/gif"],
    component: ImageRenderer,
  });
  registerRenderer({
    id: "builtin-html-v1",
    mimeTypes: ["text/html"],
    component: HtmlRenderer,
  });
  registerRenderer({
    id: "builtin-pdf-v1",
    mimeTypes: ["application/pdf"],
    component: PdfRenderer,
  });
}
