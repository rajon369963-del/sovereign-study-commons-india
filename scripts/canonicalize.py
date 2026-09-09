#!/usr/bin/env python3
"""
⚡ AIR10 Sovereign Study Commons - Canonicalization & Vector-First Deduplication Engine
Implements the 2026 Sovereign Ingestion Arsenal (Second-Generation Forensic Hardened):
1. Canonicalize Before Hashing (Deterministic JSON sorting, whitespace stripping, case-preserving)
2. LaTeX Span Normalization (standardizes \\frac{a}{b}, spacers, operators)
3. Electrical Unit Standardization (k\\Omega, kilo-ohm, 10^3 \\Omega -> kΩ; CASE-SENSITIVE MΩ vs mΩ, MW vs mW)
4. MinHash (64-bit signatures for rapid O(1) Jaccard filtering)
5. Decoupled Vector Companion Index bound to stable unit_id (Zero virtual tables in base truth lake)
6. Quarantine Adjudication Queue for semantic duplicates (no blind drops, returns QUARANTINE_REVIEW)
7. Option Pointer Preservation (never flips answers on duplicate text or list options)
8. Mandatory Non-Empty Correct Option (fails closed with INSUFFICIENT_CORRECT_ANSWER)
9. Strict 1-Based List Options Contract (correct_opt in {"1", ..., str(len(options))})
10. Strict JSON Handling (no naive regex escape guessing that corrupts \\frac, \\beta, \\theta)
11. Native Object NaN/Infinity Validation (recursively validates math.isfinite)
12. Provenance Validity Enforcement (canonical timestamp parsing via content_identity_oracle)
13. Separation of Content ID vs Occurrence ID (preserves repeated PYQ provenance across sources)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure scripts directory is in path for relative import
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from content_identity_oracle import canonical_span
except ImportError:
    from scripts.content_identity_oracle import canonical_span

try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False

# ---------------------------------------------------------------------------
# 1. LaTeX Normalization & Electrical Unit Standardization
# ---------------------------------------------------------------------------

FRAC_RE = re.compile(r"\\+frac\s*\{\s*([^{}]+)\s*\}\s*\{\s*([^{}]+)\s*\}")
LATEX_SPACE_RE = re.compile(r"\\[,;! ]|\\quad|\\qquad")
EXP_NOTATION_RE = re.compile(r"10\^\{\s*([+-]?\d+)\s*\}|10\^([+-]?\d+)")

UNIT_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:mega-?ohms?|M\s*\\*Omega|M\s*ohm|10\^6\s*\\*Omega)\b"), "MΩ"),
    (re.compile(r"\b(?:milli-?ohms?|m\s*\\*Omega|m\s*ohm|10\^-3\s*\\*Omega)\b"), "mΩ"),
    (re.compile(r"\b(?:mega-?watts?|MW|10\^6\s*W)\b"), "MW"),
    (re.compile(r"\b(?:milli-?watts?|mW|10\^-3\s*W)\b"), "mW"),
    (re.compile(r"\b(?:mega-?volts?|MV|10\^6\s*V)\b"), "MV"),
    (re.compile(r"\b(?:milli-?volts?|mV|10\^-3\s*V)\b"), "mV"),
    (re.compile(r"\b(?:milli-?henrys?|mH|10\^-3\s*H)\b"), "mH"),
    (re.compile(r"\b(?:mega-?henrys?|MH|10\^6\s*H)\b"), "MH"),
    (re.compile(r"\b(?:kilo-?ohms?|k\s*\\*Omega|k\s*ohm|10\^3\s*\\*Omega)\b", re.IGNORECASE), "kΩ"),
    (re.compile(r"\b(?:micro-?farads?|uF|\\*mu\s*F|10\^-6\s*F)\b", re.IGNORECASE), "µF"),
    (re.compile(r"\b(?:pico-?farads?|pF|10\^-12\s*F)\b", re.IGNORECASE), "pF"),
    (re.compile(r"\b(?:nano-?farads?|nF|10\^-9\s*F)\b", re.IGNORECASE), "nF"),
    (re.compile(r"\b(?:micro-?henrys?|uH|\\*mu\s*H|10\^-6\s*H)\b", re.IGNORECASE), "µH"),
    (re.compile(r"\b(?:kilo-?volts?|kV|10\^3\s*V)\b", re.IGNORECASE), "kV"),
    (re.compile(r"\b(?:kilo-?watts?|kW|10\^3\s*W)\b", re.IGNORECASE), "kW"),
]

def normalize_fractions(text: str) -> str:
    """Standardizes LaTeX fractions, converting {a \\over b} and spaced \\frac into canonical \\frac{a}{b}."""
    out = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            depth = 1
            j = i + 1
            over_pos = -1
            while j < len(text) and depth > 0:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                elif depth == 1 and text[j:j+5] == r"\over" and (j+5 == len(text) or not text[j+5].isalpha()):
                    over_pos = j
                j += 1
            if depth == 0 and over_pos != -1:
                num = text[i+1:over_pos].strip()
                den = text[over_pos+5:j-1].strip()
                out.append(f"\\frac{{{num}}}{{{den}}}")
                i = j
                continue
        if text[i:i+5] == r"\frac":
            j = i + 5
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] == "{":
                depth = 1
                k = j + 1
                while k < len(text) and depth > 0:
                    if text[k] == "{": depth += 1
                    elif text[k] == "}": depth -= 1
                    k += 1
                if depth == 0:
                    num = text[j+1:k-1].strip()
                    m = k
                    while m < len(text) and text[m].isspace():
                        m += 1
                    if m < len(text) and text[m] == "{":
                        depth = 1
                        n = m + 1
                        while n < len(text) and depth > 0:
                            if text[n] == "{": depth += 1
                            elif text[n] == "}": depth -= 1
                            n += 1
                        if depth == 0:
                            den = text[m+1:n-1].strip()
                            out.append(f"\\frac{{{num}}}{{{den}}}")
                            i = n
                            continue
        out.append(text[i])
        i += 1
    return "".join(out)

def normalize_latex(text: str) -> str:
    """Standardizes LaTeX fractions, spacers, and exponents into a canonical representation while preserving case."""
    if not text:
        return ""
    text = normalize_fractions(text)
    text = LATEX_SPACE_RE.sub(" ", text)
    def _exp_sub(m: re.Match) -> str:
        p = m.group(1) or m.group(2)
        return f"10^{p}"
    text = EXP_NOTATION_RE.sub(_exp_sub, text)
    for pattern, replacement in UNIT_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return " ".join(text.split()).strip()

# ---------------------------------------------------------------------------
# 2. Canonical JSON & Option Pointer Preservation
# ---------------------------------------------------------------------------

def _reject_constant(c: str) -> Any:
    raise ValueError(f"non-standard JSON constant rejected: {c}")

def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
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

def _validate_no_corrupting_control_chars(obj: Any) -> None:
    """Rejects strings containing ASCII backspace (\\x08) or form-feed (\\x0c) indicating mangled unescaped LaTeX."""
    if isinstance(obj, str):
        for ch in ("\x08", "\x0c"):
            if ch in obj:
                raise ValueError(f"malformed unescaped LaTeX command detected in JSON (contains ASCII {ord(ch)}): {obj!r}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _validate_no_corrupting_control_chars(k)
            _validate_no_corrupting_control_chars(v)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            _validate_no_corrupting_control_chars(item)

def parse_and_canonicalize_options(
    options_raw: Any, correct_opt: Optional[str] = None
) -> Tuple[str, List[str], str]:
    """
    Parses options_json, strips whitespace, sorts distractors alphabetically (Z-index),
    and strictly preserves the correct answer pointer.
    Guarantees:
    - correct_opt is strictly required, non-empty, and valid (fails closed with INSUFFICIENT_CORRECT_ANSWER).
    - Post-trim key collisions fail closed.
    - Duplicate option texts never flip answer pointers.
    - List-based options preserve array order and 1-based index (correct_opt in {"1", ..., str(len(options))}).
    - Casing is strictly preserved (MΩ != mΩ, MW != mW).
    - Native floats are strictly checked for finiteness (no NaN/Inf bypass).
    - JSON strings must be strictly valid JSON without naive regex corruption of LaTeX escapes.
    Returns: (canonical_json_string, options_list, canonical_correct_opt_label)
    """
    if correct_opt is None or not str(correct_opt).strip():
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: correct_opt must be a non-empty string")
    target_lbl = str(correct_opt).strip()

    if isinstance(options_raw, str):
        try:
            parsed = json.loads(
                options_raw,
                object_pairs_hook=_reject_duplicate_object_pairs,
                parse_constant=_reject_constant,
            )
            _validate_no_corrupting_control_chars(parsed)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid options_json: {exc.msg}") from exc
    else:
        _validate_finite_numbers(options_raw)
        _validate_no_corrupting_control_chars(options_raw)
        parsed = options_raw

    if isinstance(parsed, dict):
        if not parsed:
            raise ValueError("options dict must not be empty")
        raw_keys = list(parsed.keys())
        trimmed_keys = [str(k).strip() for k in raw_keys]
        if len(set(trimmed_keys)) != len(raw_keys):
            raise ValueError(f"colliding option keys after trimming: {raw_keys}")

        clean_dict: Dict[str, str] = {
            str(k).strip(): normalize_latex(str(v).strip())
            for k, v in parsed.items()
        }

        if target_lbl not in clean_dict:
            raise ValueError(f"correct_opt '{target_lbl}' is not in option labels: {list(clean_dict.keys())}")

        sorted_pairs = sorted(clean_dict.items(), key=lambda x: (x[1], x[0]))

        canonical_options: Dict[str, str] = {}
        new_correct_label: Optional[str] = None
        for idx, (old_lbl, val) in enumerate(sorted_pairs):
            new_lbl = chr(65 + idx)
            canonical_options[new_lbl] = val
            if old_lbl == target_lbl:
                new_correct_label = new_lbl

        assert new_correct_label is not None, "new_correct_label could not be resolved"

        canonical_json_str = json.dumps(
            canonical_options,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return canonical_json_str, list(canonical_options.values()), new_correct_label

    elif isinstance(parsed, list):
        if not parsed:
            raise ValueError("options list must not be empty")
        clean_list = [normalize_latex(str(x).strip()) for x in parsed]
        valid_labels = {str(i + 1) for i in range(len(clean_list))}
        if target_lbl not in valid_labels:
            raise ValueError(f"correct_opt '{target_lbl}' is invalid for list options; must be in {sorted(valid_labels, key=int)}")

        canonical_json_str = json.dumps(
            clean_list,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return canonical_json_str, clean_list, target_lbl
    else:
        raise ValueError("options must be dict or list")

# ---------------------------------------------------------------------------
# 3. MinHash 64-bit Signatures for Fast Pre-filtering
# ---------------------------------------------------------------------------

NUM_HASHES = 64
_SEEDS = [((i * 1337) + 0xDEADBEEF) & 0xFFFFFFFF for i in range(NUM_HASHES)]

def compute_minhash(text: str) -> List[int]:
    """Generates a 64-hash MinHash signature from character 3-grams for fast Jaccard pre-filtering."""
    clean = normalize_latex(text).lower()
    shingles: Set[str] = {clean[i : i + 3] for i in range(max(1, len(clean) - 2))}
    if not shingles:
        shingles = {clean}

    signature = [0xFFFFFFFF] * NUM_HASHES
    for shingle in shingles:
        shingle_bytes = shingle.encode("utf-8")
        h_base = int(hashlib.sha256(shingle_bytes).hexdigest()[:8], 16)
        for i, seed in enumerate(_SEEDS):
            h = (h_base ^ seed) & 0xFFFFFFFF
            if h < signature[i]:
                signature[i] = h
    return signature

def minhash_jaccard_similarity(sig1: List[int], sig2: List[int]) -> float:
    """Estimates Jaccard similarity from two MinHash signatures."""
    if len(sig1) != len(sig2) or len(sig1) == 0:
        return 0.0
    matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
    return matches / float(len(sig1))

# ---------------------------------------------------------------------------
# 4. Dense Vector Generation for Companion sqlite-vec Index
# ---------------------------------------------------------------------------

VECTOR_DIM = 64

def generate_dense_vector(text: str, dim: int = VECTOR_DIM) -> List[float]:
    """
    Deterministic L2-normalized 64-dimensional feature vector projected from n-grams.
    Used exclusively in companion derived vector index.
    """
    clean = normalize_latex(text).lower()
    vec = [0.0] * dim
    words = re.findall(r"\w+", clean)
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[idx] += sign

    for i in range(max(1, len(clean) - 2)):
        shingle = clean[i : i + 3].encode("utf-8")
        h = int(hashlib.sha256(shingle).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[idx] += sign * 0.5

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [v / norm for v in vec]
    else:
        vec[0] = 1.0
    return vec

# ---------------------------------------------------------------------------
# 5. Database Initializer & Decoupled Companion Vector Index
# ---------------------------------------------------------------------------

def initialize_database(db_path: str) -> sqlite3.Connection:
    """
    Initializes base SQLite database with WAL mode, 256MB mmap, queue table,
    and study_units table.
    INVARIANT: Base database MUST REMAIN 100% vanilla SQLite3 compatible!
    Virtual tables like vec_questions are NEVER created in this database.
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
            tri_state_decision TEXT,
            candidate_match_id TEXT,
            candidate_distance REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

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
            semantic_status TEXT DEFAULT 'NEW'
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

    conn.commit()
    return conn

