#!/usr/bin/env python3
"""form_cli_rag.py — RETIRING bootstrap bridge for the form-cli's self-healing memory.

The destination is fkwu/Form: the memory loop runs on the kernel (form-stdlib/
rag-heal.fk over host-read/host-write), no Python/Go/TS/Rust/shell in the runtime
path. This file is the host-IO BRIDGE that still carries the default serving path
(enumerate the body, embed via the local model door, store the index) WHILE that
native lane lands. It is bootstrap/bridge compost, not the body — the kernel path is
the proof.

THE LOGIC IS FORM, proven four-way (Go/Rust/TS/fkwu):
  - content key       form-stdlib/rag-key.fk        rk-text-key  → 7  (adler32 over bytes)
  - freshness delta   form-stdlib/rag-freshness.fk  heal/orphan  → 63
  - retrieval depth   form-stdlib/rag-adaptive-k.fk knee-cut k   → 15
  - ranking           form-stdlib/rag-retrieve.fk   L1, top-k    → 31
The functions below (content_key, freshness, rak_k, rag_l1) are MIRRORS of those
recipes for snappy serving; the Form recipe is canonical, this is the fast mirror.

THE INDEX IS WATER. A materialized cache derived from the body, not a frozen artifact.
Each entry carries the CONTENT KEY (adler32 of its source bytes) — the freshness
coordinate. Before serving, the index self-heals: re-embed only what is missing or
drifted, compost orphans. New tissue is absorbed on the next breath.

The embedder (nomic-embed-text via ollama) is a LOCAL model-door crossing, offline
once pulled — the one host crossing the key/decision arithmetic never makes.

Usage:
  form_cli_rag.py build  [--index PATH] [--docs DIR ...]   # full (re)embed over the body
  form_cli_rag.py heal   [--index PATH] [--docs DIR ...]   # delta-only: embed what drifted
  form_cli_rag.py fresh  [--index PATH]                    # report drift without changing it
  form_cli_rag.py ask    "question" [-k N] [-m MODEL] [--no-heal]
  form_cli_rag.py search "query" [-k N] [--no-heal]
"""
from __future__ import annotations
import argparse, glob, json, os, sys, urllib.request, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.expanduser("~/.coherence-network/rag-index/index.jsonl")
OLLAMA = "http://localhost:11434"

# adaptive retrieval bounds — depth is the knee within [K_MIN, K_MAX], not a constant.
K_MIN, K_MAX = 3, 12

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


def rak_k(ds: list[int], kmin: int, kmax: int) -> int:
    """Mirror of rag-adaptive-k.fk rak-k: cut at the largest gap (the knee) in the
    ascending distances, bounded by [kmin, kmax], clamped to what's available."""
    n = len(ds)
    if n <= kmin:
        return n
    kmax2 = min(kmax, n)
    lo = kmin - 1
    hi = min(kmax2 - 1, n - 2)
    if hi < lo:
        return kmin
    best_i, best_gap = lo, ds[lo + 1] - ds[lo]
    for i in range(lo + 1, hi + 1):
        gap = ds[i + 1] - ds[i]
        if gap > best_gap:               # strict > keeps the smaller k on ties
            best_i, best_gap = i, gap
    return best_i + 1


def content_key(path: str) -> str:
    """The freshness coordinate: a content hash of the source bytes. Content-addressed,
    never mtime — mtime lies across clones and checkouts; the body's own axiom is the
    content. MIRROR of rk-text-key (form-stdlib/rag-key.fk → 7 four-way): adler32 over
    the bytes, as a decimal string. zlib.adler32 IS the algorithm the Form recipe
    canonically implements (the recipe's band proves the RFC vectors); the kernel is
    the proof, this is the bootstrap mirror. ASCII-exact with the Form file key."""
    try:
        return str(zlib.adler32(open(path, "rb").read()) & 0xFFFFFFFF)
    except Exception:
        return ""


