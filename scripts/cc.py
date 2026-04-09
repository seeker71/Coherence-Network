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


# ── Main ──────────────────────────────────────────────────────────────

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
    }
    handler = cmd_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
