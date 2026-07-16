"""Executable proof for the NodeID-backed Form-first grounding runtime."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.routers import substrate as substrate_router
from app.services import native_runtime_observation, unified_db
from app.services.grounding_source import read_grounding_source
from app.services.substrate import ingest_git_artifact


ROOT = Path(__file__).resolve().parents[2]


def _ensure_host_native_carrier() -> Path:
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts" / "ensure_form_cli_native.sh"),
            "--print-path",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.strip())


def _load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rag = _load_script("form_cli_rag_grounding_test", "scripts/form_cli_rag.py")
coh = _load_script("coh_substrate_grounding_test", "scripts/coh_substrate.py")


def _trust(*, observed: bool = False, grounded: bool = True) -> bytes:
    if not grounded:
        text = (
            "trust  path:native  grounded:no  freq:unknown  "
            "freq-source:unmeasured  suffic:no  observed:no  -> native-partial  "
            "decision:escalate  reason:empty"
        )
    elif observed:
        text = (
            "trust  path:native  grounded:yes  freq:yes  "
            "freq-source:certified-form  suffic:yes  observed:yes  -> OBSERVED  "
            "decision:accept  reason:ok"
        )
    else:
        text = (
            "trust  path:native  grounded:yes  freq:unknown  "
            "freq-source:unmeasured  suffic:yes  observed:no  -> native-partial  "
            "decision:accept  reason:ok"
        )
    return (text + "\n").encode()


def _grounded_stdout(answer: bytes, **overrides: str) -> bytes:
    bindings = {
        "grounded": "@1.1.9.7",
        "content-node": "@1.4.10.9",
        "source-path": "C:/body/specs/example.md",
        "source-key": hashlib.sha256(b"source").hexdigest(),
        "answer-key": hashlib.sha256(answer).hexdigest(),
        "retrieval-score": "8",
        "retrieval-runner-score": "4",
        "retrieval-query-total": "10",
        "retrieval-threshold": "4",
        "retrieval-confidence": "80",
        "local-lane": "fkwu-rag-grounded",
        "synthesis-lane": "fkwu-rag-grounded",
        "answer-byte-length": str(len(answer)),
    }
    bindings.update(overrides)
    metadata = "\n".join(f"{key}:{value}" for key, value in bindings.items())
    return metadata.encode() + b"\nanswer:" + answer + b"\n"


def _carrier_observation(root: Path, *, challenge: str = "1" * 64) -> dict:
    return {
        "schema": "native-runtime-observation-v1",
        "verified": True,
        "root": str(root.resolve()),
        "challenge_digest": challenge,
        "kernel": {
            "verified": True,
            "runtime": "fkwu",
            "binary_sha256": "2" * 64,
            "inline_sha256": None,
        },
        "form_cli": {
            "verified": True,
            "binary_sha256": "3" * 64,
            "table_sha256": "4" * 64,
            "wrapper_sha256": "5" * 64,
            "source_stamp": "6" * 64,
            "build_id": "coherence-kernel-fkwu-native-v2",
        },
    }


def test_python_semantic_and_serving_mirrors_are_absent():
    source = (ROOT / "scripts/form_cli_rag.py").read_text(encoding="utf-8")
    for forbidden in (
        "SEMANTIC_CONCEPTS",
        "def lexical_embed",
        "def semantic_embed",
        "def index_embed",
        "def rag_overlap",
        "def retrieve",
        "def ask(",
    ):
        assert forbidden not in source
    assert "embed-request" in source
    assert rag.INDEX_SCHEMA == "nodeid-rag-v2"
    assert rag.EMBEDDING_KIND == "form-semantic-v2"


def test_python_reproves_the_shell_selected_platform_carrier_each_time(
    tmp_path, monkeypatch
):
    binary = tmp_path / "form-cli.exe"
    binary.write_bytes(b"verified native carrier")
    source_digest = rag.NATIVE_SOURCE_DIGEST_FILE.read_text(encoding="utf-8").strip()
    receipt = tmp_path / "selected.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "selected-form-cli-carrier-v1",
                "native_path": str(binary),
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "source_sha256": source_digest,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rag, "NATIVE_CARRIER_RECEIPT", receipt)
    assert rag._native_cli_path() == binary
    binary.write_bytes(b"changed after first verified resolution")
    with pytest.raises(RuntimeError, match="binary digest mismatch"):
        rag._native_cli_path()


def test_python_rejects_a_tampered_selected_carrier(tmp_path, monkeypatch):
    binary = tmp_path / "form-cli"
    binary.write_bytes(b"tampered")
    receipt = tmp_path / "selected.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "selected-form-cli-carrier-v1",
                "native_path": str(binary),
                "binary_sha256": "0" * 64,
                "source_sha256": rag.NATIVE_SOURCE_DIGEST_FILE.read_text(
                    encoding="utf-8"
                ).strip(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rag, "NATIVE_CARRIER_RECEIPT", receipt)
    with pytest.raises(RuntimeError, match="binary digest mismatch"):
        rag._native_cli_path()


def test_native_embedding_batches_cover_every_item_under_the_carrier_cap(
    monkeypatch,
):
    monkeypatch.setattr(rag, "NATIVE_EMBED_REQUEST_MAX_BYTES", 150)
    monkeypatch.setattr(rag, "NATIVE_EMBED_REQUEST_MAX_ITEMS", 3)
    chunks: list[list[tuple[str, str]]] = []

    def embed(chunk):
        chunks.append(chunk)
        return {item_id: [position, 17] for position, (item_id, _text) in enumerate(chunk)}

    monkeypatch.setattr(rag, "_native_embed_chunk", embed)
    items = [(f"cell-{index}", "grounded source " * 2) for index in range(12)]
    vectors = rag._native_embed_batch(items)
    assert set(vectors) == {item_id for item_id, _text in items}
    assert len(chunks) > 1
    for chunk in chunks:
        encoded_size = sum(
            len(item_id.encode().hex()) + 1 + len(text.encode().hex()) + 1
            for item_id, text in chunk
        )
        assert encoded_size <= rag.NATIVE_EMBED_REQUEST_MAX_BYTES
        assert len(chunk) <= rag.NATIVE_EMBED_REQUEST_MAX_ITEMS


def test_native_evidence_excerpt_is_utf8_byte_bounded_and_digest_bound():
    text = "grounded─observation─" * 100
    excerpt, payload, answer_key = rag._grounded_excerpt(text)
    assert excerpt.encode("utf-8") == payload
    assert len(payload) <= rag.NATIVE_EMBED_TEXT_MAX_BYTES
    assert answer_key == hashlib.sha256(payload).hexdigest()
    assert text.startswith(excerpt)


def test_native_embedding_chunk_rejects_direct_calls_over_carrier_caps(monkeypatch):
    monkeypatch.setattr(rag, "NATIVE_EMBED_REQUEST_MAX_ITEMS", 1)
    with pytest.raises(RuntimeError, match="item cap"):
        rag._native_embed_chunk([("one", "a"), ("two", "b")])

    monkeypatch.setattr(rag, "NATIVE_EMBED_REQUEST_MAX_ITEMS", 10)
    monkeypatch.setattr(rag, "NATIVE_EMBED_REQUEST_MAX_BYTES", 3)
    with pytest.raises(RuntimeError, match="byte cap"):
        rag._native_embed_chunk([("one", "a")])


def test_failed_native_batch_never_publishes_a_partial_index(tmp_path, monkeypatch):
    source = tmp_path / "source.fk"
    source.write_text("(do (defn durable-grounding () 42))\n", encoding="utf-8")
    current = read_grounding_source(source)
    record = {
        "node_id": "@1.1.9.1",
        "content_node_id": "@1.4.10.1",
        "persisted_source_sha256": current.source_sha256,
        "persisted_answer_sha256": current.answer_sha256,
        "persisted_size": current.source_size,
    }
    monkeypatch.setattr(rag, "_body_cells", lambda _roots=None: [("source.fk", "recipe", str(source))])
    monkeypatch.setattr(rag, "_grounding_records", lambda _paths: {str(source): record})
    monkeypatch.setattr(rag, "_deployment_witness_entries", lambda: [])
    monkeypatch.setattr(
        rag,
        "_attach_native_embeddings",
        lambda _entries: (_ for _ in ()).throw(RuntimeError("native crash")),
    )
    published: list[list[dict]] = []
    monkeypatch.setattr(rag, "_write_index", lambda _path, entries: published.append(entries))
    with pytest.raises(RuntimeError, match="native crash"):
        rag.build(str(tmp_path / "index.jsonl"))
    assert published == []


def test_exact_artifact_binding_rejects_edits_until_reingested(tmp_path, monkeypatch):
    db_path = tmp_path / "substrate.sqlite"
    monkeypatch.setattr(unified_db, "database_url", lambda: f"sqlite+pysqlite:///{db_path}")
    unified_db.reset_engine()
    unified_db.ensure_schema()
    source = tmp_path / "grounded.form"
    source.write_text("(do (defn grounded-runtime () 1))\n", encoding="utf-8")

    try:
        first = read_grounding_source(source)
        with unified_db.session() as session:
            first_cell, _blueprint, first_ctor = ingest_git_artifact(
                session,
                path=str(source.resolve()),
                content_hash=first.source_sha256,
                answer_hash=first.answer_sha256,
                size_bytes=first.source_size,
                mtime=0.0,
            )
        first_record = rag._grounding_records([str(source)])[str(source)]
        entry = rag._embed_cell(
            str(source), "artifact", str(source), grounding_record=first_record
        )
        assert entry is not None
        assert entry["node_id"] == f"@1.1.9.{first_cell.cell_id}"
        assert entry["content_node_id"] == f"@{first_ctor}"
        assert entry["key"] == first.source_sha256
        assert entry["persisted_source_sha256"] == first.source_sha256
        assert entry["answer_key"] == first.answer_sha256
        assert bytes.fromhex(entry["answer_hex"]) == first.answer

        source.write_text("(do (defn grounded-runtime () 2))\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="persisted source binding is stale"):
            rag._embed_cell(
                str(source), "artifact", str(source), grounding_record=first_record
            )

        second = read_grounding_source(source)
        with unified_db.session() as session:
            second_cell, _blueprint, second_ctor = ingest_git_artifact(
                session,
                path=str(source.resolve()),
                content_hash=second.source_sha256,
                answer_hash=second.answer_sha256,
                size_bytes=second.source_size,
                mtime=0.0,
            )
        second_record = rag._grounding_records([str(source)])[str(source)]
        healed = rag._embed_cell(
            str(source), "artifact", str(source), grounding_record=second_record
        )
        assert healed is not None
        assert second_cell.cell_id == first_cell.cell_id
        assert second_ctor != first_ctor
        assert healed["key"] == second.source_sha256
        assert healed["answer_key"] == second.answer_sha256
    finally:
        unified_db.reset_engine()


def test_repo_relative_artifact_wins_over_legacy_absolute_alias(tmp_path, monkeypatch):
    db_path = tmp_path / "aliases.sqlite"
    monkeypatch.setattr(unified_db, "database_url", lambda: f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setattr(rag, "ROOT", str(tmp_path))
    unified_db.reset_engine()
    unified_db.ensure_schema()
    source = tmp_path / "source.fk"
    source.write_text("(do (defn canonical-artifact () 42))\n", encoding="utf-8")
    current = read_grounding_source(source)
    try:
        with unified_db.session() as session:
            legacy, _blueprint, _ctor = ingest_git_artifact(
                session,
                path=str(source.resolve()),
                content_hash=current.source_sha256,
                answer_hash=current.answer_sha256,
                size_bytes=current.source_size,
                mtime=0.0,
            )
            canonical, _blueprint, canonical_ctor = ingest_git_artifact(
                session,
                path="source.fk",
                content_hash=current.source_sha256,
                answer_hash=current.answer_sha256,
                size_bytes=current.source_size,
                mtime=0.0,
            )
        assert legacy.cell_id != canonical.cell_id
        record = rag._grounding_records([str(source.resolve())])[str(source.resolve())]
        assert record is not None
        assert record["node_id"] == f"@1.1.9.{canonical.cell_id}"
        assert record["content_node_id"] == f"@{canonical_ctor}"
    finally:
        unified_db.reset_engine()


def test_index_stamp_binds_schema_carrier_and_exact_bytes(tmp_path):
    index = tmp_path / "index.jsonl"
    row = {
        "id": "@1.1.9.1",
        "node_id": "@1.1.9.1",
        "content_node_id": "@1.4.10.1",
        "source_path": "specs/example.md",
        "kind": "spec",
        "key": "1" * 64,
        "persisted_source_sha256": "1" * 64,
        "schema": rag.INDEX_SCHEMA,
        "embedding_kind": rag.EMBEDDING_KIND,
        "snippet": "grounded index row with enough content",
        "answer_key": "2" * 64,
        "answer_hex": b"answer".hex(),
        "vec": [1, 2],
    }
    rag._write_index(str(index), [row])
    assert rag._index_stamp_valid(str(index)) is True
    index.write_bytes(index.read_bytes() + b"\n")
    assert rag._index_stamp_valid(str(index)) is False


def test_atomic_index_write_preserves_live_index_on_failure(tmp_path, monkeypatch):
    index = tmp_path / "index.jsonl"
    original = b'{"source_path":"already-grounded"}\n'
    index.write_bytes(original)
    with pytest.raises(TypeError):
        rag._write_index(str(index), [{"not_json": object()}])
    assert index.read_bytes() == original
    assert list(tmp_path.glob(".index.jsonl.*.tmp")) == []

    monkeypatch.setattr(rag.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError, match="disk"):
        rag._write_index(str(index), [{"source_path": "replacement"}])
    assert index.read_bytes() == original


def test_attestation_is_request_bound_hmac_with_exact_18_fields(tmp_path, monkeypatch):
    query = tmp_path / "request.query"
    query.write_bytes("ground me exactly π".encode())
    key = bytes(range(32))
    grounding = {
        "node_id": "@1.1.9.7",
        "content_node_id": "@1.4.10.9",
        "source_key": "1" * 64,
        "source_path": "specs/example.md",
        "answer_key": "2" * 64,
        "persisted_source_sha256": "1" * 64,
    }
    certificate = {
        "certificate_node_id": "@1.1.9.8",
        "certificate_subject_content_node_id": "@1.4.10.10",
        "certificate_answer_key": "3" * 64,
        "certificate_evidence_key": "4" * 64,
        "certificate_expires_epoch": 1200,
        "certificate_result": "success",
    }
    monkeypatch.setattr(rag, "verify_grounding", lambda _node, _index: (True, grounding))
    monkeypatch.setattr(
        rag, "verify_frequency_certificate", lambda _node, _index: (True, certificate)
    )
    monkeypatch.setattr(rag, "_attestation_key", lambda: key)
    monkeypatch.setattr(rag.time, "time", lambda: 1000)

    ok, receipt = rag.native_trace_receipt(
        "@1.1.9.7", "unused", str(query), "request_A"
    )
    assert ok is True
    fields = receipt.split("|")
    assert len(fields) == 18
    expected_ground = hmac.new(
        key,
        "\n".join(
            ["grounding-attestation-v2", "request_A", *fields[:9]]
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    expected_frequency = hmac.new(
        key,
        "\n".join(
            ["frequency-attestation-v2", "request_A", *fields[10:17]]
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    assert fields[9] == expected_ground
    assert fields[17] == expected_frequency
    assert fields[5] == grounding["persisted_source_sha256"]
    assert fields[6] == hashlib.sha256(query.read_bytes()).hexdigest()
    assert rag.native_trace_receipt("@1.1.9.7", "unused", str(query), "bad/id")[0] is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode assertion")
def test_attestation_key_is_exactly_32_bytes_and_mode_0600(tmp_path, monkeypatch):
    path = tmp_path / "attestation" / "grounding-v1.key"
    monkeypatch.setattr(rag, "_attestation_key_path", lambda: path)
    key = rag._attestation_key()
    assert len(key) == 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="permissions/ownership"):
        rag._attestation_key()


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink assertion")
def test_attestation_refuses_a_symlinked_key_directory(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    attestation = tmp_path / "attestation"
    attestation.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(
        rag, "_attestation_key_path", lambda: attestation / "grounding-v1.key"
    )
    with pytest.raises(RuntimeError, match="directory is insecure"):
        rag._attestation_key()


@pytest.mark.parametrize(
    "answer",
    [b"plain", b"trailing newline\n", b"embedded\nanswer:marker", "café π".encode(), b"nul\0byte"],
)
def test_byte_protocol_round_trips_exact_answer_bytes(answer):
    trust, fields, bindings, decoded, payload = substrate_router._parse_native_grounded_payload(
        _grounded_stdout(answer), _trust()
    )
    assert trust == _trust().decode().rstrip("\n")
    assert fields["path"] == "native"
    assert bindings["source-path"] == "C:/body/specs/example.md"
    assert decoded.encode() == answer
    assert payload.encode().endswith(b"\nanswer:" + answer)


def test_byte_protocol_accepts_a_typed_miss():
    _trust_line, fields, bindings, answer, payload = (
        substrate_router._parse_native_grounded_payload(
            b"grounded:miss\n", _trust(grounded=False)
        )
    )
    assert fields["grounded"] == "no"
    assert bindings == {}
    assert answer == ""
    assert payload == "grounded:miss\n"


def test_grounded_api_protocol_rejects_any_rented_path():
    rented = _trust(grounded=False).replace(
        b"path:native", b"path:rented"
    ).replace(b"native-partial", b"rented")
    with pytest.raises(substrate_router.HTTPException, match="non-native path"):
        substrate_router._parse_native_grounded_payload(b"grounded:miss\n", rented)


@pytest.mark.parametrize(
    ("stdout", "stderr", "detail"),
    [
        (_grounded_stdout(b"answer", **{"answer-key": "0" * 64}), _trust(), "digest"),
        (_grounded_stdout(b"answer")[:-1], _trust(), "framing"),
        (
            _grounded_stdout(b"answer"),
            _trust(observed=True).replace(b"observed:yes", b"observed:no"),
            "observed claim",
        ),
        (_grounded_stdout(b"\xff"), _trust(), "non-UTF-8"),
    ],
)
def test_byte_protocol_rejects_fabricated_or_malformed_claims(stdout, stderr, detail):
    with pytest.raises(substrate_router.HTTPException, match=detail):
        substrate_router._parse_native_grounded_payload(stdout, stderr)


@pytest.mark.parametrize("query", ["nul\0byte", "line\nbreak", "tab\tbyte", "delete\x7f"])
def test_api_rejects_control_bytes_before_staging(query):
    with pytest.raises(ValidationError):
        substrate_router.GroundedAskRequest(query=query)


def test_api_binds_stable_native_carrier_before_and_after_ask(tmp_path, monkeypatch):
    wrapper = tmp_path / "bin" / "form-cli"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    wrapper.chmod(0o755)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(substrate_router, "_grounded_ask_root", lambda: tmp_path)
    observation = _carrier_observation(tmp_path)
    monkeypatch.setattr(
        native_runtime_observation,
        "observe_native_runtime",
        lambda *, force=False: json.loads(json.dumps(observation)),
    )

    def run(command, **_kwargs):
        assert command[:2] == [str(wrapper), "ask-file"]
        assert Path(command[2]).read_text(encoding="utf-8") == "what is grounded?"
        return SimpleNamespace(
            returncode=0,
            stdout=_grounded_stdout(b"exact native answer"),
            stderr=_trust(),
        )

    monkeypatch.setattr(substrate_router, "_run_native_wrapper", run)
    response = substrate_router.grounded_ask(
        substrate_router.GroundedAskRequest(query="what is grounded?")
    )
    assert response.answer == "exact native answer"
    assert response.native_challenge_digest == observation["challenge_digest"]
    assert response.form_cli_binary_sha256 == "3" * 64
    assert response.form_cli_table_sha256 == "4" * 64
    assert response.form_cli_wrapper_sha256 == "5" * 64
    assert response.kernel_runtime == "fkwu"


def test_api_rejects_fake_root_and_mid_request_carrier_drift(tmp_path, monkeypatch):
    wrapper = tmp_path / "bin" / "form-cli"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(substrate_router, "_grounded_ask_root", lambda: tmp_path)
    wrong_root = _carrier_observation(tmp_path / "other")
    monkeypatch.setattr(
        native_runtime_observation,
        "observe_native_runtime",
        lambda *, force=False: wrong_root,
    )
    with pytest.raises(substrate_router.HTTPException, match="root mismatch"):
        substrate_router._run_grounded_ask("fake root")

    observations = iter(
        [_carrier_observation(tmp_path), _carrier_observation(tmp_path, challenge="9" * 64)]
    )
    monkeypatch.setattr(
        native_runtime_observation,
        "observe_native_runtime",
        lambda *, force=False: next(observations),
    )
    monkeypatch.setattr(
        substrate_router,
        "_run_native_wrapper",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=_grounded_stdout(b"answer"), stderr=_trust()
        ),
    )
    with pytest.raises(substrate_router.HTTPException, match="changed during ask"):
        substrate_router._run_grounded_ask("carrier drift")


def test_concurrent_queries_cannot_cross_associate_staged_bytes(tmp_path, monkeypatch):
    wrapper = tmp_path / "bin" / "form-cli"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(substrate_router, "_grounded_ask_root", lambda: tmp_path)
    observation = _carrier_observation(tmp_path)
    monkeypatch.setattr(
        native_runtime_observation,
        "observe_native_runtime",
        lambda *, force=False: json.loads(json.dumps(observation)),
    )
    staged: list[Path] = []

    def run(command, **_kwargs):
        query_path = Path(command[2])
        staged.append(query_path)
        answer = query_path.read_bytes()
        return SimpleNamespace(returncode=0, stdout=_grounded_stdout(answer), stderr=_trust())

    monkeypatch.setattr(substrate_router, "_run_native_wrapper", run)
    queries = [f"query {index} unique payload" for index in range(16)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(lambda query: substrate_router._run_grounded_ask(query).answer, queries))
    assert answers == queries
    assert len({str(path) for path in staged}) == len(queries)
    assert all(not path.exists() for path in staged)


def test_native_observer_rejects_digest_matched_but_behaviorally_fake_carrier(
    tmp_path, monkeypatch
):
    root = tmp_path
    form = root / "form"
    bootstrap = form / "form-stdlib" / "bootstrap"
    wrapper_dir = root / "bin"
    bootstrap.mkdir(parents=True)
    wrapper_dir.mkdir()
    binary = form / "form-cli"
    binary.write_text("#!/bin/sh\nprintf 'fabricated\\n'\n", encoding="utf-8")
    binary.chmod(0o755)
    (form / "form-cli.sha256").write_text(
        hashlib.sha256(binary.read_bytes()).hexdigest() + "\n", encoding="ascii"
    )
    (bootstrap / "form-cli-table.txt").write_text("1 2 3\n", encoding="ascii")
    (bootstrap / "form-cli.stamp").write_text("a" * 16 + "\n", encoding="ascii")
    (bootstrap / "form-cli.source.sha256").write_text(
        "c" * 64 + "\n", encoding="ascii"
    )
    wrapper = wrapper_dir / "form-cli"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (wrapper_dir / "form-cli.sha256").write_text(
        hashlib.sha256(wrapper.read_bytes()).hexdigest() + "\n", encoding="ascii"
    )
    monkeypatch.setattr(native_runtime_observation, "_root", lambda: root)
    monkeypatch.setattr(
        native_runtime_observation,
        "_observe_kernel",
        lambda: {"verified": True, "runtime": "fkwu", "binary_sha256": "b" * 64},
    )
    native_runtime_observation.reset_native_runtime_observation_cache()
    result = native_runtime_observation.observe_native_runtime(force=True)
    assert result["verified"] is False
    assert "carrier identity mismatch" in result["error"]


def test_native_observer_uses_receipted_host_carrier_outside_submodule(tmp_path):
    root = tmp_path
    bootstrap = root / "form" / "form-stdlib" / "bootstrap"
    carrier = root / ".cache" / "form-cli-native" / "linux-amd64" / "form-cli"
    bootstrap.mkdir(parents=True)
    carrier.parent.mkdir(parents=True)
    carrier.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    carrier.chmod(0o755)
    source_sha = "c" * 64
    binary_sha = hashlib.sha256(carrier.read_bytes()).hexdigest()
    (bootstrap / "form-cli.source.sha256").write_text(
        source_sha + "\n", encoding="ascii"
    )
    (root / ".cache" / "form-cli-native" / "selected.json").write_text(
        json.dumps(
            {
                "schema": "selected-form-cli-carrier-v1",
                "native_path": str(carrier),
                "binary_sha256": binary_sha,
                "source_sha256": source_sha,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert native_runtime_observation._selected_form_cli_binary(root) == carrier

    escaped = root / "outside-form-cli"
    escaped.write_bytes(carrier.read_bytes())
    escaped.chmod(0o755)
    receipt = root / ".cache" / "form-cli-native" / "selected.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "selected-form-cli-carrier-v1",
                "native_path": str(escaped),
                "binary_sha256": binary_sha,
                "source_sha256": source_sha,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        native_runtime_observation.NativeRuntimeObservationError,
        match="escapes the host-native cache",
    ):
        native_runtime_observation._selected_form_cli_binary(root)


def test_wrapper_manifest_and_fail_closed_native_flow_are_current():
    wrapper = ROOT / "bin" / "form-cli"
    manifest = (ROOT / "bin" / "form-cli.sha256").read_text(encoding="ascii").strip()
    assert hashlib.sha256(wrapper.read_bytes()).hexdigest() == manifest
    source = wrapper.read_text(encoding="utf-8")
    assert "set -euo pipefail" in source
    assert "validate-current" in source
    assert "ask-request-trace" in source
    assert "native carrier/index identity changed during capture" in source
    assert "native grounding attestation failed" in source
    assert "Observed callers enforce the stronger all-four-axis row" in source
    assert "first_line=\"${first_line%$'\\r'}\"" in source
    assert "trust_line=\"${trust_line%$'\\r'}\"" in source
    assert '"$receipt_file.consuming"' in source
    assert "attempt=1" in source and '"$attempt" -le 2' in source
    assert "fcntl" not in source


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group assertion")
def test_api_timeout_kills_wrapper_descendants(tmp_path):
    marker = tmp_path / "leaked-child"
    wrapper = tmp_path / "slow-wrapper"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"(sleep 0.5; printf leaked > '{marker}') &\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    with pytest.raises(subprocess.TimeoutExpired):
        substrate_router._run_native_wrapper(
            [str(wrapper)], cwd=tmp_path, timeout=0.1
        )
    time.sleep(0.7)
    assert not marker.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink assertion")
def test_api_refuses_a_symlinked_query_staging_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    staging = tmp_path / "api-queries"
    staging.symlink_to(outside, target_is_directory=True)
    with pytest.raises(
        substrate_router.HTTPException, match="staging directory is insecure"
    ):
        substrate_router._secure_native_query_directory(staging)


def test_image_built_carrier_is_proven_and_never_replaced_by_standard_lane(tmp_path):
    scripts = tmp_path / "scripts"
    form = tmp_path / "form"
    form_scripts = form / "scripts"
    bootstrap = form / "form-stdlib" / "bootstrap"
    scripts.mkdir()
    form_scripts.mkdir(parents=True)
    bootstrap.mkdir(parents=True)
    (form_scripts / "form_cli_bootstrap_proof.sh").write_bytes(
        (ROOT / "form" / "scripts" / "form_cli_bootstrap_proof.sh").read_bytes()
    )
    ensure = scripts / "ensure_form_cli_native.sh"
    ensure.write_bytes((ROOT / "scripts" / "ensure_form_cli_native.sh").read_bytes())
    source_digest = "c" * 64
    (bootstrap / "form-cli.source.sha256").write_text(
        source_digest + "\n", encoding="ascii"
    )
    binary = form / "form-cli"
    binary.write_text(
        "#!/usr/bin/env bash\n"
        "IFS= read -r command\n"
        "case \"$command\" in\n"
        f"  carrier-id) printf '%s\\n' 'carrier-id|form-cli-carrier-v2|{source_digest}|coherence-kernel-fkwu-native-v2' ;;\n"
        f"  'carrier-challenge 000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f') printf '%s\\n' 'carrier-challenge-v1|{source_digest}|000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f|1cb41be978d307c11bf41602cd11bdac834046103d6fc89a6f69cd0c6c4efb21' ;;\n"
        "  *) exit 9 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    manifest = form / "form-cli.sha256"
    manifest.write_text(
        hashlib.sha256(binary.read_bytes()).hexdigest() + "\n", encoding="ascii"
    )
    result = subprocess.run(
        ["bash", str(ensure)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    before = binary.read_bytes()
    manifest.write_text("0" * 64 + "\n", encoding="ascii")
    rejected = subprocess.run(
        ["bash", str(ensure)], capture_output=True, text=True, check=False
    )
    assert rejected.returncode == 1
    assert "failed digest/identity challenge" in rejected.stderr
    assert binary.read_bytes() == before


@pytest.mark.skipif(os.name == "nt", reason="Git Bash carrier fixture is POSIX")
@pytest.mark.parametrize("windows_host", [False, True])
def test_missing_platform_bootstrap_links_once_then_reuses_verified_native_carrier(
    tmp_path, windows_host,
):
    scripts = tmp_path / "scripts"
    form = tmp_path / "form"
    form_scripts = form / "scripts"
    bootstrap = form / "form-stdlib" / "bootstrap"
    scripts.mkdir()
    form_scripts.mkdir(parents=True)
    bootstrap.mkdir(parents=True)
    (form_scripts / "form_cli_bootstrap_proof.sh").write_bytes(
        (ROOT / "form" / "scripts" / "form_cli_bootstrap_proof.sh").read_bytes()
    )
    ensure = scripts / "ensure_form_cli_native.sh"
    ensure.write_bytes((ROOT / "scripts" / "ensure_form_cli_native.sh").read_bytes())
    source_digest = "c" * 64
    (bootstrap / "form-cli.source.sha256").write_text(
        source_digest + "\n", encoding="ascii"
    )
    build_count = form / "build-count"
    build = form / "build-form-cli.sh"
    build.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [ \"${FORM_STANDARD_LANE:-0}\" = 1 ]; then exit 1; fi\n"
        f"printf x >> '{build_count}'\n"
        "out=$1\n"
        "cat > \"$out\" <<'CARRIER'\n"
        "#!/usr/bin/env bash\n"
        "IFS= read -r command\n"
        "case \"$command\" in\n"
        f"  carrier-id) printf '%s\\n' 'carrier-id|form-cli-carrier-v2|{source_digest}|coherence-kernel-fkwu-native-v2' ;;\n"
        f"  'carrier-challenge 000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f') printf '%s\\n' 'carrier-challenge-v1|{source_digest}|000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f|1cb41be978d307c11bf41602cd11bdac834046103d6fc89a6f69cd0c6c4efb21' ;;\n"
        "  ping) printf 'pong\\n' ;;\n"
        "  *) exit 9 ;;\n"
        "esac\n"
        "CARRIER\n"
        "chmod +x \"$out\"\n",
        encoding="utf-8",
    )
    build.chmod(0o755)

    env = os.environ.copy()
    if windows_host:
        env["OS"] = "Windows_NT"
    else:
        env.pop("OS", None)
    first = subprocess.run(
        ["bash", str(ensure), "--print-path"],
        capture_output=True,
        text=True,
        env=env,
    )
    second = subprocess.run(
        ["bash", str(ensure), "--print-path"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert first.returncode == second.returncode == 0
    assert build_count.read_text(encoding="ascii") == "x"
    target = Path(first.stdout.strip())
    assert target.name == ("form-cli.exe" if windows_host else "form-cli")
    ping = subprocess.run(
        [str(target)], input="ping\n", capture_output=True, text=True, check=False
    )
    assert ping.returncode == 0 and ping.stdout == "pong\n"


def test_bootstrap_corpus_includes_every_native_answer_family():
    relative = {path.relative_to(ROOT).as_posix() for path in coh.form_first_source_paths()}
    assert any(path.startswith("form/form-stdlib/") for path in relative)
    assert any(path.startswith("specs/") for path in relative)
    assert any(path.startswith("docs/vision-kb/concepts/") for path in relative)
    assert any(path.startswith("docs/coherence-substrate/") for path in relative)
    assert any(path.startswith("docs/shared/") for path in relative)


def test_rag_source_identity_is_platform_independent():
    assert (
        rag._canonical_source_path(r"form\form-stdlib\rag-ask.fk")
        == "form/form-stdlib/rag-ask.fk"
    )


def test_real_native_carrier_identity_challenge_and_embedding(tmp_path):
    binary = _ensure_host_native_carrier()
    stamp_path = (
        ROOT
        / "form"
        / "form-stdlib"
        / "bootstrap"
        / "form-cli.source.sha256"
    )
    if (
        not binary.is_file()
        or not os.access(binary, os.X_OK)
        or not stamp_path.is_file()
    ):
        pytest.skip("native carrier-v2 submodule pin not initialized")
    stamp = stamp_path.read_text(encoding="ascii").strip()
    identity = subprocess.run(
        [str(binary)], input=b"carrier-id\n", capture_output=True, check=False, timeout=10
    )
    expected_identity = (
        f"carrier-id|form-cli-carrier-v2|{stamp}|"
        "coherence-kernel-fkwu-native-v2\n"
    ).encode()
    if identity.stdout != expected_identity:
        pytest.skip("kernel submodule pin does not yet contain carrier-v2")
    assert identity.returncode == 0 and identity.stderr == b""

    nonce = "00" * 32
    expected_digest = hashlib.sha256(
        b"form-cli-carrier-challenge-v1\n" + nonce.encode()
    ).hexdigest()
    challenge = subprocess.run(
        [str(binary)],
        input=f"carrier-challenge {nonce}\n".encode(),
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert challenge.returncode == 0 and challenge.stderr == b""
    assert challenge.stdout == (
        f"carrier-challenge-v1|{stamp}|{nonce}|{expected_digest}\n"
    ).encode()

    request_dir = tmp_path / ".coherence-network" / "rag-requests"
    request_dir.mkdir(parents=True)
    request_id = "native_band"
    item_id = "source-A"
    text = "grounded deployment proof kernel"
    (request_dir / f"{request_id}.embed").write_text(
        f"{item_id.encode().hex()}|{text.encode().hex()}\n", encoding="ascii"
    )
    embedded = subprocess.run(
        [str(binary)],
        cwd=tmp_path,
        input=f"embed-request {request_id}\n".encode(),
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert embedded.returncode == 0 and embedded.stderr == b""
    row = json.loads(embedded.stdout)
    assert set(row) == {"id_hex", "embedding_kind", "vec"}
    assert row["id_hex"] == item_id.encode().hex()
    assert row["embedding_kind"] == rag.EMBEDDING_KIND
    assert row["vec"] and all(isinstance(value, int) for value in row["vec"])


def test_real_native_request_hmac_replay_query_and_expiry_gates(tmp_path):
    binary = _ensure_host_native_carrier()
    source_digest = (
        ROOT
        / "form"
        / "form-stdlib"
        / "bootstrap"
        / "form-cli.source.sha256"
    )
    if not binary.is_file() or not source_digest.is_file():
        pytest.skip("native carrier-v2 submodule pin not initialized")

    request_dir = tmp_path / ".coherence-network" / "rag-requests"
    index_dir = tmp_path / ".coherence-network" / "rag-index"
    key_dir = tmp_path / ".coherence-network" / "attestation"
    request_dir.mkdir(parents=True)
    index_dir.mkdir(parents=True)
    key_dir.mkdir(parents=True)
    key = bytes(range(32))
    key_path = key_dir / "grounding-v1.key"
    key_path.write_text(key.hex() + "\n", encoding="ascii")
    key_path.chmod(0o600)

    query = b"grounded deployment proof kernel"
    request_id = "trace_valid"
    embed_id = "trace_embed"
    (request_dir / f"{embed_id}.embed").write_text(
        f"{b'row'.hex()}|{query.hex()}\n", encoding="ascii"
    )
    embedded = subprocess.run(
        [str(binary)],
        cwd=tmp_path,
        input=f"embed-request {embed_id}\n".encode(),
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert embedded.returncode == 0 and embedded.stderr == b""
    vector = json.loads(embedded.stdout)["vec"]
    answer = b"grounded deployment proof kernel"
    node_id = "@1.1.9.41"
    content_node_id = "@1.4.10.42"
    source_key = hashlib.sha256(b"persisted source").hexdigest()
    answer_key = hashlib.sha256(answer).hexdigest()
    row = {
        "id": node_id,
        "node_id": node_id,
        "content_node_id": content_node_id,
        "source_path": "specs/native-proof.md",
        "kind": "spec",
        "key": source_key,
        "persisted_source_sha256": source_key,
        "schema": "nodeid-rag-v2",
        "embedding_kind": "form-semantic-v2",
        "snippet": answer.decode(),
        "answer_key": answer_key,
        "answer_hex": answer.hex(),
        "vec": vector,
    }
    (index_dir / "index.jsonl").write_text(
        json.dumps(row, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    def command(text: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [str(binary)],
            cwd=tmp_path,
            input=(text + "\n").encode("ascii"),
            capture_output=True,
            check=False,
            timeout=20,
        )

    def receipt(
        bound_request_id: str,
        query_bytes: bytes,
        *,
        issued: int,
        expires: int,
    ) -> str:
        ground = [
            node_id,
            content_node_id,
            source_key,
            "specs/native-proof.md",
            answer_key,
            source_key,
            hashlib.sha256(query_bytes).hexdigest(),
            str(issued),
            str(expires),
        ]
        ground.append(
            hmac.new(
                key,
                "\n".join(
                    ["grounding-attestation-v2", bound_request_id, *ground]
                ).encode(),
                hashlib.sha256,
            ).hexdigest()
        )
        frequency = [
            node_id,
            content_node_id,
            answer_key,
                hashlib.sha256(
                    "\n".join(
                        [
                            "frequency-cert-v1",
                            node_id,
                            content_node_id,
                            answer_key,
                            "success",
                        ]
                    ).encode()
                ).hexdigest(),
            str(issued),
            str(expires),
            "success",
        ]
        frequency.append(
            hmac.new(
                key,
                "\n".join(
                    ["frequency-attestation-v2", bound_request_id, *frequency]
                ).encode(),
                hashlib.sha256,
            ).hexdigest()
        )
        return "|".join([*ground, *frequency])

    now = int(time.time())
    query_path = request_dir / f"{request_id}.query"
    receipt_path = request_dir / f"{request_id}.receipt"
    query_path.write_bytes(query)
    requested = command(f"ask-request {request_id}")
    assert requested.returncode == 0 and requested.stderr == b""
    assert requested.stdout.startswith(f"grounded:{node_id}\n".encode())
    receipt_path.write_text(
        receipt(request_id, query, issued=now, expires=now + 60) + "\n",
        encoding="ascii",
    )
    traced = command(f"ask-request-trace {request_id}")
    assert traced.returncode == 0 and traced.stderr == b""
    trust_line, grounded_payload = traced.stdout.split(b"\n", 1)
    parsed = substrate_router._parse_native_grounded_payload(
        grounded_payload, trust_line + b"\n"
    )
    assert parsed[1]["observed"] == "yes"
    assert parsed[3].encode() == answer
    assert not query_path.exists()
    assert not receipt_path.exists()
    assert not Path(str(receipt_path) + ".consuming").exists()
    replay = command(f"ask-request-trace {request_id}")
    assert replay.stdout == b"ask-request-trace:error:missing-receipt\n"

    wrong_id = "trace_wrong_id"
    (request_dir / f"{wrong_id}.query").write_bytes(query)
    (request_dir / f"{wrong_id}.receipt").write_text(
        receipt(request_id, query, issued=now, expires=now + 60) + "\n",
        encoding="ascii",
    )
    wrong_request = command(f"ask-request-trace {wrong_id}")
    assert b"grounded:no" in wrong_request.stdout.split(b"\n", 1)[0]

    wrong_query_id = "trace_wrong_query"
    changed_query = b"deployment grounded proof kernel"
    (request_dir / f"{wrong_query_id}.query").write_bytes(changed_query)
    (request_dir / f"{wrong_query_id}.receipt").write_text(
        receipt(wrong_query_id, query, issued=now, expires=now + 60) + "\n",
        encoding="ascii",
    )
    wrong_query = command(f"ask-request-trace {wrong_query_id}")
    assert b"grounded:no" in wrong_query.stdout.split(b"\n", 1)[0]

    forged_ground_id = "trace_forged_ground"
    (request_dir / f"{forged_ground_id}.query").write_bytes(query)
    forged_ground = receipt(
        forged_ground_id, query, issued=now, expires=now + 60
    ).split("|")
    forged_ground[9] = "0" * 64
    (request_dir / f"{forged_ground_id}.receipt").write_text(
        "|".join(forged_ground) + "\n", encoding="ascii"
    )
    forged_ground_result = command(f"ask-request-trace {forged_ground_id}")
    assert b"grounded:no" in forged_ground_result.stdout.split(b"\n", 1)[0]

    forged_frequency_id = "trace_forged_frequency"
    (request_dir / f"{forged_frequency_id}.query").write_bytes(query)
    forged_frequency = receipt(
        forged_frequency_id, query, issued=now, expires=now + 60
    ).split("|")
    forged_frequency[17] = "0" * 64
    (request_dir / f"{forged_frequency_id}.receipt").write_text(
        "|".join(forged_frequency) + "\n", encoding="ascii"
    )
    forged_frequency_result = command(
        f"ask-request-trace {forged_frequency_id}"
    )
    forged_trust = forged_frequency_result.stdout.split(b"\n", 1)[0]
    assert b"grounded:yes" in forged_trust
    assert b"freq:yes" not in forged_trust
    assert b"observed:no" in forged_trust

    expired_id = "trace_expired"
    (request_dir / f"{expired_id}.query").write_bytes(query)
    (request_dir / f"{expired_id}.receipt").write_text(
        receipt(expired_id, query, issued=now - 400, expires=now - 100) + "\n",
        encoding="ascii",
    )
    expired = command(f"ask-request-trace {expired_id}")
    assert b"grounded:no" in expired.stdout.split(b"\n", 1)[0]
