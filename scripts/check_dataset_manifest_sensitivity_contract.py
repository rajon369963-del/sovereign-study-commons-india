#!/usr/bin/env python3
"""Fail closed when manifest-sensitivity authority or trigger coverage drifts.

The reviewed contract is intentionally separate from the executable court so a
silent implementation-only removal/rename cannot reduce required semantic
coverage while CI stays green. The same checker also binds the frozen authority
files to the production Data integrity push trigger so a main-branch authority
change cannot silently skip the court.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COURT = ROOT / "scripts" / "test_dataset_manifest_sensitivity.py"
CONTRACT = ROOT / "ci" / "dataset-manifest-sensitivity-contract.json"
WORKFLOW = ROOT / ".github" / "workflows" / "data-integrity.yml"
REQUIRED_PUSH_PATHS = {
    "scripts/test_dataset_manifest_sensitivity.py",
    "scripts/check_dataset_manifest_sensitivity_contract.py",
    "ci/dataset-manifest-sensitivity-contract.json",
    ".github/workflows/data-integrity.yml",
}


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


def workflow_push_paths() -> set[str]:
    """Parse the bounded `on.push.paths` list without adding a YAML dependency."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    in_push = False
    in_paths = False
    paths: set[str] = set()
    for line in lines:
        if line == "  push:":
            in_push = True
            in_paths = False
            continue
        if in_push and line.startswith("  ") and not line.startswith("    ") and line.strip():
            break
        if not in_push:
            continue
        if line == "    paths:":
            in_paths = True
            continue
        if in_paths:
            if not line.startswith("      - "):
                if line.strip():
                    break
                continue
            value = line.split("-", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            paths.add(value)
    return paths


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

    push_paths = workflow_push_paths()
    missing_push_paths = sorted(REQUIRED_PUSH_PATHS - push_paths)
    if missing_push_paths:
        raise SystemExit(
            "manifest sensitivity contract HOLD: Data integrity push trigger omits authority surface(s): "
            f"{missing_push_paths}"
        )

    print(
        "[PASS] manifest sensitivity frozen authority: "
        f"version={contract['contract_version']} inventory_sha256={observed_digest} mutants={len(observed)} "
        f"trigger_paths={len(REQUIRED_PUSH_PATHS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
