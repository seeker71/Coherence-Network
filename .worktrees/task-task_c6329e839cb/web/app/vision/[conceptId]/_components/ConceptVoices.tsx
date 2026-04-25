"use client";

/**
 * Community voices on a concept — lived experience from those living it.
 *
 * Not moderated, not gated, not paywalled. Anyone can offer a short
 * testimony: "this is how we live it here". The form sits below the
 * existing voices as a warm invitation.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";
import { ReactionBar } from "@/components/ReactionBar";

const CONTRIBUTOR_KEY = "cc-contributor-id";

interface Voice {
  id: string;
  concept_id: string;
  author_name: string;
  author_id: string | null;
  locale: string;
  body: string;
  location: string | null;
  created_at: string | null;
  proposed_as_proposal_id: string | null;
}

interface Props {
  conceptId: string;
}

export function ConceptVoices({ conceptId }: Props) {
  const t = useT();
  const locale = useLocale();

  const [voices, setVoices] = useState<Voice[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [ripening, setRipening] = useState<string | null>(null);

  // Form state
  const [authorName, setAuthorName] = useState("");
  const [body, setBody] = useState("");
  const [location, setLocation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [thanked, setThanked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const base = getApiBase();
        const res = await fetch(`${base}/api/concepts/${conceptId}/voices`);
        if (!res.ok) {
          if (!cancelled) setVoices([]);
          return;
        }
        const data = await res.json();
        if (!cancelled) setVoices(data.voices || []);
      } catch {
        if (!cancelled) setVoices([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [conceptId]);

  async function ripenVoice(voiceId: string) {
    setRipening(voiceId);
    try {
      let authorId: string | null = null;
      try {
        authorId = localStorage.getItem(CONTRIBUTOR_KEY);
      } catch {
        /* ignore */
      }
      const base = getApiBase();
      const res = await fetch(`${base}/api/concepts/voices/${voiceId}/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author_id: authorId }),
      });
      if (!res.ok) return;
      const data = await res.json();
      const pid: string = data.proposal_id;
      setVoices((prev) =>
        (prev || []).map((v) =>
          v.id === voiceId ? { ...v, proposed_as_proposal_id: pid } : v,
        ),
      );
    } finally {
      setRipening(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!authorName.trim() || !body.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/concepts/${conceptId}/voices`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author_name: authorName.trim(),
          body: body.trim(),
          locale,
          location: location.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || "unable to offer voice");
        return;
      }
      const newVoice: Voice = await res.json();
      setVoices((prev) => [newVoice, ...(prev || [])]);
      setAuthorName("");
      setBody("");
      setLocation("");
      setThanked(true);
      setTimeout(() => setThanked(false), 4000);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <section className="max-w-3xl pt-12">
        <p className="text-sm text-stone-500 italic">{t("vision.voicesLoading")}</p>
      </section>
    );
  }

  return (
    <section className="max-w-3xl pt-12 border-t border-stone-800/60">
      <h2 className="text-xl md:text-2xl font-light text-amber-200/90 mb-2">
        {t("vision.voicesHeading")}
      </h2>
      <p className="text-sm text-stone-400 mb-6">{t("vision.voicesLede")}</p>

      {voices && voices.length > 0 ? (
        <ul className="space-y-6 mb-10">
          {voices.map((v) => (
            <li
              key={v.id}
              className="rounded-md border border-stone-800/60 bg-stone-900/40 p-5"
            >
              <p className="text-stone-200 leading-relaxed whitespace-pre-wrap">{v.body}</p>
              <p className="text-xs text-stone-500 mt-3 flex flex-wrap gap-x-3 gap-y-1">
                {v.author_id ? (
                  <Link
                    href={`/people/${encodeURIComponent(v.author_id)}`}
                    className="text-amber-300/90 hover:text-amber-200 underline-offset-4 hover:underline transition-colors"
                  >
                    {v.author_name}
                  </Link>
                ) : (
                  <span className="text-amber-300/80">{v.author_name}</span>
                )}
                {v.location && <span>· {v.location}</span>}
                {v.created_at && (
                  <time dateTime={v.created_at}>
                    · {new Date(v.created_at).toLocaleDateString(locale)}
                  </time>
                )}
                <span className="uppercase tracking-wide">· {v.locale}</span>
              </p>
              {/* Each voice is itself a surface for care — a reader can
                  react with a warm emoji or add a short reply. This turns
                  the voice list into a choir: her sentence, others' hearts
                  arriving under it, a felt sense of being received. The
                  emoji palette here is intentionally smaller than the
                  concept-level bar so voice-reactions read as light,
                  intimate gestures rather than a full decision surface. */}
              <div className="mt-3 border-t border-stone-800/40 pt-3">
                <ReactionBar
                  entityType="voice"
                  entityId={v.id}
                  palette={["💛", "🙏", "🌱", "🫶"]}
                  compact
                />
              </div>
              <div className="mt-3 flex items-center gap-3 text-xs">
                {v.proposed_as_proposal_id ? (
                  <Link
                    href={`/meet/proposal/${encodeURIComponent(v.proposed_as_proposal_id)}`}
                    className="text-emerald-300 hover:text-emerald-200"
                  >
                    {t("vision.voiceBecameProposal")} →
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => ripenVoice(v.id)}
                    disabled={ripening === v.id}
                    className="rounded-full border border-teal-700/40 bg-teal-950/20 hover:bg-teal-950/40 text-teal-200 px-3 py-1 transition-colors disabled:opacity-50"
                  >
                    {ripening === v.id ? t("vision.voiceRipening") : t("vision.voiceRipen")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-stone-500 italic mb-10">
          {t("vision.voicesEmpty")}
        </p>
      )}

      <div className="rounded-md border border-amber-700/30 bg-amber-950/10 p-5">
        <h3 className="text-sm font-medium text-amber-200/90 mb-4">
          {t("vision.voicesShareHeading")}
        </h3>
        {thanked && (
          <p className="text-sm text-emerald-300/90 mb-3">{t("vision.voicesThankYou")}</p>
        )}
        {error && <p className="text-sm text-rose-300/90 mb-3">{error}</p>}
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="text"
            value={authorName}
            onChange={(e) => setAuthorName(e.target.value)}
            placeholder={t("vision.voicesAuthorPlaceholder")}
            className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60"
            maxLength={80}
            required
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={t("vision.voicesBodyPlaceholder")}
            className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60 resize-y"
            rows={3}
            maxLength={1000}
            required
          />
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder={t("vision.voicesLocationPlaceholder")}
            className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60"
            maxLength={80}
          />
          <button
            type="submit"
            disabled={submitting || !authorName.trim() || !body.trim()}
            className="inline-flex items-center gap-2 rounded-md bg-amber-700/80 hover:bg-amber-600/90 disabled:bg-stone-800 disabled:text-stone-600 text-stone-950 px-4 py-2 text-sm font-medium transition-colors"
          >
            {submitting ? t("vision.voicesSubmitting") : t("vision.voicesSubmit")}
          </button>
        </form>
      </div>
    </section>
  );
}
