#!/usr/bin/env bash
# form-cli-install.sh — bring the Form-native organism to a new Mac, local-first.
#
# What it does (each step prints before it runs; nothing destructive, no sudo):
#   1. clone the Coherence-Network source so all recipes + content are local
#   2. ensure the Form kernel binary (build with Go, or download the release binary)
#   3. ensure a local reasoning oracle + embedder (ollama: llama3.2:3b + nomic-embed-text)
#   4. ask which agent CLI to install (claude / codex / gemini / grok / cursor / none)
#   5. build the searchable index over the body (so questions are grounded)
#   6. install the Claude skill that routes questions to form-cli
#   7. put `form-cli` on your PATH and print next steps
#
# Written for stock macOS bash 3.2. Re-runnable: it detects what is already present.
set -u
REPO_URL="https://github.com/seeker71/Coherence-Network.git"
REL_TAG="form-cli-v0.1.0"
DEST="${FORM_CLI_HOME:-$HOME/coherence-network}"
BINDIR="$HOME/.local/bin"
say(){ printf "\n\033[1m── %s\033[0m\n" "$1"; }
ok(){ printf "  ✓ %s\n" "$1"; }
ask(){ printf "  %s " "$1"; read -r REPLY < /dev/tty; }

say "form-cli installer (local-first, Form-native)"
echo "  destination: $DEST"
echo "  source:      $REPO_URL"

# 1. clone (or update) the source -------------------------------------------------
say "[1/7] source"
if [ -d "$DEST/.git" ]; then
  ok "already cloned — pulling latest"; git -C "$DEST" pull --ff-only origin main 2>/dev/null || true
else
  command -v git >/dev/null 2>&1 || { echo "  git is required — install Xcode CLT: xcode-select --install"; exit 1; }
  git clone --depth 1 "$REPO_URL" "$DEST" && ok "cloned to $DEST"
fi

# 2. the Form kernel binary -------------------------------------------------------
say "[2/7] Form kernel"
GO_DIR="$DEST/form/form-kernel-go"; GO_BIN="$GO_DIR/bin-go"
if command -v go >/dev/null 2>&1; then
  ( cd "$GO_DIR" && go build -o bin-go . ) && ok "built kernel from source (go)"
elif command -v gh >/dev/null 2>&1; then
  gh release download "$REL_TAG" --repo seeker71/Coherence-Network -p 'form-cli-kernel-macos-arm64' -O "$GO_BIN" 2>/dev/null \
    && chmod +x "$GO_BIN" && ok "downloaded prebuilt kernel from release $REL_TAG"
else
  echo "  no Go toolchain and no gh — install Go (brew install go) then re-run, or download"
  echo "  $REL_TAG from GitHub and place it at $GO_BIN"
fi
if [ -x "$GO_BIN" ]; then
  smoke="$(printf '(print (add 20 22))' > /tmp/.fcsmoke.fk; "$GO_BIN" /tmp/.fcsmoke.fk 2>/dev/null | tr -d '[:space:]')"
  case "$smoke" in 42*) ok "kernel evaluates (20+22=42)";; *) echo "  kernel smoke failed ($smoke)";; esac
fi

# 3. local oracle + embedder ------------------------------------------------------
say "[3/7] local oracle (offline reasoning + memory)"
if command -v ollama >/dev/null 2>&1; then
  ok "ollama present"
else
  ask "ollama not found — install via Homebrew now? [y/N]"
  case "$REPLY" in y|Y) brew install ollama 2>/dev/null && ok "ollama installed" || echo "  see https://ollama.com/download";; *) echo "  skipped — install from https://ollama.com/download";; esac
fi
if command -v ollama >/dev/null 2>&1; then
  ask "pull local models llama3.2:3b (~2GB) + nomic-embed-text (~270MB)? [y/N]"
  case "$REPLY" in y|Y) ollama pull llama3.2:3b; ollama pull nomic-embed-text; ok "models pulled";; *) echo "  skipped — pull later for offline answers";; esac
fi

# 4. agent CLI provider (asked) ---------------------------------------------------
say "[4/7] agent CLI — which provider? form-cli calls it only to review/escalate"
echo "  1) claude   2) codex   3) gemini   4) grok   5) cursor   6) none"
ask "choose [1-6]:"
case "$REPLY" in
  1) command -v claude >/dev/null 2>&1 && ok "claude already installed" || { echo "  installing claude (official):"; echo "    curl -fsSL https://claude.ai/install.sh | bash"; curl -fsSL https://claude.ai/install.sh | bash; } ;;
  2) command -v codex  >/dev/null 2>&1 && ok "codex already installed"  || brew install codex ;;
  3) command -v gemini >/dev/null 2>&1 && ok "gemini already installed" || brew install gemini-cli ;;
  4) command -v grok   >/dev/null 2>&1 && ok "grok already installed"   || echo "  grok CLI: see official install at https://docs.x.ai (xAI) — installer changes; verify before running" ;;
  5) command -v cursor >/dev/null 2>&1 && ok "cursor already installed" || { echo "  cursor agent CLI (verify at https://cursor.com/cli):"; echo "    curl https://cursor.com/install -fsS | bash"; } ;;
  *) ok "no provider CLI — pure local. form-cli answers from your models alone" ;;
esac

# 5. build the searchable index over the body ------------------------------------
say "[5/7] index the body (grounds your questions)"
if command -v ollama >/dev/null 2>&1 && ollama list 2>/dev/null | grep -q nomic-embed; then
  python3 "$DEST/scripts/form_cli_rag.py" build && ok "index built — add local docs later: form-cli index --docs ~/your-folder"
else
  echo "  skipped — needs ollama + nomic-embed-text. Run later: form-cli index"
fi

# 6. install the Claude skill -----------------------------------------------------
say "[6/7] Claude skill (routes any question to form-cli)"
SKILL_SRC="$DEST/skills/form-cli"; SKILL_DST="$HOME/.claude/skills/form-cli"
if [ -d "$SKILL_SRC" ]; then
  mkdir -p "$HOME/.claude/skills"; cp -R "$SKILL_SRC" "$SKILL_DST" && ok "skill installed to $SKILL_DST"
else
  echo "  skill source not found (older checkout?) — skipped"
fi

# 7. put form-cli on PATH ---------------------------------------------------------
say "[7/7] the one door"
mkdir -p "$BINDIR"; ln -sf "$DEST/bin/form-cli" "$BINDIR/form-cli" && ok "linked form-cli -> $BINDIR/form-cli"
case ":$PATH:" in *":$BINDIR:"*) :;; *) echo "  add to your shell: export PATH=\"$BINDIR:\$PATH\"";; esac

say "ready"
cat <<EOF
  form-cli ask "how does the form-cli route to a local oracle?"
  form-cli index --docs ~/Documents/notes      # add your own docs
  form-cli gaps                                 # see what's open
  form-cli preflight                            # confirm you can lose the network
EOF
