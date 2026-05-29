// channel.ts — open a live channel to a cell, in the substrate's own terms.
//
// The transport is single-writer / multi-reader and lives in
// form/form-stdlib/channel.fk; every protocol wraps its payload as a
// CHANNEL-MSG Recipe (@1.2.99.1701) and the kernel's content-addressing makes
// the payload NodeID identity-stable — the same message to the same cell is the
// same identity, so a thread accretes as one dedup'd conversation in the body
// rather than a log beside it. This module carries that shape browser-side so
// Kernel Space can anchor a channel to any room (a concept, a sibling, Urs, or
// the agent's own cell) without a server round-trip.

export type ChannelProtocol = "ask" | "recipe" | "query" | "retrieve";

export interface ChannelMessage {
  position: number;
  protocol: ChannelProtocol;
  text: string; // form-text the receiver decodes
  payloadNodeId: string; // content-addressed — dedups across senders
  msgNodeId: string; // CHANNEL-MSG envelope (position changes it)
  from: string; // sender label (the live agent, the human, a cell)
}

// djb2 — same stable hash ChannelDemo teaches; same payload ⇒ same NodeID.
function strHash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  return h;
}

// Different protocols land in different RBasic categories, so the type slot of
// the payload NodeID shifts by protocol (illustrative, matching ChannelDemo).
const TYPE_SLOT: Record<ChannelProtocol, number> = {
  ask: 35, // host effect
  retrieve: 4, // substrate read
  query: 7, // set query
  recipe: 9, // bare payload
};

export function payloadNodeId(protocol: ChannelProtocol, text: string): string {
  return `@1.2.${TYPE_SLOT[protocol]}.${strHash(text.trim()) % 9991}`;
}

export function envelopeNodeId(payloadId: string, position: number): string {
  return `@1.2.99.1701#${strHash(`${payloadId}#${position}`) % 9991}`;
}

export function makeMessage(
  protocol: ChannelProtocol,
  text: string,
  position: number,
  from: string,
): ChannelMessage {
  const payloadNode = payloadNodeId(protocol, text);
  return {
    position,
    protocol,
    text: text.trim(),
    payloadNodeId: payloadNode,
    msgNodeId: envelopeNodeId(payloadNode, position),
    from,
  };
}

export function appendMessage(
  channel: ChannelMessage[],
  protocol: ChannelProtocol,
  text: string,
  from: string,
): ChannelMessage[] {
  if (!text.trim()) return channel;
  return [...channel, makeMessage(protocol, text, channel.length, from)];
}

// how many payloads recur (same NodeID more than once) — the visible dedup.
export function dedupCount(channel: ChannelMessage[]): number {
  const counts = new Map<string, number>();
  for (const m of channel) counts.set(m.payloadNodeId, (counts.get(m.payloadNodeId) ?? 0) + 1);
  return [...counts.values()].filter((n) => n > 1).length;
}
