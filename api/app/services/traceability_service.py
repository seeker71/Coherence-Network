# spec: 181-full-code-traceability
# idea: full-traceability-chain
"""Traceability service: report generation and backfill orchestration (Spec 181, idea full-traceability-chain)."""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.tracing import scan_all_modules_for_traced_functions
from app.models.traceability import (
    BackfillResponse,
    FunctionCoverage,
    FunctionListResponse,
    LineageFile,
    LineageResponse,
    LineageSpec,
    SpecForwardTrace,
    TracedFunction,
    TraceabilityGap,
    TraceabilityReport,
    TraceabilitySummary,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_DIR = REPO_ROOT / "cli"
SPECS_DIR = REPO_ROOT / "specs"
API_DIR = REPO_ROOT / "api" / "app"
WEB_DIR = REPO_ROOT / "web" / "app"

# In-memory backfill job state
_backfill_lock = threading.Lock()
_backfill_job: dict[str, Any] | None = None

# ---- Spec file scanning -------------------------------------------------------

_IDEA_ID_PATTERNS = [
    re.compile(r"idea[_-]id:\s*[\"']?([a-z0-9][a-z0-9-]{2,})[\"']?", re.IGNORECASE),
    re.compile(r"parent_idea[_-]id:\s*[\"']?([a-z0-9][a-z0-9-]{2,})[\"']?", re.IGNORECASE),
    re.compile(r"\*\*idea_id\*\*:\s*`([a-z0-9][a-z0-9-]{2,})`", re.IGNORECASE),
    re.compile(r"idea `([a-z0-9][a-z0-9-]{2,})`"),
]

_SPEC_REF_PATTERNS = [
    re.compile(r"#\s*spec:\s*(\S+)", re.IGNORECASE),
    re.compile(r"#\s*Implements:\s*spec[_-]?(\S+)", re.IGNORECASE),
    re.compile(r"//\s*spec:\s*(\S+)", re.IGNORECASE),
    re.compile(r"Spec\s+(\d{2,3})\b"),
]

_NOISE_IDEA_IDS = frozenset({
    "none", "null", "n/a", "string", "object", "array", "number",
    "boolean", "integer", "required", "type", "slug", "id",
})


def _spec_file_has_idea_id(content: str) -> bool:
    for pattern in _IDEA_ID_PATTERNS:
        m = pattern.search(content)
        if m:
            val = m.group(1).lower().strip("\"'").rstrip(".,;)")
            if val not in _NOISE_IDEA_IDS and len(val) >= 3:
                return True
    return False


def _extract_idea_id_from_spec(content: str) -> str | None:
    for pattern in _IDEA_ID_PATTERNS:
        m = pattern.search(content)
        if m:
            val = m.group(1).lower().strip("\"'").rstrip(".,;)")
            if val not in _NOISE_IDEA_IDS and len(val) >= 3:
                return val
    return None


def _code_file_has_spec_ref(content: str) -> bool:
    for pattern in _SPEC_REF_PATTERNS:
        if pattern.search(content):
            return True
    return False


def _count_source_files() -> tuple[int, int]:
    """Return (total, with_spec_ref) for .py/.ts/.tsx files."""
    total = 0
    with_ref = 0
    for ext in ("*.py", "*.mjs", "*.ts", "*.tsx"):
        for base in (API_DIR, WEB_DIR, CLI_DIR):
            if not base.exists():
                continue
            for f in base.rglob(ext):
                if "__pycache__" in str(f) or "node_modules" in str(f):
                    continue
                total += 1
                try:
                    content = f.read_text(errors="replace")
                    if _code_file_has_spec_ref(content):
                        with_ref += 1
                except OSError:
                    pass
    return total, with_ref


def _count_spec_files() -> tuple[int, int, list[TraceabilityGap]]:
    """Return (total, with_idea_id, gaps) for spec files."""
    gaps: list[TraceabilityGap] = []
    total = 0
    with_idea = 0
    for f in SPECS_DIR.glob("*.md"):
        if f.name == "TEMPLATE.md":
            continue
        total += 1
        try:
            content = f.read_text(errors="replace")
        except OSError:
            continue
        if _spec_file_has_idea_id(content):
            with_idea += 1
        else:
            gaps.append(
                TraceabilityGap(
                    type="spec_no_idea",
                    spec_file=f.name,
                    spec_id=f.stem,
                    severity="high",
                )
            )
    return total, with_idea, gaps


def _count_source_gaps() -> list[TraceabilityGap]:
    gaps: list[TraceabilityGap] = []
    for ext in ("*.py",):
        for f in API_DIR.rglob(ext):
            if "__pycache__" in str(f):
                continue
            if f.name.startswith("test_") or f.name in ("__init__.py", "conftest.py"):
                continue
            if not any(d in f.parts for d in ("routers", "services")):
                continue
            try:
                content = f.read_text(errors="replace")
            except OSError:
                continue
            if not _code_file_has_spec_ref(content):
                gaps.append(
                    TraceabilityGap(
                        type="file_no_spec",
                        source_file=str(f.relative_to(REPO_ROOT)),
                        severity="medium",
                    )
                )
    return gaps


# ---- Public service functions -----------------------------------------------


def build_traceability_report() -> TraceabilityReport:
    """Build a full traceability report across all dimensions."""
    spec_total, spec_with_idea, spec_gaps = _count_spec_files()
    src_total, src_with_ref = _count_source_files()
    src_gaps = _count_source_gaps()

    traced_fns = scan_all_modules_for_traced_functions()
    functions_traced = len(traced_fns)
    # Estimate total public functions by counting def lines in key dirs
    functions_total = _estimate_public_functions()

    spec_pct = round(spec_with_idea * 100.0 / max(spec_total, 1), 1)
    src_pct = round(src_with_ref * 100.0 / max(src_total, 1), 1)
    fn_pct = round(functions_traced * 100.0 / max(functions_total, 1), 1)

    # DB stats: try to query, fall back to zeros
    db_total, db_with_idea = _query_db_spec_stats()
    db_pct = round(db_with_idea * 100.0 / max(db_total, 1), 1)

    overall = round((spec_pct + src_pct + fn_pct + db_pct) / 4.0, 1)

    summary = TraceabilitySummary(
        spec_files_total=spec_total,
        spec_files_with_idea_id=spec_with_idea,
        spec_files_coverage_pct=spec_pct,
        db_specs_total=db_total,
        db_specs_with_idea_id=db_with_idea,
        db_specs_coverage_pct=db_pct,
        source_files_total=src_total,
        source_files_with_spec_ref=src_with_ref,
        source_files_coverage_pct=src_pct,
        functions_traced=functions_traced,
        functions_total=functions_total,
        function_coverage_pct=fn_pct,
        overall_traceability_pct=overall,
    )

    all_gaps = spec_gaps + src_gaps
    try:
        from app.services import traceability_links_service as tls

        persisted = tls.list_links(limit=200)
        link_count = tls.count_links()
    except Exception:
        persisted = []
        link_count = 0

    links: list[dict[str, Any]] = [
        {
            "spec_file": g.spec_file,
            "spec_id": g.spec_id,
            "idea_id": None,
            "gap": True,
        }
        for g in spec_gaps[:50]
    ]
    for row in persisted:
        links.append({**row, "gap": False, "persisted": True})

    return TraceabilityReport(
        summary=summary,
        gaps=all_gaps[:100],
        links=links,
        persisted_implementation_links=link_count,
    )


def _estimate_public_functions() -> int:
    """Count non-private function definitions in routers and services."""
    count = 0
    for d in (API_DIR / "routers", API_DIR / "services"):
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(errors="replace")
                # Count async def and def that are not _private
                count += len(re.findall(r"^\s{0,4}(?:async )?def (?!_)\w+", content, re.MULTILINE))
            except OSError:
                pass
    return max(count, 1)


def _query_db_spec_stats() -> tuple[int, int]:
    """Query spec_registry_entries for idea_id coverage (unified DB)."""
    try:
        from sqlalchemy import func

        from app.services import spec_registry_service as srs
        from app.services.spec_registry_service import SpecRegistryRecord

        srs.ensure_schema()
        from app.services import unified_db as udb

        with udb.session() as session:
            total = int(session.query(func.count(SpecRegistryRecord.spec_id)).scalar() or 0)
            with_idea = int(
                session.query(func.count(SpecRegistryRecord.spec_id))
                .filter(
                    SpecRegistryRecord.idea_id.isnot(None),
                    SpecRegistryRecord.idea_id != "",
                )
                .scalar()
                or 0
            )
        return total, with_idea
    except Exception:
        return 0, 0


def get_function_list(spec_id: str | None = None, idea_id: str | None = None) -> FunctionListResponse:
    """Return @spec_traced function list, optionally filtered."""
    all_traces = scan_all_modules_for_traced_functions()

    if spec_id:
        all_traces = [t for t in all_traces if t.get("spec_id") == spec_id]
    if idea_id:
        all_traces = [t for t in all_traces if t.get("idea_id") == idea_id]

    functions = [
        TracedFunction(
            module=t.get("module", ""),
            function=t.get("function", ""),
            spec_id=t.get("spec_id"),
            idea_id=t.get("idea_id"),
            file=t.get("file"),
            line=t.get("line"),
            description=t.get("description"),
        )
        for t in all_traces
    ]

    total_public = _estimate_public_functions()
    pct = round(len(functions) * 100.0 / max(total_public, 1), 1)
    coverage = FunctionCoverage(traced=len(functions), total_public=total_public, pct=pct)
    return FunctionListResponse(functions=functions, coverage=coverage)


def get_lineage(idea_id: str) -> LineageResponse | None:
    """Build lineage chain: idea → specs → files → functions."""
    # Get idea from API or DB
    idea_title = _get_idea_title(idea_id)
    if idea_title is None:
        # Try spec files as fallback — maybe we know it from specs
        if not _idea_referenced_in_specs(idea_id):
            return None

    specs_for_idea = _find_specs_for_idea(idea_id)
    all_traces = scan_all_modules_for_traced_functions()

    lineage_specs = []
    for spec in specs_for_idea:
        spec_traces = [t for t in all_traces if t.get("spec_id") == spec["spec_id"]]
        files_map: dict[str, list[str]] = {}
        for t in spec_traces:
            f = t.get("file") or ""
            if f:
                # Normalize to relative path
                try:
                    f = str(Path(f).relative_to(REPO_ROOT))
                except ValueError:
                    pass
            files_map.setdefault(f, []).append(t.get("function", ""))

        files = [LineageFile(path=p, functions=fns) for p, fns in files_map.items()]
        lineage_specs.append(
            LineageSpec(
                spec_id=spec["spec_id"],
                spec_title=spec.get("title"),
                files=files,
            )
        )

    return LineageResponse(
        idea_id=idea_id,
        idea_title=idea_title,
        specs=lineage_specs,
    )


def _get_idea_title(idea_id: str) -> str | None:
    """Lookup idea title from portfolio service."""
    try:
        from app.services.idea_service import get_idea

        idea = get_idea(idea_id)
        return idea.name if idea else None
    except Exception:
        return None


def _idea_referenced_in_specs(idea_id: str) -> bool:
    """Check if idea_id appears in any spec file."""
    pattern = re.compile(re.escape(idea_id), re.IGNORECASE)
    for f in SPECS_DIR.glob("*.md"):
        try:
            if pattern.search(f.read_text(errors="replace")):
                return True
        except OSError:
            pass
    return False


def _find_specs_for_idea(idea_id: str) -> list[dict[str, Any]]:
    """Find spec files that reference a given idea_id."""
    results = []
    pattern = re.compile(re.escape(idea_id), re.IGNORECASE)
    for f in sorted(SPECS_DIR.glob("*.md")):
        if f.name == "TEMPLATE.md":
            continue
        try:
            content = f.read_text(errors="replace")
        except OSError:
            continue
        extracted = _extract_idea_id_from_spec(content)
        if extracted and extracted.lower() == idea_id.lower():
            title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            results.append({
                "spec_id": f.stem,
                "title": title_m.group(1).strip()[:80] if title_m else f.stem,
            })
        elif pattern.search(content):
            title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            results.append({
                "spec_id": f.stem,
                "title": title_m.group(1).strip()[:80] if title_m else f.stem,
            })
    return results


def get_spec_forward_trace(spec_id: str) -> SpecForwardTrace | None:
    """Return all files and functions that implement a given spec."""
    spec_file = None
    for f in SPECS_DIR.glob(f"{spec_id}*.md"):
        spec_file = f
        break
    if not spec_file:
        # Try numeric match
        m = re.match(r"^(\d+)", spec_id)
        if m:
            for f in SPECS_DIR.glob(f"{m.group(1)}-*.md"):
                spec_file = f
                break

    if not spec_file:
        return None

    content = spec_file.read_text(errors="replace")
    title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else spec_file.stem
    idea_id = _extract_idea_id_from_spec(content)

    all_traces = scan_all_modules_for_traced_functions()
    spec_traces = [t for t in all_traces if t.get("spec_id") == spec_id or t.get("spec_id") == spec_file.stem]

    files: list[str] = []
    functions: list[dict[str, Any]] = []
    seen_files: set[str] = set()

    for t in spec_traces:
        f = t.get("file") or ""
        if f:
            try:
                f = str(Path(f).relative_to(REPO_ROOT))
            except ValueError:
                pass
        if f and f not in seen_files:
            seen_files.add(f)
            files.append(f)
        functions.append({
            "file": f,
            "function": t.get("function", ""),
            "line": t.get("line"),
        })

    # Also scan code files for static comments
    static_files = _scan_static_spec_refs(spec_file.stem, spec_id)
    for sf in static_files:
        if sf not in seen_files:
            seen_files.add(sf)
            files.append(sf)

    return SpecForwardTrace(
        spec_id=spec_file.stem,
        spec_title=title,
        idea_id=idea_id,
        files=files,
        functions=functions,
        prs=[],
    )


def _scan_static_spec_refs(spec_stem: str, spec_id: str) -> list[str]:
    """Find code files that reference a spec via static comments."""
    results = []
    patterns = [
        re.compile(r"spec:\s*" + re.escape(spec_stem), re.IGNORECASE),
        re.compile(r"spec:\s*" + re.escape(spec_id), re.IGNORECASE),
        re.compile(r"Spec\s+" + re.escape(spec_stem.split("-")[0].lstrip("0") or "0"), re.IGNORECASE),
    ]
    for base in (API_DIR, WEB_DIR):
        if not base.exists():
            continue
        for ext in ("*.py", "*.ts", "*.tsx"):
            for f in base.rglob(ext):
                if "__pycache__" in str(f) or "node_modules" in str(f):
                    continue
                try:
                    content = f.read_text(errors="replace")
                    if any(p.search(content) for p in patterns):
                        rel = str(f.relative_to(REPO_ROOT))
                        results.append(rel)
                except OSError:
                    pass
    return results


# ---- Backfill orchestration --------------------------------------------------


def start_backfill_job(dry_run: bool = False) -> BackfillResponse:
    """Start a background backfill job. Returns 409 info if already running."""
    global _backfill_job

    with _backfill_lock:
        if _backfill_job and _backfill_job.get("status") == "running":
            raise ValueError("Backfill job already running")

        job_id = f"backfill-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        _backfill_job = {
            "job_id": job_id,
            "status": "running",
            "dry_run": dry_run,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
        }

    thread = threading.Thread(target=_run_backfill, args=(job_id, dry_run), daemon=True)
    thread.start()

    return BackfillResponse(
        job_id=job_id,
        status="queued",
        dry_run=dry_run,
        queued_at=datetime.now(timezone.utc),
    )


