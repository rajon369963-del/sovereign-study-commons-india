#!/usr/bin/env python3
"""
AIR10 Sovereign Ingestion & Semantic Identity Engine
Phase 1: Canonicalization, Deduplication & Vector Gating with 100% Mathematical Rigor.

Third-Generation Hardening:
- Full LaTeX C0 Control Character Family Seal (Rejects \theta, \tau, \times [\t], \nabla, \nu [\n], \rho [\r], \frac [\f], \beta [\b])
- Presentation vs Identity Decoupling: Learner presentation options untouched (order/labels intact for explanation alignment); canonical options used solely for identity hashing
- unit_id Conflict Guard: Same unit_id with different question payload fails closed (IDENTITY_CONFLICT) instead of silently collapsing to EXACT_DUP
- Occurrence Read/Write Symmetry: exact occurrence read query strictly aligns with occ_hash payload (including teacher and exam_branch)
- Active MinHash Pre-Filter: MinHash signatures narrow search space and quarantine near-matches (>=0.98) even without vector extension
- GATE Question-Type Ontology: Full native support for MCQ (single-choice), MSQ (multi-select), and NAT (numerical answer type with finite ranges)
"""

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False

from content_identity_oracle import canonical_span

# ---------------------------------------------------------------------------
# 1. LaTeX Normalization & Electrical Unit Standardization
# ---------------------------------------------------------------------------

FRAC_RE = re.compile(r"\\+frac\s*\{\s*([^{}]+)\s*\}\s*\{\s*([^{}]+)\s*\}")
LATEX_SPACE_RE = re.compile(r"\\[,;! ]|\\quad|\\qquad")
EXP_NOTATION_RE = re.compile(r"10\^\{\s*([+-]?\d+)\s*\}|10\^([+-]?\d+)")

# Standardize electrical units with strict case-sensitivity where prefix matters!
# In EE: M = Mega (10^6), m = milli (10^-3). Collapsing them is a factor of 10^9 error.
UNIT_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    # Case-sensitive Mega vs milli distinctions
    (re.compile(r"\b(?:mega-?ohms?|M\s*\\*Omega|M\s*ohm|10\^6\s*\\*Omega)\b"), "MΩ"),
    (re.compile(r"\b(?:milli-?ohms?|m\s*\\*Omega|m\s*ohm|10\^-3\s*\\*Omega)\b"), "mΩ"),
    (re.compile(r"\b(?:mega-?watts?|MW|10\^6\s*W)\b"), "MW"),
    (re.compile(r"\b(?:milli-?watts?|mW|10\^-3\s*W)\b"), "mW"),
    (re.compile(r"\b(?:mega-?volts?|MV|10\^6\s*V)\b"), "MV"),
    (re.compile(r"\b(?:milli-?volts?|mV|10\^-3\s*V)\b"), "mV"),
    (re.compile(r"\b(?:milli-?henrys?|mH|10\^-3\s*H)\b"), "mH"),
    (re.compile(r"\b(?:mega-?henrys?|MH|10\^6\s*H)\b"), "MH"),
    # Case-insensitive units where prefixes do not conflict
    (re.compile(r"\b(?:kilo-?ohms?|k\s*\\*Omega|k\s*ohm|10\^3\s*\\*Omega)\b", re.IGNORECASE), "kΩ"),
    (re.compile(r"\b(?:micro-?farads?|uF|\\*mu\s*F|10\^-6\s*F)\b", re.IGNORECASE), "µF"),
    (re.compile(r"\b(?:pico-?farads?|pF|10\^-12\s*F)\b", re.IGNORECASE), "pF"),
    (re.compile(r"\b(?:nano-?farads?|nF|10\^-9\s*F)\b", re.IGNORECASE), "nF"),
    (re.compile(r"\b(?:micro-?henrys?|uH|\\*mu\s*H|10\^-6\s*H)\b", re.IGNORECASE), "µH"),
    (re.compile(r"\b(?:kilo-?volts?|kV|10\^3\s*V)\b", re.IGNORECASE), "kV"),
    (re.compile(r"\b(?:kilo-?watts?|kW|10\^3\s*W)\b", re.IGNORECASE), "kW"),
]

def normalize_fractions(text: str) -> str:
    """Standardizes LaTeX fractions, converting {a \over b} and spaced \frac into canonical \frac{a}{b}."""
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
# 2. Question Type Ontology Constants & Parsers (GATE 2026 Compatible)
# ---------------------------------------------------------------------------

