#!/usr/bin/env python3
"""cc — Coherence Network CLI.

Two-way bridge between any agent (OpenClaw, Claude, Codex, Cursor) and
the Coherence Network. Browse ideas, contribute, stake, check status,
run a node — all from the command line.

Usage:
  cc ideas                    List ideas sorted by free energy score
  cc status                   Network status (coherence score, nodes, tasks)
  cc setup                    Onboard: TOFU identity + personal API key (see ~/.coherence-network/keys.json)
  cc verify [--provider github]  Prove identity ownership after setup
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
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

API_BASE = (
    os.environ.get("COHERENCE_API_BASE")
    or os.environ.get("COHERENCE_HUB_URL")
    or "https://api.coherencycoin.com"
)
_KEYS_PATH = Path.home() / ".coherence-network" / "keys.json"


def _load_keys_file() -> dict:
    try:
        return json.loads(_KEYS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolve_api_key() -> str | None:
    """CC_API_KEY / COHERENCE_API_KEY override, then ~/.coherence-network/keys.json."""
    for env in ("CC_API_KEY", "COHERENCE_API_KEY"):
        v = os.environ.get(env)
        if v:
            return v
    k = _load_keys_file().get("api_key")
    return k if k else None


def _effective_api_key() -> str:
    """Read-only calls may fall back to dev-key; callers that need identity use _require_personal_key."""
    return _resolve_api_key() or "dev-key"


_client: httpx.Client | None = None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=30.0)
    _client.headers["X-API-Key"] = _effective_api_key()
    return _client


def _require_personal_key() -> str:
    k = _resolve_api_key()
    if not k:
        print("No API key found. Run: cc setup", file=sys.stderr)
        sys.exit(1)
    return k


def _api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    url = f"{API_BASE}{path}"
    c = _http()
    try:
        if method == "GET":
            r = c.get(url)
        elif method == "POST":
            r = c.post(url, json=body)
        elif method == "PATCH":
            r = c.patch(url, json=body)
        else:
            return None
        if r.status_code >= 400:
            print(f"Error: {r.status_code} {r.text[:200]}", file=sys.stderr)
            return None
        return r.json() if r.text.strip() else None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def _api_raw(method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
    """Same as _api but returns status + JSON for flows that need non-2xx handling."""
    url = f"{API_BASE}{path}"
    c = _http()
    try:
        if method == "POST":
            r = c.post(url, json=body)
        elif method == "GET":
            r = c.get(url)
        else:
            return 0, None
        try:
            payload = r.json() if r.text.strip() else None
        except Exception:
            payload = None
        return r.status_code, payload if isinstance(payload, dict) else None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 0, None


def _fmt_cc(v: float) -> str:
    return f"{v:,.0f} CC" if v >= 1 else f"{v:.2f} CC"


_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]{0,31}$")


def cmd_setup(args: argparse.Namespace) -> None:
    """Trust-on-first-use onboarding (MVP). OAuth/device-flow can upgrade verification later."""
    keys = _load_keys_file()
    cid = keys.get("contributor_id")
    if keys.get("api_key") and cid and not args.force:
        ans = input(f"You already have a key for {cid}. Re-run setup? [y/N] ")
        if ans.strip().lower() not in ("y", "yes"):
            return
    if args.name and args.provider and args.provider_id:
        _complete_setup(args.name.strip(), args.provider.strip().lower(), args.provider_id.strip())
        return
    if not sys.stdin.isatty():
        print(
            "Non-interactive setup requires: "
            "cc setup --name NAME --provider PROVIDER --provider-id HANDLE",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        "\nCoherence Network — cc setup\n\n"
        "Trust-on-first-use (TOFU): your identity is linked unverified first; "
        "you can prove ownership later with: cc verify\n",
    )
    name = input("What is your contributor name? (letters, numbers, hyphens, max 32 chars) ").strip()
    if not _NAME_RE.match(name):
        print("Invalid name. Use letters, numbers, hyphens only.", file=sys.stderr)
        sys.exit(1)
    provider = input("Link an identity — provider key (e.g. github): ").strip().lower()
    provider_id = input(f"Your {provider or 'provider'} handle or address: ").strip()
    if not provider or not provider_id:
        print("Provider and handle are required.", file=sys.stderr)
        sys.exit(1)
    _complete_setup(name, provider, provider_id)


def _complete_setup(name: str, provider: str, provider_id: str) -> None:
    print(f"\nLinking identity (unverified TOFU) and creating API key for {name}...")
    code, data = _api_raw(
        "POST",
        "/api/onboard",
        {
            "name": name,
            "provider": provider,
            "provider_id": provider_id,
            "display_name": name,
        },
    )
    if code != 201 or not data or not data.get("api_key"):
        print(f"Setup failed (HTTP {code}): {data}", file=sys.stderr)
        sys.exit(1)
    _KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "api_key": data["api_key"],
        "contributor_id": name,
        "provider": provider,
        "provider_id": provider_id,
        "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
        "verified": False,
    }
    _KEYS_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    try:
        _KEYS_PATH.chmod(0o600)
    except OSError:
        pass
    print("Identity linked (unverified). You can verify ownership later with: cc verify")
    print(f"API key generated: {data['api_key'][:24]}...")
    print(f"Key saved to {_KEYS_PATH}")
    print(
        f"\nSetup complete! You are now: {name} (via {provider}:{provider_id}). "
        "Run `cc status` (after setting CC_API_KEY or using this shell's keys.json).",
    )


def cmd_verify(args: argparse.Namespace) -> None:
    """Optional post-setup: GitHub gist proof (or other provider) to mark identity verified."""
    _require_personal_key()
    k = _load_keys_file()
    cid = k.get("contributor_id") or os.environ.get("COHERENCE_CONTRIBUTOR")
    if not cid:
        print("No contributor_id in keys.json. Run: cc setup", file=sys.stderr)
        sys.exit(1)
    provider = getattr(args, "provider", None) or "github"
    code, chal = _api_raw(
        "POST",
        "/api/auth/verify/challenge",
        {"contributor_id": cid, "provider": provider},
    )
    if code != 200 or not chal:
        print("Could not create verification challenge.", file=sys.stderr)
        sys.exit(1)
    print(chal.get("instructions", ""))
    proof = getattr(args, "proof", None) or input("Paste proof URL or text: ").strip()
    if not proof:
        print("Proof required.", file=sys.stderr)
        sys.exit(1)
    pid = k.get("provider_id") or ""
    pr_code, result = _api_raw(
        "POST",
        "/api/auth/verify/proof",
        {
            "contributor_id": cid,
            "provider": provider,
            "provider_id": pid,
            "proof": proof,
        },
    )
    if pr_code == 200 and result and result.get("verified"):
        print(f"{provider} identity verified!")
        upd = dict(k)
        upd["verified"] = True
        _KEYS_PATH.write_text(json.dumps(upd, indent=2) + "\n", encoding="utf-8")
        try:
            _KEYS_PATH.chmod(0o600)
        except OSError:
            pass
    else:
        print(f"Verification failed (HTTP {pr_code}): {result}", file=sys.stderr)
        sys.exit(1)


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
    _require_personal_key()
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
    _require_personal_key()
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
    _require_personal_key()
    body = {
        "contributor_id": args.contributor or os.environ.get("COHERENCE_CONTRIBUTOR", "anonymous"),
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
    _require_personal_key()
    body = {
        "contributor_id": args.contributor or os.environ.get("COHERENCE_CONTRIBUTOR", "anonymous"),
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

    p_setup = sub.add_parser("setup", help="Contributor onboarding (TOFU identity + API key)")
    p_setup.add_argument("--force", action="store_true", help="Re-run even if keys.json exists")
    p_setup.add_argument("--name", default=None, help="Non-interactive: contributor id")
    p_setup.add_argument("--provider", default=None, help="Non-interactive: identity provider key")
    p_setup.add_argument("--provider-id", dest="provider_id", default=None, help="Non-interactive: handle")

    p_verify = sub.add_parser("verify", help="Verify linked identity (e.g. GitHub gist)")
    p_verify.add_argument("--provider", default="github", help="Identity provider")
    p_verify.add_argument("--proof", default=None, help="Proof URL or text (skip prompt)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "status": cmd_status, "ideas": cmd_ideas, "idea": cmd_idea,
        "share": cmd_share, "ask": cmd_ask, "stake": cmd_stake,
        "tasks": cmd_tasks, "nodes": cmd_nodes, "specs": cmd_specs,
        "contribute": cmd_contribute, "coherence": cmd_coherence, "run": cmd_run,
        "setup": cmd_setup, "verify": cmd_verify,
    }
    handler = cmd_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