def _defn_names(txt: str) -> list[str]:
    out = []
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("(defn ") or s.startswith("(define "):
            tok = s.split("(", 2)[-1].split()
            if len(tok) >= 2:
                out.append(tok[1].rstrip(")"))
        elif s.startswith("#") or s.startswith("##"):   # markdown headings
            out.append(s.lstrip("# ").strip())
    return out


def _snippet(path: str) -> str:
    """Embed by structural unit, not an arbitrary line count: the purpose-line plus the
    cell's signature (defn names / section headings) plus the head. This lands retrieval
    on what a file IS, not on a truncated prefix."""
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    lines = [l for l in txt.splitlines() if l.strip()]
    head = "\n".join(lines[:30])
    sig = _defn_names(txt)
    sig_line = ("\nsignature: " + " ".join(sig[:40])) if sig else ""
    return (head + sig_line)[:2000]


LOCAL_DOC_EXTS = (".md", ".txt", ".org", ".rst", ".py", ".ts", ".tsx", ".js",
                  ".go", ".rs", ".fk", ".form", ".json", ".yaml", ".yml", ".sh", ".html")


def _local_doc_paths(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for fn in sorted(filenames):
            if fn.lower().endswith(LOCAL_DOC_EXTS):
                yield os.path.join(dirpath, fn)


def _body_cells(doc_roots=None):
    """Enumerate the body's current cells as (id, kind, path). id is the repo-relative
    path for body sources, the absolute path for user-pointed local docs."""
    for kind, pat in SOURCES:
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            yield os.path.relpath(path, ROOT), kind, path
    for root in (doc_roots or []):
        root = os.path.abspath(os.path.expanduser(root))
        for path in _local_doc_paths(root):
            yield path, "local", path


def _embed_cell(cell_id: str, kind: str, path: str) -> dict | None:
    sn = _snippet(path)
    if len(sn) < 20:
        return None
    try:
        vec = quantize(embed(sn))
    except Exception:
        return None
    return {"id": cell_id, "kind": kind, "key": content_key(path), "snippet": sn[:600], "vec": vec}


def _load_index(index_path: str) -> list[dict]:
    if not os.path.exists(index_path):
        return []
    return [json.loads(l) for l in open(index_path) if l.strip()]


def _write_index(index_path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w") as out:
        for e in entries:
            out.write(json.dumps(e) + "\n")


def _path_of(cell_id: str, kind: str) -> str:
    return cell_id if kind == "local" else os.path.join(ROOT, cell_id)


def freshness(index_path: str, doc_roots=None):
    """Mirror of rag-freshness.fk over the live body: returns (heal_cells, orphan_ids).
    heal_cells = body cells missing from the index or whose key drifted.
    orphan_ids = index ids whose source is gone."""
    body = list(_body_cells(doc_roots))
    body_keys = {cid: content_key(p) for cid, _k, p in body}
    index = _load_index(index_path)
    idx_keys = {e["id"]: e.get("key", "") for e in index}

    heal = [(cid, kind, path) for cid, kind, path in body
            if idx_keys.get(cid, "") != body_keys[cid]]

    orphans = []
    for e in index:
        cid, kind = e["id"], e.get("kind", "")
        if cid in body_keys:
            continue
        if kind == "local":
            if not os.path.exists(cid):     # a pointed-at local doc that vanished
                orphans.append(cid)
        else:                               # a body source that was removed/renamed
            orphans.append(cid)
    return heal, orphans


def heal(index_path: str, doc_roots=None, verbose=True) -> tuple[int, int]:
    """Self-heal the cache, git-like: embed only the drifted/missing delta, compost
    orphans, keep everything fresh untouched. A full embed runs only when absent."""
    heal_cells, orphan_ids = freshness(index_path, doc_roots)
    if not heal_cells and not orphan_ids:
        return 0, 0
    index = _load_index(index_path)
    by_id = {e["id"]: e for e in index if e["id"] not in orphan_ids}
    healed = 0
    for cid, kind, path in heal_cells:
        e = _embed_cell(cid, kind, path)
        if e is not None:
            by_id[cid] = e
            healed += 1
            if verbose and healed % 100 == 0:
                print(f"  ...{healed} cells healed", flush=True)
    _write_index(index_path, list(by_id.values()))
    if verbose:
        print(f"[rag heal: +{healed} re-embedded, -{len(orphan_ids)} composted -> {index_path}]")
    return healed, len(orphan_ids)


def build(index_path: str, doc_roots=None) -> None:
    """Full embed over the whole body — used when the index is absent or being reset.
    The steady-state path is heal(); this is the cold start."""
    entries = []
    n = 0
    for cid, kind, path in _body_cells(doc_roots):
        e = _embed_cell(cid, kind, path)
        if e is not None:
            entries.append(e)
            n += 1
            if n % 100 == 0:
                print(f"  ...{n} cells embedded", flush=True)
    _write_index(index_path, entries)
    print(f"[rag index built: {n} cells -> {index_path}]")


def _ensure_fresh(index_path: str, doc_roots=None) -> None:
    """Lazy heal before serving: if the index is absent, cold-build; otherwise heal the
    delta. Cheap when fresh (hash the body, find nothing to do)."""
    if not os.path.exists(index_path):
        build(index_path, doc_roots)
    else:
        heal(index_path, doc_roots, verbose=False)


def retrieve(query: str, index_path: str, k: int | None) -> list[dict]:
    q = quantize(embed(query))
    entries = _load_index(index_path)
    ranked = sorted(entries, key=lambda e: rag_l1(q, e["vec"]))  # ties keep first (stable sort)
    if k is None:                                                # adaptive: cut at the knee
        ds = [rag_l1(q, e["vec"]) for e in ranked]
        k = rak_k(ds, K_MIN, K_MAX)
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
    h = sub.add_parser("heal"); h.add_argument("--index", default=INDEX)
    h.add_argument("--docs", action="append", default=[])
    f = sub.add_parser("fresh"); f.add_argument("--index", default=INDEX)
    s = sub.add_parser("search"); s.add_argument("question")
    s.add_argument("-k", type=int, default=0); s.add_argument("--index", default=INDEX)
    s.add_argument("--no-heal", action="store_true")
    c = sub.add_parser("context"); c.add_argument("question")
    c.add_argument("-k", type=int, default=3); c.add_argument("--index", default=INDEX)
    c.add_argument("--no-heal", action="store_true")
    a = sub.add_parser("ask"); a.add_argument("question")
    a.add_argument("-k", type=int, default=0); a.add_argument("-m", "--model", default="qwen2.5:72b")
    a.add_argument("--index", default=INDEX); a.add_argument("--no-heal", action="store_true")
    args = ap.parse_args()

    if args.cmd == "build":
        build(args.index, args.docs); return 0
    if args.cmd == "heal":
        heal(args.index, args.docs); return 0
    if args.cmd == "fresh":
        heal_cells, orphans = freshness(args.index)
        total = len(_load_index(args.index))
        if not heal_cells and not orphans:
            print(f"[rag fresh: {total} cells, cache == body]")
        else:
            print(f"[rag drift: {len(heal_cells)} to heal, {len(orphans)} orphaned, {total} cached]")
            for cid, kind, _p in heal_cells[:20]:
                print(f"  ~ {cid} ({kind})")
        return 0

    # serving paths heal lazily unless asked not to (k=0 means adaptive)
    k = None if getattr(args, "k", 0) in (0, None) else args.k
    if not getattr(args, "no_heal", False):
        _ensure_fresh(args.index)

    if args.cmd == "search":
        for h in retrieve(args.question, args.index, k):
            print(f"{h['id']}\t{h['kind']}")
        return 0
    if args.cmd == "context":
        for h in retrieve(args.question, args.index, k or 3):
            print(f"[{h['id']}] {' '.join(h['snippet'].split())[:280]}")
        return 0

    hits = retrieve(args.question, args.index, k)
    print("── retrieved (Form-ranked: rag-retrieve.fk, knee-cut: rag-adaptive-k.fk) ──")
    for h in hits:
        print(f"  · {h['id']}  ({h['kind']})")
    print("\n── grounded answer (local oracle, no network) ──")
    print(ground(args.question, hits, args.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
