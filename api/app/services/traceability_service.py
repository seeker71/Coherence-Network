# spec: 181-full-code-traceability
# idea: full-code-traceability
"""Traceability service: report generation and backfill orchestration (Spec 181)."""

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
SPECS_DIR = REPO_ROOT / "specs"
API_DIR = REPO_ROOT / "api" / "app"
WEB_DIR = REPO_ROOT / "web" / "app"

_backfill_lock = threading.Lock()
_backfill_job: dict[str, Any] | None = None

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
    for p in _IDEA_ID_PATTERNS:
        m = p.search(content)
        if m:
            val = m.group(1).lower().strip("\"'").rstrip(".,;)")
            if val not in _NOISE_IDEA_IDS and len(val) >= 3:
                return True
    return False


def _extract_idea_id_from_spec(content: str) -> str | None:
    for p in _IDEA_ID_PATTERNS:
        m = p.search(content)
        if m:
            val = m.group(1).lower().strip("\"'").rstrip(".,;)")
            if val not in _NOISE_IDEA_IDS and len(val) >= 3:
                return val
    return None


def _code_file_has_spec_ref(content: str) -> bool:
    return any(p.search(content) for p in _SPEC_REF_PATTERNS)


def _count_spec_files() -> tuple[int, int, list[TraceabilityGap]]:
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
            gaps.append(TraceabilityGap(type="spec_no_idea", spec_file=f.name, spec_id=f.stem, severity="high"))
    return total, with_idea, gaps


def _count_source_files() -> tuple[int, int]:
    total = 0
    with_ref = 0
    for ext in ("*.py", "*.ts", "*.tsx"):
        for base in (API_DIR, WEB_DIR):
            if not base.exists():
                continue
            for f in base.rglob(ext):
                if "__pycache__" in str(f) or "node_modules" in str(f):
                    continue
                total += 1
                try:
                    if _code_file_has_spec_ref(f.read_text(errors="replace")):
                        with_ref += 1
                except OSError:
                    pass
    return total, with_ref


def _query_db_spec_stats() -> tuple[int, int]:
    try:
        from app.db import get_db_session  # type: ignore[import]
        from sqlalchemy import text
        with get_db_session() as db:
            total = db.execute(text("SELECT COUNT(*) FROM specs")).scalar()
            with_idea = db.execute(
                text("SELECT COUNT(*) FROM specs WHERE idea_id IS NOT NULL AND idea_id != ''")
            ).scalar()
            return int(total or 0), int(with_idea or 0)
    except Exception:
        return 0, 0


def _estimate_public_functions() -> int:
    count = 0
    for d in (API_DIR / "routers", API_DIR / "services"):
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                count += len(re.findall(
                    r"^\s{0,4}(?:async )?def (?!_)\w+",
                    f.read_text(errors="replace"),
                    re.MULTILINE,
                ))
            except OSError:
                pass
    return max(count, 1)


def build_traceability_report() -> TraceabilityReport:
    """Build a full traceability report across all dimensions."""
    spec_total, spec_with_idea, spec_gaps = _count_spec_files()
    src_total, src_with_ref = _count_source_files()
    traced_fns = scan_all_modules_for_traced_functions()
    functions_total = _estimate_public_functions()

    spec_pct = round(spec_with_idea * 100.0 / max(spec_total, 1), 1)
    src_pct = round(src_with_ref * 100.0 / max(src_total, 1), 1)
    fn_pct = round(len(traced_fns) * 100.0 / max(functions_total, 1), 1)
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
        functions_traced=len(traced_fns),
        functions_total=functions_total,
        function_coverage_pct=fn_pct,
        overall_traceability_pct=overall,
    )
    links = [
        {"spec_file": g.spec_file, "spec_id": g.spec_id, "idea_id": None, "gap": True}
        for g in spec_gaps[:50]
    ]
    return TraceabilityReport(summary=summary, gaps=spec_gaps[:100], links=links)


def get_function_list(
    spec_id: str | None = None,
    idea_id: str | None = None,
) -> FunctionListResponse:
    """Return @spec_traced function list, optionally filtered."""
    traces = scan_all_modules_for_traced_functions()
    if spec_id:
        traces = [t for t in traces if t.get("spec_id") == spec_id]
    if idea_id:
        traces = [t for t in traces if t.get("idea_id") == idea_id]
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
        for t in traces
    ]
    total_public = _estimate_public_functions()
    pct = round(len(functions) * 100.0 / max(total_public, 1), 1)
    return FunctionListResponse(
        functions=functions,
        coverage=FunctionCoverage(traced=len(functions), total_public=total_public, pct=pct),
    )


def _get_idea_title(idea_id: str) -> str | None:
    try:
        from app.db import get_db_session  # type: ignore[import]
        from sqlalchemy import text
        with get_db_session() as db:
            row = db.execute(
                text("SELECT name FROM ideas WHERE id = :id OR slug = :id OR name = :id"),
                {"id": idea_id},
            ).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def _idea_referenced_in_specs(idea_id: str) -> bool:
    pattern = re.compile(re.escape(idea_id), re.IGNORECASE)
    for f in SPECS_DIR.glob("*.md"):
        try:
            if pattern.search(f.read_text(errors="replace")):
                return True
        except OSError:
            pass
    return False


