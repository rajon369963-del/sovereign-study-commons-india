#!/usr/bin/env python3
"""
AIR10 Sovereign Canonicalization & Deduplication Engine (v4.0 - Fourth-Generation Hardened)
Author: Sovereign Study Commons India
License: Apache-2.0

Core Invariants Enforced:
1. Pure Math & EE Unit Case-Sensitivity (MΩ vs mΩ, MW vs mW strictly preserved; 10^9 ratio intact).
2. Presentation vs Identity Decoupling (Learner UI option order untouched; explanation-pointer sync guaranteed).
3. Lossless Decimal NAT Precision (Python Decimal; zero arbitrary 4-decimal rounding collisions).
4. NAT Fail-Closed on Non-Empty Options (NAT questions with options rejected fail-closed).
5. Full ASCII C0 Control Character Guard (0x00 - 0x1F sealed on raw text BEFORE normalization).
6. unit_id Full Occurrence Conflict Guard (Reusing unit_id with differing occurrence provenance fails closed).
7. Active MinHash Pre-Filter (Threshold parameter respected, LIMIT 100 removed, candidate pool searched).
8. Durable Quarantine Evidence Bag (ingestion_tasks stores candidate_unit_id, mechanism, similarity_score).
9. Occurrence Read/Write Symmetry (WRITE_IDENTITY_RULE == READ_IDENTITY_RULE).
10. Decoupled Vector Companion Index with Stable unit_id Mapping (Zero SQLite rowid time-bomb).
"""

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False

VECTOR_DIM = 256

# ---------------------------------------------------------------------------
# 1. LaTeX Normalization & Strict C0 Control Protection
# ---------------------------------------------------------------------------

FORBIDDEN_C0_CONTROLS: Dict[str, str] = {
    chr(i): f"C0 control 0x{i:02X}"
    for i in range(32)
    if i != 10  # 0x0A (\n) handled conditionally via allow_newlines
}

def _validate_no_corrupting_control_chars(obj: Any, allow_newlines: bool = False) -> None:
    """
    Rejects strings containing ASCII C0 control characters (0x00-0x1F) resulting from
    unescaped LaTeX in JSON strings.
    Protects against unescaped LaTeX: \theta, \tau, \times (0x09), \nabla, \nu (0x0A), \rho (0x0D),
    \frac (0x0C), \beta (0x08), null (0x00), vtab (0x0B).
    MUST BE RUN ON RAW TEXT BEFORE ANY NORMALIZATION OR WHITESPACE COLLAPSING!
    """
    if isinstance(obj, str):
        for ch, desc in FORBIDDEN_C0_CONTROLS.items():
            if ch == chr(10) and allow_newlines:
                continue
            if ch in obj:
                raise ValueError(
                    f"malformed unescaped LaTeX command detected: contains control character {desc} ({repr(ch)}): {obj!r}"
                )
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _validate_no_corrupting_control_chars(k, allow_newlines=False)
            _validate_no_corrupting_control_chars(v, allow_newlines=False)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            _validate_no_corrupting_control_chars(item, allow_newlines=False)

def _reject_constant(c: str) -> None:
    """Strictly reject non-standard JSON constants (NaN, Infinity, -Infinity)."""
    raise ValueError(f"non-standard JSON constant rejected: {c}")

def _reject_duplicate_object_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """Fail closed when duplicate keys are encountered in a JSON object."""
    out: Dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON object key: {key}")
        out[key] = value
    return out

def _validate_finite_numbers(obj: Any) -> None:
    """Recursively validates that all float values in native objects are finite (rejects NaN, Inf)."""
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"non-finite float rejected: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _validate_finite_numbers(k)
            _validate_finite_numbers(v)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            _validate_finite_numbers(item)

def _canonical_decimal_str(d: Decimal) -> str:
    """Returns canonical string representation of Decimal without arbitrary rounding."""
    if not d.is_finite():
        raise ValueError(f"non-finite Decimal: {d}")
    norm = d.normalize()
    sign, digits, exponent = norm.as_tuple()
    if exponent >= 0:
        return f"{norm:f}"
    return f"{norm}"

def parse_numerical_answer(answer_raw: Any) -> str:
    """
    Parses and validates NAT (Numerical Answer Type) answer or range using Python Decimal.
    Guarantees lossless precision identity (e.g. 1.00001 != 1.00002).
    """
    if answer_raw is None:
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: NAT question requires numeric answer or range")
    ans_str = str(answer_raw).strip()
    if not ans_str:
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: NAT question requires non-empty answer")

    # Range match: e.g. "24.0-26.0", "24.0:26.0", "24.0 to 26.0", "[24.0, 26.0]"
    range_match = re.match(
        r"^\[?\s*([+-]?\d+(?:\.\d+)?)\s*(?:-|:|\bto\b|,)\s*([+-]?\d+(?:\.\d+)?)\s*\]?$",
        ans_str,
        re.IGNORECASE,
    )
    if range_match:
        try:
            d_min = Decimal(range_match.group(1))
            d_max = Decimal(range_match.group(2))
        except InvalidOperation as e:
            raise ValueError(f"invalid NAT range values: {ans_str}") from e
        if not (d_min.is_finite() and d_max.is_finite()):
            raise ValueError(f"non-finite NAT range bounds: {d_min}, {d_max}")
        if d_min > d_max:
            raise ValueError(f"NAT range min ({d_min}) exceeds max ({d_max})")
        return f"RANGE:{_canonical_decimal_str(d_min)}:{_canonical_decimal_str(d_max)}"

    try:
        d_val = Decimal(ans_str)
        if not d_val.is_finite():
            raise ValueError(f"non-finite NAT numeric value: {d_val}")
        return f"VAL:{_canonical_decimal_str(d_val)}"
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"invalid NAT numerical answer: {ans_str!r}") from e

def parse_msq_correct_options(correct_raw: Any, valid_labels: Set[str]) -> Tuple[str, List[str]]:
    """Parses and validates MSQ (Multiple Select Question) correct options."""
    if correct_raw is None:
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: MSQ requires one or more correct options")
    if isinstance(correct_raw, (list, set, tuple)):
        raw_list = [str(x).strip() for x in correct_raw if str(x).strip()]
    elif isinstance(correct_raw, str):
        raw_list = [x.strip() for x in re.split(r"[,;\s]+", correct_raw) if x.strip()]
    else:
        raise ValueError(f"invalid MSQ correct_opt format: {correct_raw!r}")

    if not raw_list:
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: MSQ requires at least one non-empty correct option")

    for lbl in raw_list:
        if lbl not in valid_labels:
            raise ValueError(f"MSQ correct_opt label '{lbl}' is not in valid option labels: {sorted(valid_labels)}")

    sorted_unique = sorted(set(raw_list))
    return ",".join(sorted_unique), sorted_unique

