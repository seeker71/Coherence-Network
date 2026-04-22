"use client";

import { useState } from "react";
import Link from "next/link";
import { useT } from "@/components/MessagesProvider";
import {
  CONTRIBUTOR_KEY,
  NAME_KEY,
  FINGERPRINT_KEY,
} from "@/lib/identity";

type KeypairData = { public_key_hex: string; private_key_hex: string; fingerprint: string; algorithm: string };

export function ContributorSetup() {
  const t = useT();
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<"generate" | "bring" | "wallet" | null>(null);
  const [contributorId, setContributorId] = useState("");
  const [keypair, setKeypair] = useState<KeypairData | null>(null);
  const [ownPublicKey, setOwnPublicKey] = useState("");
  const [registered, setRegistered] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [privateSaved, setPrivateSaved] = useState(false);

  const generateKeypair = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/contributors/generate-keypair", { method: "POST" });
      if (!r.ok) throw new Error(t("join.failGenerate"));
      const data = await r.json();
      setKeypair(data);
      setStep(2);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("join.errorGenerating"));
    } finally {
      setLoading(false);
    }
  };

  const registerKey = async () => {
    if (!contributorId.trim() || !keypair) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`/api/contributors/${contributorId.trim()}/register-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_key_hex: keypair.public_key_hex }),
      });
      if (!r.ok) throw new Error(t("join.failRegister"));
      const data = await r.json();
      if (data.registered) {
        setRegistered(true);
        const id = contributorId.trim();
        // Legacy crypto-flow keys — kept so existing code paths
        // (wallet connect, idea submit, treasury deposit, stake,
        // identity page) that read coherence_* continue to find
        // the visitor.
        localStorage.setItem("coherence_contributor_id", id);
        localStorage.setItem("coherence_public_key", keypair.public_key_hex);
        localStorage.setItem("coherence_fingerprint", keypair.fingerprint);
        // Unified cc-* keys — MeButton, MePage, ReactionBar,
        // ProposeForm, and every other presence-aware surface reads
        // from these. Writing them here means a visitor who joined
        // via the crypto flow is recognized in the 'You' corner
        // immediately, not forgotten on the next page load.
        localStorage.setItem(CONTRIBUTOR_KEY, id);
        localStorage.setItem(NAME_KEY, id);
        localStorage.setItem(FINGERPRINT_KEY, keypair.fingerprint);
        setStep(4);
      } else {
        throw new Error(data.error || t("join.failRegister"));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("join.errorRegistering"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Step 1: Generate Identity */}
      <section className={`rounded-2xl border p-6 space-y-4 transition-all ${
        step === 1 ? "border-amber-500/30 bg-amber-900/5" : step > 1 ? "border-emerald-800/20 bg-emerald-900/5 opacity-70" : "border-stone-800/40 bg-stone-900/30 opacity-50"
      }`}>
        <div className="flex items-center gap-3">
          <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
            step > 1 ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
          }`}>{step > 1 ? "\u2713" : "1"}</span>
          <h2 className="text-lg font-light text-stone-300">{t("join.step1Title")}</h2>
        </div>

        {step === 1 && (
          <>
            <p className="text-sm text-stone-400 leading-relaxed">
              {t("join.step1Body")}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => { setMode("generate"); generateKeypair(); }}
                disabled={loading}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40"
              >
                {loading ? t("join.step1Generating") : t("join.step1Generate")}
              </button>
              <button
                onClick={() => { setMode("bring"); setStep(2); }}
                className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm"
              >
                {t("join.step1HaveKey")}
              </button>
              <button
                onClick={() => { setMode("wallet"); setStep(2); }}
                className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm"
              >
                {t("join.step1UseWallet")}
              </button>
            </div>
            <p className="text-xs text-stone-600">
              {t("join.step1Footnote")}
            </p>
          </>
        )}
        {step > 1 && keypair && (
          <p className="text-xs text-emerald-400/60">{t("join.step1Ready", { fingerprint: keypair.fingerprint })}</p>
        )}
      </section>

      {/* Step 2: Save Private Key */}
      {step >= 2 && (
        <section className={`rounded-2xl border p-6 space-y-4 transition-all ${
          step === 2 ? "border-amber-500/30 bg-amber-900/5" : step > 2 ? "border-emerald-800/20 bg-emerald-900/5 opacity-70" : "border-stone-800/40"
        }`}>
          <div className="flex items-center gap-3">
            <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step > 2 ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
            }`}>{step > 2 ? "\u2713" : "2"}</span>
            <h2 className="text-lg font-light text-stone-300">{t("join.step2Title")}</h2>
          </div>

          {step === 2 && mode === "generate" && keypair && (
            <>
              <div className="rounded-xl border border-red-800/20 bg-red-900/5 p-4 space-y-2">
                <p className="text-xs text-red-300/80 font-medium">{t("join.step2ShownOnce")}</p>
                <code className="block text-xs text-stone-300 font-mono break-all bg-stone-900/50 p-3 rounded-lg select-all">
                  {keypair.private_key_hex}
                </code>
              </div>
              <div className="space-y-2">
                <p className="text-xs text-stone-500">{t("join.step2PublicLabel")}</p>
                <code className="block text-xs text-amber-400/50 font-mono break-all bg-stone-900/30 p-2 rounded-lg">
                  {keypair.public_key_hex}
                </code>
              </div>
              <label className="flex items-center gap-2 text-sm text-stone-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={privateSaved}
                  onChange={(e) => setPrivateSaved(e.target.checked)}
                  className="rounded border-stone-700"
                />
                {t("join.step2Confirm")}
              </label>
              <button
                onClick={() => setStep(3)}
                disabled={!privateSaved}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t("join.step2Continue")}
              </button>
            </>
          )}
          {step === 2 && mode === "wallet" && (
            <>
              <p className="text-sm text-stone-400">
                {t("join.step2WalletBody")}
              </p>
              <input
                value={ownPublicKey}
                onChange={(e) => setOwnPublicKey(e.target.value.replace(/\s/g, ""))}
                placeholder={t("join.step2WalletPlaceholder")}
                className="w-full px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 font-mono focus:outline-none focus:border-amber-500/30"
              />
              <div className="text-xs text-stone-600 space-y-1">
                <p>{t("join.step2WalletHelp1")}</p>
                <p>{t("join.step2WalletHelp2")}</p>
              </div>
              <button
                onClick={() => {
                  const addr = ownPublicKey.startsWith("0x") ? ownPublicKey : `0x${ownPublicKey}`;
                  setKeypair({ public_key_hex: addr, private_key_hex: "", fingerprint: addr.slice(2, 10), algorithm: "EVM-wallet" });
                  setStep(3);
                }}
                disabled={ownPublicKey.length < 10}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t("join.step2UseWallet")}
              </button>
            </>
          )}
          {step === 2 && mode === "bring" && (
            <>
              <p className="text-sm text-stone-400">
                {t("join.step2BringBody")}
              </p>
              <input
                value={ownPublicKey}
                onChange={(e) => setOwnPublicKey(e.target.value.replace(/\s/g, ""))}
                placeholder={t("join.step2BringPlaceholder")}
                className="w-full px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 font-mono focus:outline-none focus:border-amber-500/30"
              />
              <button
                onClick={() => {
                  setKeypair({ public_key_hex: ownPublicKey, private_key_hex: "", fingerprint: ownPublicKey.slice(0, 16), algorithm: "Ed25519-external" });
                  setStep(3);
                }}
                disabled={ownPublicKey.length < 32}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {t("join.step2UseKey")}
              </button>
            </>
          )}
        </section>
      )}

      {/* Step 3: Choose Name */}
      {step >= 3 && (
        <section className={`rounded-2xl border p-6 space-y-4 transition-all ${
          step === 3 ? "border-amber-500/30 bg-amber-900/5" : step > 3 ? "border-emerald-800/20 bg-emerald-900/5 opacity-70" : "border-stone-800/40"
        }`}>
          <div className="flex items-center gap-3">
            <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step > 3 ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
            }`}>{step > 3 ? "\u2713" : "3"}</span>
            <h2 className="text-lg font-light text-stone-300">{t("join.step3Title")}</h2>
          </div>

          {step === 3 && (
            <>
              <p className="text-sm text-stone-400">{t("join.step3Body")}</p>
              <div className="flex gap-2">
                <input
                  value={contributorId}
                  onChange={(e) => setContributorId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  placeholder={t("join.step3Placeholder")}
                  className="flex-1 px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 focus:outline-none focus:border-amber-500/30"
                />
                <button
                  onClick={registerKey}
                  disabled={loading || !contributorId.trim()}
                  className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40"
                >
                  {loading ? t("join.step3Registering") : t("join.step3Register")}
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {/* Step 4: Done */}
      {step >= 4 && registered && (
        <section className="rounded-2xl border border-emerald-800/20 bg-emerald-900/5 p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium bg-emerald-500/20 text-emerald-300">{"\u2713"}</span>
            <h2 className="text-lg font-light text-emerald-300">{t("join.step4Title")}</h2>
          </div>

          <div className="space-y-2 text-sm text-stone-400">
            <div>{t("join.step4ContributorLabel")} <span className="text-stone-300 font-medium">{contributorId}</span></div>
            <div>{t("join.step4FingerprintLabel")} <span className="text-amber-400/60 font-mono">{keypair?.fingerprint}</span></div>
            <div>{t("join.step4PublicKeyLabel")} <span className="text-amber-400/40 font-mono text-xs">{keypair?.public_key_hex.slice(0, 24)}...</span></div>
          </div>

          <div className="space-y-3 pt-4 border-t border-stone-800/20">
            <p className="text-sm text-stone-300 font-medium">{t("join.step4Heading")}</p>
            <div className="space-y-2 text-sm text-stone-400">
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>{t("join.step4Point1")}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>{t("join.step4Point2")}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>{t("join.step4Point3")}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>{t("join.step4Point4")}</span>
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <Link href="/vision/economy"
              className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium">
              {t("join.step4ExploreEconomy")}
            </Link>
            <Link href="/vision"
              className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm">
              {t("join.step4BrowseConcepts")}
            </Link>
            <Link href="/verify"
              className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm">
              {t("join.step4VerifyMath")}
            </Link>
          </div>

          <p className="text-xs text-stone-600 pt-2">
            {t("join.step4VerifyHint")} <code className="text-amber-400/40">/api/contributors/{contributorId}/public-key</code>
          </p>
        </section>
      )}

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}
    </div>
  );
}