def get_backfill_status() -> dict[str, Any] | None:
    return dict(_backfill_job) if _backfill_job else None


def _run_backfill(job_id: str, dry_run: bool) -> None:
    """Background thread: run all three backfill phases."""
    global _backfill_job
    results: dict[str, Any] = {}

    try:
        results["spec_idea"] = _backfill_spec_idea_links(dry_run)
        results["db_registry_idea"] = _backfill_db_registry_idea_ids(dry_run)
        results["code_spec"] = _backfill_code_spec_links(dry_run)
    except Exception as exc:
        results["error"] = str(exc)
    finally:
        with _backfill_lock:
            if _backfill_job and _backfill_job.get("job_id") == job_id:
                _backfill_job["status"] = "completed" if "error" not in results else "failed"
                _backfill_job["result"] = results
                _backfill_job["finished_at"] = datetime.now(timezone.utc).isoformat()


def _backfill_spec_idea_links(dry_run: bool) -> dict[str, Any]:
    """Phase 1.1: scan spec files and extract idea_id, write to frontmatter if missing."""
    updated = 0
    skipped = 0
    flagged = 0

    for spec_file in sorted(SPECS_DIR.glob("*.md")):
        if spec_file.name == "TEMPLATE.md":
            continue
        try:
            content = spec_file.read_text(errors="replace")
        except OSError:
            continue

        if _spec_file_has_idea_id(content):
            skipped += 1
            continue

        # Try to extract from body
        idea_id = _extract_idea_id_from_spec(content)
        if idea_id:
            if not dry_run:
                _inject_idea_id_into_spec(spec_file, content, idea_id)
            updated += 1
        else:
            flagged += 1

    return {"updated": updated, "skipped": skipped, "needs_review": flagged, "dry_run": dry_run}


