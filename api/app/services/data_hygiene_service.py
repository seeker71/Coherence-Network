"""Data hygiene: row counts, growth snapshots, threshold breaches, friction alerts."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.friction import FrictionEvent
from app.services import friction_service
from app.services.unified_db import Base, engine, session

logger = logging.getLogger(__name__)

_TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class DataHygieneSnapshotRecord(Base):
    __tablename__ = "data_hygiene_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    table_counts_json: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")


class DataHealthUnavailable(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _database_kind(url: str) -> str:
    u = (url or "").lower()
    if "postgres" in u:
        return "postgresql"
    if "sqlite" in u:
        return "sqlite"
    return "unknown"


def _safe_table_name(name: str) -> str:
    if not _TABLE_NAME_RE.match(name):
        raise ValueError(f"invalid table name: {name!r}")
    return name


def list_user_tables(conn) -> list[str]:
    url = str(engine().url)
    if "sqlite" in url.lower():
        rows = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ).fetchall()
        return [str(r[0]) for r in rows]
    rows = conn.execute(
        text(
            "SELECT tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname = 'public' ORDER BY tablename"
        )
    ).fetchall()
    return [str(r[0]) for r in rows]


def count_rows(conn, table: str) -> int:
    t = _safe_table_name(table)
    q = text(f'SELECT COUNT(*) FROM "{t}"')
    row = conn.execute(q).fetchone()
    return int(row[0]) if row else 0


def collect_table_counts() -> dict[str, int]:
    eng = engine()
    counts: dict[str, int] = {}
    with eng.connect() as conn:
        for tbl in list_user_tables(conn):
            try:
                counts[tbl] = count_rows(conn, tbl)
            except Exception as exc:
                logger.warning("count_rows_failed table=%s err=%s", tbl, exc)
    return counts


def _default_thresholds() -> dict[str, dict[str, float | int]]:
    """Soft/hard rules per table; small tables use higher floors via min_rows."""
    return {
        "runtime_events": {
            "min_rows_pct": 500,
            "soft_pct": 20.0,
            "hard_pct": 60.0,
            "soft_abs": 2000,
            "hard_abs": 5000,
            "max_rows_soft": 150000,
            "max_rows_hard": 250000,
        },
        "telemetry_snapshots": {
            "min_rows_pct": 50,
            "soft_pct": 30.0,
            "hard_pct": 80.0,
            "soft_abs": 500,
            "hard_abs": 2000,
            "max_rows_soft": 10000,
            "max_rows_hard": 50000,
        },
        "agent_tasks": {
            "min_rows_pct": 50,
            "soft_pct": 35.0,
            "hard_pct": 90.0,
            "soft_abs": 400,
            "hard_abs": 2000,
            "max_rows_soft": 20000,
            "max_rows_hard": 100000,
        },
        "telemetry_task_metrics": {
            "min_rows_pct": 50,
            "soft_pct": 35.0,
            "hard_pct": 90.0,
            "soft_abs": 400,
            "hard_abs": 2000,
            "max_rows_soft": 20000,
            "max_rows_hard": 100000,
        },
        "measurements": {
            "min_rows_pct": 20,
            "soft_pct": 40.0,
            "hard_pct": 100.0,
            "soft_abs": 200,
            "hard_abs": 800,
            "max_rows_soft": 50000,
            "max_rows_hard": 200000,
        },
        "contribution_ledger": {
            "min_rows_pct": 20,
            "soft_pct": 40.0,
            "hard_pct": 100.0,
            "soft_abs": 200,
            "hard_abs": 800,
            "max_rows_soft": 50000,
            "max_rows_hard": 200000,
        },
    }


def _merge_env_thresholds(base: dict[str, dict[str, float | int]]) -> dict[str, dict[str, float | int]]:
    out = {k: dict(v) for k, v in base.items()}
    raw = os.getenv("DATA_HYGIENE_THRESHOLDS_JSON", "").strip()
    if not raw:
        return out
    try:
        extra = json.loads(raw)
        if isinstance(extra, dict):
            for tbl, rules in extra.items():
                if isinstance(rules, dict) and isinstance(tbl, str):
                    out.setdefault(tbl, {})
                    out[tbl].update({k: v for k, v in rules.items() if isinstance(k, str)})
    except (json.JSONDecodeError, TypeError):
        logger.warning("DATA_HYGIENE_THRESHOLDS_JSON parse failed")
    return out


def _row_status(
    *,
    name: str,
    row_count: int,
    delta_24h: int | None,
    pct_24h: float | None,
    thr: dict[str, float | int],
) -> str:
    max_h = int(thr.get("max_rows_hard") or 10**12)
    max_s = int(thr.get("max_rows_soft") or 10**12)
    if row_count >= max_h:
        return "breach"
    if row_count >= max_s:
        return "warn"
    min_floor = int(thr.get("min_rows_pct") or 100)
    soft_abs = int(thr.get("soft_abs") or 1000)
    hard_abs = int(thr.get("hard_abs") or 5000)
    soft_pct = float(thr.get("soft_pct") or 25.0)
    hard_pct = float(thr.get("hard_pct") or 75.0)
    if delta_24h is None:
        return "ok"
    if row_count < min_floor:
        if delta_24h >= hard_abs:
            return "breach"
        if delta_24h >= soft_abs:
            return "warn"
        return "ok"
    if pct_24h is not None:
        if pct_24h >= hard_pct or delta_24h >= hard_abs:
            return "breach"
        if pct_24h >= soft_pct or delta_24h >= soft_abs:
            return "warn"
    elif delta_24h >= hard_abs:
        return "breach"
    elif delta_24h >= soft_abs:
        return "warn"
    return "ok"


def _snapshot_at_or_before(
    snapshots: list[tuple[datetime, dict[str, int]]], target: datetime
) -> tuple[datetime, dict[str, int]] | None:
    """Pick the newest snapshot with captured_at <= target."""
    eligible = [(ts, c) for ts, c in snapshots if ts <= target]
    if not eligible:
        return None
    eligible.sort(key=lambda x: x[0])
    return eligible[-1]


def load_snapshots_from_db(limit: int = 200) -> list[tuple[str, datetime, dict[str, int], str]]:
    with session() as s:
        rows = (
            s.query(DataHygieneSnapshotRecord)
            .order_by(DataHygieneSnapshotRecord.captured_at.desc())
            .limit(max(1, min(limit, 5000)))
            .all()
        )
    out: list[tuple[str, datetime, dict[str, int], str]] = []
    for r in rows:
        try:
            counts = json.loads(r.table_counts_json)
            if not isinstance(counts, dict):
                continue
            c2 = {str(k): int(v) for k, v in counts.items() if str(k) and isinstance(v, (int, float))}
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        out.append((r.id, r.captured_at, c2, r.source))
    return out


def _find_delta_vs_24h_ago(
    current: dict[str, int], snapshots_chrono: list[tuple[datetime, dict[str, int]]]
) -> dict[str, tuple[int | None, float | None, datetime | None, int | None]]:
    """For each table: delta vs ~24h ago snapshot, pct, ref time, previous count."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    result: dict[str, tuple[int | None, float | None, datetime | None, int | None]] = {}
    for name, cur in current.items():
        ref = _snapshot_at_or_before(snapshots_chrono, cutoff)
        if ref is None:
            result[name] = (None, None, None, None)
            continue
        ts, prev_counts = ref
        prev = int(prev_counts.get(name, 0))
        delta = cur - prev
        pct = (delta / prev * 100.0) if prev > 0 else (100.0 if delta > 0 else 0.0)
        result[name] = (delta, round(pct, 4), ts, prev)
    return result


