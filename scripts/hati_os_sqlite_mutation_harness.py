#!/usr/bin/env python3
"""Execute SQLite mutations through a Hati-OS driver binary and verify DB effects.

This is not the full API host yet. It is the honest bridge we have today:
the Hati-OS driver organ executes host `sqlite3`, and the DB state is
validated directly after each mutation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORM = ROOT / "form"
GO_BIN = FORM / "form-kernel-go" / "bin-go"
BOOTSTRAP = ROOT / "scripts" / "bootstrap_sqlite_from_production_archive.py"


DRIVER_FORM = r'''
(defn seqq (a b) (fk-if a b b))
(defn adv () (fk-set (fk-lit 0) (fk-add (fk-get (fk-lit 0)) (fk-lit 1))))
(defn x2 () (fk-add (fk-arg) (fk-arg)))
(defn x10 () (fk-add (fk-add (x2) (x2)) (fk-add (fk-add (x2) (x2)) (x2))))
(defn curb () (fk-buf (fk-get (fk-lit 0))))
(let numf (fk-if (fk-le (fk-lit 48) (curb))
    (fk-if (fk-le (curb) (fk-lit 57))
        (seqq (adv)
            (fk-call 1 (fk-add (x10) (fk-sub (fk-buf (fk-sub (fk-get (fk-lit 0)) (fk-lit 1))) (fk-lit 48)))))
        (fk-arg))
    (fk-arg)))
(let entry (fk-call 1 (fk-lit 0)))
(print "==DRV==")
(print (fkc-emit-driver (list entry numf)))
(print "==END==")
'''


@dataclass(frozen=True)
class MutationObservation:
    name: str
    command: list[str]
    changes_reported: int
    checks: dict[str, bool]
    passed: bool


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"required tool missing: {name}")
    return path


def build_go_kernel() -> None:
    if GO_BIN.exists():
        return
    subprocess.run(["go", "build", "-o", "bin-go", "."], cwd=FORM / "form-kernel-go", check=True)


def emit_hati_os_driver_binary() -> Path:
    build_go_kernel()
    require_tool("clang")
    work = Path(tempfile.mkdtemp(prefix="hati-os-sqlite-harness."))
    driver_fk = work / "driver.fk"
    driver_fk.write_text(
        (FORM / "form-stdlib" / "minimal-surface.fk").read_text(encoding="utf-8")
        + (FORM / "form-stdlib" / "hati-os-kernel.fk").read_text(encoding="utf-8")
        + (FORM / "form-stdlib" / "hati-os-kernel-emit.fk").read_text(encoding="utf-8")
        + "\n"
        + DRIVER_FORM
        + "\n",
        encoding="utf-8",
    )
    emitted = subprocess.run([str(GO_BIN), str(driver_fk)], cwd=FORM, capture_output=True, text=True, check=True)
    c_path = work / "driver.c"
    block = []
    active = False
    for line in emitted.stdout.splitlines():
        if line == "==DRV==":
            active = True
            continue
        if line == "==END==":
            break
        if active:
            block.append(line)
    c_path.write_text("\n".join(block) + "\n", encoding="utf-8")
    bin_path = work / "hati-os-sqlite"
    subprocess.run(["clang", "-O2", "-o", str(bin_path), str(c_path)], check=True)
    return bin_path


def run_driver_int(driver: Path, command: list[str]) -> int:
    proc = subprocess.run([str(driver), *command], capture_output=True, text=True, check=True)
    first = (proc.stdout.strip().splitlines() or ["0"])[0].strip()
    return int(first or "0")


def shell_sqlite_changes_command(db_path: Path, sql: str) -> list[str]:
    quoted = str(db_path).replace("'", "'\"'\"'")
    sql_quoted = sql.replace("'", "'\"'\"'")
    shell = f"sqlite3 '{quoted}' '{sql_quoted}; SELECT changes();'"
    return ["sh", "-lc", shell]


def ensure_sqlite_archive(sqlite_path: Path, tag: str) -> None:
    if sqlite_path.exists():
        return
    subprocess.run(
        [sys.executable, str(BOOTSTRAP), "--tag", tag, "--sqlite-path", str(sqlite_path)],
        check=True,
        cwd=ROOT,
    )


def validate_create(conn: sqlite3.Connection) -> dict[str, bool]:
    node = conn.execute("SELECT type, name, description, phase FROM graph_nodes WHERE id = 'hati-os-idea';").fetchone()
    revs = conn.execute("SELECT count(*) FROM graph_node_revisions WHERE node_id = 'hati-os-idea';").fetchone()[0]
    return {
        "node_exists": node is not None,
        "type_is_idea": bool(node and node[0] == "idea"),
        "name_written": bool(node and node[1] == "Hati-OS Idea"),
        "revision_written": revs >= 1,
    }


def validate_update(conn: sqlite3.Connection) -> dict[str, bool]:
    node = conn.execute("SELECT name, description, phase FROM graph_nodes WHERE id = 'hati-os-idea';").fetchone()
    revs = conn.execute("SELECT count(*) FROM graph_node_revisions WHERE node_id = 'hati-os-idea';").fetchone()[0]
    return {
        "node_exists": node is not None,
        "name_updated": bool(node and node[0] == "Hati-OS Idea Revised"),
        "phase_updated": bool(node and node[2] == "water"),
        "revision_incremented": revs >= 2,
    }


def validate_delete(conn: sqlite3.Connection) -> dict[str, bool]:
    node_count = conn.execute("SELECT count(*) FROM graph_nodes WHERE id = 'hati-os-idea';").fetchone()[0]
    edge_count = conn.execute("SELECT count(*) FROM graph_edges WHERE from_id = 'hati-os-peer' OR to_id = 'hati-os-peer' OR from_id = 'hati-os-idea' OR to_id = 'hati-os-idea';").fetchone()[0]
    return {
        "node_deleted": node_count == 0,
        "edges_deleted": edge_count == 0,
    }


def main() -> int:
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-path", type=Path, default=ROOT / ".cache" / "hati-os" / "coherence.archive.sqlite")
    parser.add_argument("--tag", default="latest")
    args = parser.parse_args()

    require_tool("sqlite3")
    ensure_sqlite_archive(args.sqlite_path, args.tag)
    driver = emit_hati_os_driver_binary()

    conn = sqlite3.connect(str(args.sqlite_path))
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.executescript(
        """
        DELETE FROM graph_edges WHERE id IN ('hati-os-edge');
        DELETE FROM graph_node_revisions WHERE node_id IN ('hati-os-idea', 'hati-os-peer');
        DELETE FROM graph_nodes WHERE id IN ('hati-os-idea', 'hati-os-peer');
        """
    )
    conn.commit()

    create_sql = """
    INSERT INTO graph_nodes (id, type, name, description, properties, phase, created_at, updated_at)
    VALUES ('hati-os-idea', 'idea', 'Hati-OS Idea', 'created through sqlite driver', '{"stage":"none"}', 'gas', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO graph_node_revisions (id, node_id, revision_number, captured_at, source, author, fields_changed, snapshot)
    SELECT 'hati-os-rev-create', id, 1, CURRENT_TIMESTAMP, 'Hati-OS', 'codex', '["__create__"]',
           json_object('id', id, 'type', type, 'name', name, 'description', description, 'phase', phase, 'created_at', created_at, 'updated_at', updated_at, 'properties', properties)
    FROM graph_nodes
    WHERE id = 'hati-os-idea'
    """
    update_sql = """
    UPDATE graph_nodes
       SET name = 'Hati-OS Idea Revised',
           description = 'updated through sqlite driver',
           phase = 'water',
           properties = json_patch(COALESCE(properties, '{}'), '{"stage":"implementing"}'),
           updated_at = CURRENT_TIMESTAMP
     WHERE id = 'hati-os-idea';
    INSERT INTO graph_node_revisions (id, node_id, revision_number, captured_at, source, author, fields_changed, snapshot)
    SELECT 'hati-os-rev-update', id,
           (SELECT COALESCE(max(revision_number), 0) + 1 FROM graph_node_revisions WHERE node_id = 'hati-os-idea'),
           CURRENT_TIMESTAMP, 'Hati-OS', 'codex', '["name","description","phase","properties.stage"]',
           json_object('id', id, 'type', type, 'name', name, 'description', description, 'phase', phase, 'created_at', created_at, 'updated_at', updated_at, 'properties', properties)
    FROM graph_nodes
    WHERE id = 'hati-os-idea'
    """
    seed_delete_sql = """
    INSERT INTO graph_nodes (id, type, name, description, properties, phase, created_at, updated_at)
    VALUES ('hati-os-peer', 'idea', 'Hati-OS Peer', 'peer for edge delete', '{}', 'water', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO graph_edges (id, from_id, to_id, type, properties, strength, created_by, created_at)
    VALUES ('hati-os-edge', 'hati-os-peer', 'hati-os-idea', 'references', '{}', 1.0, 'Hati-OS-harness', CURRENT_TIMESTAMP);
    """
    delete_sql = """
    DELETE FROM graph_edges WHERE from_id = 'hati-os-idea' OR to_id = 'hati-os-idea';
    DELETE FROM graph_nodes WHERE id = 'hati-os-idea';
    DELETE FROM graph_nodes WHERE id = 'hati-os-peer';
    """

    observations: list[MutationObservation] = []

    create_cmd = shell_sqlite_changes_command(args.sqlite_path, create_sql)
    create_changes = run_driver_int(driver, create_cmd)
    conn.commit()
    create_checks = validate_create(conn)
    observations.append(
        MutationObservation(
            name="create_graph_node",
            command=create_cmd,
            changes_reported=create_changes,
            checks=create_checks,
            passed=create_changes >= 1 and all(create_checks.values()),
        )
    )

    update_cmd = shell_sqlite_changes_command(args.sqlite_path, update_sql)
    update_changes = run_driver_int(driver, update_cmd)
    conn.commit()
    update_checks = validate_update(conn)
    observations.append(
        MutationObservation(
            name="update_graph_node",
            command=update_cmd,
            changes_reported=update_changes,
            checks=update_checks,
            passed=update_changes >= 1 and all(update_checks.values()),
        )
    )

    conn.executescript(seed_delete_sql)
    conn.commit()
    delete_cmd = shell_sqlite_changes_command(args.sqlite_path, delete_sql)
    delete_changes = run_driver_int(driver, delete_cmd)
    conn.commit()
    delete_checks = validate_delete(conn)
    observations.append(
        MutationObservation(
            name="delete_graph_node",
            command=delete_cmd,
            changes_reported=delete_changes,
            checks=delete_checks,
            passed=delete_changes >= 1 and all(delete_checks.values()),
        )
    )

    payload = {
        "sqlite_path": str(args.sqlite_path),
        "driver_path": str(driver),
        "observations": [asdict(item) for item in observations],
        "all_passed": all(item.passed for item in observations),
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
