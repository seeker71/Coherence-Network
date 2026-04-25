#!/usr/bin/env python3
from __future__ import annotations
"""cc — Coherence Network CLI.

Two-way bridge between any agent (OpenClaw, Claude, Codex, Cursor) and
the Coherence Network. Browse ideas, contribute, stake, check status,
run a node — all from the command line.

Usage:
  cc ideas                    List ideas sorted by free energy score
  cc status                   Network status (coherence score, nodes, tasks)
  cc idea <id>                Show idea details + tasks
  cc share <name> <desc>      Share a new idea
  cc ask <idea_id> <question> Ask a question on an idea
  cc stake <idea_id> <amount> Stake CC on an idea
  cc specs                    List registered specs
  cc tasks [--status pending] List tasks
  cc nodes                    List federation nodes
  cc contribute <type> <desc> Record a contribution
  cc coherence                Show coherence score breakdown
  cc run                      Start local node runner

  cc members <workspace_id>              List workspace members
  cc invite <ws_id> <contributor> [--role member]  Invite to workspace
  cc my-workspaces <contributor_id>      List contributor workspaces

  cc send <from> <to> <body> [--subject] Send a direct message
  cc inbox <contributor_id>              Show inbox
  cc thread <contributor_a> <contributor_b>  Show message thread

  cc activity <workspace_id> [--limit 20]  Show workspace activity feed

  cc projects <workspace_id>             List workspace projects
  cc project <project_id>                Show project details
  cc create-project <ws_id> <name> [--description]  Create a project

  cc news [--limit 20]                   Show news feed
  cc news-resonance [--top 5]            Show news matched to ideas
  cc federation                          Show federation nodes
  cc beliefs [contributor_id]            Show belief profile or network stats
  cc peers <contributor_id>              Find resonant peers
  cc cc-supply                           Show CC economics
  cc governance [--limit 20]             List governance change requests

  cc frequency <concept_id>              Score concept for living vs institutional frequency
  cc frequency --file path.md            Score any file for frequency
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

CONFIG_PATH = Path.home() / ".coherence-network" / "config.json"
API_BASE = "https://api.coherencycoin.com"
API_KEY = "dev-key"

_client = httpx.Client(timeout=30.0, headers={"X-Api-Key": API_KEY})


def _api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    url = f"{API_BASE}{path}"
    try:
        if method == "GET":
            r = _client.get(url)
        elif method == "POST":
            r = _client.post(url, json=body)
        elif method == "PATCH":
            r = _client.patch(url, json=body)
        else:
            return None
        if r.status_code >= 400:
            print(f"Error: {r.status_code} {r.text[:200]}", file=sys.stderr)
            return None
        return r.json() if r.text.strip() else None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def _fmt_cc(v: float) -> str:
    return f"{v:,.0f} CC" if v >= 1 else f"{v:.2f} CC"


def _resolve_contributor_id(cli_arg: str | None) -> str:
    """Resolve contributor identity from explicit arg, then config.json, then anonymous."""
    if cli_arg and str(cli_arg).strip():
        return str(cli_arg).strip()
    try:
        if CONFIG_PATH.exists():
            payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                contributor_id = str(payload.get("contributor_id") or "").strip()
                if contributor_id:
                    return contributor_id
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        pass
    return "anonymous"


# ── Commands ──────────────────────────────────────────────────────────

def cmd_status(_args):
    """Network status overview."""
    score_data = _api("GET", "/api/coherence/score")
    ideas = _api("GET", "/api/ideas?limit=100")
    nodes = _api("GET", "/api/federation/nodes")

    idea_list = ideas.get("ideas", ideas) if isinstance(ideas, dict) else (ideas or [])
    node_list = nodes if isinstance(nodes, list) else (nodes or {}).get("nodes", [])

    if score_data and isinstance(score_data, dict):
        print(f"Coherence: {score_data.get('score', '?'):.2f}  ({score_data.get('signals_with_data', '?')}/{score_data.get('total_signals', '?')} signals)")
    print(f"Ideas:     {len(idea_list)}")
    print(f"Nodes:     {len(node_list)}")

    if score_data and isinstance(score_data, dict):
        print()
        for name, sig in score_data.get("signals", {}).items():
            s = sig.get("score", 0)
            bar = "#" * int(s * 20) + "." * (20 - int(s * 20))
            print(f"  {name:25s} [{bar}] {s:.2f}")


def cmd_ideas(_args):
    """List ideas sorted by free energy score."""
    data = _api("GET", "/api/ideas?limit=50")
    if not data:
        print("No ideas found")
        return
    ideas = data.get("ideas", data) if isinstance(data, dict) else data
    for i, idea in enumerate(ideas, 1):
        fe = idea.get("free_energy_score", 0)
        ms = idea.get("manifestation_status", "none")
        icon = {"none": ".", "partial": "~", "validated": "V"}.get(ms, "?")
        gap = idea.get("potential_value", 0) - idea.get("actual_value", 0)
        print(f"  {i:2d}. {icon} {idea['name'][:55]}")
        print(f"      FE={fe:.1f}  gap={_fmt_cc(gap)}  conf={idea.get('confidence', 0):.0%}  [{idea['id'][:20]}]")


def cmd_idea(args):
    """Show idea details."""
    data = _api("GET", f"/api/ideas/{args.idea_id}")
    if not data:
        print(f"Idea {args.idea_id} not found")
        return
    print(f"{data['name']}")
    print(f"  {data.get('description', '')[:120]}")
    print(f"  Status: {data.get('manifestation_status', 'none')}  Stage: {data.get('stage', 'none')}")
    print(f"  Value: {_fmt_cc(data.get('actual_value', 0))} / {_fmt_cc(data.get('potential_value', 0))}")
    print(f"  Confidence: {data.get('confidence', 0):.0%}")

    tasks = _api("GET", f"/api/ideas/{args.idea_id}/tasks")
    if tasks and isinstance(tasks, dict):
        groups = tasks.get("groups", [])
        if groups:
            print(f"\n  Tasks ({tasks.get('total', 0)} total):")
            for g in groups:
                sc = g.get("status_counts", {})
                print(f"    {g['task_type']:8s}  completed={sc.get('completed', 0)}  pending={sc.get('pending', 0)}  failed={sc.get('failed', 0)}")


def cmd_share(args):
    """Share a new idea."""
    idea_id = "idea-" + hashlib.sha256(args.name.encode()).hexdigest()[:12]
    body = {
        "id": idea_id,
        "name": args.name,
        "description": args.description,
        "potential_value": args.value,
        "estimated_cost": args.cost,
        "confidence": args.confidence,
    }
    result = _api("POST", "/api/ideas", body)
    if result:
        print(f"Shared: {idea_id}  {args.name}")
    else:
        print("Failed to share idea")


def cmd_ask(args):
    """Ask a question on an idea."""
    body = {
        "question": args.question,
        "value_to_whole": args.value,
        "estimated_cost": args.cost,
    }
    result = _api("POST", f"/api/ideas/{args.idea_id}/questions", body)
    if result:
        print(f"Question posted on {args.idea_id}")
    else:
        print("Failed to post question")


def cmd_stake(args):
    """Stake CC on an idea."""
    body = {
        "contributor_id": _resolve_contributor_id(args.contributor),
        "amount_cc": args.amount,
        "rationale": args.rationale or f"Staking {args.amount} CC",
    }
    result = _api("POST", f"/api/ideas/{args.idea_id}/stake", body)
    if result:
        print(f"Staked {args.amount} CC on {args.idea_id}")
    else:
        print("Failed to stake")


def cmd_tasks(args):
    """List tasks."""
    status = args.status or "pending"
    data = _api("GET", f"/api/agent/tasks?status={status}&limit={args.limit}")
    tasks = data.get("tasks", data) if isinstance(data, dict) else (data or [])
    if not tasks:
        print(f"No {status} tasks")
        return
    for t in tasks:
        tid = t["id"][:16]
        tt = t.get("task_type", "?")
        direction = (t.get("direction") or "")[:60]
        print(f"  {tid}  {tt:6s}  {direction}")
    print(f"\n{len(tasks)} {status} tasks")


def cmd_nodes(_args):
    """List federation nodes."""
    data = _api("GET", "/api/federation/nodes")
    nodes = data if isinstance(data, list) else (data or {}).get("nodes", [])
    if not nodes:
        print("No nodes registered")
        return
    for n in nodes:
        if not isinstance(n, dict):
            continue
        status = n.get("status", "?")
        icon = "O" if status == "online" else "."
        providers = ", ".join(n.get("providers", []))
        print(f"  {icon} {n.get('hostname', '?'):25s} {n.get('os_type', '?'):8s} [{providers}]")


def cmd_specs(_args):
    """List registered specs."""
    data = _api("GET", "/api/spec-registry")
    specs = data.get("specs", data) if isinstance(data, dict) else (data or [])
    if isinstance(specs, dict):
        specs = specs.get("items", [])
    if not specs:
        print("No specs registered")
        return
    for s in specs[:30]:
        if not isinstance(s, dict):
            continue
        sid = s.get("spec_id", "?")
        title = s.get("title", sid)[:55]
        has_impl = "impl" if s.get("implementation_summary") else "    "
        print(f"  {has_impl} {title}")
    print(f"\n{len(specs)} specs registered")


def cmd_contribute(args):
    """Record a contribution."""
    body = {
        "contributor_id": _resolve_contributor_id(args.contributor),
        "type": args.type,
        "amount_cc": args.amount,
        "metadata": {"description": args.description},
    }
    result = _api("POST", "/api/contributions/record", body)
    if result:
        print(f"Contribution recorded: {args.type} — {args.description[:60]}")
    else:
        print("Failed to record contribution")


def cmd_coherence(_args):
    """Show coherence score breakdown."""
    data = _api("GET", "/api/coherence/score")
    if not data or not isinstance(data, dict):
        print("Could not fetch coherence score")
        return
    print(f"Coherence Score: {data.get('score', 0):.4f}")
    print(f"Signals: {data.get('signals_with_data', 0)}/{data.get('total_signals', 0)} backed by data")
    print()
    for name, sig in data.get("signals", {}).items():
        s = sig.get("score", 0)
        w = sig.get("weight", 0)
        contrib = s * w
        details = sig.get("details", {})
        note = details.get("note", "")
        bar = "#" * int(s * 20) + "." * (20 - int(s * 20))
        print(f"  {name:25s} [{bar}] {s:.3f} x {w:.2f} = {contrib:.4f}")
        if note:
            print(f"  {'':25s} {note}")


def cmd_run(args):
    """Start local node runner."""
    script = Path(__file__).parent / "local_runner.py"
    cmd = [sys.executable, str(script), "--timeout", str(args.timeout)]
    if args.loop:
        cmd.extend(["--loop", "--interval", str(args.interval)])
    print(f"Starting node runner: {' '.join(cmd)}")
    os.execv(sys.executable, cmd)


# ── Team Membership ──────────────────────────────────────────────────

def cmd_members(args):
    """List members of a workspace."""
    data = _api("GET", f"/api/workspaces/{args.workspace_id}/members")
    if not data:
        print("No members found")
        return
    members = data if isinstance(data, list) else data.get("members", [])
    if not members:
        print("No members found")
        return
    for m in members:
        cid = m.get("contributor_id", "?")
        role = m.get("role", "?")
        status = m.get("status", "?")
        joined = m.get("joined_at", "")
        print(f"  {cid:30s}  role={role:10s}  status={status:10s}  joined={joined}")
    print(f"\n{len(members)} members")


def cmd_invite(args):
    """Invite contributor to workspace."""
    body = {"contributor_id": args.contributor_id, "role": args.role}
    result = _api("POST", f"/api/workspaces/{args.workspace_id}/invite", body)
    if result:
        print(f"Invited {args.contributor_id} to workspace {args.workspace_id} as {args.role}")
    else:
        print("Failed to send invite")


def cmd_my_workspaces(args):
    """List workspaces contributor belongs to."""
    data = _api("GET", f"/api/contributors/{args.contributor_id}/workspaces")
    if not data:
        print("No workspaces found")
        return
    workspaces = data if isinstance(data, list) else data.get("workspaces", [])
    if not workspaces:
        print("No workspaces found")
        return
    for w in workspaces:
        wid = w.get("id", w.get("workspace_id", "?"))
        name = w.get("name", "?")
        role = w.get("role", "")
        print(f"  {wid:30s}  {name:30s}  role={role}")
    print(f"\n{len(workspaces)} workspaces")


# ── Messaging ────────────────────────────────────────────────────────

def cmd_send(args):
    """Send a direct message."""
    body = {
        "from_contributor_id": args.sender,
        "to_contributor_id": args.recipient,
        "body": args.body,
        "subject": args.subject or "",
    }
    result = _api("POST", "/api/messages", body)
    if result:
        print(f"Message sent to {args.recipient}")
    else:
        print("Failed to send message")


def cmd_inbox(args):
    """Show inbox for a contributor."""
    data = _api("GET", f"/api/messages/inbox/{args.contributor_id}")
    if not data:
        print("Inbox empty")
        return
    messages = data if isinstance(data, list) else data.get("messages", [])
    if not messages:
        print("Inbox empty")
        return
    for m in messages:
        sender = m.get("from_contributor_id", m.get("from", "?"))
        subject = m.get("subject", "(no subject)")
        body_preview = (m.get("body", "") or "")[:60]
        read = "read" if m.get("read") else "unread"
        ts = m.get("created_at", m.get("timestamp", ""))
        print(f"  [{read:6s}] {sender:20s}  {subject:30s}  {body_preview}")
        if ts:
            print(f"           {ts}")
    print(f"\n{len(messages)} messages")


def cmd_thread(args):
    """Show message thread between two contributors."""
    data = _api("GET", f"/api/messages/thread/{args.contributor_a}/{args.contributor_b}")
    if not data:
        print("No messages in thread")
        return
    messages = data if isinstance(data, list) else data.get("messages", [])
    if not messages:
        print("No messages in thread")
        return
    for m in messages:
        sender = m.get("from_contributor_id", m.get("from", "?"))
        body = m.get("body", "")
        ts = m.get("created_at", m.get("timestamp", ""))
        print(f"  [{ts}] {sender}:")
        print(f"    {body}")
    print(f"\n{len(messages)} messages in thread")


# ── Activity ─────────────────────────────────────────────────────────

def cmd_activity(args):
    """Show workspace activity feed."""
    data = _api("GET", f"/api/workspaces/{args.workspace_id}/activity?limit={args.limit}")
    if not data:
        print("No activity found")
        return
    events = data if isinstance(data, list) else data.get("events", data.get("activity", []))
    if not events:
        print("No activity found")
        return
    for e in events:
        ts = e.get("timestamp", e.get("created_at", ""))
        event_type = e.get("event_type", "?")
        actor = e.get("actor", e.get("contributor_id", "?"))
        summary = e.get("summary", e.get("description", ""))
        print(f"  {ts:25s}  {event_type:20s}  {actor:20s}  {summary}")
    print(f"\n{len(events)} events")


# ── Projects ─────────────────────────────────────────────────────────

def cmd_projects(args):
    """List projects in a workspace."""
    data = _api("GET", f"/api/workspaces/{args.workspace_id}/projects")
    if not data:
        print("No projects found")
        return
    projects = data if isinstance(data, list) else data.get("projects", [])
    if not projects:
        print("No projects found")
        return
    for p in projects:
        pid = p.get("id", "?")
        name = p.get("name", "?")
        idea_count = p.get("idea_count", 0)
        print(f"  {pid:30s}  {name:30s}  ideas={idea_count}")
    print(f"\n{len(projects)} projects")


def cmd_project(args):
    """Show project details with ideas."""
    data = _api("GET", f"/api/projects/{args.project_id}")
    if not data:
        print(f"Project {args.project_id} not found")
        return
    print(f"{data.get('name', '?')}")
    desc = data.get("description", "")
    if desc:
        print(f"  {desc[:120]}")
    workspace = data.get("workspace_id", "")
    if workspace:
        print(f"  Workspace: {workspace}")
    ideas = data.get("ideas", [])
    if ideas:
        print(f"\n  Ideas ({len(ideas)}):")
        for idea in ideas:
            if isinstance(idea, dict):
                iid = idea.get("id", idea.get("idea_id", "?"))
                iname = idea.get("name", "?")
                print(f"    {iid:30s}  {iname}")
            else:
                print(f"    {idea}")
    else:
        print("  No ideas linked")


def cmd_create_project(args):
    """Create a project in a workspace."""
    body = {
        "name": args.name,
        "description": args.description or "",
        "workspace_id": args.workspace_id,
    }
    result = _api("POST", f"/api/workspaces/{args.workspace_id}/projects", body)
    if result:
        pid = result.get("id", "?") if isinstance(result, dict) else "?"
        print(f"Project created: {pid}  {args.name}")
    else:
        print("Failed to create project")


# ── Discovery / Living Network ────────────────────────────────────────

def cmd_discover(args):
    data = _api("GET", f"/api/discover/{args.contributor_id}?limit={args.limit}")
    if not data:
        print("No discovery feed available")
        return
    items = data.get("items", []) if isinstance(data, dict) else data
    if not items:
        print("Your feed is quiet — try creating ideas or setting your belief profile.")
        return
    profile = data.get("profile_summary", {}) if isinstance(data, dict) else {}
    if profile:
        axes = profile.get("top_axes", [])
        if axes:
            print(f"  Your vibe: {', '.join(axes[:3])}")
    print()
    for item in items:
        kind = item.get("kind", "?")
        icons = {"resonant_idea": "💡", "resonant_peer": "🤝", "cross_domain": "🌉", "resonant_news": "📰", "growth_edge": "🌱"}
        icon = icons.get(kind, "✨")
        score = item.get("score", 0)
        title = item.get("title", "")[:60]
        reason = item.get("reason", "")[:80]
        print(f"  {icon} [{score:.0%}] {title}")
        if reason:
            print(f"      {reason}")
        print()


def cmd_constellation(args):
    data = _api("GET", f"/api/constellation?max_nodes={args.max_nodes}")
    if not data:
        print("No constellation data available")
        return
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    stats = data.get("stats", {})
    print(f"  Constellation: {len(nodes)} nodes, {len(edges)} edges")
    if stats:
        print(f"  Clusters: {stats.get('clusters', '?')}")
    print()
    by_type = {}
    for n in nodes:
        t = n.get("type", "?")
        by_type[t] = by_type.get(t, 0) + 1
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        icons = {"idea": "💡", "contributor": "👤", "concept": "🔮"}
        print(f"  {icons.get(t, '•')} {t}: {c}")
    print()
    brightest = sorted(nodes, key=lambda n: n.get("brightness", 0), reverse=True)[:5]
    if brightest:
        print("  Brightest stars:")
        for n in brightest:
            print(f"    ✦ {n.get('name', '?')[:50]} ({n.get('type', '?')}, brightness={n.get('brightness', 0):.0%})")


def cmd_vitality(args):
    data = _api("GET", f"/api/workspaces/{args.workspace_id}/vitality")
    if not data:
        print("No vitality data available")
        return
    score = data.get("vitality_score", 0)
    desc = data.get("health_description", "")
    signals = data.get("signals", {})

    bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
    color = "🟢" if score >= 0.7 else "🟡" if score >= 0.4 else "🔴"
    print(f"  {color} Vitality: {bar} {score:.0%}")
    print(f"  {desc}")
    print()

    if signals:
        for key in ["diversity_index", "resonance_density", "flow_rate", "connection_strength", "activity_pulse"]:
            val = signals.get(key, 0)
            label = key.replace("_", " ").title()
            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
            print(f"    {label:25s} {bar} {val:.0%}")
        breath = signals.get("breath_rhythm", {})
        if breath:
            print(f"\n    Breath: gas={breath.get('gas', 0):.0%}  water={breath.get('water', 0):.0%}  ice={breath.get('ice', 0):.0%}")


def cmd_resonate(args):
    data = _api("GET", f"/api/resonance/ideas/{args.idea_id}?limit={args.limit}")
    if not data:
        print("No resonance data available")
        return
    idea_name = data.get("idea_name", args.idea_id)
    domain = data.get("domain", [])
    matches = data.get("matches", [])
    print(f"  Resonances for: {idea_name}")
    if domain:
        print(f"  Domain: {', '.join(domain)}")
    print(f"  Matches: {len(matches)}")
    print()
    for m in matches:
        coherence = m.get("coherence", 0)
        name = m.get("name_b", m.get("idea_id_b", "?"))[:50]
        cross = " 🌉" if m.get("cross_domain") else ""
        strong = " ★" if m.get("strong") else ""
        print(f"    {coherence:.0%} {name}{cross}{strong}")


# ── News ────────────────────────────────────────────────────────────────

def cmd_news(args):
    """Show news feed."""
    data = _api("GET", f"/api/news/feed?limit={args.limit}")
    if not data:
        print("No news available")
        return
    items = data.get("items", data) if isinstance(data, dict) else data
    if not items:
        print("No news available")
        return
    for item in items:
        title = item.get("title", "?")[:70]
        source = item.get("source", item.get("source_id", "?"))
        published = item.get("published", item.get("published_at", ""))
        print(f"  {title}")
        print(f"    source={source}  published={published}")
    print(f"\n{len(items)} news items")


def cmd_news_resonance(args):
    """Show news matched to ideas with resonance scores."""
    data = _api("GET", f"/api/news/resonance?top_n={args.top}")
    if not data:
        print("No news resonance data available")
        return
    matches = data.get("matches", data) if isinstance(data, dict) else data
    if not matches:
        print("No news resonance data available")
        return
    for m in matches:
        idea_name = m.get("idea_name", m.get("idea_id", "?"))[:40]
        news_title = m.get("news_title", m.get("title", "?"))[:50]
        score = m.get("resonance_score", m.get("score", 0))
        print(f"  {idea_name}")
        print(f"    news: {news_title}  resonance={score:.2f}")
    print(f"\n{len(matches)} matches")


# ── Federation ──────────────────────────────────────────────────────────

def cmd_federation(args):
    """Show federation nodes."""
    data = _api("GET", "/api/federation/nodes")
    nodes = data if isinstance(data, list) else (data or {}).get("nodes", [])
    if not nodes:
        print("No federation nodes registered")
        return
    for n in nodes:
        if not isinstance(n, dict):
            continue
        hostname = n.get("hostname", "?")
        os_type = n.get("os_type", "?")
        providers = ", ".join(n.get("providers", []))
        last_hb = n.get("last_heartbeat", n.get("last_seen", ""))
        print(f"  {hostname:25s}  os={os_type:8s}  providers=[{providers}]  heartbeat={last_hb}")
    print(f"\n{len(nodes)} federation nodes")


# ── Beliefs ─────────────────────────────────────────────────────────────

def cmd_beliefs(args):
    """Show belief profile or network belief stats."""
    if args.contributor_id:
        data = _api("GET", f"/api/beliefs/{args.contributor_id}")
        if not data:
            print(f"No belief profile for {args.contributor_id}")
            return
        print(f"Belief profile: {args.contributor_id}")
        axes = data.get("worldview_axes", data.get("axes", {}))
        if axes:
            print("  Worldview axes:")
            if isinstance(axes, dict):
                for axis, val in axes.items():
                    print(f"    {axis:30s}  {val}")
            elif isinstance(axes, list):
                for ax in axes:
                    if isinstance(ax, dict):
                        print(f"    {ax.get('name', '?'):30s}  {ax.get('value', '?')}")
                    else:
                        print(f"    {ax}")
        concepts = data.get("top_concepts", data.get("concepts", []))
        if concepts:
            print("  Top concepts:")
            for c in concepts[:10]:
                if isinstance(c, dict):
                    print(f"    {c.get('name', c.get('id', '?')):30s}  score={c.get('score', c.get('affinity', '?'))}")
                else:
                    print(f"    {c}")
    else:
        data = _api("GET", "/api/beliefs/roi")
        if not data:
            print("No belief network stats available")
            return
        print("Belief network stats:")
        if isinstance(data, dict):
            for key, val in data.items():
                print(f"  {key}: {val}")
        else:
            print(f"  {data}")


# ── Peers ───────────────────────────────────────────────────────────────

def cmd_peers(args):
    """Find resonant peers for a contributor."""
    data = _api("GET", f"/api/peers/resonant?contributor_id={args.contributor_id}&limit=10")
    if not data:
        print("No resonant peers found")
        return
    peers = data.get("peers", data) if isinstance(data, dict) else data
    if not peers:
        print("No resonant peers found")
        return
    for p in peers:
        name = p.get("name", p.get("contributor_id", "?"))[:30]
        score = p.get("resonance_score", p.get("score", 0))
        tags = ", ".join(p.get("shared_tags", p.get("tags", [])))
        print(f"  {name:30s}  resonance={score:.2f}  shared=[{tags}]")
    print(f"\n{len(peers)} resonant peers")


# ── CC Supply ───────────────────────────────────────────────────────────

def cmd_cc_supply(_args):
    """Show CC economics / token supply."""
    data = _api("GET", "/api/cc/supply")
    if not data:
        print("CC supply data not available")
        return
    if isinstance(data, dict):
        total = data.get("total_minted", "?")
        outstanding = data.get("outstanding", "?")
        coherence = data.get("coherence_score", "?")
        print(f"  Total minted:    {total}")
        print(f"  Outstanding:     {outstanding}")
        print(f"  Coherence score: {coherence}")
        for key, val in data.items():
            if key not in ("total_minted", "outstanding", "coherence_score"):
                print(f"  {key}: {val}")
    else:
        print(f"  {data}")


# ── Governance ──────────────────────────────────────────────────────────

def cmd_governance(args):
    """List governance change requests."""
    data = _api("GET", f"/api/governance/change-requests?limit={args.limit}")
    if not data:
        print("No governance change requests")
        return
    requests = data.get("change_requests", data.get("items", data)) if isinstance(data, dict) else data
    if not requests:
        print("No governance change requests")
        return
    for cr in requests:
        crid = cr.get("id", "?")[:20]
        target = cr.get("target_type", "?")
        status = cr.get("status", "?")
        proposer = cr.get("proposer_id", cr.get("proposer", "?"))
        rationale = (cr.get("rationale", cr.get("description", "")) or "")[:60]
        print(f"  {crid:20s}  target={target:12s}  status={status:10s}  proposer={proposer}")
        if rationale:
            print(f"  {'':20s}  {rationale}")
    print(f"\n{len(requests)} change requests")


# ── Proprioception ───────────────────────────��────────────────────────

def cmd_sense(args):
    """Auto-sense system state (proprioception)."""
    if args.apply:
        data = _api("POST", "/api/proprioception/apply")
    else:
        data = _api("GET", "/api/proprioception")
    if not data:
        print("Could not run proprioception scan")
        return
    report = data.get("report", data) if isinstance(data, dict) else data
    if not isinstance(report, dict):
        print(f"  {report}")
        return

    health = report.get("health", "?")
    icons = {"strong": "OK", "growing": "~~", "needs_attention": "!!"}
    print(f"  [{icons.get(health, '?')}] Health: {health}")

    specs = report.get("specs", {})
    print(f"  Specs: {specs.get('sensed', 0)} sensed, {specs.get('with_source', 0)} with source, {specs.get('missing_source', 0)} missing source")
    if specs.get("updated", 0) > 0:
        print(f"    {specs['updated']} spec value updates suggested")

    ideas = report.get("ideas", {})
    print(f"  Ideas: {ideas.get('sensed', 0)} sensed, {ideas.get('advanced', 0)} stage suggestions")
    for sug in ideas.get("suggestions", [])[:5]:
        print(f"    {sug.get('idea_id', '?')}: {sug.get('current_stage', '?')} -> {sug.get('suggested_stage', '?')} ({sug.get('reason', '')})")

    endpoints = report.get("endpoints", {})
    print(f"  Endpoints: {endpoints.get('alive', 0)}/{endpoints.get('checked', 0)} alive")

    if args.apply and "applied_specs" in data:
        print(f"\n  Applied: {data['applied_specs']} spec updates, {data['applied_ideas']} idea advances")


def cmd_notify_bridges(_args):
    """Create activity events for new resonance bridges."""
    data = _api("POST", "/api/discover/notify-bridges")
    if not data:
        print("Could not notify bridges")
        return
    count = data.get("new_bridges_notified", 0)
    ws = data.get("workspace_id", "?")
    if count > 0:
        print(f"  {count} new bridge notifications created in workspace {ws}")
    else:
        print(f"  No new bridges to notify in workspace {ws}")


# ── Breath ─────────────────────────────────────────────────────────────

def cmd_breath(args):
    """Show breath rhythm (gas/water/ice) for an idea or the portfolio."""
    if args.idea_id:
        data = _api("GET", f"/api/ideas/{args.idea_id}/breath")
        if not data:
            print(f"Breath data not available for {args.idea_id}")
            return
        print(f"  Breath: {args.idea_id}")
        rhythm = data.get("rhythm", {})
        state = data.get("state", "?")
        health = data.get("breath_health", 0)
        total = data.get("total_specs", 0)
        gas = data.get("gas_count", 0)
        water = data.get("water_count", 0)
        ice = data.get("ice_count", 0)
        print(f"  Specs: {total}  gas={gas}  water={water}  ice={ice}")
        print(f"  Rhythm: gas={rhythm.get('gas', 0):.0%}  water={rhythm.get('water', 0):.0%}  ice={rhythm.get('ice', 0):.0%}")
        print(f"  Health: {health:.0%}  State: {state}")
    else:
        data = _api("GET", "/api/ideas/breath-overview")
        if not data:
            print("Breath overview not available")
            return
        pr = data.get("portfolio_rhythm", {})
        ph = data.get("portfolio_breath_health", 0)
        print(f"  Portfolio Breath: gas={pr.get('gas', 0):.0%}  water={pr.get('water', 0):.0%}  ice={pr.get('ice', 0):.0%}  health={ph:.0%}")
        print()
        for idea in data.get("ideas", []):
            r = idea.get("rhythm", {})
            name = idea.get("name", idea.get("idea_id", "?"))[:40]
            state = idea.get("state", "?")
            specs = idea.get("total_specs", 0)
            print(f"  {name:40s}  gas={r.get('gas', 0):.0%}  water={r.get('water', 0):.0%}  ice={r.get('ice', 0):.0%}  [{state}] {specs} specs")


# ── Flow ───────────────────────────────────────────────────────────────

def cmd_flow(_args):
    """Show contribution flow metrics."""
    data = _api("GET", "/api/contributions/flow")
    if not data:
        print("Flow metrics not available")
        return
    print(f"  Contribution Flow (last {data.get('period_days', 30)} days)")
    print(f"  Total contributions: {data.get('total_contributions', 0)}")
    print(f"  Total CC flow:       {_fmt_cc(data.get('total_cc_flow', 0))}")
    print(f"  Unique contributors: {data.get('unique_contributors', 0)}")
    print(f"  Ideas receiving:     {data.get('ideas_receiving_flow', 0)}")
    print(f"  Flow reciprocity:    {data.get('flow_reciprocity', 0):.0%}")
    top = data.get("top_flowing_ideas", [])
    if top:
        print(f"\n  Top flowing ideas:")
        for t in top[:10]:
            name = t.get("name", t.get("idea_id", "?"))[:40]
            cc = t.get("cc_total", 0)
            print(f"    {name:40s}  {_fmt_cc(cc)}")


# ── Main ──────────────────────────────────────────────────────────────

# ── Visuals ────────────────────────────────────────────────────────────

def cmd_visuals_generate(args):
    """Generate/regenerate images for a concept via API."""
    force_param = "&force=true" if args.force else ""
    data = _api("POST", f"/api/concepts/{args.concept_id}/visuals/regenerate?force={'true' if args.force else 'false'}")
    if not data:
        print(f"Could not generate visuals for {args.concept_id}", file=sys.stderr)
        return
    if data.get("error"):
        print(f"  Error: {data['error']}", file=sys.stderr)
        return
    print(f"  Concept: {args.concept_id}")
    print(f"  Total: {data.get('total', 0)} visuals")
    print(f"  Downloaded: {data.get('downloaded', 0)}, Existing: {data.get('existing', 0)}, Failed: {data.get('failed', 0)}")
    for r in data.get("results", []):
        icon = {"downloaded": "\u2713", "exists": "\u00b7", "failed": "\u2717"}.get(r["status"], "?")
        print(f"    {icon} {r['file']} ({r['status']})")


# ── Config ─────────────────────────────────────────────────────────────

def cmd_config(_args):
    """Show the editable config."""
    data = _api("GET", "/api/config")
    if data is None:
        # Fall back to local config file
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            else:
                data = {}
        except (json.JSONDecodeError, OSError):
            data = {}
    if not data:
        print("  (empty config — defaults in use)")
        print(f"  Config file: {CONFIG_PATH}")
        return
    print(f"Config ({CONFIG_PATH}):\n")
    print(json.dumps(data, indent=2))


def cmd_config_set(args):
    """Set a config value."""
    key = args.key
    value = args.value
    # Try to parse as JSON (for booleans, numbers, arrays)
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed = value

    # Support dotted keys: "web.api_base_url" → {"web": {"api_base_url": ...}}
    parts = key.split(".")
    if len(parts) > 1:
        updates: dict = {}
        current = updates
        for p in parts[:-1]:
            current[p] = {}
            current = current[p]
        current[parts[-1]] = parsed
    else:
        updates = {key: parsed}

    # Try API first
    data = _api("PATCH", "/api/config", {"updates": updates})
    if data is not None:
        print(f"  Set {key} = {json.dumps(parsed)}")
        return

    # Fall back to local file edit
    try:
        config = {}
        if CONFIG_PATH.exists():
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config.update(updates)
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"  Set {key} = {json.dumps(parsed)} (local file)")
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)


# ── Stories (Living Collective) ────────────────────────────────────────

def cmd_stories(args):
    """List concepts that have a living story."""
    data = _api("GET", f"/api/concepts/domain/living-collective?limit={args.limit}")
    if not data:
        print("Could not fetch concepts")
        return
    items = data.get("items", [])
    with_story = [c for c in items if c.get("story_content")]
    without_story = [c for c in items if not c.get("story_content")]
    print(f"Living stories: {len(with_story)} of {len(items)} concepts\n")
    for c in with_story:
        hz = c.get("sacred_frequency", {}).get("hz", "")
        hz_str = f" ({hz} Hz)" if hz else ""
        story_len = len(c.get("story_content", ""))
        print(f"  \u2713 {c['name'][:45]:<45s} {story_len:>5d} chars{hz_str}")
    if without_story:
        print(f"\n  Awaiting stories ({len(without_story)}):")
        for c in without_story:
            print(f"    \u00b7 {c.get('name', c['id'])}")


def cmd_story(args):
    """Display a concept's living story."""
    data = _api("GET", f"/api/concepts/{args.concept_id}")
    if not data:
        print(f"Concept {args.concept_id} not found")
        return
    story = data.get("story_content", "")
    if not story:
        print(f"{data.get('name', args.concept_id)} has no living story yet.")
        print(f"  Create one: cc story-update {args.concept_id} --file story.md")
        return
    hz = data.get("sacred_frequency", {}).get("hz", "")
    print(f"# {data.get('name', args.concept_id)}", end="")
    if hz:
        print(f"  ({hz} Hz)")
    else:
        print()
    print()
    # Render story with basic terminal formatting
    for line in story.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            print(f"\n\033[1m{stripped[3:]}\033[0m")
        elif stripped.startswith("### "):
            print(f"\n\033[4m{stripped[4:]}\033[0m")
        elif stripped.startswith("> "):
            print(f"  \033[3m{stripped[2:]}\033[0m")
        elif stripped.startswith("!["):
            # Inline visual: ![caption](visuals:prompt)
            import re
            m = re.match(r"!\[([^\]]*)\]", stripped)
            caption = m.group(1) if m else "visual"
            print(f"  [\033[36mImage: {caption}\033[0m]")
        elif stripped.startswith("\u2192 "):
            refs = stripped[2:].split(",")
            print(f"  Connected: {', '.join(r.strip() for r in refs)}")
        elif stripped.startswith("- "):
            print(f"  \u2022 {stripped[2:]}")
        else:
            print(f"  {stripped}" if stripped else "")


def cmd_story_update(args):
    """Update a concept's living story from a markdown file."""
    import re as _re
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"File not found: {filepath}", file=sys.stderr)
        return
    content = filepath.read_text(encoding="utf-8")
    # Strip frontmatter if present
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()
    # Strip title line (# Name)
    lines = content.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    story_content = "\n".join(lines).strip()

    # Pre-flight format validation
    warnings = []
    for i, line in enumerate(story_content.split("\n"), 1):
        s = line.strip()
        if s.startswith("-> "):
            warnings.append(f"  L{i}: Use \u2192 (Unicode arrow) instead of ->")
        if s.startswith("\u2192 ") and "[" in s and "](" in s:
            warnings.append(f"  L{i}: Cross-refs should be plain IDs, not markdown links")
        if s.startswith("\u2192 ") and " \u2014 " in s:
            warnings.append(f"  L{i}: Cross-refs should not have descriptions after \u2014")
    if warnings:
        print("Format warnings:")
        for w in warnings:
            print(w)
        print()

    data = _api("PATCH", f"/api/concepts/{args.concept_id}/story", {"story_content": story_content})
    if data:
        name = data.get("name", args.concept_id)
        sc = data.get("story_content", "")
        visuals_count = len(data.get("visuals", []))
        server_warnings = data.get("warnings", [])
        print(f"  Updated: {name}")
        print(f"  Story: {len(sc)} chars, {visuals_count} visuals")
        if server_warnings:
            print(f"  Server warnings ({len(server_warnings)}):")
            for w in server_warnings:
                print(f"    L{w.get('line', '?')}: {w.get('message', '?')}")
    else:
        print(f"Failed to update story for {args.concept_id}", file=sys.stderr)


