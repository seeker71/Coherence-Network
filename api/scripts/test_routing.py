#!/usr/bin/env python3
"""Test routing plan: verify each task_type routes to expected provider/model.

Usage:
  python scripts/test_routing.py [base_url]

Checks GET /api/agent/route for each task_type and GET /api/agent/usage.
"""

import os
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"))
except ImportError:
    pass

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("AGENT_API_BASE", "http://localhost:8000")

# Expected per MODEL-ROUTING.md
EXPECTED = {
    "spec": ("local", "ollama", "qwen3-coder", "granite", "nemotron"),
    "test": ("local", "ollama", "qwen3-coder", "granite", "nemotron"),
    "impl": ("local", "ollama", "qwen3-coder", "granite", "nemotron"),
    "review": ("local", "ollama", "qwen3-coder", "granite", "nemotron"),
    "heal": ("subscription", "claude"),
}


def main():
    print("=== Routing plan test ===\n")
    print(f"API: {BASE}")
    print(f"OLLAMA_MODEL: {os.environ.get('OLLAMA_MODEL', 'default')}\n")

    with httpx.Client(timeout=10.0) as c:
        # 1. Route each task_type
        print("1. Route check")
        for tt in ["spec", "test", "impl", "review", "heal"]:
            r = c.get(f"{BASE}/api/agent/route", params={"task_type": tt})
            if r.status_code != 200:
                print(f"   {tt}: API error {r.status_code}")
                continue
            d = r.json()
            model = d.get("model", "")
            tier = d.get("tier", "")
            ok = any(k in model.lower() or k in tier.lower() for k in EXPECTED[tt])
            print(f"   {tt}: model={model} tier={tier} {'✓' if ok else '?'}")

        # 2. Usage endpoint
        print("\n2. Usage endpoint")
        r = c.get(f"{BASE}/api/agent/usage")
        if r.status_code == 200:
            d = r.json()
            print(f"   by_model: {list(d.get('by_model', {}).keys()) or '(none)'}")
            for t, cfg in d.get("routing", {}).items():
                print(f"   {t}: {cfg.get('model')} ({cfg.get('tier')})")
        else:
            print(f"   {r.status_code} {r.text[:100]}")

        # 3. Create one task per type, check usage
        print("\n3. Create tasks, verify usage")
        for tt in ["spec", "impl", "heal"]:
            r = c.post(
                f"{BASE}/api/agent/tasks",
                json={"direction": f"Routing test {tt}", "task_type": tt},
            )
            if r.status_code == 201:
                task = r.json()
                print(f"   {tt}: task {task['id'][:16]}... -> {task['model']}")

        r = c.get(f"{BASE}/api/agent/usage")
        if r.status_code == 200:
            by_model = r.json().get("by_model", {})
            for m, u in by_model.items():
                print(f"   Usage {m}: {u.get('count')} tasks")

    print("\nDone. Message bot with /usage to see usage in Telegram.")


if __name__ == "__main__":
    main()
