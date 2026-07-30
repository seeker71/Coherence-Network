"""Carry the hub's existing grocery float into the graph, so the ledger opens on a true number.

The graph is the source of truth for the grocery ledger; the hub's sheet is a
mirror. The sheet was kept by hand for months before the app existed, so the
graph starts empty while the household genuinely holds float. Until the opening
history is carried across, the app shows the manager `0` left to spend and any
balance alert fires against a ledger that has never seen a top-up.

This walks the events already recorded in the sheet through the real endpoints —
`POST /api/grocery/spend` and `POST /api/grocery/topup` — so every amount is
converted by the Form recipe on the c-bootstrapped kernel rather than written
straight into the graph. The number the app shows is then the number the recipe
computed, by the same path a market run takes.

Idempotent: an event already present with the same day, amount, and description
is left alone, so a re-run after a partial failure carries only what is missing.

Usage:
    python3 scripts/seed_grocery_ledger.py --token <writer-token> [--api URL] [--dry-run]

The token belongs to a household member with write access (a resident, or staff
carrying the vouch). Nothing here is specific to one household: the events are
read from a CSV so a different hub seeds its own opening balance with its own
file.

    python3 scripts/seed_grocery_ledger.py --token <t> --events my-ledger.csv

CSV columns: date (YYYY-MM-DD), amount_idr (signed: buy positive, top-up
negative), description.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import httpx

# The hub's ledger as it stood on 2026-07-30, carried from the sheet that was
# kept by hand. Amounts are signed the way the sheet signs them: a purchase is
# positive, a top-up negative. Descriptions the sheet never carried stay empty
# rather than invented — an unnamed purchase is honest, a guessed one is not.
DEFAULT_EVENTS: list[tuple[str, int, str]] = [
    ("2026-07-23", 385_000, ""),
    ("2026-07-23", 477_300, ""),
    ("2026-07-23", 351_000, ""),
    ("2026-07-26", 125_000, ""),
    ("2026-07-26", 443_000, ""),
    ("2026-07-26", -1_781_300, "top up"),
    ("2026-07-29", 197_000, ""),
    ("2026-07-29", 869_000, ""),
    ("2026-07-29", 162_000, ""),
    ("2026-07-29", -4_000_000, "top up"),
]

DEFAULT_API = "https://api.coherencycoin.com"


def load_events(path: Path | None) -> list[tuple[str, int, str]]:
    if path is None:
        return DEFAULT_EVENTS
    events: list[tuple[str, int, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            events.append((
                row["date"].strip(),
                int(str(row["amount_idr"]).replace(",", "").replace("_", "")),
                (row.get("description") or "").strip(),
            ))
    return events


def thousands_of(amount_idr: int) -> str:
    """The typed string the recipe expects — the *ribu* the thumb would have typed.

    The app's whole contract is that a person types thousands: 123.5 becomes
    123500. Seeding through the same door means passing the amount the way a
    thumb would, and letting the recipe do the arithmetic. Trailing zeros are
    trimmed so 385000 reads as "385", not "385.000".
    """
    text = f"{abs(amount_idr) / 1000:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def existing_keys(client: httpx.Client, api: str, token: str) -> set[tuple[str, int]]:
    """(day, magnitude) already in the graph, read through the door out.

    The export carries `amount_idr` as a magnitude — the sign lives in the
    entry's kind, which the CSV does not spell out — so the key compares
    absolute values. Two events on one day with the same magnitude in opposite
    directions would read as one; a household that genuinely does that should
    seed from a CSV and check the result.
    """
    response = client.get(f"{api}/api/grocery/export.csv", params={"token": token})
    response.raise_for_status()
    keys: set[tuple[str, int]] = set()
    for row in csv.DictReader(response.text.splitlines()):
        day = (row.get("date") or "").strip()
        raw = (row.get("amount_idr") or "0").strip() or "0"
        try:
            keys.add((day, abs(int(float(raw)))))
        except ValueError:
            continue
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True, help="a household writer token")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--events", type=Path, default=None, help="CSV of opening events")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events = load_events(args.events)
    planned = -sum(amount for _, amount, _ in events)
    print(f"{len(events)} opening events; they carry a remaining balance of Rp{planned:,}")

    with httpx.Client(timeout=30.0) as client:
        try:
            present = existing_keys(client, args.api, args.token)
        except httpx.HTTPStatusError as exc:
            print(f"could not read the existing ledger: HTTP {exc.response.status_code}")
            print("the token needs write access — a resident grants it, or use a resident's own token")
            return 1
        if present:
            print(f"the graph already holds {len(present)} event(s); those are left alone")

        carried = skipped = 0
        for day, amount, description in events:
            if (day, abs(amount)) in present:
                skipped += 1
                continue
            is_topup = amount < 0
            path = "/api/grocery/topup" if is_topup else "/api/grocery/spend"
            payload: dict[str, object] = {
                "actor_token": args.token,
                "amount": thousands_of(amount),
                "spent_on": day,
            }
            if description:
                payload["note"] = description
            label = f"{day}  {'top up' if is_topup else 'buy':7} Rp{abs(amount):,}"
            if args.dry_run:
                print(f"  would carry  {label}")
                carried += 1
                continue
            reply = client.post(f"{args.api}{path}", json=payload)
            if reply.status_code >= 400:
                print(f"  FAILED       {label} -> HTTP {reply.status_code}: {reply.text[:160]}")
                return 1
            body = reply.json()
            got = body.get("amount_idr", body.get("signed_idr"))
            print(f"  carried      {label}  -> amount_idr {got}")
            carried += 1

        print(f"\ncarried {carried}, already present {skipped}")
        if not args.dry_run:
            totals = client.get(f"{args.api}/api/grocery/totals", params={"token": args.token})
            if totals.status_code < 400:
                print(f"the ledger now reads remaining Rp{totals.json().get('remaining_idr', 0):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
