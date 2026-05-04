"use client";

// /share — register a service, belonging, space, or skill into the body's
// graph. Posts to /api/offerings (offerings.py). Each offering becomes a
// node the constellation can find by resonance.

import { useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { readIdentity } from "@/lib/identity";

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

const KINDS: { id: Kind; label: string; example: string }[] = [
  { id: "service", label: "A service", example: "rides, healing, teaching, repair, cooking, hosting" },
  { id: "belonging", label: "A belonging", example: "an instrument, a tool, a vehicle, a book" },
  { id: "space", label: "A space", example: "a bed, a retreat hut, a market spot, a garden" },
  { id: "skill", label: "A skill", example: "expertise others can learn from or hire" },
];

const EXCHANGES: { id: Exchange; label: string; hint: string }[] = [
  { id: "gift", label: "Gift", hint: "Freely given. The body gives back when it can." },
  { id: "exchange", label: "Direct exchange", hint: "I want something specific in return — described in terms below." },
  { id: "subscription", label: "Subscription", hint: "Ongoing relationship — weekly bread, monthly tune-up, annual retreat." },
  { id: "by-resonance", label: "By resonance", hint: "Whatever feels right when both cells meet at the exchange." },
];

export default function SharePage() {
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
      setError("Give the offering a title (at least 2 characters).");
      return;
    }
    if (!description.trim() || description.trim().length < 10) {
      setError("Describe the offering a little (at least 10 characters).");
      return;
    }
    if (!contactName.trim() || !contactEmail.trim()) {
      setError("A contact name and email lets cells reach you about this.");
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
      setError(
        err instanceof Error
          ? err.message
          : "Something didn't connect. You can also write directly to umuff71@gmail.com."
      );
      setSubmitting(false);
    }
  }

  if (confirmation) {
    return (
      <main className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none">
        <p className="not-prose text-xs uppercase tracking-widest text-amber-400">
          Held in the body
        </p>
        <h1 className="text-3xl font-light tracking-tight">
          Your offering is woven in
        </h1>
        <p className="text-lg text-stone-300 leading-relaxed">
          The body now holds <strong>{confirmation.title}</strong> as part of
          its memory. Cells looking for this kind of {confirmation.kind} will
          find you by resonance.
        </p>
        <div className="not-prose rounded-xl border border-amber-500/30 bg-amber-500/5 p-5 my-6 space-y-1">
          <p className="text-xs uppercase tracking-widest text-amber-400">
            Offering held
          </p>
          <p className="text-base text-stone-100 font-medium">
            {confirmation.title}
          </p>
          <p className="text-sm text-stone-300">
            {confirmation.kind} · {confirmation.exchange}
          </p>
          <p className="text-xs text-muted-foreground font-mono mt-2">
            id: {confirmation.id}
          </p>
        </div>
        <p className="text-base text-stone-300 leading-relaxed">
          You can register more offerings, or sit with the body for a while.
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
            Register another
          </button>
          <Link
            href="/me"
            className="text-sm text-amber-500 hover:text-amber-400"
          >
            Your presence →
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
        Sharing
      </p>
      <h1 className="text-3xl font-light tracking-tight">
        Share what you carry
      </h1>

      <p className="text-lg leading-relaxed text-stone-300">
        Register a service, a belonging, a space, or a skill into the body's
        memory. Cells looking for this kind of thing will find you by
        resonance — not advertising, not algorithms.
      </p>

      <p className="text-sm text-muted-foreground italic">
        New here? <Link href="/begin">Begin</Link> first to weave in as a
        cell, then come back to register specific offerings.
      </p>

      <hr className="border-border/30 my-8" />

      <form onSubmit={handleSubmit} className="not-prose space-y-6">
        <div className="space-y-2">
          <label htmlFor="title" className="block text-sm font-medium text-stone-200">
            Title <span className="text-amber-500">*</span>
          </label>
          <input
            id="title"
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="A short name for this offering"
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-medium text-stone-200">
            What kind of offering? <span className="text-amber-500">*</span>
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {KINDS.map((k) => (
              <label
                key={k.id}
                className={`flex flex-col gap-1 rounded-md border px-3 py-3 cursor-pointer transition-colors ${
                  kind === k.id
                    ? "border-amber-500/60 bg-amber-500/10"
                    : "border-border/30 bg-card/20 hover:bg-card/40"
                }`}
              >
                <div className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="kind"
                    checked={kind === k.id}
                    onChange={() => setKind(k.id)}
                    className="accent-amber-500"
                  />
                  <span className="text-sm font-medium text-stone-200">
                    {k.label}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground italic ml-6">
                  e.g. {k.example}
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="description" className="block text-sm font-medium text-stone-200">
            Description <span className="text-amber-500">*</span>
          </label>
          <textarea
            id="description"
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={5}
            placeholder="Describe what you're offering in your own words — what it is, what it isn't, how it lives."
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="location" className="block text-sm font-medium text-stone-200">
            Where it lives
          </label>
          <input
            id="location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="A city, a region, 'remote', or 'wherever the body is'"
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-medium text-stone-200">
            How does it move?
          </label>
          <div className="space-y-2">
            {EXCHANGES.map((x) => (
              <label
                key={x.id}
                className={`flex items-start gap-2 rounded-md border px-3 py-2 cursor-pointer transition-colors ${
                  exchange === x.id
                    ? "border-amber-500/60 bg-amber-500/10"
                    : "border-border/30 bg-card/20 hover:bg-card/40"
                }`}
              >
                <input
                  type="radio"
                  name="exchange"
                  checked={exchange === x.id}
                  onChange={() => setExchange(x.id)}
                  className="mt-1 accent-amber-500"
                />
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-stone-200">
                    {x.label}
                  </span>
                  <span className="text-xs text-muted-foreground italic">
                    {x.hint}
                  </span>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="terms" className="block text-sm font-medium text-stone-200">
            Terms (optional)
          </label>
          <textarea
            id="terms"
            value={terms}
            onChange={(e) => setTerms(e.target.value)}
            rows={3}
            placeholder="Pricing, availability, limits, anything that helps cells know if it fits."
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="contact_name" className="block text-sm font-medium text-stone-200">
              Contact name <span className="text-amber-500">*</span>
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
              Contact email <span className="text-amber-500">*</span>
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
            Image URLs (optional, one per line)
          </label>
          <textarea
            id="image_urls"
            value={imageUrls}
            onChange={(e) => setImageUrls(e.target.value)}
            rows={3}
            placeholder="https://… (one URL per line, up to 10)"
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
            {submitting ? "Weaving in…" : "Share with the body"}
          </button>
          <Link href="/with-us" className="text-sm text-muted-foreground hover:text-amber-400">
            ← Read more
          </Link>
        </div>
      </form>
    </main>
  );
}
