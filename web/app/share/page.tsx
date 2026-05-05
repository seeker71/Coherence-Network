"use client";

// /share — register a service, belonging, space, or skill into the body's
// graph. Posts to /api/offerings (offerings.py). Each offering becomes a
// node the constellation can find by resonance.

import { useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { readIdentity } from "@/lib/identity";
import { useT } from "@/components/MessagesProvider";
import { L } from "@/components/inline-link";

interface OfferingResponse {
  id: string;
  title: string;
  kind: string;
  description: string;
  contact_name: string;
  contact_email: string;
  exchange: string;
}

type Kind = "service" | "belonging" | "space" | "skill";
type Exchange = "gift" | "exchange" | "subscription" | "by-resonance";

const KIND_IDS: Kind[] = ["service", "belonging", "space", "skill"];
const EXCHANGE_IDS: Exchange[] = ["gift", "exchange", "subscription", "by-resonance"];

// Render a translated string carrying inline [label](href) markdown links
// plus optional **bold** runs.
function renderProse(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  // Two passes: first split on links, then within each non-link chunk handle **bold**.
  const linkRe = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  const pushPlain = (chunk: string) => {
    if (!chunk) return;
    const boldRe = /\*\*([^*]+)\*\*/g;
    let li = 0;
    let bm: RegExpExecArray | null;
    while ((bm = boldRe.exec(chunk)) !== null) {
      if (bm.index > li) parts.push(chunk.slice(li, bm.index));
      parts.push(<strong key={`b${key++}`}>{bm[1]}</strong>);
      li = bm.index + bm[0].length;
    }
    if (li < chunk.length) parts.push(chunk.slice(li));
  };
  while ((m = linkRe.exec(text)) !== null) {
    if (m.index > lastIdx) pushPlain(text.slice(lastIdx, m.index));
    const [, label, href] = m;
    parts.push(
      <L key={`l${key++}`} href={href}>
        {label}
      </L>,
    );
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) pushPlain(text.slice(lastIdx));
  return parts;
}

function interp(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) => (vars[k] === undefined ? `{${k}}` : vars[k]));
}

