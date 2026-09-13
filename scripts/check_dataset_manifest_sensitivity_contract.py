#!/usr/bin/env python3
"""Fail closed when the runtime manifest-sensitivity mutant inventory drifts.

The reviewed contract is intentionally separate from the executable court so a
silent implementation-only removal/rename cannot reduce required semantic
coverage while CI stays green.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COURT = ROOT / "scripts" / "test_dataset_manifest_sensitivity.py"
CONTRACT = ROOT / "ci" / "dataset-manifest-sensitivity-contract.json"


def runtime_mutant_ids() -> list[str]:
    tree = ast.parse(COURT.read_text(encoding="utf-8"), filename=str(COURT))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "mutants" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            raise SystemExit("manifest sensitivity contract HOLD: mutants inventory is not a literal list/tuple")
        ids: list[str] = []
        for item in node.value.elts:
            if not isinstance(item, ast.Tuple) or len(item.elts) != 2:
                raise SystemExit("manifest sensitivity contract HOLD: malformed mutant tuple")
            name = item.elts[0]
            if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
                raise SystemExit("manifest sensitivity contract HOLD: mutant ID must be a literal string")
            ids.append(name.value)
        return ids
    raise SystemExit("manifest sensitivity contract HOLD: runtime mutants inventory not found")


def canonical_digest(ids: list[str]) -> str:
    payload = json.dumps(ids, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = contract["expected_mutant_ids"]
    expected_digest = contract["expected_inventory_sha256"]
    observed = runtime_mutant_ids()
    observed_digest = canonical_digest(observed)

    if canonical_digest(expected) != expected_digest:
        raise SystemExit("manifest sensitivity contract HOLD: frozen authority digest is internally inconsistent")
    if observed != expected or observed_digest != expected_digest:
        raise SystemExit(
            "manifest sensitivity contract HOLD: runtime inventory drift; "
            f"expected={expected} observed={observed} "
            f"expected_sha256={expected_digest} observed_sha256={observed_digest}"
        )

    print(
        "[PASS] manifest sensitivity frozen authority: "
        f"version={contract['contract_version']} inventory_sha256={observed_digest} mutants={len(observed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
