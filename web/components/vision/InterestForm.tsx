"use client";

import { useState } from "react";

type Role = {
  slug: string;
  name: string;
  description: string;
};

const ROLES: Role[] = [
  { slug: "living-structure-weaver", name: "Living-structure weaver", description: "Architects, builders, earthship enthusiasts, cob practitioners, bamboo growers" },
  { slug: "nourishment-alchemist", name: "Nourishment alchemist", description: "Permaculturists, fermentation practitioners, food foresters, communal cooks" },
  { slug: "frequency-holder", name: "Frequency holder", description: "Musicians, sound healers, voice practitioners, silence holders" },
  { slug: "vitality-keeper", name: "Vitality keeper", description: "Bodyworkers, movement facilitators, nature immersion guides, breathwork practitioners" },
  { slug: "transmission-source", name: "Transmission source", description: "Experienced community builders, facilitators, elders of any tradition that resonates" },
  { slug: "form-grower", name: "Form-grower", description: "Earth workers, timber framers, stone masons, hands that shape space that breathes" },
];

type FormState = {
  name: string;
  email: string;
  location: string;
  skills: string;
  offering: string;
  resonant_roles: string[];
  message: string;
  consent_share_name: boolean;
  consent_share_location: boolean;
  consent_share_skills: boolean;
  consent_findable: boolean;
  consent_email_updates: boolean;
};

const INITIAL: FormState = {
  name: "",
  email: "",
  location: "",
  skills: "",
  offering: "",
  resonant_roles: [],
  message: "",
  consent_share_name: false,
  consent_share_location: false,
  consent_share_skills: false,
  consent_findable: false,
  consent_email_updates: false,
};

export function InterestForm() {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const toggleRole = (slug: string) => {
    setForm((f) => ({
      ...f,
      resonant_roles: f.resonant_roles.includes(slug)
        ? f.resonant_roles.filter((r) => r !== slug)
        : [...f.resonant_roles, slug],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const res = await fetch("/api/interest/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Something went wrong. Please try again.");
      }

      setSubmitted(true);
    } catch (err: any) {
      setError(err.message || "Connection error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="text-center space-y-6 py-12">
        <div className="text-5xl">✦</div>
        <h3 className="text-2xl font-light text-amber-300/90">
          The field feels you
        </h3>
        <p className="text-stone-400 max-w-md mx-auto leading-relaxed">
          Your resonance has been registered. You are now part of the forming
          field. {form.consent_email_updates && "We'll keep you in the flow as things emerge."}
        </p>
        <button
          onClick={() => { setSubmitted(false); setForm(INITIAL); }}
          className="text-sm text-stone-600 hover:text-stone-400 transition-colors"
        >
          Register another soul
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Name + Email */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-sm text-stone-400">Your name *</label>
          <input
            type="text"
            required
            minLength={2}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="How the field knows you"
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm text-stone-400">Email *</label>
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Never shared without your consent"
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
      </div>

      {/* Location + Skills */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-sm text-stone-400">Where are you?</label>
          <input
            type="text"
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            placeholder="City, region, or just the continent"
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm text-stone-400">What do you bring?</label>
          <input
            type="text"
            value={form.skills}
            onChange={(e) => setForm({ ...form, skills: e.target.value })}
            placeholder="Skills, materials, ideas, energy, land..."
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
      </div>

      {/* Roles */}
      <div className="space-y-4">
        <label className="text-sm text-stone-400">Which roles call to you?</label>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {ROLES.map((role) => {
            const selected = form.resonant_roles.includes(role.slug);
            return (
              <button
                key={role.slug}
                type="button"
                onClick={() => toggleRole(role.slug)}
                className={`p-4 rounded-xl border text-left transition-all duration-300 ${
                  selected
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-300/90"
                    : "border-stone-800/30 bg-stone-900/20 text-stone-500 hover:border-stone-700/40 hover:text-stone-400"
                }`}
              >
                <div className="text-sm font-medium mb-1">{role.name}</div>
                <div className="text-xs leading-relaxed opacity-70">{role.description}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Offering */}
      <div className="space-y-2">
        <label className="text-sm text-stone-400">How do you want to contribute?</label>
        <textarea
          value={form.offering}
          onChange={(e) => setForm({ ...form, offering: e.target.value })}
          placeholder="Time, land, resources, specific skills, funding, simply holding space... anything that feels right"
          rows={3}
          className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all resize-none"
        />
      </div>

      {/* Message */}
      <div className="space-y-2">
        <label className="text-sm text-stone-400">A message from your heart</label>
        <textarea
          value={form.message}
          onChange={(e) => setForm({ ...form, message: e.target.value })}
          placeholder="What draws you? What do you feel? What do you envision?"
          rows={3}
          className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all resize-none"
        />
      </div>

      {/* Consent */}
      <div className="space-y-4 p-6 rounded-xl border border-stone-800/20 bg-stone-900/10">
        <p className="text-sm text-stone-400 font-medium">Your privacy, your choice</p>
        <p className="text-xs text-stone-600 leading-relaxed">
          Your email is never shared. Everything else is opt-in.
          Choose what you're comfortable sharing with other people who are also gathering.
        </p>
        <div className="space-y-3">
          {[
            { key: "consent_share_name" as const, label: "Show my name to other interested people" },
            { key: "consent_share_location" as const, label: "Show my general location" },
            { key: "consent_share_skills" as const, label: "Show what I bring" },
            { key: "consent_findable" as const, label: "Appear in the community directory" },
            { key: "consent_email_updates" as const, label: "Keep me updated on progress" },
          ].map((c) => (
            <label key={c.key} className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={form[c.key]}
                onChange={(e) => setForm({ ...form, [c.key]: e.target.checked })}
                className="mt-0.5 rounded border-stone-700 bg-stone-900/60 text-amber-500 focus:ring-amber-500/30 focus:ring-offset-0"
              />
              <span className="text-sm text-stone-500 group-hover:text-stone-400 transition-colors">
                {c.label}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Submit */}
      <div className="text-center">
        <button
          type="submit"
          disabled={submitting}
          className="px-10 py-4 rounded-xl bg-gradient-to-r from-amber-500/20 via-teal-500/20 to-violet-500/20 border border-amber-500/20 text-amber-300/90 hover:from-amber-500/30 hover:via-teal-500/30 hover:to-violet-500/30 hover:border-amber-500/30 transition-all duration-500 font-medium text-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Sending your resonance..." : "I feel it. I'm in."}
        </button>
      </div>
    </form>
  );
}
