#!/usr/bin/env python3
"""Fail-closed regression court for Issue #31.

This test intentionally fails on the known-bad unit_id short-circuit. It proves
that reusing a stable unit_id with unchanged educational content but changed
occurrence/provenance must never be silently classified as EXACT_DUP.
"""
from __future__ import annotations

import copy
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonicalize import DECISION_EXACT_DUP, ingest_question, init_db


def base_record() -> dict:
    return {
        "unit_id": "REGRESSION-UNIT-001",
        "exam_branch": "GATE-EE",
        "subject": "Control Systems",
        "topic": "Stability",
        "teacher": "Teacher A",
        "video_id": "video-001",
        "timestamp_span": "00:10-00:20",
        "exact_quote": "Nyquist criterion quote v1",
        "question_text": "Which criterion determines closed-loop stability?",
        "options_json": '{"A":"Nyquist","B":"Routh"}',
        "correct_opt": "A",
        "explanation": "Evidence-bound explanation.",
        "socratic_hints_json": "[]",
        "drive_url": "",
        "question_type": "MCQ",
    }


def assert_not_silent_exact_dup(field: str, new_value: str) -> None:
    conn = init_db(":memory:")
    original = base_record()
    first, _, _ = ingest_question(conn, original)
    assert first != DECISION_EXACT_DUP, (field, "first admission unexpectedly duplicate")

    corrected = copy.deepcopy(original)
    corrected[field] = new_value
    try:
        decision, _, _ = ingest_question(conn, corrected)
    except ValueError as exc:
        assert "IDENTITY_CONFLICT" in str(exc), (field, str(exc))
        return

    assert decision != DECISION_EXACT_DUP, (
        field,
        "PROVENANCE_CORRECTION_SHADOW: changed occurrence/provenance was silently discarded as EXACT_DUP",
    )


def main() -> int:
    adversaries = {
        "teacher": "Teacher B",
        "exam_branch": "GATE-EE-2027",
        "video_id": "video-002",
        "timestamp_span": "00:30-00:40",
        "exact_quote": "Nyquist criterion quote corrected",
    }
    for field, value in adversaries.items():
        assert_not_silent_exact_dup(field, value)
    print("PASS: no silent unit_id provenance-correction loss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
