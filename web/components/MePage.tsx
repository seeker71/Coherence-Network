"use client";

/**
 * MePage — your presence made visible.
 *
 * Reads the four localStorage keys (name, contributor_id, fingerprint,
 * invited_by) and fetches the personal feed to tally what you've
 * offered so far. No new backend endpoint — we aggregate the feed
 * items client-side so this page ships small.
 *
 * "Clear identity" wipes the four localStorage keys plus anything
 * else with the `cc-` prefix (chat drafts, presence caches, etc.) so
 * the next page load is a clean beginning. It doesn't touch the
 * server — the contributor node stays where it is; you just stop
 * being tagged as them from this browser.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";
import {
  NAME_KEY,
  CONTRIBUTOR_KEY,
  FINGERPRINT_KEY,
  INVITED_BY_KEY,
  readIdentity,
} from "@/lib/identity";

interface FeedItem {
  reason: string;
  created_at: string | null;
}

interface Footprint {
  voices: number;
  heartsGiven: number;
  heartsReceived: number;
  repliesReceived: number;
  proposals: number;
  liftedProposals: number;
  oldestIso: string | null;
}

function emptyFootprint(): Footprint {
  return {
    voices: 0,
    heartsGiven: 0,
    heartsReceived: 0,
    repliesReceived: 0,
    proposals: 0,
    liftedProposals: 0,
    oldestIso: null,
  };
}

function aggregate(items: FeedItem[]): Footprint {
  const fp = emptyFootprint();
  for (const it of items) {
    switch (it.reason) {
      case "i_voiced":
        fp.voices += 1;
        break;
      case "i_reacted":
        fp.heartsGiven += 1;
        break;
      case "i_proposed":
        fp.proposals += 1;
        break;
      case "lifted_from_my_proposal":
        fp.liftedProposals += 1;
        break;
      case "i_supported":
        fp.heartsGiven += 1;
        break;
      case "replied_to_me":
        fp.repliesReceived += 1;
        break;
      case "reaction_on_my_voice":
        fp.heartsReceived += 1;
        break;
      default:
        break;
    }
    if (it.created_at) {
      if (!fp.oldestIso || it.created_at < fp.oldestIso) {
        fp.oldestIso = it.created_at;
      }
    }
  }
  return fp;
}

function shortId(s: string): string {
  if (!s) return "";
  if (s.length <= 12) return s;
  return `${s.slice(0, 6)}…${s.slice(-4)}`;
}

function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return null;
  const ms = Date.now() - then;
  return Math.max(0, Math.floor(ms / (24 * 60 * 60 * 1000)));
}

export function MePage() {
  const t = useT();
  const locale = useLocale();
  const [loading, setLoading] = useState(true);
  const [identity, setIdentity] = useState<ReturnType<typeof readIdentity> | null>(null);
  const [footprint, setFootprint] = useState<Footprint>(emptyFootprint());
  const [confirming, setConfirming] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const ident = readIdentity();
        setIdentity(ident);
        if (!ident.contributorId) {
          setLoading(false);
          return;
        }
        const base = getApiBase();
        const res = await fetch(
          `${base}/api/feed/personal?contributor_id=${encodeURIComponent(
            ident.contributorId,
          )}&limit=500&lang=${encodeURIComponent(locale)}`,
        );
        if (!res.ok) {
          setFetchError(`feed: ${res.status}`);
          setLoading(false);
          return;
        }
        const data = await res.json();
        const items: FeedItem[] = Array.isArray(data.items) ? data.items : [];
        setFootprint(aggregate(items));
        setLoading(false);
      } catch (e) {
        setFetchError(String(e));
        setLoading(false);
      }
    })();
  }, [locale]);

  function clearIdentity() {
    try {
      // Known keys first (always wipe these)
      localStorage.removeItem(NAME_KEY);
      localStorage.removeItem(CONTRIBUTOR_KEY);
      localStorage.removeItem(FINGERPRINT_KEY);
      localStorage.removeItem(INVITED_BY_KEY);
      // Belt + suspenders: anything else prefixed cc- gets cleaned too.
      // This catches chat drafts, dismissed nudges, presence caches
      // that accumulated during this presence's lifetime.
      const toRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith("cc-")) toRemove.push(k);
      }
      toRemove.forEach((k) => localStorage.removeItem(k));
    } catch {
      /* ignore */
    }
    // Reload to let the fresh first-paint build a new presence
    window.location.href = "/";
  }

  if (loading) {
    return (
      <section className="text-sm text-muted-foreground">{t("me.loading")}</section>
    );
  }

  const hasName = Boolean(identity?.name?.trim());
  const hasContributor = Boolean(identity?.contributorId);
  const hasAny = hasName || hasContributor || Boolean(identity?.fingerprint);

  const sinceDays = daysSince(footprint.oldestIso);

  return (
    <div className="space-y-6">
      {/* Who the field knows you as */}
      <section className="px-5 py-4 rounded-2xl border border-[hsl(var(--primary)/0.25)] bg-card">
        <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
          {t("me.knownAsEyebrow")}
        </p>
        {hasName ? (
          <p className="text-xl font-light text-foreground leading-snug">
            {identity?.name}
          </p>
        ) : (
          <p className="text-base font-light text-foreground leading-snug">
            {t("me.unnamedHeading")}
          </p>
        )}
        {!hasName && (
          <p className="text-sm text-muted-foreground leading-relaxed mt-1">
            {t("me.unnamedLede")}
          </p>
        )}
        {hasName && !hasContributor && (
          <p className="text-sm text-muted-foreground leading-relaxed mt-1">
            {t("me.namedNotGraduated")}
          </p>
        )}
        {sinceDays !== null && (
          <p className="text-sm text-muted-foreground mt-2">
            {t("me.presenceSince").replace("{days}", String(sinceDays))}
          </p>
        )}
      </section>

      {/* Footprint — only if graduated, otherwise just a small nudge */}
      {hasContributor && (
        <section className="px-5 py-4 rounded-2xl border border-border bg-card">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-muted-foreground mb-2">
            {t("me.footprintEyebrow")}
          </p>
          {fetchError ? (
            <p className="text-sm text-muted-foreground">{t("me.footprintError")}</p>
          ) : (
            <FootprintProse fp={footprint} t={t} />
          )}
        </section>
      )}

      {!hasContributor && (
        <section className="px-5 py-4 rounded-2xl border border-border bg-card">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-muted-foreground mb-1.5">
            {t("me.footprintEyebrow")}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {t("me.notYetGraduated")}
          </p>
        </section>
      )}

      {/* Invited by — if known */}
      {identity?.invitedBy && (
        <section className="px-5 py-4 rounded-2xl border border-border bg-card">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-muted-foreground mb-1.5">
            {t("me.invitedByEyebrow")}
          </p>
          <p className="text-sm text-foreground leading-relaxed">
            {t("me.invitedByBody").replace("{who}", shortId(identity.invitedBy))}
          </p>
        </section>
      )}

      {/* Technical view — folded away by default */}
      {hasAny && (
        <details className="px-5 py-3 rounded-2xl border border-border bg-card">
          <summary className="text-sm text-muted-foreground cursor-pointer select-none">
            {t("me.technicalSummary")}
          </summary>
          <dl className="mt-3 text-xs text-muted-foreground space-y-1 font-mono">
            {identity?.contributorId && (
              <div>
                <dt className="inline">{t("me.contributorIdLabel")}</dt>{" "}
                <dd className="inline text-foreground">{shortId(identity.contributorId)}</dd>
              </div>
            )}
            {identity?.fingerprint && (
              <div>
                <dt className="inline">{t("me.fingerprintLabel")}</dt>{" "}
                <dd className="inline text-foreground">{shortId(identity.fingerprint)}</dd>
              </div>
            )}
          </dl>
        </details>
      )}

      {/* Clear identity — always offered */}
      <section className="px-5 py-4 rounded-2xl border border-border bg-card">
        <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-muted-foreground mb-1.5">
          {t("me.clearEyebrow")}
        </p>
        <p className="text-sm text-muted-foreground leading-relaxed mb-3">
          {t("me.clearLede")}
        </p>
        {!confirming ? (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="inline-flex items-center rounded-full border border-border px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
          >
            {t("me.clearCta")}
          </button>
        ) : (
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={clearIdentity}
              className="inline-flex items-center rounded-full bg-[hsl(var(--destructive,0_84%_60%))] text-white px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity"
            >
              {t("me.clearConfirm")}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="inline-flex items-center rounded-full border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-muted transition-colors"
            >
              {t("me.clearCancel")}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

/**
 * Render the footprint as a single warm sentence plus optional detail,
 * so it reads as story rather than dashboard.
 */
function FootprintProse({
  fp,
  t,
}: {
  fp: Footprint;
  t: ReturnType<typeof useT>;
}) {
  const parts: string[] = [];
  if (fp.voices > 0) {
    parts.push(
      fp.voices === 1
        ? t("me.footprintVoice1")
        : t("me.footprintVoicesN").replace("{n}", String(fp.voices)),
    );
  }
  if (fp.heartsGiven > 0) {
    parts.push(
      fp.heartsGiven === 1
        ? t("me.footprintHeartGiven1")
        : t("me.footprintHeartsGivenN").replace("{n}", String(fp.heartsGiven)),
    );
  }
  if (fp.proposals > 0 || fp.liftedProposals > 0) {
    const total = fp.proposals + fp.liftedProposals;
    parts.push(
      total === 1
        ? t("me.footprintProposal1")
        : t("me.footprintProposalsN").replace("{n}", String(total)),
    );
  }
  const received: string[] = [];
  if (fp.heartsReceived > 0) {
    received.push(
      fp.heartsReceived === 1
        ? t("me.footprintHeartReceived1")
        : t("me.footprintHeartsReceivedN").replace("{n}", String(fp.heartsReceived)),
    );
  }
  if (fp.repliesReceived > 0) {
    received.push(
      fp.repliesReceived === 1
        ? t("me.footprintReply1")
        : t("me.footprintRepliesN").replace("{n}", String(fp.repliesReceived)),
    );
  }

  if (parts.length === 0 && received.length === 0) {
    return (
      <p className="text-sm text-muted-foreground leading-relaxed">
        {t("me.footprintEmpty")}
      </p>
    );
  }

  return (
    <div className="text-sm text-foreground leading-relaxed space-y-2">
      {parts.length > 0 && (
        <p>
          {t("me.footprintOfferedPrefix")} {parts.join(t("me.footprintJoin"))}.
        </p>
      )}
      {received.length > 0 && (
        <p className="text-muted-foreground">
          {t("me.footprintReceivedPrefix")}{" "}
          {received.join(t("me.footprintJoin"))}.
        </p>
      )}
    </div>
  );
}