def runtime_events_facets() -> dict[str, Any] | None:
    eng = engine()
    out: dict[str, Any] = {}
    dialect = getattr(eng.dialect, "name", "") or ""
    try:
        with eng.connect() as conn:
            tables = list_user_tables(conn)
            if "runtime_events" not in tables:
                return None
            ep = conn.execute(
                text(
                    'SELECT endpoint, COUNT(*) AS c FROM "runtime_events" '
                    "GROUP BY endpoint ORDER BY c DESC LIMIT 15"
                )
            ).fetchall()
            src = conn.execute(
                text(
                    'SELECT source, COUNT(*) AS c FROM "runtime_events" '
                    "GROUP BY source ORDER BY c DESC LIMIT 10"
                )
            ).fetchall()
            if dialect == "postgresql":
                hour = conn.execute(
                    text(
                        "SELECT date_trunc('hour', recorded_at) AS h, COUNT(*) AS c "
                        'FROM "runtime_events" '
                        "WHERE recorded_at >= NOW() - INTERVAL '48 hours' "
                        "GROUP BY h ORDER BY h DESC LIMIT 48"
                    )
                ).fetchall()
            else:
                hour = conn.execute(
                    text(
                        "SELECT strftime('%Y-%m-%d %H', recorded_at) AS h, COUNT(*) AS c "
                        'FROM "runtime_events" '
                        "WHERE recorded_at >= datetime('now', '-48 hours') "
                        "GROUP BY h ORDER BY h DESC LIMIT 48"
                    )
                ).fetchall()
        out["top_endpoints"] = [{"endpoint": str(r[0]), "count": int(r[1])} for r in ep]
        out["top_sources"] = [{"source": str(r[0]), "count": int(r[1])} for r in src]
        out["events_per_hour_48h"] = [{"bucket": str(r[0]), "count": int(r[1])} for r in hour]
    except Exception as exc:
        logger.debug("runtime_events_facets_failed: %s", exc)
        return None
    return out or None


