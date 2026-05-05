"use client";

// /begin — the warm entry into the body. A simple form, not a multi-step
// onboarding. The visitor writes who they are and what they carry; the body
// receives them and lands them on /arrival/{id} as a held cell.

import { useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useT } from "@/components/MessagesProvider";
import { L } from "@/components/inline-link";
import {
  NAME_KEY,
  CONTRIBUTOR_KEY,
  EMAIL_KEY,
} from "@/lib/identity";

interface GraduateOut {
  contributor_id: string;
  created: boolean;
  email?: string | null;
  author_display_name?: string | null;
}

const ROLE_IDS = [
  "land-steward",
  "builder-maker",
  "healer",
  "teacher",
  "musician-artist",
  "farmer-gardener",
  "cook-baker",
  "engineer-coder",
  "writer-translator",
  "host-keeper",
  "transport-mechanic",
  "elder-witness",
  "other",
] as const;

// Render a translated string carrying inline [label](href) markdown links.
function renderProse(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const [, label, href] = m;
    parts.push(
      <L key={`l${key++}`} href={href}>
        {label}
      </L>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function BeginPage() {
  const t = useT();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [authorName, setAuthorName] = useState("");
  const [email, setEmail] = useState("");
  const [location, setLocation] = useState("");
  const [skills, setSkills] = useState("");
  const [offering, setOffering] = useState("");
  const [message, setMessage] = useState("");
  const [resonantRoles, setResonantRoles] = useState<string[]>([]);

  const toggleRole = (id: string) => {
    setResonantRoles((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    );
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!authorName.trim()) {
      setError(t("begin.errorNameRequired"));
      return;
    }
    if (!email.trim()) {
      setError(t("begin.errorEmailRequired"));
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${getApiBase()}/api/contributors/graduate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author_name: authorName.trim(),
          email: email.trim(),
          location: location.trim() || null,
          skills: skills.trim() || null,
          offering: offering.trim() || null,
          message: message.trim() || null,
          resonant_roles: resonantRoles.length ? resonantRoles : null,
          consent_email_updates: true,
          consent_share_name: true,
          consent_findable: true,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`Server returned ${res.status}: ${body.slice(0, 180)}`);
      }
      const data = (await res.json()) as GraduateOut;
      // Persist to the shared identity layer so /me, /identity, /me/work see
      // the new visitor without an extra round-trip.
      try {
        localStorage.setItem(NAME_KEY, authorName.trim());
        localStorage.setItem(CONTRIBUTOR_KEY, data.contributor_id);
        localStorage.setItem(EMAIL_KEY, email.trim());
      } catch {}
      router.push(`/arrival/${encodeURIComponent(data.contributor_id)}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("begin.errorGeneric"),
      );
      setSubmitting(false);
    }
  }

  return (
    <main
      id="main-content"
      className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none"
    >
      <p className="not-prose text-xs uppercase tracking-widest text-muted-foreground">
        {t("begin.eyebrow")}
      </p>
      <h1 className="text-3xl font-light tracking-tight">{t("begin.h1")}</h1>

      <p className="text-lg leading-relaxed text-stone-300">
        {renderProse(t("begin.intro"))}
      </p>

      <p className="text-sm text-muted-foreground italic">
        {renderProse(t("begin.emailFallback"))}
      </p>

      <hr className="border-border/30 my-8" />

      <form onSubmit={handleSubmit} className="not-prose space-y-6">
        <div className="space-y-2">
          <label htmlFor="author_name" className="block text-sm font-medium text-stone-200">
            {t("begin.labelName")} <span className="text-amber-500">*</span>
          </label>
          <input
            id="author_name"
            type="text"
            required
            value={authorName}
            onChange={(e) => setAuthorName(e.target.value)}
            placeholder={t("begin.placeholderName")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="email" className="block text-sm font-medium text-stone-200">
            {t("begin.labelEmail")} <span className="text-amber-500">*</span>
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("begin.placeholderEmail")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
          <p className="text-xs text-muted-foreground italic">
            {t("begin.emailHelp")}
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="location" className="block text-sm font-medium text-stone-200">
            {t("begin.labelLocation")}
          </label>
          <input
            id="location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder={t("begin.placeholderLocation")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-medium text-stone-200">
            {t("begin.labelRoles")}
          </label>
          <p className="text-xs text-muted-foreground italic">
            {t("begin.rolesHelp")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {ROLE_IDS.map((id) => (
              <label
                key={id}
                className="flex items-center gap-2 rounded-md border border-border/30 bg-card/20 px-3 py-2 cursor-pointer hover:bg-card/40 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={resonantRoles.includes(id)}
                  onChange={() => toggleRole(id)}
                  className="accent-amber-500"
                />
                <span className="text-sm text-stone-200">
                  {t(`begin.roles.${id}`)}
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="skills" className="block text-sm font-medium text-stone-200">
            {t("begin.labelSkills")}
          </label>
          <textarea
            id="skills"
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            rows={3}
            placeholder={t("begin.placeholderSkills")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="offering" className="block text-sm font-medium text-stone-200">
            {t("begin.labelOffering")}
          </label>
          <textarea
            id="offering"
            value={offering}
            onChange={(e) => setOffering(e.target.value)}
            rows={3}
            placeholder={t("begin.placeholderOffering")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
          <p className="text-xs text-muted-foreground italic">
            {renderProse(t("begin.offeringHelp"))}
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="message" className="block text-sm font-medium text-stone-200">
            {t("begin.labelMessage")}
          </label>
          <textarea
            id="message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            placeholder={t("begin.placeholderMessage")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        {error ? (
          <div className="rounded-md border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        ) : null}

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-6 py-3 transition-colors"
          >
            {submitting ? t("begin.submitBtnSubmitting") : t("begin.submitBtn")}
          </button>
          <Link href="/with-us" className="text-sm text-muted-foreground hover:text-amber-400">
            {t("begin.readFirst")}
          </Link>
        </div>

        <p className="text-xs text-muted-foreground italic pt-2">
          {renderProse(t("begin.finePrint"))}
        </p>
      </form>
    </main>
  );
}
