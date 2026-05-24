"use client";

// MeAliasesClient — interactive surface for the contributor's pubkey claim,
// alias listing, and rotation flow. All ed25519 key generation and signing
// happens in the browser via @noble/ed25519; the private key is shown once
// and never transmitted.

import { useCallback, useEffect, useMemo, useState } from "react";
import * as ed from "@noble/ed25519";

import { readIdentity, CONTRIBUTOR_KEY } from "@/lib/identity";

// @noble/ed25519 v3's async API (signAsync / getPublicKeyAsync) uses
// WebCrypto's SubtleCrypto for SHA-512 by default. We only need to wire
// up a sync sha512 if we ever call ed.sign / ed.getPublicKey synchronously,
// which we don't. So no extra dependency on @noble/hashes here.

type Alias = {
  peer_instance_id: string;
  peer_contributor_id: string;
  public_key_hex: string;
  recognized_at: string | null;
  signature_verified: boolean;
};

type AliasesResponse = {
  contributor_id: string;
  aliases: Alias[];
};

type ClaimPayload = {
  contributor_id: string;
  public_key_hex: string;
  issued_at: string;
  rotates_from?: string;
};

type Labels = {
  contributorIdLabel: string;
  contributorIdPlaceholder: string;
  contributorIdHelp: string;
  loading: string;
  noPubkey: string;
  yourPubkey: string;
  generateClaim: string;
  generating: string;
  claimSuccess: string;
  privateKeyOnce: string;
  privateKeyWarning: string;
  privateKeyAcknowledge: string;
  aliasesHeading: string;
  aliasesEmpty: string;
  aliasPeer: string;
  aliasAs: string;
  aliasRecognizedAt: string;
  rotateHeading: string;
  rotateLede: string;
  rotateWarning: string;
  rotateOldKeyLabel: string;
  rotateOldKeyPlaceholder: string;
  rotateAction: string;
  rotateInProgress: string;
  rotateSuccess: string;
  errorPrefix: string;
  sovereigntyNote: string;
};

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function fromHex(hex: string): Uint8Array {
  const clean = hex.trim().toLowerCase();
  if (clean.length % 2 !== 0) throw new Error("invalid hex length");
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) {
    const byte = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
    if (Number.isNaN(byte)) throw new Error("invalid hex character");
    out[i] = byte;
  }
  return out;
}

// Canonical JSON matches api/app/services/identity_signing.canonical_json
// (sorted keys, separators=(',',':')) so signatures verify identically.
function canonicalJson(obj: Record<string, string>): string {
  const keys = Object.keys(obj).sort();
  const parts = keys.map((k) => `${JSON.stringify(k)}:${JSON.stringify(obj[k])}`);
  return `{${parts.join(",")}}`;
}

async function signPayload(
  payload: ClaimPayload,
  privateKeyHex: string,
): Promise<string> {
  const message = new TextEncoder().encode(
    canonicalJson(payload as unknown as Record<string, string>),
  );
  const sig = await ed.signAsync(message, fromHex(privateKeyHex));
  return toHex(sig);
}

