import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const source = readFileSync(join(__dirname, "../app/grocery/page.tsx"), "utf8");

describe("Hati grocery balance layout", () => {
  it("places the phone balance before the entry pad", () => {
    const phoneBalance = source.indexOf('className="mt-6 lg:hidden"');
    const entryPad = source.indexOf('className="mt-3 grid gap-6 lg:mt-6');

    expect(phoneBalance).toBeGreaterThan(-1);
    expect(entryPad).toBeGreaterThan(phoneBalance);
  });

  it("keeps the laptop balance in the ledger column", () => {
    expect(source).toContain('className="mb-3 hidden lg:block"');
  });

  it("never turns an unavailable historical Sheet balance into zero", () => {
    expect(source).toContain('remaining_idr: number | null');
    expect(source).toContain('remaining === null ? "—" : rupiah(remaining)');
    expect(source).toContain('remaining={confirmedRemaining}');
    expect(source).not.toContain('remaining={totals?.remaining_idr ?? 0}');
  });

  it("does not call the Sheet unavailable while its first read is still loading", () => {
    expect(source).toContain('useState<BalanceReadState>("loading")');
    expect(source).toContain('statusText={balanceStatusText}');
    expect(source).not.toContain('unavailable={t.balanceUnavailable}');
  });

  it("keeps healing a transient Sheet read without replacing a confirmed balance", () => {
    expect(source).toContain("for (const delayMs of BALANCE_RETRY_DELAYS_MS)");
    expect(source).toContain('window.addEventListener("online", recover)');
    expect(source).toContain('document.addEventListener("visibilitychange", onVisible)');
    expect(source).toContain("confirmedRemainingRef.current = attempt.value.remaining_idr");
    expect(source).toContain("generation !== balanceReadGenerationRef.current");
  });

  it("coalesces ordinary reads and cancels only for a required fresh read", () => {
    expect(source).toContain("if (active && !forceFresh) return active");
    expect(source).toContain("balanceReadAbortRef.current?.abort()");
    expect(source).toContain("void refresh(true, true)");
    expect(source).toContain("return confirmedRemainingRef.current === null ? \"loading\" : \"retrying\"");
  });

  it("refreshes both totals and today's rows after Bali midnight", () => {
    expect(source).toContain("if (today !== boardDayRef.current)");
    expect(source).toContain("void refresh(true)");
    expect(source).toContain("boardDayRef.current = requestedDay");
    expect(source).toContain("if (Array.isArray(s))");
  });

  it("does not present stale aggregates as current when totals cannot refresh", () => {
    expect(source).toContain("if (!receivedTotals) setTotals(null)");
    expect(source).toContain("totals ? rupiah(totals.day_total_idr) : \"—\"");
    expect(source).toContain("totals ? rupiah(totals.month_total_idr) : \"—\"");
  });

  it("coalesces same-day board recovery and cancels obsolete board reads", () => {
    expect(source).toContain("boardRefreshDayRef.current === requestedDay");
    expect(source).toContain("if (activeBoard) boardRefreshAbortRef.current?.abort()");
    expect(source).toContain("boardController.signal");
    expect(source).toContain("generation !== boardRefreshGenerationRef.current");
    expect(source).toContain("() => boardController.abort()");
    expect(source).toContain("window.clearTimeout(boardTimeout)");
    expect(source).toContain("A shared timeout may abort only one slow sibling");
  });

  it("hides stale entries while a new-day or post-mutation board read recovers", () => {
    expect(source).toContain("replaceBoard || requestedDay !== boardDayRef.current");
    expect(source).toContain("setSpends([])");
    expect(source).toContain("setEntriesLoading(true)");
    expect(source).toContain("setEntriesLoading(false)");
    expect(source).toContain("{t.entriesConnecting}");
    expect(source).toContain("if (replaceBoard) boardDayRef.current = null");
  });

  it("returns an unauthorized device to the identity recovery door", () => {
    expect(source).toContain("if (attempt.authorizationFailed)");
    expect(source).toContain("clearInvalidIdentity()");
    expect(source).toContain("localStorage.removeItem(TOKEN_KEY)");
    expect(source).toContain("localStorage.removeItem(QUEUE_KEY)");
    expect(source).toContain("setToken(null)");
  });

  it("makes a blocked pre-Entry-ID row visible instead of replaying silently", () => {
    expect(source).toContain("blocked_legacy?: number");
    expect(source).toContain("sheet.blocked_legacy ?? 0");
  });
});
