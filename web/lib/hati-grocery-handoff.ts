const HATI_GROCERY_ORIGIN = "https://app.hati.earth";
const COHERENCE_WEB_ORIGIN = "https://coherencycoin.com";

type HandoffLocation = {
  hostname: string;
  origin: string;
};

function isLocalHost(hostname: string): boolean {
  const host = hostname.toLowerCase();
  return host === "localhost" || host === "127.0.0.1" || host === "::1";
}

/**
 * Carry an already-validated Hati Suci device identity to the grocery origin.
 * The destination is fixed rather than caller-controlled, so the household
 * token can never be turned into an open-redirect payload.
 */
export function groceryHandoffHref(
  token: string,
  location: HandoffLocation,
): string {
  const target = isLocalHost(location.hostname)
    ? new URL("/grocery", location.origin)
    : new URL("/", HATI_GROCERY_ORIGIN);
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
