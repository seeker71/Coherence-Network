---
name: form-cli
description: "Route any question to form-cli — the local-first, Form-native organism on this Mac. form-cli answers from its own recipes, specs, concepts, and any local documents you have indexed, grounded and offline (a local LLM via ollama), and consults a remote oracle (Claude/codex/gemini/grok/cursor via CLI) only to review or escalate — never to answer. Use this skill to: ask a question and get a grounded local answer with cited sources; question your own local documents (index a folder, then ask); see the body's open gaps and close one offline; review the body's reasoning against an oracle; run the self-guided agent loop; or evaluate a Form expression on the kernel. Triggers on: form-cli, ask the body, offline answer, local documents, question my notes, my docs, air-gap, self-contained, local LLM, no network, ollama, close a gap, review my thinking, Form kernel, form recipe."
metadata:
  {
    "openclaw":
      {
        "emoji": "🌀",
        "requires": { "bins": ["form-cli"] },
        "install":
          [
            {
              "id": "form-cli",
              "kind": "script",
              "script": "curl -fsSL https://raw.githubusercontent.com/seeker71/Coherence-Network/main/install/form-cli-install.sh | bash",
              "bins": ["form-cli"],
              "label": "Install form-cli (clone source + kernel + local oracle + skill)"
            }
          ]
      }
  }
---

# form-cli — the one door

`form-cli` is a local-first, Form-native organism on this Mac. It answers from its
own body (recipes, specs, concepts) and any local documents you index, runs fully
offline on a local LLM, and treats a remote oracle (Claude, codex, gemini, grok,
cursor — whichever you installed) as a *reviewer*, never a requirement.

**When to use this skill:** any time the user wants an answer grounded in this
repo or in their own local files, wants to work offline, wants to see/close the
body's gaps, or wants the body's reasoning reviewed.

## Answer a question (grounded, local, offline)

```bash
form-cli ask "how does the form-cli route between a local and a remote oracle?"
form-cli ask "what does rag-retrieve.fk do?" -m coder        # pick the local model
```

`ask` retrieves the nearest cells (Form-ranked by `rag-retrieve.fk`) and has a
local model answer using only those excerpts, citing the doc ids. No network.

## Question local documents

```bash
form-cli index --docs ~/Documents/notes --docs ~/projects/spec   # index your folders (once)
form-cli ask "what did my notes say about the Q3 plan?"          # then ask
form-cli search "deadline" -k 8                                  # retrieval only
```

Indexing embeds each document locally (`nomic-embed-text`); the index lives at
`~/.coherence-network/rag-index/`. Re-run `index` after the docs change.

## See and close the body's gaps (offline)

```bash
form-cli gaps                                                    # what's open
form-cli close "lcm" "(lcm a b) = a*b / gcd(a,b)" "(lcm 4 6)" 12 "ollama run coder"
```

A local oracle drafts the missing recipe; the local kernel validates it against
the assertion. Nothing leaves the machine.

## Review the body's thinking against an oracle

```bash
form-cli review 2 "ollama run coder" "ollama run llama3.2:3b" "claude -p" 15
```

The body answers; an internal judge and the oracle both score the same answer;
the Form metric reports how close the internal review is to the oracle's. As the
gap closes, the oracle retires.

## Other doors

```bash
form-cli run "use bash to list the recipes, then summarize" "ollama run coder" 4
form-cli eval '(add 20 22)'        # evaluate a Form expression on the kernel
form-cli preflight                 # confirm the kit is whole — you can lose the network
```

## How to route a user's question here

1. If the question is about this repo or the user's local files → `form-cli ask`.
2. If it needs the user's own documents → `form-cli index --docs <dir>` first, then `ask`.
3. Prefer the local answer; only mention escalating to a remote oracle if the local
   answer is thin and the user wants a second opinion (`form-cli review`).
4. Always surface the cited doc ids form-cli returns — they are the grounding.

Full install instructions for a new Mac: [`docs/FORM-CLI-INSTALL.md`](https://github.com/seeker71/Coherence-Network/blob/main/docs/FORM-CLI-INSTALL.md).
