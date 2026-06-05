// Hati Suci — the resident-service nervous system (first Light Hub membrane).
// Mobile-first, bilingual. Light identity: a device token remembers you;
// residents invite others by name + role via a WhatsApp-shareable link that
// auto-registers and binds them on first tap. Seeing is open to any registered
// cell; writing (asking, tending, settling) needs a resident's vouch.
"use client";

import QRCode from "qrcode";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useT } from "@/components/MessagesProvider";

type Role = "resident" | "staff" | "member";
type Member = {
  id: string;
  name: string;
  role: Role;
  write_access: boolean;
  status: string;
  token: string;
  phone?: string | null;
  invited_by_name?: string | null;
};
type PublicMember = {
  id: string;
  name: string;
  role: Role;
  write_access: boolean;
  status: string;
  invited_by_name?: string | null;
  created_at: string;
};

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

const TOKEN_KEY = "hatiSuci.token";

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return (await res.json()) as T;
}

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(path);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
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
  const [resolved, setResolved] = useState(false);
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [members, setMembers] = useState<PublicMember[]>([]);

  const [joinName, setJoinName] = useState("");
  const [kind, setKind] = useState<Kind>("food");
  const [detail, setDetail] = useState("");
  const [location, setLocation] = useState("");
  const [whenText, setWhenText] = useState("");
  const [busy, setBusy] = useState(false);

  const [invName, setInvName] = useState("");
  const [invRole, setInvRole] = useState<Role>("member");
  const [invPhone, setInvPhone] = useState("");
  const [inviteLink, setInviteLink] = useState<{ name: string; url: string; whatsapp: string; qr: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const [completingId, setCompletingId] = useState<string | null>(null);
  const [costAmount, setCostAmount] = useState("");
  const [costNote, setCostNote] = useState("");

  // Identity: ?token in URL → store + clean; then localStorage token → /me.
  useEffect(() => {
    let token: string | null = null;
    try {
      const url = new URL(window.location.href);
      const qt = url.searchParams.get("token");
      if (qt) {
        localStorage.setItem(TOKEN_KEY, qt);
        url.searchParams.delete("token");
        window.history.replaceState({}, "", url.pathname + url.search);
      }
      token = localStorage.getItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    if (!token) {
      setResolved(true);
      return;
    }
    void (async () => {
      const me = await getJSON<Member>(`/api/household/me?token=${encodeURIComponent(token)}`);
      if (me) setMember(me);
      else {
        try {
          localStorage.removeItem(TOKEN_KEY);
        } catch {
          /* ignore */
        }
      }
      setResolved(true);
    })();
  }, []);

  const load = useCallback(async () => {
    const r = await getJSON<ServiceRequest[]>("/api/household/requests?limit=200");
    if (r) setRequests(r);
    const m = await getJSON<PublicMember[]>("/api/household/members");
    if (m) setMembers(m);
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const watch = useCallback(async () => {
    const name = joinName.trim();
    if (!name) return;
    setBusy(true);
    try {
      const m = await postJSON<Member>("/api/household/members", {
        name,
        locale: document.documentElement.lang || "en",
      });
      localStorage.setItem(TOKEN_KEY, m.token);
      setMember(m);
    } catch {
      /* surfaced via disabled state */
    } finally {
      setBusy(false);
    }
  }, [joinName]);

  const token = member?.token ?? "";
  const canWrite = !!member?.write_access;
  const isResident = member?.role === "resident";

  const submitRequest = useCallback(async () => {
    if (!token || !detail.trim()) return;
    setBusy(true);
    try {
      await postJSON("/api/household/requests", {
        actor_token: token,
        kind,
        detail: detail.trim(),
        location: location.trim() || null,
        when_text: whenText.trim() || null,
      });
      setDetail("");
      setLocation("");
      setWhenText("");
      await load();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }, [token, detail, kind, location, whenText, load]);

  const act = useCallback(
    async (id: string, verb: string, extra: Record<string, unknown> = {}) => {
      if (!token) return;
      try {
        await postJSON(`/api/household/requests/${id}/${verb}`, { actor_token: token, ...extra });
        await load();
      } catch {
        /* ignore */
      }
    },
    [token, load],
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

  const makeInvite = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    try {
      const inv = await postJSON<Member>("/api/household/invites", {
        inviter_token: token,
        name: invName.trim() || null,
        role: invRole,
        phone: invPhone.trim() || null,
      });
      const url = `${window.location.origin}/hati-suci?token=${encodeURIComponent(inv.token)}`;
      const dispName = invName.trim() || t(`hatiSuci.role.${invRole}`);
      const msg = `${t("hatiSuci.whatsappMsg", { name: dispName })} ${url}`;
      const digits = invPhone.replace(/[^0-9]/g, "");
      const whatsapp = digits
        ? `https://wa.me/${digits}?text=${encodeURIComponent(msg)}`
        : `https://wa.me/?text=${encodeURIComponent(msg)}`;
      const qr = await QRCode.toDataURL(url, { width: 240, margin: 1 });
      setInviteLink({ name: dispName, url, whatsapp, qr });
      setInvName("");
      setInvPhone("");
      await load();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }, [token, invName, invRole, invPhone, t, load]);

  const grantWrite = useCallback(
    async (memberId: string) => {
      if (!token) return;
      try {
        await postJSON(`/api/household/members/${memberId}/grant-write`, { actor_token: token });
        await load();
      } catch {
        /* ignore */
      }
    },
    [token, load],
  );

  const switchUser = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setMember(null);
  }, []);

  const copyLink = useCallback((url: string) => {
    try {
      void navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }, []);

  const sorted = useMemo(() => {
    const rank: Record<Status, number> = { open: 0, acknowledged: 1, in_progress: 2, completed: 3, cancelled: 4 };
    return [...requests].sort((a, b) => {
      const r = rank[a.status] - rank[b.status];
      if (r !== 0) return r;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [requests]);

  const pendingVouch = useMemo(
    () => members.filter((m) => !m.write_access && m.role === "member"),
    [members],
  );

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

  if (!resolved) {
    return (
      <main className="min-h-screen px-4 py-8">
        <div className="mx-auto w-full max-w-md">
          <p className="text-muted-foreground">{t("hatiSuci.title")}…</p>
        </div>
      </main>
    );
  }

  // ---- Join gate (no identity yet) ----
  if (!member) {
    return (
      <main className="min-h-screen px-4 py-8">
        <div className="mx-auto w-full max-w-md space-y-5">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-light tracking-tight">{t("hatiSuci.title")}</h1>
            {langToggle}
          </div>
          <p className="text-sm text-muted-foreground">{t("hatiSuci.tagline")}</p>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
            <p className="text-sm text-muted-foreground">{t("hatiSuci.join.openInvite")}</p>
            <input
              value={joinName}
              onChange={(e) => setJoinName(e.target.value)}
              placeholder={t("hatiSuci.reg.namePlaceholder")}
              className="w-full rounded-xl border border-border/40 bg-background px-4 py-3 text-base outline-none focus:border-primary/60"
            />
            <button
              onClick={watch}
              disabled={busy || !joinName.trim()}
              className="w-full rounded-xl bg-primary px-4 py-3 text-base font-medium text-primary-foreground disabled:opacity-50"
            >
              {t("hatiSuci.join.watch")}
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
              {t("hatiSuci.you")}: <span className="text-foreground">{member.name}</span> · {t(`hatiSuci.role.${member.role}`)}
              {!canWrite ? ` · ${t("hatiSuci.seeOnly")}` : ""}{" "}
              <button onClick={switchUser} className="underline underline-offset-2 hover:text-foreground">
                {t("hatiSuci.switchUser")}
              </button>
            </p>
          </div>
          {langToggle}
        </header>

        {/* Invite (residents only) */}
        {isResident && (
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 space-y-3">
            <h2 className="text-base font-medium">{t("hatiSuci.invite.heading")}</h2>
            <div className="grid grid-cols-3 gap-2">
              {(["resident", "staff", "member"] as Role[]).map((r) => (
                <button
                  key={r}
                  onClick={() => setInvRole(r)}
                  className={`rounded-xl border px-2 py-2 text-sm transition-colors ${
                    invRole === r
                      ? "border-primary/60 bg-primary/10 text-foreground"
                      : "border-border/40 text-muted-foreground hover:bg-accent/40"
                  }`}
                >
                  {t(`hatiSuci.role.${r}`)}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                value={invName}
                onChange={(e) => setInvName(e.target.value)}
                placeholder={t("hatiSuci.invite.namePlaceholder")}
                className="rounded-xl border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
              />
              <input
                value={invPhone}
                onChange={(e) => setInvPhone(e.target.value)}
                inputMode="tel"
                placeholder={t("hatiSuci.invite.phonePlaceholder")}
                className="rounded-xl border border-border/40 bg-background px-3 py-2 text-sm outline-none focus:border-primary/60"
              />
            </div>
            <button
              onClick={makeInvite}
              disabled={busy}
              className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {t("hatiSuci.invite.create")}
            </button>

            {inviteLink && (
              <div className="space-y-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
                <div className="flex flex-col items-center gap-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={inviteLink.qr} alt="Join QR" width={200} height={200} className="rounded-lg bg-white p-2" />
                  <p className="text-center text-xs text-muted-foreground">{t("hatiSuci.invite.scanToJoin", { name: inviteLink.name })}</p>
                </div>
                <p className="break-all rounded-lg bg-background/60 px-2 py-1.5 text-[11px] text-muted-foreground">{inviteLink.url}</p>
                <div className="flex gap-2">
                  <a
                    href={inviteLink.whatsapp}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 rounded-lg border border-emerald-500/40 px-3 py-2 text-center text-sm font-medium text-emerald-600 dark:text-emerald-400"
                  >
                    {t("hatiSuci.invite.shareWhatsApp")}
                  </a>
                  <button
                    onClick={() => copyLink(inviteLink.url)}
                    className="rounded-lg border border-border/40 px-3 py-2 text-sm text-muted-foreground hover:bg-accent/40"
                  >
                    {copied ? t("hatiSuci.invite.copied") : t("hatiSuci.invite.copy")}
                  </button>
                </div>
              </div>
            )}

            {/* Vouch see-only members into write */}
            {pendingVouch.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <p className="text-xs text-muted-foreground">{t("hatiSuci.people.heading")}</p>
                {pendingVouch.map((m) => (
                  <div key={m.id} className="flex items-center justify-between rounded-lg bg-background/50 px-3 py-1.5 text-sm">
                    <span className="text-foreground">{m.name} <span className="text-muted-foreground">· {t("hatiSuci.seeOnly")}</span></span>
                    <button
                      onClick={() => grantWrite(m.id)}
                      className="rounded-md border border-sky-500/40 px-2 py-1 text-xs text-sky-500 hover:bg-sky-500/10"
                    >
                      {t("hatiSuci.people.grantWrite")}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Ask the field (writers) or a gentle note (see-only) */}
        {canWrite ? (
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
        ) : (
          <p className="rounded-2xl border border-dashed border-border/40 px-4 py-4 text-center text-sm text-muted-foreground">
            {t("hatiSuci.noWriteNote")}
          </p>
        )}

        {/* The open board */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">{t("hatiSuci.board.heading")}</h2>
            <span className="text-xs text-muted-foreground">{t("hatiSuci.board.everyoneSees")}</span>
          </div>

          {sorted.length === 0 && (
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
                      canWrite && (
                        <button
                          onClick={() => act(r.id, "pay")}
                          className="rounded-md border border-emerald-500/40 px-2 py-1 text-emerald-500 hover:bg-emerald-500/10"
                        >
                          {t("hatiSuci.act.markPaid")}
                        </button>
                      )
                    )}
                  </div>
                )}

                {active && canWrite && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {r.status === "open" && (
                      <button
                        onClick={() => act(r.id, "acknowledge")}
                        className="rounded-lg border border-sky-500/40 px-3 py-1.5 text-sm text-sky-500 hover:bg-sky-500/10"
                      >
                        {t("hatiSuci.act.acknowledge")}
                      </button>
                    )}
                    {(r.status === "open" || r.status === "acknowledged") && (
                      <button
                        onClick={() => act(r.id, "start")}
                        className="rounded-lg border border-indigo-500/40 px-3 py-1.5 text-sm text-indigo-400 hover:bg-indigo-500/10"
                      >
                        {t("hatiSuci.act.start")}
                      </button>
                    )}
                    {completingId !== r.id && (
                      <button
                        onClick={() => setCompletingId(r.id)}
                        className="rounded-lg border border-emerald-500/40 px-3 py-1.5 text-sm text-emerald-500 hover:bg-emerald-500/10"
                      >
                        {t("hatiSuci.act.complete")}
                      </button>
                    )}
                    {(mine || isResident) && (
                      <button
                        onClick={() => act(r.id, "cancel")}
                        className="rounded-lg border border-border/40 px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent/40"
                      >
                        {t("hatiSuci.act.cancel")}
                      </button>
                    )}
                  </div>
                )}

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
