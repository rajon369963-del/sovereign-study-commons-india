#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "data_lake/contracts/parquet_contracts_v1.json"
MANIFEST = ROOT / "data_lake/dataset_manifest.json"
README = ROOT / "README.md"
QUICK_QUERY_HEADING = "## Quick local query (DuckDB)"
QUICK_QUERY_LOCATOR = "README.md#quick-local-query"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def qpath(path: Path) -> str:
    return str(path).replace("'", "''")


def normalize_reviewed_sql(sql: str) -> str:
    normalized = sql.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.rstrip("\n") + "\n"


def extract_reviewed_query(readme_bytes: bytes, locator: str) -> str:
    assert locator == QUICK_QUERY_LOCATOR, f"unsupported consumer source locator: {locator}"
    text = readme_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    headings = [i for i, line in enumerate(lines) if line == QUICK_QUERY_HEADING]
    assert len(headings) == 1, f"README source heading expected exactly once, observed={len(headings)}"

    section_start = headings[0] + 1
    section_end = len(lines)
    for i in range(section_start, len(lines)):
        if lines[i].startswith("## "):
            section_end = i
            break

    sql_blocks = []
    i = section_start
    while i < section_end:
        if lines[i].strip().lower() == "```sql":
            close = i + 1
            while close < section_end and lines[close].strip() != "```":
                close += 1
            assert close < section_end, "README Quick local query SQL fence is unterminated"
            sql_blocks.append("\n".join(lines[i + 1 : close]))
            i = close
        i += 1

    assert len(sql_blocks) == 1, f"README source SQL fence expected exactly once, observed={len(sql_blocks)}"
    return normalize_reviewed_sql(sql_blocks[0])


def validate_reviewed_source(contract: dict, readme_bytes: bytes) -> str:
    query = extract_reviewed_query(readme_bytes, contract["consumer_contract_source"])
    observed = hashlib.sha256(query.encode("utf-8")).hexdigest()
    expected = contract["reviewed_source_sha256"]
    assert observed == expected, (
        f"{contract['bundle_id']}: reviewed source sha256 expected={expected} observed={observed}"
    )
    return query


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


def validate_contract(
    contract: dict,
    asset_path: Path,
    *,
    enforce_identity: bool = True,
    manifest_entry: dict | None = None,
    consumer_query: str | None = None,
) -> dict:
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

    query = consumer_query
    if query is None:
        assert contract.get("consumer_query_authority") == "fixture-only-non-authoritative", (
            f"{contract['bundle_id']}: embedded consumer query cannot be authoritative"
        )
        query = contract["consumer_query"].replace("{asset}", quoted)

    previous_cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        consumer_rows = con.execute(query).fetchall()
    finally:
        os.chdir(previous_cwd)
    assert consumer_rows, f"{contract['bundle_id']}: consumer query returned no rows"
    return {"rows": rows, "schema": schema, "consumer_result_rows": len(consumer_rows)}


def expect_source_failure(contract: dict, readme_bytes: bytes, marker: str) -> None:
    try:
        validate_reviewed_source(contract, readme_bytes)
    except AssertionError as exc:
        assert marker in str(exc), exc
    else:
        raise AssertionError(f"known-bad README source mutant unexpectedly passed: {marker}")


def self_test_mutants() -> None:
    fixture_contract = {
        "bundle_id": "synthetic-exam-branch-contract",
        "required_columns": {"exam_branch": "VARCHAR"},
        "consumer_query": "SELECT exam_branch, COUNT(*) AS units_count FROM read_parquet('{asset}') GROUP BY exam_branch ORDER BY exam_branch",
        "consumer_query_authority": "fixture-only-non-authoritative",
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

        source_sql = f"SELECT exam_branch, COUNT(*) AS units_count\nFROM '{qpath(good)}'\nGROUP BY exam_branch;\n"
        source_contract = {
            "bundle_id": "synthetic-reviewed-source-contract",
            "consumer_contract_source": QUICK_QUERY_LOCATOR,
            "reviewed_source_sha256": hashlib.sha256(source_sql.encode("utf-8")).hexdigest(),
        }
        source = f"# Fixture\n\n{QUICK_QUERY_HEADING}\n\n```sql\n{source_sql}```\n".encode()
        assert validate_reviewed_source(source_contract, source) == source_sql
        assert validate_reviewed_source(source_contract, source.replace(b"\n", b"\r\n")) == source_sql

        drift = source.replace(b"GROUP BY exam_branch;", b"GROUP BY exam_branch ORDER BY exam_branch;")
        expect_source_failure(source_contract, drift, "reviewed source sha256")
        expect_source_failure(source_contract, source.replace(QUICK_QUERY_HEADING.encode(), b"## Renamed query"), "source heading")
        expect_source_failure(source_contract, source + source, "source heading")
        bad_digest = dict(source_contract, reviewed_source_sha256="0" * 64)
        expect_source_failure(bad_digest, source, "reviewed source sha256")

    print("PASS: readable/schema and README-source identity mutants are rejected by the reviewed contract")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test-mutants", action="store_true")
    args = parser.parse_args()

    contracts = json.loads(CONTRACTS.read_text())
    manifests = manifest_index()
    readme_bytes = README.read_bytes()
    report = []
    for contract in contracts["assets"]:
        asset_rel = contract["asset_path"]
        asset = ROOT / asset_rel
        assert asset.exists(), f"contract asset missing: {asset_rel}"
        assert asset_rel in manifests, f"manifest entry missing: {asset_rel}"
        reviewed_query = validate_reviewed_source(contract, readme_bytes)
        result = validate_contract(
            contract,
            asset,
            manifest_entry=manifests[asset_rel],
            consumer_query=reviewed_query,
        )
        report.append({"bundle_id": contract["bundle_id"], "asset_path": asset_rel, **result})

    if args.self_test_mutants:
        self_test_mutants()

    print(json.dumps({"parquet_contracts": report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