def cmd_frequency(args):
    """Score text for living vs institutional frequency."""
    text = None

    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"File not found: {filepath}", file=sys.stderr)
            return
        text = filepath.read_text(encoding="utf-8")
        source = str(filepath)
    elif args.concept_id:
        data = _api("GET", f"/api/concepts/{args.concept_id}")
        if not data:
            print(f"Concept {args.concept_id} not found", file=sys.stderr)
            return
        text = data.get("story_content", "")
        if not text:
            print(f"{data.get('name', args.concept_id)} has no living story to score.")
            return
        source = f"concept:{args.concept_id}"
    else:
        print("Provide a concept_id or --file path", file=sys.stderr)
        return

    result = _api("POST", "/api/concepts/frequency-score", {"text": text})
    if not result:
        print("Frequency scoring failed", file=sys.stderr)
        return

    overall = result.get("score", 0)
    backend = result.get("backend", "unknown")
    lc_sim = result.get("living_centroid_sim", 0)
    ic_sim = result.get("institutional_centroid_sim", 0)

    # Color the overall score
    if overall > 0.7:
        color = "\033[32m"  # green
    elif overall >= 0.4:
        color = "\033[33m"  # yellow
    else:
        color = "\033[31m"  # red
    reset = "\033[0m"

    print(f"Frequency Score: {color}{overall:.2f}{reset}  ({source})")
    print(f"  Backend: {backend}")
    print(f"  Living centroid sim:        {lc_sim:.4f}")
    print(f"  Institutional centroid sim: {ic_sim:.4f}")
    print()
    print("Per-sentence breakdown:")
    print("-" * 72)

    for item in result.get("sentences", []):
        s = item.get("score", 0)
        if s > 0.7:
            sc = f"\033[32m{s:.2f}\033[0m"
        elif s >= 0.4:
            sc = f"\033[33m{s:.2f}\033[0m"
        else:
            sc = f"\033[31m{s:.2f}\033[0m"

        snippet = item.get("text", "")
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        print(f"  [{sc}] {snippet}")

    print("-" * 72)
    n_sentences = len(result.get("sentences", []))
    living_count = sum(1 for s in result.get("sentences", []) if s.get("score", 0) > 0.7)
    mixed_count = sum(1 for s in result.get("sentences", []) if 0.4 <= s.get("score", 0) <= 0.7)
    inst_count = sum(1 for s in result.get("sentences", []) if s.get("score", 0) < 0.4)
    print(f"  {n_sentences} sentences: \033[32m{living_count} living\033[0m, "
          f"\033[33m{mixed_count} mixed\033[0m, \033[31m{inst_count} institutional\033[0m")


