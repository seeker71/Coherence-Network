"use client";

// /begin — the warm entry into the body. A simple form, not a multi-step
// onboarding. The visitor writes who they are and what they carry; the body
// receives them and lands them on /arrival/{id} as a held cell.

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { L } from "@/components/inline-link";
import { getApiBase } from "@/lib/api";
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

const RESONANT_ROLES = [
  { id: "land-steward", label: "Land · stewardship" },
  { id: "builder-maker", label: "Builder · maker · craftsperson" },
  { id: "healer", label: "Healer · bodyworker · therapist" },
  { id: "teacher", label: "Teacher · guide · facilitator" },
  { id: "musician-artist", label: "Musician · artist · creator" },
  { id: "farmer-gardener", label: "Farmer · gardener · grower" },
  { id: "cook-baker", label: "Cook · baker · food-tender" },
  { id: "engineer-coder", label: "Engineer · coder · systems" },
  { id: "writer-translator", label: "Writer · translator" },
  { id: "host-keeper", label: "Host · space-keeper" },
  { id: "transport-mechanic", label: "Transport · mechanic" },
  { id: "elder-witness", label: "Elder · witness" },
  { id: "other", label: "Other (in your own words below)" },
];

export default function BeginPage() {
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
      setError("A name lets the body know who's arriving.");
      return;
    }
    if (!email.trim()) {
      setError("An email lets the body reach back.");
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
        err instanceof Error
          ? err.message
          : "Something didn't connect. You can also write directly to urs at umuff71@gmail.com."
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
        Weaving in
      </p>
      <h1 className="text-3xl font-light tracking-tight">Begin</h1>

      <p className="text-lg leading-relaxed text-stone-300">
        Tell the body who's arriving. None of this is required to be exact —
        you can update any of it later. Just enough that the body knows who
        you are and how to reach back. If you'd like to read the slowest
        welcome first, <Link href="/come-in" className="text-amber-400 hover:text-amber-300">/come-in</Link>{" "}
        speaks plainly to any human or AI; the long contemplation lives at{" "}
        <Link href="/one-sheet" className="text-amber-400 hover:text-amber-300">/one-sheet</Link>.
      </p>

      <p className="text-sm text-muted-foreground italic">
        If writing a form isn't your way, write directly to{" "}
        <a
          href="mailto:umuff71@gmail.com"
          className="text-amber-400 hover:text-amber-300"
        >
          umuff71@gmail.com
        </a>
        . Both paths land you in the same body. The personal ground this
        body has grown from is held at{" "}
        <Link href="/silence" className="text-amber-400 hover:text-amber-300">/silence</Link>.
      </p>

      <hr className="border-border/30 my-8" />

      <form onSubmit={handleSubmit} className="not-prose space-y-6">
        <div className="space-y-2">
          <label htmlFor="author_name" className="block text-sm font-medium text-stone-200">
            Your name <span className="text-amber-500">*</span>
          </label>
          <input
            id="author_name"
            type="text"
            required
            value={authorName}
            onChange={(e) => setAuthorName(e.target.value)}
            placeholder="The name you'd like the body to know you by"
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="email" className="block text-sm font-medium text-stone-200">
            Email <span className="text-amber-500">*</span>
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@somewhere.earth"
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
          <p className="text-xs text-muted-foreground italic">
            Not shared publicly. The body reaches back through this.
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="location" className="block text-sm font-medium text-stone-200">
            Where you are
          </label>
          <input
            id="location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="City, region, or 'wherever the body is'"
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-3">
          <label className="block text-sm font-medium text-stone-200">
            What kind of cell are you?
          </label>
          <p className="text-xs text-muted-foreground italic">
            Pick whatever resonates. None is fine. Many is fine.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {RESONANT_ROLES.map((opt) => (
              <label
                key={opt.id}
                className="flex items-center gap-2 rounded-md border border-border/30 bg-card/20 px-3 py-2 cursor-pointer hover:bg-card/40 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={resonantRoles.includes(opt.id)}
                  onChange={() => toggleRole(opt.id)}
                  className="accent-amber-500"
                />
                <span className="text-sm text-stone-200">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="skills" className="block text-sm font-medium text-stone-200">
            What you bring
          </label>
          <textarea
            id="skills"
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            rows={3}
            placeholder="A few words about what your hands, voice, and heart already know how to do."
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="offering" className="block text-sm font-medium text-stone-200">
            What you'd offer
          </label>
          <textarea
            id="offering"
            value={offering}
            onChange={(e) => setOffering(e.target.value)}
            rows={3}
            placeholder="A service, a presence, a thing to share, a space, a skill — in your own words."
            className="w-full rounded-md border border-border/40 bg-card/30 px-3 py-2 text-stone-200 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
          <p className="text-xs text-muted-foreground italic">
            You can register specific offerings later at <L href="/share">/share</L>.
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="message" className="block text-sm font-medium text-stone-200">
            Anything you want the body to know
          </label>
          <textarea
            id="message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            placeholder="What's calling. Who pointed you. What you'd love to find. What you're ready to leave behind."
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
            {submitting ? "Weaving in…" : "Weave in"}
          </button>
          <Link href="/with-us" className="text-sm text-muted-foreground hover:text-amber-400">
            ← Read first
          </Link>
        </div>

        <p className="text-xs text-muted-foreground italic pt-2">
          By weaving in you're saying yes to being part of{" "}
          <Link href="/vision/lc-network" className="text-amber-500 hover:text-amber-400">the body</Link>.
          The network reaches back with care, not noise. You keep
          sovereignty over what you share, and you can ask to be removed
          at any time. After landing you'll see your{" "}
          <Link href="/me/work" className="text-amber-500 hover:text-amber-400">body of work</Link>{" "}
          page — empty at first, filling as you contribute. For full
          crypto-key sovereignty (ed25519 keypair, advanced), use{" "}
          <Link href="/join" className="text-amber-500 hover:text-amber-400">/join</Link>{" "}
          instead. To register specific offerings, services, or spaces
          right away, <Link href="/share" className="text-amber-500 hover:text-amber-400">/share</Link>{" "}
          is the dedicated surface.
        </p>
      </form>
    </main>
  );
}
