#!/usr/bin/env python3
"""Detached transmute+capture worker — spawned by the Stop hook.

A hook CAN reason; it just must not BLOCK. So capture_hook spawns this worker in
its own session and returns immediately. Here we transmute the turn (routed
reasoner: a local model by default, the subscription CLI if configured — never a
metered API) and write the full (request, raw, transmuted) pair. If the reasoner
is unreachable, the raw turn is still captured so the corpus grows.

Input: argv[1] = path to a temp JSON {request, raw, lane}; deleted after read.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # mcp-server/


def main() -> int:
    if len(sys.argv) < 2:
        return 0
    tmp = sys.argv[1]
    try:
        payload = json.loads(Path(tmp).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return 0
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    try:
        from coherence_mcp_server import form_cli_tools as fct
        fct.transmute_and_capture(
            payload.get("request", ""), payload.get("raw", ""),
            payload.get("lane", "agent-cli:claude-code"),
        )
    except Exception:  # noqa: BLE001 — last resort: raw capture so the corpus grows
        try:
            from coherence_mcp_server import form_cli_tools as fct
            fct.catalog_capture(payload.get("request", ""), payload.get("raw", ""),
                                "", payload.get("lane", ""), "turn-raw")
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
