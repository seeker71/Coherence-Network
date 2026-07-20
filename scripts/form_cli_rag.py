#!/usr/bin/env python3
"""Filesystem/DB carrier for the native form-cli's self-healing memory.

Python owns only cold-start materialization: enumerate source bytes, resolve the
exact ARTIFACT REF+CTOR persisted in the substrate, stage native embedding batches,
and atomically serialize the disposable index.  Semantic features, embedding,
ranking, sufficiency, answer selection, and trust decisions live only in the
c-bootstrapped coherence-kernel form-cli.

Every ordinary index row binds a full source SHA-256 and exact answer SHA-256 to
the structured ARTIFACT CTOR.  The bridge refuses edited-but-unpersisted sources.
Every query-time receipt is short-lived HMAC-authenticated and includes the exact
query digest and persisted source digest; public SHA-only receipts are not trust.

Usage:
  form_cli_rag.py build  [--index PATH] [--docs DIR ...]   # full (re)embed over the body
  form_cli_rag.py heal   [--index PATH] [--docs DIR ...]   # delta-only: embed what drifted
  form_cli_rag.py fresh  [--index PATH]                    # report drift without changing it
  form_cli_rag.py validate-index [--index PATH]             # schema/stamp/integrity gate
"""
from __future__ import annotations
import argparse
import glob
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Source worktrees keep the package at ROOT/api/app; the production API image
# flattens api/ into /app, so copied deployment scripts see ROOT/app instead.
# Select the package-bearing root explicitly in either layout.
API_ROOT = ROOT if os.path.isdir(os.path.join(ROOT, "app")) else os.path.join(ROOT, "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from app.services.grounding_source import read_grounding_source  # noqa: E402

INDEX = os.path.expanduser("~/.coherence-network/rag-index/index.jsonl")
INDEX_SCHEMA = "nodeid-rag-v2"
EMBEDDING_KIND = "form-semantic-v2"
INDEX_STAMP_SCHEMA = "native-rag-index-stamp-v1"
ATTESTATION_LIFETIME_SECONDS = 60
NATIVE_EMBED_REQUEST_MAX_BYTES = 4 * 1024 * 1024
# The emitted carrier materializes a request's JSONL result before returning it.
# Bound cardinality independently of input bytes so a corpus containing many
# short cells cannot exhaust the carrier while assembling its response.
NATIVE_EMBED_REQUEST_MAX_ITEMS = 128
NATIVE_EMBED_TEXT_MAX_BYTES = 600
NATIVE_CARRIER_RECEIPT = Path(ROOT) / ".cache" / "form-cli-native" / "selected.json"
NATIVE_SOURCE_DIGEST_FILE = (
    Path(ROOT) / "form" / "form-stdlib" / "bootstrap" / "form-cli.source.sha256"
)

SOURCES = [
    ("recipe",    "form/form-stdlib/*.fk"),
    ("spec",      "specs/*.md"),
    ("concept",   "docs/vision-kb/concepts/*.md"),
    ("substrate", "docs/coherence-substrate/*.form"),
    ("teaching",  "docs/shared/*.md"),
]


def _native_cli_path() -> Path:
    """Read and re-prove the carrier selected by the outer host shell."""
    try:
        receipt = json.loads(NATIVE_CARRIER_RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "verified native form-cli receipt missing; run "
            "scripts/ensure_form_cli_native.sh"
        ) from exc
    if receipt.get("schema") != "selected-form-cli-carrier-v1":
        raise RuntimeError("verified native form-cli receipt schema mismatch")
    raw = receipt.get("native_path")
    binary_digest = receipt.get("binary_sha256")
    source_digest = receipt.get("source_sha256")
    if not isinstance(raw, str) or not raw:
        raise RuntimeError("verified native form-cli receipt has no carrier path")
    binary = Path(raw)
    try:
        current_binary_digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        current_source_digest = NATIVE_SOURCE_DIGEST_FILE.read_text(
            encoding="utf-8"
        ).strip()
    except OSError as exc:
        raise RuntimeError("verified native form-cli receipt target is unreadable") from exc
    if current_binary_digest != binary_digest:
        raise RuntimeError("verified native form-cli receipt binary digest mismatch")
    if current_source_digest != source_digest:
        raise RuntimeError("verified native form-cli receipt source digest mismatch")
    return binary


def _bounded_native_embed_text(text: str) -> str:
    """Return at most the carrier's proven UTF-8 byte projection.

    The complete persisted source remains independently bound by its source
    digest and ARTIFACT CTOR. This bound controls the exact evidence excerpt
    carried through native retrieval and answer materialization.
    """
    raw = text.encode("utf-8")
    if len(raw) <= NATIVE_EMBED_TEXT_MAX_BYTES:
        return text
    return raw[:NATIVE_EMBED_TEXT_MAX_BYTES].decode("utf-8", errors="ignore")


def _grounded_excerpt(text: str) -> tuple[str, bytes, str]:
    """Create the exact bounded evidence excerpt carried by the native index."""
    excerpt = _bounded_native_embed_text(text)
    payload = excerpt.encode("utf-8")
    return excerpt, payload, hashlib.sha256(payload).hexdigest()


def _native_embed_batch(items: list[tuple[str, str]]) -> dict[str, list[int]]:
    """Ask one c-bootstrapped process to embed the complete batch.

    Python stages bytes and serializes the resulting cache; semantic concepts,
    token normalization, hashing, ranking, and sufficiency remain exclusively
    in coherence-kernel.
    """
    if not items:
        return {}
    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_bytes = 0
    for item in items:
        item_id, value = item
        line_bytes = (
            len(item_id.encode("utf-8").hex())
            + 1
            + len(value.encode("utf-8").hex())
            + 1
        )
        if line_bytes > NATIVE_EMBED_REQUEST_MAX_BYTES:
            raise RuntimeError(f"native embed item exceeds carrier cap: {item_id}")
        if current and (
            current_bytes + line_bytes > NATIVE_EMBED_REQUEST_MAX_BYTES
            or len(current) >= NATIVE_EMBED_REQUEST_MAX_ITEMS
        ):
            chunks.append(current)
            current = []
            current_bytes = 0
        current.append(item)
        current_bytes += line_bytes
    if current:
        chunks.append(current)

    vectors: dict[str, list[int]] = {}
    for chunk in chunks:
        chunk_vectors = _native_embed_chunk(chunk)
        if set(vectors).intersection(chunk_vectors):
            raise RuntimeError("native embed duplicate id across chunks")
        vectors.update(chunk_vectors)
    if set(vectors) != {item_id for item_id, _value in items}:
        raise RuntimeError("native embed batch reconciliation failed")
    return vectors


def _native_embed_chunk(items: list[tuple[str, str]]) -> dict[str, list[int]]:
    """Run one request chunk bounded by the carrier's byte and item caps."""
    if len(items) > NATIVE_EMBED_REQUEST_MAX_ITEMS:
        raise RuntimeError("native embed request exceeds carrier item cap")
    encoded_bytes = sum(
        len(item_id.encode("utf-8").hex())
        + 1
        + len(text.encode("utf-8").hex())
        + 1
        for item_id, text in items
    )
    if encoded_bytes > NATIVE_EMBED_REQUEST_MAX_BYTES:
        raise RuntimeError("native embed request exceeds carrier byte cap")
    binary = _native_cli_path()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"native form-cli unavailable: {binary}")
    home = Path.home()
    request_dir = home / ".coherence-network" / "rag-requests"
    request_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    metadata = request_dir.lstat()
    if request_dir.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise RuntimeError("native embed request directory is insecure")
    if os.name != "nt":
        os.chmod(request_dir, 0o700)
        metadata = request_dir.lstat()
        if (
            metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise RuntimeError("native embed request directory ownership/mode invalid")
    request_id = f"embed_{os.getpid()}_{secrets.token_hex(12)}"
    request_file = request_dir / f"{request_id}.embed"
    expected: dict[str, str] = {}
    try:
        with request_file.open("w", encoding="ascii", newline="\n") as staged:
            for item_id, text in items:
                id_hex = item_id.encode("utf-8").hex()
                if id_hex in expected:
                    raise RuntimeError(f"duplicate native embed id: {item_id}")
                expected[id_hex] = item_id
                staged.write(f"{id_hex}|{text.encode('utf-8').hex()}\n")
            staged.flush()
            os.fsync(staged.fileno())
        process = subprocess.run(
            [str(binary)],
            cwd=home,
            input=f"embed-request {request_id}\n".encode("ascii"),
            capture_output=True,
            timeout=300,
            check=False,
        )
        if process.returncode != 0:
            error = process.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"native embed-request failed ({process.returncode}): {error}"
            )
        try:
            output = process.stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise RuntimeError("native embed-request emitted invalid UTF-8") from exc
        vectors: dict[str, list[int]] = {}
        for line in output.splitlines():
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError("native embed-request emitted invalid JSONL") from exc
            if set(row) != {"id_hex", "embedding_kind", "vec"}:
                raise RuntimeError("native embed-request schema mismatch")
            id_hex = row["id_hex"]
            if id_hex not in expected or expected[id_hex] in vectors:
                raise RuntimeError("native embed-request id mismatch")
            if row["embedding_kind"] != EMBEDDING_KIND:
                raise RuntimeError("native embed-request kind mismatch")
            vec = row["vec"]
            if not isinstance(vec, list) or any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in vec
            ):
                raise RuntimeError("native embed-request vector schema mismatch")
            vectors[expected[id_hex]] = vec
        if set(vectors) != set(expected.values()):
            raise RuntimeError("native embed-request incomplete batch")
        return vectors
    finally:
        try:
            request_file.unlink()
        except FileNotFoundError:
            pass