export default function SharePage() {
  const t = useT();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<OfferingResponse | null>(null);

  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<Kind>("service");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [exchange, setExchange] = useState<Exchange>("by-resonance");
  const [terms, setTerms] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [imageUrls, setImageUrls] = useState("");

  // Pre-fill contact from identity if available.
  if (typeof window !== "undefined" && !contactName && !contactEmail) {
    const ident = readIdentity();
    if (ident.name && !contactName) setContactName(ident.name);
    if (ident.email && !contactEmail) setContactEmail(ident.email);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!title.trim() || title.trim().length < 2) {
      setError(t("share.errorTitleRequired"));
      return;
    }
    if (!description.trim() || description.trim().length < 10) {
      setError(t("share.errorDescriptionRequired"));
      return;
    }
    if (!contactName.trim() || !contactEmail.trim()) {
      setError(t("share.errorContactRequired"));
      return;
    }

    setSubmitting(true);
    try {
      const ident = typeof window !== "undefined" ? readIdentity() : null;
      const urls = imageUrls
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean)
        .slice(0, 10);

      const res = await fetch(`${getApiBase()}/api/offerings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          kind,
          description: description.trim(),
          location: location.trim() || null,
          exchange,
          terms: terms.trim() || null,
          contact_name: contactName.trim(),
          contact_email: contactEmail.trim(),
          image_urls: urls,
          contributor_id: ident?.contributorId || null,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`Server returned ${res.status}: ${body.slice(0, 180)}`);
      }
      const data = (await res.json()) as OfferingResponse;
      setConfirmation(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("share.errorGeneric"));
      setSubmitting(false);
    }
  }

  if (confirmation) {
    return (
      <main className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none">
        <p className="not-prose text-xs uppercase tracking-widest text-amber-400">
          {t("share.confirmEyebrow")}
        </p>
        <h1 className="text-3xl font-light tracking-tight">{t("share.confirmH1")}</h1>
        <p className="text-lg text-stone-300 leading-relaxed">
          {renderProse(
            interp(t("share.confirmBodyTemplate"), {
              title: confirmation.title,
              kind: confirmation.kind,
            }),
          )}
        </p>
        <div className="not-prose rounded-xl border border-amber-500/30 bg-amber-500/5 p-5 my-6 space-y-1">
          <p className="text-xs uppercase tracking-widest text-amber-400">
            {t("share.offeringHeldEyebrow")}
          </p>
          <p className="text-base text-stone-100 font-medium">
            {confirmation.title}
          </p>
          <p className="text-sm text-stone-300">
            {confirmation.kind} · {confirmation.exchange}
          </p>
          <p className="text-xs text-muted-foreground font-mono mt-2">
            {t("share.idLabel")} {confirmation.id}
          </p>
        </div>
        <p className="text-base text-stone-300 leading-relaxed">
          {renderProse(t("share.confirmAfter"))}
        </p>
        <div className="not-prose flex items-center gap-4 mt-6">
          <button
            type="button"
            onClick={() => {
              setConfirmation(null);
              setTitle("");
              setDescription("");
              setLocation("");
              setTerms("");
              setImageUrls("");
              setSubmitting(false);
            }}
            className="rounded-md bg-amber-600 hover:bg-amber-500 text-white font-medium px-5 py-2.5 transition-colors text-sm"
          >
            {t("share.registerAnother")}
          </button>
          <Link href="/me" className="text-sm text-amber-500 hover:text-amber-400">
            {t("share.yourPresence")}
          </Link>
          <Link href="/with-us" className="text-sm text-amber-500 hover:text-amber-400">
            {t("share.howWeaveIn")}
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main
      id="main-content"
      className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none"
    >
      <p className="not-prose text-xs uppercase tracking-widest text-muted-foreground">
        {t("share.eyebrow")}
      </p>
      <h1 className="text-3xl font-light tracking-tight">{t("share.h1")}</h1>

      <p className="text-lg leading-relaxed text-stone-300">
        {renderProse(t("share.intro"))}
      </p>

      <p className="text-sm text-muted-foreground italic">
        {renderProse(t("share.newHere"))}
      </p>

      <hr className="border-border/30 my-8" />

      <form onSubmit={handleSubmit} className="not-prose space-y-6">
        <div className="space-y-2">
          <label htmlFor="title" className="block text-sm font-medium text-stone-200">
            {t("share.labelTitle")} <span className="text-amber-500">*</span>
          </label>
          <input
            id="title"
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("share.placeholderTitle")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-medium text-stone-200">
            {t("share.labelKind")} <span className="text-amber-500">*</span>
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {KIND_IDS.map((k) => (
              <label
                key={k}
                className={`flex flex-col gap-1 rounded-md border px-3 py-3 cursor-pointer transition-colors ${
                  kind === k
                    ? "border-amber-500/60 bg-amber-500/10"
                    : "border-border/30 bg-card/20 hover:bg-card/40"
                }`}
              >
                <div className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="kind"
                    checked={kind === k}
                    onChange={() => setKind(k)}
                    className="accent-amber-500"
                  />
                  <span className="text-sm font-medium text-stone-200">
                    {t(`share.kinds.${k}.label`)}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground italic ml-6">
                  {t("share.kindExamplePrefix")} {t(`share.kinds.${k}.example`)}
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="description" className="block text-sm font-medium text-stone-200">
            {t("share.labelDescription")} <span className="text-amber-500">*</span>
          </label>
          <textarea
            id="description"
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={5}
            placeholder={t("share.placeholderDescription")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="location" className="block text-sm font-medium text-stone-200">
            {t("share.labelLocation")}
          </label>
          <input
            id="location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder={t("share.placeholderLocation")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-medium text-stone-200">
            {t("share.labelExchange")}
          </label>
          <div className="space-y-2">
            {EXCHANGE_IDS.map((x) => (
              <label
                key={x}
                className={`flex items-start gap-2 rounded-md border px-3 py-2 cursor-pointer transition-colors ${
                  exchange === x
                    ? "border-amber-500/60 bg-amber-500/10"
                    : "border-border/30 bg-card/20 hover:bg-card/40"
                }`}
              >
                <input
                  type="radio"
                  name="exchange"
                  checked={exchange === x}
                  onChange={() => setExchange(x)}
                  className="mt-1 accent-amber-500"
                />
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-stone-200">
                    {t(`share.exchanges.${x}.label`)}
                  </span>
                  <span className="text-xs text-muted-foreground italic">
                    {t(`share.exchanges.${x}.hint`)}
                  </span>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="terms" className="block text-sm font-medium text-stone-200">
            {t("share.labelTerms")}
          </label>
          <textarea
            id="terms"
            value={terms}
            onChange={(e) => setTerms(e.target.value)}
            rows={3}
            placeholder={t("share.placeholderTerms")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="contact_name" className="block text-sm font-medium text-stone-200">
              {t("share.labelContactName")} <span className="text-amber-500">*</span>
            </label>
            <input
              id="contact_name"
              type="text"
              required
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="contact_email" className="block text-sm font-medium text-stone-200">
              {t("share.labelContactEmail")} <span className="text-amber-500">*</span>
            </label>
            <input
              id="contact_email"
              type="email"
              required
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
            />
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="image_urls" className="block text-sm font-medium text-stone-200">
            {t("share.labelImageUrls")}
          </label>
          <textarea
            id="image_urls"
            value={imageUrls}
            onChange={(e) => setImageUrls(e.target.value)}
            rows={3}
            placeholder={t("share.placeholderImageUrls")}
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40 font-mono text-sm"
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
            {submitting ? t("share.submitBtnSubmitting") : t("share.submitBtn")}
          </button>
          <Link href="/with-us" className="text-sm text-muted-foreground hover:text-amber-400">
            {t("share.readMore")}
          </Link>
        </div>
      </form>
    </main>
  );
}
