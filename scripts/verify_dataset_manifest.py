#!/usr/bin/env python3
"""
Reproducible Dataset Manifest Verification Harness (Issue #2 / #86).

Verifies committed data lake assets against data_lake/dataset_manifest.json:
- Exact governed membership (manifest paths == physical SQLite/Parquet paths)
- Duplicate/ambiguous manifest path rejection
- Exact SHA-256 hash match
- Byte size match
- Row count match via native SQLite and DuckDB
- Explicit provenance and licensing status audit (flags UNKNOWN/REVIEW_REQUIRED)
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_sqlite_row_count(path: Path, table_name: str) -> int:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cur = con.execute(f"SELECT COUNT(*) FROM \"{table_name}\";")
        return cur.fetchone()[0]
    finally:
        con.close()


def get_parquet_row_count(path: Path) -> int:
    if HAS_DUCKDB:
        con = duckdb.connect()
        try:
            res = con.execute(f"SELECT COUNT(*) FROM '{path}';").fetchone()
            return res[0]
        finally:
            con.close()
    import subprocess
    out = subprocess.check_output(["duckdb", "-c", f"SELECT COUNT(*) FROM '{path}';"])
    lines = [line.strip() for line in out.decode().splitlines() if line.strip()]
    for line in reversed(lines):
        line_clean = line.strip("│ ").strip()
        if line_clean.isdigit():
            return int(line_clean)
    raise ValueError(f"Could not parse row count from duckdb output: {out}")


def governed_physical_paths(repo_root: Path) -> set[str]:
    data_root = repo_root / "data_lake"
    paths = set()
    for pattern in ("sqlite/*.sqlite", "parquet/*.parquet"):
        for path in data_root.glob(pattern):
            if path.is_file():
                paths.add(path.relative_to(repo_root).as_posix())
    return paths


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = repo_root / "data_lake" / "dataset_manifest.json"

    if not manifest_path.is_file():
        print(f"[-] FATAL: Manifest not found at {manifest_path}", file=sys.stderr)
        return 1

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assets = manifest.get("assets", [])
    if not assets:
        print("[-] FATAL: Manifest contains no assets", file=sys.stderr)
        return 1

    errors = []
    manifest_paths = [asset.get("path") for asset in assets]
    invalid_paths = [p for p in manifest_paths if not isinstance(p, str) or not p]
    if invalid_paths:
        errors.append("manifest contains missing/invalid asset path")

    path_counts = Counter(p for p in manifest_paths if isinstance(p, str) and p)
    duplicates = sorted(p for p, count in path_counts.items() if count != 1)
    if duplicates:
        errors.append(f"duplicate/ambiguous manifest paths: {duplicates}")

    physical_paths = governed_physical_paths(repo_root)
    declared_paths = set(path_counts)
    unlisted = sorted(physical_paths - declared_paths)
    missing = sorted(declared_paths - physical_paths)
    if unlisted:
        errors.append(f"governed physical assets missing from manifest: {unlisted}")
    if missing:
        errors.append(f"manifest entries missing physical governed assets: {missing}")

    print(f"=== Verifying Dataset Manifest ({len(assets)} declared assets) ===")
    print(json.dumps({
        "manifest_asset_count": len(assets),
        "unique_manifest_path_count": len(declared_paths),
        "physical_governed_asset_count": len(physical_paths),
        "duplicate_paths": duplicates,
        "unlisted_physical_assets": unlisted,
        "missing_physical_assets": missing,
    }, indent=2, sort_keys=True))

    for asset in assets:
        rel_path = asset.get("path")
        expected_size = asset.get("byte_size")
        expected_sha = asset.get("sha256")
        expected_rows = asset.get("claimed_row_count")
        provenance = asset.get("provenance_class")
        license_status = asset.get("license_status")

        if not isinstance(rel_path, str) or not rel_path:
            continue
        abs_path = repo_root / rel_path
        print(f"\n[+] Inspecting: {rel_path}")

        if not abs_path.is_file():
            print("    [!] Missing file!")
            continue

        actual_size = abs_path.stat().st_size
        if actual_size != expected_size:
            errors.append(f"{rel_path}: size mismatch (expected {expected_size}, got {actual_size})")
            print(f"    [!] Size mismatch: {actual_size} != {expected_size}")
        else:
            print(f"    [✓] Size verified: {actual_size} bytes")

        actual_sha = compute_sha256(abs_path)
        if actual_sha != expected_sha:
            errors.append(f"{rel_path}: SHA256 mismatch (expected {expected_sha}, got {actual_sha})")
            print(f"    [!] SHA256 mismatch: {actual_sha}")
        else:
            print(f"    [✓] SHA256 verified: {actual_sha[:16]}...")

        try:
            if asset.get("format") == "sqlite3":
                actual_rows = get_sqlite_row_count(abs_path, asset.get("primary_table", "study_units"))
            else:
                actual_rows = get_parquet_row_count(abs_path)
            if actual_rows != expected_rows:
                errors.append(f"{rel_path}: row count mismatch (expected {expected_rows}, got {actual_rows})")
                print(f"    [!] Row count mismatch: {actual_rows} != {expected_rows}")
            else:
                print(f"    [✓] Row count verified: {actual_rows} rows")
        except Exception as e:
            errors.append(f"{rel_path}: row count verification failed: {e}")
            print(f"    [!] Row count verification error: {e}")

        if license_status == "UNKNOWN/REVIEW_REQUIRED":
            print(f"    [⚠️] Provenance boundary: {provenance} | License: {license_status}")
        else:
            print(f"    [✓] Provenance: {provenance} | License: {license_status}")

    print("\n" + "=" * 60)
    if errors:
        print(f"[-] FAIL: {len(errors)} error(s) found during manifest verification:", file=sys.stderr)
        for err in errors:
            print(f"    - {err}", file=sys.stderr)
        return 2

    print("[✓] PASS: Manifest exactly matches governed physical membership, byte sizes, SHA-256 hashes, and row counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