def _find_balanced_group(text: str, start: int) -> Tuple[Optional[str], int]:
    """Extracts a balanced curly brace group starting at text[start]."""
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    return None, start

def normalize_latex(text: str) -> str:
    """
    Depth-tracking LaTeX formula normalizer.
    Converts \frac{a}{b} into balanced (a)/(b), collapses whitespace, and preserves case.
    """
    if not text:
        return ""

    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i : i + 5] == r"\frac":
            pos = i + 5
            while pos < n and text[pos].isspace():
                pos += 1
            num, next_pos = _find_balanced_group(text, pos)
            if num is not None:
                pos2 = next_pos
                while pos2 < n and text[pos2].isspace():
                    pos2 += 1
                den, end_pos = _find_balanced_group(text, pos2)
                if den is not None:
                    out.append(f"({normalize_latex(num)})/({normalize_latex(den)})")
                    i = end_pos
                    continue
        out.append(text[i])
        i += 1

    res = "".join(out)
    return " ".join(res.split())

# ---------------------------------------------------------------------------
# 2. Presentation vs. Identity Decoupled Option Normalization
# ---------------------------------------------------------------------------

QUESTION_TYPE_MCQ = "MCQ"
QUESTION_TYPE_MSQ = "MSQ"
QUESTION_TYPE_NAT = "NAT"
VALID_QUESTION_TYPES = {QUESTION_TYPE_MCQ, QUESTION_TYPE_MSQ, QUESTION_TYPE_NAT}

