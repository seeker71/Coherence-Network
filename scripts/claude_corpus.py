#!/usr/bin/env python3
# claude_corpus.py — CARRIER (data prep only). Taps Claude Code session transcripts
# (~/.claude/projects/**/*.jsonl) into (task -> tools-used) corpus turns and appends them
# to the shared tool-use corpus (~/.coherence-network/form-cli-corpus/corpus.jsonl) that
# codex_corpus.py / agent_tooluse_featurize.py already read. Claude Code sessions are
# Read/Edit/Write-heavy, so this grows exactly the low-performing tool-prediction lanes the
# sovereignty attention signal (attention-signal.fk) names. Sibling to codex_corpus.py.
#
# Privacy: stores only the task text (truncated) + the tool names used — never reasoning or
# answers — and appends to a LOCAL file (~/.coherence-network/, not git). Idempotent: a turn
# whose (task, tool-set) is already present is skipped, so re-running never duplicates.
import json, os, glob, hashlib, sys, collections

PROJECTS = os.path.expanduser("~/.claude/projects")
CORPUS = os.path.expanduser("~/.coherence-network/form-cli-corpus/corpus.jsonl")


def _human_prompt(rec):
    """A genuine human prompt (not a tool_result, which also arrives as user-role)."""
    if rec.get("type") != "user":
        return None
    m = rec.get("message", {})
    if not isinstance(m, dict) or m.get("role") != "user":
        return None
    c = m.get("content")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
        has_tool_result = any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)
        if texts and not has_tool_result:
            return " ".join(texts).strip()
    return None


def _assistant_tools(rec):
    if rec.get("type") != "assistant":
        return []
    m = rec.get("message", {})
    c = m.get("content") if isinstance(m, dict) else None
    if not isinstance(c, list):
        return []
    return [b.get("name") for b in c if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name")]


def _turns(path):
    """Yield (task, tools) per human-prompt -> assistant-tools exchange."""
    task, tools = None, []
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return
    for line in lines:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        hp = _human_prompt(rec)
        if hp is not None:
            if task and tools:
                yield task, tools
            task, tools = hp, []
            continue
        tools.extend(_assistant_tools(rec))
    if task and tools:
        yield task, tools


def _key(task, tools):
    body = task + "|" + ",".join(sorted({t for t in tools if t}))
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def main():
    dry = "--dry-run" in sys.argv
    seen = set()
    if os.path.exists(CORPUS):
        for line in open(CORPUS, encoding="utf-8"):
            try:
                e = json.loads(line)
                seen.add(_key(e.get("task", ""), [s.get("tool") for s in e.get("steps", [])]))
            except Exception:
                pass

    files = [f for f in glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True)
             if "Coherence-Network" in f]
    added, lane = 0, collections.Counter()
    os.makedirs(os.path.dirname(CORPUS), exist_ok=True)
    out = None if dry else open(CORPUS, "a", encoding="utf-8")
    for f in files:
        for task, tools in _turns(f):
            task = task[:1500]  # truncate FIRST so the dedup key matches what is stored (idempotent)
            k = _key(task, tools)
            if k in seen:
                continue
            seen.add(k)
            rec = {
                "task": task, "oracle": "claude", "outcome": "success",
                "source": "claude-transcript",
                "steps": [{"tool": t} for t in tools],
                "task_sig": hashlib.sha1(task.encode("utf-8")).hexdigest()[:16],
            }
            if out:
                out.write(json.dumps(rec) + "\n")
            added += 1
            for t in set(tools):
                lane[t] += 1
    if out:
        out.close()
    print(f"[claude corpus] {len(files)} session(s) -> {added} new turns"
          f"{' (dry-run, not written)' if dry else ' -> ' + CORPUS}")
    for t, n in lane.most_common(12):
        print(f"  {t:<26} {n} turns")


if __name__ == "__main__":
    main()
