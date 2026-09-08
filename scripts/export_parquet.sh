#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DUCKDB_BIN="/Users/rajondas/.local/bin/duckdb"

if ! command -v "$DUCKDB_BIN" &>/dev/null; then
  if command -v duckdb &>/dev/null; then
    DUCKDB_BIN="duckdb"
  else
    echo "❌ Error: duckdb binary not found!"
    exit 1
  fi
fi

SQLITE_DB="$REPO_ROOT/data_lake/sqlite/universal_study_lake.sqlite"
PARQUET_OUT="$REPO_ROOT/data_lake/parquet/universal_study_lake.parquet"

echo "⚡ [AIR10 DUCKDB EXPORTER] Exporting $SQLITE_DB to $PARQUET_OUT..."

"$DUCKDB_BIN" -c "
INSTALL sqlite_scanner;
LOAD sqlite_scanner;
ATTACH '$SQLITE_DB' AS lake (TYPE SQLITE);
COPY (SELECT * FROM lake.study_units ORDER BY unit_id ASC) TO '$PARQUET_OUT' (FORMAT PARQUET, COMPRESSION ZSTD);
"

echo "✅ Successfully exported Parquet lake:"
ls -lh "$PARQUET_OUT"

echo "📊 Verification Query:"
"$DUCKDB_BIN" -c "
SELECT exam_branch, COUNT(*) as units_count, COUNT(DISTINCT teacher) as teacher_count
FROM '$PARQUET_OUT'
GROUP BY exam_branch;
"
