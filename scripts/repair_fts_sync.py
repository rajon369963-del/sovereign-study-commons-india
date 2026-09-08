#!/usr/bin/env python3
"""Cause-specific FTS5 membership repair for the committed study lake.

This script is intentionally narrow:
- binds universal_fts to study_units by rowid membership,
- repairs missing source rows without inventing exclusions,
- installs INSERT/UPDATE/DELETE synchronization triggers compatible with the
  current standalone/contentful FTS5 schema,
- proves the repaired GATE-EE-COM-004 row is semantically searchable, and
- runs a transactional insert/update/delete canary to prove future sync.

It does not migrate the FTS schema and does not claim learner efficacy.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

SOURCE = "study_units"
FTS = "universal_fts"
TARGET_UNIT_ID = "GATE-EE-COM-004"
SEMANTIC_TERM = "Nyquist"
CANARY_UNIT_ID = "__FTS_SYNC_CANARY__"
CANARY_HASH = "f" * 64
CANARY_TERM = "FTS_SYNC_CANARY_TERM"


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info({qident(table)})")]


def ids(con: sqlite3.Connection, table: str) -> set[int]:
    if table == FTS:
        shadow = f"{FTS}_content"
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (shadow,)
        ).fetchone()
        if exists:
            return {row[0] for row in con.execute(f"SELECT id FROM {qident(shadow)}")}
    return {row[0] for row in con.execute(f"SELECT rowid FROM {qident(table)}")}


def common_indexed_columns(con: sqlite3.Connection) -> list[str]:
    src = columns(con, SOURCE)
    fts = columns(con, FTS)
    common = [c for c in fts if c in src]
    if not common:
        raise RuntimeError("no common columns between study_units and universal_fts")
    return common


def insert_missing(con: sqlite3.Connection, common: list[str]) -> list[int]:
    source_ids = ids(con, SOURCE)
    indexed_ids = ids(con, FTS)
    missing = sorted(source_ids - indexed_ids)
    if not missing:
        return []
    cols_sql = ", ".join(qident(c) for c in common)
    for rowid in missing:
        con.execute(
            f"INSERT INTO {qident(FTS)}(rowid, {cols_sql}) "
            f"SELECT rowid, {cols_sql} FROM {qident(SOURCE)} WHERE rowid=?",
            (rowid,),
        )
    return missing


def install_triggers(con: sqlite3.Connection, common: list[str]) -> None:
    cols_sql = ", ".join(qident(c) for c in common)
    new_values = ", ".join(f"new.{qident(c)}" for c in common)
    trigger_sql = {
        "study_units_ai_universal_fts": f"""
            CREATE TRIGGER IF NOT EXISTS study_units_ai_universal_fts
            AFTER INSERT ON {qident(SOURCE)} BEGIN
              INSERT INTO {qident(FTS)}(rowid, {cols_sql})
              VALUES (new.rowid, {new_values});
            END
        """,
        "study_units_au_universal_fts": f"""
            CREATE TRIGGER IF NOT EXISTS study_units_au_universal_fts
            AFTER UPDATE ON {qident(SOURCE)} BEGIN
              DELETE FROM {qident(FTS)} WHERE rowid = old.rowid;
              INSERT INTO {qident(FTS)}(rowid, {cols_sql})
              VALUES (new.rowid, {new_values});
            END
        """,
        "study_units_ad_universal_fts": f"""
            CREATE TRIGGER IF NOT EXISTS study_units_ad_universal_fts
            AFTER DELETE ON {qident(SOURCE)} BEGIN
              DELETE FROM {qident(FTS)} WHERE rowid = old.rowid;
            END
        """,
    }
    for sql in trigger_sql.values():
        con.execute(sql)


def assert_membership_equal(con: sqlite3.Connection) -> None:
    source_ids = ids(con, SOURCE)
    indexed_ids = ids(con, FTS)
    missing = sorted(source_ids - indexed_ids)
    extra = sorted(indexed_ids - source_ids)
    if missing or extra:
        raise AssertionError(
            f"FTS membership drift remains: missing={missing[:20]} extra={extra[:20]}"
        )


def assert_semantic_target(con: sqlite3.Connection) -> int:
    row = con.execute(
        f"SELECT rowid FROM {qident(SOURCE)} WHERE unit_id=?", (TARGET_UNIT_ID,)
    ).fetchone()
    if not row:
        raise AssertionError(f"target source unit missing: {TARGET_UNIT_ID}")
    target_rowid = row[0]
    hit = con.execute(
        f"SELECT rowid FROM {qident(FTS)} WHERE {qident(FTS)} MATCH ? AND rowid=?",
        (SEMANTIC_TERM, target_rowid),
    ).fetchone()
    if not hit:
        raise AssertionError(
            f"semantic canary failed: {TARGET_UNIT_ID} not retrievable by {SEMANTIC_TERM!r}"
        )
    return target_rowid


def assert_sync_canary(con: sqlite3.Connection, common: list[str]) -> None:
    src_cols = columns(con, SOURCE)
    target_row = con.execute(
        f"SELECT rowid FROM {qident(SOURCE)} WHERE unit_id=?", (TARGET_UNIT_ID,)
    ).fetchone()
    if not target_row:
        raise AssertionError("cannot seed sync canary: target source row missing")
    seed_rowid = target_row[0]

    clone_cols = [c for c in src_cols]
    select_parts = []
    for col in clone_cols:
        qc = qident(col)
        if col == "unit_id":
            select_parts.append("?")
        elif col == "sha256_hash":
            select_parts.append("?")
        else:
            select_parts.append(qc)

    con.execute("SAVEPOINT fts_sync_canary")
    try:
        con.execute(
            f"INSERT INTO {qident(SOURCE)} ({', '.join(qident(c) for c in clone_cols)}) "
            f"SELECT {', '.join(select_parts)} FROM {qident(SOURCE)} WHERE rowid=?",
            (CANARY_UNIT_ID, CANARY_HASH, seed_rowid),
        )
        canary_rowid = con.execute(
            f"SELECT rowid FROM {qident(SOURCE)} WHERE unit_id=?", (CANARY_UNIT_ID,)
        ).fetchone()[0]
        if canary_rowid not in ids(con, FTS):
            raise AssertionError("INSERT trigger failed to add canary to FTS")

        update_col = next((c for c in ("topic", "question_text", "exact_quote", "explanation") if c in common), None)
        if not update_col:
            raise AssertionError("no suitable common text column for UPDATE trigger canary")
        con.execute(
            f"UPDATE {qident(SOURCE)} SET {qident(update_col)}=? WHERE rowid=?",
            (CANARY_TERM, canary_rowid),
        )
        hit = con.execute(
            f"SELECT rowid FROM {qident(FTS)} WHERE {qident(FTS)} MATCH ? AND rowid=?",
            (CANARY_TERM, canary_rowid),
        ).fetchone()
        if not hit:
            raise AssertionError("UPDATE trigger failed semantic FTS refresh")

        con.execute(f"DELETE FROM {qident(SOURCE)} WHERE rowid=?", (canary_rowid,))
        if canary_rowid in ids(con, FTS):
            raise AssertionError("DELETE trigger failed to remove canary from FTS")
    finally:
        con.execute("ROLLBACK TO fts_sync_canary")
        con.execute("RELEASE fts_sync_canary")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"database not found: {args.db}")

    with sqlite3.connect(args.db) as con:
        integrity_before = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity_before != "ok":
            raise AssertionError(f"pre-repair integrity_check={integrity_before!r}")

        common = common_indexed_columns(con)
        missing_before = sorted(ids(con, SOURCE) - ids(con, FTS))
        repaired = insert_missing(con, common)
        install_triggers(con, common)
        con.commit()

        assert_membership_equal(con)
        target_rowid = assert_semantic_target(con)
        assert_sync_canary(con, common)
        assert_membership_equal(con)
        integrity_after = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity_after != "ok":
            raise AssertionError(f"post-repair integrity_check={integrity_after!r}")

        trigger_names = [
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'study_units_%_universal_fts' ORDER BY name"
            )
        ]
        print(
            json.dumps(
                {
                    "status": "PASS_REPAIR_CANDIDATE",
                    "missing_before": missing_before,
                    "repaired_rowids": repaired,
                    "missing_after": sorted(ids(con, SOURCE) - ids(con, FTS)),
                    "extra_after": sorted(ids(con, FTS) - ids(con, SOURCE)),
                    "target_unit_id": TARGET_UNIT_ID,
                    "target_rowid": target_rowid,
                    "semantic_term": SEMANTIC_TERM,
                    "sync_canary": "INSERT_UPDATE_DELETE_PASS",
                    "triggers": trigger_names,
                    "integrity_check": integrity_after,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
