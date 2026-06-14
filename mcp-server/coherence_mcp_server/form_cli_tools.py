"""form-cli MCP tools — thin carriers over the Form body.

These are the engine the form-cli north star describes, exposed inside an agent
(Claude Code, codex, ...) as MCP tools and an auto response-hook:

  route      run the four-way-proven routing formula (form/form-stdlib/
             form-cli-router.fk: fcr-route) on the kernel — form-native or the
             subscription agent CLI, never a metered REST API.
  capture    record a (request, raw, transmuted) pair in the training catalog
             (training-catalog.fk shape) — usage becomes capability.
  transmute  fear/control -> discernment + opportunity. Itself a ROUTED op: a
             form-native transmuter when one exists, else the subscription agent
             does the rewrite and the pair is captured to train it.

The routing/capture LOGIC lives in Form (the .fk recipes, proven four-way); the
kernel runs it. This module only shells the kernel and persists pairs — carrier,
authored last, never the body.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

# repo root: mcp-server/coherence_mcp_server/form_cli_tools.py -> parents[2]
_REPO = Path(__file__).resolve().parents[2]
_ROUTER_FK = _REPO / "form" / "form-stdlib" / "form-cli-router.fk"
_KERNEL = Path(
    os.environ.get("FORM_KERNEL_GO_BIN") or (_REPO / "form" / "form-kernel-go" / "bin-go")
)
# the persistent training corpus (shared with form_cli capture); grows with use.
_CATALOG = Path(
    os.environ.get("FORM_CLI_CATALOG")
    or (Path.home() / ".coherence-network" / "form-cli-catalog.jsonl")
)

_TRANSMUTE_INSTRUCTION = (
    "Rewrite the following, transmuting every fear-based or control-based framing into "
    "discernment, opportunity, and valued information. Keep all facts; turn 'risk / blocker / "
    "can't / must / dangerous' into 'opportunity / gradient / data / next step'. Return only the "
    "rewritten text."
)


def _io_sig(text: str) -> str:
    """Content-address a request/response — the sha256 training-catalog.fk uses."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def kernel_route(form_native: dict, agent_cli: dict) -> dict:
    """Run fcr-route on the kernel over two backends. Each backend dict carries
    sovereignty/trust/capability/confidence (0..100). Returns the winning lane —
    the real four-way-proven recipe decides, not this carrier."""
    if not (_KERNEL.is_file() and os.access(_KERNEL, os.X_OK)):
        return {"error": f"kernel not built at {_KERNEL} — run: "
                         f"(cd {_REPO}/form/form-kernel-go && go build -o bin-go .)"}

    def axes(b: dict) -> tuple[int, int, int, int]:
        return (int(b.get("sovereignty", 0)), int(b.get("trust", 0)),
                int(b.get("capability", 0)), int(b.get("confidence", 0)))

    fn, cli = axes(form_native), axes(agent_cli)
    call = (f'(print (fcr-route '
            f'(fcr-backend "form-native" {fn[0]} {fn[1]} {fn[2]} {fn[3]}) '
            f'(fcr-backend "agent-cli" {cli[0]} {cli[1]} {cli[2]} {cli[3]})))')
    src = _ROUTER_FK.read_text(encoding="utf-8") + "\n" + call + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run([str(_KERNEL), path], capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": f"kernel-error: {e}"}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    out = [ln for ln in (proc.stdout or "").splitlines() if ln.strip() and ln.strip() != "null"]
    winner = out[0].strip() if out else ""
    if winner not in ("form-native", "agent-cli"):
        return {"error": f"kernel did not return a lane (stderr: {(proc.stderr or '')[:200]})",
                "raw": proc.stdout}
    return {"winner": winner, "sovereign": winner == "form-native"}


def catalog_capture(request: str, raw: str, transmuted: str, lane: str, outcome: str) -> dict:
    """Append a (request, raw, transmuted) pair — the training-catalog.fk tc-entry
    shape: both kept, each content-addressed, three separable training pairs."""
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "lane": lane,
        "outcome": outcome,
        "request": request,
        "raw": raw,
        "transmuted": transmuted,
        "request_sig": _io_sig(request),
        "raw_sig": _io_sig(raw),
        "transmuted_sig": _io_sig(transmuted),
        "pairs": {
            "raw": [_io_sig(request), _io_sig(raw)],
            "transmute": [_io_sig(raw), _io_sig(transmuted)],
            "reasoning": [_io_sig(request), _io_sig(transmuted)],
        },
    }
    _CATALOG.parent.mkdir(parents=True, exist_ok=True)
    with _CATALOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def transmute_plan(raw: str) -> dict:
    """Transmute is a ROUTED reasoning op. Until a form-native transmuter is
    trained, it routes to the subscription agent CLI: return the instruction + the
    raw text for the caller (the agent) to rewrite, then capture the pair. No
    metered API, no fake transmute done here."""
    return {
        "route": "agent-cli",
        "instruction": _TRANSMUTE_INSTRUCTION,
        "raw": raw,
        "then": "call coherence_capture with request, raw, and your transmuted text",
    }