def _inject_idea_id_into_spec(spec_file: Path, content: str, idea_id: str) -> None:
    """Add idea_id to spec frontmatter if not already present."""
    # If there's already a --- frontmatter block, add inside it
    fm_pattern = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
    m = fm_pattern.match(content)
    if m:
        if "idea_id" not in m.group(1):
            new_content = content[: m.start(1)] + m.group(1) + f"\nidea_id: {idea_id}" + content[m.end(1) :]
            spec_file.write_text(new_content, encoding="utf-8")
    else:
        # Prepend frontmatter
        new_content = f"---\nidea_id: {idea_id}\n---\n\n" + content
        spec_file.write_text(new_content, encoding="utf-8")


def _extract_idea_id_from_code_header(content: str) -> str | None:
    """Match `# idea: slug` or `// idea: slug` in the first block of comments."""
    head = "\n".join(content.splitlines()[:60])
    for pat in (
        re.compile(r"^#\s*idea:\s*(\S+)", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^//\s*idea:\s*(\S+)", re.MULTILINE | re.IGNORECASE),
    ):
        m = pat.search(head)
        if m:
            val = m.group(1).strip().strip("`'\"")
            if val.lower() not in _NOISE_IDEA_IDS and len(val) >= 3:
                return val
    return None


def _collect_static_spec_links() -> list[dict[str, Any]]:
    """Scan api/, web/, cli/ for spec reference comments."""
    links: list[dict[str, Any]] = []
    for ext in ("*.py", "*.ts", "*.tsx", "*.mjs"):
        for base in (API_DIR, WEB_DIR, CLI_DIR):
            if not base.exists():
                continue
            for f in base.rglob(ext):
                if "__pycache__" in str(f) or "node_modules" in str(f):
                    continue
                try:
                    content = f.read_text(errors="replace")
                except OSError:
                    continue
                idea_hint = _extract_idea_id_from_code_header(content)
                for pattern in _SPEC_REF_PATTERNS:
                    for m in pattern.finditer(content):
                        spec_ref = (m.group(1) or "").strip().rstrip(".,;)`'\"")
                        if not spec_ref:
                            continue
                        line_num = content[: m.start()].count("\n") + 1
                        links.append({
                            "source_file": str(f.relative_to(REPO_ROOT)),
                            "spec_id": spec_ref,
                            "line_number": line_num,
                            "confidence": 1.0,
                            "link_type": "static_comment",
                            "idea_id": idea_hint,
                        })
    return links


def _backfill_db_registry_idea_ids(dry_run: bool) -> dict[str, Any]:
    """Set idea_id on spec_registry_entries when content_path points to a spec file with idea metadata."""
    from app.services import spec_registry_service as srs
    from app.services.spec_registry_service import SpecRegistryRecord

    srs.ensure_schema()
    from app.services import unified_db as udb

    updated = 0
    skipped = 0
    with udb.session() as session:
        rows = (
            session.query(SpecRegistryRecord)
            .filter(
                (SpecRegistryRecord.idea_id.is_(None)) | (SpecRegistryRecord.idea_id == ""),
            )
            .all()
        )
        for row in rows:
            path: Path | None = None
            if row.content_path:
                cand = REPO_ROOT / str(row.content_path)
                if cand.is_file():
                    path = cand
            if path is None:
                skipped += 1
                continue
            try:
                text = path.read_text(errors="replace")
            except OSError:
                skipped += 1
                continue
            idea_id = _extract_idea_id_from_spec(text)
            if not idea_id:
                skipped += 1
                continue
            if dry_run:
                updated += 1
            else:
                row.idea_id = idea_id
                row.updated_at = datetime.now(timezone.utc)
                session.add(row)
                updated += 1
        if not dry_run:
            session.commit()
    return {"updated": updated, "skipped": skipped, "dry_run": dry_run}


def _backfill_code_spec_links(dry_run: bool) -> dict[str, Any]:
    """Phase 1.3: scan code files for spec references; persist to traceability_implementation_links."""
    links = _collect_static_spec_links()
    persisted = 0
    if not dry_run:
        from app.services import traceability_links_service as tls

        persisted = tls.replace_all_links(links)
    return {
        "links_found": len(links),
        "persisted_rows": persisted,
        "dry_run": dry_run,
        "sample": links[:5],
    }


if __name__ == "__main__":
    _rep = build_traceability_report()
    print("persisted_implementation_links", _rep.persisted_implementation_links)
    print("overall_traceability_pct", _rep.summary.overall_traceability_pct)
