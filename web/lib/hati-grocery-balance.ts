// Token-silent resilience policy for the private Hati grocery Sheet balance.

export type BalanceReadState = "loading" | "retrying" | "ready" | "unavailable";

export type BalanceCopyKey =
  | "balanceConnecting"
  | "balanceRetrying"
  | "balanceLastConfirmed"
  | "balanceUnavailable";

// The API owns the 13-second Sheet/DB deadline. Give that boundary room to
// finish, then make one fresh semantic attempt when it reports a transient
// miss. The minute cadence below continues healing without hammering Apps
// Script or letting a failed first breath become the page's permanent truth.
export const BALANCE_REQUEST_TIMEOUT_MS = 16_000;
export const BALANCE_RETRY_DELAYS_MS = [0, 1_500] as const;
export const BALANCE_REFRESH_INTERVAL_MS = 60_000;
// How often the "confirmed … ago" line re-reads the clock.
export const BALANCE_AGE_TICK_MS = 30_000;
const BALI_UTC_OFFSET_MS = 8 * 60 * 60 * 1_000;

// Read the UTC+8 calendar directly from the instant. Browser-local offsets
// must not participate: on a Bali-configured phone they would cancel +8 and
// postpone the day boundary until 08:00.
export function baliCalendarDay(nowMs: number = Date.now()): string {
  return new Date(nowMs + BALI_UTC_OFFSET_MS).toISOString().slice(0, 10);
}

export function isAuthorizationFailure(status: number): boolean {
  return status === 401 || status === 403;
}

export function isConfirmedSheetBalance(
  totals: { remaining_idr: number | null; remaining_source: string } | null,
): totals is { remaining_idr: number; remaining_source: "sheet" } {
  return (
    totals?.remaining_source === "sheet" &&
    typeof totals.remaining_idr === "number" &&
    Number.isFinite(totals.remaining_idr)
  );
}

export function balanceCopyKey(
  state: BalanceReadState,
  hasConfirmedBalance: boolean,
): BalanceCopyKey | null {
  if (state === "ready") return null;
  if (hasConfirmedBalance) return "balanceLastConfirmed";
  if (state === "loading") return "balanceConnecting";
  if (state === "retrying") return "balanceRetrying";
  return "balanceUnavailable";
}

// How old the last confirmed balance is, as the unit a person would say it in.
// `null` when nothing has been confirmed yet. A confirmation instant from the
// future (a phone clock behind the server) reads as "just now", never as a
// negative age.
export type ConfirmationAge =
  | { unit: "now" }
  | { unit: "minutes"; count: number }
  | { unit: "hours"; count: number }
  | { unit: "days"; count: number };

export function confirmationAge(
  confirmedAtIso: string | null | undefined,
  nowMs: number = Date.now(),
): ConfirmationAge | null {
  if (!confirmedAtIso) return null;
  const confirmedMs = Date.parse(confirmedAtIso);
  if (!Number.isFinite(confirmedMs)) return null;
  const minutes = Math.floor(Math.max(0, nowMs - confirmedMs) / 60_000);
  if (minutes < 1) return { unit: "now" };
  if (minutes < 60) return { unit: "minutes", count: minutes };
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return { unit: "hours", count: hours };
  return { unit: "days", count: Math.floor(hours / 24) };
}

// One key per draft, minted when the manager taps Record and kept in the
// offline queue, so every re-post of that draft names the same entry and the
// server records one market run however many times the phone sends it.
export function newEntryKey(): string {
  const generator = typeof crypto !== "undefined" ? crypto : undefined;
  if (generator && typeof generator.randomUUID === "function") {
    return `draft-${generator.randomUUID()}`;
  }
  const bytes = new Uint8Array(12);
  if (generator && typeof generator.getRandomValues === "function") {
    generator.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `draft-${Date.now().toString(36)}-${hex}`;
}

// A draft queued before keys existed gets one the first time the queue is read,
// so the next flush of that older draft is idempotent too. Returns the same
// array object when nothing needed a key, so callers can skip the write-back.
export function withEntryKeys<T extends { entry_key?: string | null }>(
  drafts: T[],
): Array<T & { entry_key: string }> {
  let changed = false;
  const keyed = drafts.map((draft) => {
    if (typeof draft.entry_key === "string" && draft.entry_key.length >= 8) {
      return draft as T & { entry_key: string };
    }
    changed = true;
    return { ...draft, entry_key: newEntryKey() };
  });
  return changed ? keyed : (drafts as Array<T & { entry_key: string }>);
}
