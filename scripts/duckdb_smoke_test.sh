#!/usr/bin/env bash
# ==============================================================================
# Sovereign Study Commons India - DuckDB Smoke Test Harness (Issue #3)
# ==============================================================================
# Verifies that committed Parquet assets open successfully, validates schema,
# prints exact row counts, and executes bounded queries against documented columns.
# Exits non-zero immediately on any missing file, schema mismatch, or query error.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "=== Sovereign Study Commons India: DuckDB Smoke Test Harness ==="

# The smoke queries below use the DuckDB CLI directly. Fail closed before any
# dataset work instead of advertising a Python-module fallback that is not used.
if ! command -v duckdb >/dev/null 2>&1; then
    echo "[-] FATAL: DuckDB CLI is required for this smoke test but was not found in PATH." >&2
    echo "[-] Install the DuckDB CLI, then rerun ./scripts/duckdb_smoke_test.sh." >&2
    exit 1
fi
echo "[+] Using DuckDB CLI: $(command -v duckdb)"

# 1. Target Assets Verification
PARQUET_ASSETS=(
    "data_lake/parquet/universal_study_lake.parquet"
    "data_lake/parquet/gate_ee_5k_questions.parquet"
    "data_lake/parquet/upsc_polity_5k_videos.parquet"
)

for asset in "${PARQUET_ASSETS[@]}"; do
    if [[ ! -f "${asset}" ]]; then
        echo "[-] FATAL: Committed Parquet asset missing: ${asset}" >&2
        exit 1
    fi
    echo "[+] Verified file existence: ${asset} ($(stat -f%z "${asset}" 2>/dev/null || stat -c%s "${asset}") bytes)"
done

# 2. Schema and Row Count Inspection
echo ""
echo "=== 1. Schema & Row Count Inspection ==="
duckdb -c "
SELECT 
    'universal_study_lake' AS asset, 
    count(*) AS row_count,
    count(DISTINCT unit_id) AS distinct_units
FROM 'data_lake/parquet/universal_study_lake.parquet'
UNION ALL
SELECT 
    'gate_ee_5k_questions' AS asset, 
    count(*) AS row_count,
    count(DISTINCT id) AS distinct_units
FROM 'data_lake/parquet/gate_ee_5k_questions.parquet'
UNION ALL
SELECT 
    'upsc_polity_5k_videos' AS asset, 
    count(*) AS row_count,
    count(DISTINCT video_id) AS distinct_units
FROM 'data_lake/parquet/upsc_polity_5k_videos.parquet';
"

# 3. Bounded Query 1: Universal Study Lake Exam Distribution
echo ""
echo "=== 2. Bounded Query 1: Universal Study Lake Exam Distribution ==="
duckdb -c "
SELECT 
    exam_branch, 
    count(*) AS units, 
    count(DISTINCT teacher) AS teachers
FROM 'data_lake/parquet/universal_study_lake.parquet'
GROUP BY exam_branch
ORDER BY units DESC;
"

# 4. Bounded Query 2: GATE EE Questions Top Subjects & Average Marks
echo ""
echo "=== 3. Bounded Query 2: GATE EE Questions Top Subjects & Average Marks ==="
duckdb -c "
SELECT 
    subject, 
    count(*) AS q_count,
    round(avg(marks), 2) AS avg_marks,
    round(avg(negative_marks), 2) AS avg_neg_marks
FROM 'data_lake/parquet/gate_ee_5k_questions.parquet'
GROUP BY subject
ORDER BY q_count DESC
LIMIT 5;
"

# 5. Bounded Query 3: UPSC Polity Top Channels & Total Duration
echo ""
echo "=== 4. Bounded Query 3: UPSC Polity Top Teachers & Aggregated Duration ==="
duckdb -c "
SELECT 
    teacher, 
    count(*) AS video_count, 
    sum(duration) AS total_duration_seconds
FROM 'data_lake/parquet/upsc_polity_5k_videos.parquet'
GROUP BY teacher
ORDER BY video_count DESC
LIMIT 5;
"

echo ""
echo "[✓] PASS: All DuckDB smoke queries executed successfully against committed Parquet assets."
exit 0
