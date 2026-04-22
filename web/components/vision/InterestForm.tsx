"use client";

import { useState } from "react";
import { useT, useLocale } from "@/components/MessagesProvider";
import { LOCALES, type LocaleCode } from "@/lib/locales";
import {
  NAME_KEY,
  CONTRIBUTOR_KEY,
  EMAIL_KEY,
  ensureFingerprint,
} from "@/lib/identity";

type RoleKey =
  | "livingStructureWeaver"
  | "nourishmentAlchemist"
  | "frequencyHolder"
  | "vitalityKeeper"
  | "transmissionSource"
  | "formGrower";

// Slugs sent to the API stay English-slug-stable across languages.
const ROLES: { key: RoleKey; slug: string }[] = [
  { key: "livingStructureWeaver", slug: "living-structure-weaver" },
  { key: "nourishmentAlchemist", slug: "nourishment-alchemist" },
  { key: "frequencyHolder", slug: "frequency-holder" },
  { key: "vitalityKeeper", slug: "vitality-keeper" },
  { key: "transmissionSource", slug: "transmission-source" },
  { key: "formGrower", slug: "form-grower" },
];

type FormState = {
  name: string;
  email: string;
  location: string;
  skills: string;
  offering: string;
  resonant_roles: string[];
  message: string;
  locale: LocaleCode;
  consent_share_name: boolean;
  consent_share_location: boolean;
  consent_share_skills: boolean;
  consent_findable: boolean;
  consent_email_updates: boolean;
};

function initialState(detected: LocaleCode): FormState {
  return {
    name: "",
    email: "",
    location: "",
    skills: "",
    offering: "",
    resonant_roles: [],
    message: "",
    locale: detected,
    consent_share_name: false,
    consent_share_location: false,
    consent_share_skills: false,
    consent_findable: false,
    consent_email_updates: false,
  };
}

