#!/usr/bin/env python3
"""Fail closed on fabricated verification semantics in automation-facing repo files.

This narrow lint does not prove factual correctness. It only blocks a small set of
previously observed false-green labels from re-entering executable/agent surfaces.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "scripts" / "gemini_spark_daemon.py",
    ROOT / ".agents" / "skills" / "sovereign-full-yolo-factory" / "SKILL.md",
    ROOT / ".agents" / "skills" / "sovereign-hyper-interconnection" / "SKILL.md",
]

FORBIDDEN = {
    "PASSED_PHYSICAL_VERIFICATION": "physical verification label without an executed verifier receipt",
    "SUCCESS_PHYSICAL": "physical-success label without an executed verifier receipt",
    "verified via native C17 kernels": "C17 execution claim without an execution receipt",
    "Cross-referenced against 100 historical competitor patterns": "completed competitor-census claim without a manifest",
    "Multi-Account Quota Harvester": "quota-evasion framing",
}

REQUIRED = {
    ROOT / "scripts" / "gemini_spark_daemon.py": [
        "SYNTHESIZED_UNVERIFIED",
        '"executed": False',
        '"git_commit_attempted": False',
    ],
    ROOT / ".agents" / "skills" / "sovereign-full-yolo-factory" / "SKILL.md": [
        "LOCAL_ONLY",
        "SYNTHESIZED_UNVERIFIED",
        "SHA-256 digest proves byte identity only",
    ],
    ROOT / ".agents" / "skills" / "sovereign-hyper-interconnection" / "SKILL.md": [
        "TARGET_100_COMPETITORS",
        "TARGET_100_PRACTITIONER_INSIGHTS",
        "TARGET_100_REUSABLE_WHEELS",
    ],
}


def main() -> int:
    errors = []
    for path in TARGETS:
        if not path.is_file():
            errors.append(f"missing required truth surface: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle, reason in FORBIDDEN.items():
            if needle in text:
                errors.append(f"{path.relative_to(ROOT)} contains forbidden {needle!r}: {reason}")
        for needle in REQUIRED.get(path, []):
            if needle not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required boundary {needle!r}")

    if errors:
        print("AUTOMATION_TRUTH_LINT=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AUTOMATION_TRUTH_LINT=PASS_BOUNDED")
    print("Scope: false-green label hygiene only; semantic/physical correctness remains separately verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
