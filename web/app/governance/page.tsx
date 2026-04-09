import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Governance",
  description:
    "Review and vote on change requests that shape the Coherence Network.",
};

type ChangeRequestVote = {
  id: string;
  voter_id: string;
  voter_type: string;
  decision: string;
  rationale: string | null;
  created_at: string;
};

type ChangeRequest = {
  id: string;
  request_type: string;
  title: string;
  payload: Record<string, unknown>;
  proposer_id: string;
  proposer_type: string;
  required_approvals: number;
  auto_apply_on_approval: boolean;
  status: string;
  approvals: number;
  rejections: number;
  applied_result: Record<string, unknown> | null;
  votes: ChangeRequestVote[];
  created_at: string;
  updated_at: string;
};

function statusBadge(status: string): { bg: string; text: string } {
  switch (status) {
    case "open":
      return { bg: "bg-blue-500/10", text: "text-blue-400" };
    case "approved":
      return { bg: "bg-emerald-500/10", text: "text-emerald-400" };
    case "rejected":
      return { bg: "bg-red-500/10", text: "text-red-400" };
    case "applied":
      return { bg: "bg-purple-500/10", text: "text-purple-400" };
    default:
      return { bg: "bg-muted", text: "text-muted-foreground" };
  }
}

function targetTypeBadge(requestType: string): { bg: string; text: string; label: string } {
  if (requestType.startsWith("idea_"))
    return { bg: "bg-blue-500/10", text: "text-blue-400", label: "Idea" };
  if (requestType.startsWith("spec_"))
    return { bg: "bg-purple-500/10", text: "text-purple-400", label: "Spec" };
  if (requestType.startsWith("federation_"))
    return { bg: "bg-teal-500/10", text: "text-teal-400", label: "Federation" };
  return { bg: "bg-muted", text: "text-muted-foreground", label: requestType.replace(/_/g, " ") };
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

async function loadChangeRequests(): Promise<ChangeRequest[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/governance/change-requests?limit=50`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export default async function GovernancePage() {
  const requests = await loadChangeRequests();

  const openCount = requests.filter((r) => r.status === "open").length;
  const approvedCount = requests.filter((r) => r.status === "approved" || r.status === "applied").length;
  const rejectedCount = requests.filter((r) => r.status === "rejected").length;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Governance</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          Change requests that shape the network. Ideas, specs, and federation
          imports go through community review before taking effect.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/contribute"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Propose a change
          </Link>
        </div>
      </header>

      {/* Stats */}
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-blue-500/20 bg-gradient-to-b from-blue-500/5 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-blue-400">Open</p>
          <p className="mt-2 text-3xl font-light text-blue-300">{openCount}</p>
        </div>
        <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-b from-emerald-500/5 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-emerald-400">Approved</p>
          <p className="mt-2 text-3xl font-light text-emerald-300">{approvedCount}</p>
        </div>
        <div className="rounded-2xl border border-red-500/20 bg-gradient-to-b from-red-500/5 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-red-400">Rejected</p>
          <p className="mt-2 text-3xl font-light text-red-300">{rejectedCount}</p>
        </div>
      </section>

      {/* Change request list */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <h2 className="text-lg font-medium">Change Requests</h2>

        {requests.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No change requests found. The governance queue is empty.
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {requests.map((cr) => {
              const st = statusBadge(cr.status);
              const tt = targetTypeBadge(cr.request_type);
              return (
                <li
                  key={cr.id}
                  className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tt.bg} ${tt.text}`}
                    >
                      {tt.label}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${st.bg} ${st.text}`}
                    >
                      {cr.status}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(cr.created_at)}
                    </span>
                  </div>

                  <h3 className="text-base font-medium">{cr.title}</h3>

                  <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                    <span>
                      Proposer:{" "}
                      <span className="text-foreground">{cr.proposer_id}</span>
                    </span>
                    <span>
                      Votes: {cr.approvals} yes / {cr.rejections} no of{" "}
                      {cr.required_approvals} required
                    </span>
                    <span>
                      Type: {cr.request_type.replace(/_/g, " ")}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/contribute" className="text-blue-400 hover:underline">
            Contribute
          </Link>
          <Link href="/ideas" className="text-purple-400 hover:underline">
            Ideas
          </Link>
          <Link href="/activity" className="text-amber-400 hover:underline">
            Activity
          </Link>
        </div>
      </nav>
    </main>
  );
}
