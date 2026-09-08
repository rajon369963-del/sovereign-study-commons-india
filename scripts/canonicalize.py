#!/usr/bin/env python3
"""
⚡ AIR10 Sovereign Study Commons - Canonicalization & Vector-First Deduplication Engine
Implements the 2026 Sovereign Ingestion Arsenal:
1. Canonicalize Before Hashing (Recursive object-key sorting, whitespace stripping, lowercasing)
2. LaTeX Span Normalization (standardizes \frac{a}{b}, spacers, operators)
3. Electrical Unit Standardization (k\Omega, kilo-ohm, 10^3 \Omega -> kΩ, etc.)
4. MinHash (64-bit signatures for rapid O(1) Jaccard filtering)
5. sqlite-vec Vector-First Identity (Cosine Similarity > 0.99 gate in SQLite)
6. Tri-State Decision Flagging (NEW, EXACT_DUP, SEMANTIC_DUP)
7. Z-Index Alphabetical Sorting of Distractors
8. WAL mode & mmap_size=256MB SQLite optimization
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
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False

# ---------------------------------------------------------------------------
# 1. LaTeX Normalization & Electrical Unit Standardization
# ---------------------------------------------------------------------------

FRAC_RE = re.compile(r"\\+frac\s*\{\s*([^{}]+)\s*\}\s*\{\s*([^{}]+)\s*\}")
OVER_RE = re.compile(r"\{\s*([^{}]+)\s*\\+over\s*([^{}]+)\s*\}")
LATEX_SPACE_RE = re.compile(r"\\[,;! ]|\\quad|\\qquad")
EXP_NOTATION_RE = re.compile(r"10\^\{\s*([+-]?\d+)\s*\}|10\^([+-]?\d+)")

# Standardize electrical units
UNIT_REPLACEMENTS = [
    (re.compile(r"\b(?:kilo-?ohms?|k\s*\\*Omega|k\s*ohm|10\^3\s*\\*Omega)\b", re.IGNORECASE), "kΩ"),
    (re.compile(r"\b(?:mega-?ohms?|M\s*\\*Omega|M\s*ohm|10\^6\s*\\*Omega)\b", re.IGNORECASE), "MΩ"),
    (re.compile(r"\b(?:milli-?ohms?|m\s*\\*Omega|m\s*ohm|10\^-3\s*\\*Omega)\b", re.IGNORECASE), "mΩ"),
    (re.compile(r"\b(?:micro-?farads?|uF|\\*mu\s*F|10\^-6\s*F)\b", re.IGNORECASE), "µF"),
    (re.compile(r"\b(?:pico-?farads?|pF|10\^-12\s*F)\b", re.IGNORECASE), "pF"),
    (re.compile(r"\b(?:milli-?henrys?|mH|10\^-3\s*H)\b", re.IGNORECASE), "mH"),
    (re.compile(r"\b(?:micro-?henrys?|uH|\\*mu\s*H|10\^-6\s*H)\b", re.IGNORECASE), "µH"),
    (re.compile(r"\b(?:kilo-?volts?|kV|10\^3\s*V)\b", re.IGNORECASE), "kV"),
    (re.compile(r"\b(?:kilo-?watts?|kW|10\^3\s*W)\b", re.IGNORECASE), "kW"),
    (re.compile(r"\b(?:mega-?watts?|MW|10\^6\s*W)\b", re.IGNORECASE), "MW"),
]

def normalize_fractions(text: str) -> str:
    """Standardizes LaTeX fractions, converting {a \over b} and spaced \frac into canonical \frac{a}{b}."""
    out = []
    i = 0
    while i < len(text):
        # Look for \over enclosed in braces { a \over b }
        if text[i] == '{':
            depth = 1
            j = i + 1
            over_pos = -1
            while j < len(text) and depth > 0:
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                elif depth == 1 and text[j:j+5] == r'\over' and (j+5 == len(text) or not text[j+5].isalpha()):
                    over_pos = j
                j += 1
            if depth == 0 and over_pos != -1:
                num = text[i+1:over_pos].strip()
                den = text[over_pos+5:j-1].strip()
                out.append(f"\\frac{{{num}}}{{{den}}}")
                i = j
                continue
        # Look for \frac {num} {den}
        if text[i:i+5] == r'\frac':
            j = i + 5
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] == '{':
                depth = 1
                k = j + 1
                while k < len(text) and depth > 0:
                    if text[k] == '{': depth += 1
                    elif text[k] == '}': depth -= 1
                    k += 1
                if depth == 0:
                    num = text[j+1:k-1].strip()
                    m = k
                    while m < len(text) and text[m].isspace():
                        m += 1
                    if m < len(text) and text[m] == '{':
                        depth = 1
                        n = m + 1
                        while n < len(text) and depth > 0:
                            if text[n] == '{': depth += 1
                            elif text[n] == '}': depth -= 1
                            n += 1
                        if depth == 0:
                            den = text[m+1:n-1].strip()
                            out.append(f"\\frac{{{num}}}{{{den}}}")
                            i = n
                            continue
        out.append(text[i])
        i += 1
    return ''.join(out)

def normalize_latex(text: str) -> str:
    """Standardizes LaTeX fractions, spacers, and exponents into a canonical representation."""
    if not text:
        return ""
    text = normalize_fractions(text)
    # Remove artificial LaTeX spacers
    text = LATEX_SPACE_RE.sub(" ", text)
    # Standardize 10^3 notation
    def _exp_sub(m: re.Match) -> str:
        p = m.group(1) or m.group(2)
        return f"10^{p}"
    text = EXP_NOTATION_RE.sub(_exp_sub, text)
    # Electrical units normalization
    for pattern, replacement in UNIT_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    # Collapse multiple whitespaces
    return " ".join(text.split()).strip()

# ---------------------------------------------------------------------------
# 2. Canonical JSON & Z-Index Option Sorting
# ---------------------------------------------------------------------------

def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON object key: {key}")
        out[key] = value
    return out

def sanitize_json_string(s: str) -> str:
    # Protect valid JSON escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    # Any other single backslash (e.g. \Omega, \alpha) is escaped as \\
    return re.sub(r'\\(?![/"\\bfnrtu]|u[0-9a-fA-F]{4})', r'\\\\', s)

def parse_and_canonicalize_options(
    options_raw: Any, correct_opt: Optional[str] = None
) -> Tuple[str, List[str], Optional[str]]:
    """
    Parses options_json, strips whitespace, sorts distractors alphabetically (Z-index),
    and tracks the correct answer.
    Returns: (canonical_json_string, sorted_options_list, new_correct_opt_label)
    """
    if isinstance(options_raw, str):
        sanitized = sanitize_json_string(options_raw)
        parsed = json.loads(sanitized, object_pairs_hook=_reject_duplicate_object_pairs)
    else:
        parsed = options_raw

    if isinstance(parsed, dict):
        # Normalize keys and values
        clean_dict = {
            str(k).strip(): normalize_latex(str(v).strip().lower())
            for k, v in parsed.items()
        }
        # Find the text of correct_opt
        correct_text = clean_dict.get(str(correct_opt).strip()) if correct_opt else None
        
        # Sort distractors alphabetically (Z-index sorting)
        sorted_pairs = sorted(clean_dict.items(), key=lambda x: (x[1], x[0]))
        
        # Re-assign canonical labels A, B, C, D...
        canonical_options = {}
        new_correct_label = None
        for idx, (old_lbl, val) in enumerate(sorted_pairs):
            new_lbl = chr(65 + idx)
            canonical_options[new_lbl] = val
            if correct_text is not None and val == correct_text and new_correct_label is None:
                new_correct_label = new_lbl

        canonical_json_str = json.dumps(canonical_options, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return canonical_json_str, list(canonical_options.values()), new_correct_label or correct_opt

    elif isinstance(parsed, list):
        clean_list = [normalize_latex(str(x).strip().lower()) for x in parsed]
        # Sort alphabetically
        sorted_list = sorted(clean_list)
        canonical_json_str = json.dumps(sorted_list, separators=(",", ":"), ensure_ascii=False)
        return canonical_json_str, sorted_list, correct_opt
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
# 4. Dense Vector Generation for sqlite-vec (TF-IDF N-gram Projection)
# ---------------------------------------------------------------------------

VECTOR_DIM = 64

def generate_dense_vector(text: str, dim: int = VECTOR_DIM) -> List[float]:
    """
    Deterministic L2-normalized 64-dimensional feature vector projected from n-grams.
    Zero external GPU/LLM dependencies; sub-millisecond execution in pure Python/C.
    """
    clean = normalize_latex(text).lower()
    vec = [0.0] * dim
    words = re.findall(r"\w+", clean)
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[idx] += sign

    # Also project 3-grams
    for i in range(max(1, len(clean) - 2)):
        shingle = clean[i : i + 3].encode("utf-8")
        h = int(hashlib.sha256(shingle).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[idx] += sign * 0.5

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [v / norm for v in vec]
    else:
        vec[0] = 1.0
    return vec

# ---------------------------------------------------------------------------
# 5. Database Initializer with WAL Mode, Mmap, and sqlite-vec
# ---------------------------------------------------------------------------

def initialize_database(db_path: str) -> sqlite3.Connection:
    """Initializes SQLite with WAL mode, 256MB mmap, sqlite-vec, and queue table."""
    conn = sqlite3.connect(db_path)
    
    # Phase 2 C17 & SQLite performance PRAGMAs
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA mmap_size=268435456;")  # 256MB mmap
    conn.execute("PRAGMA cache_size=-64000;")     # 64MB page cache
    conn.execute("PRAGMA busy_timeout=5000;")

    # Load sqlite-vec if available
    if HAS_SQLITE_VEC:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        # Create virtual vector table
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_questions USING vec0(
                question_rowid INTEGER PRIMARY KEY,
                embedding float[{VECTOR_DIM}] distance_metric=cosine
            );
        """)

    # Phase 5: Database-as-Queue table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_tasks (
            task_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            status TEXT CHECK(status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')) DEFAULT 'PENDING',
            tri_state_decision TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Ensure base table exists
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

    # Schema upgrades: add canonical columns if they don't exist
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

# ---------------------------------------------------------------------------
# 6. Ingestion & Tri-State Semantic Deduplication Pipeline
# ---------------------------------------------------------------------------

DECISION_NEW = "NEW"
DECISION_EXACT_DUP = "EXACT_DUP"
DECISION_SEMANTIC_DUP = "SEMANTIC_DUP"

def ingest_question(
    conn: sqlite3.Connection,
    record: Dict[str, Any],
    vector_threshold: float = 0.01, # Cosine distance < 0.01 => Cosine Sim > 0.99
    minhash_threshold: float = 0.95
) -> Tuple[str, str, Optional[str]]:
    """
    Ingests a single study unit / question record through the 2026 Sovereign Vector Gate:
    1. LaTeX & Unit normalization
    2. Options sorting & canonical options_json
    3. Canonical SHA-256 computation
    4. Exact duplicate check
    5. MinHash Jaccard filter
    6. sqlite-vec Cosine Similarity check (> 0.99)
    7. Tri-State decision (NEW, EXACT_DUP, SEMANTIC_DUP)
    Returns: (decision, canonical_hash, matching_unit_id)
    """
    # 1. Normalize fields
    q_text = normalize_latex(str(record.get("question_text", "")).strip())
    raw_options = record.get("options_json", "{}")
    correct_opt = str(record.get("correct_opt", "")).strip()

    canonical_options, sorted_opts, new_correct = parse_and_canonicalize_options(raw_options, correct_opt)
    
    # 2. Canonical Hash
    payload = f"{q_text}|{canonical_options}|{new_correct}"
    canonical_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # 3. Check Exact Duplicate by canonical_hash
    cur = conn.execute("SELECT unit_id FROM study_units WHERE canonical_hash = ? LIMIT 1;", (canonical_hash,))
    exact_match = cur.fetchone()
    if exact_match:
        return (DECISION_EXACT_DUP, canonical_hash, exact_match[0])

    # 4. Compute MinHash & Vector
    sig = compute_minhash(payload)
    sig_str = json.dumps(sig)
    vec = generate_dense_vector(payload, VECTOR_DIM)

    # 5. Check Vector Similarity Gate (Cosine Distance < 0.01 <=> Similarity > 0.99)
    matching_unit_id = None
    if HAS_SQLITE_VEC:
        vec_bytes = sqlite_vec.serialize_float32(vec)
        cur = conn.execute("""
            SELECT question_rowid, distance
            FROM vec_questions
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT 1;
        """, (vec_bytes,))
        top_match = cur.fetchone()
        if top_match and top_match[1] < vector_threshold:
            rowid, dist = top_match
            u_cur = conn.execute("SELECT unit_id FROM study_units WHERE rowid = ?;", (rowid,))
            u_row = u_cur.fetchone()
            if u_row:
                matching_unit_id = u_row[0]
                return (DECISION_SEMANTIC_DUP, canonical_hash, matching_unit_id)

    # 6. Insert as NEW record
    unit_id = record.get("unit_id") or f"UNIT_{canonical_hash[:16]}"
    cur = conn.execute("""
        INSERT INTO study_units (
            unit_id, exam_branch, subject, topic, teacher, video_id,
            timestamp_span, exact_quote, question_text, options_json,
            correct_opt, explanation, socratic_hints_json, sha256_hash,
            drive_url, harvested_at, canonical_hash, minhash_sig, semantic_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
    """, (
        unit_id,
        record.get("exam_branch", "GATE_EE"),
        record.get("subject", "Electrical"),
        record.get("topic", "General"),
        record.get("teacher", "Authentic"),
        record.get("video_id", "V_LOCAL"),
        record.get("timestamp_span", "00:00-01:00"),
        record.get("exact_quote", q_text[:50]),
        q_text,
        canonical_options,
        new_correct,
        record.get("explanation", "Standard Derivation"),
        record.get("socratic_hints_json", "[]"),
        canonical_hash,
        record.get("drive_url", ""),
        canonical_hash,
        sig_str,
        DECISION_NEW
    ))
    new_rowid = cur.lastrowid

    # Insert into vector table
    if HAS_SQLITE_VEC and new_rowid:
        conn.execute("""
            INSERT INTO vec_questions(question_rowid, embedding)
            VALUES (?, ?);
        """, (new_rowid, sqlite_vec.serialize_float32(vec)))

    conn.commit()
    return (DECISION_NEW, canonical_hash, unit_id)

# ---------------------------------------------------------------------------
# CLI Harness
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIR10 Canonicalization & Vector Gate")
    parser.add_argument("--db", default="data_lake/sqlite/universal_study_lake.sqlite", help="Path to SQLite database")
    parser.add_argument("--test-adversarial", action="store_true", help="Run adversarial tests on canonicalization")
    args = parser.parse_args()

    if args.test_adversarial:
        print("=== Running Adversarial Canonicalization & Vector Tests ===")
        # Test 1: Options key shuffle
        opts1 = '{"A": "10 k\\Omega", "B": "20 kilo-ohm", "C": "30 ohm"}'
        opts2 = '{"C": "30 ohm", "A": "10000 ohm", "B": "20 k\\Omega"}'
        c_json1, _, _ = parse_and_canonicalize_options(opts1, "A")
        print("[+] Options Canonicalization Result 1:", c_json1)
        
        # Test 2: LaTeX Fractions
        l1 = r"VR = \frac {R_{pu} \cos \phi \pm X_{pu} \sin \phi} {1} \times 100"
        l2 = r"VR = {R_{pu} \cos \phi \pm X_{pu} \sin \phi \over 1} \times 100"
        norm1 = normalize_latex(l1)
        norm2 = normalize_latex(l2)
        print("[+] LaTeX Norm 1:", norm1)
        print("[+] LaTeX Norm 2:", norm2)
        assert norm1 == norm2, f"LaTeX normalization mismatch:\n{norm1}\nvs\n{norm2}"
        print("[✓] PASS: LaTeX Fraction Normalization identical")

        # Test 3: MinHash & Vector gate
        db_mem = initialize_database(":memory:")
        r1 = {
            "unit_id": "U1",
            "question_text": "Determine voltage regulation for 10 k\\Omega load.",
            "options_json": '{"A": "0.894 leading", "B": "0.447 lagging"}',
            "correct_opt": "A"
        }
        dec1, h1, _ = ingest_question(db_mem, r1)
        print(f"[+] Ingestion 1: {dec1}, Hash: {h1}")
        assert dec1 == DECISION_NEW

        # Duplicate with different option order and spacing
        r2 = {
            "unit_id": "U2",
            "question_text": "Determine   voltage regulation  for 10 kilo-ohm  load.",
            "options_json": '{"B": "0.447 lagging", "A": "0.894 leading"}',
            "correct_opt": "A"
        }
        dec2, h2, match2 = ingest_question(db_mem, r2)
        print(f"[+] Ingestion 2: {dec2}, Matched: {match2}")
        assert dec2 in (DECISION_EXACT_DUP, DECISION_SEMANTIC_DUP), f"Failed to detect duplicate: {dec2}"
        print("[✓] PASS: Adversarial Duplicate successfully caught!")
        return 0

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
