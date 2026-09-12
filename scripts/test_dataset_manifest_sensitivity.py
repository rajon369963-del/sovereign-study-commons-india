#!/usr/bin/env python3
"""Hermetic negative-sensitivity court for scripts/verify_dataset_manifest.py.

Uses only tiny synthetic SQLite/Parquet assets in temporary repositories. It never
mutates committed data_lake bytes. The production verifier is copied verbatim and
invoked through its real CLI contract for every fixture.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_VERIFIER = ROOT / "scripts" / "verify_dataset_manifest.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_base_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "data_lake" / "sqlite").mkdir(parents=True)
    (repo / "data_lake" / "parquet").mkdir(parents=True)
    shutil.copy2(PRODUCTION_VERIFIER, repo / "scripts" / "verify_dataset_manifest.py")

    sqlite_path = repo / "data_lake" / "sqlite" / "synthetic.sqlite"
    with sqlite3.connect(sqlite_path) as con:
        con.execute("CREATE TABLE study_units (unit_id INTEGER PRIMARY KEY, marker TEXT NOT NULL)")
        con.execute("INSERT INTO study_units(marker) VALUES ('fixture-a'), ('fixture-b')")
        con.commit()

    parquet_path = repo / "data_lake" / "parquet" / "synthetic.parquet"
    con = duckdb.connect(database=":memory:")
    try:
        quoted = str(parquet_path).replace("'", "''")
        con.execute(
            "COPY (SELECT * FROM (VALUES (1, 'x'), (2, 'y')) AS t(unit_id, marker)) "
            f"TO '{quoted}' (FORMAT PARQUET)"
        )
    finally:
        con.close()

    manifest = {
        "assets": [
            {
                "path": "data_lake/sqlite/synthetic.sqlite",
                "format": "sqlite3",
                "primary_table": "study_units",
                "byte_size": sqlite_path.stat().st_size,
                "sha256": sha256(sqlite_path),
                "claimed_row_count": 2,
                "provenance_class": "SYNTHETIC_TEST_FIXTURE",
                "license_status": "TEST_ONLY/VERIFIED",
            },
            {
                "path": "data_lake/parquet/synthetic.parquet",
                "format": "parquet",
                "byte_size": parquet_path.stat().st_size,
                "sha256": sha256(parquet_path),
                "claimed_row_count": 2,
                "provenance_class": "SYNTHETIC_TEST_FIXTURE",
                "license_status": "TEST_ONLY/VERIFIED",
            },
        ]
    }
    write_manifest(repo, manifest)
    return repo


def read_manifest(repo: Path) -> dict:
    return json.loads((repo / "data_lake" / "dataset_manifest.json").read_text(encoding="utf-8"))


def write_manifest(repo: Path, manifest: dict) -> None:
    (repo / "data_lake" / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_verifier(repo: Path, *, verifier: Path | None = None) -> subprocess.CompletedProcess[str]:
    target = verifier or (repo / "scripts" / "verify_dataset_manifest.py")
    return subprocess.run(
        [sys.executable, str(target)],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=20,
    )


def fresh_fixture() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    holder = tempfile.TemporaryDirectory(prefix="manifest-sensitivity-")
    return holder, create_base_repo(Path(holder.name))


def require_pass(name: str, repo: Path) -> None:
    result = run_verifier(repo)
    if result.returncode != 0:
        raise AssertionError(f"{name}: expected PASS, rc={result.returncode}\n{result.stdout[-2000:]}")


def require_reject(name: str, repo: Path) -> None:
    result = run_verifier(repo)
    if result.returncode == 0:
        raise AssertionError(f"{name}: known-bad fixture unexpectedly passed\n{result.stdout[-2000:]}")
    print(f"[PASS] {name}: verifier rejected fixture with rc={result.returncode}")


def mutate_wrong_sha(repo: Path) -> None:
    manifest = read_manifest(repo)
    manifest["assets"][0]["sha256"] = "0" * 64
    write_manifest(repo, manifest)


def mutate_wrong_size(repo: Path) -> None:
    manifest = read_manifest(repo)
    manifest["assets"][0]["byte_size"] += 1
    write_manifest(repo, manifest)


def mutate_wrong_rowcount(repo: Path) -> None:
    manifest = read_manifest(repo)
    manifest["assets"][0]["claimed_row_count"] += 1
    write_manifest(repo, manifest)


def mutate_unlisted_physical_asset(repo: Path) -> None:
    extra = repo / "data_lake" / "sqlite" / "unlisted.sqlite"
    with sqlite3.connect(extra) as con:
        con.execute("CREATE TABLE study_units (unit_id INTEGER PRIMARY KEY)")
        con.execute("INSERT INTO study_units DEFAULT VALUES")
        con.commit()


def mutate_missing_physical_file(repo: Path) -> None:
    (repo / "data_lake" / "parquet" / "synthetic.parquet").unlink()


def mutate_duplicate_manifest_path(repo: Path) -> None:
    manifest = read_manifest(repo)
    manifest["assets"].append(copy.deepcopy(manifest["assets"][0]))
    write_manifest(repo, manifest)


def main() -> int:
    holder, repo = fresh_fixture()
    try:
        require_pass("KNOWN_GOOD_SYNTHETIC_SET", repo)
    finally:
        holder.cleanup()

    mutants = [
        ("WRONG_SHA_MANIFEST", mutate_wrong_sha),
        ("WRONG_SIZE_MANIFEST", mutate_wrong_size),
        ("WRONG_ROWCOUNT_MANIFEST", mutate_wrong_rowcount),
        ("UNLISTED_PHYSICAL_ASSET", mutate_unlisted_physical_asset),
        ("MANIFEST_ENTRY_MISSING_FILE", mutate_missing_physical_file),
        ("DUPLICATE_MANIFEST_PATH", mutate_duplicate_manifest_path),
    ]

    for name, mutate in mutants:
        holder, repo = fresh_fixture()
        try:
            mutate(repo)
            require_reject(name, repo)
        finally:
            holder.cleanup()

    # Mechanism-ablation oracle: the same known-bad fixture must NOT be accepted
    # if the production verifier is replaced by a no-op. We intentionally run
    # this no-op only inside the temporary fixture and assert that the court
    # observes the bypass as a false green.
    holder, repo = fresh_fixture()
    try:
        mutate_wrong_sha(repo)
        noop = repo / "scripts" / "noop_verifier.py"
        noop.write_text("raise SystemExit(0)\n", encoding="utf-8")
        bypass = run_verifier(repo, verifier=noop)
        if bypass.returncode != 0:
            raise AssertionError("NOOP_VERIFIER_MUTANT unexpectedly failed; ablation fixture is invalid")
        real = run_verifier(repo)
        if real.returncode == 0:
            raise AssertionError("production verifier failed to distinguish the bypass fixture")
        print("[PASS] NOOP_VERIFIER_BYPASS: court distinguishes bypass false-green from production rejection")
    finally:
        holder.cleanup()

    print("[PASS] manifest parity sensitivity court: known-good + 6 frozen mutants + bypass ablation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
