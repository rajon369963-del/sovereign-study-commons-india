#!/usr/bin/env python3
"""Fail closed on unsupported automation truth promotions.

This deterministic lint is a claim-registration guard, not a factual verifier.
A bounded verified-count token/prose promotion is allowed only when a reviewable
manifest binds that exact claim to a matching count, item locators, local
evidence paths, a source revision, a generation timestamp, and an explicit
verifier boundary.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "automation_truth_claim_manifest.json"
SELF = Path(__file__).resolve()

SCAN_ROOTS = [ROOT / "scripts", ROOT / ".agents", ROOT / ".github" / "workflows"]
TOP_LEVEL_SURFACES = [ROOT / "README.md", ROOT / "ROADMAP.md"]
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".txt", ".toml"}

FORBIDDEN = {
    "PASSED_PHYSICAL_VERIFICATION": "physical verification label without an executed verifier receipt",
    "SUCCESS_PHYSICAL": "physical-success label without an executed verifier receipt",
    "verified via native C17 kernels": "C17 execution claim without an execution receipt",
    "Cross-referenced against 100 historical competitor patterns": "completed competitor-census claim without a manifest",
    "Multi-Account Quota Harvester": "quota-evasion framing",
}

# Bounded aliases of the same historical false-green status family. These are
# deliberately token/status shaped rather than fuzzy prose, to avoid policing
# ordinary contributor discussion.
FORBIDDEN_STATUS_RE = re.compile(
    r"\b(?:PASSED?|SUCCESS|SUCCESSFUL|VERIFIED|VALIDATED|CONFIRMED)[_-]PHYSICAL(?:[_-]VERIFICATION)?\b"
    r"|\bPHYSICAL[_-](?:PASS(?:ED)?|SUCCESS|VERIFIED|VALIDATED|CONFIRMED)\b",
    re.IGNORECASE,
)

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

COUNT_TEXT = r"(?:\d+|one(?:\s+|-)hundred)"
FAMILY_TEXT = r"(?:competitors?|competitor\s+records?|practitioner\s+insights?|reusable\s+wheels?|hacks?|tips?|tricks?)"
STATUS_TEXT = r"(?:verified|validated|confirmed)"
STATUS_ADVERB_TEXT = r"(?:(?:independently|fully)\s+)?"
VERIFIED_TOKEN_RES = [
    re.compile(r"\bVERIFIED_(\d+)_([A-Z0-9_]+)\b", re.IGNORECASE),
    re.compile(r"\bVERIFIED-(\d+)-([A-Z0-9-]+)\b", re.IGNORECASE),
]
VERIFIED_PROSE_RES = [
    re.compile(
        rf"\b{STATUS_TEXT}(?:\s+(?:exactly|all|a\s+total\s+of))?\s+({COUNT_TEXT})\s+({FAMILY_TEXT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:all\s+)?({COUNT_TEXT})\s+({FAMILY_TEXT})\s+(?:(?:were|are)\s+(?:all\s+)?{STATUS_ADVERB_TEXT}|have\s+(?:(?:all\s+)?been\s+{STATUS_ADVERB_TEXT}|(?:all\s+)?(?:independently|fully)\s+been\s+))?{STATUS_TEXT}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:all\s+)?({COUNT_TEXT})\s+{STATUS_ADVERB_TEXT}{STATUS_TEXT}\s+({FAMILY_TEXT})\b",
        re.IGNORECASE,
    ),
]
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)
MAX_FUTURE_SKEW = timedelta(minutes=5)


def _count_value(text):
    if text.isdigit():
        return int(text)
    normalized = re.sub(r"[-\s]+", " ", text.strip().casefold())
    if normalized == "one hundred":
        return 100
    return None


def _canonical_family(text):
    if not isinstance(text, str):
        return None
    normalized = re.sub(r"[-_\s]+", " ", text.strip().casefold())
    aliases = {
        "competitor": "competitors",
        "competitors": "competitors",
        "competitor record": "competitors",
        "competitor records": "competitors",
        "practitioner insight": "practitioner_insights",
        "practitioner insights": "practitioner_insights",
        "reusable wheel": "reusable_wheels",
        "reusable wheels": "reusable_wheels",
        "hack": "hacks",
        "hacks": "hacks",
        "tip": "tips",
        "tips": "tips",
        "trick": "tricks",
        "tricks": "tricks",
    }
    return aliases.get(normalized)


def _token_count(token):
    for regex in VERIFIED_TOKEN_RES:
        match = regex.fullmatch(token)
        if match:
            return int(match.group(1))
    return None


def _token_family(token):
    for regex in VERIFIED_TOKEN_RES:
        match = regex.fullmatch(token)
        if match:
            return _canonical_family(match.group(2))
    return None


def _phrase_count(phrase):
    for regex in VERIFIED_PROSE_RES:
        match = regex.fullmatch(phrase)
        if match:
            return _count_value(match.group(1))
    return None


def _phrase_family(phrase):
    for regex in VERIFIED_PROSE_RES:
        match = regex.fullmatch(phrase)
        if match:
            return _canonical_family(match.group(2))
    return None


def _valid_rfc3339(value):
    if not isinstance(value, str) or RFC3339_RE.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return False
    return parsed.astimezone(timezone.utc) <= datetime.now(timezone.utc) + MAX_FUTURE_SKEW


def _checked_revision():
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    revision = result.stdout.strip()
    return revision.lower() if FULL_SHA_RE.fullmatch(revision) else None


def _evidence_matches_revision(source_revision, rel_path, candidate):
    """Return True only when current evidence bytes equal the path at source_revision."""
    try:
        canonical_rel = candidate.relative_to(ROOT.resolve()).as_posix()
        result = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{source_revision}:{canonical_rel}"],
            check=True,
            capture_output=True,
        )
        current_bytes = candidate.read_bytes()
    except (OSError, subprocess.CalledProcessError, ValueError):
        return False
    return current_bytes == result.stdout


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
    if payload.get("version") != 2 or not isinstance(claims, list):
        errors.append("manifest must contain version=2 and claims=[]")
        return {}, {}

    checked_revision = _checked_revision() if claims else None
    by_token, by_phrase = {}, {}
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"manifest claim[{i}] must be an object")
            continue

        token = claim.get("token")
        phrase = claim.get("phrase")
        family = claim.get("claim_family")
        expected_count = claim.get("expected_count")
        actual_count = claim.get("actual_item_count")
        item_locators = claim.get("item_locators")
        evidence_paths = claim.get("evidence_paths")
        source_revision = claim.get("source_revision")
        generated_at = claim.get("generated_at")
        verifier_boundary = claim.get("verifier_boundary")

        manifest_family = _canonical_family(family)
        if not isinstance(family, str) or not family.strip():
            errors.append(f"manifest claim[{i}] requires claim_family")
        elif manifest_family is None:
            errors.append(f"manifest claim[{i}] claim_family is outside bounded family grammar: {family!r}")
        if not isinstance(expected_count, int) or expected_count < 0:
            errors.append(f"manifest claim[{i}] has invalid expected_count")
            continue
        if not isinstance(actual_count, int) or actual_count < 0:
            errors.append(f"manifest claim[{i}] has invalid actual_item_count")
            continue
        if actual_count != expected_count:
            errors.append(f"manifest claim[{i}] expected_count != actual_item_count")
        if not isinstance(item_locators, list) or len(item_locators) != actual_count:
            errors.append(f"manifest claim[{i}] item_locators length must equal actual_item_count")
        elif any(not isinstance(locator, str) or not locator.strip() for locator in item_locators):
            errors.append(f"manifest claim[{i}] item_locators must be non-empty strings")
        elif len(set(item_locators)) != len(item_locators):
            errors.append(f"manifest claim[{i}] item_locators must be unique")

        source_revision_valid = isinstance(source_revision, str) and FULL_SHA_RE.fullmatch(source_revision) is not None
        if not source_revision_valid:
            errors.append(f"manifest claim[{i}] source_revision must be a full 40-hex commit SHA")
        elif checked_revision is None:
            errors.append(f"manifest claim[{i}] cannot verify source_revision because checked repository revision is unavailable")
        elif source_revision.casefold() != checked_revision:
            errors.append(
                f"manifest claim[{i}] source_revision must equal checked repository revision {checked_revision}"
            )

        if not isinstance(evidence_paths, list) or not evidence_paths:
            errors.append(f"manifest claim[{i}] requires non-empty evidence_paths")
        else:
            for rel in evidence_paths:
                if not isinstance(rel, str) or not rel.strip():
                    errors.append(f"manifest claim[{i}] has invalid evidence path: {rel!r}")
                    continue
                candidate = (ROOT / rel).resolve()
                try:
                    candidate.relative_to(ROOT.resolve())
                except ValueError:
                    errors.append(f"manifest claim[{i}] evidence path escapes repository: {rel!r}")
                    continue
                if not candidate.is_file():
                    errors.append(f"manifest claim[{i}] evidence path missing: {rel!r}")
                    continue
                if source_revision_valid and not _evidence_matches_revision(source_revision, rel, candidate):
                    errors.append(
                        f"manifest claim[{i}] evidence path bytes do not match source_revision: {rel!r}"
                    )

        if not _valid_rfc3339(generated_at):
            errors.append(f"manifest claim[{i}] generated_at must be timezone-aware RFC3339 and not materially future-dated")
        if not isinstance(verifier_boundary, str) or not verifier_boundary.strip():
            errors.append(f"manifest claim[{i}] requires verifier_boundary")

        if token:
            token_count = _token_count(token)
            token_family = _token_family(token)
            if token_count is None:
                errors.append(f"manifest claim[{i}] token is outside bounded VERIFIED count grammar: {token!r}")
            elif token_count != expected_count:
                errors.append(f"manifest claim[{i}] token count disagrees with expected_count")
            if token_family is None:
                errors.append(f"manifest claim[{i}] token family is outside bounded family grammar: {token!r}")
            elif manifest_family is not None and token_family != manifest_family:
                errors.append(f"manifest claim[{i}] token family disagrees with claim_family")
            key = token.casefold()
            if key in by_token:
                errors.append(f"duplicate manifest token: {token}")
            by_token[key] = claim
        if phrase:
            phrase_count = _phrase_count(phrase)
            phrase_family = _phrase_family(phrase)
            if phrase_count is None:
                errors.append(f"manifest claim[{i}] phrase is outside bounded verified-count grammar: {phrase!r}")
            elif phrase_count != expected_count:
                errors.append(f"manifest claim[{i}] phrase count disagrees with expected_count")
            if phrase_family is None:
                errors.append(f"manifest claim[{i}] phrase family is outside bounded family grammar: {phrase!r}")
            elif manifest_family is not None and phrase_family != manifest_family:
                errors.append(f"manifest claim[{i}] phrase family disagrees with claim_family")
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

    forbidden_casefold = [(needle.casefold(), needle, reason) for needle, reason in FORBIDDEN.items()]
    for path in iter_surfaces():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT)
        text_casefold = text.casefold()
        for folded_needle, needle, reason in forbidden_casefold:
            if folded_needle in text_casefold:
                errors.append(f"{rel} contains forbidden {needle!r} (case-insensitive match): {reason}")
        for match in FORBIDDEN_STATUS_RE.finditer(text):
            errors.append(f"{rel} contains forbidden physical-status alias {match.group(0)!r}")
        for regex in VERIFIED_TOKEN_RES:
            for match in regex.finditer(text):
                token, count_text = match.group(0), match.group(1)
                claim = by_token.get(token.casefold())
                if claim is None:
                    errors.append(f"{rel} contains unmanifested verified-count token {token!r}")
                elif claim["expected_count"] != int(count_text):
                    errors.append(f"{rel} token {token!r} count disagrees with manifest")
        for regex in VERIFIED_PROSE_RES:
            for match in regex.finditer(text):
                phrase, count_text = match.group(0), match.group(1)
                count = _count_value(count_text)
                claim = by_phrase.get(phrase.casefold())
                if claim is None:
                    errors.append(f"{rel} contains unmanifested verified-count phrase {phrase!r}")
                elif claim["expected_count"] != count:
                    errors.append(f"{rel} phrase {phrase!r} count disagrees with manifest")

    if errors:
        print("AUTOMATION_TRUTH_LINT=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AUTOMATION_TRUTH_LINT=PASS_BOUNDED")
    print("Scope: deterministic claim-registration hygiene; manifest/path consistency is not factual verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())