def cmd_keygen(_args):
    """Generate a new Ed25519 keypair."""
    data = _api("POST", "/api/contributors/generate-keypair")
    if not data:
        print("Failed to generate keypair", file=sys.stderr)
        return
    print(f"  Algorithm: {data.get('algorithm')}")
    print(f"  Public key:  {data.get('public_key_hex')}")
    print(f"  Private key: {data.get('private_key_hex')}")
    print(f"  Fingerprint: {data.get('fingerprint')}")
    print(f"\n  \033[33mSave your private key — it will not be shown again.\033[0m")
    print(f"  Register: cc register-key <your-id> {data.get('public_key_hex')}")


def cmd_register_key(args):
    """Register a public key for a contributor."""
    data = _api("POST", f"/api/contributors/{args.contributor_id}/register-key",
                {"public_key_hex": args.public_key_hex})
    if not data:
        print("Failed to register key", file=sys.stderr)
        return
    if data.get("registered"):
        print(f"  Registered: {args.contributor_id}")
        print(f"  Fingerprint: {data.get('fingerprint')}")
    else:
        print(f"  Error: {data.get('error')}", file=sys.stderr)


def cmd_verify(args):
    """Verify hash chain integrity for an asset."""
    data = _api("GET", f"/api/verification/recompute/{args.asset_id}")
    if not data:
        print(f"Could not verify {args.asset_id}", file=sys.stderr)
        return
    valid = data.get("valid", False)
    entries = data.get("entries", 0)
    color = "\033[32m" if valid else "\033[31m"
    reset = "\033[0m"
    print(f"  {color}{'VALID' if valid else 'INVALID'}{reset}  {args.asset_id}  ({entries} entries)")
    if not valid and data.get("first_failure"):
        f = data["first_failure"]
        print(f"  First failure: day={f.get('day')} index={f.get('entry_index')}")
        if "stored_hash" in f:
            print(f"    stored:   {f['stored_hash']}")
            print(f"    computed: {f['computed_hash']}")


