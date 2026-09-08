#!/usr/bin/env python3
"""Fail-closed audit for Sovereign Study Commons content identity.

This script intentionally does NOT add a UNIQUE constraint. It distinguishes:
1) snapshot properties of study_units.sha256_hash; from
2) a proven semantic contract defining what bytes/fields the hash represents.

A unique-looking column is not yet a content-identity definition.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def audit(db: Path) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        table = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='study_units'"
        ).fetchone()
        if not table:
            raise RuntimeError("study_units table missing")

        cols = {
            row[1]: {"notnull": bool(row[3]), "pk": bool(row[5])}
            for row in con.execute("PRAGMA table_info(study_units)")
        }
        for required in ("unit_id", "sha256_hash"):
            if required not in cols:
                raise RuntimeError(f"study_units.{required} missing")

        rows = con.execute(
            "SELECT rowid, unit_id, sha256_hash FROM study_units ORDER BY rowid"
        ).fetchall()
        invalid = []
        nulls = []
        for rowid, unit_id, value in rows:
            if value is None:
                nulls.append({"rowid": rowid, "unit_id": unit_id})
            elif not SHA256_RE.fullmatch(value):
                invalid.append(
                    {"rowid": rowid, "unit_id": unit_id, "observed_length": len(value)}
                )

        dup_groups = [
            {"sha256_hash": h, "count": n}
            for h, n in con.execute(
                """
                SELECT sha256_hash, COUNT(*)
                FROM study_units
                WHERE sha256_hash IS NOT NULL
                GROUP BY sha256_hash
                HAVING COUNT(*) > 1
                ORDER BY sha256_hash
                """
            )
        ]

        contract_table = con.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='content_identity_contract'"
        ).fetchone()

        semantic_contract = {
            "status": "UNBOUND",
            "reason": (
                "No DB-native content_identity_contract table defines canonical payload "
                "fields/bytes, canonicalization, algorithm and version."
            ),
        }
        if contract_table:
            ccols = [
                r[1]
                for r in con.execute("PRAGMA table_info(content_identity_contract)")
            ]
            required_contract = {
                "version",
                "algorithm",
                "canonicalization",
                "payload_fields",
            }
            if required_contract.issubset(ccols):
                contracts = con.execute(
                    "SELECT version, algorithm, canonicalization, payload_fields "
                    "FROM content_identity_contract"
                ).fetchall()
                if len(contracts) == 1:
                    semantic_contract = {
                        "status": "DECLARED_NOT_RECOMPUTED",
                        "contract": {
                            "version": contracts[0][0],
                            "algorithm": contracts[0][1],
                            "canonicalization": contracts[0][2],
                            "payload_fields": contracts[0][3],
                        },
                        "reason": (
                            "A declaration exists, but this auditor cannot promote it until "
                            "stored hashes are independently recomputed from the declared payload."
                        ),
                    }

        snapshot_pass = integrity == "ok" and not nulls and not invalid and not dup_groups

        return {
            "database": str(db),
            "integrity_check": integrity,
            "rows": len(rows),
            "sha256_column_not_null_declared": cols["sha256_hash"]["notnull"],
            "sha256_null_rows": nulls,
            "sha256_invalid_format_rows": invalid,
            "duplicate_full_hash_groups": dup_groups,
            "snapshot_hash_uniqueness": "PASS" if snapshot_pass else "FAIL",
            "semantic_content_identity_contract": semantic_contract,
            "unique_constraint_migration_gate": (
                "HOLD_SEMANTIC_IDENTITY_UNBOUND"
                if semantic_contract["status"] != "RECOMPUTED_PASS"
                else "ELIGIBLE_FOR_SEPARATE_MIGRATION_COURT"
            ),
        }
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument(
        "--require-semantic-contract",
        action="store_true",
        help="exit non-zero until semantic identity is independently recomputable",
    )
    args = parser.parse_args()
    report = audit(args.database)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["snapshot_hash_uniqueness"] != "PASS":
        return 2
    if (
        args.require_semantic_contract
        and report["semantic_content_identity_contract"]["status"] != "RECOMPUTED_PASS"
    ):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
