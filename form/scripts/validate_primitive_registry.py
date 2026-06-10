#!/usr/bin/env python3
"""Drift gate between the kernel native surface and primitive-registry.fk.

The registry (form/form-stdlib/primitive-registry.fk) is the body: every
kernel native declares (name, category, spec, verification recipe, expected
outside, lane) in the kernel-satsang ksat-part discipline, proven three-way
by tests/primitive-registry-band.fk. This script is the thin sensing carrier
that reads both sides and surfaces drift — it computes nothing the band
hasn't already proven, it only checks that the declared maps still match the
kernel source they describe.

Checks (exit 1 on any):
  - every Go kernel native (main.go registerNative + the fieldConstructors
    table + registerEnvNative) has a registry entry, and vice versa
  - every registry category token matches the Go attribution constructor
  - every lane-1 entry is present in all three kernels (rust + ts); every
    sibling-gapped name stays lane 0
  - no duplicate registrations in main.go (the write_form_binary shape)
  - no empty spec lines
  - the band's pinned counts (total / lane-1 / lane-0) match the registry

Report (always): lane totals, category histogram, the visible lane-0 tail
with reasons, sibling gaps, stdlib band circulation per native, and the
Go-only server.go host-IO surface as a named separate count.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FORM = Path(__file__).resolve().parent.parent
GO_MAIN = FORM / "form-kernel-go" / "main.go"
GO_SERVER = FORM / "form-kernel-go" / "server.go"
RS_MAIN = FORM / "form-kernel-rust" / "src" / "main.rs"
TS_KERNEL = FORM / "form-kernel-ts" / "src" / "kernel.ts"
REGISTRY = FORM / "form-stdlib" / "primitive-registry.fk"
BAND = FORM / "form-stdlib" / "tests" / "primitive-registry-band.fk"
TESTS_DIR = FORM / "form-stdlib" / "tests"

CAT_TOKENS = {
    "catCall": "call",
    "catAccess": "access",
    "catMethod": "method",
    "catCompare": "compare",
    "catListNat": "list",
    "catWitness": "witness",
    "catUndefined": "undefined",
}


def go_natives() -> tuple[dict[str, str], list[str]]:
    """(name -> category token) from main.go, plus duplicate names."""
    src = GO_MAIN.read_text()
    out: dict[str, str] = {}
    dups: list[str] = []
    for name, cat in re.findall(
        r'k\.registerNative\(\s*"([^"]+)",\s*(cat[A-Za-z]+)\(', src
    ):
        token = CAT_TOKENS.get(cat)
        if token is None and cat == "catFieldPrimitive":
            continue  # the table loop line, not a name
        if name in out:
            dups.append(name)
        out[name] = token or cat
    # fieldConstructors table — registered through one generic loop.
    table = re.search(r"fieldConstructors := \[\]struct \{.*?\n\t\}\n", src, re.S)
    if table:
        for name in re.findall(r'\{"([a-z_]+)",', table.group(0)):
            if name in out:
                dups.append(name)
            out[name] = "field"
    for name, cat in re.findall(
        r'k\.registerEnvNative\(\s*"([^"]+)",\s*(cat[A-Za-z]+)\(', src
    ):
        if name in out:
            dups.append(name)
        out[name] = CAT_TOKENS.get(cat, cat)
    return out, dups


def sibling_names(path: Path, patterns: list[str]) -> set[str]:
    src = path.read_text()
    names: set[str] = set()
    for pat in patterns:
        names |= set(re.findall(pat, src))
    return names


def rust_names() -> set[str]:
    return sibling_names(RS_MAIN, [
        r'register_(?:env_)?native\(\s*"([^"]+)"',
        r'native_field_constructor!\([^,]+,\s*[^,]+,\s*\d+,\s*"([^"]+)"',
        r'^\s*"(field_[a-z_]+)",\s*$',
    ])


def ts_names() -> set[str]:
    return sibling_names(TS_KERNEL, [
        r'register(?:Env)?Native\(\s*"([^"]+)"',
        r'\[\s*"([a-z_0-9?-]+)"\s*,\s*RBasic\.',
    ])


def registry_entries() -> list[dict]:
    """Parse (prim "name" "token" "spec" <verify> <expected> <mode>) cells."""
    src = REGISTRY.read_text()
    entries = []
    for m in re.finditer(r'\(prim "', src):
        start = m.start()
        depth = 0
        end = start
        in_str = False
        prev = ""
        for i in range(start, len(src)):
            ch = src[i]
            if in_str:
                if ch == '"' and prev != "\\":
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            prev = ch
        cell = src[start:end]
        head = re.match(r'\(prim "([^"]+)" "([^"]+)" "([^"]*)"', cell)
        tail = re.search(r"\)\s+(-?\d+)\s+([01])\)$", cell)
        if not head or not tail:
            print(f"FAIL unparseable registry cell at offset {start}: {cell[:80]}...")
            sys.exit(1)
        entries.append({
            "name": head.group(1),
            "token": head.group(2),
            "spec": head.group(3),
            "expected": int(tail.group(1)),
            "mode": int(tail.group(2)),
            "has_verify": "(defn pv-" in cell,
        })
    return entries


def band_pins() -> dict[str, int]:
    src = BAND.read_text()
    total = re.search(r"\(eq \(len reg\) (\d+)\)", src)
    verified = re.search(r"\(eq \(prim-verified-count reg\) (\d+)\)", src)
    lane1 = re.search(r"\(eq \(prim-mode-count reg 1\) (\d+)\)", src)
    lane0 = re.search(r"\(eq \(prim-mode-count reg 0\) (\d+)\)", src)
    if not (total and verified and lane1 and lane0):
        print("FAIL band pins not found in primitive-registry-band.fk")
        sys.exit(1)
    return {
        "total": int(total.group(1)),
        "verified": int(verified.group(1)),
        "lane1": int(lane1.group(1)),
        "lane0": int(lane0.group(1)),
    }


def stdlib_band_circulation(names: list[str]) -> set[str]:
    blob = "".join(
        p.read_text(errors="replace") for p in sorted(TESTS_DIR.glob("*.fk"))
    )
    seen = set()
    for n in names:
        if re.search(r"\(" + re.escape(n) + r"[\s)]", blob):
            seen.add(n)
    return seen


def main() -> int:
    go, go_dups = go_natives()
    rs = rust_names()
    ts = ts_names()
    entries = registry_entries()
    by_name = {e["name"]: e for e in entries}
    failures: list[str] = []

    if go_dups:
        failures.append(
            f"duplicate registerNative in main.go: {sorted(set(go_dups))}"
        )

    missing = sorted(set(go) - set(by_name))
    if missing:
        failures.append(f"kernel natives missing from registry: {missing}")
    phantom = sorted(set(by_name) - set(go))
    if phantom:
        failures.append(f"registry names not registered in main.go: {phantom}")

    for name in sorted(set(go) & set(by_name)):
        want, got = go[name], by_name[name]["token"]
        if want != got:
            failures.append(
                f"category drift {name}: go declares {want}, registry holds {got}"
            )

    gaps = {n for n in go if n not in rs or n not in ts}
    for e in entries:
        if e["mode"] == 1 and e["name"] in gaps:
            failures.append(
                f"lane-1 entry {e['name']} is sibling-gapped "
                f"(rust={'y' if e['name'] in rs else 'n'} "
                f"ts={'y' if e['name'] in ts else 'n'})"
            )
        if not e["spec"].strip():
            failures.append(f"empty spec for {e['name']}")
        if not e["has_verify"]:
            failures.append(f"no verification recipe declared for {e['name']}")

    lane1 = sum(1 for e in entries if e["mode"] == 1)
    lane0 = sum(1 for e in entries if e["mode"] == 0)
    pins = band_pins()
    if pins["total"] != len(entries) or pins["lane1"] != lane1 \
            or pins["lane0"] != lane0 or pins["verified"] != lane1:
        failures.append(
            f"band pins drifted: band declares total={pins['total']} "
            f"lane1={pins['lane1']} lane0={pins['lane0']} "
            f"verified={pins['verified']}; registry holds "
            f"total={len(entries)} lane1={lane1} lane0={lane0}"
        )

    circulating = stdlib_band_circulation(list(by_name))
    declared_only = sorted(
        e["name"] for e in entries
        if e["mode"] == 0 and e["name"] not in circulating
    )

    cats: dict[str, int] = {}
    for e in entries:
        cats[e["token"]] = cats.get(e["token"], 0) + 1
    server_count = len(
        re.findall(r'k\.registerNative\(\s*"', GO_SERVER.read_text())
    ) if GO_SERVER.is_file() else 0

    print(f"natives: {len(go)} (go main.go surface)  registry: {len(entries)}")
    print(f"lanes: {lane1} in-band verified  ·  {lane0} carrier-declared")
    print("categories: " + "  ".join(
        f"{k}:{v}" for k, v in sorted(cats.items(), key=lambda kv: -kv[1])
    ))
    if gaps:
        print(f"sibling gaps ({len(gaps)}): " + " ".join(sorted(gaps)))
    print(
        f"band circulation: {len(circulating)}/{len(entries)} names appear "
        f"in stdlib tests"
    )
    if declared_only:
        print(
            f"declared-only tail ({len(declared_only)}, verification recipes "
            f"awaiting a carrier): " + " ".join(declared_only)
        )
    print(f"server.go host-IO surface (go-only, not in registry): {server_count}")

    if failures:
        print()
        for f in failures:
            print(f"FAIL {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