def cmd_chain(args):
    """Show hash chain for an asset."""
    data = _api("GET", f"/api/verification/chain/{args.asset_id}")
    if not data:
        print(f"No chain for {args.asset_id}")
        return
    print(f"Hash chain: {args.asset_id} ({len(data)} entries)\n")
    for entry in data[-args.limit:]:
        print(f"  {entry['day']}  reads={entry['read_count']:>6d}  "
              f"cc={entry['cc_total']:>12s}  hash={entry['merkle_hash'][:16]}...")


def cmd_snapshot(args):
    """Show or verify a weekly snapshot."""
    if args.week:
        week = args.week
    else:
        from datetime import date as _date, timedelta as _td
        prev = _date.today() - _td(days=7)
        week = prev.strftime("%G-W%V")

    if args.verify:
        data = _api("GET", f"/api/verification/snapshot/{week}/verify")
        if not data:
            print(f"Could not verify snapshot {week}", file=sys.stderr)
            return
        valid = data.get("signature_valid", False)
        color = "\033[32m" if valid else "\033[31m"
        reset = "\033[0m"
        print(f"  Snapshot {week}: signature {color}{'VALID' if valid else 'INVALID'}{reset}")
        print(f"  Merkle root: {data.get('merkle_root', '?')[:32]}...")
        print(f"  Signed by:   {data.get('signed_by', '?')[:32]}...")
    else:
        data = _api("GET", f"/api/verification/snapshot/{week}")
        if not data:
            print(f"No snapshot for {week}")
            return
        print(f"  Week: {data.get('week')}")
        print(f"  Merkle root: {data.get('merkle_root', '')[:32]}...")
        print(f"  Total reads: {data.get('total_reads', 0)}")
        print(f"  Total CC:    {data.get('total_cc', '0')}")
        print(f"  Assets:      {data.get('assets_count', 0)}")
        print(f"  Published:   {data.get('published_at', 'not yet')}")


