#!/usr/bin/env python3
"""Run Telegram diagnostics: config, webhook simulation, test-send, diagnostics endpoint.

Usage:
  python scripts/telegram_diagnostics.py [base_url]

Requires API running. Default base_url: http://localhost:8000
"""

import json
import os
import sys

# Ensure api dir is on path and load .env
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(_api_dir)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CHAT_ID = (os.environ.get("TELEGRAM_CHAT_IDS") or "").strip().split(",")[0].strip()


def main():
    print("=== Telegram diagnostics ===\n")
    print(f"Base URL: {BASE}")
    print(f"Chat ID (from TELEGRAM_CHAT_IDS): {CHAT_ID or '(not set)'}\n")

    with httpx.Client(timeout=10.0) as c:
        # 1. Config / diagnostics
        print("1. GET /api/agent/telegram/diagnostics")
        try:
            r = c.get(f"{BASE}/api/agent/telegram/diagnostics")
            if r.status_code == 200:
                d = r.json()
                print(f"   Config: has_token={d.get('config',{}).get('has_token')}")
                print(f"   Webhook events: {len(d.get('webhook_events', []))}")
                print(f"   Send results: {len(d.get('send_results', []))}")
                if d.get("send_results"):
                    last = d["send_results"][-1]
                    print(f"   Last send: ok={last.get('ok')} status={last.get('status_code')}")
                    if not last.get("ok") and last.get("response_text"):
                        print(f"   Response: {last['response_text'][:300]}")
            else:
                print(f"   {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")

        # 2. Simulate webhook (requires TELEGRAM_CHAT_IDS for chat/from ids)
        print("\n2. POST /api/agent/telegram/webhook (simulated /status)")
        if not CHAT_ID:
            print("   Skipped (TELEGRAM_CHAT_IDS not set)")
        else:
            try:
                chat_id_val = int(CHAT_ID) if CHAT_ID.isdigit() else CHAT_ID
                r = c.post(
                    f"{BASE}/api/agent/telegram/webhook",
                    json={
                        "message": {
                            "chat": {"id": chat_id_val},
                            "from": {"id": chat_id_val},
                            "text": "/status",
                        }
                    },
                )
                print(f"   {r.status_code} {r.text[:100]}")
            except Exception as e:
                print(f"   Error: {e}")

        # 3. Diagnostics again
        print("\n3. GET /api/agent/telegram/diagnostics (after webhook)")
        try:
            r = c.get(f"{BASE}/api/agent/telegram/diagnostics")
            if r.status_code == 200:
                d = r.json()
                for sr in d.get("send_results", [])[-3:]:
                    print(f"   send: chat_id={sr.get('chat_id')} ok={sr.get('ok')} status={sr.get('status_code')}")
                    if not sr.get("ok") and sr.get("response_text"):
                        print(f"      -> {sr['response_text'][:200]}")
        except Exception as e:
            print(f"   Error: {e}")

        # 4. Test outbound send
        print("\n4. POST /api/agent/telegram/test-send")
        try:
            r = c.post(f"{BASE}/api/agent/telegram/test-send", params={"text": "Diagnostic test"})
            if r.status_code == 200:
                d = r.json()
                print(f"   ok={d.get('ok')}")
                for res in d.get("results", []):
                    print(f"   chat_id={res.get('chat_id')} status={res.get('status_code')}")
                    rc = res.get("response")
                    if isinstance(rc, dict) and not rc.get("ok"):
                        print(f"      -> {json.dumps(rc)[:200]}")
            else:
                print(f"   {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")

    print("\nDone. Check Telegram for messages. If none, see send_results above.")


if __name__ == "__main__":
    main()
