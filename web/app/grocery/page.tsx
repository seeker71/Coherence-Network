// app.hati.earth — the grocery ledger. One number, one tap.
//
// The manager stands in the market and types what they spent, in thousands
// (the *ribu* habit): 123.5 is Rp 123.500. Everything else is already
// filled in — today's date, and a description that comes from the shop
// they're standing at when GPS finds one, from a category icon when it
// doesn't, or from the custom field when they want to say it themselves.
//
// Entries that can't reach the API (a market with no signal) queue in
// localStorage and flush on the next breath, so a walk out of coverage
// never costs the manager their entry.
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Shop = {
  id: string;
  name: string;
  kind: string;
  lat?: number | null;
  lon?: number | null;
  default_description: string;
  pinned: boolean;
};

type Category = { key: string; emoji: string; en: string; id: string };

type Spend = {
  id: string;
  amount_typed: string;
  amount_idr: number;
  currency: string;
  description: string;
  category?: string | null;
  note?: string | null;
  place_id?: string | null;
  place_name?: string | null;
  spent_on: string;
  by_name: string;
  created_at: string;
  sheet_synced: boolean;
};

type SheetStatus = {
  configured: boolean;
  sheet_url?: string | null;
  pending: number;
};

type Totals = {
  on: string;
  day_total_idr: number;
  day_count: number;
  month_total_idr: number;
  month_count: number;
  remaining_idr: number;
};

type SendResult =
  | { kind: "saved"; spend: Spend }
  | { kind: "rejected" }
  | { kind: "offline" };

type Draft = {
  actor_token: string;
  amount: string;
  category: string | null;
  note: string | null;
  place_id: string | null;
  lat: number | null;
  lon: number | null;
  spent_on: string;
  kind: "buy" | "topup";
};

const TOKEN_KEY = "hatiSuci.token";
const QUEUE_KEY = "hatiGrocery.queue";
const LANG_KEY = "hatiGrocery.lang";

type Lang = "en" | "id";

const T = {
  en: {
    title: "Groceries",
    spent: "Spent",
    thousands: "in thousands",
    hint: "123.5 = Rp 123.500",
    at: "At",
    near: "you're here",
    whatFor: "What for",
    custom: "Or type it",
    customPh: "anything the icons don't say",
    save: "Record",
    saving: "Recording…",
    today: "Today",
    month: "This month",
    entries: "entries",
    recent: "Today's entries",
    none: "Nothing recorded yet today.",
    queued: "waiting for signal",
    offline: "No signal — held on this phone, will send itself.",
    identify: "Open your Hati Suci link on this phone first.",
    identifyBody:
      "This ledger uses the same door as the house board. Tap your invite link, then come back here.",
    noShop: "No shop nearby",
    saveShop: "Remember this shop",
    shopName: "Shop name",
    shopDesc: "Default description",
    add: "Save shop",
    cancel: "Cancel",
    locating: "Finding you…",
    sheet: "Sheet",
    csv: "Download CSV",
    openSheet: "Open the sheet",
    waiting: "waiting",
    zero: "Type an amount first",
    savedOk: "Recorded",
    modeBuy: "Spent",
    modeTop: "Top up",
    remaining: "Left to spend",
    topNote: "who it came from (optional)",
    saveTop: "Add to the float",
    undo: "Undo",
    refused: "That amount wasn't accepted — check it and try again.",
    removedMirrored: "Removed here. It already reached the sheet — delete that row there too.",
    remove: "Remove",
  },
  id: {
    title: "Belanja",
    spent: "Belanja",
    thousands: "dalam ribuan",
    hint: "123,5 = Rp 123.500",
    at: "Di",
    near: "Anda di sini",
    whatFor: "Untuk apa",
    custom: "Atau tulis sendiri",
    customPh: "yang tidak ada di ikon",
    save: "Catat",
    saving: "Mencatat…",
    today: "Hari ini",
    month: "Bulan ini",
    entries: "catatan",
    recent: "Catatan hari ini",
    none: "Belum ada catatan hari ini.",
    queued: "menunggu sinyal",
    offline: "Tidak ada sinyal — disimpan di HP, akan terkirim sendiri.",
    identify: "Buka tautan Hati Suci Anda di HP ini dulu.",
    identifyBody:
      "Buku belanja ini memakai pintu yang sama dengan papan rumah. Ketuk tautan undangan Anda, lalu kembali ke sini.",
    noShop: "Tidak ada toko di dekat sini",
    saveShop: "Simpan toko ini",
    shopName: "Nama toko",
    shopDesc: "Deskripsi bawaan",
    add: "Simpan toko",
    cancel: "Batal",
    locating: "Mencari lokasi…",
    sheet: "Sheet",
    csv: "Unduh CSV",
    openSheet: "Buka sheet",
    waiting: "menunggu",
    zero: "Isi jumlahnya dulu",
    savedOk: "Tercatat",
    modeBuy: "Belanja",
    modeTop: "Isi ulang",
    remaining: "Sisa",
    topNote: "dari siapa (opsional)",
    saveTop: "Tambah ke kas",
    undo: "Batalkan",
    refused: "Jumlahnya tidak diterima — periksa lalu coba lagi.",
    removedMirrored: "Dihapus di sini. Sudah masuk sheet — hapus barisnya di sana juga.",
    remove: "Hapus",
  },
} as const;

