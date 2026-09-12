#!/usr/bin/env python3
"""Bounded cross-guard for the currently required data-integrity job."""
from __future__ import annotations

import sys
from pathlib import Path

WORKFLOW = Path(".github/workflows/data-integrity.yml")
TARGET_JOB = "verify-data-lake"
TARGET_JOB_NAME = "verify-data-lake"
REQUIRED_STEPS = {
    "Verify dataset manifest parity": "python scripts/verify_dataset_manifest.py",
    "Verify manifest parity negative sensitivity": "python scripts/test_dataset_manifest_sensitivity.py",
}


class StructureError(RuntimeError):
    pass


def _job_block(text: str, job_key: str) -> list[str]:
    lines = text.splitlines()
    marker = f"  {job_key}:"
    try:
        start = lines.index(marker)
    except ValueError as exc:
        raise StructureError(f"missing required job {job_key!r}") from exc
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            end = index
            break
    return lines[start:end]


def _active_named_steps(job_lines: list[str]) -> dict[str, str]:
    try:
        steps_index = job_lines.index("    steps:")
    except ValueError as exc:
        raise StructureError("required job has no active steps block") from exc
    step_lines = job_lines[steps_index + 1 :]
    starts = [i for i, line in enumerate(step_lines) if line.startswith("      - name:")]
    steps: dict[str, str] = {}
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(step_lines)
        block = step_lines[start:end]
        name = block[0].split(":", 1)[1].strip().strip("'\"")
        run_lines = [line for line in block[1:] if line.startswith("        run:")]
        if len(run_lines) != 1:
            continue
        raw = run_lines[0].split(":", 1)[1].strip()
        if not raw or raw in {"|", ">", "|-", ">-"}:
            continue
        steps[name] = raw.strip("'\"")
    return steps


def assert_required_structure(text: str) -> None:
    job = _job_block(text, TARGET_JOB)
    if f"    name: {TARGET_JOB_NAME}" not in job:
        raise StructureError(
            f"required job {TARGET_JOB!r} must emit current protected check name {TARGET_JOB_NAME!r}"
        )
    steps = _active_named_steps(job)
    for name, command in REQUIRED_STEPS.items():
        observed = steps.get(name)
        if observed != command:
            raise StructureError(
                f"required active step {name!r} must run {command!r}; observed={observed!r}"
            )


def _remove_step(text: str, step_name: str) -> str:
    lines = text.splitlines(keepends=True)
    marker = f"      - name: {step_name}"
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == marker), None)
    if start is None:
        raise AssertionError(f"fixture cannot find step {step_name!r}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("      - name:") or (
            lines[index].startswith("  ") and not lines[index].startswith("    ")
        ):
            end = index
            break
    return "".join(lines[:start] + lines[end:])


def _must_reject(label: str, mutant: str) -> None:
    try:
        assert_required_structure(mutant)
    except StructureError:
        print(f"PASS_NEGATIVE {label}")
        return
    raise AssertionError(f"false-green structure mutant: {label}")


def run_hostile_court(text: str) -> None:
    assert_required_structure(text)
    print("PASS_POSITIVE current-active-structure")
    removed_parity = _remove_step(text, "Verify dataset manifest parity")
    _must_reject("remove-production-verifier-step", removed_parity)
    neutralized = text.replace(
        "        run: python scripts/verify_dataset_manifest.py",
        "        run: true",
        1,
    )
    if neutralized == text:
        raise AssertionError("fixture could not neutralize production verifier invocation")
    _must_reject("neutralize-production-verifier-with-true", neutralized)
    dead_text = removed_parity.replace(
        "    steps:\n",
        "    steps:\n"
        "      - name: Dead documentation scalar\n"
        "        run: |\n"
        "          cat <<'EOF'\n"
        "          - name: Verify dataset manifest parity\n"
        "            run: python scripts/verify_dataset_manifest.py\n"
        "          EOF\n",
        1,
    )
    _must_reject("command-present-only-in-dead-scalar", dead_text)
    removed_sensitivity = _remove_step(text, "Verify manifest parity negative sensitivity")
    _must_reject("remove-negative-sensitivity-step", removed_sensitivity)


def main() -> int:
    try:
        text = WORKFLOW.read_text(encoding="utf-8")
        run_hostile_court(text)
    except (OSError, StructureError, AssertionError) as exc:
        print(f"HOLD_REQUIRED_CHECK_SELF_BYPASS_GUARD: {exc}", file=sys.stderr)
        return 1
    print("REQUIRED_CHECK_SELF_BYPASS_RESISTANCE_PASS_BOUNDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
