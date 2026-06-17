---
name: walk-g1-g7
description: "Walk the floor->north-star roadmap (self-growing-machine.form G1-G7) using ONLY form-cli — nothing else. For each open step: form-cli roadmap (the plan) -> form-cli asm (learn LLVM's lowering offline from clang) -> form-cli close (a LOCAL oracle drafts the recipe, the kernel validates) -> validate.sh four-way -> ship. Measure: how many times the loop had to escalate to a REMOTE oracle (claude -p) vs stay local; how many steps shipped; and for each that did not ship, why not and the smallest fix to form-cli that would let it. Use to drive an offline self-build session and produce an honest report. Triggers on: walk the roadmap, G1 to G7, build the lever via form-cli, form-lower lever, offline self-build, can form-cli ship a step."
metadata:
  {
    "openclaw":
      {
        "emoji": "🧗",
        "requires": { "bins": ["form-cli", "ollama"] }
      }
  }
---

# walk-g1-g7 — build the tower with only form-cli

The discipline: **only `form-cli` subcommands.** No hand-written recipes, no Edit/Write,
no remote LLM unless the loop itself escalates. Local oracle is `ollama run coder`
(or `qwen2.5:72b`); the remote tier is `claude -p` and every use of it is COUNTED.

## The loop, per open step

```bash
form-cli roadmap                     # the plan; read the next open step + its spec
form-cli asm "<C for the construct>" # learn LLVM's lowering offline (clang, local)
form-cli close "<id>" "<spec informed by the asm>" "<assert>" "<expected>" "ollama run coder"
# close: a LOCAL oracle drafts the recipe; the kernel validates it against the assert.
# if it validates -> register a band + run: cd form && ./validate.sh ... (four-way) -> ship.
# if it does not -> record WHY, do not hand-write the fix; the point is to find what
#   form-cli itself still lacks.
```

## What to measure and report

- **remote calls**: count every time the loop used `claude -p` (target: 0).
- **shipped**: how many steps produced a four-way-validated recipe via form-cli alone.
- **for each not shipped**: the exact reason (the kernel error, the missing capability),
  and the smallest fix *to form-cli* that would let it ship next time.

## The honest frame

A step "shipped via form-cli" only if a `form-cli` command (not the operator) produced
the validated recipe. If the operator had to write the recipe by hand, that step did
NOT ship via form-cli — record it as a gap in form-cli and name the fix. The report's
value is the gap list + fixes, not a green count.
