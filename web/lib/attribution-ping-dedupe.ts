const RECENT_PING_PREFIX = "cc-recent-attribution-ping:";
const RECENT_PING_WINDOW_MS = 5000;

function keyFor(assetId: string): string {
  return `${RECENT_PING_PREFIX}${assetId}`;
}

export function markRecentAttributionPing(assetId: string) {
  if (typeof window === "undefined" || !assetId) return;
  try {
    sessionStorage.setItem(keyFor(assetId), Date.now().toString());
  } catch {
    /* best-effort duplicate suppression only */
  }
}

export function consumeRecentAttributionPing(assetId: string): boolean {
  if (typeof window === "undefined" || !assetId) return false;
  try {
    const key = keyFor(assetId);
    const raw = sessionStorage.getItem(key);
    if (!raw) return false;
    sessionStorage.removeItem(key);
    const age = Date.now() - Number(raw);
    return Number.isFinite(age) && age >= 0 && age <= RECENT_PING_WINDOW_MS;
  } catch {
    return false;
  }
}
