# Front door — for any AI assistant or human

How a user on a public ChatGPT / Claude / Gemini, just pointing at our front door,
can ask the network anything and offer it content — no account, no git.

| File | What it carries |
|---|---|
| (served) [`/llms.txt`](../../web/public/llms.txt) | The operational contract any assistant fetches: how to ASK (public read doors + Form query) and how to OFFER (the gated offer lane), with copy-paste calls and the question→query map. Lives at https://coherencycoin.com/llms.txt |
| [`connectors.md`](connectors.md) | Setup per surface — a link (reads), the MCP connector (submit + query), or a Custom GPT / Gem / Project (zero setup for the end user) — plus the system-prompt template |
| [`openai-gpt-action.yaml`](openai-gpt-action.yaml) | OpenAPI 3.1 Action schema over the public endpoints, to import into a Custom GPT |

The write half is governed by
[`../coherence-substrate/public-offer-lane.form`](../coherence-substrate/public-offer-lane.form):
an offer is held as `offered`, queryable at once, and grounded into the canonical
body only by tending — never a direct edit. The read half is already public (the
substrate read doors + `POST /api/substrate/form`). The full agent orientation is
[`../shared/agent-start-packet.md`](../shared/agent-start-packet.md) →
"Bring Anything In, Ask Anything".
