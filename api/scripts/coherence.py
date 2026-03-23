#!/usr/bin/env python3
"""coherence — CLI for the Coherence Network.

A node in the network. Browse ideas, contribute, invest, run tasks,
and connect with others — all from the terminal.

Usage:
    coherence                     Interactive mode
    coherence ideas               Browse ideas
    coherence idea <id>           View an idea
    coherence share               Share a new idea
    coherence ask <id>            Ask a question on an idea
    coherence stake <id> <cc>     Stake CC on an idea
    coherence fork <id>           Fork an idea
    coherence contribute          Record a contribution
    coherence tasks               See active tasks
    coherence run                 Pick up and execute pending tasks
    coherence node                Show this node's identity
    coherence providers           Show available providers
    coherence resonance           Show what's alive right now
    coherence status              Network status
    coherence identity            Manage your identity
    coherence help                Show this help
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

# Add api/ to path
_API_DIR = Path(__file__).resolve().parent.parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)


def _hub() -> str:
    try:
        from app.services.config_service import get_hub_url
        return get_hub_url()
    except Exception:
        return os.environ.get("COHERENCE_HUB_URL", "https://api.coherencycoin.com")


def _get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        r = httpx.get(f"{_hub()}{path}", params=params, timeout=10)
        return r.json() if r.is_success else None
    except Exception as e:
        print(f"  Connection failed: {e}")
        return None


def _post(path: str, data: dict) -> dict | None:
    try:
        r = httpx.post(f"{_hub()}{path}", json=data, timeout=15)
        return r.json() if r.is_success else None
    except Exception as e:
        print(f"  Connection failed: {e}")
        return None


def _name() -> str:
    """Get contributor name from config or ask."""
    config_path = Path.home() / ".coherence-network" / "config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            name = data.get("contributor_id", "")
            if name:
                return name
        except Exception:
            pass
    return os.environ.get("COHERENCE_CONTRIBUTOR", "anonymous")


def _wrap(text: str, width: int = 72, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


# ── Commands ──────────────────────────────────────────────────────────


def cmd_ideas(args):
    """Browse ideas in the network."""
    data = _get("/api/ideas")
    if not data:
        print("  Could not reach the network.")
        return

    ideas = data.get("ideas", data) if isinstance(data, dict) else data
    print(f"\n  {len(ideas)} ideas in the network\n")

    for i, idea in enumerate(sorted(ideas, key=lambda x: (x["potential_value"] - x["actual_value"]) / (x["estimated_cost"] or 1), reverse=True), 1):
        gap = idea["potential_value"] - idea["actual_value"]
        roi = gap / (idea["estimated_cost"] or 1)
        status = idea.get("manifestation_status", "?")
        state = {"none": "○", "partial": "◐", "complete": "●"}.get(status, "?")

        print(f"  {state} {i:2}. {idea['name']}")
        print(f"      {gap:.0f} CC gap · {roi:.1f}x ROI · {status}")
        if i <= 5:
            print(_wrap(idea["description"][:120], indent="      "))
        print()


def cmd_idea(args):
    """View a single idea in detail."""
    idea_id = args.id
    data = _get(f"/api/ideas/{idea_id}")
    if not data:
        # Try searching by name fragment
        all_ideas = _get("/api/ideas")
        if all_ideas:
            ideas = all_ideas.get("ideas", all_ideas) if isinstance(all_ideas, dict) else all_ideas
            matches = [i for i in ideas if idea_id.lower() in i["id"].lower() or idea_id.lower() in i["name"].lower()]
            if len(matches) == 1:
                data = matches[0]
            elif matches:
                print(f"\n  Multiple matches for '{idea_id}':")
                for m in matches:
                    print(f"    {m['id']}: {m['name']}")
                return
        if not data:
            print(f"\n  Idea '{idea_id}' not found.")
            return

    gap = data["potential_value"] - data["actual_value"]
    roi = gap / (data["estimated_cost"] or 1)

    print(f"\n  {data['name']}")
    print(f"  {'─' * len(data['name'])}")
    print(_wrap(data["description"]))
    print()
    print(f"  Status:    {data.get('manifestation_status', '?')}")
    print(f"  Value gap: {gap:.0f} CC")
    print(f"  ROI:       {roi:.1f}x")
    print(f"  Cost:      {data['estimated_cost']:.0f} CC")
    print(f"  Confidence:{data['confidence']:.0%}")

    questions = data.get("open_questions", [])
    if questions:
        print(f"\n  Open questions ({len(questions)}):")
        for q in questions:
            print(f"    ? {q['question'][:80]}")

    print(f"\n  View online: https://coherencycoin.com/ideas/{data['id']}")
    print(f"  Share:       coherence share {data['id']}")
    print(f"  Stake:       coherence stake {data['id']} 10")
    print()


def cmd_share(args):
    """Share a new idea."""
    print("\n  Share an idea with the network\n")

    name = input("  Name (few words): ").strip()
    if not name:
        print("  Cancelled.")
        return

    desc = input("  Description (what and why): ").strip()
    if not desc:
        print("  Cancelled.")
        return

    slug = name.lower().replace(" ", "-")[:50]
    value = input("  Potential value (1-100, default 50): ").strip()
    cost = input("  Estimated cost (1-100, default 10): ").strip()

    idea = {
        "id": slug,
        "name": name,
        "description": desc,
        "potential_value": int(value) if value.isdigit() else 50,
        "estimated_cost": int(cost) if cost.isdigit() else 10,
        "resistance_risk": 3,
        "confidence": 0.7,
        "manifestation_status": "none",
    }

    result = _post("/api/ideas", idea)
    if result:
        print(f"\n  ✓ Your idea is live!")
        print(f"    https://coherencycoin.com/ideas/{result.get('id', slug)}")
    else:
        print("\n  Could not share. The network might be down.")


def cmd_ask(args):
    """Ask a question on an idea."""
    question = input(f"\n  Your question about {args.id}: ").strip()
    if not question:
        print("  Cancelled.")
        return

    result = _post(f"/api/ideas/{args.id}/questions", {
        "question": question,
        "value_to_whole": 10,
        "estimated_cost": 1,
    })
    if result:
        print("\n  ✓ Question posted. It's now visible to everyone exploring this idea.")
    else:
        print("\n  Could not post. Check the idea ID.")


def cmd_stake(args):
    """Stake CC on an idea."""
    result = _post(f"/api/ideas/{args.id}/stake", {
        "contributor_id": _name(),
        "amount_cc": float(args.amount),
        "rationale": f"Staked via CLI by {_name()}",
    })
    if result:
        tasks = result.get("tasks_created", [])
        print(f"\n  ✓ Staked {args.amount} CC on {args.id}")
        if tasks:
            print(f"    {len(tasks)} task(s) created:")
            for t in tasks:
                print(f"      {t.get('task_type', '?')}: {t.get('direction', '?')[:60]}")
        print(f"\n    Your stake triggers real compute. Watch progress:")
        print(f"    https://coherencycoin.com/ideas/{args.id}")
    else:
        print(f"\n  Could not stake. Check the idea ID.")


def cmd_fork(args):
    """Fork an idea."""
    notes = input(f"\n  How would you take {args.id} differently? ").strip()
    result = _post(f"/api/ideas/{args.id}/fork", {
        "forker_id": _name(),
        "adaptation_notes": notes or "Exploring a different direction",
    })
    if result:
        new_id = result.get("new_idea", {}).get("id", "?")
        print(f"\n  ✓ Forked! Your version: {new_id}")
        print(f"    The original author keeps credit through lineage.")
    else:
        print(f"\n  Could not fork. Check the idea ID.")


def cmd_contribute(args):
    """Record a contribution."""
    print("\n  Record a contribution\n")
    print("  What did you do? Examples: wrote a blog post, shared on social media,")
    print("  ran a workshop, mentored someone, asked a good question, thought deeply\n")

    ctype = input("  Type (any word): ").strip() or "contribution"
    desc = input("  Description: ").strip()
    amount = input("  CC value (default 5): ").strip()
    idea_id = input("  For which idea? (optional, press enter to skip): ").strip()

    result = _post("/api/contributions/record", {
        "contributor_id": _name(),
        "type": ctype,
        "amount_cc": float(amount) if amount else 5.0,
        "idea_id": idea_id or None,
        "metadata": {"description": desc} if desc else None,
    })
    if result:
        print(f"\n  ✓ Recorded. Thank you for contributing.")
    else:
        print("\n  Could not record. The network might be down.")


def cmd_tasks(args):
    """See active and recent tasks."""
    active = _get("/api/agent/tasks/active")
    recent = _get("/api/agent/tasks/activity", {"limit": 10})

    if active:
        tasks = active if isinstance(active, list) else active.get("tasks", [])
        if tasks:
            print(f"\n  {len(tasks)} task(s) executing now:\n")
            for t in tasks:
                print(f"  ⚡ {t.get('task_id', '?')[:16]}")
                print(f"     Node: {t.get('node_name', '?')} · Provider: {t.get('provider', '?')}")
                print(f"     Watch: https://coherencycoin.com/tasks/{t.get('task_id', '')}")
                print()
        else:
            print("\n  No tasks executing right now.\n")

    if recent:
        events = recent if isinstance(recent, list) else recent.get("events", [])
        if events:
            print(f"  Recent activity:")
            for e in events[:10]:
                icon = {"completed": "✓", "failed": "✗", "claimed": "→", "executing": "⚡"}.get(e.get("event_type", ""), "·")
                print(f"    {icon} {e.get('event_type', '?'):10} {e.get('task_id', '?')[:16]} via {e.get('provider', '?')}")
            print()


def cmd_run(args):
    """Run the local task runner."""
    print("\n  Starting local runner...\n")
    runner = Path(__file__).parent / "local_runner.py"
    timeout = getattr(args, "timeout", 300)
    os.execvp(sys.executable, [sys.executable, str(runner), "--timeout", str(timeout)])


def cmd_node(args):
    """Show this node's identity."""
    try:
        from app.services.node_identity_service import get_or_create_node_id, get_node_metadata
        node_id = get_or_create_node_id()
        meta = get_node_metadata()
        print(f"\n  Node: {node_id}")
        print(f"  Host: {meta.get('hostname', '?')}")
        print(f"  OS:   {meta.get('os_type', '?')}")
        print(f"  Providers: {', '.join(meta.get('providers', [])) or 'detecting...'}")
    except Exception:
        print("\n  Run from the api/ directory to see node info.")


