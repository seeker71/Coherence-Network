# form-cli — install on a new Mac

A local-first, Form-native organism: ask any question and get an answer grounded
in this body's recipes/specs/concepts and your own local documents, fully offline
on a local LLM. A remote oracle (Claude, codex, gemini, grok, cursor) is consulted
only to *review* — never required to answer.

## One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/seeker71/Coherence-Network/main/install/form-cli-install.sh | bash
```

It prints every step before running it, asks before anything heavy, and is
re-runnable. It will:

1. **clone the source** to `~/coherence-network` (all recipes + content, local)
2. **set up the Form kernel** — builds from source if you have Go, otherwise
   downloads the prebuilt macOS arm64 binary from the [latest release](https://github.com/seeker71/Coherence-Network/releases)
3. **set up a local oracle** — installs [ollama](https://ollama.com) (if you allow)
   and pulls `llama3.2:3b` (reasoning) + `nomic-embed-text` (memory)
4. **ask which agent CLI** to install — `claude` / `codex` / `gemini` / `grok` /
   `cursor` / none. (`codex` and `gemini` install via Homebrew; `claude` via its
   official installer; `grok`/`cursor` print the official command to verify first.)
5. **index the body** so questions are grounded
6. **install the Claude skill** (`~/.claude/skills/form-cli`) that routes questions to form-cli
7. **put `form-cli` on your PATH** (`~/.local/bin/form-cli`)

### Manual (if you prefer)

```bash
git clone https://github.com/seeker71/Coherence-Network.git ~/coherence-network
cd ~/coherence-network/form/form-kernel-go && go build -o bin-go .   # or download the release binary
brew install ollama && ollama pull llama3.2:3b && ollama pull nomic-embed-text
ln -s ~/coherence-network/bin/form-cli ~/.local/bin/form-cli
form-cli index
```

## Using it

```bash
form-cli ask "how does the form-cli route to a local oracle?"   # grounded, offline
form-cli index --docs ~/Documents/notes                         # add your own docs
form-cli ask "what did my notes say about the budget?"          # then question them
form-cli gaps                                                    # the body's open gaps
form-cli close "lcm" "(lcm a b) = a*b/gcd(a,b)" "(lcm 4 6)" 12 "ollama run coder"
form-cli review                                                 # review the body vs an oracle
form-cli preflight                                              # confirm you can lose the network
```

## Requirements

- macOS on Apple silicon (arm64). The prebuilt kernel is `arm64`; on other
  platforms, build from source (needs [Go](https://go.dev/dl/)).
- For offline answers: [ollama](https://ollama.com) + the two pulled models. Without
  them the kernel, recipes, gaps, and `eval` still work; `ask` needs the models.

## What "local-first" means here

`form-cli` answers from the body and your local models with **no network**. The
agent CLI you pick is used only when you explicitly ask it to *review* or escalate
(`form-cli review`), and the body learns from those reviews until its own answer
and its own review match the oracle — at which point it stops needing the network
at all. Run `form-cli preflight` to confirm the kit is whole.
