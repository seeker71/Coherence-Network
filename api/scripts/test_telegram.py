#!/usr/bin/env python3
"""Test Telegram integration: outbound alert and optional API flow.

Run from api/:  python scripts/test_telegram.py
Requires: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS in .env
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure api/ is on path and load .env
api_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(api_dir))
os.chdir(api_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(api_dir / ".env")
except ImportError:
    pass  # No dotenv; rely on exported env


async def main() -> int:
    from app.services import telegram_adapter

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids = os.environ.get("TELEGRAM_CHAT_IDS", "").strip()

    if not token or not chat_ids:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_IDS in .env")
        print("Copy api/.env.example to api/.env and add your values.")
        print("See docs/API-KEYS-SETUP.md for setup steps.")
        return 1

    print("Sending test alert to Telegram...")
    ok = await telegram_adapter.send_alert(
        "*Coherence Agent* — Test alert\n\n"
        "If you see this, the integration works."
    )
    if ok:
        print("OK — Check Telegram for the message.")
    else:
        print("FAIL — Could not send.")
        print("Tip: You must message the bot first! Open Telegram → search @Coherence_Network_bot → tap Start")
        return 1

    # Optional: test via API (create task, trigger needs_decision alert)
    if "--api" in sys.argv:
        import httpx
        base = os.environ.get("API_BASE_URL", "http://localhost:8000")
        print(f"\nTesting API flow (base={base})...")
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"{base}/api/agent/tasks",
                json={"direction": "Test task for Telegram alert", "task_type": "impl"},
            )
            if r.status_code != 201:
                print(f"API error: {r.status_code} {r.text}")
                return 1
            task_id = r.json()["id"]
            r2 = await c.patch(
                f"{base}/api/agent/tasks/{task_id}",
                json={"status": "needs_decision", "output": "Test output"},
            )
            if r2.status_code != 200:
                print(f"API PATCH error: {r2.status_code}")
                return 1
        print("OK — Alert should appear in Telegram (needs_decision).")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
