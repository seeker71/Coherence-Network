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
  /** Legacy ops pages → consolidated surfaces (nodes vs pipeline). */
  async redirects() {
    return [
      { source: "/usage", destination: "/pipeline", permanent: true },
      { source: "/runtime", destination: "/pipeline", permanent: true },
      { source: "/remote-ops", destination: "/pipeline", permanent: true },
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
