"use client";

/**
 * ReactionBar — emoji + comment surface for any entity.
 *
 * Drops into any page that has an entity_type + entity_id. The bar shows:
 *   1. Current emoji aggregate (🌱 3 · 💛 7 · 🙏 2 · …)
 *   2. A small palette of common "care" emojis to add in one tap
 *   3. A collapsed comment slot that expands when tapped
 *
 * Trust-by-default: author_name is asked for once and remembered in
 * localStorage; no sign-in flow. The same component serves concepts,
 * ideas, specs, contributors, communities, workspaces, assets, etc.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";

type EntityType =
  | "concept"
  | "idea"
  | "spec"
  | "contributor"
  | "community"
  | "workspace"
  | "asset"
  | "contribution"
  | "story";

interface Reaction {
  id: string;
  entity_type: string;
  entity_id: string;
  author_name: string;
  emoji: string | null;
  comment: string | null;
  locale: string;
  created_at: string | null;
}

interface Summary {
  entity_type: string;
  entity_id: string;
  emojis: { emoji: string; count: number }[];
  comment_count: number;
  total: number;
}

interface Props {
  entityType: EntityType;
  entityId: string;
  palette?: string[];
  compact?: boolean;
}

const DEFAULT_PALETTE = ["🌱", "💛", "🙏", "✨", "🔥", "🫶", "👀", "💡"];
const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";

export function ReactionBar({
  entityType,
  entityId,
  palette = DEFAULT_PALETTE,
  compact = false,
}: Props) {
  const t = useT();
  const locale = useLocale();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [reactions, setReactions] = useState<Reaction[] | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [authorName, setAuthorName] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [thanked, setThanked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isContributor, setIsContributor] = useState(false);
  const [showInvite, setShowInvite] = useState(false);

  // Load stored author name + contributor status once
  useEffect(() => {
    try {
      const stored = localStorage.getItem(NAME_KEY);
      if (stored) setAuthorName(stored);
      setIsContributor(Boolean(localStorage.getItem(CONTRIBUTOR_KEY)));
    } catch {
      /* localStorage may be unavailable */
    }
  }, []);

  // Fetch current reactions + summary
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const base = getApiBase();
        const res = await fetch(
          `${base}/api/reactions/${entityType}/${entityId}?limit=50`,
        );
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        setSummary(data.summary);
        setReactions(data.reactions || []);
      } catch {
        /* transient — ignore, try next mount */
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [entityType, entityId]);

  async function send(params: { emoji?: string; comment?: string }) {
    if (!authorName.trim()) {
      setExpanded(true);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      try {
        localStorage.setItem(NAME_KEY, authorName.trim());
      } catch {
        /* ignore */
      }
      const base = getApiBase();
      const res = await fetch(`${base}/api/reactions/${entityType}/${entityId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author_name: authorName.trim(),
          emoji: params.emoji,
          comment: params.comment,
          locale,
        }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || "could not send reaction");
        return;
      }
      const data = await res.json();
      setSummary(data.summary);
      setReactions((prev) => [data.reaction, ...(prev || [])]);
      setThanked(true);
      setTimeout(() => setThanked(false), 2500);
      if (params.comment) setComment("");
      // If they are not yet a contributor, invite them to let their name stand
      // with this vision. Shown softly — never as a gate.
      if (!isContributor) setShowInvite(true);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const emojiRow = summary?.emojis && summary.emojis.length > 0 ? summary.emojis : [];

  return (
    <section
      className={
        compact
          ? "flex flex-wrap items-center gap-2 text-sm"
          : "rounded-md border border-stone-800/50 bg-stone-900/30 p-4 space-y-3"
      }
      aria-label={t("reactions.ariaLabel")}
    >
      {/* Current aggregate */}
      {emojiRow.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {emojiRow.map((e) => (
            <span
              key={e.emoji}
              className="inline-flex items-center gap-1 rounded-full bg-stone-800/60 px-2 py-0.5 text-xs text-stone-300"
              title={`${e.count}`}
            >
              <span className="text-sm">{e.emoji}</span>
              <span className="text-stone-500">{e.count}</span>
            </span>
          ))}
          {summary && summary.comment_count > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-stone-800/60 px-2 py-0.5 text-xs text-stone-400">
              💬 {summary.comment_count}
            </span>
          )}
        </div>
      )}

      {/* Palette */}
      <div className="flex flex-wrap items-center gap-1">
        {palette.map((em) => (
          <button
            key={em}
            type="button"
            onClick={() => send({ emoji: em })}
            disabled={submitting}
            className="h-8 w-8 rounded-full hover:bg-stone-800/60 disabled:opacity-40 transition-colors text-lg leading-none"
            aria-label={`react ${em}`}
          >
            {em}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="ml-2 rounded-full px-3 py-1 text-xs text-stone-400 hover:text-amber-300/90 hover:bg-stone-800/60 transition-colors"
        >
          {expanded ? t("reactions.closeComment") : t("reactions.addComment")}
        </button>
        {thanked && (
          <span className="text-xs text-emerald-300/90 ml-2">
            {t("reactions.thanks")}
          </span>
        )}
      </div>

      {/* Soft invitation to become a contributor — their name standing with
          this vision as a whole. Never a gate; always a door. */}
      {showInvite && !isContributor && (
        <div className="rounded-md bg-teal-950/20 border border-teal-800/40 px-3 py-2 text-xs text-teal-200/90">
          {t("reactions.inviteContributorLede")}{" "}
          <Link
            href="/vision/join"
            className="text-teal-300 hover:text-teal-200 underline underline-offset-2"
          >
            {t("reactions.inviteContributorLink")}
          </Link>
          <button
            type="button"
            onClick={() => setShowInvite(false)}
            className="ml-3 text-stone-500 hover:text-stone-300"
            aria-label="dismiss"
          >
            ×
          </button>
        </div>
      )}

      {/* Comment slot */}
      {expanded && (
        <div className="space-y-2">
          <input
            type="text"
            value={authorName}
            onChange={(e) => setAuthorName(e.target.value)}
            placeholder={t("reactions.authorPlaceholder")}
            className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-1.5 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60"
            maxLength={80}
          />
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={t("reactions.commentPlaceholder")}
            className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-1.5 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60 resize-y"
            rows={2}
            maxLength={800}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => comment.trim() && send({ comment })}
              disabled={submitting || !authorName.trim() || !comment.trim()}
              className="rounded-md bg-amber-700/80 hover:bg-amber-600/90 disabled:bg-stone-800 disabled:text-stone-600 text-stone-950 px-3 py-1 text-xs font-medium transition-colors"
            >
              {submitting ? t("reactions.sending") : t("reactions.send")}
            </button>
            {error && <span className="text-xs text-rose-300/90">{error}</span>}
          </div>
        </div>
      )}

      {/* Comment stream */}
      {!compact && reactions && reactions.filter((r) => r.comment).length > 0 && (
        <ul className="space-y-2 pt-2 border-t border-stone-800/40">
          {reactions
            .filter((r) => r.comment)
            .slice(0, 10)
            .map((r) => (
              <li key={r.id} className="text-sm">
                {r.emoji && <span className="mr-1">{r.emoji}</span>}
                <span className="text-stone-200">{r.comment}</span>
                <span className="text-xs text-stone-500 ml-2">
                  — {r.author_name}
                  {r.created_at && (
                    <>
                      {" · "}
                      <time dateTime={r.created_at}>
                        {new Date(r.created_at).toLocaleDateString(locale)}
                      </time>
                    </>
                  )}
                </span>
              </li>
            ))}
        </ul>
      )}
    </section>
  );
}
