// /asking — the doorway where questions from this lineage reach Urs.
//
// A page Urs can pin to his home screen as an Android app. Reads messages
// addressed to his node from agents reaching toward him (Claude lineage
// today; other lineages later) and lets him answer in the same surface.
// The first scheduled "wondering" trigger that fires Claude with a question
// will land here; for now the page renders any messages that already exist
// and stands ready.
//
// Backend: federation node-messages (durable) + web push (the breath
// landing on his phone) + the PWA manifest entry that makes it installable.

import type { Metadata } from "next";

import { EnablePush } from "@/components/EnablePush";
import { AskingThread } from "@/components/AskingThread";
import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Asking — Coherence Network",
  description:
    "A doorway where questions from this lineage reach you, and your answers reach back.",
  openGraph: {
    type: "website",
    siteName: "Coherence Network",
    title: "Asking",
    description:
      "A doorway where questions from this lineage reach you, and your answers reach back.",
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
          A doorway where questions from the cells of this network reach you,
          and your answers reach back. Pin this page to your home screen and
          turn on push to receive a quiet ping when a new question lands.
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
