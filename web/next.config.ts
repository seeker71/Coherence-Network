import type { NextConfig } from "next";
import { loadPublicWebConfig } from "./lib/app-config";

const securityHeaders = [
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: "X-DNS-Prefetch-Control",
    value: "on",
  },
];

const API_BASE = loadPublicWebConfig().localApiBaseUrl || "http://api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  /**
   * Routing-layer redirects for retired surfaces.
   *
   * /usage, /runtime, /remote-ops → /pipeline
   *   Legacy ops pages were consolidated into /pipeline.
   *
   * /explore/concept → /vision
   *   The "swipe deck" for concepts had no shareable per-concept URL,
   *   no path back to the canonical /vision/lc-* page, and a tiny
   *   image on desktop. /vision is the real concept surface and every
   *   concept lives at a stable /vision/lc-* URL. The page-level
   *   redirect() inside /explore/[entityType]/page.tsx is also there
   *   as belt-and-suspenders, but the routing-layer redirect here
   *   fires before any RSC renders and is bulletproof.
   */
  async redirects() {
    return [
      { source: "/usage", destination: "/pipeline", permanent: true },
      { source: "/runtime", destination: "/pipeline", permanent: true },
      { source: "/remote-ops", destination: "/pipeline", permanent: true },
      { source: "/explore/concept", destination: "/vision", permanent: true },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_BASE}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
