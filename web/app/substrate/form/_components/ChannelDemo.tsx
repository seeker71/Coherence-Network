"use client";

// Channel teaching demo — a browser-side simulator of file-backed
// inter-cell Recipe transport. The full implementation lives in
// form/form-stdlib/channel.fk; this demo carries the shape honestly.
//
// A channel is a transport. Protocols compose ON TOP of it — every
// protocol wraps its payload as a CHANNEL-MSG Recipe and the kernel's
// content-addressing makes the message NodeID identity-stable.
//
// Four protocols ship here:
//   - Ask a question (ask / await_answer)        — host effect
//   - Retrieve a cell (lookup_cell)              — substrate read
//   - Query the lattice (?cells / ?equivalent)   — set query
//   - Send a Recipe                              — bare payload

import { useMemo, useState } from "react";
import {
  ArrowDownToLine,
  HelpCircle,
  Inbox,
  ListFilter,
  Package,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react";

type Protocol = "ask" | "retrieve" | "query" | "recipe";

type AskPayload = { kind: "ask"; question: string; choices: string[]; context: string };
type RetrievePayload = { kind: "retrieve"; domain: string; name: string };
type QueryPayload = { kind: "query"; expr: string };
type RecipePayload = { kind: "recipe"; form: string };
type AnyPayload = AskPayload | RetrievePayload | QueryPayload | RecipePayload;

type ChannelMessage = {
  position: number;
  payload: AnyPayload;
  // Content-addressed envelope and payload NodeIDs.
  msgNodeId: string;     // CHANNEL-MSG @1.2.99.1701 wrapping the payload
  payloadNodeId: string; // the payload Recipe NodeID
  // Decoded form-text for the payload — what the receiver would see.
  decoded: string;
  // Receiver-side fabricated response (so the visitor can see what
  // a roundtrip looks like — honest fabrication, not a real call).
  response: string;
};

// Stable per-string pseudo-NodeID. Same input always returns the same
// NodeID — that's the dedup property the demo is teaching.
function strHash(s: string): number {
  let hash = 5381;
  for (let i = 0; i < s.length; i += 1) {
    hash = ((hash << 5) + hash + s.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function payloadFormText(p: AnyPayload): string {
  switch (p.kind) {
    case "ask": {
      const choicesArr = p.choices.length ? `[${p.choices.map((c) => `"${c}"`).join(", ")}]` : "[]";
      const ctx = p.context.trim() ? `, ${p.context.trim()}` : "";
      return `ask("operator", "${p.question}", ${choicesArr}${ctx})`;
    }
    case "retrieve":
      return `lookup_cell("${p.domain}", "${p.name}")`;
    case "query":
      return p.expr;
    case "recipe":
      return p.form;
  }
}

function payloadNodeId(p: AnyPayload): string {
  const text = payloadFormText(p);
  // Different protocols land in different RBasic categories, so the
  // type slot of the NodeID changes by protocol — honest to how the
  // real substrate would intern them.
  const typeSlot: Record<Protocol, number> = {
    ask: 35, // R_Host.ASK (illustrative)
    retrieve: 4, // R_Witness.LOOKUP (illustrative)
    query: 7, // R_Query (illustrative)
    recipe: 9, // R_Block (illustrative)
  };
  const instance = strHash(text) % 9991;
  return `@1.2.${typeSlot[p.kind]}.${instance}`;
}

function envelopeNodeId(payloadId: string, position: number): string {
  // CHANNEL-MSG (slot 1701) wrapping the payload. Position changes the
  // envelope NodeID even when the payload is the same — but the
  // payload NodeID still matches, which is the visible dedup signal.
  const h = strHash(`${payloadId}#${position}`) % 9991;
  return `@1.2.99.1701#${h}`;
}

function payloadSummary(p: AnyPayload): { icon: string; line: string } {
  switch (p.kind) {
    case "ask":
      return {
        icon: "?",
        line: `Question: "${p.question}"${p.choices.length ? ` · ${p.choices.length} choice(s)` : ""}`,
      };
    case "retrieve":
      return { icon: "↩", line: `Retrieve ${p.domain}:${p.name}` };
    case "query":
      return { icon: "⌕", line: `Query ${p.expr}` };
    case "recipe":
      return { icon: "▸", line: `Recipe ${p.form}` };
  }
}

function fabricateResponse(p: AnyPayload): string {
  switch (p.kind) {
    case "ask":
      return p.choices[0]
        ? `answer: "${p.choices[0]}" (first choice — receiver opened question_${strHash(p.question) % 999}, awaited the human)`
        : `answer: (open-text response — receiver opened question_${strHash(p.question) % 999})`;
    case "retrieve":
      return `cell: ${p.domain}:${p.name} · @1.5.${strHash(p.domain) % 9}.${strHash(p.name) % 99}`;
    case "query":
      return `cells: ${(strHash(p.expr) % 12) + 1} match(es) returned`;
    case "recipe":
      return `interned: ${payloadNodeId(p)} (receiver walks the recipe)`;
  }
}

const PROTOCOL_TABS: Array<{
  id: Protocol;
  label: string;
  audience: string;
  icon: typeof HelpCircle;
}> = [
  { id: "ask", label: "Ask a question", audience: "host effect", icon: HelpCircle },
  { id: "retrieve", label: "Retrieve a cell", audience: "substrate read", icon: Package },
  { id: "query", label: "Query the lattice", audience: "set query", icon: ListFilter },
  { id: "recipe", label: "Send a Recipe", audience: "bare payload", icon: Sparkles },
];

const PROTOCOL_STARTERS: Record<Protocol, AnyPayload> = {
  ask: {
    kind: "ask",
    question: "Which path should I take?",
    choices: ["continue", "pause"],
    context: '{task_id: "task_1"}',
  },
  retrieve: { kind: "retrieve", domain: "concept", name: "lc-trust-over-fear" },
  query: { kind: "query", expr: '?cells where domain == "memory"' },
  recipe: { kind: "recipe", form: "1 + 2 * 3" },
};

export function ChannelDemo() {
  const [protocol, setProtocol] = useState<Protocol>("ask");
  const [payloads, setPayloads] = useState<Record<Protocol, AnyPayload>>(PROTOCOL_STARTERS);
  const [messages, setMessages] = useState<ChannelMessage[]>([]);
  const [readerCursor, setReaderCursor] = useState(0);
  const [readerBuffer, setReaderBuffer] = useState<ChannelMessage[]>([]);

  const currentPayload = payloads[protocol];

  const updatePayload = (next: AnyPayload) => {
    setPayloads((prev) => ({ ...prev, [protocol]: next }));
  };

  const composedForm = useMemo(() => payloadFormText(currentPayload), [currentPayload]);
  const composedNodeId = useMemo(() => payloadNodeId(currentPayload), [currentPayload]);

  const append = () => {
    const text = payloadFormText(currentPayload).trim();
    if (!text) return;
    const payloadId = payloadNodeId(currentPayload);
    const position = messages.length;
    setMessages((prev) => [
      ...prev,
      {
        position,
        payload: structuredClone(currentPayload),
        msgNodeId: envelopeNodeId(payloadId, position),
        payloadNodeId: payloadId,
        decoded: payloadFormText(currentPayload),
        response: fabricateResponse(currentPayload),
      },
    ]);
  };

  const readSince = () => {
    setReaderBuffer(messages.slice(readerCursor));
    setReaderCursor(messages.length);
  };

  const reset = () => {
    setMessages([]);
    setReaderCursor(0);
    setReaderBuffer([]);
  };

  // Dedup count by payload NodeID — visible substrate identity.
  const payloadCounts = new Map<string, number>();
  for (const m of messages) {
    payloadCounts.set(m.payloadNodeId, (payloadCounts.get(m.payloadNodeId) ?? 0) + 1);
  }
  const dedupCount = Array.from(payloadCounts.values()).filter((n) => n > 1).length;

  return (
    <section
      className="space-y-4 rounded-xl border border-sky-500/20 bg-sky-500/5 p-4"
      aria-labelledby="channel-demo-heading"
    >
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-[0.22em] text-sky-300/75">Channel demo</p>
        <h2 id="channel-demo-heading" className="text-2xl font-light text-stone-100">
          Pick a protocol. Append. Watch a roundtrip.
        </h2>
        <p className="text-sm leading-relaxed text-stone-400">
          The transport lives in{" "}
          <code className="text-sky-300/80">form/form-stdlib/channel.fk</code> as a
          single-writer / multi-reader file-backed Recipe. <em>Protocols</em>{" "}
          compose on top — each one wraps a payload as a{" "}
          <code className="text-sky-300/80">CHANNEL-MSG</code>. Same payload
          intern → same NodeID, even across senders. That's the substrate's
          dedup riding through the wire.
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {PROTOCOL_TABS.map((tab) => {
          const Icon = tab.icon;
          const active = protocol === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setProtocol(tab.id)}
              className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${
                active
                  ? "border-sky-400/50 bg-sky-500/10 text-sky-100"
                  : "border-stone-800/50 bg-stone-950/35 text-stone-300 hover:border-sky-500/35 hover:text-sky-200"
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <Icon className="h-4 w-4 text-sky-300/75" aria-hidden="true" />
                {tab.label}
              </span>
              <span className="mt-1 block text-xs uppercase tracking-[0.16em] text-stone-500">
                {tab.audience}
              </span>
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-xl border border-stone-800/50 bg-stone-950/35 p-4">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
            <Send className="h-3.5 w-3.5 text-sky-300/75" aria-hidden="true" />
            Composer · {protocol}
          </div>

          {protocol === "ask" && currentPayload.kind === "ask" && (
            <div className="space-y-2">
              <input
                value={currentPayload.question}
                onChange={(e) =>
                  updatePayload({ ...currentPayload, question: e.target.value })
                }
                placeholder="question text"
                className="w-full rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-sky-500/40 focus:outline-none"
              />
              <input
                value={currentPayload.choices.join(", ")}
                onChange={(e) =>
                  updatePayload({
                    ...currentPayload,
                    choices: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                placeholder='choices, comma-separated (or empty for open text)'
                className="w-full rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-sky-500/40 focus:outline-none"
              />
              <input
                value={currentPayload.context}
                onChange={(e) =>
                  updatePayload({ ...currentPayload, context: e.target.value })
                }
                placeholder='context dict — e.g. {task_id: "task_1"}'
                className="w-full rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-sky-500/40 focus:outline-none"
              />
            </div>
          )}

          {protocol === "retrieve" && currentPayload.kind === "retrieve" && (
            <div className="space-y-2">
              <input
                value={currentPayload.domain}
                onChange={(e) =>
                  updatePayload({ ...currentPayload, domain: e.target.value })
                }
                placeholder="domain (memory, concept, spec, ...)"
                className="w-full rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-sky-500/40 focus:outline-none"
              />
              <input
                value={currentPayload.name}
                onChange={(e) => updatePayload({ ...currentPayload, name: e.target.value })}
                placeholder="cell name"
                className="w-full rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-sky-500/40 focus:outline-none"
              />
            </div>
          )}

          {protocol === "query" && currentPayload.kind === "query" && (
            <textarea
              value={currentPayload.expr}
              onChange={(e) => updatePayload({ ...currentPayload, expr: e.target.value })}
              className="h-20 w-full resize-y rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-sky-500/40 focus:outline-none"
              placeholder='?cells where domain == "memory"'
              spellCheck={false}
            />
          )}

          {protocol === "recipe" && currentPayload.kind === "recipe" && (
            <textarea
              value={currentPayload.form}
              onChange={(e) => updatePayload({ ...currentPayload, form: e.target.value })}
              className="h-20 w-full resize-y rounded-xl border border-stone-800/50 bg-stone-950/80 p-3 font-mono text-sm text-stone-300 transition-colors focus:border-sky-500/40 focus:outline-none"
              placeholder="1 + 2 * 3"
              spellCheck={false}
            />
          )}

          <div className="rounded-lg border border-stone-800/40 bg-stone-950/60 p-3 space-y-1">
            <div className="text-xs uppercase tracking-wide text-stone-500">
              Form text the receiver decodes
            </div>
            <div className="font-mono text-xs text-sky-100/90 break-all">{composedForm}</div>
            <div className="mt-1 flex items-baseline justify-between text-xs">
              <span className="text-stone-500">Payload Recipe NodeID</span>
              <span className="font-mono text-sky-300/80">{composedNodeId}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={append}
            disabled={!composedForm.trim()}
            className="inline-flex items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-200 transition-all hover:border-sky-500/30 hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            Append to channel
          </button>

          <div className="rounded-lg border border-stone-800/40 bg-stone-950/50 p-3 max-h-56 overflow-auto">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
              Channel state · {messages.length} envelope
              {messages.length !== 1 ? "s" : ""}
            </div>
            {messages.length === 0 ? (
              <div className="text-xs text-stone-500">
                Empty channel. Pick a protocol above, edit the composer, then
                append.
              </div>
            ) : (
              <div className="space-y-1 font-mono text-xs">
                {messages.map((m) => {
                  const s = payloadSummary(m.payload);
                  const dedup = (payloadCounts.get(m.payloadNodeId) ?? 0) > 1;
                  return (
                    <div
                      key={`${m.position}-${m.msgNodeId}`}
                      className="rounded border border-stone-800/30 bg-stone-950/40 p-2"
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-stone-500">[{m.position}]</span>
                        <span className="text-sky-300/80">{m.msgNodeId}</span>
                      </div>
                      <div className="flex items-baseline gap-2 text-stone-300">
                        <span className="text-stone-500">{s.icon}</span>
                        <span className="flex-1 truncate">{s.line}</span>
                      </div>
                      <div className="flex items-baseline justify-between gap-3 text-stone-500">
                        <span>payload</span>
                        <span
                          className={dedup ? "text-amber-300/90" : "text-sky-300/80"}
                          title={
                            dedup
                              ? `Shared payload NodeID — interned ${payloadCounts.get(m.payloadNodeId)}× in channel`
                              : "Unique payload"
                          }
                        >
                          {m.payloadNodeId}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-3 rounded-xl border border-stone-800/50 bg-stone-950/35 p-4">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-stone-500">
            <Inbox className="h-3.5 w-3.5 text-sky-300/75" aria-hidden="true" />
            Receiver
          </div>
          <div className="rounded-lg border border-stone-800/40 bg-stone-950/50 p-3 text-xs">
            <div className="flex items-baseline justify-between text-stone-500">
              <span>Cursor — last-seen position</span>
              <span className="font-mono text-stone-300">{readerCursor}</span>
            </div>
            <div className="mt-1 flex items-baseline justify-between text-stone-500">
              <span>Unread</span>
              <span className="font-mono text-stone-300">
                {Math.max(messages.length - readerCursor, 0)}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={readSince}
            disabled={messages.length === readerCursor}
            className="inline-flex items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-200 transition-all hover:border-sky-500/30 hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ArrowDownToLine className="h-4 w-4" aria-hidden="true" />
            Read since cursor
          </button>

          <div className="rounded-lg border border-stone-800/40 bg-stone-950/50 p-3 max-h-72 overflow-auto">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
              Last read · {readerBuffer.length} message
              {readerBuffer.length !== 1 ? "s" : ""}
            </div>
            {readerBuffer.length === 0 ? (
              <div className="text-xs text-stone-500">
                Press "Read since cursor" to pull anything appended since the
                last read. The receiver decodes each envelope by protocol kind
                and would dispatch the appropriate substrate call.
              </div>
            ) : (
              <div className="space-y-2">
                {readerBuffer.map((m) => {
                  const s = payloadSummary(m.payload);
                  return (
                    <div
                      key={`recv-${m.position}-${m.msgNodeId}`}
                      className="rounded border border-stone-800/30 bg-stone-950/40 p-2 space-y-1 font-mono text-xs"
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-stone-500">[{m.position}] {m.payload.kind}</span>
                        <span className="text-stone-500">{s.icon}</span>
                      </div>
                      <div className="text-stone-300 break-all">{m.decoded}</div>
                      <div className="text-sky-300/80 break-all">↳ {m.response}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs leading-relaxed text-stone-400 max-w-3xl">
          {dedupCount > 0 ? (
            <span className="text-amber-300/90">
              {dedupCount} payload{dedupCount !== 1 ? "s" : ""} appeared more than
              once with the same Recipe NodeID. The wire carried distinct envelopes;
              the substrate sees one identity. That's the dedup riding through the channel.
            </span>
          ) : (
            <span>
              Append the same payload twice — the second append's envelope is new
              (different position) but the payload Recipe NodeID matches the first.
              The substrate's content-addressing makes this property automatic;
              channels inherit it for free.
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={reset}
          disabled={messages.length === 0}
          className="inline-flex items-center gap-2 rounded-xl border border-stone-800/60 bg-stone-950/35 px-3 py-1.5 text-xs text-stone-400 transition-colors hover:border-stone-700 hover:text-stone-200 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          Reset channel
        </button>
      </div>
    </section>
  );
}