// Rp 123.500 — Indonesian grouping, the way the manager reads a price tag.
function rupiah(n: number): string {
  return "Rp " + n.toLocaleString("id-ID");
}

// What the typed thousands mean, mirrored for the live preview only.
// The recorded value is always the kernel's answer, never this.
function previewIdr(typed: string): number {
  const raw = typed.trim().replace(",", ".");
  if (!raw) return 0;
  const [w, f = ""] = raw.split(".");
  const whole = parseInt(w || "0", 10);
  if (Number.isNaN(whole)) return 0;
  const frac = f.slice(0, 3);
  const scaled = frac ? Math.floor((parseInt(frac, 10) * 1000) / Math.pow(10, frac.length)) : 0;
  return whole * 1000 + scaled;
}

function todayLocal(): string {
  // Bali is UTC+8, no DST — the same "today" the API files under.
  const now = new Date();
  const bali = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  return bali.toISOString().slice(0, 10);
}

export default function GroceryPage() {
  const [lang, setLang] = useState<Lang>("id");
  const t = T[lang];

  const [token, setToken] = useState<string | null>(null);
  const [resolved, setResolved] = useState(false);

  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);

  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [shop, setShop] = useState<Shop | null>(null);

  const [spends, setSpends] = useState<Spend[]>([]);
  const [totals, setTotals] = useState<Totals | null>(null);
  const [queued, setQueued] = useState<Draft[]>([]);
  const [sheet, setSheet] = useState<SheetStatus | null>(null);

  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ amount: number; id: string } | null>(null);
  const [mode, setMode] = useState<"buy" | "topup">("buy");
  const [addingShop, setAddingShop] = useState(false);
  const [shopName, setShopName] = useState("");
  const [shopDesc, setShopDesc] = useState("");
  const amountRef = useRef<HTMLInputElement>(null);

  const idr = useMemo(() => previewIdr(amount), [amount]);

  // ---- identity: the same device token the house board uses ----------------
  useEffect(() => {
    let saved: string | null = null;
    try {
      const url = new URL(window.location.href);
      const qt = url.searchParams.get("token");
      if (qt) {
        localStorage.setItem(TOKEN_KEY, qt);
        url.searchParams.delete("token");
        window.history.replaceState({}, "", url.pathname + url.search);
      }
      saved = localStorage.getItem(TOKEN_KEY);
      const savedLang = localStorage.getItem(LANG_KEY);
      if (savedLang === "en" || savedLang === "id") setLang(savedLang);
    } catch {
      /* private mode — the ledger still works, it just won't remember */
    }
    setToken(saved);
    setResolved(true);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch {
      /* ignore */
    }
  }, [lang]);

  const readQueue = useCallback((): Draft[] => {
    try {
      const raw = localStorage.getItem(QUEUE_KEY);
      return raw ? (JSON.parse(raw) as Draft[]) : [];
    } catch {
      return [];
    }
  }, []);

  const writeQueue = useCallback((drafts: Draft[]) => {
    try {
      localStorage.setItem(QUEUE_KEY, JSON.stringify(drafts));
    } catch {
      /* ignore */
    }
    setQueued(drafts);
  }, []);

  // ---- the board: categories, today's entries, totals ----------------------
  const refresh = useCallback(async () => {
    if (!token) return;
    const q = `token=${encodeURIComponent(token)}`;
    const [s, tot, sh] = await Promise.all([
      fetch(`/api/grocery/spend?${q}&on=${todayLocal()}`).then((r) => (r.ok ? r.json() : [])).catch(() => []),
      fetch(`/api/grocery/totals?${q}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      fetch(`/api/grocery/sheet?${q}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    ]);
    setSpends(Array.isArray(s) ? s : []);
    setTotals(tot);
    setSheet(sh);
  }, [token]);

  useEffect(() => {
    fetch("/api/grocery/categories")
      .then((r) => (r.ok ? r.json() : []))
      .then((c) => setCategories(Array.isArray(c) ? c : []))
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    void refresh();
    setQueued(readQueue());
  }, [refresh, readQueue]);

  // ---- where we are: GPS → nearest stored shop → its description ----------
  useEffect(() => {
    if (!token || typeof navigator === "undefined" || !navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Math.round(pos.coords.latitude * 1e6);
        const lon = Math.round(pos.coords.longitude * 1e6);
        setCoords({ lat, lon });
        fetch(`/api/grocery/shops/nearest?lat=${lat}&lon=${lon}&token=${encodeURIComponent(token)}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((s) => setShop(s && s.id ? s : null))
          .catch(() => setShop(null))
          .finally(() => setLocating(false));
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  }, [token]);

  // ---- sending, with the queue as the safety net ---------------------------
  // Three outcomes, never conflated. A rejection is NOT a save: the old code
  // returned "don't requeue" as success, so a refused amount cleared the form
  // and looked recorded while nothing landed.
  const send = useCallback(async (draft: Draft): Promise<SendResult> => {
    try {
      const res = await fetch(draft.kind === "topup" ? "/api/grocery/topup" : "/api/grocery/spend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (res.ok) return { kind: "saved", spend: (await res.json()) as Spend };
      // A 4xx is the server saying this entry is wrong — retrying forever
      // would never fix it, so it is refused, not queued.
      if (res.status < 500) return { kind: "rejected" };
      return { kind: "offline" };
    } catch {
      return { kind: "offline" };
    }
  }, []);

  const flush = useCallback(async () => {
    const pending = readQueue();
    if (!pending.length) return;
    const left: Draft[] = [];
    for (const d of pending) {
      const r = await send(d);
      if (r.kind === "offline") left.push(d);   // a refused draft is dropped, not retried forever
    }
    writeQueue(left);
    if (left.length < pending.length) void refresh();
  }, [readQueue, writeQueue, send, refresh]);

  useEffect(() => {
    void flush();
    const onOnline = () => void flush();
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [flush]);

  const record = useCallback(async () => {
    if (!token) return;
    if (!amount.trim() || idr <= 0) {
      setFlash(t.zero);
      amountRef.current?.focus();
      return;
    }
    setBusy(true);
    const draft: Draft = {
      actor_token: token,
      amount: amount.trim(),
      category,
      note: note.trim() || null,
      place_id: shop?.id ?? null,
      lat: shop ? null : coords?.lat ?? null,
      lon: shop ? null : coords?.lon ?? null,
      spent_on: todayLocal(),
      kind: mode,
    };
    const result = await send(draft);
    setBusy(false);
    if (result.kind === "rejected") {
      // Keep what they typed — it is the thing that needs changing.
      setFlash(t.refused);
      amountRef.current?.focus();
      return;
    }
    if (result.kind === "offline") {
      writeQueue([...readQueue(), draft]);
      setFlash(t.offline);
    } else {
      // Say it plainly and show the undo, so nobody taps twice wondering.
      setSaved({ amount: result.spend.amount_idr, id: result.spend.id });
      setFlash(null);
      void refresh();
    }
    setAmount("");
    setNote("");
    setCategory(null);
    amountRef.current?.focus();
  }, [token, amount, idr, category, note, shop, coords, mode, send, writeQueue, readQueue, refresh, t]);

  // The confirmation fades on its own; the entry stays removable from the list.
  useEffect(() => {
    if (!saved) return;
    const timer = window.setTimeout(() => setSaved(null), 8000);
    return () => window.clearTimeout(timer);
  }, [saved]);

  const remove = useCallback(async (id: string) => {
    if (!token) return;
    setBusy(true);
    try {
      const res = await fetch(
        `/api/grocery/spend/${encodeURIComponent(id)}?actor_token=${encodeURIComponent(token)}`,
        { method: "DELETE" },
      );
      if (res.ok) {
        const body = (await res.json()) as { was_mirrored: boolean };
        setSaved(null);
        // The sheet is the hub's own document — we never reach in and edit a
        // row we already handed over, so say when one needs removing by hand.
        setFlash(body.was_mirrored ? t.removedMirrored : null);
        void refresh();
      }
    } catch {
      /* leave it in place; the ledger is still the record */
    }
    setBusy(false);
  }, [token, refresh, t]);

  const saveShop = useCallback(async () => {
    if (!token || !shopName.trim() || !shopDesc.trim()) return;
    setBusy(true);
    try {
      const res = await fetch("/api/grocery/shops", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor_token: token,
          name: shopName.trim(),
          default_description: shopDesc.trim(),
          lat: coords?.lat ?? null,
          lon: coords?.lon ?? null,
        }),
      });
      if (res.ok) {
        const s = (await res.json()) as Shop;
        setShop(s);
        setAddingShop(false);
        setShopName("");
        setShopDesc("");
      }
    } catch {
      /* the shop can be saved again later; the entry never depended on it */
    }
    setBusy(false);
  }, [token, shopName, shopDesc, coords]);

  // ---- the door ------------------------------------------------------------
  if (!resolved) {
    return <main className="min-h-screen bg-neutral-950" />;
  }

  if (!token) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 text-neutral-200">
        <div className="text-xs uppercase tracking-[0.2em] text-amber-500">Hati · {t.title}</div>
        <h1 className="mt-3 text-2xl font-semibold text-neutral-50">{t.identify}</h1>
        <p className="mt-3 text-sm text-neutral-400">{t.identifyBody}</p>
        <a href="/hati-suci" className="mt-6 rounded-xl border border-amber-500/50 bg-amber-500/5 px-5 py-3 text-center text-amber-300">
          Hati Suci →
        </a>
      </main>
    );
  }

  return (
    // -mb-16 cancels the layout's bottom-nav reserve: ChromeGate hides that
    // nav on this contained route, and the reserved 4rem would otherwise show
    // as a band of site background under a full-bleed app surface.
    <main className="-mb-16 min-h-screen bg-neutral-950 text-neutral-200 md:mb-0">
      <div className="mx-auto w-full max-w-6xl px-4 pb-24 pt-6 sm:px-6">
        <header className="flex items-center justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-[0.2em] text-amber-500">Hati</div>
            <h1 className="text-xl font-semibold text-neutral-50">{t.title}</h1>
          </div>
          <button
            onClick={() => setLang(lang === "id" ? "en" : "id")}
            className="min-h-[44px] rounded-lg border border-neutral-800 px-4 text-xs uppercase tracking-wider text-neutral-400"
          >
            {lang === "id" ? "EN" : "ID"}
          </button>
        </header>

        {/* On a phone this is one column; on a laptop the ledger sits beside
            the entry pad instead of a 1000px-wide empty gutter. */}
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
          <section className="min-w-0">
            {/* ---- the number ---- */}
            <div className="mb-3 grid grid-cols-2 gap-2 rounded-xl border border-neutral-800 bg-neutral-900/40 p-1">
              {(["buy", "topup"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); setSaved(null); setFlash(null); }}
                  aria-pressed={mode === m}
                  className={`rounded-lg px-4 py-3 text-base transition ${
                    mode === m
                      ? "bg-amber-500/20 text-amber-200"
                      : "text-neutral-500 hover:text-neutral-300"
                  }`}
                >
                  {m === "buy" ? t.modeBuy : t.modeTop}
                </button>
              ))}
            </div>

            <label className="block text-sm text-neutral-400">
              {mode === "buy" ? t.spent : t.modeTop}{" "}
              <span className="text-neutral-600">· {t.thousands}</span>
            </label>
            <div className="mt-2 flex items-baseline gap-3 rounded-2xl border border-neutral-800 bg-neutral-900/60 px-5 py-4 focus-within:border-amber-500/60">
              <span className="text-2xl text-neutral-500">Rp</span>
              <input
                ref={amountRef}
                value={amount}
                onChange={(e) => setAmount(e.target.value.replace(/[^0-9.,]/g, ""))}
                inputMode="decimal"
                autoFocus
                placeholder="0"
                aria-label={`${t.spent} — ${t.thousands}`}
                className="w-full bg-transparent text-5xl font-semibold tabular-nums text-neutral-50 outline-none placeholder:text-neutral-700"
              />
              <span className="shrink-0 text-sm text-neutral-600">ribu</span>
            </div>
            <div className="mt-2 flex items-baseline justify-between gap-3">
              {idr > 0 ? (
                <span className="text-2xl font-medium tabular-nums text-amber-400">{rupiah(idr)}</span>
              ) : (
                <span className="text-sm text-neutral-600">{t.hint}</span>
              )}
              <span className="shrink-0 text-sm text-neutral-600">{todayLocal()}</span>
            </div>

            {/* ---- where: the stored shop fills the description in ---- */}
            {mode === "buy" && (
            <div className="mt-5 rounded-xl border border-neutral-800 bg-neutral-900/40 px-4 py-3">
              {locating ? (
                <div className="text-sm text-neutral-500">{t.locating}</div>
              ) : shop ? (
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[11px] uppercase tracking-wider text-emerald-500">
                      {t.at} · {t.near}
                    </div>
                    <div className="truncate text-neutral-100">{shop.name}</div>
                    <div className="truncate text-sm text-neutral-500">{shop.default_description}</div>
                  </div>
                  <button
                    onClick={() => setShop(null)}
                    aria-label={t.noShop}
                    className="-m-1 min-h-[44px] min-w-[44px] shrink-0 rounded-lg text-neutral-500 hover:text-neutral-300"
                  >
                    ✕
                  </button>
                </div>
              ) : addingShop ? (
                <div className="grid gap-2">
                  <input
                    value={shopName}
                    onChange={(e) => setShopName(e.target.value)}
                    placeholder={t.shopName}
                    className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm outline-none focus:border-amber-500/60"
                  />
                  <input
                    value={shopDesc}
                    onChange={(e) => setShopDesc(e.target.value)}
                    placeholder={t.shopDesc}
                    className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm outline-none focus:border-amber-500/60"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => void saveShop()}
                      disabled={busy || !shopName.trim() || !shopDesc.trim()}
                      className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-1.5 text-sm text-amber-300 disabled:opacity-40"
                    >
                      {t.add}
                    </button>
                    <button onClick={() => setAddingShop(false)} className="px-3 py-1.5 text-sm text-neutral-500">
                      {t.cancel}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm text-neutral-500">{t.noShop}</span>
                  {coords && (
                    <button onClick={() => setAddingShop(true)} className="shrink-0 text-xs text-amber-400 underline">
                      {t.saveShop}
                    </button>
                  )}
                </div>
              )}
            </div>
            )}

            {/* ---- icons carry the description when no shop does ---- */}
            {mode === "buy" && (
            <div className="mt-5">
              <div className="text-sm text-neutral-400">{t.whatFor}</div>
              <div className="mt-2 grid grid-cols-4 gap-2 sm:grid-cols-6">
                {categories.map((c) => {
                  const on = category === c.key;
                  return (
                    <button
                      key={c.key}
                      onClick={() => setCategory(on ? null : c.key)}
                      aria-pressed={on}
                      className={`flex min-h-[5.5rem] flex-col items-center justify-center gap-1.5 rounded-xl border px-2 py-3 transition ${
                        on
                          ? "border-amber-500/70 bg-amber-500/10"
                          : "border-neutral-800 bg-neutral-900/40 hover:border-neutral-700"
                      }`}
                    >
                      <span className="text-3xl leading-none">{c.emoji}</span>
                      <span className="text-center text-xs leading-tight text-neutral-300">
                        {lang === "id" ? c.id : c.en}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
            )}

            {/* ---- and the custom field for everything else ---- */}
            <div className="mt-4">
              <label className="block text-sm text-neutral-400">
                {mode === "buy" ? t.custom : t.topNote}
              </label>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={mode === "buy" ? t.customPh : t.topNote}
                maxLength={200}
                className="mt-2 w-full rounded-xl border border-neutral-800 bg-neutral-900/60 px-4 py-3 outline-none focus:border-amber-500/60"
              />
            </div>

            {saved && (
              <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-4 py-3">
                <div className="min-w-0 text-emerald-300">
                  <span className="text-lg">✓ {t.savedOk}</span>
                  <span className="ml-2 tabular-nums text-emerald-200">{rupiah(saved.amount)}</span>
                </div>
                <button
                  onClick={() => void remove(saved.id)}
                  disabled={busy}
                  className="min-h-[44px] shrink-0 rounded-lg border border-emerald-500/40 px-5 text-sm text-emerald-200 disabled:opacity-40"
                >
                  {t.undo}
                </button>
              </div>
            )}

            {flash && <div className="mt-3 text-sm text-amber-400">{flash}</div>}

            <button
              onClick={() => void record()}
              disabled={busy}
              className="mt-5 w-full rounded-2xl border border-amber-500/60 bg-amber-500/15 px-6 py-4 text-lg font-medium text-amber-200 transition hover:bg-amber-500/25 disabled:opacity-50"
            >
              {busy
                ? t.saving
                : `${mode === "buy" ? t.save : t.saveTop}${idr > 0 ? ` · ${rupiah(idr)}` : ""}`}
            </button>
          </section>

          {/* ---- the ledger ---- */}
          <aside className="min-w-0">
            <div className="mb-3 rounded-xl border border-amber-500/40 bg-amber-500/5 px-4 py-3">
              <div className="text-[11px] uppercase tracking-wider text-amber-600">{t.remaining}</div>
              <div className="mt-1 truncate text-2xl font-medium tabular-nums text-amber-300">
                {rupiah(totals?.remaining_idr ?? 0)}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 px-4 py-3">
                <div className="text-[11px] uppercase tracking-wider text-neutral-500">{t.today}</div>
                <div className="mt-1 truncate text-lg tabular-nums text-neutral-100">
                  {rupiah(totals?.day_total_idr ?? 0)}
                </div>
                <div className="text-xs text-neutral-600">
                  {totals?.day_count ?? 0} {t.entries}
                </div>
              </div>
              <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 px-4 py-3">
                <div className="text-[11px] uppercase tracking-wider text-neutral-500">{t.month}</div>
                <div className="mt-1 truncate text-lg tabular-nums text-neutral-100">
                  {rupiah(totals?.month_total_idr ?? 0)}
                </div>
                <div className="text-xs text-neutral-600">
                  {totals?.month_count ?? 0} {t.entries}
                </div>
              </div>
            </div>

            <div className="mt-4 text-sm text-neutral-400">{t.recent}</div>
            <ul className="mt-2 divide-y divide-neutral-900 rounded-xl border border-neutral-800 bg-neutral-900/30">
              {queued.map((d, i) => (
                <li key={`q-${i}`} className="flex items-center justify-between gap-3 px-4 py-3 opacity-60">
                  <div className="min-w-0">
                    <div className="truncate text-neutral-300">{d.note || d.category || "—"}</div>
                    <div className="text-xs text-amber-500/70">{t.queued}</div>
                  </div>
                  <div className="shrink-0 tabular-nums text-neutral-400">{rupiah(previewIdr(d.amount))}</div>
                </li>
              ))}
              {spends.length === 0 && queued.length === 0 && (
                <li className="px-4 py-6 text-center text-sm text-neutral-600">{t.none}</li>
              )}
              {spends.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <div className="truncate text-neutral-200">{s.description}</div>
                    <div className="truncate text-xs text-neutral-600">
                      {s.place_name ? `${s.place_name} · ` : ""}
                      {s.by_name}
                      {s.sheet_synced ? ` · ${t.sheet} ✓` : ""}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="tabular-nums text-neutral-100">{rupiah(s.amount_idr)}</span>
                    <button
                      onClick={() => void remove(s.id)}
                      disabled={busy}
                      aria-label={`${t.remove} ${rupiah(s.amount_idr)}`}
                      className="min-h-[44px] min-w-[44px] rounded-lg text-neutral-600 hover:text-red-400 disabled:opacity-40"
                    >
                      ✕
                    </button>
                  </div>
                </li>
              ))}
            </ul>

            <div className="mt-3 flex flex-wrap gap-4">
              <a
                href={`/api/grocery/export.csv?token=${encodeURIComponent(token)}`}
                className="text-xs text-neutral-500 underline"
              >
                {t.csv}
              </a>
              {sheet?.sheet_url && (
                <a
                  href={sheet.sheet_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-neutral-500 underline"
                >
                  {t.openSheet}
                  {sheet.pending > 0 ? ` · ${sheet.pending} ${t.waiting}` : ""}
                </a>
              )}
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
