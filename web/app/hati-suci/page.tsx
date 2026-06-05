// Hati Suci — the resident-service nervous system (first Light Hub membrane).
// Mobile-first, bilingual (EN/ID). One open board everyone sees: residents
// ask for food / laundry / a ride / a repair; staff acknowledge and complete;
// outside-resource costs ride along and get marked settled. No secrets.
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useT } from "@/components/MessagesProvider";

type Role = "resident" | "staff";
type Member = { id: string; name: string; role: Role; locale: string };

type Kind = "food" | "laundry" | "cleaning" | "ride" | "repair" | "room" | "supplies" | "other";
type Status = "open" | "acknowledged" | "in_progress" | "completed" | "cancelled";

type ServiceRequest = {
  id: string;
  kind: Kind;
  detail: string;
  location?: string | null;
  when_text?: string | null;
  status: Status;
  requester_id: string;
  requester_name: string;
  acknowledged_by_name?: string | null;
  completed_by_name?: string | null;
  cost_amount?: number | null;
  cost_currency?: string;
  cost_note?: string | null;
  cost_status?: "none" | "recorded" | "paid";
  paid_by_name?: string | null;
  created_at: string;
  updated_at: string;
};

const KINDS: { key: Kind; emoji: string }[] = [
  { key: "food", emoji: "🍲" },
  { key: "laundry", emoji: "🧺" },
  { key: "cleaning", emoji: "🧹" },
  { key: "ride", emoji: "🛵" },
  { key: "repair", emoji: "🔧" },
  { key: "room", emoji: "🛏️" },
  { key: "supplies", emoji: "🛒" },
  { key: "other", emoji: "✨" },
];

const STORAGE_KEY = "hatiSuci.member";

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return (await res.json()) as T;
}

function setLocaleCookie(locale: string) {
  document.cookie = `NEXT_LOCALE=${locale}; path=/; max-age=${60 * 60 * 24 * 365}`;
}

