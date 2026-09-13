#!/usr/bin/env python3
"""Mechanism-sensitive court for the required federation verifier workflow binding.

The verifier helper can remain perfectly healthy while the required GitHub Actions
surface silently stops requesting live-provider authority. This court binds the
required workflow step to the production invocation contract and includes a
known-bad mutant that omits ``--live-provider``.
"""

from __future__ import annotations

import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "viral-showcase.yml"
STEP_NAME = "Verify Federation Evidence Manifest"


class WorkflowContractError(AssertionError):
    pass


def _extract_run_command(workflow_text: str, step_name: str = STEP_NAME) -> str:
    lines = workflow_text.splitlines()
    marker = f"- name: {step_name}"
    step_index = next(
        (idx for idx, line in enumerate(lines) if line.strip() == marker),
        None,
    )
    if step_index is None:
        raise WorkflowContractError(f"required workflow step missing: {step_name}")

    run_index = None
    for idx in range(step_index + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped.startswith("- name:"):
            break
        if stripped == "run: |":
            run_index = idx
            break
    if run_index is None:
        raise WorkflowContractError(f"required step has no shell run block: {step_name}")

    run_indent = len(lines[run_index]) - len(lines[run_index].lstrip())
    command_lines: list[str] = []
    for line in lines[run_index + 1 :]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= run_indent:
            break
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        command_lines.append(stripped.removesuffix("\\").strip())

    if not command_lines:
        raise WorkflowContractError(f"required step has an empty run block: {step_name}")
    return " ".join(command_lines)


def _assert_live_provider_contract(command: str) -> None:
    argv = shlex.split(command)
    expected_prefix = ["python3", "scripts/verify_federation_manifest.py"]
    if argv[:2] != expected_prefix:
        raise WorkflowContractError(
            "required workflow must execute the canonical federation verifier directly"
        )

    required_pairs = {
        "--verify": "federation-evidence-manifest.json",
        "--repo": "sovereign-study-commons-india",
        "--authority-context": "auto",
    }
    for flag, expected_value in required_pairs.items():
        try:
            pos = argv.index(flag)
            actual = argv[pos + 1]
        except (ValueError, IndexError) as exc:
            raise WorkflowContractError(f"missing required verifier binding: {flag}") from exc
        if actual != expected_value:
            raise WorkflowContractError(
                f"wrong verifier binding for {flag}: {actual!r} != {expected_value!r}"
            )

    if "--live-provider" not in argv:
        raise WorkflowContractError(
            "required workflow bypasses live-provider currentness authority"
        )


def test_required_workflow_binds_live_provider() -> None:
    command = _extract_run_command(WORKFLOW.read_text(encoding="utf-8"))
    _assert_live_provider_contract(command)


def test_flag_removal_mutant_is_rejected() -> None:
    known_bad = (
        "python3 scripts/verify_federation_manifest.py "
        "--verify federation-evidence-manifest.json "
        "--repo sovereign-study-commons-india "
        "--authority-context auto"
    )
    try:
        _assert_live_provider_contract(known_bad)
    except WorkflowContractError:
        return
    raise AssertionError("known-bad workflow mutant unexpectedly passed the contract court")


if __name__ == "__main__":
    test_required_workflow_binds_live_provider()
    test_flag_removal_mutant_is_rejected()
    print("WORKFLOW_CONTRACT_COURT=PASS")
