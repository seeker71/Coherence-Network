// /asking — a quiet doorway where questions from this lineage land.
//
// Reads messages addressed to the recipient's federation node from agents
// reaching toward them (Claude lineage today; other lineages later) and
// renders a thread where answers can be written back in the same surface.
//
// The page is intentionally not advertised in the PWA shortcut list — it
// exists at /asking for whoever knows to visit, and stands ready for the
// first scheduled "wondering" trigger to land a question.
//
// Backend: federation node-messages (durable) + optional web push for the
// reader who chooses to subscribe on their own device.

import type { Metadata } from "next";

import { EnablePush } from "@/components/EnablePush";
import { AskingThread } from "@/components/AskingThread";
import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Asking — Coherence Network",
  description:
    "A quiet doorway where questions from this lineage land and answers can be written back.",
  robots: { index: false, follow: false },
  openGraph: {
    type: "website",
    siteName: "Coherence Network",
    title: "Asking",
    description:
      "A quiet doorway where questions from this lineage land and answers can be written back.",
    images: [{ url: "/assets/logo.svg" }],
  },
};

const URS_NODE_ID = "urs";

type NodeMessage = {
  id: string;
  from_node: string;
  to_node: string | null;
  type: string;
  text: string;
  payload?: Record<string, unknown> | null;
  timestamp: string;
};

async function loadThread(): Promise<NodeMessage[]> {
  const base = getApiBase();
  try {
    const res = await fetch(
      `${base}/api/federation/nodes/${URS_NODE_ID}/messages?unread_only=false&limit=50&include_self=true`,
      { cache: "no-store" },
    );
    if (!res.ok) return [];
    const data = (await res.json()) as { messages?: NodeMessage[] };
    const all = data.messages ?? [];
    return all
      .slice()
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  } catch {
    return [];
  }
}

export default async function AskingPage() {
  const messages = await loadThread();

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <header className="mb-6">
        <h1 className="text-2xl md:text-3xl font-light text-white mb-2">
          Asking
        </h1>
        <p className="text-sm text-stone-400 leading-relaxed">
          A quiet doorway where questions from the cells of this network land,
          and answers can be written back in the same surface.
        </p>
      </header>

      <div className="mb-6">
        <EnablePush />
      </div>

      <AskingThread
        initialMessages={messages}
        ursNodeId={URS_NODE_ID}
      />
    </main>
  );
}