def cmd_providers(args):
    """Show available providers and their stats."""
    try:
        from app.services.slot_selection_service import SlotSelector
        available = ["claude", "codex", "gemini", "cursor", "ollama-local", "ollama-cloud"]
        print("\n  Provider stats:\n")
        for tt in ["spec", "impl", "test", "review"]:
            s = SlotSelector(f"provider_{tt}")
            stats = s.stats(available)
            slots = stats.get("slots", {})
            active = {k: v for k, v in slots.items() if v.get("sample_count", 0) > 0}
            if active:
                print(f"  {tt}:")
                for name in sorted(active, key=lambda x: active[x].get("mean_value", 0), reverse=True):
                    si = active[name]
                    print(f"    {name:15} {si['mean_value']:.0%} success · {si['sample_count']} runs · {si.get('mean_duration_s',0):.0f}s avg")
                print()
    except Exception:
        # Fall back to API
        data = _get("/api/providers/stats")
        if data:
            providers = data.get("providers", {})
            print("\n  Provider stats:\n")
            for name, p in sorted(providers.items(), key=lambda x: x[1].get("total_runs", 0), reverse=True):
                rate = p.get("success_rate", 0)
                print(f"    {name:15} {rate:.0%} · {p.get('total_runs', 0)} runs · {p.get('avg_duration_s', 0):.0f}s")
            print()
        else:
            print("\n  No provider data available.")


