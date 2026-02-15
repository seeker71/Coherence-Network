export const PROD_API_URL = "https://coherence-network-production.up.railway.app";
export const DEV_API_URL = "http://localhost:8000";

function _stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

export function getApiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env && env.trim()) return _stripTrailingSlash(env.trim());
  if (process.env.NODE_ENV === "production") return PROD_API_URL;
  return DEV_API_URL;
}