def content_key(path: str) -> str:
    """Return the full persisted source identity, never an mtime/path proxy."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def _snippet(path: str) -> str:
    """Filesystem carrier for the shared exact answer-byte projection."""
    try:
        return read_grounding_source(path).snippet
    except OSError:
        return ""


LOCAL_DOC_EXTS = (".md", ".txt", ".org", ".rst", ".py", ".ts", ".tsx", ".js",
                  ".go", ".rs", ".fk", ".form", ".json", ".yaml", ".yml", ".sh", ".html")


def _local_doc_paths(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for fn in sorted(filenames):
            if fn.lower().endswith(LOCAL_DOC_EXTS):
                yield os.path.join(dirpath, fn)


def _canonical_source_path(path: str) -> str:
    """Return the platform-independent source identity stored in substrate."""
    return path.replace("\\", "/")


def _body_cells(doc_roots=None):
    """Enumerate sources as ``(source_path, kind, filesystem_path)``.

    ``source_path`` locates bytes and is not an identity. ``_embed_cell`` binds
    each source to its independently resolved substrate CTOR NodeID.
    """
    for kind, pat in SOURCES:
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            yield _canonical_source_path(os.path.relpath(path, ROOT)), kind, path
    for root in (doc_roots or []):
        root = os.path.abspath(os.path.expanduser(root))
        for path in _local_doc_paths(root):
            yield path, "local", path


def _grounding_records(paths: list[str]) -> dict[str, dict | None]:
    """Resolve exact persisted ARTIFACT bindings for source paths.

    The ARTIFACT CTOR is the content-addressed grounding identity.  Domain
    cells may coexist for semantic structure, but a path-only domain REF can
    never substitute for this full source/answer digest binding.
    """
    result: dict[str, dict | None] = {path: None for path in paths}
    try:
        from app.services.substrate import NodeID
        from app.services.substrate.projection import ctor_field_lookup
        from app.services.substrate.orm import (
            SubstrateNamedCellORM,
            SubstrateNodeORM,
        )
        from app.services.unified_db import session as session_scope

        candidates: dict[str, list[str]] = {}
        flattened: list[str] = []
        for path in paths:
            absolute = os.path.realpath(path)
            values: list[str] = []
            relative = _canonical_source_path(os.path.relpath(absolute, ROOT))
            if not relative.startswith(".."):
                values.extend([relative, "/app/" + relative])
            values.extend([absolute, os.path.abspath(path)])
            values = list(dict.fromkeys(values))
            candidates[path] = values
            flattened.extend(values)

        with session_scope() as session:
            cells: list = []
            for start in range(0, len(flattened), 500):
                cells.extend(
                    session.query(SubstrateNamedCellORM)
                    .filter(SubstrateNamedCellORM.domain == "artifact")
                    .filter(
                        SubstrateNamedCellORM.source_path.in_(
                            flattened[start:start + 500]
                        )
                    )
                    .order_by(SubstrateNamedCellORM.cell_id)
                    .all()
                )
            by_source: dict[str, list] = {}
            for cell in cells:
                by_source.setdefault(cell.source_path, []).append(cell)
            selected: dict[str, object] = {}
            for path, values in candidates.items():
                for value in values:
                    matches = {
                        cell.cell_id: cell for cell in by_source.get(value, [])
                    }
                    if len(matches) > 1:
                        refs = ", ".join(
                            f"@1.1.9.{cell_id}" for cell_id in sorted(matches)
                        )
                        raise RuntimeError(
                            f"ambiguous ARTIFACT grounding for {path}: {refs}"
                        )
                    if matches:
                        selected[path] = next(iter(matches.values()))
                        break
            ctor_ids = {
                cell.ctor_recipe_node_id
                for cell in selected.values()
                if cell.ctor_recipe_node_id is not None
            }
            nodes: list = []
            for start in range(0, len(ctor_ids), 500):
                chunk = sorted(ctor_ids)[start:start + 500]
                nodes.extend(
                    session.query(SubstrateNodeORM)
                    .filter(SubstrateNodeORM.node_id.in_(chunk))
                    .all()
                )
            by_db_id = {node.node_id: node for node in nodes}
            for path, cell in selected.items():
                node = by_db_id.get(cell.ctor_recipe_node_id)
                if node is None:
                    continue
                ctor = NodeID(node.package, node.level, node.type_, node.instance)
                result[path] = {
                    "node_id": f"@1.1.9.{cell.cell_id}",
                    "content_node_id": f"@{ctor}",
                    "persisted_source_sha256": ctor_field_lookup(
                        session, ctor, "content_hash"
                    ),
                    "persisted_answer_sha256": ctor_field_lookup(
                        session, ctor, "answer_hash"
                    ),
                    "persisted_size": ctor_field_lookup(
                        session, ctor, "size_bytes"
                    ),
                }
    except Exception as exc:
        raise RuntimeError(f"substrate grounding resolution failed: {exc}") from exc
    return result


def _grounding_bindings(
    paths: list[str],
) -> dict[str, tuple[str | None, str | None]]:
    records = _grounding_records(paths)
    return {
        path: (
            record.get("node_id") if record else None,
            record.get("content_node_id") if record else None,
        )
        for path, record in records.items()
    }


def _grounding_node_id(path: str) -> str | None:
    return _grounding_bindings([path]).get(path, (None, None))[0]


def _embed_cell(
    source_path: str,
    kind: str,
    path: str,
    *,
    node_id: str | None = None,
    content_node_id: str | None = None,
    grounding_record: dict | None = None,
) -> dict | None:
    try:
        current = read_grounding_source(path)
    except OSError:
        return None
    sn, answer, answer_key = _grounded_excerpt(current.snippet)
    if len(sn) < 20:
        return None
    if grounding_record is None:
        grounding_record = _grounding_records([path]).get(path)
    if grounding_record is not None:
        node_id = node_id or grounding_record.get("node_id")
        content_node_id = content_node_id or grounding_record.get(
            "content_node_id"
        )
    if node_id is None or content_node_id is None or grounding_record is None:
        return None
    try:
        persisted_size = int(grounding_record.get("persisted_size"))
    except (TypeError, ValueError):
        persisted_size = -1
    if (
        grounding_record.get("persisted_source_sha256")
        != current.source_sha256
        or grounding_record.get("persisted_answer_sha256")
        != current.answer_sha256
        or persisted_size != current.source_size
    ):
        raise RuntimeError(
            f"persisted source binding is stale for {source_path}; "
            "run `python3 scripts/coh_substrate.py bootstrap`"
        )
    return {
        "id": node_id,
        "node_id": node_id,
        "content_node_id": content_node_id,
        "source_path": source_path,
        "kind": kind,
        "key": current.source_sha256,
        "persisted_source_sha256": current.source_sha256,
        "schema": INDEX_SCHEMA,
        "embedding_kind": EMBEDDING_KIND,
        "snippet": sn,
        "answer_key": answer_key,
        "answer_hex": answer.hex(),
    }


def _attach_native_embeddings(entries: list[dict]) -> list[dict]:
    """Attach native vectors from the bounded lexical retrieval projection.

    The exact evidence excerpt remains in ``answer_hex`` and is covered by
    ``answer_key``; the complete source is independently bound by the persisted
    source digest and ARTIFACT CTOR. The vector uses that same 600-byte UTF-8
    excerpt, keeping native discovery and answer materialization bounded
    independently of source-file size and Unicode byte width.
    """
    vectors = _native_embed_batch(
        [
            (
                str(entry["source_path"]),
                _bounded_native_embed_text(str(entry["snippet"])),
            )
            for entry in entries
        ]
    )
    for entry in entries:
        entry["vec"] = vectors[str(entry["source_path"])]
    return entries


def _deployment_witness_entries() -> list[dict]:
    """Materialize the latest persisted deployment WITNESS into typed RAG."""
    api_root = os.path.join(ROOT, "api")
    if api_root not in sys.path:
        sys.path.insert(0, api_root)
    try:
        from app.services.deployment_observation import latest_deployment_observation
        from app.services.unified_db import session as session_scope

        with session_scope() as session:
            witness = latest_deployment_observation(session, allow_expired=True)
    except Exception as exc:
        raise RuntimeError(f"deployment WITNESS resolution failed: {exc}") from exc
    if witness is None:
        return []
    answer = str(witness["answer"])
    snippet = (
        "Observed deployment WITNESS proof. "
        f"release {witness['actual_sha']} passed {witness['health_route']} "
        f"with result {witness['health_result']} on kernel runtime "
        f"{witness['kernel_runtime']}; dual-vantage evidence "
        f"{witness['evidence_key']}; "
        f"observed {witness['observed_at']} expires {witness['expires_at']}."
    )
    return [
        {
            "id": witness["node_id"],
            "node_id": witness["node_id"],
            "content_node_id": witness["content_node_id"],
            "source_path": witness["source_path"],
            "kind": "deployment-witness",
            "key": witness["source_key"],
            "persisted_source_sha256": witness["source_key"],
            "schema": INDEX_SCHEMA,
            "embedding_kind": EMBEDDING_KIND,
            "snippet": snippet[:600],
            "answer_key": witness["answer_key"],
            "answer_hex": answer.encode("utf-8").hex(),
        }
    ]


def _load_index(index_path: str) -> list[dict]:
    if not os.path.exists(index_path):
        return []
    with open(index_path, encoding="utf-8") as index_in:
        return [json.loads(line) for line in index_in if line.strip()]


def _index_stamp_path(index_path: str) -> str:
    return index_path + ".stamp.json"


def _native_source_stamp() -> str:
    """Bind the cache to the committed native table/stamp inputs."""
    digest = hashlib.sha256(b"native-rag-carrier-v1\n")
    for relative in (
        "form/form-stdlib/bootstrap/form-cli.source.sha256",
        "form/form-stdlib/bootstrap/form-cli.stamp",
        "form/form-stdlib/bootstrap/form-cli-table.txt",
    ):
        path = Path(ROOT) / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _write_json_atomic(path: str, payload: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    fd, temporary_path = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary_path, path)
        temporary_path = ""
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _index_stamp_valid(index_path: str) -> bool:
    stamp_path = _index_stamp_path(index_path)
    try:
        raw = Path(index_path).read_bytes()
        stamp = json.loads(Path(stamp_path).read_text(encoding="utf-8"))
        rows = _load_index(index_path)
        return (
            set(stamp)
            == {
                "carrier_source_sha256",
                "embedding_kind",
                "index_schema",
                "index_sha256",
                "row_count",
                "schema",
            }
            and stamp["schema"] == INDEX_STAMP_SCHEMA
            and stamp["index_schema"] == INDEX_SCHEMA
            and stamp["embedding_kind"] == EMBEDDING_KIND
            and stamp["carrier_source_sha256"] == _native_source_stamp()
            and stamp["index_sha256"] == hashlib.sha256(raw).hexdigest()
            and stamp["row_count"] == len(rows)
            and all(
                row.get("schema") == INDEX_SCHEMA
                and row.get("embedding_kind") == EMBEDDING_KIND
                and isinstance(row.get("vec"), list)
                for row in rows
            )
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _index_files_current(index_path: str) -> bool:
    """Cheaply detect source drift before a native ask.

    This does not replace query-time CTOR verification.  It prevents a valid
    old stamp from repeatedly selecting an edited source and triggers the full
    bootstrap/heal reconciliation before the first retry.
    """
    if not _index_stamp_valid(index_path):
        return False
    try:
        rows = _load_index(index_path)
        by_source = {str(row.get("source_path") or ""): row for row in rows}
        if len(by_source) != len(rows):
            return False
        expected_sources: set[str] = set()
        for source, _kind, path in _body_cells():
            expected_sources.add(source)
            row = by_source.get(source)
            if row is None:
                return False
            current = read_grounding_source(path)
            excerpt, answer, answer_key = _grounded_excerpt(current.snippet)
            if (
                row.get("key") != current.source_sha256
                or row.get("persisted_source_sha256")
                != current.source_sha256
                or row.get("answer_key") != answer_key
                or row.get("answer_hex") != answer.hex()
                or row.get("snippet") != excerpt
            ):
                return False
        dynamic = {
            row["source_path"]: row for row in _deployment_witness_entries()
        }
        expected_sources.update(dynamic)
        for source, expected in dynamic.items():
            row = by_source.get(source)
            if row is None or any(
                row.get(key) != value for key, value in expected.items()
            ):
                return False
        for source, row in by_source.items():
            if source in expected_sources:
                continue
            if row.get("kind") != "local" or not os.path.isfile(source):
                return False
            current = read_grounding_source(source)
            _excerpt, _answer, answer_key = _grounded_excerpt(current.snippet)
            if (
                row.get("key") != current.source_sha256
                or row.get("answer_key") != answer_key
            ):
                return False
        return True
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _write_index(index_path: str, entries: list[dict]) -> None:
    directory = os.path.dirname(os.path.abspath(index_path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(index_path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            for entry in sorted(
                entries, key=lambda item: item.get("source_path", "")
            ):
                out.write(json.dumps(entry, separators=(",", ":")) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary_path, index_path)
        temporary_path = ""
        raw = Path(index_path).read_bytes()
        _write_json_atomic(
            _index_stamp_path(index_path),
            {
                "carrier_source_sha256": _native_source_stamp(),
                "embedding_kind": EMBEDDING_KIND,
                "index_schema": INDEX_SCHEMA,
                "index_sha256": hashlib.sha256(raw).hexdigest(),
                "row_count": len(entries),
                "schema": INDEX_STAMP_SCHEMA,
            },
        )
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def freshness(index_path: str, doc_roots=None):
    """Mirror of rag-freshness.fk over the live body: returns (heal_cells, orphan_ids).
    heal_cells = body cells missing from the index or whose key drifted.
    orphan_ids = index ids whose source is gone."""
    body = list(_body_cells(doc_roots))
    dynamic = {
        entry["source_path"]: entry for entry in _deployment_witness_entries()
    }
    current_by_path = {
        path: read_grounding_source(path) for _source, _kind, path in body
    }
    body_keys = {
        source: current_by_path[path].source_sha256
        for source, _kind, path in body
    }
    body_keys.update({source: entry["key"] for source, entry in dynamic.items()})
    records = _grounding_records([path for _source, _kind, path in body])
    index = _load_index(index_path)
    by_source = {entry.get("source_path", ""): entry for entry in index}
    rebuild_all = bool(index) and not _index_stamp_valid(index_path)

    heal = []
    for source, kind, path in body:
        entry = by_source.get(source)
        current = current_by_path[path]
        excerpt, answer, answer_key = _grounded_excerpt(current.snippet)
        record = records.get(path)
        if (
            rebuild_all
            or entry is None
            or record is None
            or entry.get("key", "") != body_keys[source]
            or entry.get("persisted_source_sha256")
            != current.source_sha256
            or entry.get("schema") != INDEX_SCHEMA
            or entry.get("embedding_kind") != EMBEDDING_KIND
            or not str(entry.get("node_id", "")).startswith("@")
            or entry.get("id") != entry.get("node_id")
            or entry.get("node_id") != record.get("node_id")
            or entry.get("content_node_id") != record.get("content_node_id")
            or record.get("persisted_source_sha256")
            != current.source_sha256
            or record.get("persisted_answer_sha256")
            != current.answer_sha256
            or int(record.get("persisted_size") or -1) != current.source_size
            or entry.get("snippet") != excerpt
            or entry.get("answer_key") != answer_key
            or entry.get("answer_hex") != answer.hex()
            or not isinstance(entry.get("vec"), list)
        ):
            heal.append((source, kind, path))

    for source, expected in dynamic.items():
        existing = by_source.get(source)
        if (
            rebuild_all
            or existing is None
            or any(
                existing.get(key) != value
                for key, value in expected.items()
                if key != "vec"
            )
            or not isinstance(existing.get("vec"), list)
        ):
            heal.append((source, "deployment-witness", ""))

    orphans = []
    for entry in index:
        source = entry.get("source_path", "")
        kind = entry.get("kind", "")
        if source in body_keys:
            continue
        if kind == "local":
            if not os.path.exists(source):
                orphans.append(source)
        else:                               # a body source that was removed/renamed
            orphans.append(source)
    return heal, orphans


def heal(index_path: str, doc_roots=None, verbose=True) -> tuple[int, int]:
    """Self-heal the cache, git-like: embed only the drifted/missing delta, compost
    orphans, keep everything fresh untouched. A full embed runs only when absent."""
    heal_cells, orphan_ids = freshness(index_path, doc_roots)
    if not heal_cells and not orphan_ids:
        return 0, 0
    index = _load_index(index_path)
    by_source = {
        entry.get("source_path", ""): entry
        for entry in index
        if entry.get("source_path", "") not in orphan_ids
    }
    healed = 0
    ungrounded: list[str] = []
    records = _grounding_records(
        [path for _source, kind, path in heal_cells if kind != "deployment-witness"]
    )
    dynamic = {
        entry["source_path"]: entry for entry in _deployment_witness_entries()
    }
    pending: list[dict] = []
    for source, kind, path in heal_cells:
        if kind == "deployment-witness":
            entry = dynamic.get(source)
            if entry is not None:
                pending.append(entry)
            else:
                ungrounded.append(source)
                by_source.pop(source, None)
            continue
        record = records.get(path)
        entry = _embed_cell(
            source,
            kind,
            path,
            grounding_record=record,
        )
        if entry is not None:
            pending.append(entry)
        else:
            ungrounded.append(source)
            by_source.pop(source, None)
    if ungrounded:
        preview = ", ".join(ungrounded[:5])
        raise RuntimeError(
            f"{len(ungrounded)} RAG sources have no current persisted ARTIFACT "
            f"binding; run `python3 scripts/coh_substrate.py bootstrap` ({preview})"
        )
    _attach_native_embeddings(pending)
    for entry in pending:
        by_source[str(entry["source_path"])] = entry
        healed += 1
        if verbose and healed % 100 == 0:
            print(f"  ...{healed} cells healed", flush=True)
    _write_index(index_path, list(by_source.values()))
    if verbose:
        print(f"[rag heal: +{healed} re-embedded, -{len(orphan_ids)} composted -> {index_path}]")
    return healed, len(orphan_ids)


def build(index_path: str, doc_roots=None) -> None:
    """Full embed over the whole body — used when the index is absent or being reset.
    The steady-state path is heal(); this is the cold start."""
    entries = []
    n = 0
    ungrounded: list[str] = []
    body = list(_body_cells(doc_roots))
    records = _grounding_records([path for _source, _kind, path in body])
    for source, kind, path in body:
        entry = _embed_cell(
            source,
            kind,
            path,
            grounding_record=records.get(path),
        )
        if entry is not None:
            entries.append(entry)
            n += 1
            if n % 100 == 0:
                print(f"  ...{n} cells embedded", flush=True)
        else:
            ungrounded.append(source)
    entries.extend(_deployment_witness_entries())
    if ungrounded:
        preview = ", ".join(ungrounded[:5])
        raise RuntimeError(
            f"{len(ungrounded)} RAG sources have no substrate CTOR NodeID; "
            f"run `python3 scripts/coh_substrate.py bootstrap` first ({preview})"
        )
    _attach_native_embeddings(entries)
    _write_index(index_path, entries)
    print(f"[rag index built: {n} cells -> {index_path}]")


def _ensure_fresh(index_path: str, doc_roots=None) -> None:
    """Lazy heal before serving: if the index is absent, cold-build; otherwise heal the
    delta. Cheap when fresh (hash the body, find nothing to do)."""
    if not os.path.exists(index_path):
        build(index_path, doc_roots)
    else:
        heal(index_path, doc_roots, verbose=False)


def verify_grounding(node_id: str, index_path: str) -> tuple[bool, dict]:
    """Verify a selected RAG hit against current source bytes and substrate.

    This is the retiring query-time resolver carrier. It observes facts only;
    the Form gate receives the exact bound receipt and owns the trust verdict.
    """
    matches = [
        entry for entry in _load_index(index_path)
        if entry.get("node_id") == node_id and entry.get("id") == node_id
    ]
    result = {
        "node_id": node_id,
        "verified": False,
        "reason": "",
        "source_path": None,
        "content_node_id": None,
        "source_key": None,
        "answer_key": None,
        "persisted_source_sha256": None,
    }
    if not _index_stamp_valid(index_path):
        result["reason"] = "index-stamp"
        return False, result
    if len(matches) != 1:
        result["reason"] = "index-row-count"
        return False, result

    entry = matches[0]
    source = str(entry.get("source_path", ""))
    result["source_path"] = source
    result["content_node_id"] = entry.get("content_node_id")
    result["source_key"] = entry.get("key")
    result["answer_key"] = entry.get("answer_key")
    result["persisted_source_sha256"] = entry.get(
        "persisted_source_sha256"
    )
    if entry.get("kind") == "deployment-witness":
        expected = next(
            (
                row
                for row in _deployment_witness_entries()
                if row.get("node_id") == node_id
            ),
            None,
        )
        if expected is None or any(
            entry.get(key) != value for key, value in expected.items()
        ):
            result["reason"] = "witness-index-drift"
            return False, result
        api_root = os.path.join(ROOT, "api")
        if api_root not in sys.path:
            sys.path.insert(0, api_root)
        try:
            from app.services.deployment_observation import (
                verify_deployment_observation,
            )
            from app.services.unified_db import session as session_scope

            with session_scope() as session:
                witness = verify_deployment_observation(
                    session,
                    node_id,
                    expected_answer_key=str(entry["answer_key"]),
                    allow_expired=True,
                )
        except Exception as exc:
            result["reason"] = f"witness:{exc}"
            return False, result
        if (
            witness["content_node_id"] != entry.get("content_node_id")
            or witness["source_key"] != entry.get("key")
            or witness["source_path"] != source
            or witness["answer"].encode("utf-8").hex()
            != entry.get("answer_hex")
        ):
            result["reason"] = "witness-binding"
            return False, result
        result["verified"] = True
        result["reason"] = "resolved-current-witness-binding"
        return True, result

    path = source if os.path.isabs(source) else os.path.join(ROOT, source)
    if not os.path.isfile(path):
        result["reason"] = "source-missing"
        return False, result

    try:
        current = read_grounding_source(path)
    except OSError:
        result["reason"] = "source-read"
        return False, result
    binding = _grounding_records([path]).get(path)
    if binding is None:
        result["reason"] = "artifact-binding"
        return False, result
    try:
        persisted_size = int(binding.get("persisted_size"))
    except (TypeError, ValueError):
        persisted_size = -1
    result["persisted_source_sha256"] = binding.get(
        "persisted_source_sha256"
    )
    excerpt, answer, answer_key = _grounded_excerpt(current.snippet)
    checks = (
        (entry.get("schema") == INDEX_SCHEMA, "schema"),
        (entry.get("embedding_kind") == EMBEDDING_KIND, "embedding-kind"),
        (entry.get("key") == current.source_sha256, "content-key"),
        (
            entry.get("persisted_source_sha256") == current.source_sha256,
            "index-persisted-source",
        ),
        (binding.get("node_id") == node_id, "artifact-ref"),
        (
            binding.get("content_node_id") == entry.get("content_node_id"),
            "artifact-ctor",
        ),
        (
            binding.get("persisted_source_sha256")
            == current.source_sha256,
            "persisted-source-sha256",
        ),
        (
            binding.get("persisted_answer_sha256")
            == current.answer_sha256,
            "persisted-answer-sha256",
        ),
        (persisted_size == current.source_size, "persisted-source-size"),
        (entry.get("snippet") == excerpt, "snippet"),
        (entry.get("answer_hex") == answer.hex(), "answer-hex"),
        (entry.get("answer_key") == answer_key, "answer-key"),
        (isinstance(entry.get("vec"), list), "embedding"),
    )
    for passed, reason in checks:
        if not passed:
            result["reason"] = reason
            return False, result
    result["verified"] = True
    result["reason"] = "resolved-current-binding"
    return True, result


def verify_frequency_certificate(
    node_id: str, index_path: str
) -> tuple[bool, dict]:
    """Return a bound certificate only for a fresh persisted WITNESS answer."""
    matches = [
        entry
        for entry in _load_index(index_path)
        if entry.get("node_id") == node_id
        and entry.get("id") == node_id
        and entry.get("kind") == "deployment-witness"
    ]
    result = {
        "node_id": node_id,
        "verified": False,
        "reason": "index-row-count",
        "certificate_node_id": None,
        "certificate_subject_content_node_id": None,
        "certificate_answer_key": None,
        "certificate_evidence_key": None,
        "certificate_issued_epoch": None,
        "certificate_expires_epoch": None,
        "certificate_result": None,
        "certificate_receipt_key": None,
    }
    if len(matches) != 1:
        return False, result
    entry = matches[0]
    grounded, grounding = verify_grounding(node_id, index_path)
    if not grounded:
        result["reason"] = grounding["reason"]
        return False, result
    api_root = os.path.join(ROOT, "api")
    if api_root not in sys.path:
        sys.path.insert(0, api_root)
    try:
        from app.services.deployment_observation import (
            verify_deployment_observation,
        )
        from app.services.unified_db import session as session_scope

        with session_scope() as session:
            witness = verify_deployment_observation(
                session,
                node_id,
                expected_answer_key=str(entry["answer_key"]),
            )
    except Exception as exc:
        result["reason"] = str(exc)
        return False, result
    result.update(
        {
            "verified": True,
            "reason": "fresh-content-bound-deployment-witness",
            "certificate_node_id": witness["certificate_node_id"],
            "certificate_subject_content_node_id": witness[
                "certificate_subject_content_node_id"
            ],
            "certificate_answer_key": witness["answer_key"],
            "certificate_evidence_key": witness["source_key"],
            "certificate_issued_epoch": int(time.time()),
            "certificate_expires_epoch": witness[
                "certificate_expires_epoch"
            ],
            "certificate_result": witness["certificate_result"],
            "certificate_receipt_key": witness["certificate_receipt_key"],
        }
    )
    return True, result


def _attestation_key_path() -> Path:
    return Path.home() / ".coherence-network" / "attestation" / "grounding-v1.key"


def _attestation_key() -> bytes:
    """Load or atomically create the host-local 256-bit attestation key."""
    path = _attestation_key_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory_metadata = path.parent.lstat()
    if path.parent.is_symlink() or not stat.S_ISDIR(directory_metadata.st_mode):
        raise RuntimeError("attestation directory is insecure")
    if os.name != "nt":
        try:
            os.chmod(path.parent, 0o700)
        except OSError as exc:
            raise RuntimeError("cannot secure attestation directory") from exc
        directory_metadata = path.parent.lstat()
        if (
            directory_metadata.st_uid != os.getuid()
            or stat.S_IMODE(directory_metadata.st_mode) != 0o700
        ):
            raise RuntimeError("attestation directory permissions/ownership invalid")
    if not path.exists():
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}")
        fd = -1
        try:
            fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            payload = secrets.token_hex(32).encode("ascii") + b"\n"
            os.write(fd, payload)
            os.fsync(fd)
            os.close(fd)
            fd = -1
            os.link(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except FileExistsError:
            pass
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("attestation key is not a regular file")
    if os.name == "nt":
        identity = getpass.getuser()
        acl = subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{identity}:(R,W)",
            ],
            capture_output=True,
            check=False,
        )
        if acl.returncode != 0:
            raise RuntimeError("attestation key Windows ACL hardening failed")
    elif (
        metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise RuntimeError("attestation key permissions/ownership invalid")
    try:
        encoded = path.read_text(encoding="ascii").strip()
        key = bytes.fromhex(encoded)
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("attestation key is malformed") from exc
    if len(key) != 32 or encoded != encoded.lower():
        raise RuntimeError("attestation key is not canonical 256-bit hex")
    return key


def _hmac_sha256(key: bytes, fields: list[str]) -> str:
    return hmac.new(key, "\n".join(fields).encode("utf-8"), hashlib.sha256).hexdigest()


def native_trace_receipt(
    node_id: str, index_path: str, query_file: str, request_id: str
) -> tuple[bool, str]:
    """Build the no-boolean, TOCTOU-bound argument consumed by native Form."""
    if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id) is None:
        return (
            False,
            "none|none|none|none|none|none|none|0|0|none|"
            "none|none|none|none|0|0|none|none",
        )
    try:
        with open(query_file, "rb") as query_in:
            query_key = hashlib.sha256(query_in.read()).hexdigest()
    except OSError:
        return (
            False,
            "none|none|none|none|none|none|none|0|0|none|"
            "none|none|none|none|0|0|none|none",
        )
    empty = (
        "none|none|none|none|none|none|"
        f"{query_key}|0|0|none|none|none|none|none|0|0|none|none"
    )
    grounded, receipt = verify_grounding(node_id, index_path)
    if not grounded:
        return False, empty
    persisted_source = str(receipt.get("persisted_source_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", persisted_source):
        return False, empty
    issued = int(time.time())
    expires = issued + ATTESTATION_LIFETIME_SECONDS
    key = _attestation_key()
    fields = [
        str(receipt["node_id"]),
        str(receipt["content_node_id"]),
        str(receipt["source_key"]),
        str(receipt["source_path"]),
        str(receipt["answer_key"]),
        persisted_source,
        query_key,
        str(issued),
        str(expires),
    ]
    fields.append(
        _hmac_sha256(
            key,
            ["grounding-attestation-v2", request_id, *fields],
        )
    )
    certified, certificate = verify_frequency_certificate(node_id, index_path)
    if certified:
        cert_issued = int(time.time())
        cert_expires = min(
            cert_issued + ATTESTATION_LIFETIME_SECONDS,
            int(certificate["certificate_expires_epoch"]),
        )
        cert_fields = [
            str(certificate["certificate_node_id"]),
            str(certificate["certificate_subject_content_node_id"]),
            str(certificate["certificate_answer_key"]),
            str(certificate["certificate_evidence_key"]),
            str(cert_issued),
            str(cert_expires),
            str(certificate["certificate_result"]),
        ]
        fields.extend(
            [
                *cert_fields,
                _hmac_sha256(
                    key,
                    ["frequency-attestation-v2", request_id, *cert_fields],
                ),
            ]
        )
    else:
        fields.extend(["none", "none", "none", "none", "0", "0", "none", "none"])
    rendered = [str(field) for field in fields]
    if len(rendered) != 18 or any(
        not field or "|" in field or "\n" in field or "\r" in field
        for field in rendered
    ):
        return False, empty
    return True, "|".join(rendered)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--index", default=INDEX)
    b.add_argument("--docs", action="append", default=[], help="extra local folder(s) to index, repeatable")
    h = sub.add_parser("heal")
    h.add_argument("--index", default=INDEX)
    h.add_argument("--docs", action="append", default=[])
    f = sub.add_parser("fresh")
    f.add_argument("--index", default=INDEX)
    v = sub.add_parser("verify-grounding")
    v.add_argument("node_id")
    v.add_argument("--index", default=INDEX)
    fc = sub.add_parser("verify-frequency-certificate")
    fc.add_argument("node_id")
    fc.add_argument("--index", default=INDEX)
    tr = sub.add_parser("trace-receipt")
    tr.add_argument("node_id")
    tr.add_argument("--index", default=INDEX)
    tr.add_argument("--query-file", required=True)
    tr.add_argument("--request-id", required=True)
    vi = sub.add_parser("validate-index")
    vi.add_argument("--index", default=INDEX)
    vc = sub.add_parser("validate-current")
    vc.add_argument("--index", default=INDEX)
    args = ap.parse_args()

    if args.cmd == "build":
        build(args.index, args.docs)
        return 0
    if args.cmd == "heal":
        heal(args.index, args.docs)
        return 0
    if args.cmd == "fresh":
        heal_cells, orphans = freshness(args.index)
        total = len(_load_index(args.index))
        if not heal_cells and not orphans:
            print(f"[rag fresh: {total} cells, cache == body]")
        else:
            print(f"[rag drift: {len(heal_cells)} to heal, {len(orphans)} orphaned, {total} cached]")
            for cid, kind, _p in heal_cells[:20]:
                print(f"  ~ {cid} ({kind})")
        return 0 if not heal_cells and not orphans else 1
    if args.cmd == "verify-grounding":
        verified, result = verify_grounding(args.node_id, args.index)
        print(json.dumps(result, separators=(",", ":")))
        return 0 if verified else 1
    if args.cmd == "verify-frequency-certificate":
        verified, result = verify_frequency_certificate(args.node_id, args.index)
        print(json.dumps(result, separators=(",", ":")))
        return 0 if verified else 1
    if args.cmd == "trace-receipt":
        verified, receipt = native_trace_receipt(
            args.node_id, args.index, args.query_file, args.request_id
        )
        print(receipt)
        return 0 if verified else 1
    if args.cmd == "validate-index":
        return 0 if _index_stamp_valid(args.index) else 1
    if args.cmd == "validate-current":
        return 0 if _index_files_current(args.index) else 1
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"form-cli rag: {exc}", file=sys.stderr)
        sys.exit(1)
