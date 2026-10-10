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
