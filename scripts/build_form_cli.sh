#!/usr/bin/env bash
# build_form_cli.sh — build the COMPILED, self-contained form-cli native binary and install it.
#
# The form-cli logic is Form recipes; this bakes them into the kernel binary (go:embed) so the
# result is a single native executable with the recipes inside — no repo tree, no bash/python glue
# for the core (repl/ask+/do/eval). Host-carrier commands (stats/train/shadow) delegate to the repo
# dispatcher (they need GPU/files by nature). Re-run after editing any embedded recipe.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KDIR="$ROOT/form/form-kernel-go"
STD="$ROOT/form/form-stdlib"
DEST="${1:-$HOME/.local/bin/form-cli}"

# 1. regenerate the embedded recipe bundle from the source recipes (the binary's baked-in body)
mkdir -p "$KDIR/fcli_embed"
cat "$STD/form-cli-router.fk" "$STD/form-cli-judge.fk" "$STD/form-cli-sufficiency.fk" \
    "$STD/form-cli-ask.fk" "$STD/form-cli-repl.fk" "$STD/form-native-run.fk" \
    > "$KDIR/fcli_embed/bundle.fk"
echo "  embedded bundle: $(grep -c '(defn ' "$KDIR/fcli_embed/bundle.fk") recipes, $(wc -c < "$KDIR/fcli_embed/bundle.fk" | tr -d ' ') bytes"

# 2. compile (the binary must be NAMED form-cli to trigger the embedded mode)
( cd "$KDIR" && go build -o form-cli . )
echo "  compiled: $(ls -lh "$KDIR/form-cli" | awk '{print $5}') native arm64"

# 3. install to a stable path (a real binary — survives worktree cleanup)
mkdir -p "$(dirname "$DEST")"
rm -f "$DEST"
cp "$KDIR/form-cli" "$DEST"
echo "  installed → $DEST"
echo "  try:  form-cli eval '(mul 6 7)'   |   form-cli ask+ \"...\"   |   form-cli do \"...\"   |   form-cli  (repl)"
