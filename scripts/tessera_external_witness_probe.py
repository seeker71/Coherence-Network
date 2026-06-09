#!/usr/bin/env python3
"""Probe Tessera's public data surface as a compact external witness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


BASE_URL = "https://s3.us-west-2.amazonaws.com/tessera-embeddings"
DEFAULT_VERSION_PATH = "v1.1"
DEFAULT_VERSION = "1.1"
DEFAULT_VARIANT = "cambridge"
DEFAULT_YEAR = 2024
DEFAULT_LON = "0.15"
DEFAULT_LAT = "52.05"
DEFAULT_RANGE_BYTES = 4096


@dataclass(frozen=True)
class HttpWitness:
    url: str
    status: int
    content_length: int
    etag: str
    last_modified: str
    content_range: str = ""


def _request(url: str, *, method: str = "HEAD", range_bytes: int = 0, timeout: int = 20) -> tuple[HttpWitness, bytes]:
    headers: dict[str, str] = {}
    if method == "GET" and range_bytes > 0:
        headers["Range"] = f"bytes=0-{range_bytes - 1}"
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read() if method == "GET" else b""
            info = response.info()
            length_text = info.get("Content-Length", "0")
            return (
                HttpWitness(
                    url=url,
                    status=response.status,
                    content_length=int(length_text) if length_text.isdigit() else len(body),
                    etag=info.get("ETag", "").strip('"'),
                    last_modified=info.get("Last-Modified", ""),
                    content_range=info.get("Content-Range", ""),
                ),
                body,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read() if method == "GET" else b""
        info = exc.headers
        length_text = info.get("Content-Length", "0")
        return (
            HttpWitness(
                url=url,
                status=exc.code,
                content_length=int(length_text) if length_text.isdigit() else len(body),
                etag=info.get("ETag", "").strip('"'),
                last_modified=info.get("Last-Modified", ""),
                content_range=info.get("Content-Range", ""),
            ),
            body,
        )


def _tile_name(lon: str, lat: str) -> str:
    return f"grid_{float(lon):.2f}_{float(lat):.2f}"


def _representation_path(version_path: str, variant: str) -> str:
    if version_path == "v1.1" and variant == "cambridge":
        return "global_0.1_degree_representation.cambridge"
    return "global_0.1_degree_representation"


def build_urls(version_path: str, variant: str, year: int, lon: str, lat: str) -> dict[str, str]:
    tile = _tile_name(lon, lat)
    representation = _representation_path(version_path, variant)
    tile_root = f"{BASE_URL}/{version_path}/{representation}/{year}/{tile}/{tile}"
    return {
        "manifest": f"{BASE_URL}/{version_path}/manifest.parquet",
        "embedding": f"{tile_root}.npy",
        "scales": f"{tile_root}_scales.npy",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    urls = build_urls(args.version_path, args.variant, args.year, args.lon, args.lat)
    manifest, _ = _request(urls["manifest"], timeout=args.timeout)
    embedding, evidence = _request(urls["embedding"], method="GET", range_bytes=args.range_bytes, timeout=args.timeout)
    scales, _ = _request(urls["scales"], timeout=args.timeout)
    digest = hashlib.sha256(evidence).hexdigest()
    ok = manifest.status == 200 and embedding.status in {200, 206} and scales.status == 200 and len(evidence) > 0
    return {
        "source": {
            "name": "Tessera GeoTessera",
            "access": "anonymous public S3 plus GeoTessera Python and Zarr clients",
            "license": "CC0 embeddings; MIT client code",
            "base_url": BASE_URL + "/",
            "docs_url": "https://geotessera.readthedocs.io/en/latest/",
        },
        "dataset": {
            "version": args.version,
            "version_path": args.version_path,
            "variant": args.variant,
            "year": args.year,
        },
        "coordinate": {
            "lon": args.lon,
            "lat": args.lat,
            "tile": _tile_name(args.lon, args.lat),
        },
        "manifest": asdict(manifest),
        "embedding_tile": asdict(embedding),
        "scale_tile": asdict(scales),
        "range_evidence": {
            "range_start": 0,
            "range_end": max(0, len(evidence) - 1),
            "byte_count": len(evidence),
            "sha256": digest,
        },
        "answers": {
            "what": "Tessera embedding tile and byte-range hash",
            "where": f"{_tile_name(args.lon, args.lat)} centered at lon={args.lon}, lat={args.lat}",
            "when": f"{args.year} annual embedding",
            "who": "GeoTessera and University of Cambridge Tessera project",
            "how": "anonymous S3 HEAD plus byte-range GET hash",
            "why": "external witness anchor for Form question answers",
        },
        "ok": ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--version-path", default=DEFAULT_VERSION_PATH)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--lon", default=DEFAULT_LON)
    parser.add_argument("--lat", default=DEFAULT_LAT)
    parser.add_argument("--range-bytes", type=int, default=DEFAULT_RANGE_BYTES)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    if args.range_bytes <= 0:
        parser.error("--range-bytes must be positive")
    payload = build_payload(args)
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
