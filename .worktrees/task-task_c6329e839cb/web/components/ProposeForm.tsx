"use client";

import Link from "next/link";
import { useState } from "react";
import { getApiBase } from "@/lib/api";

const NAME_KEY = "cc-reaction-author-name";
const CONTRIBUTOR_KEY = "cc-contributor-id";

interface Props {
  strings: {
    titlePlaceholder: string;
    bodyPlaceholder: string;
    authorPlaceholder: string;
    submit: string;
    submitting: string;
    thanks: string;
    viewAll: string;
  };
  locale: string;
}

export function ProposeForm({ strings, locale }: Props) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [authorName, setAuthorName] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    try {
      return localStorage.getItem(NAME_KEY) || "";
    } catch {
      return "";
    }
  });
  const [submitting, setSubmitting] = useState(false);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !authorName.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      try {
        localStorage.setItem(NAME_KEY, authorName.trim());
      } catch {
        /* ignore */
      }
      let contributorId: string | null = null;
      try {
        contributorId = localStorage.getItem(CONTRIBUTOR_KEY);
      } catch {
        /* ignore */
      }
      const base = getApiBase();
      const res = await fetch(`${base}/api/proposals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          body: body.trim(),
          author_name: authorName.trim(),
          author_id: contributorId,
          locale,
        }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || "could not create proposal");
        return;
      }
      const created = await res.json();
      setCreatedId(created.id);
      setTitle("");
      setBody("");
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (createdId) {
    return (
      <div className="rounded-md border border-emerald-700/40 bg-emerald-950/20 p-5 space-y-3">
        <p className="text-emerald-200">{strings.thanks}</p>
        <div className="flex gap-3 text-sm">
          <Link
            href={`/meet/proposal/${encodeURIComponent(createdId)}`}
            className="rounded-md bg-amber-700/80 hover:bg-amber-600/90 text-stone-950 px-3 py-1.5"
          >
            →
          </Link>
          <Link
            href="/explore/proposal"
            className="rounded-md bg-stone-800 hover:bg-stone-700 text-stone-100 px-3 py-1.5"
          >
            {strings.viewAll}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 rounded-md border border-stone-800/50 bg-stone-900/40 p-5"
    >
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder={strings.titlePlaceholder}
        className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-base text-stone-100 placeholder-stone-600 focus:outline-none focus:border-amber-600/60"
        maxLength={200}
        required
      />
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={strings.bodyPlaceholder}
        className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60 resize-y"
        rows={4}
        maxLength={4000}
      />
      <input
        type="text"
        value={authorName}
        onChange={(e) => setAuthorName(e.target.value)}
        placeholder={strings.authorPlaceholder}
        className="w-full rounded-md bg-stone-950/60 border border-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600/60"
        maxLength={80}
        required
      />
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting || !title.trim() || !authorName.trim()}
          className="rounded-md bg-amber-700/80 hover:bg-amber-600/90 disabled:bg-stone-800 disabled:text-stone-600 text-stone-950 px-4 py-2 text-sm font-medium"
        >
          {submitting ? strings.submitting : strings.submit}
        </button>
        {error && <span className="text-xs text-rose-300/90">{error}</span>}
      </div>
    </form>
  );
}