export function InterestForm() {
  const t = useT();
  const detectedLocale = useLocale() as LocaleCode;
  const [form, setForm] = useState<FormState>(() => initialState(detectedLocale));
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
        const body = await res.text();
        // FastAPI returns plain-text on 5xx; try to extract a JSON
        // detail first, fall back to the status + body prefix.
        let msg = t("interestForm.errorGeneric");
        try {
          const parsed = JSON.parse(body);
          msg = parsed?.detail || msg;
        } catch {
          msg = `HTTP ${res.status}: ${body.slice(0, 120)}`;
        }
        throw new Error(msg);
      }

      // The backend register endpoint returns the interested-person
      // id AND the contributor_id (same email → same contributor on
      // every device the visitor ever opens the app on). Persisting
      // both locally is what makes the 'You' page remember them.
      //
      // Backend is the source of truth for profile + identity;
      // localStorage is a fast cache that can be rebuilt any time
      // via /api/contributors/claim-by-identity on a new device.
      const data = await res.json().catch(() => ({}));
      try {
        const trimmed = form.name.trim();
        const emailTrimmed = form.email.trim();
        if (trimmed) localStorage.setItem(NAME_KEY, trimmed);
        if (emailTrimmed) localStorage.setItem(EMAIL_KEY, emailTrimmed);
        if (data.contributor_id) {
          localStorage.setItem(CONTRIBUTOR_KEY, data.contributor_id);
        }
        ensureFingerprint();
        // Signal other mounted components (the MeButton in the
        // header) that identity changed so they re-read without a
        // manual reload.
        try {
          window.dispatchEvent(new StorageEvent("storage", { key: CONTRIBUTOR_KEY }));
        } catch {
          /* some browsers gate the StorageEvent ctor — non-fatal */
        }
      } catch {
        // localStorage unavailable (private mode, quota): the
        // server already has the contributor + interest node, so
        // the visitor can recover on their next visit by signing in
        // with their email — the backend will return their full
        // profile.
      }

      setSubmitted(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t("interestForm.errorNetwork");
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="text-center space-y-6 py-12">
        <div className="text-5xl">✦</div>
        <h3 className="text-2xl font-light text-amber-300/90">
          {t("interestForm.thanksTitle")}
        </h3>
        <p className="text-stone-400 max-w-md mx-auto leading-relaxed">
          {t("interestForm.thanksBody")}{" "}
          {form.consent_email_updates && t("interestForm.thanksUpdates")}
        </p>
        <button
          onClick={() => { setSubmitted(false); setForm(initialState(detectedLocale)); }}
          className="text-sm text-stone-600 hover:text-stone-400 transition-colors"
        >
          {t("interestForm.registerAgain")}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Your language — pre-filled from the viewer's current locale.
          Always visible so the contributor can correct the guess. */}
      <div className="space-y-2">
        <label className="text-sm text-stone-400">
          {t("interestForm.labelLocale")}
        </label>
        <div className="flex flex-wrap items-center gap-2">
          {LOCALES.map((loc) => {
            const selected = form.locale === loc.code;
            return (
              <button
                key={loc.code}
                type="button"
                onClick={() => setForm({ ...form, locale: loc.code })}
                aria-pressed={selected}
                className={`rounded-full px-3 py-1.5 text-sm border transition-colors ${
                  selected
                    ? "border-amber-500/60 bg-amber-500/10 text-amber-200"
                    : "border-stone-800/60 bg-stone-900/40 text-stone-400 hover:border-stone-700 hover:text-stone-300"
                }`}
              >
                <span className="font-medium uppercase tracking-wider mr-2 text-xs">
                  {loc.code}
                </span>
                {loc.nativeName}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-stone-600 leading-relaxed">
          {t("interestForm.localeHint")}
        </p>
      </div>

      {/* Name + Email */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-sm text-stone-400">{t("interestForm.labelName")}</label>
          <input
            type="text"
            required
            minLength={2}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder={t("interestForm.placeholderName")}
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm text-stone-400">{t("interestForm.labelEmail")}</label>
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder={t("interestForm.placeholderEmail")}
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
      </div>

      {/* Location + Skills */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-sm text-stone-400">{t("interestForm.labelLocation")}</label>
          <input
            type="text"
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            placeholder={t("interestForm.placeholderLocation")}
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm text-stone-400">{t("interestForm.labelSkills")}</label>
          <input
            type="text"
            value={form.skills}
            onChange={(e) => setForm({ ...form, skills: e.target.value })}
            placeholder={t("interestForm.placeholderSkills")}
            className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
          />
        </div>
      </div>

      {/* Roles */}
      <div className="space-y-4">
        <label className="text-sm text-stone-400">{t("interestForm.labelRoles")}</label>
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
                <div className="text-sm font-medium mb-1">
                  {t(`interestForm.roles.${role.key}.name`)}
                </div>
                <div className="text-xs leading-relaxed opacity-70">
                  {t(`interestForm.roles.${role.key}.desc`)}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Offering */}
      <div className="space-y-2">
        <label className="text-sm text-stone-400">{t("interestForm.labelOffering")}</label>
        <textarea
          value={form.offering}
          onChange={(e) => setForm({ ...form, offering: e.target.value })}
          placeholder={t("interestForm.placeholderOffering")}
          rows={3}
          className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all resize-none"
        />
      </div>

      {/* Message */}
      <div className="space-y-2">
        <label className="text-sm text-stone-400">{t("interestForm.labelMessage")}</label>
        <textarea
          value={form.message}
          onChange={(e) => setForm({ ...form, message: e.target.value })}
          placeholder={t("interestForm.placeholderMessage")}
          rows={3}
          className="w-full px-4 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-200 placeholder:text-stone-700 focus:border-amber-500/30 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all resize-none"
        />
      </div>

      {/* Consent */}
      <div className="space-y-4 p-6 rounded-xl border border-stone-800/20 bg-stone-900/10">
        <p className="text-sm text-stone-400 font-medium">
          {t("interestForm.privacyTitle")}
        </p>
        <p className="text-xs text-stone-600 leading-relaxed">
          {t("interestForm.privacyLede")}
        </p>
        <div className="space-y-3">
          {[
            { key: "consent_share_name" as const, labelKey: "interestForm.consentShareName" },
            { key: "consent_share_location" as const, labelKey: "interestForm.consentShareLocation" },
            { key: "consent_share_skills" as const, labelKey: "interestForm.consentShareSkills" },
            { key: "consent_findable" as const, labelKey: "interestForm.consentFindable" },
            { key: "consent_email_updates" as const, labelKey: "interestForm.consentUpdates" },
          ].map((c) => (
            <label key={c.key} className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={form[c.key]}
                onChange={(e) => setForm({ ...form, [c.key]: e.target.checked })}
                className="mt-0.5 rounded border-stone-700 bg-stone-900/60 text-amber-500 focus:ring-amber-500/30 focus:ring-offset-0"
              />
              <span className="text-sm text-stone-500 group-hover:text-stone-400 transition-colors">
                {t(c.labelKey)}
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
          {submitting ? t("interestForm.submitting") : t("interestForm.submit")}
        </button>
      </div>
    </form>
  );
}