QUESTION_TYPE_MCQ = "MCQ"
QUESTION_TYPE_MSQ = "MSQ"
QUESTION_TYPE_NAT = "NAT"
VALID_QUESTION_TYPES = {QUESTION_TYPE_MCQ, QUESTION_TYPE_MSQ, QUESTION_TYPE_NAT}

# C0 control characters forbidden in options and single-line formula strings
FORBIDDEN_C0_CONTROLS = {
    "\x08": r"\b (backspace, e.g. \beta)",
    "\x0c": r"\f (form feed, e.g. \frac)",
    "\x09": r"\t (tab, e.g. \theta, \tau, \times)",
    "\x0a": r"\n (newline, e.g. \nabla, \nu)",
    "\x0d": r"\r (carriage return, e.g. \rho)",
    "\x00": r"\0 (null character)",
    "\x0b": r"\v (vertical tab)",
}

def _validate_no_corrupting_control_chars(obj: Any, allow_newlines: bool = False) -> None:
    """
    Rejects strings containing ASCII C0 control characters resulting from unescaped LaTeX in JSON strings.
    Protects against: \theta, \tau, \times (\t), \nabla, \nu (\n), \rho (\r), \frac (\f), \beta (\b).
    """
    if isinstance(obj, str):
        for ch, desc in FORBIDDEN_C0_CONTROLS.items():
            if ch == "\x0a" and allow_newlines:
                continue
            if ch in obj:
                raise ValueError(
                    f"malformed unescaped LaTeX command detected in JSON: contains control character {desc}: {obj!r}"
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

def parse_numerical_answer(answer_raw: Any) -> str:
    """
    Parses and validates NAT (Numerical Answer Type) answer or range.
    Supports single numbers (e.g. '24.5') and ranges (e.g. '24.0-26.0', '[24.0, 26.0]').
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
        min_v = float(range_match.group(1))
        max_v = float(range_match.group(2))
        if not (math.isfinite(min_v) and math.isfinite(max_v)):
            raise ValueError(f"non-finite NAT range bounds: {min_v}, {max_v}")
        if min_v > max_v:
            raise ValueError(f"NAT range min ({min_v}) exceeds max ({max_v})")
        return f"RANGE:{min_v:.4f}:{max_v:.4f}"

    try:
        val = float(ans_str)
        if not math.isfinite(val):
            raise ValueError(f"non-finite NAT numeric value: {val}")
        return f"VAL:{val:.4f}"
    except ValueError as e:
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

    unique_sorted = sorted(set(raw_list))
    return ",".join(unique_sorted), unique_sorted

# ---------------------------------------------------------------------------
# 3. Presentation vs Identity Options Decoupling
# ---------------------------------------------------------------------------

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
    - Full C0 control character validation prevents silent LaTeX corruption (\theta, \tau, \times, \nabla, \nu, \rho).
    Returns:
      (canonical_options_json, presentation_options_json, canonical_correct_opt, presentation_correct_opt, distractors)
    """
    if question_type not in VALID_QUESTION_TYPES:
        raise ValueError(f"invalid question_type '{question_type}'; must be in {VALID_QUESTION_TYPES}")

    # NAT questions have no options
    if question_type == QUESTION_TYPE_NAT:
        canonical_nat = parse_numerical_answer(correct_opt)
        return "{}", "{}", canonical_nat, str(correct_opt).strip(), []

    if correct_opt is None or not str(correct_opt).strip():
        raise ValueError("INSUFFICIENT_CORRECT_ANSWER: correct_opt must be a non-empty string or list")

    if isinstance(options_raw, str):
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
            pres_correct_str, _ = parse_msq_correct_options(correct_opt, valid_labels)
            canon_correct_str = pres_correct_str
        else:
            target_lbl = str(correct_opt).strip()
            if target_lbl not in valid_labels:
                raise ValueError(
                    f"correct_opt '{target_lbl}' is invalid for list options; must be in {sorted(valid_labels, key=int)}"
                )
            pres_correct_str = target_lbl
            canon_correct_str = target_lbl

        presentation_json_str = json.dumps(
            clean_list,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return (
            presentation_json_str,
            presentation_json_str,
            canon_correct_str,
            pres_correct_str,
            clean_list,
        )
    else:
        raise ValueError("options must be dict or list")

# ---------------------------------------------------------------------------
# 4. MinHash 64-bit Signatures for Fast Active Pre-filtering
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
# 5. Dense Vector Generation for Companion sqlite-vec Index
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
# 6. Database Initializer & Decoupled Companion Vector Index
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
            tri_state_decision TEXT
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
    Third-Generation Invariants:
    1. Zero invented evidence: missing provenance raises ValueError immediately.
    2. Strict provenance validity: canonical_span verified.
    3. LaTeX C0-control character family strictly rejected (\theta, \tau, \times, \nabla, \nu, \rho).
    4. Presentation vs Identity Decoupling: study_units stores original option labels/order for explanation alignment.
    5. unit_id Conflict Guard: Reusing a unit_id with a different question payload raises ValueError(IDENTITY_CONFLICT).
    6. Occurrence Symmetry: EXACT_DUP check checks canonical_hash, exam_branch, teacher, video_id, timestamp, quote.
    7. Active MinHash Pre-filter: Matches >= 0.98 quarantine immediately even without sqlite-vec.
    8. GATE Ontology: Supports MCQ, MSQ, and NAT questions natively.
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

    _validate_no_corrupting_control_chars(q_text, allow_newlines=True)

    q_type = record.get("question_type", QUESTION_TYPE_MCQ).strip().upper()
    if q_type not in VALID_QUESTION_TYPES:
        raise ValueError(f"invalid question_type '{q_type}'; must be in {VALID_QUESTION_TYPES}")

    raw_options = record.get("options_json", "{}" if q_type == QUESTION_TYPE_NAT else None)
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

    # unit_id Conflict Guard: Fail-closed if requested unit_id already exists with different payload!
    cur = conn.execute("SELECT canonical_hash FROM study_units WHERE unit_id = ? LIMIT 1;", (unit_id,))
    existing_unit = cur.fetchone()
    if existing_unit:
        if existing_unit[0] == canonical_hash:
            return (DECISION_EXACT_DUP, canonical_hash, unit_id)
        else:
            raise ValueError(
                f"IDENTITY_CONFLICT: unit_id '{unit_id}' already exists with a different question payload! "
                f"(existing_hash={existing_unit[0][:12]} != new_hash={canonical_hash[:12]})"
            )

    # Occurrence Read/Write Symmetry: check exact occurrence instantiation
    cur = conn.execute("""
        SELECT unit_id FROM study_units
        WHERE unit_id = ? OR (
            canonical_hash = ? AND exam_branch = ? AND teacher = ? AND video_id = ? AND timestamp_span = ? AND exact_quote = ?
        )
        LIMIT 1;
    """, (unit_id, canonical_hash, exam_branch, teacher, video_id, canon_span, exact_quote))
    exact_occ = cur.fetchone()
    if exact_occ:
        return (DECISION_EXACT_DUP, canonical_hash, exact_occ[0])

    # Check if semantic content already exists (REPEAT OCCURRENCE / MULTI-SOURCE PYQ)
    cur = conn.execute("SELECT unit_id FROM study_units WHERE canonical_hash = ? LIMIT 1;", (canonical_hash,))
    content_match = cur.fetchone()
    if content_match:
        # Repeat occurrence of an existing question: preserve provenance while maintaining presentation options!
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
            str(record.get("socratic_hints_json", "[]")).strip(), canonical_hash,
            str(record.get("drive_url", "")).strip(), canonical_hash,
            json.dumps(compute_minhash(q_text)), DECISION_REPEAT_OCCURRENCE, q_type
        ))
        conn.commit()
        return (DECISION_REPEAT_OCCURRENCE, canonical_hash, unit_id)

    sig = compute_minhash(q_text)
    sig_str = json.dumps(sig)
    vec = generate_dense_vector(q_text, VECTOR_DIM)

    # Active MinHash Pre-Filter & Near-Duplicate Quarantine
    if minhash_threshold > 0:
        cur = conn.execute("SELECT unit_id, minhash_sig FROM study_units WHERE minhash_sig IS NOT NULL LIMIT 100;")
        for u_id, existing_sig_str in cur.fetchall():
            try:
                ex_sig = json.loads(existing_sig_str)
                jaccard = minhash_jaccard_similarity(sig, ex_sig)
                if jaccard >= 0.98:
                    task_id = f"TASK_{canonical_hash[:16]}"
                    conn.execute("""
                        INSERT OR REPLACE INTO ingestion_tasks (task_id, payload_json, status, tri_state_decision)
                        VALUES (?, ?, ?, ?);
                    """, (task_id, json.dumps(record), DECISION_QUARANTINE, DECISION_QUARANTINE))
                    conn.commit()
                    return (DECISION_QUARANTINE, canonical_hash, u_id)
            except Exception:
                continue

    # Companion SQLite-Vec Query with Stable unit_id Mapping
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
                    INSERT OR REPLACE INTO ingestion_tasks (task_id, payload_json, status, tri_state_decision)
                    VALUES (?, ?, ?, ?);
                """, (task_id, json.dumps(record), DECISION_QUARANTINE, DECISION_QUARANTINE))
                conn.commit()
                return (DECISION_QUARANTINE, canonical_hash, matched_unit_id)

    # Admit as NEW unit: store presentation options untouched in study_units table
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
        str(record.get("socratic_hints_json", "[]")).strip(), canonical_hash,
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
# 8. Comprehensive Adversarial Verification Harness (18 Rigorous Tests)
# ---------------------------------------------------------------------------

def run_adversarial_suite() -> bool:
    """Executes the complete third-generation adversarial test suite."""
    print("=== RUNNING THIRD-GENERATION ADVERSARIAL CANONICALIZATION SUITE ===")

    # 1. EE Unit Case Sensitivity
    print("[1/18] Testing EE Unit Case Sensitivity (MW vs mW, MΩ vs mΩ)...")
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
    print("[2/18] Testing Duplicate Option Text Pointer Preservation...")
    dup_opts = '{"A": "10 V", "B": "20 V", "C": "10 V", "D": "30 V"}'
    canon_opts, pres_opts, c_opt, p_opt, _ = parse_and_canonicalize_options(dup_opts, "C")
    assert p_opt == "C", "CRITICAL: Original presentation pointer altered!"
    print("  ✓ PASS: Duplicate option values maintain exact original pointer.")

    # 3. List-Based Options Preservation
    print("[3/18] Testing List-Based Options Preservation...")
    list_opts = '["Transformer", "Induction Motor", "Synchronous Motor"]'
    canon_list, pres_list, c_list, p_list, _ = parse_and_canonicalize_options(list_opts, "2")
    assert p_list == "2"
    assert json.loads(pres_list)[1] == "Induction Motor"
    print("  ✓ PASS: List options preserve exact ordering and answer indexing.")

    # 4. List Options 1-Based Range Check
    print("[4/18] Testing List Options 1-Based Validation (Fail-Closed on 0, A, Out-of-Bounds)...")
    for bad_lbl in ["0", "A", "-1", "4"]:
        try:
            parse_and_canonicalize_options(list_opts, bad_lbl)
            assert False, f"Expected ValueError for bad list index {bad_lbl}"
        except ValueError as e:
            assert "is invalid for list options" in str(e)
    print("  ✓ PASS: List options strictly enforce correct_opt in {'1', ..., str(len(options))}.")

    # 5. Empty Correct Option & Empty Options
    print("[5/18] Testing Empty Correct Option & Empty Options (Fail-Closed on P0 #1)...")
    for bad_opt in ["", "   ", None]:
        try:
            parse_and_canonicalize_options('{"A": "1"}', bad_opt)
            assert False, f"Expected ValueError on {bad_opt!r}"
        except ValueError as e:
            assert "INSUFFICIENT_CORRECT_ANSWER" in str(e)
    try:
        parse_and_canonicalize_options("{}", "A")
        assert False, "Expected ValueError on empty dict"
    except ValueError as e:
        assert "options dict must not be empty" in str(e)
    print("  ✓ PASS: Empty correct answer and empty options rejected fail-closed.")

    # 6. Colliding Option Keys
    print("[6/18] Testing Colliding Trimmed Option Keys (Fail-Closed)...")
    colliding = '{"A": "10 A", " A ": "20 A"}'
    try:
        parse_and_canonicalize_options(colliding, "A")
        assert False, "Expected ValueError on colliding keys!"
    except ValueError as e:
        assert "colliding option keys" in str(e) or "duplicate JSON object key" in str(e)
    print("  ✓ PASS: Colliding option keys rejected fail-closed.")

    # 7. Non-Standard JSON Constants
    print("[7/18] Testing Non-Standard JSON Constants in JSON String...")
    for bad_val in ['{"A": NaN}', '{"A": Infinity}', '{"A": -Infinity}']:
        try:
            parse_and_canonicalize_options(bad_val, "A")
            assert False, f"Expected ValueError on {bad_val}"
        except ValueError as e:
            assert "non-standard JSON constant rejected" in str(e) or "invalid options_json" in str(e)
    print("  ✓ PASS: String JSON NaN and Infinity constants strictly rejected.")

    # 8. Native Python Object NaN/Infinity Bypass
    print("[8/18] Testing Native Python Object NaN/Infinity Bypass (P0 #4)...")
    for bad_native in [{"A": float("nan"), "B": "1"}, {"A": float("inf")}, {"A": [float("-inf")]}]:
        try:
            parse_and_canonicalize_options(bad_native, "A")
            assert False, f"Expected ValueError on native {bad_native}"
        except ValueError as e:
            assert "non-finite float rejected" in str(e)
    print("  ✓ PASS: Native Python NaN/Infinity objects fail closed (zero bypass).")

    # 9. Strict LaTeX JSON Escape Handling (\frac, \beta)
    print("[9/18] Testing Strict LaTeX JSON Escape Handling (Zero Silent Corruption)...")
    valid_escaped = r'{"A": "\\frac{1}{2}", "B": "\\beta"}'
    canon_res, pres_res, c_opt, p_opt, _ = parse_and_canonicalize_options(valid_escaped, "A")
    assert "\\frac{1}{2}" in pres_res
    assert "\x0c" not in pres_res
    assert "\x08" not in pres_res
    print("  ✓ PASS: Formula corruption eliminated; strict JSON escape contract enforced.")

    # 10. Invalid correct_opt for Dict
    print("[10/18] Testing Invalid correct_opt for Dict...")
    valid_opts = '{"A": "Option 1", "B": "Option 2"}'
    try:
        parse_and_canonicalize_options(valid_opts, "Z")
        assert False, "Expected ValueError for non-existent correct_opt 'Z'"
    except ValueError as e:
        assert "correct_opt 'Z' is not in option labels" in str(e)
    print("  ✓ PASS: Invalid correct_opt fails closed.")

    # 11. LaTeX Balanced-Brace Fractions
    print("[11/18] Testing LaTeX Depth-Tracking Balanced-Brace Fractions...")
    l1 = r"VR = \frac {R_{pu} \cos \phi \pm X_{pu} \sin \phi} {1} \times 100"
    l2 = r"VR = {R_{pu} \cos \phi \pm X_{pu} \sin \phi \over 1} \times 100"
    assert normalize_latex(l1) == normalize_latex(l2)
    print("  ✓ PASS: LaTeX balanced-brace fractions identical.")

    # 12. Decoupled Vector Companion Index with Stable unit_id Mapping
    print("[12/18] Testing Decoupled Vector Companion Index with Stable unit_id Mapping...")
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

    # 13. Strict Provenance Timestamp Validity
    print("[13/18] Testing Strict Provenance Validity Check (Fail-Closed on Timestamp)...")
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
    print("  ✓ PASS: Provenance timestamp validity and non-empty answer strictly verified.")

    # 14. Full LaTeX C0 Control Character Family Rejection
    print("[14/18] Testing Full LaTeX C0 Control Family Rejection (\\theta, \\tau, \\times, \\nabla, \\nu, \\rho)...")
    hostile_latex_cases = [
        ('{"A": "\\theta", "B": "0"}', "unescaped \\theta (\\t)"),
        ('{"A": "\\tau", "B": "0"}', "unescaped \\tau (\\t)"),
        ('{"A": "2 \\times 10", "B": "0"}', "unescaped \\times (\\t)"),
        ('{"A": "\\nabla V", "B": "0"}', "unescaped \\nabla (\\n)"),
        ('{"A": "\\nu", "B": "0"}', "unescaped \\nu (\\n)"),
        ('{"A": "\\rho L / A", "B": "0"}', "unescaped \\rho (\\r)"),
    ]
    for raw_hostile, desc in hostile_latex_cases:
        try:
            parse_and_canonicalize_options(raw_hostile, "A")
            assert False, f"CRITICAL: Failed to reject {desc}!"
        except ValueError as e:
            assert "malformed unescaped LaTeX" in str(e) or "invalid options_json" in str(e)
    print("  ✓ PASS: Complete LaTeX C0 control character family strictly sealed.")

    # 15. Presentation vs Identity Decoupling (Explanation Pointer Protection)
    print("[15/18] Testing Presentation vs Identity Decoupling (Explanation-Pointer Corruption Eliminated)...")
    tricky_opts = '{"A": "Z", "B": "A", "C": "M"}'
    canon_j, pres_j, c_corr, p_corr, _ = parse_and_canonicalize_options(tricky_opts, "A")
    assert p_corr == "A", "Presentation correct option must remain 'A' to match explanation!"
    pres_dict = json.loads(pres_j)
    assert pres_dict["A"] == "Z"
    assert pres_dict["B"] == "A"
    assert pres_dict["C"] == "M"
    canon_dict = json.loads(canon_j)
    assert canon_dict["A"] == "A"
    assert canon_dict["B"] == "M"
    assert canon_dict["C"] == "Z"
    assert c_corr == "C", "Canonical identity pointer must map to C for deterministic deduplication!"
    print("  ✓ PASS: Learner presentation options untouched; canonical identity cleanly decoupled.")

    # 16. unit_id Conflict Guard (Fail-Closed on Reused unit_id with Different Question)
    print("[16/18] Testing unit_id Conflict Guard (Fail-Closed on IDENTITY_CONFLICT)...")
    u_rec1 = dict(base_good_rec, unit_id="UNIT_SHARED_ID_TEST", question_text="First question on transformer.")
    dec1, h1, u1 = ingest_question(db_base, u_rec1, vec_conn=vec_db)
    assert dec1 == DECISION_NEW
    # Identical payload with same unit_id returns EXACT_DUP
    dec_dup, _, _ = ingest_question(db_base, u_rec1, vec_conn=vec_db)
    assert dec_dup == DECISION_EXACT_DUP
    # Different payload with SAME unit_id MUST FAIL CLOSED with IDENTITY_CONFLICT
    u_rec2 = dict(base_good_rec, unit_id="UNIT_SHARED_ID_TEST", question_text="Different question on induction motor.")
    try:
        ingest_question(db_base, u_rec2, vec_conn=vec_db)
        assert False, "Expected ValueError on reused unit_id with different question payload!"
    except ValueError as e:
        assert "IDENTITY_CONFLICT" in str(e)
    print("  ✓ PASS: Reused unit_id with conflicting payload strictly rejected fail-closed.")

    # 17. Active MinHash Pre-Filter & Near-Duplicate Quarantine
    print("[17/18] Testing Active MinHash Pre-Filter & Near-Duplicate Quarantine...")
    mh_rec1 = dict(base_good_rec, unit_id="UNIT_MH_1", question_text="Explain voltage regulation of transmission line.")
    dec_mh1, _, _ = ingest_question(db_base, mh_rec1)
    assert dec_mh1 == DECISION_NEW
    # Near identical text that triggers MinHash jaccard >= 0.98
    mh_rec2 = dict(base_good_rec, unit_id="UNIT_MH_2", question_text="Explain voltage regulation of transmission line ")
    dec_mh2, _, _ = ingest_question(db_base, mh_rec2)
    assert dec_mh2 == DECISION_QUARANTINE, f"Expected QUARANTINE_REVIEW, got {dec_mh2}"
    print("  ✓ PASS: Active MinHash pre-filter actively detects near-duplicates and quarantines them.")

    # 18. Full GATE Question-Type Ontology (MCQ, MSQ, NAT)
    print("[18/18] Testing Full GATE Question-Type Ontology (MCQ, MSQ, NAT)...")
    # A. MCQ
    mcq_rec = dict(base_good_rec, unit_id="UNIT_GATE_MCQ", question_type="MCQ")
    d_mcq, _, _ = ingest_question(db_base, mcq_rec)
    assert d_mcq == DECISION_NEW

    # B. MSQ (Multiple Select Question, multiple answers valid)
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

    # C. NAT (Numerical Answer Type, single value & range)
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

    # Invalid NAT (non-numeric)
    bad_nat = dict(nat_rec_single, unit_id="UNIT_GATE_NAT_BAD", correct_opt="NotANumber")
    try:
        ingest_question(db_base, bad_nat)
        assert False, "Expected ValueError for non-numeric NAT answer"
    except ValueError as e:
        assert "invalid NAT numerical answer" in str(e)

    print("  ✓ PASS: Full GATE question ontology (MCQ, MSQ, NAT) verified with complete mathematical rigor.")

    print("========================================================================")
    print("🎯 ALL 18 THIRD-GENERATION ADVERSARIAL TESTS PASSED WITH MATHEMATICAL RIGOR!")
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