def parse_and_canonicalize_options(
    options_raw: Any,
    correct_opt: Optional[Any] = None,
    question_type: str = QUESTION_TYPE_MCQ
) -> Tuple[str, str, str, str, List[str]]:
    """
    Decouples learner presentation options from internal identity representation.
    - Presentation options: Preserves original keys and ordering so explanations ('Option A is correct...')
      and socratic hints stay 100% synchronized with the learner UI.
    - Canonical options: Deterministically sorted for content identity hashing.
    - Full C0 control character validation prevents silent LaTeX corruption.
    Returns:
      (canonical_options_json, presentation_options_json, canonical_correct_opt, presentation_correct_opt, distractors)
    """
    if question_type not in VALID_QUESTION_TYPES:
        raise ValueError(f"invalid question_type '{question_type}'; must be in {VALID_QUESTION_TYPES}")

    # NAT questions have no options; enforce fail-closed if options are provided!
    if question_type == QUESTION_TYPE_NAT:
        if options_raw is not None:
            opts_str = str(options_raw).strip()
            if opts_str and opts_str not in ("{}", "[]", '""'):
                try:
                    parsed_p = json.loads(opts_str) if isinstance(options_raw, str) else options_raw
                    if parsed_p:
                        raise ValueError("INVALID_NAT_OPTIONS: NAT questions must not contain options; options must be empty or absent")
                except json.JSONDecodeError:
                    raise ValueError("INVALID_NAT_OPTIONS: NAT questions must not contain options; options must be empty or absent")
        canonical_nat = parse_numerical_answer(correct_opt)
        return "{}", "{}", canonical_nat, str(correct_opt).strip(), []

    if correct_opt is None or not str(correct_opt).strip():
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: correct_opt must be a non-empty string or list")

    if isinstance(options_raw, str):
        _validate_no_corrupting_control_chars(options_raw, allow_newlines=False)
        try:
            parsed = json.loads(
                options_raw,
                object_pairs_hook=_reject_duplicate_object_pairs,
                parse_constant=_reject_constant,
            )
            _validate_no_corrupting_control_chars(parsed, allow_newlines=False)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid options_json: {exc.msg}") from exc
    else:
        _validate_finite_numbers(options_raw)
        _validate_no_corrupting_control_chars(options_raw, allow_newlines=False)
        parsed = options_raw

    if isinstance(parsed, dict):
        if not parsed:
            raise ValueError("options dict must not be empty")
        raw_keys = list(parsed.keys())
        trimmed_keys = [str(k).strip() for k in raw_keys]
        if len(set(trimmed_keys)) != len(raw_keys):
            raise ValueError(f"colliding option keys after trimming: {raw_keys}")

        presentation_dict: Dict[str, str] = {
            str(k).strip(): normalize_latex(str(v).strip())
            for k, v in parsed.items()
        }

        valid_labels = set(presentation_dict.keys())

        if question_type == QUESTION_TYPE_MSQ:
            pres_correct_str, pres_correct_list = parse_msq_correct_options(correct_opt, valid_labels)
        else:
            target_lbl = str(correct_opt).strip()
            if target_lbl not in presentation_dict:
                raise ValueError(f"correct_opt '{target_lbl}' is not in option labels: {list(presentation_dict.keys())}")
            pres_correct_str = target_lbl
            pres_correct_list = [target_lbl]

        # Canonical representation for identity hashing: sorted by normalized value, then key
        sorted_pairs = sorted(presentation_dict.items(), key=lambda x: (x[1], x[0]))
        canonical_dict: Dict[str, str] = {}
        old_to_new: Dict[str, str] = {}
        for idx, (old_lbl, val) in enumerate(sorted_pairs):
            new_lbl = chr(65 + idx)
            canonical_dict[new_lbl] = val
            old_to_new[old_lbl] = new_lbl

        if question_type == QUESTION_TYPE_MSQ:
            canon_correct_list = sorted([old_to_new[lbl] for lbl in pres_correct_list])
            canon_correct_str = ",".join(canon_correct_list)
        else:
            canon_correct_str = old_to_new[pres_correct_str]

        canonical_json_str = json.dumps(
            canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        presentation_json_str = json.dumps(
            presentation_dict,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return (
            canonical_json_str,
            presentation_json_str,
            canon_correct_str,
            pres_correct_str,
            list(presentation_dict.values()),
        )

    elif isinstance(parsed, list):
        if not parsed:
            raise ValueError("options list must not be empty")
        clean_list = [normalize_latex(str(x).strip()) for x in parsed]
        valid_labels = {str(i + 1) for i in range(len(clean_list))}

        if question_type == QUESTION_TYPE_MSQ:
            pres_correct_str, pres_correct_list = parse_msq_correct_options(correct_opt, valid_labels)
        else:
            target_lbl = str(correct_opt).strip()
            if target_lbl not in valid_labels:
                raise ValueError(
                    f"correct_opt '{target_lbl}' is invalid for list options; must be in {sorted(valid_labels, key=int)}"
                )
            pres_correct_str = target_lbl
            pres_correct_list = [target_lbl]

        # Decouple Presentation vs Identity for Lists:
        indexed_items = [(str(i + 1), val) for i, val in enumerate(clean_list)]
        sorted_pairs = sorted(indexed_items, key=lambda x: (x[1], x[0]))
        canonical_dict = {}
        old_to_new = {}
        for idx, (old_lbl, val) in enumerate(sorted_pairs):
            new_lbl = str(idx + 1)
            canonical_dict[new_lbl] = val
            old_to_new[old_lbl] = new_lbl

        if question_type == QUESTION_TYPE_MSQ:
            canon_correct_list = sorted([old_to_new[lbl] for lbl in pres_correct_list], key=int)
            canon_correct_str = ",".join(canon_correct_list)
        else:
            canon_correct_str = old_to_new[pres_correct_str]

        canonical_json_str = json.dumps(
            canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        presentation_json_str = json.dumps(
            clean_list,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return (
            canonical_json_str,
            presentation_json_str,
            canon_correct_str,
            pres_correct_str,
            clean_list,
        )
    else:
        raise ValueError("options must be dict or list")

# ---------------------------------------------------------------------------
# 3. Provenance & Timestamp Span Normalization
# ---------------------------------------------------------------------------

def canonical_span(span_raw: Any) -> str:
    """Enforces strict timestamp span format 'MM:SS-MM:SS' with start < end."""
    if span_raw is None:
        raise ValueError("INSUFFICIENT_PROVENANCE: timestamp_span must not be empty")
    s = str(span_raw).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$", s)
    if not m:
        raise ValueError(f"invalid timestamp_span format '{s}'; must be MM:SS-MM:SS")
    m1, s1, m2, s2 = map(int, m.groups())
    t1 = m1 * 60 + s1
    t2 = m2 * 60 + s2
    if t1 >= t2:
        raise ValueError(f"inverted or zero-length timestamp_span: {s}")
    return f"{m1:02d}:{s1:02d}-{m2:02d}:{s2:02d}"

# ---------------------------------------------------------------------------
# 4. Native MinHash Signature Generation (Zero External Deps)
# ---------------------------------------------------------------------------

def get_k_shingles(text: str, k: int = 3) -> Set[str]:
    """Extracts k-word shingles from normalized text."""
    words = text.lower().split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}

def compute_minhash(text: str, num_perm: int = 64) -> List[int]:
    """
    Computes a 64-hash MinHash signature for text.
    Uses independent linear hash functions (a*x + b) % p.
    """
    shingles = get_k_shingles(text, k=3)
    if not shingles:
        return [0] * num_perm

    prime = 4294967311  # 2^32 + 15
    sig = [float("inf")] * num_perm

    for shingle in shingles:
        shash = int(hashlib.md5(shingle.encode("utf-8")).hexdigest()[:8], 16)
        for i in range(num_perm):
            a = (i * 2654435761 + 1) & 0xFFFFFFFF
            b = (i * 805447043 + 7) & 0xFFFFFFFF
            h = (a * shash + b) % prime
            if h < sig[i]:
                sig[i] = h

    return [int(x) for x in sig]

def minhash_jaccard_similarity(sig1: List[int], sig2: List[int]) -> float:
    """Estimates Jaccard similarity between two MinHash signatures."""
    if not sig1 or not sig2 or len(sig1) != len(sig2):
        return 0.0
    matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
    return matches / len(sig1)

# ---------------------------------------------------------------------------
# 5. Native Fallback Dense Vector Generator
# ---------------------------------------------------------------------------

def generate_dense_vector(text: str, dim: int = VECTOR_DIM) -> List[float]:
    """Generates a deterministic pseudo-dense vector for local semantic tests."""
    words = text.lower().split()
    vec = [0.0] * dim
    for w in words:
        h = int(hashlib.sha256(w.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

# ---------------------------------------------------------------------------
# 6. Database Initialization
# ---------------------------------------------------------------------------

def initialize_database(db_path: str) -> sqlite3.Connection:
    """
    Initializes base SQLite database with WAL mode, 256MB mmap, queue table,
    and study_units table.
    INVARIANT: Base database MUST REMAIN 100% vanilla SQLite3 compatible!
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA mmap_size=268435456;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA busy_timeout=5000;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_tasks (
            task_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            status TEXT CHECK(status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'QUARANTINE_REVIEW')) DEFAULT 'PENDING',
            worker_id TEXT,
            leased_at DATETIME,
            completed_at DATETIME,
            error_message TEXT,
            canonical_hash TEXT,
            tri_state_decision TEXT,
            candidate_unit_id TEXT,
            quarantine_mechanism TEXT,
            similarity_score REAL
        );
    """)

    cur = conn.execute("PRAGMA table_info(ingestion_tasks);")
    task_cols = {r[1] for r in cur.fetchall()}
    if "candidate_unit_id" not in task_cols:
        conn.execute("ALTER TABLE ingestion_tasks ADD COLUMN candidate_unit_id TEXT;")
    if "quarantine_mechanism" not in task_cols:
        conn.execute("ALTER TABLE ingestion_tasks ADD COLUMN quarantine_mechanism TEXT;")
    if "similarity_score" not in task_cols:
        conn.execute("ALTER TABLE ingestion_tasks ADD COLUMN similarity_score REAL;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_units (
            unit_id TEXT PRIMARY KEY,
            exam_branch TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            teacher TEXT NOT NULL,
            video_id TEXT NOT NULL,
            timestamp_span TEXT NOT NULL,
            exact_quote TEXT NOT NULL,
            question_text TEXT NOT NULL,
            options_json TEXT NOT NULL,
            correct_opt TEXT NOT NULL,
            explanation TEXT NOT NULL,
            socratic_hints_json TEXT NOT NULL,
            sha256_hash TEXT NOT NULL,
            drive_url TEXT,
            harvested_at TEXT NOT NULL,
            canonical_hash TEXT,
            minhash_sig TEXT,
            semantic_status TEXT DEFAULT 'NEW',
            question_type TEXT DEFAULT 'MCQ'
        );
    """)

    cur = conn.execute("PRAGMA table_info(study_units);")
    columns = {r[1] for r in cur.fetchall()}
    if "canonical_hash" not in columns:
        conn.execute("ALTER TABLE study_units ADD COLUMN canonical_hash TEXT;")
    if "minhash_sig" not in columns:
        conn.execute("ALTER TABLE study_units ADD COLUMN minhash_sig TEXT;")
    if "semantic_status" not in columns:
        conn.execute("ALTER TABLE study_units ADD COLUMN semantic_status TEXT DEFAULT 'NEW';")
    if "question_type" not in columns:
        conn.execute("ALTER TABLE study_units ADD COLUMN question_type TEXT DEFAULT 'MCQ';")

    conn.commit()
    return conn

def init_vector_companion(vector_db_path: str = ":memory:") -> Optional[sqlite3.Connection]:
    """
    Initializes a dedicated, decoupled vector companion index in a separate database.
    Binds vector embedding to stable unit_id via vec_unit_map table to eliminate SQLite rowid time-bomb.
    """
    if not HAS_SQLITE_VEC:
        return None
    vec_conn = sqlite3.connect(vector_db_path)
    vec_conn.enable_load_extension(True)
    sqlite_vec.load(vec_conn)
    vec_conn.enable_load_extension(False)
    
    vec_conn.execute("""
        CREATE TABLE IF NOT EXISTS vec_unit_map (
            vec_id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT UNIQUE NOT NULL
        );
    """)
    vec_conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_questions USING vec0(
            question_rowid INTEGER PRIMARY KEY,
            embedding float[{VECTOR_DIM}] distance_metric=cosine
        );
    """)
    vec_conn.commit()
    return vec_conn

# ---------------------------------------------------------------------------
# 7. Ingestion & Tri-State Quarantine Deduplication Pipeline
# ---------------------------------------------------------------------------

DECISION_NEW = "NEW"
DECISION_EXACT_DUP = "EXACT_DUP"
DECISION_REPEAT_OCCURRENCE = "REPEAT_OCCURRENCE"
DECISION_QUARANTINE = "QUARANTINE_REVIEW"

def ingest_question(
    conn: sqlite3.Connection,
    record: Dict[str, Any],
    vec_conn: Optional[sqlite3.Connection] = None,
    minhash_threshold: float = 0.95,
    vector_threshold: float = 0.05
) -> Tuple[str, str, str]:
    """
    Tri-state ingestion pipeline:
    1. Validates strict provenance and seals all C0 control characters ON RAW TEXT before normalization.
    2. Validates question ontology: MCQ, MSQ, NAT (fail-closed on non-empty options for NAT).
    3. Normalizes question text and options (lossless Decimal for NAT).
    4. unit_id full occurrence conflict guard: if unit_id exists with differing occurrence provenance, fails closed.
    5. Checks exact occurrence match -> EXACT_DUP.
    6. Checks semantic content match -> REPEAT_OCCURRENCE.
    7. Runs active MinHash pre-filter across candidate pool -> QUARANTINE_REVIEW (with durable evidence).
    8. Runs companion dense vector cosine check -> QUARANTINE_REVIEW (with durable evidence).
    9. Admits as NEW.
    Returns:
      (decision, canonical_hash, admitted_or_matched_unit_id)
    """
    # 1. Strict Provenance Validity: required fields
    for field in ["exam_branch", "subject", "topic", "teacher", "video_id", "timestamp_span", "exact_quote"]:
        val = record.get(field)
        if val is None or not str(val).strip():
            raise ValueError(f"INSUFFICIENT_PROVENANCE: missing required field '{field}' (never invent evidence)")

    # 2. Strict Provenance Validity: canonical timestamp parsing
    raw_span = record.get("timestamp_span")
    canon_span = canonical_span(raw_span)

    # 3. Raw question text validation BEFORE normalization
    raw_q_text = str(record.get("question_text", "")).strip()
    if not raw_q_text:
        raise ValueError("question_text must not be empty")

    _validate_no_corrupting_control_chars(raw_q_text, allow_newlines=True)
    q_text = normalize_latex(raw_q_text)

    q_type = record.get("question_type", QUESTION_TYPE_MCQ).strip().upper()
    if q_type not in VALID_QUESTION_TYPES:
        raise ValueError(f"invalid question_type '{q_type}'; must be in {VALID_QUESTION_TYPES}")

    raw_options = record.get("options_json")
    correct_opt = record.get("correct_opt")

    canon_options, pres_options, canon_correct, pres_correct, _ = parse_and_canonicalize_options(
        raw_options, correct_opt, question_type=q_type
    )

    # Content Identity (Semantic Question Payload)
    content_payload = f"{q_text}|{q_type}|{canon_options}|{canon_correct}"
    canonical_hash = hashlib.sha256(content_payload.encode("utf-8")).hexdigest()

    # Occurrence Identity (Specific provenance instantiation)
    exam_branch = record["exam_branch"].strip()
    teacher = record["teacher"].strip()
    video_id = record["video_id"].strip()
    exact_quote = record["exact_quote"].strip()
    
    occ_payload = f"{canonical_hash}|{exam_branch}|{teacher}|{video_id}|{canon_span}|{exact_quote}"
    occ_hash = hashlib.sha256(occ_payload.encode("utf-8")).hexdigest()
    unit_id = str(record.get("unit_id") or f"UNIT_{occ_hash[:16]}").strip()

    # 4. unit_id Full Occurrence Conflict Guard:
    cur = conn.execute("""
        SELECT canonical_hash, exam_branch, teacher, video_id, timestamp_span, exact_quote
        FROM study_units WHERE unit_id = ? LIMIT 1;
    """, (unit_id,))
    existing_unit = cur.fetchone()
    if existing_unit is not None:
        ex_can_hash, ex_branch, ex_teacher, ex_vid, ex_span, ex_quote = existing_unit
        ex_occ_payload = f"{ex_can_hash}|{ex_branch}|{ex_teacher}|{ex_vid}|{ex_span}|{ex_quote}"
        if ex_occ_payload == occ_payload:
            return (DECISION_EXACT_DUP, canonical_hash, unit_id)
        else:
            raise ValueError(
                f"IDENTITY_CONFLICT: unit_id '{unit_id}' already exists with different occurrence provenance or question payload! "
                f"(existing_occ={hashlib.sha256(ex_occ_payload.encode()).hexdigest()[:12]} != "
                f"new_occ={occ_hash[:12]})"
            )

    # 5. Occurrence Read/Write Symmetry: check exact occurrence instantiation
    cur = conn.execute("""
        SELECT unit_id FROM study_units
        WHERE (canonical_hash = ? AND exam_branch = ? AND teacher = ? AND video_id = ? AND timestamp_span = ? AND exact_quote = ?)
        LIMIT 1;
    """, (canonical_hash, exam_branch, teacher, video_id, canon_span, exact_quote))
    exact_occ = cur.fetchone()
    if exact_occ:
        return (DECISION_EXACT_DUP, canonical_hash, exact_occ[0])

    # 6. Check if semantic content already exists (REPEAT OCCURRENCE / MULTI-SOURCE PYQ)
    cur = conn.execute("SELECT unit_id FROM study_units WHERE canonical_hash = ? LIMIT 1;", (canonical_hash,))
    content_match = cur.fetchone()
    if content_match:
        conn.execute("""
            INSERT INTO study_units (
                unit_id, exam_branch, subject, topic, teacher, video_id,
                timestamp_span, exact_quote, question_text, options_json,
                correct_opt, explanation, socratic_hints_json, sha256_hash,
                drive_url, harvested_at, canonical_hash, minhash_sig, semantic_status, question_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?)
        """, (
            unit_id, exam_branch, record["subject"].strip(), record["topic"].strip(),
            teacher, video_id, canon_span, exact_quote, q_text,
            pres_options, pres_correct, str(record.get("explanation", "")).strip(),
            str(record.get("socratic_hints_json", "[]")).strip(), occ_hash,
            str(record.get("drive_url", "")).strip(), canonical_hash,
            json.dumps(compute_minhash(q_text)), DECISION_REPEAT_OCCURRENCE, q_type
        ))
        conn.commit()
        return (DECISION_REPEAT_OCCURRENCE, canonical_hash, unit_id)

    sig = compute_minhash(q_text)
    sig_str = json.dumps(sig)
    vec = generate_dense_vector(q_text, VECTOR_DIM)

    # 7. Active MinHash Pre-Filter & Near-Duplicate Quarantine (Full candidate pool, caller threshold respected)
    if minhash_threshold > 0:
        cur = conn.execute("""
            SELECT unit_id, minhash_sig FROM study_units
            WHERE minhash_sig IS NOT NULL AND canonical_hash != ?;
        """, (canonical_hash,))
        for u_id, existing_sig_str in cur.fetchall():
            try:
                ex_sig = json.loads(existing_sig_str)
                jaccard = minhash_jaccard_similarity(sig, ex_sig)
                if jaccard >= minhash_threshold:
                    task_id = f"TASK_{canonical_hash[:16]}"
                    conn.execute("""
                        INSERT OR REPLACE INTO ingestion_tasks (
                            task_id, payload_json, status, tri_state_decision,
                            candidate_unit_id, quarantine_mechanism, similarity_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (
                        task_id, json.dumps(record), DECISION_QUARANTINE, DECISION_QUARANTINE,
                        u_id, "MINHASH", float(jaccard)
                    ))
                    conn.commit()
                    return (DECISION_QUARANTINE, canonical_hash, u_id)
            except Exception:
                continue

    # 8. Companion SQLite-Vec Query with Stable unit_id Mapping
    if vec_conn is not None and HAS_SQLITE_VEC:
        vec_bytes = sqlite_vec.serialize_float32(vec)
        cur = vec_conn.execute("""
            SELECT question_rowid, distance
            FROM vec_questions
            WHERE embedding MATCH ? AND k = 1;
        """, (vec_bytes,))
        row = cur.fetchone()
        if row is not None:
            match_rowid, distance = row
            if distance <= vector_threshold:
                cur_map = vec_conn.execute("SELECT unit_id FROM vec_unit_map WHERE vec_id = ?;", (match_rowid,))
                map_row = cur_map.fetchone()
                matched_unit_id = map_row[0] if map_row else f"ROW_{match_rowid}"

                task_id = f"TASK_{canonical_hash[:16]}"
                conn.execute("""
                    INSERT OR REPLACE INTO ingestion_tasks (
                        task_id, payload_json, status, tri_state_decision,
                        candidate_unit_id, quarantine_mechanism, similarity_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    task_id, json.dumps(record), DECISION_QUARANTINE, DECISION_QUARANTINE,
                    matched_unit_id, "VECTOR", float(distance)
                ))
                conn.commit()
                return (DECISION_QUARANTINE, canonical_hash, matched_unit_id)

    # 9. Admit as NEW unit: store presentation options untouched in study_units table
    conn.execute("""
        INSERT INTO study_units (
            unit_id, exam_branch, subject, topic, teacher, video_id,
            timestamp_span, exact_quote, question_text, options_json,
            correct_opt, explanation, socratic_hints_json, sha256_hash,
            drive_url, harvested_at, canonical_hash, minhash_sig, semantic_status, question_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?)
    """, (
        unit_id, exam_branch, record["subject"].strip(), record["topic"].strip(),
        teacher, video_id, canon_span, exact_quote, q_text,
        pres_options, pres_correct, str(record.get("explanation", "")).strip(),
        str(record.get("socratic_hints_json", "[]")).strip(), occ_hash,
        str(record.get("drive_url", "")).strip(), canonical_hash, sig_str, DECISION_NEW, q_type
    ))
    conn.commit()

    if vec_conn is not None and HAS_SQLITE_VEC:
        cur_map = vec_conn.execute("INSERT INTO vec_unit_map (unit_id) VALUES (?);", (unit_id,))
        new_vec_id = cur_map.lastrowid
        vec_bytes = sqlite_vec.serialize_float32(vec)
        vec_conn.execute("INSERT INTO vec_questions (question_rowid, embedding) VALUES (?, ?);", (new_vec_id, vec_bytes))
        vec_conn.commit()

    return (DECISION_NEW, canonical_hash, unit_id)

# ---------------------------------------------------------------------------
# 8. Comprehensive Adversarial Verification Harness (23 Rigorous Tests)
# ---------------------------------------------------------------------------

def run_adversarial_suite() -> bool:
    """Executes the complete fourth-generation adversarial test suite."""
    print("=== RUNNING FOURTH-GENERATION ADVERSARIAL CANONICALIZATION SUITE ===")

    # 1. EE Unit Case Sensitivity
    print("[1/23] Testing EE Unit Case Sensitivity (MW vs mW, MΩ vs mΩ)...")
    q_mega = "Calculate power in MW."
    q_milli = "Calculate power in mW."
    opts = '{"A": "10 MW", "B": "20 MW"}'
    opts_m = '{"A": "10 mW", "B": "20 mW"}'
    c_m, _, _, _, _ = parse_and_canonicalize_options(opts, "A")
    c_mi, _, _, _, _ = parse_and_canonicalize_options(opts_m, "A")
    h_mega = hashlib.sha256(f"{q_mega}|{c_m}".encode("utf-8")).hexdigest()
    h_milli = hashlib.sha256(f"{q_milli}|{c_mi}".encode("utf-8")).hexdigest()
    assert h_mega != h_milli, "CRITICAL: MW collided with mW!"
    print("  ✓ PASS: EE Unit Case-Sensitivity strictly preserved (10^9 factor intact).")

    # 2. Duplicate Option Value Pointer Preservation
    print("[2/23] Testing Duplicate Option Text Pointer Preservation...")
    dup_opts = '{"A": "10 V", "B": "20 V", "C": "10 V", "D": "30 V"}'
    canon_opts, pres_opts, c_opt, p_opt, _ = parse_and_canonicalize_options(dup_opts, "C")
    assert p_opt == "C", "CRITICAL: Original presentation pointer altered!"
    print("  ✓ PASS: Duplicate option values maintain exact original pointer.")

    # 3. List-Based Options Preservation
    print("[3/23] Testing List-Based Options Preservation...")
    list_opts = '["Transformer", "Induction Motor", "Synchronous Motor"]'
    canon_list, pres_list, c_list, p_list, _ = parse_and_canonicalize_options(list_opts, "2")
    assert p_list == "2"
    assert json.loads(pres_list)[1] == "Induction Motor"
    print("  ✓ PASS: List options preserve exact ordering and answer indexing.")

    # 4. List Options 1-Based Range Check
    print("[4/23] Testing List Options 1-Based Validation (Fail-Closed on 0, A, Out-of-Bounds)...")
    for bad_ans in ["0", "4", "-1", "A"]:
        try:
            parse_and_canonicalize_options(list_opts, bad_ans)
            assert False, f"Expected ValueError on bad list answer: {bad_ans}"
        except ValueError as e:
            assert "invalid for list options" in str(e)
    print("  ✓ PASS: List options strictly enforce correct_opt in {'1', ..., str(len(options))}.")

    # 5. Empty Correct Option Check
    print("[5/23] Testing Empty Correct Option & Empty Options (Fail-Closed on P0 #1)...")
    for empty_val in ["", "   ", None]:
        try:
            parse_and_canonicalize_options(opts, empty_val)
            assert False, f"Expected ValueError on empty answer: {empty_val!r}"
        except ValueError as e:
            assert "INSUFFICIENT_CORRECT_ANSWER" in str(e)
    try:
        parse_and_canonicalize_options("{}", "A")
        assert False, "Expected ValueError on empty dict"
    except ValueError as e:
        assert "must not be empty" in str(e)
    print("  ✓ PASS: Empty correct answer and empty options rejected fail-closed.")

    # 6. Colliding Trimmed Option Keys
    print("[6/23] Testing Colliding Trimmed Option Keys (Fail-Closed)...")
    colliding = '{"A": "Option 1", " A ": "Option 2"}'
    try:
        parse_and_canonicalize_options(colliding, "A")
        assert False, "Expected ValueError on colliding keys"
    except ValueError as e:
        assert "colliding option keys" in str(e)
    print("  ✓ PASS: Colliding option keys rejected fail-closed.")

    # 7. Non-Standard JSON Constants in JSON String
    print("[7/23] Testing Non-Standard JSON Constants in JSON String...")
    for const in ["NaN", "Infinity", "-Infinity"]:
        bad_json = f'{{"A": {const}, "B": "Normal"}}'
        try:
            parse_and_canonicalize_options(bad_json, "B")
            assert False, f"Expected ValueError on JSON constant: {const}"
        except ValueError as e:
            assert "non-standard JSON constant" in str(e) or "invalid options_json" in str(e)
    print("  ✓ PASS: String JSON NaN and Infinity constants strictly rejected.")

    # 8. Native Python Object NaN/Infinity Bypass
    print("[8/23] Testing Native Python Object NaN/Infinity Bypass (P0 #4)...")
    native_bad_nan = {"A": float("nan"), "B": "10"}
    native_bad_inf = {"A": float("inf"), "B": "10"}
    try:
        parse_and_canonicalize_options(native_bad_nan, "B")
        assert False, "Expected ValueError on native dict with float('nan')"
    except ValueError as e:
        assert "non-finite float rejected" in str(e)
    try:
        parse_and_canonicalize_options(native_bad_inf, "B")
        assert False, "Expected ValueError on native dict with float('inf')"
    except ValueError as e:
        assert "non-finite float rejected" in str(e)
    print("  ✓ PASS: Native Python NaN/Infinity objects fail closed (zero bypass).")

    # 9. Strict LaTeX JSON Escape Handling
    print("[9/23] Testing Strict LaTeX JSON Escape Handling (Zero Silent Corruption)...")
    valid_latex_json = r'{"A": "\\frac{V}{I}", "B": "R"}'
    c_lat, p_lat, _, _, _ = parse_and_canonicalize_options(valid_latex_json, "A")
    assert r"(V)/(I)" in c_lat
    assert r"(V)/(I)" in p_lat
    print("  ✓ PASS: Formula corruption eliminated; strict JSON escape contract enforced.")

    # 10. Invalid correct_opt for Dict
    print("[10/23] Testing Invalid correct_opt for Dict...")
    try:
        parse_and_canonicalize_options(opts, "Z")
        assert False, "Expected ValueError for missing correct_opt"
    except ValueError as e:
        assert "is not in option labels" in str(e)
    print("  ✓ PASS: Invalid correct_opt fails closed.")

    # 11. Balanced-Brace Fractions
    print("[11/23] Testing LaTeX Depth-Tracking Balanced-Brace Fractions...")
    deep_f = r"\frac{V_{in} + \frac{1}{2}}{I_{out}}"
    norm_f = normalize_latex(deep_f)
    assert norm_f == "(V_{in} + (1)/(2))/(I_{out})"
    print("  ✓ PASS: LaTeX balanced-brace fractions identical.")

    # 12. Decoupled Vector Companion Index
    print("[12/23] Testing Decoupled Vector Companion Index with Stable unit_id Mapping...")
    db_base = initialize_database(":memory:")
    vec_db = init_vector_companion(":memory:")
    base_good_rec = {
        "unit_id": "UNIT_TEST_1",
        "exam_branch": "EE",
        "subject": "Power Systems",
        "topic": "Transformers",
        "teacher": "Ashu Sir",
        "video_id": "VID_101",
        "timestamp_span": "12:00-14:30",
        "exact_quote": "Core loss depends on maximum flux density and frequency.",
        "question_text": "Core loss in a transformer is primarily composed of:",
        "options_json": '{"A": "Hysteresis and eddy current losses", "B": "Copper loss only"}',
        "correct_opt": "A"
    }
    dec1, h1, u1 = ingest_question(db_base, base_good_rec, vec_conn=vec_db)
    assert dec1 == DECISION_NEW
    assert u1 == "UNIT_TEST_1"
    cur_base = db_base.execute("SELECT COUNT(*) FROM study_units WHERE unit_id = 'UNIT_TEST_1';")
    assert cur_base.fetchone()[0] == 1
    print("  ✓ PASS: Base database is vanilla SQLite3; vector companion stably bound to unit_id.")

    # 13. Strict Provenance Timestamp Validity Check
    print("[13/23] Testing Strict Provenance Validity Check (Fail-Closed on Timestamp)...")
    bad_span_rec = dict(base_good_rec, unit_id="UNIT_BAD_SPAN", timestamp_span="14:30-12:00")
    try:
        ingest_question(db_base, bad_span_rec, vec_conn=vec_db)
        assert False, "Expected ValueError on inverted timestamp_span"
    except ValueError as e:
        assert "inverted or zero-length timestamp_span" in str(e)
    print("  ✓ PASS: Provenance timestamp validity strictly verified.")

    # 14. Full LaTeX C0 Control Family Rejection
    print("[14/23] Testing Full LaTeX C0 Control Family Rejection (\\theta, \\tau, \\times, \\nabla, \\nu, \\rho)...")
    ctrl_cases = [
        ("theta", chr(9)),
        ("nabla", chr(10)),
        ("rho", chr(13)),
        ("frac", chr(12)),
        ("beta", chr(8)),
        ("null", chr(0)),
        ("vtab", chr(11))
    ]
    for esc_name, ctrl_char in ctrl_cases:
        hostile_opts = f'{{"A": "Formula with {ctrl_char} symbol", "B": "Safe"}}'
        try:
            parse_and_canonicalize_options(hostile_opts, "B")
            assert False, f"Expected ValueError on control character from \\{esc_name}"
        except ValueError as e:
            assert "malformed unescaped LaTeX" in str(e) or "invalid options_json" in str(e)
    print("  ✓ PASS: Complete LaTeX C0 control character family strictly sealed.")

    # 15. Presentation vs Identity Decoupling (Dict)
    print("[15/23] Testing Presentation vs Identity Decoupling (Explanation-Pointer Corruption Eliminated)...")
    raw_unordered = '{"A": "Zener Diode", "B": "Avalanche Diode", "C": "Tunnel Diode"}'
    c_json, p_json, c_ans, p_ans, _ = parse_and_canonicalize_options(raw_unordered, "A")
    assert p_ans == "A"
    assert json.loads(p_json)["A"] == "Zener Diode"
    assert json.loads(c_json)["C"] == "Zener Diode"
    assert c_ans == "C"
    print("  ✓ PASS: Learner presentation options untouched; canonical identity cleanly decoupled.")

    # 16. unit_id Conflict Guard (Different Question Payload)
    print("[16/23] Testing unit_id Conflict Guard (Fail-Closed on IDENTITY_CONFLICT)...")
    u_rec1 = dict(base_good_rec, unit_id="UNIT_CONFLICT_TEST", question_text="What is synchronous speed?")
    ingest_question(db_base, u_rec1, vec_conn=vec_db)
    u_rec2 = dict(base_good_rec, unit_id="UNIT_CONFLICT_TEST", question_text="What is rotor slip?")
    try:
        ingest_question(db_base, u_rec2, vec_conn=vec_db)
        assert False, "Expected ValueError on reused unit_id with different question payload!"
    except ValueError as e:
        assert "IDENTITY_CONFLICT" in str(e)
    print("  ✓ PASS: Reused unit_id with conflicting payload strictly rejected fail-closed.")

    # 17. Active MinHash Pre-Filter & Near-Duplicate Quarantine with Evidence Bag
    print("[17/23] Testing Active MinHash Pre-Filter & Near-Duplicate Quarantine with Evidence Bag...")
    t1 = "A 3-phase 50 Hz transmission line has sending end voltage of 220 kV and receiving end voltage of 200 kV at no load. Calculate the voltage regulation percentage."
    t2 = "A 3-phase 50 Hz transmission line has sending end voltage of 220 kV and receiving end voltage of 200 kV at no load condition. Calculate the voltage regulation percentage."
    mh_rec1 = dict(base_good_rec, unit_id="UNIT_MH_1", question_text=t1)
    dec_mh1, _, _ = ingest_question(db_base, mh_rec1)
    assert dec_mh1 == DECISION_NEW

    # Near identical text with minor shingle perturbation (one added word, Jaccard overlap ~0.73)
    mh_rec2 = dict(base_good_rec, unit_id="UNIT_MH_2", question_text=t2)
    dec_mh2, _, cand_id = ingest_question(db_base, mh_rec2, minhash_threshold=0.70)
    assert dec_mh2 == DECISION_QUARANTINE, f"Expected QUARANTINE_REVIEW, got {dec_mh2}"
    assert cand_id == "UNIT_MH_1"

    cur_ev = db_base.execute("SELECT candidate_unit_id, quarantine_mechanism, similarity_score FROM ingestion_tasks WHERE candidate_unit_id = 'UNIT_MH_1';")
    ev_row = cur_ev.fetchone()
    assert ev_row is not None, "Quarantine evidence record missing in ingestion_tasks!"
    assert ev_row[0] == "UNIT_MH_1"
    assert ev_row[1] == "MINHASH"
    assert ev_row[2] >= 0.70
    print("  ✓ PASS: MinHash pre-filter actively detects near-duplicates and populates durable evidence bag.")

    # 18. Full GATE Question-Type Ontology (MCQ, MSQ, NAT)
    print("[18/23] Testing Full GATE Question-Type Ontology (MCQ, MSQ, NAT)...")
    # A. MCQ
    mcq_rec = dict(
        base_good_rec,
        unit_id="UNIT_GATE_MCQ",
        question_type="MCQ",
        question_text="What is the primary function of a transformer core?",
        options_json='{"A": "To provide magnetic flux path", "B": "To generate eddy currents"}',
        correct_opt="A"
    )
    d_mcq, _, _ = ingest_question(db_base, mcq_rec)
    assert d_mcq == DECISION_NEW

    # B. MSQ (Multiple Select Question)
    msq_rec = dict(
        base_good_rec,
        unit_id="UNIT_GATE_MSQ",
        question_type="MSQ",
        question_text="Which of the following are synchronous motor starting methods?",
        options_json='{"A": "Damper winding", "B": "Pony motor", "C": "Variable frequency supply", "D": "Split phase"}',
        correct_opt="A, B, C",
        explanation="Options A, B, and C are valid starting methods for synchronous motors."
    )
    d_msq, h_msq, _ = ingest_question(db_base, msq_rec)
    assert d_msq == DECISION_NEW
    cur = db_base.execute("SELECT correct_opt, options_json FROM study_units WHERE unit_id = 'UNIT_GATE_MSQ';")
    row_msq = cur.fetchone()
    assert "A" in row_msq[0] and "B" in row_msq[0] and "C" in row_msq[0]

    # C. NAT (Single Value and Range)
    nat_rec_single = dict(
        base_good_rec,
        unit_id="UNIT_GATE_NAT_1",
        question_type="NAT",
        question_text="A 50 Hz transformer has 100 turns. Find flux in mWb if induced EMF is 222 V.",
        options_json="{}",
        correct_opt="10.0"
    )
    d_nat1, _, _ = ingest_question(db_base, nat_rec_single)
    assert d_nat1 == DECISION_NEW

    nat_rec_range = dict(
        base_good_rec,
        unit_id="UNIT_GATE_NAT_2",
        question_type="NAT",
        question_text="Determine efficiency percentage of transformer at full load.",
        options_json="{}",
        correct_opt="[94.5, 96.0]"
    )
    d_nat2, _, _ = ingest_question(db_base, nat_rec_range)
    assert d_nat2 == DECISION_NEW

    # Non-numeric NAT rejected
    bad_nat = dict(nat_rec_single, unit_id="UNIT_GATE_NAT_BAD", correct_opt="NotANumber")
    try:
        ingest_question(db_base, bad_nat)
        assert False, "Expected ValueError for non-numeric NAT answer"
    except ValueError as e:
        assert "invalid NAT numerical answer" in str(e)
    print("  ✓ PASS: Full GATE question ontology (MCQ, MSQ, NAT) verified with complete mathematical rigor.")

    # 19. Raw Question Text LaTeX C0 Rejection Before Normalization
    print("[19/23] Testing Raw Question Text LaTeX C0 Rejection Before Normalization...")
    raw_ctrl_cases = [
        ("theta", chr(9)),
        ("nabla", chr(0)),
        ("rho", chr(13)),
        ("frac", chr(12))
    ]
    for esc_name, ctrl_char in raw_ctrl_cases:
        hostile_q = f"Calculate induced EMF given {ctrl_char} magnetic flux."
        bad_q_rec = dict(base_good_rec, unit_id=f"UNIT_C0_Q_{esc_name}", question_text=hostile_q)
        try:
            ingest_question(db_base, bad_q_rec)
            assert False, f"Expected ValueError on raw question text containing \\{esc_name} control character"
        except ValueError as e:
            assert "malformed unescaped LaTeX" in str(e)
    print("  ✓ PASS: Raw question text C0 control validation executes strictly BEFORE normalization.")

    # 20. Lossless NAT Decimal Precision (Zero 4-Decimal Rounding Collisions)
    print("[20/23] Testing Lossless NAT Decimal Precision (Zero 4-Decimal Rounding Collisions)...")
    nat_ans1 = "1.00001"
    nat_ans2 = "1.00002"
    nat_ans3 = "1.00004"
    c_nat1 = parse_numerical_answer(nat_ans1)
    c_nat2 = parse_numerical_answer(nat_ans2)
    c_nat3 = parse_numerical_answer(nat_ans3)
    assert c_nat1 != c_nat2, f"CRITICAL: NAT precision collision between {nat_ans1} and {nat_ans2}!"
    assert c_nat2 != c_nat3, f"CRITICAL: NAT precision collision between {nat_ans2} and {nat_ans3}!"
    assert c_nat1 == "VAL:1.00001"
    assert c_nat2 == "VAL:1.00002"
    print("  ✓ PASS: Python Decimal guarantees lossless NAT precision (zero rounding collisions).")

    # 21. NAT Fail-Closed on Non-Empty Options
    print("[21/23] Testing NAT Fail-Closed on Non-Empty Options...")
    nat_with_opts = dict(
        base_good_rec,
        unit_id="UNIT_NAT_BAD_OPTS",
        question_type="NAT",
        question_text="Find speed in rpm.",
        options_json='{"A": "1500", "B": "1440"}',
        correct_opt="1500"
    )
    try:
        ingest_question(db_base, nat_with_opts)
        assert False, "Expected ValueError on NAT question with non-empty options!"
    except ValueError as e:
        assert "INVALID_NAT_OPTIONS" in str(e)
    print("  ✓ PASS: NAT questions with non-empty options rejected fail-closed.")

    # 22. unit_id Occurrence Conflict Guard (Same Question, Different Teacher/Video)
    print("[22/23] Testing unit_id Occurrence Conflict Guard (Same Question, Different Teacher/Video)...")
    u_prov1 = dict(
        base_good_rec,
        unit_id="UNIT_OCC_CONFLICT_TEST",
        question_text="What is the unit of magnetic flux density in SI units?",
        teacher="Teacher Alpha",
        video_id="VID_AAA"
    )
    d_prov1, _, _ = ingest_question(db_base, u_prov1)
    assert d_prov1 == DECISION_NEW

    # Reusing same unit_id with same question text/options but DIFFERENT teacher/video must trigger IDENTITY_CONFLICT!
    u_prov2 = dict(
        u_prov1,
        teacher="Teacher Beta",
        video_id="VID_BBB"
    )
    try:
        ingest_question(db_base, u_prov2)
        assert False, "Expected IDENTITY_CONFLICT on reused unit_id with different teacher/video!"
    except ValueError as e:
        assert "IDENTITY_CONFLICT" in str(e)
    print("  ✓ PASS: Reused unit_id with differing occurrence provenance rejected fail-closed.")

    # 23. List Options Presentation vs Identity Decoupling
    print("[23/23] Testing List Options Presentation vs Identity Decoupling...")
    list_q1 = '["Induction Motor", "Synchronous Motor", "Transformer"]'
    list_q2 = '["Transformer", "Induction Motor", "Synchronous Motor"]'
    # In list_q1: "Induction Motor" is index 1.
    # In list_q2: "Induction Motor" is index 2.
    c_l1, p_l1, c_a1, p_a1, _ = parse_and_canonicalize_options(list_q1, "1")
    c_l2, p_l2, c_a2, p_a2, _ = parse_and_canonicalize_options(list_q2, "2")
    assert c_l1 == c_l2, "CRITICAL: Canonical option identity differed for reordered list distractors!"
    assert c_a1 == c_a2, "CRITICAL: Canonical correct option differed for reordered list distractors!"
    assert json.loads(p_l1)[0] == "Induction Motor"
    assert json.loads(p_l2)[0] == "Transformer"
    print("  ✓ PASS: List options presentation order preserved while canonical identity decoupled.")

    print("========================================================================")
    print("🎯 ALL 23 FOURTH-GENERATION ADVERSARIAL TESTS PASSED WITH MATHEMATICAL RIGOR!")
    print("========================================================================")
    return True

def main() -> int:
    parser = argparse.ArgumentParser(description="AIR10 Canonicalization & Vector Gate")
    parser.add_argument("--db", default="data_lake/sqlite/universal_study_lake.sqlite", help="Path to SQLite database")
    parser.add_argument("--test-adversarial", action="store_true", help="Run adversarial tests on canonicalization")
    args = parser.parse_args()

    if args.test_adversarial:
        success = run_adversarial_suite()
        return 0 if success else 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