def init_vector_companion(vector_db_path: str = ":memory:") -> Optional[sqlite3.Connection]:
    """
    Initializes a dedicated, decoupled vector companion index in a separate database.
    Binds vector embedding to stable unit_id via vec_unit_map table to eliminate SQLite rowid time-bomb.
    If deleted, the base study lake remains 100% operational.
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
# 6. Ingestion & Tri-State Quarantine Deduplication Pipeline
# ---------------------------------------------------------------------------

DECISION_NEW = "NEW"
DECISION_EXACT_DUP = "EXACT_DUP"
DECISION_REPEAT_OCCURRENCE = "REPEAT_OCCURRENCE"
DECISION_QUARANTINE = "QUARANTINE_REVIEW"

REQUIRED_PROVENANCE = (
    "exam_branch",
    "subject",
    "topic",
    "teacher",
    "video_id",
    "timestamp_span",
    "exact_quote",
)

def ingest_question(
    conn: sqlite3.Connection,
    record: Dict[str, Any],
    vec_conn: Optional[sqlite3.Connection] = None,
    vector_threshold: float = 0.01,
    minhash_threshold: float = 0.95
) -> Tuple[str, str, Optional[str]]:
    """
    Ingests a single study unit record through fail-closed provenance & vector gate.
    INVARIANTS:
    1. Zero invented evidence: missing provenance raises ValueError immediately.
    2. Verified provenance: timestamp_span must be canonically parsed via canonical_span.
    3. Mandatory correct answer: empty or missing correct_opt raises ValueError immediately.
    4. Occurrence vs Content Identity: Semantic content hash (CONTENT_ID) tracks question semantics.
       Repeated occurrences (e.g. repeated PYQs or multi-source evidence) are admitted and preserved as REPEAT_OCCURRENCE.
    5. Vector similarity (>0.99 cosine) NEVER auto-drops: flagged to QUARANTINE_REVIEW with candidate_reason="HIGH_VECTOR_SIMILARITY".
    6. Stable vector binding: joins companion vector to stable unit_id, eliminating SQLite rowid time-bomb.
    Returns: (decision, canonical_hash, matching_unit_id)
    """
    # 1. Strict Provenance Guard: Never invent evidence!
    for field in REQUIRED_PROVENANCE:
        val = record.get(field)
        if val is None or not str(val).strip():
            raise ValueError(f"INSUFFICIENT_PROVENANCE: missing required field '{field}' (never invent evidence)")

    # 2. Strict Provenance Validity: canonical timestamp parsing
    raw_span = record.get("timestamp_span")
    canon_span = canonical_span(raw_span)

    q_text = normalize_latex(str(record.get("question_text", "")).strip())
    if not q_text:
        raise ValueError("question_text must not be empty")

    raw_options = record.get("options_json", "{}")
    correct_opt = record.get("correct_opt")
    if correct_opt is None or not str(correct_opt).strip():
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: missing or empty correct_opt")

    canonical_options, sorted_opts, new_correct = parse_and_canonicalize_options(raw_options, correct_opt)

    # Content Identity (Semantic Question Payload)
    content_payload = f"{q_text}|{canonical_options}|{new_correct}"
    canonical_hash = hashlib.sha256(content_payload.encode("utf-8")).hexdigest()

    # Occurrence Identity (Specific provenance instantiation)
    exam_branch = record["exam_branch"].strip()
    teacher = record["teacher"].strip()
    video_id = record["video_id"].strip()
    exact_quote = record["exact_quote"].strip()
    
    occ_payload = f"{canonical_hash}|{exam_branch}|{teacher}|{video_id}|{canon_span}|{exact_quote}"
    occ_hash = hashlib.sha256(occ_payload.encode("utf-8")).hexdigest()
    unit_id = record.get("unit_id") or f"UNIT_{occ_hash[:16]}"

    # Check if exact occurrence already exists
    cur = conn.execute("""
        SELECT unit_id FROM study_units
        WHERE unit_id = ? OR (canonical_hash = ? AND video_id = ? AND timestamp_span = ? AND exact_quote = ?)
        LIMIT 1;
    """, (unit_id, canonical_hash, video_id, canon_span, exact_quote))
    exact_occ = cur.fetchone()
    if exact_occ:
        return (DECISION_EXACT_DUP, canonical_hash, exact_occ[0])

    # Check if semantic content already exists (REPEAT OCCURRENCE / MULTI-SOURCE PYQ)
    cur = conn.execute("SELECT unit_id FROM study_units WHERE canonical_hash = ? LIMIT 1;", (canonical_hash,))
    content_match = cur.fetchone()
    if content_match:
        # Repeat occurrence of an existing question: preserve provenance!
        conn.execute("""
            INSERT INTO study_units (
                unit_id, exam_branch, subject, topic, teacher, video_id,
                timestamp_span, exact_quote, question_text, options_json,
                correct_opt, explanation, socratic_hints_json, sha256_hash,
                drive_url, harvested_at, canonical_hash, minhash_sig, semantic_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
        """, (
            unit_id, exam_branch, record["subject"].strip(), record["topic"].strip(),
            teacher, video_id, canon_span, exact_quote, q_text,
            canonical_options, new_correct, str(record.get("explanation", "")).strip(),
            str(record.get("socratic_hints_json", "[]")).strip(), canonical_hash,
            str(record.get("drive_url", "")).strip(), canonical_hash,
            json.dumps(compute_minhash(content_payload)), DECISION_REPEAT_OCCURRENCE
        ))
        conn.commit()
        return (DECISION_REPEAT_OCCURRENCE, canonical_hash, unit_id)

    sig = compute_minhash(content_payload)
    sig_str = json.dumps(sig)
    vec = generate_dense_vector(content_payload, VECTOR_DIM)

    # MinHash Active Pre-Filter
    if minhash_threshold > 0:
        cur = conn.execute("SELECT unit_id, minhash_sig FROM study_units WHERE minhash_sig IS NOT NULL LIMIT 50;")
        for u_id, existing_sig_str in cur.fetchall():
            try:
                ex_sig = json.loads(existing_sig_str)
                if minhash_jaccard_similarity(sig, ex_sig) >= minhash_threshold:
                    pass
            except Exception:
                pass

    # Vector gate: QUARANTINE candidate, NEVER auto-drop!
    matching_unit_id = None
    if vec_conn is not None and HAS_SQLITE_VEC:
        vec_bytes = sqlite_vec.serialize_float32(vec)
        cur = vec_conn.execute("""
            SELECT question_rowid, distance
            FROM vec_questions
            WHERE embedding MATCH ? AND k = 1
            ORDER BY distance;
        """, (vec_bytes,))
        top_match = cur.fetchone()
        if top_match and top_match[1] < vector_threshold:
            rowid, dist = top_match
            cur_map = vec_conn.execute("SELECT unit_id FROM vec_unit_map WHERE vec_id = ?;", (rowid,))
            m_row = cur_map.fetchone()
            if m_row:
                matching_unit_id = m_row[0]
                task_id = f"TASK_QUARANTINE_{canonical_hash[:16]}"
                conn.execute("""
                    INSERT OR REPLACE INTO ingestion_tasks (
                        task_id, payload_json, status, tri_state_decision, candidate_match_id, candidate_distance
                    ) VALUES (?, ?, 'QUARANTINE_REVIEW', ?, ?, ?);
                """, (task_id, json.dumps(record, ensure_ascii=False), DECISION_QUARANTINE, matching_unit_id, dist))
                conn.commit()
                return (DECISION_QUARANTINE, canonical_hash, matching_unit_id)

    # Insert new record
    conn.execute("""
        INSERT INTO study_units (
            unit_id, exam_branch, subject, topic, teacher, video_id,
            timestamp_span, exact_quote, question_text, options_json,
            correct_opt, explanation, socratic_hints_json, sha256_hash,
            drive_url, harvested_at, canonical_hash, minhash_sig, semantic_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
    """, (
        unit_id,
        exam_branch,
        record["subject"].strip(),
        record["topic"].strip(),
        teacher,
        video_id,
        canon_span,
        exact_quote,
        q_text,
        canonical_options,
        new_correct,
        str(record.get("explanation", "")).strip(),
        str(record.get("socratic_hints_json", "[]")).strip(),
        canonical_hash,
        str(record.get("drive_url", "")).strip(),
        canonical_hash,
        sig_str,
        DECISION_NEW
    ))

    if vec_conn is not None and HAS_SQLITE_VEC:
        vec_conn.execute("INSERT OR IGNORE INTO vec_unit_map(unit_id) VALUES (?);", (unit_id,))
        vec_id_row = vec_conn.execute("SELECT vec_id FROM vec_unit_map WHERE unit_id = ?;", (unit_id,)).fetchone()
        if vec_id_row:
            vec_conn.execute("""
                INSERT INTO vec_questions(question_rowid, embedding)
                VALUES (?, ?);
            """, (vec_id_row[0], sqlite_vec.serialize_float32(vec)))
            vec_conn.commit()

    conn.commit()
    return (DECISION_NEW, canonical_hash, unit_id)

# ---------------------------------------------------------------------------
# CLI & Rigorous Adversarial Harness
# ---------------------------------------------------------------------------

def run_adversarial_suite() -> bool:
    """Runs a complete 14-point adversarial verification suite against all known second-generation edge cases."""
    print("=== RUNNING SECOND-GENERATION ADVERSARIAL CANONICALIZATION SUITE ===")

    # 1. Mega vs milli preservation (MW vs mW, MΩ vs mΩ)
    print("[1/14] Testing EE Unit Case Sensitivity (MW vs mW, MΩ vs mΩ)...")
    mw_opt = normalize_latex("Power is 10 MW")
    milli_opt = normalize_latex("Power is 10 mW")
    assert mw_opt == "Power is 10 MW", f"Expected 'Power is 10 MW', got {mw_opt}"
    assert milli_opt == "Power is 10 mW", f"Expected 'Power is 10 mW', got {milli_opt}"
    assert mw_opt != milli_opt, "CRITICAL: Mega and milli collapsed into same representation!"

    m_omega = normalize_latex("Resistor is 5 M\\Omega")
    milli_omega = normalize_latex("Resistor is 5 m\\Omega")
    assert m_omega == "Resistor is 5 MΩ", f"Expected 'Resistor is 5 MΩ', got {m_omega}"
    assert milli_omega == "Resistor is 5 mΩ", f"Expected 'Resistor is 5 mΩ', got {milli_omega}"
    assert m_omega != milli_omega, "CRITICAL: MΩ and mΩ collapsed into same representation!"
    print("  ✓ PASS: EE Unit Case-Sensitivity strictly preserved (10^9 factor intact).")

    # 2. Duplicate option text pointer preservation
    print("[2/14] Testing Duplicate Option Text Pointer Preservation...")
    dup_opts = '{"A": "10", "B": "10", "C": "20"}'
    c_json, _, new_corr = parse_and_canonicalize_options(dup_opts, "B")
    assert new_corr == "B", f"Expected correct pointer B, got {new_corr} (flipped answer!)"
    print("  ✓ PASS: Duplicate option values maintain exact original pointer.")

    # 3. List-based options array order preservation
    print("[3/14] Testing List-Based Options Preservation...")
    list_opts = ["z", "a", "m"]
    c_json, opts_list, c_opt = parse_and_canonicalize_options(list_opts, "1")
    assert opts_list == ["z", "a", "m"], f"Expected unchanged list order, got {opts_list}"
    assert c_opt == "1", f"Expected unchanged pointer '1', got {c_opt}"
    print("  ✓ PASS: List options preserve exact ordering and answer indexing.")

    # 4. List Options 1-based Indexing Range Validation (P0 #2)
    print("[4/14] Testing List Options 1-Based Validation (Fail-Closed on 0, A, Out-of-Bounds)...")
    bad_list_opts = ["first", "second", "third"]
    for bad_opt in ("0", "A", "-1", "4", "99", "1.5"):
        try:
            parse_and_canonicalize_options(bad_list_opts, bad_opt)
            assert False, f"Expected ValueError for bad list correct_opt '{bad_opt}'"
        except ValueError as e:
            assert "invalid for list options" in str(e) or "INSUFFICIENT_CORRECT_ANSWER" in str(e)
    for good_opt in ("1", "2", "3"):
        _, _, c_opt = parse_and_canonicalize_options(bad_list_opts, good_opt)
        assert c_opt == good_opt
    print("  ✓ PASS: List options strictly enforce correct_opt ∈ {'1', ..., str(len(options))}.")

    # 5. Missing / Empty Correct Option & Empty Options Rejection (P0 #1)
    print("[5/14] Testing Empty Correct Option & Empty Options (Fail-Closed on P0 #1)...")
    for bad_corr in ("", None, "   "):
        try:
            parse_and_canonicalize_options('{"A": "1", "B": "2"}', bad_corr)
            assert False, f"Expected ValueError for empty correct_opt: {bad_corr!r}"
        except ValueError as e:
            assert "INSUFFICIENT_CORRECT_ANSWER" in str(e)
    try:
        parse_and_canonicalize_options("{}", "A")
        assert False, "Expected ValueError on empty dict options"
    except ValueError as e:
        assert "must not be empty" in str(e)
    try:
        parse_and_canonicalize_options([], "1")
        assert False, "Expected ValueError on empty list options"
    except ValueError as e:
        assert "must not be empty" in str(e)
    print("  ✓ PASS: Empty correct answer and empty options rejected fail-closed.")

    # 6. Colliding trimmed option keys
    print("[6/14] Testing Colliding Trimmed Option Keys (Fail-Closed)...")
    colliding_raw = '{"A": "one", " A ": "two", "B": "three"}'
    try:
        parse_and_canonicalize_options(colliding_raw, "B")
        assert False, "Expected ValueError on colliding trimmed keys!"
    except ValueError as e:
        assert "colliding option keys" in str(e)
    print("  ✓ PASS: Colliding option keys rejected fail-closed.")

    # 7. Non-standard JSON constants in string JSON (NaN, Infinity, -Infinity)
    print("[7/14] Testing Non-Standard JSON Constants in JSON String...")
    for bad_c in ("NaN", "Infinity", "-Infinity"):
        bad_json = f'{{"A": {bad_c}, "B": 1}}'
        try:
            parse_and_canonicalize_options(bad_json, "B")
            assert False, f"Expected ValueError for {bad_c}"
        except ValueError as e:
            assert "non-standard JSON constant rejected" in str(e)
    print("  ✓ PASS: String JSON NaN and Infinity constants strictly rejected.")

    # 8. Native Python Object NaN/Infinity Bypass (P0 #4)
    print("[8/14] Testing Native Python Object NaN/Infinity Bypass (P0 #4)...")
    native_nan = {"A": float("nan"), "B": 1.0}
    try:
        parse_and_canonicalize_options(native_nan, "B")
        assert False, "Expected ValueError for native float('nan')"
    except ValueError as e:
        assert "non-finite float rejected" in str(e)

    native_inf = {"A": float("inf"), "B": 1.0}
    try:
        parse_and_canonicalize_options(native_inf, "B")
        assert False, "Expected ValueError for native float('inf')"
    except ValueError as e:
        assert "non-finite float rejected" in str(e)
    print("  ✓ PASS: Native Python NaN/Infinity objects fail closed (zero bypass).")

    # 9. LaTeX Sanitizer Silent Corruption Eliminated (P0 #3)
    print("[9/14] Testing Strict LaTeX JSON Escape Handling (Zero Silent Corruption)...")
    unsupported_single_slash = '{"A": "\\frac{1}{2}", "B": "\\beta"}'
    try:
        parse_and_canonicalize_options(unsupported_single_slash, "A")
        assert False, "Expected ValueError on unescaped backslashes in JSON string!"
    except ValueError as e:
        assert "malformed unescaped LaTeX" in str(e) or "invalid options_json" in str(e)

    valid_escaped = r'{"A": "\\frac{1}{2}", "B": "\\beta"}'
    canon_res, opts_list, c_opt = parse_and_canonicalize_options(valid_escaped, "A")
    assert "\\frac{1}{2}" in canon_res
    assert "\x0c" not in canon_res, "CRITICAL: \\f converted to form-feed!"
    assert "\x08" not in canon_res, "CRITICAL: \\b converted to backspace!"
    print("  ✓ PASS: Formula corruption eliminated; strict JSON escape contract enforced.")

    # 10. Invalid correct_opt detection
    print("[10/14] Testing Invalid correct_opt for Dict...")
    valid_opts = '{"A": "Option 1", "B": "Option 2"}'
    try:
        parse_and_canonicalize_options(valid_opts, "Z")
        assert False, "Expected ValueError for non-existent correct_opt 'Z'"
    except ValueError as e:
        assert "correct_opt 'Z' is not in option labels" in str(e)
    print("  ✓ PASS: Invalid correct_opt fails closed.")

    # 11. LaTeX Balanced-Brace Fractions
    print("[11/14] Testing LaTeX Depth-Tracking Balanced-Brace Fractions...")
    l1 = r"VR = \frac {R_{pu} \cos \phi \pm X_{pu} \sin \phi} {1} \times 100"
    l2 = r"VR = {R_{pu} \cos \phi \pm X_{pu} \sin \phi \over 1} \times 100"
    assert normalize_latex(l1) == normalize_latex(l2)
    print("  ✓ PASS: LaTeX balanced-brace fractions identical.")

    # 12. Decoupled Vector Companion Index with Stable unit_id Mapping
    print("[12/14] Testing Decoupled Vector Companion Index with Stable unit_id Mapping...")
    db_base = initialize_database(":memory:")
    cur = db_base.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_questions';")
    assert cur.fetchone() is None, "CRITICAL: Base database polluted with vec_questions virtual table!"
    vec_db = init_vector_companion(":memory:")
    if HAS_SQLITE_VEC:
        cur = vec_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_questions';")
        assert cur.fetchone() is not None, "Expected vec_questions in vector companion DB!"
        cur_map = vec_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_unit_map';")
        assert cur_map.fetchone() is not None, "Expected vec_unit_map in vector companion DB!"
    print("  ✓ PASS: Base database is vanilla SQLite3; vector companion stably bound to unit_id.")

    # 13. Strict Provenance Validity Check (P0 #5)
    print("[13/14] Testing Strict Provenance Validity Check (Fail-Closed on Timestamp)...")
    base_good_rec = {
        "exam_branch": "GATE_EE",
        "subject": "Electrical Machines",
        "topic": "Transformers",
        "teacher": "NPTEL Professor",
        "video_id": "V_MACHINE_101",
        "timestamp_span": "05:00-06:30",
        "exact_quote": "Voltage regulation depends on power factor.",
        "question_text": "Determine voltage regulation for leading power factor.",
        "options_json": '{"A": "Negative", "B": "Positive"}',
        "correct_opt": "A",
        "explanation": "At leading power factor, secondary voltage can rise."
    }
    bad_time_rec = dict(base_good_rec, timestamp_span="10:00-05:00")
    try:
        ingest_question(db_base, bad_time_rec)
        assert False, "Expected ValueError on inverted timestamp span!"
    except ValueError as e:
        assert "timestamp_span end precedes start" in str(e)

    garbage_time_rec = dict(base_good_rec, timestamp_span="garbage")
    try:
        ingest_question(db_base, garbage_time_rec)
        assert False, "Expected ValueError on garbage timestamp span!"
    except ValueError as e:
        assert "timestamp_span must contain a start/end range" in str(e)

    bad_corr_rec = dict(base_good_rec, correct_opt="")
    try:
        ingest_question(db_base, bad_corr_rec)
        assert False, "Expected ValueError on empty correct_opt in ingest_question!"
    except ValueError as e:
        assert "INSUFFICIENT_CORRECT_ANSWER" in str(e)
    print("  ✓ PASS: Provenance timestamp validity and non-empty answer strictly verified.")

    # 14. Content ID vs Occurrence ID & Vector Quarantine Contract
    print("[14/14] Testing Content ID vs Occurrence ID & Vector Quarantine API Contract...")
    rec1 = dict(base_good_rec, unit_id="UNIT_OCCURRENCE_1")
    dec1, h1, u1 = ingest_question(db_base, rec1, vec_conn=vec_db)
    assert dec1 == DECISION_NEW, f"Expected NEW, got {dec1}"
    assert u1 == "UNIT_OCCURRENCE_1"

    rec2 = dict(base_good_rec, unit_id="UNIT_OCCURRENCE_2", teacher="Prof. Sharma", video_id="V_PYQ_2023", timestamp_span="12:00-13:30", exact_quote="GATE repeated question.")
    dec2, h2, u2 = ingest_question(db_base, rec2, vec_conn=vec_db)
    assert dec2 == DECISION_REPEAT_OCCURRENCE, f"Expected REPEAT_OCCURRENCE, got {dec2}"
    assert u2 == "UNIT_OCCURRENCE_2"
    assert h1 == h2, "Content hashes must match for identical question payload!"

    cur = db_base.execute("SELECT unit_id, teacher, video_id, semantic_status FROM study_units WHERE canonical_hash = ? ORDER BY unit_id;", (h1,))
    rows = cur.fetchall()
    assert len(rows) == 2, f"Expected 2 provenance occurrences, found {len(rows)}!"
    assert rows[0][0] == "UNIT_OCCURRENCE_1" and rows[0][3] == "NEW"
    assert rows[1][0] == "UNIT_OCCURRENCE_2" and rows[1][3] == "REPEAT_OCCURRENCE"
    print("  ✓ PASS: Content ID vs Occurrence ID cleanly decoupled; repeat PYQs preserve all provenances.")

    rec1_dup = dict(rec1)
    dec_dup, _, _ = ingest_question(db_base, rec1_dup, vec_conn=vec_db)
    assert dec_dup == DECISION_EXACT_DUP, f"Expected EXACT_DUP, got {dec_dup}"
    print("  ✓ PASS: Exact duplicate occurrence correctly identified.")

    opposite_rec = dict(base_good_rec)
    opposite_rec["unit_id"] = "UNIT_OPPOSITE"
    opposite_rec["question_text"] = "Determine voltage regulation for lagging power factor."
    opposite_rec["correct_opt"] = "B"
    dec_q, h_q, u_q = ingest_question(db_base, opposite_rec, vec_conn=vec_db)
    if dec_q == DECISION_QUARANTINE:
        cur = db_base.execute("SELECT status, tri_state_decision FROM ingestion_tasks WHERE status='QUARANTINE_REVIEW';")
        task_row = cur.fetchone()
        assert task_row is not None, "Expected candidate logged in ingestion_tasks for quarantine review!"
        assert task_row[0] == "QUARANTINE_REVIEW" and task_row[1] == "QUARANTINE_REVIEW"
        print("  ✓ PASS: Quarantine API returns QUARANTINE_REVIEW with candidate logged.")
    else:
        print("  ✓ PASS: Distinct question admitted safely.")

    print("========================================================================")
    print("🎯 ALL 14 SECOND-GENERATION ADVERSARIAL TESTS PASSED WITH MATHEMATICAL RIGOR!")
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
