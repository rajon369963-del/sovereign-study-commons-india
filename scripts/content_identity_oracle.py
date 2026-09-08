#!/usr/bin/env python3
"""Deterministic, fail-closed oracle for proposed Content Identity v1.

Comparison/audit helper only. No database writes, hash migration, or uniqueness constraints.
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any

SAME = "SAME"
DISTINCT = "DISTINCT"
CONFLICT = "CONFLICT_OR_INVALID"
HUMAN = "HUMAN_ADJUDICATION_REQUIRED"

IDENTITY_TEXT = ("exam_branch", "video_id", "question_text", "exact_quote")
REQUIRED_RECORD = (*IDENTITY_TEXT, "timestamp_span", "options_json", "correct_opt", "explanation")
LINEAGE_REQUIRED = ("old_value", "new_value", "evidence", "causal_event_id")
ALLOWED_METADATA_CORRECTION_KEYS = frozenset({"teacher", "subject", "topic"})


def trim(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON object key: {key}")
        out[key] = value
    return out


def _reject_nonstandard_constant(token: str) -> Any:
    raise ValueError(f"non-standard JSON constant: {token}")


def parse_json_fail_closed(raw: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_object_pairs,
            parse_constant=_reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid options_json: {exc.msg}") from exc


def canonical_json(raw: Any) -> str:
    if isinstance(raw, str):
        value = parse_json_fail_closed(raw)
    else:
        value = raw
    if not isinstance(value, (dict, list)):
        raise ValueError("options_json must decode to object or array")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def option_labels(raw: Any) -> set[str]:
    if isinstance(raw, str):
        value = parse_json_fail_closed(raw)
    else:
        value = raw
    if isinstance(value, dict):
        return {trim(k) for k in value.keys()}
    if isinstance(value, list):
        return {str(i + 1) for i in range(len(value))}
    raise ValueError("options_json must decode to object or array")


_TIME_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$")
_SPAN_RE = re.compile(r"^\s*(.*?)\s*(?:-|–|—|to)\s*(.*?)\s*$", re.IGNORECASE)


def _seconds(token: str) -> int:
    m = _TIME_RE.fullmatch(token.strip())
    if not m:
        raise ValueError("timestamp must be MM:SS or HH:MM:SS")
    h = int(m.group(1) or 0)
    mnt = int(m.group(2))
    sec = int(m.group(3))
    if mnt >= 60 or sec >= 60:
        raise ValueError("timestamp minute/second out of range")
    return h * 3600 + mnt * 60 + sec


def canonical_span(raw: Any) -> str:
    text = trim(raw)
    m = _SPAN_RE.fullmatch(text)
    if not m:
        raise ValueError("timestamp_span must contain a start/end range")
    start, end = _seconds(m.group(1)), _seconds(m.group(2))
    if end < start:
        raise ValueError("timestamp_span end precedes start")
    return f"{start}-{end}"


def validate_record(record: dict[str, Any]) -> dict[str, str]:
    missing = [k for k in REQUIRED_RECORD if k not in record]
    if missing:
        raise ValueError("missing required fields: " + ",".join(missing))
    out = {k: trim(record.get(k)) for k in IDENTITY_TEXT}
    if not all(out.values()):
        raise ValueError("identity text fields must be non-empty")
    out["timestamp_span"] = canonical_span(record.get("timestamp_span"))
    out["options_json"] = canonical_json(record.get("options_json"))
    correct = trim(record.get("correct_opt"))
    if not correct or correct not in option_labels(record.get("options_json")):
        raise ValueError("correct_opt is not a canonical option label")
    out["correct_opt"] = correct
    out["explanation"] = trim(record.get("explanation"))
    if not out["explanation"]:
        raise ValueError("explanation must be non-empty")
    return out


def valid_lineage(lineage: Any, old: Any, new: Any) -> bool:
    if not isinstance(lineage, dict):
        return False
    if any(not trim(lineage.get(k)) for k in LINEAGE_REQUIRED):
        return False
    return trim(lineage.get("old_value")) == trim(old) and trim(lineage.get("new_value")) == trim(new)


def metadata_decision(fixture: dict[str, Any]) -> dict[str, Any]:
    base = fixture.get("base_metadata")
    cand = fixture.get("candidate_metadata")
    if not isinstance(base, dict) or not isinstance(cand, dict):
        return {"decision": CONFLICT, "reason": "metadata fixture missing base/candidate metadata"}
    changed = [k for k in sorted(set(base) | set(cand)) if trim(base.get(k)) != trim(cand.get(k))]
    if not changed:
        return {"decision": SAME, "reason": "metadata unchanged"}
    if len(changed) != 1:
        return {"decision": CONFLICT, "reason": "multiple metadata fields changed in one correction"}
    field = changed[0]
    if field not in ALLOWED_METADATA_CORRECTION_KEYS:
        return {"decision": CONFLICT, "reason": f"metadata field '{field}' not authorized for automatic correction", "adjudication": HUMAN}
    if valid_lineage(fixture.get("provenance_lineage"), base.get(field), cand.get(field)):
        return {"decision": SAME, "reason": f"lineage-bound metadata correction:{field}"}
    return {"decision": CONFLICT, "reason": f"metadata correction lacks matching lineage:{field}", "adjudication": HUMAN}


def record_decision(base_raw: Any, cand_raw: Any) -> dict[str, Any]:
    if not isinstance(base_raw, dict) or not isinstance(cand_raw, dict):
        return {"decision": CONFLICT, "reason": "base/candidate record missing"}
    try:
        base = validate_record(base_raw)
        cand = validate_record(cand_raw)
    except ValueError as exc:
        return {"decision": CONFLICT, "reason": str(exc)}

    semantic_fields = ("exam_branch", "video_id", "timestamp_span", "question_text", "options_json", "exact_quote")
    changed = [k for k in semantic_fields if base[k] != cand[k]]

    if not changed:
        if base["correct_opt"] != cand["correct_opt"]:
            return {"decision": CONFLICT, "reason": "same canonical evidence has contradictory correct_opt"}
        if base["explanation"] == cand["explanation"]:
            return {"decision": SAME, "reason": "canonical learner/source semantics identical"}
        return {"decision": CONFLICT, "reason": "explanation changed but compatibility is not mechanically decidable", "adjudication": HUMAN}

    payload_changed = any(k in changed for k in ("question_text", "options_json", "exact_quote"))
    locator_changed = any(k in changed for k in ("exam_branch", "video_id", "timestamp_span"))
    if payload_changed and locator_changed:
        return {"decision": DISTINCT, "reason": "both canonical source locator and evidence payload changed"}
    return {"decision": CONFLICT, "reason": "identity-bearing change is insufficient to prove SAME or DISTINCT automatically", "adjudication": HUMAN}


def decide(fixture: dict[str, Any]) -> dict[str, Any]:
    if "base_metadata" in fixture or "candidate_metadata" in fixture:
        result = metadata_decision(fixture)
    else:
        result = record_decision(fixture.get("base"), fixture.get("candidate"))
    return {"id": fixture.get("id"), **result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_file")
    parser.add_argument("--check-expected", action="store_true", help="test fixture expectations; not independent evidence")
    args = parser.parse_args()
    with open(args.fixture_file, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    failures = []
    for fixture in doc.get("fixtures", []):
        result = decide(fixture)
        print(json.dumps(result, sort_keys=True))
        if args.check_expected and fixture.get("expected") != result["decision"]:
            failures.append((fixture.get("id"), fixture.get("expected"), result["decision"]))
    if failures:
        for fid, expected, actual in failures:
            print(f"EXPECTATION_MISMATCH {fid}: expected={expected} actual={actual}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