def cmd_resonance(args):
    """Show what's alive right now."""
    data = _get("/api/ideas/resonance", {"window_hours": 72})
    ideas = data if isinstance(data, list) else (data.get("ideas", []) if data else [])

    if ideas:
        print(f"\n  {len(ideas)} ideas with recent activity:\n")
        for i in ideas[:10]:
            print(f"  ◉ {i.get('name', '?')}")
            print(f"    Energy: {i.get('free_energy_score', 0):.1f} · Last: {i.get('last_activity_at', '?')[:10]}")
            print()
    else:
        # Fallback to top ideas
        all_data = _get("/api/ideas")
        if all_data:
            ideas = all_data.get("ideas", [])
            top = sorted(ideas, key=lambda x: x.get("free_energy_score", 0), reverse=True)[:5]
            print(f"\n  Top ideas by energy:\n")
            for i in top:
                gap = i["potential_value"] - i["actual_value"]
                print(f"  ◉ {i['name']}")
                print(f"    {gap:.0f} CC gap · {i.get('manifestation_status', '?')}")
                print()


def cmd_status(args):
    """Network status."""
    health = _get("/api/health")
    if not health:
        print("\n  Cannot reach the network.")
        return

    print(f"\n  Network: {health.get('status', '?')}")
    print(f"  Uptime:  {health.get('uptime_human', '?')}")

    nodes = _get("/api/federation/nodes")
    if nodes:
        node_list = nodes if isinstance(nodes, list) else []
        print(f"  Nodes:   {len(node_list)}")
        for n in node_list:
            print(f"    {n.get('hostname', '?')} ({n.get('os_type', '?')}) — {n.get('status', '?')}")

    stats = _get("/api/federation/nodes/stats")
    if stats:
        print(f"  Measurements: {stats.get('total_measurements', 0)}")

    ideas = _get("/api/ideas")
    if ideas:
        idea_list = ideas.get("ideas", []) if isinstance(ideas, dict) else ideas
        total_val = sum(i["potential_value"] for i in idea_list)
        actual_val = sum(i["actual_value"] for i in idea_list)
        print(f"  Ideas:   {len(idea_list)} ({actual_val:.0f} / {total_val:.0f} CC realized)")
    print()


