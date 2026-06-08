#!/usr/bin/env python3
"""Validate locale surfaces for default-locale parity and English-bias drift."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCALE = "en"
WEB_MESSAGES_DIR = ROOT / "web" / "messages"
CLI_MESSAGES_DIR = ROOT / "cli" / "lib" / "messages"
WEB_MANIFEST = WEB_MESSAGES_DIR / "manifest.ts"
API_MANIFEST = ROOT / "api" / "app" / "data" / "locale_manifest.json"

NON_DEFAULT_BIASED_PHRASES = (
    "english anchor",
    "english bundle",
    "falls back to english",
    "fallback to english",
    "seeded from the english",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            out.update(_flatten(child, path))
    else:
        out[prefix] = value
    return out


def _json_locale_codes(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        path.stem
        for path in directory.glob("*.json")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", path.stem)
    )


def _web_manifest_codes() -> list[str]:
    if not WEB_MANIFEST.exists():
        return []
    text = WEB_MANIFEST.read_text(encoding="utf-8")
    match = re.search(r"export const LOCALES = (\[.*?\]) as const;", text, re.S)
    if not match:
        return []
    return sorted(entry["code"] for entry in json.loads(match.group(1)))


def _api_manifest_entries() -> list[dict[str, str]]:
    if not API_MANIFEST.exists():
        return []
    manifest = _read_json(API_MANIFEST)
    entries = manifest.get("locales", []) if isinstance(manifest, dict) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def _attunement_meta(bundle: dict[str, Any], code: str) -> dict[str, str]:
    raw = bundle.get("_attunement", {}) if isinstance(bundle, dict) else {}
    attunement = raw if isinstance(raw, dict) else {}
    name = attunement.get("name") or attunement.get("languageName") or code
    native_name = attunement.get("nativeName") or attunement.get("native_name") or name
    return {"name": str(name), "native_name": str(native_name)}


def validate() -> list[str]:
    errors: list[str] = []
    web_codes = _json_locale_codes(WEB_MESSAGES_DIR)
    cli_codes = _json_locale_codes(CLI_MESSAGES_DIR)

    if DEFAULT_LOCALE not in web_codes:
        return [f"web/messages/{DEFAULT_LOCALE}.json is required"]

    default_bundle = _read_json(WEB_MESSAGES_DIR / f"{DEFAULT_LOCALE}.json")
    default_keys = set(_flatten(default_bundle))
    web_bundles = {
        code: _read_json(WEB_MESSAGES_DIR / f"{code}.json")
        for code in web_codes
    }

    for code, bundle in web_bundles.items():
        keys = set(_flatten(bundle))
        missing = sorted(default_keys - keys)
        extra = sorted(keys - default_keys)
        if missing:
            errors.append(f"web/messages/{code}.json missing keys: {', '.join(missing[:8])}")
        if extra:
            errors.append(f"web/messages/{code}.json extra keys: {', '.join(extra[:8])}")

    manifest_codes = _web_manifest_codes()
    if manifest_codes != web_codes:
        errors.append(
            f"web/messages/manifest.ts locales {manifest_codes or 'unreadable'} "
            f"do not match installed web bundles {web_codes}"
        )

    api_entries = _api_manifest_entries()
    api_codes = sorted(str(entry.get("code")) for entry in api_entries if entry.get("code"))
    if api_codes != web_codes:
        errors.append(
            f"api/app/data/locale_manifest.json locales {api_codes or 'unreadable'} "
            f"do not match installed web bundles {web_codes}"
        )
    else:
        api_by_code = {entry["code"]: entry for entry in api_entries if entry.get("code")}
        for code, bundle in web_bundles.items():
            expected = _attunement_meta(bundle, code)
            actual = api_by_code.get(code, {})
            if actual.get("name") != expected["name"] or actual.get("native_name") != expected["native_name"]:
                errors.append(
                    f"api locale metadata for {code} does not match web _attunement metadata"
                )

    if cli_codes != web_codes:
        errors.append(
            f"cli/lib/messages locales {cli_codes or 'unreadable'} "
            f"do not match installed web bundles {web_codes}"
        )

    for code, bundle in web_bundles.items():
        if code == DEFAULT_LOCALE:
            continue
        for key, value in _flatten(bundle).items():
            if not isinstance(value, str):
                continue
            lower_value = value.lower()
            for phrase in NON_DEFAULT_BIASED_PHRASES:
                if phrase in lower_value:
                    errors.append(
                        f"web/messages/{code}.json:{key} contains biased phrase {phrase!r}"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true", help="Print a one-line reading.")
    args = parser.parse_args()

    errors = validate()
    if errors:
        if args.summary:
            print(f"locale surface drift: {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
        return 1

    summary = (
        "locale surfaces aligned: "
        f"{len(_json_locale_codes(WEB_MESSAGES_DIR))} web/API/CLI locales, "
        "message parity clean, non-default bundles free of English-anchor wording"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