def _find_specs_for_idea(idea_id: str) -> list[dict[str, Any]]:
    results = []
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
                "title": (title_m.group(1).strip()[:80] if title_m else f.stem),
            })
    return results


def get_lineage(idea_id: str) -> LineageResponse | None:
    """Build lineage chain: idea to specs to files to functions."""
    idea_title = _get_idea_title(idea_id)
    if idea_title is None and not _idea_referenced_in_specs(idea_id):
        return None
    specs_for_idea = _find_specs_for_idea(idea_id)
    all_traces = scan_all_modules_for_traced_functions()
    lineage_specs = []
    for spec in specs_for_idea:
        spec_traces = [t for t in all_traces if t.get("spec_id") == spec["spec_id"]]
        files_map: dict[str, list[str]] = {}
        for t in spec_traces:
            f = t.get("file") or ""
            try:
                f = str(Path(f).relative_to(REPO_ROOT))
            except ValueError:
                pass
            files_map.setdefault(f, []).append(t.get("function", ""))
        lineage_specs.append(LineageSpec(
            spec_id=spec["spec_id"],
            spec_title=spec.get("title"),
            files=[LineageFile(path=p, functions=fns) for p, fns in files_map.items()],
        ))
    return LineageResponse(idea_id=idea_id, idea_title=idea_title, specs=lineage_specs)


def get_spec_forward_trace(spec_id: str) -> SpecForwardTrace | None:
    """Return all files and functions that implement a given spec."""
    spec_file = None
    for f in SPECS_DIR.glob(f"{spec_id}*.md"):
        spec_file = f
        break
    if not spec_file:
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
    spec_traces = [t for t in all_traces if t.get("spec_id") in (spec_id, spec_file.stem)]

    files: list[str] = []
    functions: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    for t in spec_traces:
        f = t.get("file") or ""
        try:
            f = str(Path(f).relative_to(REPO_ROOT))
        except ValueError:
            pass
        if f and f not in seen_files:
            seen_files.add(f)
            files.append(f)
        functions.append({"file": f, "function": t.get("function", ""), "line": t.get("line")})

    # Also scan static comments
    for base in (API_DIR, WEB_DIR):
        if not base.exists():
            continue
        for ext in ("*.py", "*.ts", "*.tsx"):
            for fpath in base.rglob(ext):
                if "__pycache__" in str(fpath) or "node_modules" in str(fpath):
                    continue
                try:
                    fcontent = fpath.read_text(errors="replace")
                except OSError:
                    continue
                if spec_file.stem in fcontent or spec_id in fcontent:
                    try:
                        rel = str(fpath.relative_to(REPO_ROOT))
                    except ValueError:
                        rel = str(fpath)
                    if rel not in seen_files:
                        seen_files.add(rel)
                        files.append(rel)

    return SpecForwardTrace(
        spec_id=spec_file.stem,
        spec_title=title,
        idea_id=idea_id,
        files=files,
        functions=functions,
        prs=[],
    )


def start_backfill_job(dry_run: bool = False) -> BackfillResponse:
    """Start a background backfill job. Raises ValueError if already running."""
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
    threading.Thread(target=_run_backfill, args=(job_id, dry_run), daemon=True).start()
    return BackfillResponse(
        job_id=job_id, status="queued", dry_run=dry_run, queued_at=datetime.now(timezone.utc)
    )


def get_backfill_status() -> dict[str, Any] | None:
    return dict(_backfill_job) if _backfill_job else None


def _run_backfill(job_id: str, dry_run: bool) -> None:
    global _backfill_job
    results: dict[str, Any] = {}
    try:
        updated = skipped = flagged = 0
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
            idea_id = _extract_idea_id_from_spec(content)
            if idea_id and not dry_run:
                fm_m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if fm_m and "idea_id" not in fm_m.group(1):
                    new_content = "---\n" + fm_m.group(1) + "\nidea_id: " + idea_id + "\n---" + content[fm_m.end():]
                    spec_file.write_text(new_content, encoding="utf-8")
                elif not fm_m:
                    spec_file.write_text("---\nidea_id: " + idea_id + "\n---\n\n" + content, encoding="utf-8")
                updated += 1
            elif idea_id:
                updated += 1
            else:
                flagged += 1
        results["spec_idea"] = {"updated": updated, "skipped": skipped, "needs_review": flagged}

        links = []
        for fpath in API_DIR.rglob("*.py"):
            if "__pycache__" in str(fpath):
                continue
            try:
                fcontent = fpath.read_text(errors="replace")
            except OSError:
                continue
            for p in _SPEC_REF_PATTERNS:
                for m in p.finditer(fcontent):
                    line_num = fcontent[: m.start()].count("\n") + 1
                    links.append({
                        "source_file": str(fpath.relative_to(REPO_ROOT)),
                        "spec_id": m.group(1),
                        "line_number": line_num,
                    })
        results["code_spec"] = {"links_found": len(links)}
    except Exception as exc:
        results["error"] = str(exc)
    finally:
        with _backfill_lock:
            if _backfill_job and _backfill_job.get("job_id") == job_id:
                _backfill_job["status"] = "completed" if "error" not in results else "failed"
                _backfill_job["result"] = results
                _backfill_job["finished_at"] = datetime.now(timezone.utc).isoformat()
