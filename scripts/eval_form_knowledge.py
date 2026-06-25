#!/usr/bin/env python3
"""Honest base-vs-tuned eval for the Form-knowledge teacher fine-tune.

Asks a held-out set of Form questions to two ollama models (the base and the
fine-tuned form model) over Ollama's /api/generate teacher wire, and scores each
answer by deterministic keyphrase coverage: each question has a set of required
facts (any-of groups) drawn from the body. An answer scores the
fraction of fact-groups it covers. This is deterministic and reproducible -- no
LLM judge, no fabricated numbers.

This is not the `form-cli ask` runtime path. `form-cli ask` is native fkwu
grounded RAG and must not be evaluated as an Ollama/HTTP local oracle.

The eval questions are NOT in the training corpus (they are paraphrases / new
angles on body facts), so this measures generalization, not memorization.

Usage:
    python3 scripts/eval_form_knowledge.py --base llama3.2:3b --tuned form-llama
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

# Each item: question + list of fact-groups. A fact-group is a list of
# acceptable substrings (case-insensitive, any-of). The answer covers the group
# if it contains ANY member. Score = covered_groups / total_groups.
EVAL: list[dict] = [
    {"q": "Explain what a Blueprint NodeID is and what it is made of.",
     "facts": [["structural identity", "what something is", "what it is"],
               ["package", "node-id", "nodeid"],
               ["same", "equivalent", "shape"]]},
    {"q": "How are SUBSTANCE and STATE related in the substrate?",
     "facts": [["orthogonal", "two axes", "separate", "independent"],
               ["any kind", "can be", "any state"],
               ["blueprint", "recipe", "namedcell", "ice", "water", "gas"]]},
    {"q": "Describe the three thermodynamic states a cell can be in.",
     "facts": [["ice", "frozen"],
               ["water", "fluid", "circulat"],
               ["gas", "diffuse", "potential"]]},
    {"q": "When a cell freezes from water to ice, what stays the same?",
     "facts": [["nodeid", "node-id", "identity"],
               ["kind", "substance", "conserv"]]},
    {"q": "What are the five core axioms?",
     "facts": [["state", "0", "1", "nothing"],
               ["cell", "node-id", "nodeid"],
               ["content-address", "composition", "identity"],
               ["boundary", "interface", "offer"],
               ["offer", "acknowledg", "run"]]},
    {"q": "Is the ability of the system to safely change itself an axiom or something derived?",
     "facts": [["theorem", "derived", "not an axiom"],
               ["self", "change", "update"]]},
    {"q": "What does the Form kernel serve, and what header marks a native route?",
     "facts": [["x-form-router", "native-kernel", "native kernel"],
               ["kernel", "front door", "route", "http"]]},
    {"q": "What is Python's job in this architecture?",
     "facts": [["fan-out", "fanout", "scatter", "query carrier"],
               ["never", "not", "body", "nothing more"]]},
    {"q": "When should I use the substrate instead of my conversation context?",
     "facts": [["structural", "shape", "equivalen"],
               ["lexical", "git", "name", "context"]]},
    {"q": "Why must I never write (and a b c) in Form?",
     "facts": [["binary", "two", "third"],
               ["nest", "(and (and", "divergen"]]},
    {"q": "What is the trap with (empty x) in Form?",
     "facts": [["construct", "not a predicate", "absence", "empty list"],
               ["truthy", "(eq (len", "len"]]},
    {"q": "How do I express a less-than comparison in the curated Form band primitives?",
     "facts": [["(gt b a)", "gt b a", "flip", "gt"],
               ["no lt", "without lt", "recursion", "no sub"]]},
    {"q": "Name the four phase transitions in the substrate.",
     "facts": [["condense"], ["freeze"], ["melt"], ["sublimat"]]},
    {"q": "What is the difference between an fkwu divergence and an unsupported op?",
     "facts": [["divergen", "different answer", "wrong"],
               ["unsupported", "op family", "lacks", "3-kernel", "limitation"],
               ["hard gate", "before merge", "correctness", "named gap"]]},
    {"q": "How does form-cli ask answer locally now?",
     "facts": [["fkwu", "native"],
               ["rag", "grounded", "index"],
               ["no http", "not ollama", "no localhost", "not localhost", "no 11434", "not http-fetch"]]},
    {"q": "In the Coherence Network repo, when a new agent has little context, what file should it start with?",
     "facts": [["docs/shared/agent-start-packet.md", "agent-start-packet"],
               ["new agent", "little context", "start"]]},
    {"q": "In Coherence Network AGENTS.md, what command senses the body on arrival?",
     "facts": [["make wellness"],
               ["body", "arrival", "sense", "senses"]]},
    {"q": "In Coherence Network, what command name is used for Form-first local reasoning before spending a rented frontier model?",
     "facts": [["form-cli ask"],
               ["before", "rented", "frontier", "oracle"]]},
    {"q": "What is the proof floor for a new Form band?",
     "facts": [["go", "rust", "typescript"],
               ["fkwu", "fourth arm", "four-way", "four way"]]},
    {"q": "Write a Form recipe that returns the maximum of two integers.",
     "facts": [["(defn", "defn"],
               ["(if (gt", "if (gt", "gt"]]},
    {"q": "Write a Form recipe that sums a list of integers by recursion.",
     "facts": [["(defn", "defn"],
               ["(if (ge", "ge", "len"],
               ["add", "acc"]]},
    {"q": "What three counts determine a cell's state?",
     "facts": [["degree"], ["population"], ["churn"]]},
    {"q": "Can the kernel use a host's own drivers, or must everything be reimplemented natively?",
     "facts": [["may", "can", "allowed", "use"],
               ["driver", "os api", "kernel api", "carrier"],
               ["measure", "health", "not", "optional", "never a must", "choice"]]},
]


def ollama_generate(model: str, prompt: str, host: str, timeout: int = 120) -> str:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(f"{host}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("response", "")


def score(answer: str, facts: list[list[str]]) -> float:
    a = answer.lower()
    if not facts:
        return 0.0
    covered = sum(1 for grp in facts if any(s.lower() in a for s in grp))
    return covered / len(facts)


def run_model(model: str, host: str) -> tuple[float, list[tuple[str, float, str]]]:
    rows = []
    total = 0.0
    for item in EVAL:
        ans = ollama_generate(model, item["q"], host)
        sc = score(ans, item["facts"])
        total += sc
        rows.append((item["q"], sc, ans))
    return total / len(EVAL), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="llama3.2:3b")
    ap.add_argument("--tuned", default="form-llama")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print(f"Eval set: {len(EVAL)} held-out Form questions (keyphrase-coverage scoring)\n")
    base_avg, base_rows = run_model(args.base, args.host)
    tuned_avg, tuned_rows = run_model(args.tuned, args.host)

    print(f"{'question':<60} {'base':>6} {'tuned':>6}")
    print("-" * 74)
    for (q, bs, ba), (_, ts, ta) in zip(base_rows, tuned_rows):
        print(f"{q[:58]:<60} {bs*100:>5.0f}% {ts*100:>5.0f}%")
        if args.verbose:
            print(f"    BASE : {ba[:140].strip()!r}")
            print(f"    TUNED: {ta[:140].strip()!r}")
    print("-" * 74)
    print(f"{'AVERAGE':<60} {base_avg*100:>5.1f}% {tuned_avg*100:>5.1f}%")
    lift = (tuned_avg - base_avg) * 100
    print(f"\nLift: base {base_avg*100:.1f}%  ->  tuned {tuned_avg*100:.1f}%  ({lift:+.1f} points)")

    # also dump JSON for the repo eval artifact
    out = {
        "eval_size": len(EVAL),
        "scoring": "keyphrase-coverage (deterministic, any-of fact groups)",
        "base_model": args.base, "tuned_model": args.tuned,
        "base_avg": round(base_avg, 4), "tuned_avg": round(tuned_avg, 4),
        "lift_points": round(lift, 2),
        "per_question": [
            {"q": q, "base": round(bs, 3), "tuned": round(ts, 3)}
            for (q, bs, _), (_, ts, _) in zip(base_rows, tuned_rows)
        ],
    }
    print("\n--- JSON ---")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