def _health_score(rows: list[dict[str, Any]]) -> float:
    breach = sum(1 for r in rows if r.get("status") == "breach")
    warn = sum(1 for r in rows if r.get("status") == "warn")
    if breach:
        return max(0.0, 1.0 - 0.35 * breach - 0.15 * warn)
    if warn:
        return max(0.35, 1.0 - 0.12 * warn)
    return 1.0


def _open_friction_data_growth() -> list[str]:
    events, _ = friction_service.load_events()
    ids: list[str] = []
    for e in events:
        if e.status != "open":
            continue
        if e.block_type != friction_service.BLOCK_TYPE_DATA_GROWTH_ANOMALY:
            continue
        ids.append(e.id)
    return ids


def _already_open_for_table(table: str) -> bool:
    marker = f"data_hygiene:table={table}"
    events, _ = friction_service.load_events()
    for e in events:
        if e.status != "open" or e.block_type != friction_service.BLOCK_TYPE_DATA_GROWTH_ANOMALY:
            continue
        if marker in (e.notes or ""):
            if e.timestamp >= datetime.now(timezone.utc) - timedelta(hours=24):
                return True
    return False


def maybe_raise_friction(
    *,
    table: str,
    row_count: int,
    delta_24h: int | None,
    pct_24h: float | None,
    status: str,
) -> None:
    if status != "breach":
        return
    if _already_open_for_table(table):
        return
    notes = (
        f"data_hygiene:table={table} rows={row_count} "
        f"delta_24h={delta_24h} pct_24h={pct_24h}. "
        f"Inspect retention, duplicate tool calls, and worker loops."
    )
    evt = FrictionEvent(
        id=f"fric_{uuid.uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc),
        stage="data_hygiene",
        block_type=friction_service.BLOCK_TYPE_DATA_GROWTH_ANOMALY,
        severity="high",
        owner="data_hygiene",
        unblock_condition=(
            f"Reduce growth for {table}: tune retention, fix duplicate ingestion, or raise thresholds with review."
        ),
        energy_loss_estimate=0.5,
        cost_of_delay=0.25,
        status="open",
        notes=notes,
    )
    friction_service.append_event(evt)


