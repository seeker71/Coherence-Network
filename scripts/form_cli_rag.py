#!/usr/bin/env python3
"""form_cli_rag.py — offline semantic memory for the form-cli's local oracle.

The form-cli's tier-1 oracle (a local LLM) can reason but is blind to the body —
it cannot recall the recipes / specs / concepts / substrate cells it lives inside.
This carrier gives it memory: it embeds every body doc with a LOCAL embedder
(nomic-embed-text via ollama), ranks a query against that index by L1 distance,
and grounds the local oracle's answer in the nearest docs. Fully offline once the
embed + chat models are pulled — no network crossing.

THE LOGIC IS FORM. The ranking primitive (L1 over quantized embedding bins,
nearest-walk, top-k) is form-stdlib/rag-retrieve.fk, proven four-way (Go/Rust/TS/
fkwu) by tests/rag-retrieve-band.fk and demonstrated ranking all 994 docs on the
Go kernel. This Python is a thin host-IO carrier: the embed call, the index store,
and a python mirror of rag-l1 for snappy serving (the kernel path is the proof,
this is the fast bootstrap until the kernel reads the index natively).

Usage:
  form_cli_rag.py build [--index PATH]              # (re)build the index over the body
  form_cli_rag.py ask "question" [-k 5] [-m MODEL]  # retrieve + ground a local answer
"""
from __future__ import annotations
import argparse, glob, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.expanduser("~/.coherence-network/rag-index/index.jsonl")
OLLAMA = "http://localhost:11434"

SOURCES = [
    ("recipe",    "form/form-stdlib/*.fk"),
    ("spec",      "specs/*.md"),
    ("concept",   "docs/vision-kb/concepts/*.md"),
    ("substrate", "docs/coherence-substrate/*.form"),
]


def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(OLLAMA + path,
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def embed(text: str) -> list[float]:
    return _post("/api/embeddings", {"model": "nomic-embed-text", "prompt": text[:4000]})["embedding"]


def quantize(vec: list[float]) -> list[int]:
    # nomic vectors ~[-1,1] -> ints 0..1000 (the embedding-as-recipe.fk convention)
    return [max(0, min(1000, int(round((x + 1.0) * 500)))) for x in vec]


def rag_l1(a: list[int], b: list[int]) -> int:
    # mirrors rag-retrieve.fk rag-l1 exactly: sum |a[i]-b[i]|, stop at the shorter
    return sum(abs(x - y) for x, y in zip(a, b))


def _snippet(path: str) -> str:
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    lines = [l for l in txt.splitlines() if l.strip()]
    return "\n".join(lines[:18])[:1200]


LOCAL_DOC_EXTS = (".md", ".txt", ".org", ".rst", ".py", ".ts", ".tsx", ".js",
                  ".go", ".rs", ".fk", ".form", ".json", ".yaml", ".yml", ".sh", ".html")


def _local_doc_paths(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for fn in sorted(filenames):
            if fn.lower().endswith(LOCAL_DOC_EXTS):
                yield os.path.join(dirpath, fn)


def build(index_path: str, doc_roots=None) -> None:
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    n = 0
    with open(index_path, "w") as out:
        def emit(rel_id, kind, sn):
            nonlocal n
            try:
                vec = quantize(embed(sn))
            except Exception:
                return
            out.write(json.dumps({"id": rel_id, "kind": kind, "snippet": sn[:400], "vec": vec}) + "\n")
            n += 1
            if n % 100 == 0:
                print(f"  ...{n} docs embedded", flush=True)
        # the body itself (recipes, specs, concepts, substrate)
        for kind, pat in SOURCES:
            for path in sorted(glob.glob(os.path.join(ROOT, pat))):
                sn = _snippet(path)
                if len(sn) >= 20:
                    emit(os.path.relpath(path, ROOT), kind, sn)
        # any local document folders the user points at
        for root in (doc_roots or []):
            root = os.path.abspath(os.path.expanduser(root))
            for path in _local_doc_paths(root):
                sn = _snippet(path)
                if len(sn) >= 20:
                    emit(path, "local", sn)
    print(f"[rag index built: {n} docs -> {index_path}]")


def retrieve(query: str, index_path: str, k: int) -> list[dict]:
    q = quantize(embed(query))
    entries = [json.loads(l) for l in open(index_path) if l.strip()]
    ranked = sorted(entries, key=lambda e: rag_l1(q, e["vec"]))  # ties keep first (stable sort)
    return ranked[:k]


def ground(query: str, hits: list[dict], model: str) -> str:
    context = "\n\n".join(f"[{h['id']}]\n{h['snippet']}" for h in hits)
    prompt = (
        "You are the Coherence Network's offline cell. Answer the question using ONLY the "
        "excerpts from the body below. Cite the doc ids you used. If the excerpts do not "
        "answer it, say so plainly.\n\n"
        f"=== body excerpts ===\n{context}\n\n=== question ===\n{query}\n\n=== answer ===\n"
    )
    return _post("/api/generate", {"model": model, "prompt": prompt, "stream": False})["response"].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--index", default=INDEX)
    b.add_argument("--docs", action="append", default=[], help="extra local folder(s) to index, repeatable")
    s = sub.add_parser("search"); s.add_argument("question")
    s.add_argument("-k", type=int, default=5); s.add_argument("--index", default=INDEX)
    c = sub.add_parser("context"); c.add_argument("question")
    c.add_argument("-k", type=int, default=3); c.add_argument("--index", default=INDEX)
    a = sub.add_parser("ask"); a.add_argument("question")
    a.add_argument("-k", type=int, default=5); a.add_argument("-m", "--model", default="qwen2.5:72b")
    a.add_argument("--index", default=INDEX)
    args = ap.parse_args()
    if args.cmd == "build":
        build(args.index, args.docs); return 0
    if args.cmd == "search":
        for h in retrieve(args.question, args.index, args.k):
            print(f"{h['id']}\t{h['kind']}")
        return 0
    if args.cmd == "context":
        # grounding block for the form-cli loop's guide: nearest body docs, terse
        for h in retrieve(args.question, args.index, args.k):
            print(f"[{h['id']}] {' '.join(h['snippet'].split())[:280]}")
        return 0
    hits = retrieve(args.question, args.index, args.k)
    print("── retrieved (Form-ranked: rag-retrieve.fk) ──")
    for h in hits:
        print(f"  · {h['id']}  ({h['kind']})")
    print("\n── grounded answer (local oracle, no network) ──")
    print(ground(args.question, hits, args.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