function StatusBadge({ status }: { status: Status }) {
  const t = useT();
  const tone: Record<Status, string> = {
    open: "bg-amber-500/15 text-amber-500 border-amber-500/30",
    acknowledged: "bg-sky-500/15 text-sky-500 border-sky-500/30",
    in_progress: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
    completed: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
    cancelled: "bg-muted text-muted-foreground border-border/40",
  };
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone[status]}`}>
      {t(`hatiSuci.status.${status}`)}
    </span>
  );
}

export default function HatiSuciPage() {
  const t = useT();
  const [member, setMember] = useState<Member | null>(null);
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [loaded, setLoaded] = useState(false);

  // registration form
  const [regName, setRegName] = useState("");
  const [regRole, setRegRole] = useState<Role>("resident");

  // new-request form
  const [kind, setKind] = useState<Kind>("food");
  const [detail, setDetail] = useState("");
  const [location, setLocation] = useState("");
  const [whenText, setWhenText] = useState("");
  const [busy, setBusy] = useState(false);

  // per-card completion (optional outside-resource cost)
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [costAmount, setCostAmount] = useState("");
  const [costNote, setCostNote] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setMember(JSON.parse(raw) as Member);
    } catch {
      /* ignore */
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/household/requests?limit=200");
      if (res.ok) setRequests((await res.json()) as ServiceRequest[]);
    } catch {
      /* keep last good */
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const register = useCallback(async () => {
    const name = regName.trim();
    if (!name) return;
    setBusy(true);
    try {
      const created = await postJSON<Member>("/api/household/members", {
        name,
        role: regRole,
        locale: document.documentElement.lang || "en",
      });
      localStorage.setItem(STORAGE_KEY, JSON.stringify(created));
      setMember(created);
    } catch {
      /* surfaced via disabled state */
    } finally {
      setBusy(false);
    }
  }, [regName, regRole]);

  const submitRequest = useCallback(async () => {
    if (!member || !detail.trim()) return;
    setBusy(true);
    try {
      await postJSON("/api/household/requests", {
        requester_id: member.id,
        kind,
        detail: detail.trim(),
        location: location.trim() || null,
        when_text: whenText.trim() || null,
      });
      setDetail("");
      setLocation("");
      setWhenText("");
      await load();
    } finally {
      setBusy(false);
    }
  }, [member, detail, kind, location, whenText, load]);

  const act = useCallback(
    async (id: string, verb: string, extra: Record<string, unknown> = {}) => {
      if (!member) return;
      try {
        await postJSON(`/api/household/requests/${id}/${verb}`, { actor_id: member.id, ...extra });
        await load();
      } catch {
        /* ignore — board refreshes on next tick */
      }
    },
    [member, load],
  );

  const confirmComplete = useCallback(
    async (id: string) => {
      const amount = parseFloat(costAmount);
      await act(id, "complete", {
        cost_amount: Number.isFinite(amount) && amount > 0 ? amount : null,
        cost_note: costNote.trim() || null,
        cost_currency: "IDR",
      });
      setCompletingId(null);
      setCostAmount("");
      setCostNote("");
    },
    [act, costAmount, costNote],
  );

  const switchUser = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setMember(null);
  }, []);

  const sorted = useMemo(() => {
    const rank: Record<Status, number> = { open: 0, acknowledged: 1, in_progress: 2, completed: 3, cancelled: 4 };
    return [...requests].sort((a, b) => {
      const r = rank[a.status] - rank[b.status];
      if (r !== 0) return r;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [requests]);

  const isStaff = member?.role === "staff";

  // ---- Language toggle (always available) ----
  const langToggle = (
    <div className="flex gap-1 text-xs">
      {["en", "id"].map((l) => (
        <button
          key={l}
          onClick={() => {
            setLocaleCookie(l);
            window.location.reload();
          }}
          className="rounded-md border border-border/40 px-2 py-1 uppercase text-muted-foreground hover:text-foreground hover:bg-accent/60"
        >
          {l}
        </button>
      ))}
    </div>
  );

  // ---- Registration gate ----
  if (!member) {
    return (
      <main className="min-h-screen px-4 py-8">
        <div className="mx-auto w-full max-w-md space-y-5">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-light tracking-tight">{t("hatiSuci.title")}</h1>
            {langToggle}
          </div>
          <p className="text-sm text-muted-foreground">{t("hatiSuci.tagline")}</p>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-4">
            <p className="text-sm text-muted-foreground">{t("hatiSuci.reg.prompt")}</p>
            <input
              value={regName}
              onChange={(e) => setRegName(e.target.value)}
              placeholder={t("hatiSuci.reg.namePlaceholder")}
              className="w-full rounded-xl border border-border/40 bg-background px-4 py-3 text-base outline-none focus:border-primary/60"
            />
            <div className="grid grid-cols-2 gap-2">
              {(["resident", "staff"] as Role[]).map((r) => (
                <button
                  key={r}
                  onClick={() => setRegRole(r)}
                  className={`rounded-xl border px-3 py-3 text-sm transition-colors ${
                    regRole === r
                      ? "border-primary/60 bg-primary/10 text-foreground"
                      : "border-border/40 text-muted-foreground hover:bg-accent/40"
                  }`}
                >
                  {t(`hatiSuci.role.${r}`)}
                </button>
              ))}
            </div>
            <button
              onClick={register}
              disabled={busy || !regName.trim()}
              className="w-full rounded-xl bg-primary px-4 py-3 text-base font-medium text-primary-foreground disabled:opacity-50"
            >
              {t("hatiSuci.reg.enter")}
            </button>
          </div>
        </div>
      </main>
    );
  }

  // ---- Main board ----
  return (
    <main className="min-h-screen px-4 py-6">
      <div className="mx-auto w-full max-w-2xl space-y-5">
        <header className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-light tracking-tight">{t("hatiSuci.title")}</h1>
            <p className="text-sm text-muted-foreground">
              {t("hatiSuci.you")}: <span className="text-foreground">{member.name}</span> · {t(`hatiSuci.role.${member.role}`)}{" "}
              <button onClick={switchUser} className="underline underline-offset-2 hover:text-foreground">
                {t("hatiSuci.switchUser")}
              </button>
            </p>
          </div>
          {langToggle}
        </header>

        {/* Ask the field */}
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-3">
          <h2 className="text-base font-medium">{t("hatiSuci.add.heading")}</h2>
          <div className="grid grid-cols-4 gap-2">
            {KINDS.map((k) => (
              <button
                key={k.key}
                onClick={() => setKind(k.key)}
                className={`flex flex-col items-center gap-1 rounded-xl border px-1 py-2 text-xs transition-colors ${
                  kind === k.key
                    ? "border-primary/60 bg-primary/10 text-foreground"
                    : "border-border/40 text-muted-foreground hover:bg-accent/40"
                }`}
              >
                <span className="text-xl leading-none">{k.emoji}</span>
                <span className="text-center leading-tight">{t(`hatiSuci.kind.${k.key}`)}</span>
              </button>
            ))}
          </div>
          <textarea
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            placeholder={t("hatiSuci.add.detailPlaceholder")}
            rows={2}
            className="w-full rounded-xl border border-border/40 bg-background px-3 py-2 text-base outline-none focus:border-primary/60"
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder={t("hatiSuci.add.locationPlaceholder")}
              className="rounded-xl border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
            />
            <input
              value={whenText}
              onChange={(e) => setWhenText(e.target.value)}
              placeholder={t("hatiSuci.add.whenPlaceholder")}
              className="rounded-xl border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
            />
          </div>
          <button
            onClick={submitRequest}
            disabled={busy || !detail.trim()}
            className="w-full rounded-xl bg-primary px-4 py-3 text-base font-medium text-primary-foreground disabled:opacity-50"
          >
            {t("hatiSuci.add.button")}
          </button>
        </section>

        {/* The open board */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">{t("hatiSuci.board.heading")}</h2>
            <span className="text-xs text-muted-foreground">{t("hatiSuci.board.everyoneSees")}</span>
          </div>

          {loaded && sorted.length === 0 && (
            <p className="rounded-2xl border border-dashed border-border/40 px-4 py-8 text-center text-sm text-muted-foreground">
              {t("hatiSuci.board.empty")}
            </p>
          )}

          {sorted.map((r) => {
            const emoji = KINDS.find((k) => k.key === r.kind)?.emoji ?? "✨";
            const active = r.status !== "completed" && r.status !== "cancelled";
            const mine = r.requester_id === member.id;
            return (
              <article
                key={r.id}
                className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-2"
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl leading-none">{emoji}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-foreground break-words">{r.detail}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {t("hatiSuci.meta.requestedBy")} {r.requester_name}
                      {r.location ? ` · ${r.location}` : ""}
                      {r.when_text ? ` · ${r.when_text}` : ""}
                    </p>
                  </div>
                  <StatusBadge status={r.status} />
                </div>

                {(r.acknowledged_by_name || r.completed_by_name) && (
                  <p className="text-xs text-muted-foreground">
                    {r.completed_by_name
                      ? `${t("hatiSuci.meta.completedBy")} ${r.completed_by_name}`
                      : `${t("hatiSuci.meta.acknowledgedBy")} ${r.acknowledged_by_name}`}
                  </p>
                )}

                {/* Outside-resource cost */}
                {r.cost_status && r.cost_status !== "none" && (
                  <div className="flex items-center justify-between rounded-xl bg-background/60 px-3 py-2 text-xs">
                    <span className="text-muted-foreground">
                      💸 {r.cost_currency} {Number(r.cost_amount || 0).toLocaleString()}
                      {r.cost_note ? ` · ${r.cost_note}` : ""}
                    </span>
                    {r.cost_status === "paid" ? (
                      <span className="text-emerald-500">
                        {t("hatiSuci.cost.paid")}
                        {r.paid_by_name ? ` · ${r.paid_by_name}` : ""}
                      </span>
                    ) : (
                      <button
                        onClick={() => act(r.id, "pay")}
                        className="rounded-md border border-emerald-500/40 px-2 py-1 text-emerald-500 hover:bg-emerald-500/10"
                      >
                        {t("hatiSuci.act.markPaid")}
                      </button>
                    )}
                  </div>
                )}

                {/* Actions */}
                {active && (isStaff || mine) && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {isStaff && r.status === "open" && (
                      <button
                        onClick={() => act(r.id, "acknowledge")}
                        className="rounded-lg border border-sky-500/40 px-3 py-1.5 text-sm text-sky-500 hover:bg-sky-500/10"
                      >
                        {t("hatiSuci.act.acknowledge")}
                      </button>
                    )}
                    {isStaff && (r.status === "open" || r.status === "acknowledged") && (
                      <button
                        onClick={() => act(r.id, "start")}
                        className="rounded-lg border border-indigo-500/40 px-3 py-1.5 text-sm text-indigo-400 hover:bg-indigo-500/10"
                      >
                        {t("hatiSuci.act.start")}
                      </button>
                    )}
                    {isStaff && completingId !== r.id && (
                      <button
                        onClick={() => setCompletingId(r.id)}
                        className="rounded-lg border border-emerald-500/40 px-3 py-1.5 text-sm text-emerald-500 hover:bg-emerald-500/10"
                      >
                        {t("hatiSuci.act.complete")}
                      </button>
                    )}
                    {(isStaff || mine) && (
                      <button
                        onClick={() => act(r.id, "cancel")}
                        className="rounded-lg border border-border/40 px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent/40"
                      >
                        {t("hatiSuci.act.cancel")}
                      </button>
                    )}
                  </div>
                )}

                {/* Complete with optional outside-resource cost */}
                {completingId === r.id && (
                  <div className="space-y-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
                    <p className="text-xs text-muted-foreground">{t("hatiSuci.cost.heading")}</p>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        value={costAmount}
                        onChange={(e) => setCostAmount(e.target.value)}
                        inputMode="numeric"
                        placeholder={t("hatiSuci.cost.amountPlaceholder")}
                        className="rounded-lg border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
                      />
                      <input
                        value={costNote}
                        onChange={(e) => setCostNote(e.target.value)}
                        placeholder={t("hatiSuci.cost.notePlaceholder")}
                        className="rounded-lg border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => confirmComplete(r.id)}
                        className="flex-1 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-white"
                      >
                        {t("hatiSuci.act.complete")}
                      </button>
                      <button
                        onClick={() => setCompletingId(null)}
                        className="rounded-lg border border-border/40 px-3 py-2 text-sm text-muted-foreground"
                      >
                        {t("hatiSuci.act.cancelAction")}
                      </button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </section>
      </div>
    </main>
  );
}