def cmd_public_key(_args):
    """Show the verification Ed25519 public key."""
    data = _api("GET", "/api/verification/public-key")
    if not data:
        print("Could not fetch public key", file=sys.stderr)
        return
    print(f"  Algorithm: {data.get('algorithm')}")
    print(f"  Public key: {data.get('public_key_hex')}")
    print(f"  Usage: {data.get('usage')}")


def cmd_field(args):
    """Analyze token-level frequency field for a concept."""
    data = _api("GET", f"/api/concepts/{args.concept_id}/frequency-field")
    if not data:
        print(f"Could not analyze {args.concept_id}", file=sys.stderr)
        return
    if data.get("error"):
        print(f"  Error: {data['error']}", file=sys.stderr)
        return

    green = "\033[32m"
    red = "\033[31m"
    yellow = "\033[33m"
    dim = "\033[2m"
    reset = "\033[0m"

    print(f"Frequency Field: {args.concept_id}")
    print(f"  Marked tokens: {data.get('total_marked_tokens', 0)}  "
          f"({green}{data.get('living_tokens', 0)} living{reset}, "
          f"{red}{data.get('institutional_tokens', 0)} institutional{reset})")
    print(f"  Field mean: {data.get('field_mean', 0):.3f}")

    # Top living
    top_living = data.get("top_living", [])
    if top_living:
        print(f"\n  {green}Living tokens:{reset}")
        for t in top_living[:8]:
            bar = "█" * int(t["signal"] * 10)
            print(f"    {green}{t['signal']:+.2f}{reset}  {bar}  {t['word']} ({t['count']}x)")

    # Top institutional
    top_inst = data.get("top_institutional", [])
    if top_inst:
        print(f"\n  {red}Institutional tokens:{reset}")
        for t in top_inst[:8]:
            bar = "█" * int(abs(t["signal"]) * 10)
            print(f"    {red}{t['signal']:+.2f}{reset}  {bar}  {t['word']} ({t['count']}x)")

    # Dissonances
    dissonances = data.get("dissonances", [])
    if dissonances:
        print(f"\n  {yellow}Dissonances ({len(dissonances)}):{reset} tokens out of tune with their context")
        for d in dissonances[:10]:
            neg = " (negated)" if d.get("negated") else ""
            print(f"    L{d['line']:>3d}  {red}{d['word']}{reset} = {d['signal']:+.2f}  "
                  f"context = {d['context_avg']:+.2f}  "
                  f"deviation = {d['deviation']:+.2f}{neg}")
            print(f"         {dim}{d['sentence'][:80]}{reset}")
    else:
        print(f"\n  {green}No dissonances found — the field is coherent.{reset}")

    # Suggestions
    suggestions = data.get("suggestions", [])
    if suggestions:
        print(f"\n  Suggestions ({len(suggestions)}):")
        for s in suggestions[:10]:
            print(f"    L{s['line']:>3d}  {red}{s['original']}{reset} → {green}{s['suggested']}{reset}")


