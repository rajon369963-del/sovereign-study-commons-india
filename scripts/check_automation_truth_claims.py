#!/usr/bin/env python3
"""Fail closed on known fabricated automation truth semantics.

This deterministic lint is a claim-registration guard, not a factual verifier.
A VERIFIED_<N>_* or verified-count promotion is allowed only when it is explicitly
registered in a reviewable manifest with a matching count and existing evidence paths.
"""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "automation_truth_claim_manifest.json"
SELF = Path(__file__).resolve()

SCAN_ROOTS = [
    ROOT / "scripts",
    ROOT / ".agents",
    ROOT / ".github" / "workflows",
]
TOP_LEVEL_SURFACES = [ROOT / "README.md", ROOT / "ROADMAP.md"]
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".txt", ".toml"}

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

VERIFIED_TOKEN_RE = re.compile(r"\bVERIFIED_(\d+)_([A-Z0-9_]+)\b")
VERIFIED_PROSE_RE = re.compile(
    r"\b(?:verified|validated|confirmed)\s+(\d+)\s+"
    r"(?:competitors?|practitioner\s+insights?|reusable\s+wheels?|hacks?|tips?|tricks?)\b",
    re.IGNORECASE,
)


def load_manifest(errors):
    if not MANIFEST.is_file():
        errors.append("missing automation_truth_claim_manifest.json")
        return {}, {}
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid automation truth manifest: {exc}")
        return {}, {}
    claims = payload.get("claims")
    if payload.get("version") != 1 or not isinstance(claims, list):
        errors.append("manifest must contain version=1 and claims=[]")
        return {}, {}
    by_token, by_phrase = {}, {}
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"manifest claim[{i}] must be an object")
            continue
        token = claim.get("token")
        phrase = claim.get("phrase")
        count = claim.get("count")
        evidence_paths = claim.get("evidence_paths")
        if not isinstance(count, int) or count < 0:
            errors.append(f"manifest claim[{i}] has invalid count")
            continue
        if not isinstance(evidence_paths, list) or not evidence_paths:
            errors.append(f"manifest claim[{i}] requires non-empty evidence_paths")
            continue
        for rel in evidence_paths:
            if not isinstance(rel, str) or not (ROOT / rel).is_file():
                errors.append(f"manifest claim[{i}] evidence path missing: {rel!r}")
        if token:
            if token in by_token:
                errors.append(f"duplicate manifest token: {token}")
            by_token[token] = claim
        if phrase:
            key = phrase.casefold()
            if key in by_phrase:
                errors.append(f"duplicate manifest phrase: {phrase}")
            by_phrase[key] = claim
        if not token and not phrase:
            errors.append(f"manifest claim[{i}] needs token or phrase")
    return by_token, by_phrase


def iter_surfaces():
    seen = set()
    for base in SCAN_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                resolved = path.resolve()
                if resolved not in {SELF, MANIFEST.resolve()} and resolved not in seen:
                    seen.add(resolved)
                    yield path
    for path in TOP_LEVEL_SURFACES:
        if path.is_file() and path.resolve() not in seen:
            yield path


def main() -> int:
    errors = []
    by_token, by_phrase = load_manifest(errors)

    for path, needles in REQUIRED.items():
        if not path.is_file():
            errors.append(f"missing required truth surface: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required boundary {needle!r}")

    for path in iter_surfaces():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT)
        for needle, reason in FORBIDDEN.items():
            if needle in text:
                errors.append(f"{rel} contains forbidden {needle!r}: {reason}")
        for match in VERIFIED_TOKEN_RE.finditer(text):
            token, count_text = match.group(0), match.group(1)
            claim = by_token.get(token)
            if claim is None:
                errors.append(f"{rel} contains unmanifested verified-count token {token!r}")
            elif claim["count"] != int(count_text):
                errors.append(f"{rel} token {token!r} count disagrees with manifest")
        for match in VERIFIED_PROSE_RE.finditer(text):
            phrase, count_text = match.group(0), match.group(1)
            claim = by_phrase.get(phrase.casefold())
            if claim is None:
                errors.append(f"{rel} contains unmanifested verified-count phrase {phrase!r}")
            elif claim["count"] != int(count_text):
                errors.append(f"{rel} phrase {phrase!r} count disagrees with manifest")

    if errors:
        print("AUTOMATION_TRUTH_LINT=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AUTOMATION_TRUTH_LINT=PASS_BOUNDED")
    print("Scope: deterministic claim-registration hygiene; semantic/physical correctness remains separately verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
