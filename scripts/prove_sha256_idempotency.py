#!/usr/bin/env python3
"""Prove full-SHA write-boundary idempotency on an isolated SQLite copy.

This is a migration-readiness canary, not a migration. It:
- fails if current study_units hashes are null/duplicated,
- creates a UNIQUE(full sha256_hash) index on the disposable copy,
- proves a serial duplicate hash is rejected,
- races two distinct unit_ids with one new hash and requires exactly one commit,
- proves the winning source row has exactly one FTS membership row,
- cleans the canary row and proves no ghost FTS membership remains,
- finishes with PRAGMA integrity_check=ok.

Never run this against the committed repository database in place.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import threading
from pathlib import Path

SOURCE = "study_units"
FTS_CONTENT = "universal_fts_content"
SEED_UNIT_ID = "GATEEE-COM-004"
CANARY_HASH = "d" * 64
CANARY_UNIT_IDS = ("__SHA256_RACE_A__", "__SHA256_RACE_B__")
INDEX_NAME = "ux_study_units_sha256_hash"


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info({qident(table)})")]


def clone_insert(con: sqlite3.Connection, unit_id: str, sha256_hash: str) -> None:
    cols = columns(con, SOURCE)
    select_parts: list[str] = []
    params: list[object] = []
    for col in cols:
        if col == "unit_id":
            select_parts.append("?")
            params.append(unit_id)
        elif col == "sha256_hash":
            select_parts.append("?")
            params.append(sha256_hash)
        else:
            select_parts.append(qident(col))
    params.append(SEED_UNIT_ID)
    con.execute(
        f"INSERT INTO {qident(SOURCE)} ({', '.join(qident(c) for c in cols)}) "
        f"SELECT {', '.join(select_parts)} FROM {qident(SOURCE)} WHERE unit_id=?",
        params,
    )
    if con.execute("SELECT changes()").fetchone()[0] != 1:
        raise AssertionError(f"seed row missing or clone insert failed for {unit_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"database not found: {args.db}")

    with sqlite3.connect(args.db) as con:
        con.execute("PRAGMA foreign_keys=ON")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise AssertionError(f"pre-canary integrity_check={integrity!r}")
        total, nonnull, distinct = con.execute(
            f"SELECT COUNT(*), COUNT(sha256_hash), COUNT(DISTINCT sha256_hash) FROM {qident(SOURCE)}"
        ).fetchone()
        if not (total == nonnull == distinct):
            raise AssertionError(
                f"current full-SHA preflight failed: total={total} nonnull={nonnull} distinct={distinct}"
            )
        if con.execute(
            f"SELECT COUNT(*) FROM {qident(SOURCE)} WHERE sha256_hash=?", (CANARY_HASH,)
        ).fetchone()[0]:
            raise AssertionError("reserved canary hash already exists")
        con.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {qident(INDEX_NAME)} "
            f"ON {qident(SOURCE)}(sha256_hash)"
        )
        con.commit()

        # Serial rejection: duplicate an existing durable hash under a different unit_id.
        existing_hash = con.execute(
            f"SELECT sha256_hash FROM {qident(SOURCE)} WHERE unit_id=?", (SEED_UNIT_ID,)
        ).fetchone()
        if not existing_hash:
            raise AssertionError(f"seed unit missing: {SEED_UNIT_ID}")
        serial_rejected = False
        try:
            clone_insert(con, "__SHA256_SERIAL_DUP__", existing_hash[0])
            con.commit()
        except sqlite3.IntegrityError:
            con.rollback()
            serial_rejected = True
        if not serial_rejected:
            raise AssertionError("serial duplicate full SHA was admitted")

    # Concurrent first-writer race on one previously unused full hash.
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, str]] = []
    lock = threading.Lock()

    def racer(unit_id: str) -> None:
        local = sqlite3.connect(args.db, timeout=10, isolation_level=None)
        local.execute("PRAGMA busy_timeout=10000")
        try:
            barrier.wait(timeout=10)
            local.execute("BEGIN")
            clone_insert(local, unit_id, CANARY_HASH)
            local.execute("COMMIT")
            outcome = "COMMITTED"
        except sqlite3.IntegrityError:
            try:
                local.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            outcome = "REJECTED_UNIQUE"
        finally:
            local.close()
        with lock:
            outcomes.append((unit_id, outcome))

    threads = [threading.Thread(target=racer, args=(unit_id,)) for unit_id in CANARY_UNIT_IDS]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("concurrent canary thread did not finish")

    with sqlite3.connect(args.db) as con:
        winners = con.execute(
            f"SELECT rowid, unit_id FROM {qident(SOURCE)} WHERE sha256_hash=?", (CANARY_HASH,)
        ).fetchall()
        if len(winners) != 1:
            raise AssertionError(f"expected exactly one durable race winner, got {winners!r}")
        committed = [o for _, o in outcomes if o == "COMMITTED"]
        rejected = [o for _, o in outcomes if o == "REJECTED_UNIQUE"]
        if len(committed) != 1 or len(rejected) != 1:
            raise AssertionError(f"unexpected race outcomes: {outcomes!r}")

        winner_rowid, winner_unit_id = winners[0]
        fts_rows = con.execute(
            f"SELECT COUNT(*) FROM {qident(FTS_CONTENT)} WHERE id=?", (winner_rowid,)
        ).fetchone()[0]
        if fts_rows != 1:
            raise AssertionError(f"winner FTS membership expected 1 row, got {fts_rows}")

        con.execute(f"DELETE FROM {qident(SOURCE)} WHERE rowid=?", (winner_rowid,))
        con.commit()
        ghost_source = con.execute(
            f"SELECT COUNT(*) FROM {qident(SOURCE)} WHERE sha256_hash=?", (CANARY_HASH,)
        ).fetchone()[0]
        ghost_fts = con.execute(
            f"SELECT COUNT(*) FROM {qident(FTS_CONTENT)} WHERE id=?", (winner_rowid,)
        ).fetchone()[0]
        if ghost_source or ghost_fts:
            raise AssertionError(
                f"canary cleanup left ghost state: source={ghost_source} fts={ghost_fts}"
            )
        final_integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if final_integrity != "ok":
            raise AssertionError(f"post-canary integrity_check={final_integrity!r}")

        print(json.dumps({
            "status": "PASS_ISOLATED_SHA256_IDEMPOTENCY_CANARY",
            "index": INDEX_NAME,
            "preflight_rows": total,
            "serial_duplicate": "REJECTED_UNIQUE",
            "concurrent_outcomes": sorted(outcomes),
            "durable_winner_unit_id": winner_unit_id,
            "durable_rows_for_canary_hash_before_cleanup": 1,
            "fts_rows_for_winner_before_cleanup": fts_rows,
            "ghost_source_rows_after_cleanup": ghost_source,
            "ghost_fts_rows_after_cleanup": ghost_fts,
            "integrity_check": final_integrity,
        }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