def cmd_frequency_edit(args):
    """Find and fix institutional-frequency phrases in a concept or file."""
    from pathlib import Path as _P

    text = None
    filepath = None

    if args.file:
        filepath = _P(args.file)
        if not filepath.exists():
            print(f"File not found: {filepath}", file=sys.stderr)
            return
        text = filepath.read_text(encoding="utf-8")
        source = str(filepath)
    elif args.concept_id:
        # Try local file first
        kb_path = _P(__file__).parent.parent / "docs" / "vision-kb" / "concepts" / f"{args.concept_id}.md"
        if kb_path.exists():
            filepath = kb_path
            text = kb_path.read_text(encoding="utf-8")
            source = str(kb_path)
        else:
            data = _api("GET", f"/api/concepts/{args.concept_id}")
            if not data:
                print(f"Concept {args.concept_id} not found", file=sys.stderr)
                return
            text = data.get("story_content", "")
            source = f"concept:{args.concept_id}"
    else:
        print("Provide a concept_id or --file path", file=sys.stderr)
        return

    if not text:
        print("No content to edit.")
        return

    result = _api("POST", "/api/concepts/frequency-edit", {"text": text})
    if not result:
        print("Frequency editing failed", file=sys.stderr)
        return

    before = result.get("before_score", 0)
    after = result.get("after_score", 0)
    changes = result.get("changes", [])

    if not changes:
        print(f"  \033[32m{before:.3f}\033[0m  No institutional phrases found. ({source})")
        return

    print(f"  Source: {source}")
    print(f"  Before: {before:.3f}  After: {after:.3f}  (+{after - before:.3f})")
    print(f"  Changes ({len(changes)}):\n")

    for c in changes:
        print(f"    L{c['line']:>3d}  \033[31m{c['original']}\033[0m → \033[32m{c['suggested']}\033[0m")
        print(f"         {c['context']}")

    if args.apply and filepath:
        new_text = result.get("new_text", "")
        if new_text:
            filepath.write_text(new_text, encoding="utf-8")
            print(f"\n  \033[32mApplied {len(changes)} changes to {filepath}\033[0m")
        else:
            print(f"\n  No new text returned — changes not applied.", file=sys.stderr)
    elif filepath:
        print(f"\n  Add --apply to write changes to {filepath}")


def main():
    parser = argparse.ArgumentParser(
        prog="cc",
        description="Coherence Network CLI — two-way bridge to the network",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Network status overview")
    sub.add_parser("ideas", help="List ideas")
    sub.add_parser("nodes", help="List federation nodes")
    sub.add_parser("specs", help="List registered specs")
    sub.add_parser("coherence", help="Coherence score breakdown")

    p_idea = sub.add_parser("idea", help="Show idea details")
    p_idea.add_argument("idea_id")

    p_share = sub.add_parser("share", help="Share a new idea")
    p_share.add_argument("name")
    p_share.add_argument("description")
    p_share.add_argument("--value", type=float, default=30)
    p_share.add_argument("--cost", type=float, default=8)
    p_share.add_argument("--confidence", type=float, default=0.7)

    p_ask = sub.add_parser("ask", help="Ask a question on an idea")
    p_ask.add_argument("idea_id")
    p_ask.add_argument("question")
    p_ask.add_argument("--value", type=float, default=10)
    p_ask.add_argument("--cost", type=float, default=1)

    p_stake = sub.add_parser("stake", help="Stake CC on an idea")
    p_stake.add_argument("idea_id")
    p_stake.add_argument("amount", type=float)
    p_stake.add_argument("--contributor", default=None)
    p_stake.add_argument("--rationale", default=None)

    p_tasks = sub.add_parser("tasks", help="List tasks")
    p_tasks.add_argument("--status", default="pending")
    p_tasks.add_argument("--limit", type=int, default=20)

    p_contrib = sub.add_parser("contribute", help="Record a contribution")
    p_contrib.add_argument("type", help="e.g. code, spec, review, promotion")
    p_contrib.add_argument("description")
    p_contrib.add_argument("--contributor", default=None)
    p_contrib.add_argument("--amount", type=float, default=5)

    p_run = sub.add_parser("run", help="Start local node runner")
    p_run.add_argument("--timeout", type=int, default=300)
    p_run.add_argument("--loop", action="store_true")
    p_run.add_argument("--interval", type=int, default=120)

    # ── Team Membership ──
    p_members = sub.add_parser("members", help="List members of a workspace")
    p_members.add_argument("workspace_id")

    p_invite = sub.add_parser("invite", help="Invite contributor to workspace")
    p_invite.add_argument("workspace_id")
    p_invite.add_argument("contributor_id")
    p_invite.add_argument("--role", default="member")

    p_myws = sub.add_parser("my-workspaces", help="List workspaces for a contributor")
    p_myws.add_argument("contributor_id")

    # ── Messaging ──
    p_send = sub.add_parser("send", help="Send a direct message")
    p_send.add_argument("sender", metavar="from")
    p_send.add_argument("recipient", metavar="to")
    p_send.add_argument("body")
    p_send.add_argument("--subject", default="")

    p_inbox = sub.add_parser("inbox", help="Show inbox")
    p_inbox.add_argument("contributor_id")

    p_thread = sub.add_parser("thread", help="Show thread between two contributors")
    p_thread.add_argument("contributor_a")
    p_thread.add_argument("contributor_b")

    # ── Activity ──
    p_activity = sub.add_parser("activity", help="Show workspace activity feed")
    p_activity.add_argument("workspace_id")
    p_activity.add_argument("--limit", type=int, default=20)

    # ── Discovery / Living Network ──
    p_discover = sub.add_parser("discover", help="Serendipity feed — what resonates with you")
    p_discover.add_argument("contributor_id", nargs="?", default="default-contributor")
    p_discover.add_argument("--limit", type=int, default=15)

    p_constellation = sub.add_parser("constellation", help="Network visualization — nodes and edges")
    p_constellation.add_argument("--max-nodes", type=int, default=50)

    p_vitality = sub.add_parser("vitality", help="Workspace health as living-system signals")
    p_vitality.add_argument("workspace_id", nargs="?", default="coherence-network")

    p_resonate = sub.add_parser("resonate", help="Find ideas that resonate with an idea")
    p_resonate.add_argument("idea_id")
    p_resonate.add_argument("--limit", type=int, default=10)

    # ── Projects ──
    p_projects = sub.add_parser("projects", help="List projects in a workspace")
    p_projects.add_argument("workspace_id")

    p_project = sub.add_parser("project", help="Show project details with ideas")
    p_project.add_argument("project_id")

    p_createproj = sub.add_parser("create-project", help="Create a project in a workspace")
    p_createproj.add_argument("workspace_id")
    p_createproj.add_argument("name")
    p_createproj.add_argument("--description", default="")

    # ── News ──
    p_news = sub.add_parser("news", help="Show news feed")
    p_news.add_argument("--limit", type=int, default=20)

    p_newsres = sub.add_parser("news-resonance", help="Show news matched to ideas")
    p_newsres.add_argument("--top", type=int, default=5)

    # ── Federation ──
    sub.add_parser("federation", help="Show federation nodes")

    # ── Beliefs ──
    p_beliefs = sub.add_parser("beliefs", help="Show belief profile or network stats")
    p_beliefs.add_argument("contributor_id", nargs="?", default=None)

    # ── Peers ──
    p_peers = sub.add_parser("peers", help="Find resonant peers")
    p_peers.add_argument("contributor_id")

    # ── CC Supply ──
    sub.add_parser("cc-supply", help="Show CC economics / token supply")

    # ── Governance ──
    p_governance = sub.add_parser("governance", help="List governance change requests")
    p_governance.add_argument("--limit", type=int, default=20)

    # ── Breath ──
    p_breath = sub.add_parser("breath", help="Show breath rhythm (gas/water/ice) for an idea or portfolio")
    p_breath.add_argument("idea_id", nargs="?", default=None)

    # ── Flow ──
    sub.add_parser("flow", help="Show contribution flow metrics")

    # ── Proprioception ──
    p_sense = sub.add_parser("sense", help="Auto-sense system state (proprioception)")
    p_sense.add_argument("--apply", action="store_true", help="Apply suggested updates")

    # ── Bridge Notifications ──
    sub.add_parser("notify-bridges", help="Create activity events for new resonance bridges")

    # ── Config ──
    sub.add_parser("config", help="Show editable config (~/.coherence-network/config.json)")

    p_config_set = sub.add_parser("config-set", help="Set a config value")
    p_config_set.add_argument("key", help="Config key (e.g. web.api_base_url)")
    p_config_set.add_argument("value", help="Value to set")

    # ── Stories (Living Collective) ──
    p_stories = sub.add_parser("stories", help="List concepts with living stories")
    p_stories.add_argument("--limit", type=int, default=50)

    p_story = sub.add_parser("story", help="View a concept's living story")
    p_story.add_argument("concept_id")

    p_story_update = sub.add_parser("story-update", help="Update a concept's story from a markdown file")
    p_story_update.add_argument("concept_id")
    p_story_update.add_argument("--file", "-f", required=True, help="Path to markdown file with story content")

    p_visuals = sub.add_parser("visuals-generate", help="Generate/regenerate images for a concept")
    p_visuals.add_argument("concept_id")
    p_visuals.add_argument("--force", action="store_true", help="Re-download even if files exist")

    p_frequency = sub.add_parser("frequency", help="Score text for living vs institutional frequency")
    p_frequency.add_argument("concept_id", nargs="?", default=None, help="Concept ID to score")
    p_frequency.add_argument("--file", default=None, help="Score a markdown file instead")

    # ── Identity ──
    sub.add_parser("keygen", help="Generate a new Ed25519 keypair for signing contributions")

    p_register_key = sub.add_parser("register-key", help="Register your public key")
    p_register_key.add_argument("contributor_id")
    p_register_key.add_argument("public_key_hex")

    # ── Verification ──
    p_verify = sub.add_parser("verify", help="Verify hash chain integrity for an asset")
    p_verify.add_argument("asset_id")

    p_chain = sub.add_parser("chain", help="Show hash chain for an asset")
    p_chain.add_argument("asset_id")
    p_chain.add_argument("--limit", type=int, default=30)

    p_snapshot = sub.add_parser("snapshot", help="Show or verify a weekly snapshot")
    p_snapshot.add_argument("week", nargs="?", default=None, help="Week (e.g. 2026-W16)")
    p_snapshot.add_argument("--verify", action="store_true", help="Verify signature")

    p_pubkey = sub.add_parser("public-key", help="Show verification Ed25519 public key")

    p_field = sub.add_parser("field", help="Token-level frequency field analysis for a concept")
    p_field.add_argument("concept_id")

    p_freq_edit = sub.add_parser("frequency-edit", help="Find and fix institutional-frequency phrases")
    p_freq_edit.add_argument("concept_id", nargs="?", default=None, help="Concept ID to edit")
    p_freq_edit.add_argument("--file", default=None, help="Edit a markdown file instead")
    p_freq_edit.add_argument("--apply", action="store_true", help="Apply changes to the file")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "status": cmd_status, "ideas": cmd_ideas, "idea": cmd_idea,
        "share": cmd_share, "ask": cmd_ask, "stake": cmd_stake,
        "tasks": cmd_tasks, "nodes": cmd_nodes, "specs": cmd_specs,
        "contribute": cmd_contribute, "coherence": cmd_coherence, "run": cmd_run,
        # Team Membership
        "members": cmd_members, "invite": cmd_invite, "my-workspaces": cmd_my_workspaces,
        # Messaging
        "send": cmd_send, "inbox": cmd_inbox, "thread": cmd_thread,
        # Activity
        "activity": cmd_activity,
        # Projects
        "projects": cmd_projects, "project": cmd_project, "create-project": cmd_create_project,
        # Discovery / Living Network
        "discover": cmd_discover, "constellation": cmd_constellation,
        "vitality": cmd_vitality, "resonate": cmd_resonate,
        # News / Federation / Beliefs / Peers / CC Supply / Governance
        "news": cmd_news, "news-resonance": cmd_news_resonance,
        "federation": cmd_federation, "beliefs": cmd_beliefs,
        "peers": cmd_peers, "cc-supply": cmd_cc_supply,
        "governance": cmd_governance,
        # Breath + Flow
        "breath": cmd_breath, "flow": cmd_flow,
        # Proprioception + Bridge Notifications
        "sense": cmd_sense, "notify-bridges": cmd_notify_bridges,
        # Stories (Living Collective)
        "stories": cmd_stories, "story": cmd_story, "story-update": cmd_story_update,
        "visuals-generate": cmd_visuals_generate,
        # Frequency scoring
        "frequency": cmd_frequency, "field": cmd_field, "frequency-edit": cmd_frequency_edit,
        # Identity
        "keygen": cmd_keygen, "register-key": cmd_register_key,
        # Verification
        "verify": cmd_verify, "chain": cmd_chain, "snapshot": cmd_snapshot, "public-key": cmd_public_key,
        # Config
        "config": cmd_config, "config-set": cmd_config_set,
    }
    handler = cmd_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
