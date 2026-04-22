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
  readIdentity,
  claimByIdentity,
  clearLocalIdentity,
} from "@/lib/identity";

interface FeedItem {
  reason: string;
  created_at: string | null;
}

interface TrailConcept {
  concept_id: string;
  asset_id: string;
  count: number;
  last_at: string | null;
}

interface Trail {
  total_reads: number;
  concept_count: number;
  concepts: TrailConcept[];
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
  const [trail, setTrail] = useState<Trail | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  // Cross-device sign-in state — a visitor landing here from a new
  // phone/laptop can type their email to recover their contributor.
  const [signInEmail, setSignInEmail] = useState("");
  const [signInStatus, setSignInStatus] = useState<"idle" | "loading" | "notFound" | "error">("idle");

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
        const [feedRes, trailRes] = await Promise.all([
          fetch(
            `${base}/api/feed/personal?contributor_id=${encodeURIComponent(
              ident.contributorId,
            )}&limit=200&lang=${encodeURIComponent(locale)}`,
          ),
          fetch(
            `${base}/api/views/trail/${encodeURIComponent(ident.contributorId)}?limit=8&days=180`,
          ).catch(() => null),
        ]);
        if (!feedRes.ok) {
          setFetchError(`feed: ${feedRes.status}`);
          setLoading(false);
          return;
        }
        const feedData = await feedRes.json();
        const items: FeedItem[] = Array.isArray(feedData.items) ? feedData.items : [];
        setFootprint(aggregate(items));
        if (trailRes && trailRes.ok) {
          const trailData = await trailRes.json();
          setTrail({
            total_reads: Number(trailData.total_reads) || 0,
            concept_count: Number(trailData.concept_count) || 0,
            concepts: Array.isArray(trailData.concepts) ? trailData.concepts : [],
          });
        }
        setLoading(false);
      } catch (e) {
        setFetchError(String(e));
        setLoading(false);
      }
    })();
  }, [locale]);

  function clearIdentity() {
    // Backend state stays — only the local cache is wiped, so
    // signing back in with email (here or on another device)
    // restores the full presence.
    clearLocalIdentity();
    window.location.href = "/";
  }

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    const email = signInEmail.trim();
    if (!email) return;
    setSignInStatus("loading");
    try {
      const profile = await claimByIdentity(getApiBase(), { email });
      if (!profile) {
        setSignInStatus("notFound");
        return;
      }
      // claimByIdentity wrote every cc-* key. A hard reload picks
      // up the freshly-hydrated state end-to-end (server-rendered
      // metadata + every mounted component).
      window.location.reload();
    } catch {
      setSignInStatus("error");
    }
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

      {/* First-arrival warmth — a graduated contributor with no trail yet.
         The body says hello before any dashboard-like surface appears. */}
      {hasContributor && !fetchError && isFirstArrival(footprint, trail) && (
        <section className="px-5 py-4 rounded-2xl border border-[hsl(var(--primary)/0.35)] bg-[hsl(var(--primary)/0.06)]">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
            {t("me.arrivalEyebrow")}
          </p>
          <p className="text-base text-foreground leading-relaxed">
            {hasName
              ? t("me.arrivalGreeting").replace("{name}", identity?.name ?? "")
              : t("me.arrivalGreetingUnnamed")}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed mt-2">
            {t("me.arrivalLede")}
          </p>
        </section>
      )}

      {/* Footprint — only if graduated, otherwise just a small nudge */}
      {hasContributor && (
        <section className="px-5 py-4 rounded-2xl border border-border bg-card">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-muted-foreground mb-2">
            {t("me.footprintEyebrow")}
          </p>
          {fetchError ? (
            <p className="text-sm text-muted-foreground">{t("me.footprintError")}</p>
          ) : (
            <>
              <FootprintProse fp={footprint} t={t} />
              {trail && trail.concepts.length > 0 && (
                <TrailProse trail={trail} t={t} />
              )}
            </>
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

      {/*
        * Cross-device sign-in. The visitor's full profile —
        * name, locale, roles, consent flags, every voice + reaction
        * + proposal attributed to their contributor_id — lives on
        * the backend. On a new phone/laptop we just ask for their
        * email, and the server hands back their contributor so
        * everything resumes. No magic link yet; anyone who knows
        * someone's email can claim that soft identity, which is fine
        * for presence (voices/reactions/resonance) but not for
        * wallet-signed actions — those layer crypto on top.
        */}
      {!hasContributor && (
        <section className="px-5 py-4 rounded-2xl border border-[hsl(var(--primary)/0.25)] bg-card">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
            {t("me.signInEyebrow")}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed mb-3">
            {t("me.signInLede")}
          </p>
          <form onSubmit={handleSignIn} className="flex flex-col sm:flex-row gap-2">
            <input
              type="email"
              required
              value={signInEmail}
              onChange={(e) => { setSignInEmail(e.target.value); setSignInStatus("idle"); }}
              placeholder={t("me.signInPlaceholder")}
              className="flex-1 px-4 py-2 rounded-full bg-background/40 border border-border text-sm text-foreground placeholder:text-muted-foreground focus:border-[hsl(var(--primary))] focus:outline-none transition-colors"
              disabled={signInStatus === "loading"}
            />
            <button
              type="submit"
              disabled={signInStatus === "loading" || !signInEmail.trim()}
              className="px-4 py-2 rounded-full bg-[hsl(var(--primary))] text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
            >
              {signInStatus === "loading" ? t("me.signInWorking") : t("me.signInCta")}
            </button>
          </form>
          {signInStatus === "notFound" && (
            <p className="mt-2 text-xs text-muted-foreground">
              {t("me.signInNotFound")}
            </p>
          )}
          {signInStatus === "error" && (
            <p className="mt-2 text-xs text-destructive">
              {t("me.signInError")}
            </p>
          )}
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

/**
 * A graduated contributor who has yet to voice, react, or leave reads
 * we can attribute. The body greets them by name before any metrics
 * surface appears — "You arrived. The field received you."
 */
function isFirstArrival(fp: Footprint, trail: Trail | null): boolean {
  const offered =
    fp.voices + fp.heartsGiven + fp.proposals + fp.liftedProposals;
  const received = fp.heartsReceived + fp.repliesReceived;
  const reads = trail?.total_reads ?? 0;
  return offered === 0 && received === 0 && reads === 0;
}

/**
 * Render the concept-trail as a warm sentence. The concept ids are
 * linked so the reader can step back into what drew them.
 */
function TrailProse({
  trail,
  t,
}: {
  trail: Trail;
  t: ReturnType<typeof useT>;
}) {
  if (trail.concepts.length === 0) return null;

  const top = trail.concepts.slice(0, 5);
  const hasMore = trail.concept_count > top.length;

  return (
    <p className="mt-3 text-sm text-foreground leading-relaxed">
      {t("me.trailPrefix")}{" "}
      {top.map((c, i) => (
        <span key={c.concept_id}>
          <a
            href={`/vision/${encodeURIComponent(c.concept_id)}`}
            className="text-foreground underline decoration-dotted underline-offset-4 hover:decoration-solid"
          >
            {humanizeConceptId(c.concept_id)}
          </a>
          {i < top.length - 1 ? t("me.footprintJoin") : hasMore ? "" : "."}
        </span>
      ))}
      {hasMore && (
        <span className="text-muted-foreground">
          {" "}
          {t("me.trailAndMore").replace(
            "{n}",
            String(trail.concept_count - top.length),
          )}
        </span>
      )}
    </p>
  );
}

function humanizeConceptId(id: string): string {
  // lc-sensing → Sensing ; lc-v-living-spaces → Living spaces
  const stripped = id.replace(/^lc-(v-)?/, "");
  const spaced = stripped.replace(/-/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
