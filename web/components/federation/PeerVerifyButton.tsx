// Re-verify a peer's signed capability manifest from the browser.
// Calls /api/federation/capabilities/{instance_id}/verify and displays the
// alignment outcome in-place. Honors the peer's sovereignty: failure to
// verify is reported as honest absence, never as accusation.

"use client";

import { useState } from "react";

type VerifyState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; verified: boolean; note: string; signedAt?: string }
  | { kind: "absent"; reason: string };

type Props = {
  peerInstanceId: string;
  peerEndpoint: string;
  apiBase: string;
  labels: {
    verify: string;
    verifying: string;
    verified: string;
    unsigned: string;
    absent: string;
  };
};

export default function PeerVerifyButton({
  peerInstanceId,
  peerEndpoint,
  apiBase,
  labels,
}: Props) {
  const [state, setState] = useState<VerifyState>({ kind: "idle" });

  async function onClick() {
    setState({ kind: "loading" });
    try {
      // 1) Ask the peer to sign its own manifest.
      const signRes = await fetch(
        `${peerEndpoint.replace(/\/$/, "")}/api/federation/capabilities/sign`,
        { method: "POST", cache: "no-store" }
      );
      if (!signRes.ok) {
        setState({
          kind: "absent",
          reason:
            signRes.status === 503
              ? labels.unsigned
              : `${signRes.status}`,
        });
        return;
      }
      const signed = await signRes.json();
      // 2) Verify the signature against the peer secret we hold.
      const verifyRes = await fetch(
        `${apiBase}/api/federation/capabilities/${encodeURIComponent(
          peerInstanceId
        )}/verify`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(signed),
        }
      );
      if (!verifyRes.ok) {
        setState({ kind: "absent", reason: `${verifyRes.status}` });
        return;
      }
      const align = await verifyRes.json();
      setState({
        kind: "ok",
        verified: Boolean(align.verified),
        note: String(align.verification_note ?? ""),
        signedAt: signed.signed_at,
      });
    } catch (err) {
      setState({
        kind: "absent",
        reason: err instanceof Error ? err.message : labels.absent,
      });
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={onClick}
        disabled={state.kind === "loading"}
        className="self-start rounded-full border border-border/30 bg-background/40 px-3 py-1 text-xs text-muted-foreground transition hover:border-border/60 hover:text-foreground disabled:opacity-50"
      >
        {state.kind === "loading" ? labels.verifying : labels.verify}
      </button>
      {state.kind === "ok" ? (
        <span
          className={`text-xs ${
            state.verified ? "text-emerald-300" : "text-amber-300"
          }`}
        >
          {state.verified ? `✓ ${labels.verified}` : `~ ${labels.unsigned}`}
          {state.note ? ` — ${state.note}` : null}
        </span>
      ) : null}
      {state.kind === "absent" ? (
        <span className="text-xs text-muted-foreground">
          {labels.absent}
          {state.reason ? ` (${state.reason})` : null}
        </span>
      ) : null}
    </div>
  );
}
