#!/usr/bin/env python3
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "data_lake/contracts/parquet_contracts_v1.json"
MANIFEST = ROOT / "data_lake/dataset_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def qpath(path: Path) -> str:
    return str(path).replace("'", "''")


def broad_readability_check(path: Path) -> None:
    con = duckdb.connect(database=":memory:")
    quoted = qpath(path)
    rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{quoted}')").fetchone()[0]
    schema = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{quoted}')").fetchall()
    assert rows > 0, f"{path}: zero rows"
    assert schema, f"{path}: empty schema"


def manifest_index() -> dict:
    data = json.loads(MANIFEST.read_text())
    return {a["path"]: a for a in data["assets"]}


def validate_contract(contract: dict, asset_path: Path, *, enforce_identity: bool = True, manifest_entry: dict | None = None) -> dict:
    con = duckdb.connect(database=":memory:")
    quoted = qpath(asset_path)
    rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{quoted}')").fetchone()[0]
    assert rows > 0, f"{asset_path}: zero rows"
    schema_rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{quoted}')").fetchall()
    schema = {r[0]: str(r[1]).upper() for r in schema_rows}

    if enforce_identity:
        observed_sha = sha256(asset_path)
        assert observed_sha == contract["asset_sha256"], (
            f"{contract['bundle_id']}: asset_sha256 expected={contract['asset_sha256']} observed={observed_sha}"
        )

    for column, expected_type in contract["required_columns"].items():
        assert column in schema, f"{contract['bundle_id']}: required column missing: {column}"
        observed_type = schema[column]
        assert observed_type == expected_type.upper(), (
            f"{contract['bundle_id']}: {column} type expected={expected_type} observed={observed_type}"
        )

    if manifest_entry is not None:
        for field, expected in contract["manifest_contract"].items():
            observed = manifest_entry.get(field)
            assert observed == expected, (
                f"{contract['bundle_id']}: manifest {field} expected={expected!r} observed={observed!r}"
            )

    query = contract["consumer_query"].replace("{asset}", quoted)
    consumer_rows = con.execute(query).fetchall()
    assert consumer_rows, f"{contract['bundle_id']}: consumer query returned no rows"
    return {"rows": rows, "schema": schema, "consumer_result_rows": len(consumer_rows)}


def self_test_mutants() -> None:
    fixture_contract = {
        "bundle_id": "synthetic-exam-branch-contract",
        "required_columns": {"exam_branch": "VARCHAR"},
        "consumer_query": "SELECT exam_branch, COUNT(*) AS units_count FROM read_parquet('{asset}') GROUP BY exam_branch ORDER BY exam_branch",
    }
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        con = duckdb.connect(database=":memory:")
        good = td / "good.parquet"
        bad_type = td / "bad-type.parquet"
        bad_rename = td / "bad-rename.parquet"
        con.execute(f"COPY (SELECT 'GATE_EE'::VARCHAR AS exam_branch) TO '{qpath(good)}' (FORMAT PARQUET)")
        con.execute(f"COPY (SELECT 7::INTEGER AS exam_branch) TO '{qpath(bad_type)}' (FORMAT PARQUET)")
        con.execute(f"COPY (SELECT 'GATE_EE'::VARCHAR AS exam_track) TO '{qpath(bad_rename)}' (FORMAT PARQUET)")

        validate_contract(fixture_contract, good, enforce_identity=False)

        for mutant, expected_marker in ((bad_type, "type expected"), (bad_rename, "required column missing")):
            broad_readability_check(mutant)
            try:
                validate_contract(fixture_contract, mutant, enforce_identity=False)
            except AssertionError as exc:
                assert expected_marker in str(exc), (mutant, exc)
            else:
                raise AssertionError(f"known-bad readable mutant unexpectedly passed contract: {mutant}")

    print("PASS: readable/non-empty schema mutants are rejected by the reviewed contract")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test-mutants", action="store_true")
    args = parser.parse_args()

    contracts = json.loads(CONTRACTS.read_text())
    manifests = manifest_index()
    report = []
    for contract in contracts["assets"]:
        asset_rel = contract["asset_path"]
        asset = ROOT / asset_rel
        assert asset.exists(), f"contract asset missing: {asset_rel}"
        assert asset_rel in manifests, f"manifest entry missing: {asset_rel}"
        result = validate_contract(contract, asset, manifest_entry=manifests[asset_rel])
        report.append({"bundle_id": contract["bundle_id"], "asset_path": asset_rel, **result})

    if args.self_test_mutants:
        self_test_mutants()

    print(json.dumps({"parquet_contracts": report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