function shortHex(hex: string, head = 10, tail = 6): string {
  if (!hex) return "";
  if (hex.length <= head + tail + 1) return hex;
  return `${hex.slice(0, head)}…${hex.slice(-tail)}`;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function MeAliasesClient({
  initialContributorId,
  labels,
}: {
  initialContributorId: string;
  labels: Labels;
}) {
  const [contributorId, setContributorId] = useState(initialContributorId);
  const [aliases, setAliases] = useState<Alias[] | null>(null);
  const [pubkey, setPubkey] = useState<string>("");
  const [loading, setLoading] = useState(false);

  // After a fresh claim, the private key is held in component state and
  // shown ONCE. The user must acknowledge before we drop it.
  const [freshPrivateKey, setFreshPrivateKey] = useState<string>("");
  const [busyClaim, setBusyClaim] = useState(false);
  const [error, setError] = useState<string>("");

  // Rotation: user pastes their old private key to authorize the swap.
  const [showRotate, setShowRotate] = useState(false);
  const [oldPrivateKey, setOldPrivateKey] = useState("");
  const [busyRotate, setBusyRotate] = useState(false);
  const [rotateSuccess, setRotateSuccess] = useState(false);

  // First mount: if no contributor_id was passed via ?contributor_id=, try
  // to read it from localStorage so a logged-in visitor lands on their own
  // page automatically.
  useEffect(() => {
    if (initialContributorId) return;
    try {
      const local = readIdentity();
      if (local.contributorId) setContributorId(local.contributorId);
    } catch {
      /* ignore */
    }
  }, [initialContributorId]);

  const loadAliases = useCallback(async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError("");
    try {
      // Aliases endpoint also implicitly tells us if a pubkey is claimed:
      // an empty `aliases` list just means no peers recognize us yet, so
      // we additionally probe identity/lookup to learn the pubkey itself.
      const [aliasRes, lookupRes] = await Promise.all([
        fetch(`/api/federation/identity/aliases/${encodeURIComponent(id)}`),
        // We don't have a direct GET /identity/{id}/pubkey today, but the
        // aliases payload doesn't carry the local pubkey either. The
        // pubkey shows up indirectly through any alias row. When the
        // contributor has NO aliases yet we just rely on the claim flow
        // showing them their key — sovereignty stays clean.
        Promise.resolve(null),
      ]);
      if (!aliasRes.ok) {
        throw new Error(`aliases lookup returned ${aliasRes.status}`);
      }
      const data: AliasesResponse = await aliasRes.json();
      setAliases(data.aliases);
      if (data.aliases.length > 0) {
        setPubkey(data.aliases[0].public_key_hex);
      }
      // lookupRes is currently a no-op placeholder.
      void lookupRes;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setAliases([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (contributorId.trim()) {
      void loadAliases(contributorId.trim());
    }
  }, [contributorId, loadAliases]);

  const claim = useCallback(async () => {
    setError("");
    setRotateSuccess(false);
    const id = contributorId.trim();
    if (!id) {
      setError(labels.contributorIdHelp);
      return;
    }
    setBusyClaim(true);
    try {
      const privBytes = ed.utils.randomSecretKey();
      const pubBytes = await ed.getPublicKeyAsync(privBytes);
      const privHex = toHex(privBytes);
      const pubHex = toHex(pubBytes);
      const payload: ClaimPayload = {
        contributor_id: id,
        public_key_hex: pubHex,
        issued_at: new Date().toISOString(),
      };
      const sigHex = await signPayload(payload, privHex);
      const res = await fetch("/api/identity/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contributor_id: id,
          public_key_hex: pubHex,
          claim_signature: sigHex,
          claim_payload: payload,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`claim failed (${res.status}): ${text}`);
      }
      // Remember on the device too — convenience for the next visit.
      try {
        localStorage.setItem(CONTRIBUTOR_KEY, id);
      } catch {
        /* ignore */
      }
      setPubkey(pubHex);
      setFreshPrivateKey(privHex);
      // Refresh aliases (won't show new ones yet, but keeps the surface honest).
      await loadAliases(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyClaim(false);
    }
  }, [contributorId, labels.contributorIdHelp, loadAliases]);

  const rotate = useCallback(async () => {
    setError("");
    setRotateSuccess(false);
    const id = contributorId.trim();
    const oldPriv = oldPrivateKey.trim();
    if (!id || !oldPriv || !pubkey) {
      setError(labels.rotateOldKeyPlaceholder);
      return;
    }
    setBusyRotate(true);
    try {
      // Recover the OLD pubkey from the supplied OLD private key — this is
      // also the implicit check that the user actually holds it.
      const oldPubBytes = await ed.getPublicKeyAsync(fromHex(oldPriv));
      const oldPubHex = toHex(oldPubBytes);
      if (oldPubHex !== pubkey) {
        throw new Error("the old private key does not match the current pubkey");
      }
      // Generate NEW keypair.
      const newPrivBytes = ed.utils.randomSecretKey();
      const newPubBytes = await ed.getPublicKeyAsync(newPrivBytes);
      const newPrivHex = toHex(newPrivBytes);
      const newPubHex = toHex(newPubBytes);
      const issuedAt = new Date().toISOString();
      const claimPayload: ClaimPayload = {
        contributor_id: id,
        public_key_hex: newPubHex,
        issued_at: issuedAt,
      };
      const rotationPayload: ClaimPayload = {
        contributor_id: id,
        public_key_hex: newPubHex,
        issued_at: issuedAt,
        rotates_from: oldPubHex,
      };
      const claimSig = await signPayload(claimPayload, newPrivHex);
      const rotationSig = await signPayload(rotationPayload, oldPriv);
      const res = await fetch("/api/identity/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contributor_id: id,
          public_key_hex: newPubHex,
          claim_signature: claimSig,
          claim_payload: claimPayload,
          rotation_signature: rotationSig,
          rotation_payload: rotationPayload,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`rotation failed (${res.status}): ${text}`);
      }
      setPubkey(newPubHex);
      setFreshPrivateKey(newPrivHex);
      setRotateSuccess(true);
      setShowRotate(false);
      setOldPrivateKey("");
      await loadAliases(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyRotate(false);
    }
  }, [
    contributorId,
    labels.rotateOldKeyPlaceholder,
    loadAliases,
    oldPrivateKey,
    pubkey,
  ]);

  const hasContributor = contributorId.trim().length > 0;
  const hasPubkey = pubkey.length > 0 || (aliases?.length ?? 0) > 0;

  const displayedPubkey = useMemo(() => pubkey, [pubkey]);

  return (
    <div className="space-y-8">
      {/* Contributor identity selector */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <label
          htmlFor="contributor-id"
          className="block text-xs uppercase tracking-widest text-muted-foreground"
        >
          {labels.contributorIdLabel}
        </label>
        <input
          id="contributor-id"
          type="text"
          value={contributorId}
          onChange={(e) => setContributorId(e.target.value)}
          placeholder={labels.contributorIdPlaceholder}
          className="w-full rounded-lg border border-border/30 bg-background/60 px-3 py-2 text-sm font-mono focus:border-amber-400/60 focus:outline-none"
        />
        <p className="text-xs text-muted-foreground/70">{labels.contributorIdHelp}</p>
      </section>

      {error ? (
        <p className="rounded-2xl border border-amber-400/30 bg-amber-500/5 p-4 text-sm text-amber-200">
          {labels.errorPrefix} {error}
        </p>
      ) : null}

      {/* Pubkey + claim flow */}
      <section className="space-y-3">
        {!hasContributor ? null : loading && aliases === null ? (
          <p className="text-sm text-muted-foreground">{labels.loading}</p>
        ) : hasPubkey ? (
          <article className="rounded-2xl border border-amber-400/20 bg-amber-500/5 p-5 space-y-2">
            <div className="text-xs uppercase tracking-widest text-amber-200/80">
              {labels.yourPubkey}
            </div>
            <div className="text-sm font-mono break-all text-amber-100">
              {displayedPubkey || shortHex(aliases?.[0]?.public_key_hex ?? "")}
            </div>
            {rotateSuccess ? (
              <p className="text-xs text-amber-200/90 pt-1">
                {labels.rotateSuccess}
              </p>
            ) : null}
          </article>
        ) : (
          <article className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 space-y-4">
            <p className="text-sm text-muted-foreground">{labels.noPubkey}</p>
            <button
              type="button"
              onClick={claim}
              disabled={busyClaim || !hasContributor}
              className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-200 hover:bg-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {busyClaim ? labels.generating : labels.generateClaim}
            </button>
          </article>
        )}
      </section>

      {/* Fresh private key — shown ONCE */}
      {freshPrivateKey ? (
        <section className="rounded-2xl border border-amber-400/40 bg-amber-500/10 p-5 space-y-3">
          <div className="space-y-1">
            <h3 className="text-sm font-medium text-amber-200">
              {labels.privateKeyOnce}
            </h3>
            <p className="text-xs text-amber-200/80">{labels.privateKeyWarning}</p>
          </div>
          <textarea
            readOnly
            value={freshPrivateKey}
            onFocus={(e) => e.currentTarget.select()}
            className="w-full rounded-lg border border-amber-400/40 bg-background/60 px-3 py-2 text-xs font-mono text-amber-100 min-h-[80px]"
          />
          <p className="text-xs text-amber-200/70">{labels.claimSuccess}</p>
          <button
            type="button"
            onClick={() => setFreshPrivateKey("")}
            className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-200 hover:bg-amber-500/20 transition-colors"
          >
            {labels.privateKeyAcknowledge}
          </button>
        </section>
      ) : null}

      {/* Aliases list */}
      {hasContributor ? (
        <section className="space-y-3">
          <h2 className="text-lg font-medium">{labels.aliasesHeading}</h2>
          {aliases === null ? (
            <p className="text-sm text-muted-foreground">{labels.loading}</p>
          ) : aliases.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 text-sm text-muted-foreground">
              {labels.aliasesEmpty}
            </p>
          ) : (
            <ul className="space-y-2">
              {aliases.map((a) => (
                <li
                  key={`${a.peer_instance_id}-${a.peer_contributor_id}`}
                  className="rounded-2xl border border-amber-400/20 bg-amber-500/5 p-4 space-y-1"
                >
                  <p className="text-sm text-amber-200">
                    <span className="text-muted-foreground/80 text-xs uppercase tracking-widest mr-2">
                      {labels.aliasPeer}
                    </span>
                    <span className="font-mono">{a.peer_instance_id}</span>
                  </p>
                  <p className="text-sm">
                    <span className="text-muted-foreground/80 text-xs uppercase tracking-widest mr-2">
                      {labels.aliasAs}
                    </span>
                    <span className="font-mono">{a.peer_contributor_id}</span>
                  </p>
                  <p className="text-xs text-muted-foreground/70">
                    {labels.aliasRecognizedAt}: {formatTimestamp(a.recognized_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {/* Rotation */}
      {hasPubkey ? (
        <section className="space-y-3">
          <h2 className="text-lg font-medium">{labels.rotateHeading}</h2>
          <p className="text-sm text-muted-foreground">{labels.rotateLede}</p>
          {!showRotate ? (
            <button
              type="button"
              onClick={() => setShowRotate(true)}
              className="rounded-lg border border-border/40 bg-background/40 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-amber-400/40 transition-colors"
            >
              {labels.rotateAction}
            </button>
          ) : (
            <article className="rounded-2xl border border-amber-400/30 bg-amber-500/5 p-5 space-y-3">
              <p className="text-xs text-amber-200/90">{labels.rotateWarning}</p>
              <label
                htmlFor="old-private-key"
                className="block text-xs uppercase tracking-widest text-muted-foreground"
              >
                {labels.rotateOldKeyLabel}
              </label>
              <textarea
                id="old-private-key"
                value={oldPrivateKey}
                onChange={(e) => setOldPrivateKey(e.target.value)}
                placeholder={labels.rotateOldKeyPlaceholder}
                className="w-full rounded-lg border border-border/30 bg-background/60 px-3 py-2 text-xs font-mono min-h-[80px] focus:border-amber-400/60 focus:outline-none"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={rotate}
                  disabled={busyRotate || !oldPrivateKey.trim()}
                  className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-200 hover:bg-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {busyRotate ? labels.rotateInProgress : labels.rotateAction}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowRotate(false);
                    setOldPrivateKey("");
                  }}
                  className="rounded-lg border border-border/30 bg-background/40 px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  ×
                </button>
              </div>
            </article>
          )}
        </section>
      ) : null}

      <p className="text-xs text-muted-foreground/70 pt-4 border-t border-border/20">
        {labels.sovereigntyNote}
      </p>
    </div>
  );
}
