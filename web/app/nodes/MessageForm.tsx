"use client";

import { useState } from "react";
import { useT } from "@/components/MessagesProvider";

type FederationNode = {
  node_id: string;
  hostname: string;
};

type Message = {
  id: string;
  from_node: string;
  to_node: string;
  message_type: string;
  payload: Record<string, unknown>;
  created_at: string;
  read: boolean;
};

export default function MessageForm({
  nodes,
  apiBase,
}: {
  nodes: FederationNode[];
  apiBase: string;
}) {
  const t = useT();
  const [targetNode, setTargetNode] = useState<string>("broadcast");
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [selectedNodeForMessages, setSelectedNodeForMessages] = useState<string>("");

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!messageText.trim()) return;
    setSending(true);
    setSendResult(null);
    try {
      const payload = { message_type: "text", payload: { text: messageText.trim() } };
      let url: string;
      if (targetNode === "broadcast") {
        url = `${apiBase}/api/federation/broadcast`;
      } else {
        url = `${apiBase}/api/federation/nodes/${targetNode}/messages`;
      }
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setSendResult("Message sent.");
        setMessageText("");
      } else {
        const text = await res.text();
        setSendResult(`Error ${res.status}: ${text}`);
      }
    } catch (err) {
      setSendResult(`Failed: ${err}`);
    } finally {
      setSending(false);
    }
  }

  async function loadMessages(nodeId: string) {
    setSelectedNodeForMessages(nodeId);
    if (!nodeId) {
      setMessages([]);
      return;
    }
    setLoadingMessages(true);
    try {
      const res = await fetch(
        `${apiBase}/api/federation/nodes/${nodeId}/messages?unread_only=false&limit=20`
      );
      if (res.ok) {
        setMessages(await res.json());
      } else {
        setMessages([]);
      }
    } catch {
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }

  function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  return (
    <>
      {/* Message compose form */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4 text-sm">
        <h2 className="text-xl font-semibold">{t("messageForm.sendHeading")}</h2>
        <form onSubmit={handleSend} className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <select
              value={targetNode}
              onChange={(e) => setTargetNode(e.target.value)}
              className="rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-amber-500/50"
            >
              <option value="broadcast">{t("messageForm.broadcast")}</option>
              {nodes.map((n) => (
                <option key={n.node_id} value={n.node_id}>
                  {n.hostname}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              placeholder={t("messageForm.placeholder")}
              className="flex-1 rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-amber-500/50"
            />
            <button
              type="submit"
              disabled={sending || !messageText.trim()}
              className="rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-40 px-4 py-2 text-sm font-medium text-white transition-colors"
            >
              {sending ? `${t("messageForm.loading")}` : t("messageForm.sendBtn")}
            </button>
          </div>
          {sendResult && (
            <p className={`text-xs ${sendResult.startsWith("Error") || sendResult.startsWith("Failed") ? "text-red-400" : "text-green-400"}`}>
              {sendResult}
            </p>
          )}
        </form>
      </section>

      {/* Recent messages */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4 text-sm">
        <h2 className="text-xl font-semibold">{t("messageForm.recentHeading")}</h2>
        <select
          value={selectedNodeForMessages}
          onChange={(e) => loadMessages(e.target.value)}
          className="rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-amber-500/50"
        >
          <option value="">{t("messageForm.selectNode")}</option>
          {nodes.map((n) => (
            <option key={n.node_id} value={n.node_id}>
              {n.hostname}
            </option>
          ))}
        </select>

        {loadingMessages && <p className="text-muted-foreground">{t("messageForm.loading")}</p>}

        {!loadingMessages && selectedNodeForMessages && messages.length === 0 && (
          <p className="text-muted-foreground">{t("messageForm.noMessages")}</p>
        )}

        {messages.length > 0 && (
          <ul className="space-y-2">
            {messages.map((msg) => (
              <li
                key={msg.id}
                className={`rounded-xl border p-3 ${msg.read ? "border-border/20 bg-background/40" : "border-amber-500/30 bg-amber-500/5"}`}
              >
                <div className="flex justify-between items-start gap-2">
                  <span className="font-medium">{msg.message_type}</span>
                  <span className="text-muted-foreground text-xs whitespace-nowrap">
                    {relativeTime(msg.created_at)}
                    {!msg.read && <span className="ml-1 text-amber-400">unread</span>}
                  </span>
                </div>
                <p className="text-muted-foreground mt-1">
                  from {msg.from_node.slice(0, 8)}... &rarr; {msg.to_node.slice(0, 8)}...
                </p>
                {msg.payload && typeof msg.payload === "object" && "text" in msg.payload && (
                  <p className="mt-1">{String(msg.payload.text)}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