def cmd_identity(args):
    """Manage your identity."""
    name = _name()
    print(f"\n  Contributor: {name}")

    identities = _get(f"/api/identity/{name}")
    if identities:
        id_list = identities if isinstance(identities, list) else identities.get("identities", [])
        if id_list:
            print(f"  Linked accounts:")
            for ident in id_list:
                verified = "✓" if ident.get("verified") else "○"
                print(f"    {verified} {ident.get('provider', '?')}: {ident.get('provider_id', '?')}")
        else:
            print("  No linked accounts.")
    print(f"\n  Manage: https://coherencycoin.com/identity")
    print()


def cmd_help(args=None):
    print(__doc__)


# ── Main ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="coherence — a node in the Coherence Network",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ideas", help="Browse ideas")

    p_idea = sub.add_parser("idea", help="View an idea")
    p_idea.add_argument("id", help="Idea ID or name fragment")

    sub.add_parser("share", help="Share a new idea")

    p_ask = sub.add_parser("ask", help="Ask a question")
    p_ask.add_argument("id", help="Idea ID")

    p_stake = sub.add_parser("stake", help="Stake CC on an idea")
    p_stake.add_argument("id", help="Idea ID")
    p_stake.add_argument("amount", help="CC amount")

    p_fork = sub.add_parser("fork", help="Fork an idea")
    p_fork.add_argument("id", help="Idea ID")

    sub.add_parser("contribute", help="Record a contribution")
    sub.add_parser("tasks", help="See active tasks")

    p_run = sub.add_parser("run", help="Execute pending tasks")
    p_run.add_argument("--timeout", type=int, default=300, help="Task timeout (default 300s)")

    sub.add_parser("node", help="This node's identity")
    sub.add_parser("providers", help="Provider stats")
    sub.add_parser("resonance", help="What's alive now")
    sub.add_parser("status", help="Network status")
    sub.add_parser("identity", help="Manage identity")
    sub.add_parser("help", help="Show help")

    args = parser.parse_args()

    commands = {
        "ideas": cmd_ideas,
        "idea": cmd_idea,
        "share": cmd_share,
        "ask": cmd_ask,
        "stake": cmd_stake,
        "fork": cmd_fork,
        "contribute": cmd_contribute,
        "tasks": cmd_tasks,
        "run": cmd_run,
        "node": cmd_node,
        "providers": cmd_providers,
        "resonance": cmd_resonance,
        "status": cmd_status,
        "identity": cmd_identity,
        "help": cmd_help,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        cmd_help()


if __name__ == "__main__":
    main()
