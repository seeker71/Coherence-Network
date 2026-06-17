#!/usr/bin/env bash
# form_cli_roadmap.sh — list the floor->north-star steps and the next one to build.
#
# The steps and the queries (total / open / next) are roadmap.fk on the kernel
# (four-way); this carrier only formats. For an OPEN step that is a closable recipe
# gap, the printed spec is what you hand to form_cli_close_gap.sh — a LOCAL oracle
# drafts the recipe, the LOCAL kernel validates it. No remote LLM, fully offline.
#
# Usage: form_cli_roadmap.sh            # the whole tower, done + open, next named
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

prog="$(mktemp)"
{ cat "$STD/roadmap.fk"
  echo '(defn rm-emit (rows) (if (eq (len rows) 0) 0 (do (print (rm-id (head rows))) (print (rm-phase (head rows))) (print (rm-status (head rows))) (print (rm-title (head rows))) (rm-emit (tail rows)))))'
  echo '(rm-emit (rm-seed))'
  echo '(print "===")'
  echo '(print (rm-open-count (rm-seed)))'
  echo '(print (rm-id (rm-next-open (rm-seed))))'
  echo '(print (rm-title (rm-next-open (rm-seed))))'
  echo '(print (rm-spec (rm-next-open (rm-seed))))'
} > "$prog"
out="$("$GO" "$prog" 2>/dev/null | sed '/^null$/d')"; rm -f "$prog"

echo "── floor → north-star (roadmap.fk on the kernel) ──"
# steps: 4 lines each (id, phase, status, title) until the === marker
printf '%s\n' "$out" | awk '
  /^===$/ {body=1; next}
  !body {
    n=(NR-1)%4
    if (n==0) id=$0
    else if (n==1) phase=$0
    else if (n==2) status=$0
    else { mark=(status=="done")?"✓":"○"; printf "  %s  [%s] %-12s %s\n", mark, phase, id, $0 }
    next
  }
  body && tail==0 {open=$0; tail=1; next}
  body && tail==1 {nid=$0; tail=2; next}
  body && tail==2 {ntitle=$0; tail=3; next}
  body && tail==3 {nspec=$0; tail=4;
    printf "\n  open: %s   next to build: %s — %s\n", open, nid, ntitle
    printf "  spec: %s\n", nspec
    printf "  build it offline:  form-cli close \"%s\" \"<recipe-spec>\" \"<assert>\" \"<expected>\" \"ollama run coder\"\n", nid
  }
'
