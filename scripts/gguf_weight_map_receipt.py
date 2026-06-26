#!/usr/bin/env python3
"""gguf_weight_map_receipt.py — walk a real GGUF tensor map without loading weights."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import BinaryIO, Any


GGUF_MAGIC = 0x46554747
DEFAULT_ALIGNMENT = 32

GGUF_VALUE_TYPES = {
    0: ("uint8", 1),
    1: ("int8", 1),
    2: ("uint16", 2),
    3: ("int16", 2),
    4: ("uint32", 4),
    5: ("int32", 4),
    6: ("float32", 4),
    7: ("bool", 1),
    8: ("string", None),
    9: ("array", None),
    10: ("uint64", 8),
    11: ("int64", 8),
    12: ("float64", 8),
}

GGML_TYPES = {
    0: "F32",
    1: "F16",
    2: "Q4_0",
    3: "Q4_1",
    4: "Q4_2",
    5: "Q4_3",
    6: "Q5_0",
    7: "Q5_1",
    8: "Q8_0",
    9: "Q8_1",
    10: "Q2_K",
    11: "Q3_K",
    12: "Q4_K",
    13: "Q5_K",
    14: "Q6_K",
    15: "Q8_K",
    16: "IQ2_XXS",
    17: "IQ2_XS",
    18: "IQ3_XXS",
    19: "IQ1_S",
    20: "IQ4_NL",
    21: "IQ3_S",
    22: "IQ2_S",
    23: "IQ4_XS",
    24: "I8",
    25: "I16",
    26: "I32",
    27: "I64",
    28: "F64",
    29: "IQ1_M",
    30: "BF16",
}

LLAMA_REQUIRED_TENSORS = (
    "rope_freqs.weight",
    "token_embd.weight",
    "blk.0.attn_norm.weight",
    "blk.0.attn_q.weight",
    "blk.0.attn_k.weight",
    "blk.0.attn_v.weight",
    "blk.0.attn_output.weight",
    "blk.0.ffn_norm.weight",
    "blk.0.ffn_gate.weight",
    "blk.0.ffn_up.weight",
    "blk.0.ffn_down.weight",
    "output_norm.weight",
)


class GGUFReadError(RuntimeError):
    """Raised when the GGUF table cannot be walked."""


def read_exact(f: BinaryIO, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise GGUFReadError(f"unexpected EOF while reading {n} bytes at offset {f.tell()}")
    return data


def read_u32(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 4), "little", signed=False)


def read_u64(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 8), "little", signed=False)


def read_i32(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 4), "little", signed=True)


def read_i64(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 8), "little", signed=True)


def read_f32(f: BinaryIO) -> float:
    import struct

    return struct.unpack("<f", read_exact(f, 4))[0]


def read_f64(f: BinaryIO) -> float:
    import struct

    return struct.unpack("<d", read_exact(f, 8))[0]


def read_string(f: BinaryIO) -> str:
    length = read_u64(f)
    if length > 256 * 1024 * 1024:
        raise GGUFReadError(f"implausible GGUF string length {length} at offset {f.tell() - 8}")
    return read_exact(f, length).decode("utf-8", "replace")


def align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def small_scalar(f: BinaryIO, value_type: int) -> Any:
    if value_type == 0:
        return int.from_bytes(read_exact(f, 1), "little", signed=False)
    if value_type == 1:
        return int.from_bytes(read_exact(f, 1), "little", signed=True)
    if value_type == 2:
        return int.from_bytes(read_exact(f, 2), "little", signed=False)
    if value_type == 3:
        return int.from_bytes(read_exact(f, 2), "little", signed=True)
    if value_type == 4:
        return read_u32(f)
    if value_type == 5:
        return read_i32(f)
    if value_type == 6:
        return read_f32(f)
    if value_type == 7:
        return bool(int.from_bytes(read_exact(f, 1), "little", signed=False))
    if value_type == 10:
        return read_u64(f)
    if value_type == 11:
        return read_i64(f)
    if value_type == 12:
        return read_f64(f)
    raise GGUFReadError(f"unsupported scalar metadata type {value_type}")


def skip_array_value(f: BinaryIO, element_type: int, count: int) -> dict[str, Any]:
    type_name, fixed_size = GGUF_VALUE_TYPES.get(element_type, (f"type_{element_type}", None))
    start = f.tell()
    sample: list[Any] = []
    if fixed_size is not None:
        f.seek(count * fixed_size, os.SEEK_CUR)
    elif element_type == 8:
        for i in range(count):
            value = read_string(f)
            if i < 3:
                sample.append(value)
    elif element_type == 9:
        for _ in range(count):
            nested_type = read_u32(f)
            nested_count = read_u64(f)
            skip_array_value(f, nested_type, nested_count)
    else:
        raise GGUFReadError(f"unsupported array metadata type {element_type}")
    return {
        "type": "array",
        "element_type": type_name,
        "count": count,
        "bytes": f.tell() - start,
        "sample": sample,
    }


def read_metadata_value(f: BinaryIO, value_type: int) -> Any:
    if value_type == 8:
        return read_string(f)
    if value_type == 9:
        element_type = read_u32(f)
        count = read_u64(f)
        return skip_array_value(f, element_type, count)
    return small_scalar(f, value_type)


def read_header(f: BinaryIO) -> dict[str, int]:
    magic = read_u32(f)
    version = read_u32(f)
    tensor_count = read_u64(f)
    kv_count = read_u64(f)
    if magic != GGUF_MAGIC:
        raise GGUFReadError(f"bad magic 0x{magic:08x}; not a GGUF file")
    return {
        "magic": magic,
        "version": version,
        "tensor_count": tensor_count,
        "metadata_kv_count": kv_count,
    }


def summarize_metadata(f: BinaryIO, kv_count: int) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    tokenizer_keys: list[str] = []
    tokenizer_array_counts: dict[str, int] = {}
    for _ in range(kv_count):
        key = read_string(f)
        value_type = read_u32(f)
        value = read_metadata_value(f, value_type)
        if key.startswith("tokenizer."):
            tokenizer_keys.append(key)
            if isinstance(value, dict) and value.get("type") == "array":
                tokenizer_array_counts[key] = int(value.get("count", 0))
        if key in {
            "general.architecture",
            "general.name",
            "general.basename",
            "general.size_label",
            "general.alignment",
            "llama.block_count",
            "llama.embedding_length",
            "llama.context_length",
            "llama.attention.head_count",
            "llama.attention.head_count_kv",
            "tokenizer.ggml.model",
            "tokenizer.ggml.pre",
            "tokenizer.ggml.bos_token_id",
            "tokenizer.ggml.eos_token_id",
        }:
            metadata[key] = value
    metadata["tokenizer_keys"] = tokenizer_keys
    metadata["tokenizer_array_counts"] = tokenizer_array_counts
    return metadata, {
        "tokenizer_key_count": len(tokenizer_keys),
        "tokenizer_array_counts": tokenizer_array_counts,
    }


def choose_default_path() -> Path | None:
    home = Path.home()
    candidates: list[Path] = []
    candidates.extend(sorted((home / ".ollama/models/blobs").glob("sha256-*")))
    candidates.extend(sorted((home / "mentor-install/.models").glob("*.gguf")))

    preferred: list[Path] = []
    fallback: list[Path] = []
    for path in candidates:
        try:
            size = path.stat().st_size
            if size < 1_000_000_000:
                continue
            with path.open("rb") as f:
                if int.from_bytes(f.read(4), "little", signed=False) != GGUF_MAGIC:
                    continue
            if 1_500_000_000 <= size <= 2_500_000_000:
                preferred.append(path)
            else:
                fallback.append(path)
        except OSError:
            continue
    if preferred:
        return preferred[0]
    if fallback:
        return fallback[0]
    return None


def receipt_for(path: Path) -> dict[str, Any]:
    file_size = path.stat().st_size
    with path.open("rb") as f:
        header = read_header(f)
        metadata_start = f.tell()
        metadata, metadata_summary = summarize_metadata(f, int(header["metadata_kv_count"]))
        tensor_table_start = f.tell()
        alignment = int(metadata.get("general.alignment") or DEFAULT_ALIGNMENT)

        # First pass finds the end of the tensor table. Data starts after alignment.
        raw_tensors: list[dict[str, Any]] = []
        for index in range(int(header["tensor_count"])):
            name = read_string(f)
            ndims = read_u32(f)
            if ndims > 16:
                raise GGUFReadError(f"tensor {index} has implausible dim count {ndims}")
            dims = [read_u64(f) for _ in range(ndims)]
            ggml_type = read_u32(f)
            data_offset = read_u64(f)
            raw_tensors.append(
                {
                    "index": index,
                    "name": name,
                    "dims": dims,
                    "ggml_type": ggml_type,
                    "type": GGML_TYPES.get(ggml_type, f"type_{ggml_type}"),
                    "data_offset": data_offset,
                }
            )
        tensor_table_end = f.tell()
        tensor_data_start = align_up(tensor_table_end, alignment)

    tensors = []
    for row in raw_tensors:
        absolute_start = tensor_data_start + int(row["data_offset"])
        with_start = dict(row)
        with_start["absolute_start"] = absolute_start
        tensors.append(with_start)
    by_offset = sorted(tensors, key=lambda row: (int(row["data_offset"]), int(row["index"])))
    for row_index, row in enumerate(by_offset):
        absolute_end = int(by_offset[row_index + 1]["absolute_start"]) if row_index + 1 < len(by_offset) else file_size
        row["absolute_end"] = absolute_end
        row["byte_length_by_next_offset"] = max(0, absolute_end - int(row["absolute_start"]))

    names = {str(row["name"]) for row in tensors}
    architecture = str(metadata.get("general.architecture") or "")
    required = LLAMA_REQUIRED_TENSORS if architecture == "llama" else ()
    missing_required = [name for name in required if name not in names]
    offset_values = [int(row["data_offset"]) for row in by_offset]
    unique_offsets = len(offset_values) == len(set(offset_values))
    nondecreasing_offsets = offset_values == sorted(offset_values)
    ranges_within_file = all(
        tensor_data_start <= int(row["absolute_start"]) <= int(row["absolute_end"]) <= file_size
        for row in by_offset
    )
    aligned_offsets = all(int(row["absolute_start"]) % alignment == 0 for row in by_offset)
    type_counts = Counter(str(row["type"]) for row in tensors)

    tensor_sample_keys = (
        "index",
        "name",
        "type",
        "dims",
        "data_offset",
        "absolute_start",
        "absolute_end",
        "byte_length_by_next_offset",
    )
    first = [{key: row[key] for key in tensor_sample_keys} for row in by_offset[:8]]
    last = [{key: row[key] for key in tensor_sample_keys} for row in by_offset[-8:]]
    focus_names = list(dict.fromkeys([*required, "output.weight"]))
    focus_tensors = {
        str(row["name"]): {key: row[key] for key in tensor_sample_keys}
        for row in tensors
        if str(row["name"]) in focus_names
    }

    pass_conditions = [
        int(header["tensor_count"]) == len(tensors),
        int(header["metadata_kv_count"]) >= 1,
        tensor_table_start > metadata_start,
        tensor_table_end <= tensor_data_start <= file_size,
        unique_offsets,
        nondecreasing_offsets,
        ranges_within_file,
        aligned_offsets,
        not missing_required,
        bool(metadata_summary["tokenizer_key_count"]),
    ]

    verdict = "pass" if all(pass_conditions) else "fail"
    return {
        "receipt_kind": "gguf-full-weight-map-receipt",
        "verdict": verdict,
        "path": str(path),
        "filename": path.name,
        "size_bytes": file_size,
        "header": header,
        "metadata": {
            "architecture": architecture,
            "name": metadata.get("general.name"),
            "basename": metadata.get("general.basename"),
            "size_label": metadata.get("general.size_label"),
            "alignment": alignment,
            "llama_block_count": metadata.get("llama.block_count"),
            "llama_embedding_length": metadata.get("llama.embedding_length"),
            "llama_context_length": metadata.get("llama.context_length"),
            "llama_head_count": metadata.get("llama.attention.head_count"),
            "llama_head_count_kv": metadata.get("llama.attention.head_count_kv"),
            "tokenizer_model": metadata.get("tokenizer.ggml.model"),
            "tokenizer_pre": metadata.get("tokenizer.ggml.pre"),
            "tokenizer_bos_token_id": metadata.get("tokenizer.ggml.bos_token_id"),
            "tokenizer_eos_token_id": metadata.get("tokenizer.ggml.eos_token_id"),
            "tokenizer_keys": metadata.get("tokenizer_keys", []),
            "tokenizer_array_counts": metadata.get("tokenizer_array_counts", {}),
        },
        "tensor_map": {
            "count_header": int(header["tensor_count"]),
            "count_observed": len(tensors),
            "metadata_start": metadata_start,
            "tensor_table_start": tensor_table_start,
            "tensor_table_end": tensor_table_end,
            "tensor_data_start": tensor_data_start,
            "alignment": alignment,
            "unique_offsets": unique_offsets,
            "nondecreasing_offsets": nondecreasing_offsets,
            "ranges_within_file": ranges_within_file,
            "aligned_offsets": aligned_offsets,
            "type_counts": dict(sorted(type_counts.items())),
            "required_tensors": list(required),
            "missing_required_tensors": missing_required,
            "first_by_data_offset": first,
            "last_by_data_offset": last,
            "focus_tensors": focus_tensors,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="GGUF path. Defaults to a real local Ollama/model GGUF.")
    parser.add_argument("--json", dest="json_path", help="Write the full receipt JSON to this path.")
    args = parser.parse_args()

    path = Path(args.path).expanduser() if args.path else choose_default_path()
    if path is None:
        print("no real GGUF path found in ~/.ollama/models/blobs or ~/mentor-install/.models", file=sys.stderr)
        return 2

    try:
        receipt = receipt_for(path)
    except (OSError, GGUFReadError) as exc:
        print(f"FAIL gguf weight map receipt: {exc}", file=sys.stderr)
        return 1

    if args.json_path:
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tensor_map = receipt["tensor_map"]
    metadata = receipt["metadata"]
    print(f"receipt: {receipt['receipt_kind']} verdict={receipt['verdict']}")
    print(f"file: {receipt['filename']} bytes={receipt['size_bytes']}")
    print(
        "header: "
        f"v={receipt['header']['version']} "
        f"n_tensors={receipt['header']['tensor_count']} "
        f"n_kv={receipt['header']['metadata_kv_count']} "
        f"architecture={metadata.get('architecture')}"
    )
    print(
        "tensor-map: "
        f"walked={tensor_map['count_observed']} "
        f"data_start={tensor_map['tensor_data_start']} "
        f"alignment={tensor_map['alignment']} "
        f"ranges_within_file={int(tensor_map['ranges_within_file'])} "
        f"aligned_offsets={int(tensor_map['aligned_offsets'])}"
    )
    print(f"types: {json.dumps(tensor_map['type_counts'], sort_keys=True)}")
    print(f"tokenizer-arrays: {json.dumps(metadata.get('tokenizer_array_counts', {}), sort_keys=True)}")
    missing = tensor_map["missing_required_tensors"]
    print(f"required-tensors: {'ok' if not missing else 'missing ' + ','.join(missing)}")
    return 0 if receipt["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
