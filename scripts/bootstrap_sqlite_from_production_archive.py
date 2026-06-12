#!/usr/bin/env python3
"""Bootstrap a local SQLite DB from a real archived production Postgres dump.

Flow:
  1. Download a plain-SQL pg_dump archive from seeker71/coherence-network-archive
     (or use a provided dump path).
  2. Restore it into a throwaway local Postgres cluster.
  3. Reflect every table and project all rows into SQLite.

The point is honest portability: the SQLite file is initialized from the real
production SQL archive, not from hand-maintained fixtures.
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Column, Index, MetaData, Table, Text, create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.sqltypes import NullType


ARCHIVE_REPO = "seeker71/coherence-network-archive"
DEFAULT_SQLITE = Path(".cache/hati-os/coherence.archive.sqlite")
DEFAULT_DOWNLOAD_DIR = Path(".cache/production-archive")


def log(message: str) -> None:
    print(f"[bootstrap] {message}", file=sys.stderr, flush=True)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"required tool not found: {name}")
    return path


def run(cmd: list[str], *, cwd: Path | None = None, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        input=input_bytes,
        capture_output=True,
        check=False,
    )


def run_text(cmd: list[str], *, cwd: Path | None = None) -> str:
    proc = run(cmd, cwd=cwd)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        stdout = proc.stdout.decode("utf-8", "replace").strip()
        raise RuntimeError(stderr or stdout or f"command failed: {' '.join(cmd)}")
    return proc.stdout.decode("utf-8", "replace").strip()


def gzip_is_valid(path: Path) -> bool:
    proc = run(["gzip", "-t", str(path)])
    return proc.returncode == 0


def latest_archive_tag(repo: str) -> str:
    log(f"resolving latest archive tag from {repo}")
    return run_text(
        ["gh", "release", "list", "--repo", repo, "--limit", "1", "--json", "tagName", "--jq", ".[0].tagName"]
    )


def download_archive(repo: str, tag: str, download_dir: Path) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    log(f"resolving asset for {repo}@{tag}")
    asset_name = run_text(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "assets",
            "--jq",
            ".assets[0].name",
        ]
    )
    target = download_dir / asset_name
    if target.exists():
        if gzip_is_valid(target):
            log(f"using cached archive {target}")
            return target
        log(f"cached archive is truncated or invalid, re-downloading {target}")
        target.unlink()
    log(f"downloading archive to {target}")
    cmd = ["gh", "release", "download", tag, "--repo", repo, "--dir", str(download_dir), "--clobber"]
    proc = run(cmd)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(stderr or f"failed to download release {tag}")
    if not target.exists():
        raise RuntimeError(f"download reported success but asset missing: {target}")
    return target


@dataclass(frozen=True)
class TempPostgres:
    dsn: str
    maintenance_dsn: str
    directory: Path
    port: int


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def provision_temp_postgres() -> TempPostgres:
    initdb = require_tool("initdb")
    pg_ctl = require_tool("pg_ctl")
    require_tool("psql")
    directory = Path(tempfile.mkdtemp(prefix="archive-restore-pg."))
    port = free_port()
    data_dir = directory / "data"
    log(f"initdb temp postgres at {directory}")
    init = run([initdb, "-D", str(data_dir), "-U", "postgres", "--auth=trust"])
    if init.returncode != 0:
        raise RuntimeError(init.stderr.decode("utf-8", "replace").strip() or "initdb failed")
    log(f"starting temp postgres on 127.0.0.1:{port}")
    start = run(
        [
            pg_ctl,
            "-D",
            str(data_dir),
            "-o",
            f"-p {port} -k {directory}",
            "-l",
            str(directory / "log"),
            "start",
        ]
    )
    if start.returncode != 0:
        raise RuntimeError(start.stderr.decode("utf-8", "replace").strip() or "pg_ctl start failed")
    maintenance_dsn = f"postgresql://postgres@127.0.0.1:{port}/postgres"
    dsn = f"postgresql://postgres@127.0.0.1:{port}/coherence_restore_sqlite"
    log("creating restore database coherence_restore_sqlite")
    run_text(["psql", maintenance_dsn, "-v", "ON_ERROR_STOP=1", "-Atc", "CREATE DATABASE coherence_restore_sqlite;"])
    return TempPostgres(dsn=dsn, maintenance_dsn=maintenance_dsn, directory=directory, port=port)


def stop_temp_postgres(pg: TempPostgres | None, *, keep: bool = False) -> None:
    if pg is None:
        return
    pg_ctl = shutil.which("pg_ctl")
    if pg_ctl:
        run([pg_ctl, "-D", str(pg.directory / "data"), "stop", "-m", "fast"])
    if not keep:
        shutil.rmtree(pg.directory, ignore_errors=True)


def restore_dump_to_postgres(pg: TempPostgres, dump_path: Path) -> None:
    log(f"restoring dump {dump_path} into temp postgres")
    with gzip.open(dump_path, "rb") as fh:
        sql_bytes = fh.read()
    proc = run(["psql", pg.dsn, "-v", "ON_ERROR_STOP=1"], input_bytes=sql_bytes)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(stderr or "restore into temp postgres failed")


def sqlite_type_for(column: Column[Any]) -> Any:
    type_name = column.type.__class__.__name__.lower()
    if "uuid" in type_name:
        return Text()
    try:
        generic = column.type.as_generic()
    except Exception:
        generic = column.type
    if isinstance(generic, NullType):
        return Text()
    return generic


def adapt_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return value


def copy_all_tables(pg_engine: Engine, sqlite_engine: Engine) -> dict[str, dict[str, Any]]:
    src_meta = MetaData()
    log("reflecting postgres schema")
    src_meta.reflect(bind=pg_engine)
    dst_meta = MetaData()
    report: dict[str, dict[str, Any]] = {}

    # Disable FK enforcement during bulk load; we only need a faithful local carrier.
    with sqlite_engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")

    dst_tables: dict[str, Table] = {}
    for table_name in sorted(src_meta.tables):
        src_table = src_meta.tables[table_name]
        dst_columns = []
        for col in src_table.columns:
            dst_columns.append(
                Column(
                    col.name,
                    sqlite_type_for(col),
                    primary_key=col.primary_key,
                    nullable=col.nullable,
                )
            )
        dst_table = Table(table_name, dst_meta, *dst_columns)
        dst_tables[table_name] = dst_table

    log(f"creating sqlite schema for {len(src_meta.tables)} tables")
    dst_meta.create_all(sqlite_engine)

    for table_name in sorted(src_meta.tables):
        src_table = src_meta.tables[table_name]
        dst_table = dst_tables[table_name]
        log(f"copying table {table_name}")
        inserted = 0
        with pg_engine.connect() as src_conn, sqlite_engine.begin() as dst_conn:
            result = src_conn.execution_options(stream_results=True).execute(text(f'SELECT * FROM "{table_name}"'))
            batch: list[dict[str, Any]] = []
            for row in result.mappings():
                batch.append({key: adapt_value(value) for key, value in dict(row).items()})
                if len(batch) >= 1000:
                    dst_conn.execute(dst_table.insert(), batch)
                    inserted += len(batch)
                    batch = []
            if batch:
                dst_conn.execute(dst_table.insert(), batch)
                inserted += len(batch)

        with pg_engine.connect() as conn:
            pg_count = int(conn.execute(select(func.count()).select_from(src_table)).scalar_one())
        with sqlite_engine.connect() as conn:
            sqlite_count = int(conn.execute(select(func.count()).select_from(dst_table)).scalar_one())
        report[table_name] = {
            "rows_postgres": pg_count,
            "rows_sqlite": sqlite_count,
            "inserted": inserted,
        }
        if pg_count != sqlite_count:
            raise RuntimeError(f"row-count mismatch for {table_name}: postgres={pg_count} sqlite={sqlite_count}")

    # Recreate simple column indexes after data copy.
    for table_name in sorted(src_meta.tables):
        src_table = src_meta.tables[table_name]
        dst_table = dst_tables[table_name]
        for index in src_table.indexes:
            cols = []
            supported = True
            for expr in index.expressions:
                col_name = getattr(expr, "name", None)
                if not col_name or col_name not in dst_table.c:
                    supported = False
                    break
                cols.append(dst_table.c[col_name])
            if supported and cols:
                Index(index.name, *cols).create(bind=sqlite_engine, checkfirst=True)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=ARCHIVE_REPO)
    parser.add_argument("--tag", default="latest", help="Archive release tag or 'latest'")
    parser.add_argument("--dump-path", type=Path, default=None, help="Existing .sql.gz archive to restore")
    parser.add_argument("--download-dir", type=Path, default=DEFAULT_DOWNLOAD_DIR)
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--keep-temp-postgres", action="store_true")
    args = parser.parse_args()

    require_tool("gh")
    dump_path = args.dump_path
    resolved_tag = args.tag
    if dump_path is None:
        if resolved_tag == "latest":
            resolved_tag = latest_archive_tag(args.repo)
        dump_path = download_archive(args.repo, resolved_tag, args.download_dir)
    if not dump_path.exists():
        raise RuntimeError(f"dump not found: {dump_path}")

    args.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if args.sqlite_path.exists():
        args.sqlite_path.unlink()

    pg: TempPostgres | None = None
    try:
        pg = provision_temp_postgres()
        restore_dump_to_postgres(pg, dump_path)
        pg_engine = create_engine(pg.dsn)
        sqlite_engine = create_engine(f"sqlite:///{args.sqlite_path}")
        report = copy_all_tables(pg_engine, sqlite_engine)
    finally:
        stop_temp_postgres(pg, keep=args.keep_temp_postgres)
    log(f"sqlite archive ready at {args.sqlite_path}")

    payload = {
        "archive_repo": args.repo,
        "tag": resolved_tag,
        "dump_path": str(dump_path),
        "sqlite_path": str(args.sqlite_path),
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "table_count": len(report),
        "tables": report,
    }
    meta_path = args.sqlite_path.with_suffix(args.sqlite_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise
