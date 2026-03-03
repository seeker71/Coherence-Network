#!/usr/bin/env python3
"""ChatGPT web backup using Playwright.

This script mirrors the user's fallback pattern for cases where normal API routes
are throttled or unavailable:
- tries chatgpt.com first, then chat.openai.com
- supports persisted storage state for one-time interactive login
- can run headless or headed
- returns the most recent answer text for the submitted question
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional, List

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


CHATGPT_URLS = [
    "https://chatgpt.com/",
    "https://chat.openai.com/",
]



def _now_ms() -> int:
    return int(time.time() * 1000)


def _find_chat_input(page):
    # Prefer stable patterns first, then fallback to generic editable containers.
    selectors: list[str] = [
        "textarea",
        "div[contenteditable='true']",
        "[role='textbox']",
        "textarea[aria-label*='Message' i]",
        "div[aria-label*='message' i][contenteditable='true']",
        "[data-testid*='chat-input' i]",
    ]
    for selector in selectors:
        try:
            for idx in range(8):
                loc = page.locator(selector).nth(idx)
                if loc.count() > 0 and loc.first.is_visible():
                    return loc.first
        except Exception:
            continue

    return None


def _page_text(page) -> str:
    for selector in ["main", "#__next", "body"]:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                txt = loc.inner_text(timeout=1500)
                if txt and txt.strip():
                    return txt
        except Exception:
            pass

    try:
        return page.inner_text("body")
    except Exception:
        return ""


def _find_send(page) -> bool:
    candidates = [
        page.get_by_role("button", name="Send"),
        page.get_by_role("button", name="Submit"),
        page.locator('button[type="submit"]'),
        page.locator('[aria-label*="Send" i]'),
        page.locator('[data-testid*="send" i]'),
    ]
    for candidate in candidates:
        try:
            if candidate.count() == 0:
                continue
            btn = candidate.first
            if btn.is_enabled():
                btn.click()
                return True
        except Exception:
            continue
    return False


def _wait_for_settle(page, before_text: str, timeout_s: int) -> str:
    deadline = time.time() + timeout_s
    last = before_text

    while time.time() < deadline:
        current = _page_text(page)
        if current and current != last:
            last = current
            break
        time.sleep(0.25)
    else:
        raise PWTimeoutError("Timed out waiting for any page text change after sending.")

    stable_ticks = 0
    while time.time() < deadline:
        current = _page_text(page)
        if current == last:
            stable_ticks += 1
        else:
            stable_ticks = 0
            last = current
        if stable_ticks >= 8:
            return last
        time.sleep(0.25)

    raise PWTimeoutError("Timed out waiting for response text to settle.")


def _extract_answer(after_text: str, question: str, max_chars: int = 2500) -> str:
    # Best effort: take text after the last occurrence of the submitted question.
    tail = after_text[-12000:] if after_text else ""
    idx = tail.rfind(question.strip())
    if idx != -1:
        answer = tail[idx + len(question.strip()):].strip()
        return answer[-max_chars:].strip() if answer else ""

    # Fallback: return final chunk of transcript.
    return tail[-max_chars:].strip()


def _goto_first(page, urls: List[str]) -> str:
    last_error: Optional[Exception] = None
    for url in urls:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1_200)
            return url
        except Exception as exc:  # pragma: no cover - network/session dependent
            last_error = exc
            continue

    raise RuntimeError(f"Could not open any ChatGPT URL ({last_error}).")


def _ensure_session_and_input(page, state_path: str, headed: bool):
    input_field = _find_chat_input(page)
    if input_field:
        return input_field, True

    if not headed:
        return None, False

    print("\nNo chat input detected. Complete login once in the opened browser window,")
    print("send any text you would normally send to ChatGPT, then press Enter here.")
    input()

    try:
        page.context.storage_state(path=state_path)
        print(f"Saved storage state to: {state_path}")
    except Exception as exc:
        print(f"Warning: storage save failed: {exc}", file=sys.stderr)

    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1_200)
    return _find_chat_input(page), bool(_find_chat_input(page))


def _choose_urls(platform: str) -> List[str]:
    if platform == "chatgpt":
        return CHATGPT_URLS[:1]
    return CHATGPT_URLS


def _extract_answer_preview(text: str) -> str:
    return text[:2500].replace("\n", " ").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-q", "--question", required=True)
    parser.add_argument(
        "--platform",
        choices=["auto", "chatgpt"],
        default="auto",
        help="Which UI endpoints to use first.",
    )
    parser.add_argument(
        "--state",
        default=os.path.join("output", "playwright", "chatgpt_storage_state.json"),
        help="Path to saved Playwright storage state file.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (headful is easier for first login).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds to wait for response settle.",
    )
    parser.add_argument("--debug", action="store_true", help="Print extra debug context.")
    args = parser.parse_args()

    state_path = args.state
    headed = not args.headless

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = (
            browser.new_context(storage_state=state_path)
            if os.path.exists(state_path)
            else browser.new_context()
        )
        page = context.new_page()

        start_url = _goto_first(page, _choose_urls(args.platform))
        if args.debug:
            print(f"[debug] opened: {start_url} -> current: {page.url}")

        chat_input, ok = _ensure_session_and_input(page, state_path, headed=headed)
        if not ok or not chat_input:
            print(
                "Could not locate chat input. Rerun without --headless for manual login and try again. ",
                file=sys.stderr,
            )
            return 2

        before = _page_text(page)
        try:
            chat_input.click()
        except Exception:
            pass

        try:
            chat_input.fill(args.question)
        except Exception:
            chat_input.type(args.question, delay=5)

        sent = _find_send(page)
        if not sent:
            try:
                chat_input.press("Enter")
            except Exception:
                pass

        if not sent and args.debug:
            print("[debug] Could not find explicit send button; used Enter fallback.", file=sys.stderr)

        try:
            after = _wait_for_settle(page, before_text=before, timeout_s=args.timeout)
        except PWTimeoutError as exc:
            print(str(exc), file=sys.stderr)
            if args.debug:
                print(f"[debug] page.url: {page.url}", file=sys.stderr)
            return 3

        answer = _extract_answer(after, args.question)
        if args.debug:
            print(f"[debug] raw_answer_preview={_extract_answer_preview(answer)}")
        print(answer or "[No answer parsed. Rerun with --debug for diagnostics.]")

        if headed and not os.path.exists(state_path):
            try:
                context.storage_state(path=state_path)
            except Exception:
                pass

        context.close()
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