def build_data_health_payload(*, evaluate_friction: bool = False) -> dict[str, Any]:
    try:
        eng = engine()
        _ = eng.url
    except Exception as exc:
        raise DataHealthUnavailable(str(exc)) from exc
    try:
        current = collect_table_counts()
    except Exception as exc:
        logger.exception("collect_table_counts failed")
        raise DataHealthUnavailable(str(exc)) from exc

    snap_rows = load_snapshots_from_db(limit=500)
    chrono: list[tuple[datetime, dict[str, int]]] = [
        (ts, counts) for _id, ts, counts, _src in reversed(snap_rows)
    ]
    deltas = _find_delta_vs_24h_ago(current, chrono)
    thr_map = _merge_env_thresholds(_default_thresholds())
    defaults = {
        "min_rows_pct": 100,
        "soft_pct": 30.0,
        "hard_pct": 85.0,
        "soft_abs": 500,
        "hard_abs": 3000,
        "max_rows_soft": 10**9,
        "max_rows_hard": 10**9,
    }

    table_models: list[dict[str, Any]] = []
    for name in sorted(current.keys()):
        cur = current[name]
        delta_24h, pct_24h, prev_ts, prev_count = deltas.get(name, (None, None, None, None))
        thr = {**defaults, **thr_map.get(name, {})}
        st = _row_status(
            name=name,
            row_count=cur,
            delta_24h=delta_24h,
            pct_24h=pct_24h,
            thr=thr,
        )
        row = {
            "name": name,
            "row_count": cur,
            "previous_snapshot_at": prev_ts,
            "previous_row_count": prev_count,
            "delta_24h": delta_24h,
            "pct_change_24h": pct_24h,
            "status": st,
        }
        table_models.append(row)
        if evaluate_friction:
            maybe_raise_friction(
                table=name,
                row_count=cur,
                delta_24h=delta_24h,
                pct_24h=pct_24h,
                status=st,
            )

    last_snap: datetime | None = None
    if snap_rows:
        last_snap = max(s[1] for s in snap_rows)

    stale_h: float | None = None
    hints: list[str] = [
        "Check runtime_events top_endpoints and top_sources for duplicate or chatty paths.",
        "Compare events_per_hour_48h for sudden spikes.",
    ]
    now = datetime.now(timezone.utc)
    if last_snap:
        stale_h = (now - last_snap.astimezone(timezone.utc)).total_seconds() / 3600.0
        if stale_h > 48:
            hints.insert(
                0,
                f"No fresh snapshot in {stale_h:.1f}h; schedule POST /api/data-health/snapshot or cron.",
            )

    facets = runtime_events_facets()

    score = _health_score(table_models)
    return {
        "generated_at": now,
        "database_kind": _database_kind(str(engine().url)),
        "health_score": round(score, 4),
        "last_snapshot_at": last_snap,
        "snapshot_stale_hours": stale_h,
        "tables": table_models,
        "open_friction_ids": _open_friction_data_growth(),
        "investigation_hints": hints,
        "runtime_events_facets": facets,
    }


def persist_snapshot(source: str = "manual") -> dict[str, Any]:
    counts = collect_table_counts()
    sid = f"dhs_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    payload = json.dumps(counts, sort_keys=True)
    with session() as s:
        rec = DataHygieneSnapshotRecord(id=sid, captured_at=now, table_counts_json=payload, source=source)
        s.add(rec)
    alerts = 0
    health = build_data_health_payload(evaluate_friction=True)
    for t in health["tables"]:
        if t.get("status") == "breach":
            alerts += 1
    return {
        "id": sid,
        "captured_at": now,
        "source": source,
        "table_counts": counts,
        "alerts_raised": alerts,
    }


def list_snapshots_api(limit: int = 20) -> dict[str, Any]:
    cap = max(1, min(limit, 100))
    rows = load_snapshots_from_db(limit=cap)
    items: list[dict[str, Any]] = []
    for sid, ts, counts, src in rows:
        items.append(
            {
                "id": sid,
                "captured_at": ts,
                "source": src,
                "table_counts": counts,
            }
        )
    return {"snapshots": items, "limit": cap, "total_returned": len(items)}
