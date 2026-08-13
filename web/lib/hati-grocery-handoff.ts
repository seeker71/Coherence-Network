const HATI_GROCERY_ORIGIN = "https://app.hati.earth";
const COHERENCE_WEB_ORIGIN = "https://coherencycoin.com";

type HandoffLocation = {
  hostname: string;
  origin: string;
};

const PRODUCTION_HOSTS = new Set([
  "coherencycoin.com",
  "www.coherencycoin.com",
  "hati.earth",
  "www.hati.earth",
  "app.hati.earth",
]);

function isProductionHost(hostname: string): boolean {
  return PRODUCTION_HOSTS.has(hostname.toLowerCase());
}

/**
 * Carry an already-validated Hati Suci device identity to the grocery origin.
 * The destination is fixed rather than caller-controlled, so the household
 * token can never be turned into an open-redirect payload. Only the known
 * production hosts hand off to app.hati.earth; every other host — localhost,
 * a LAN IP a phone is pointed at, a preview deploy — stays on its own
 * same-origin /grocery route.
 */
export function groceryHandoffHref(
  token: string,
  location: HandoffLocation,
): string {
  const target = isProductionHost(location.hostname)
    ? new URL("/", HATI_GROCERY_ORIGIN)
    : new URL("/grocery", location.origin);
  target.searchParams.set("token", token);
  return target.toString();
}

/**
 * app.hati.earth cannot read localStorage owned by coherencycoin.com. Return
 * to the canonical Hati Suci door once; that door sends a known member back
 * through groceryHandoffHref without asking them to sign in again.
 */
export function hatiSuciRecoveryHref(location: HandoffLocation): string {
  const origin =
    location.hostname.toLowerCase() === "app.hati.earth"
      ? COHERENCE_WEB_ORIGIN
      : location.origin;
  const target = new URL("/hati-suci", origin);
  target.searchParams.set("to", "grocery");
  return target.toString();
}

export function requestsGroceryReturn(search: string): boolean {
  return new URLSearchParams(search).get("to") === "grocery";
}
