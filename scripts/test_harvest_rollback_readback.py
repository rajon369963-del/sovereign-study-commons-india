#!/usr/bin/env python3
"""Exact-path court for harvest export-failure rollback authority."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARVEST = ROOT / "scripts" / "harvest_community.js"

SCHEMA = """
CREATE TABLE study_units (
  unit_id TEXT PRIMARY KEY,
  exam_branch TEXT,
  subject TEXT,
  topic TEXT,
  teacher TEXT,
  video_id TEXT,
  timestamp_span TEXT,
  exact_quote TEXT,
  question_text TEXT,
  options_json TEXT,
  correct_opt TEXT,
  explanation TEXT,
  socratic_hints_json TEXT,
  sha256_hash TEXT,
  drive_url TEXT,
  harvested_at TEXT
);
"""

SQLITE_SHIM = r'''#!/usr/bin/env python3
import os
import sqlite3
import sys

if len(sys.argv) != 3:
    print("expected sqlite3 <db> <query>", file=sys.stderr)
    raise SystemExit(64)

db, query = sys.argv[1], sys.argv[2]
normalized = query.lstrip().upper()
mode = os.environ.get("HARVEST_TEST_DELETE_MODE", "NORMAL")

if normalized.startswith("DELETE FROM STUDY_UNITS"):
    if mode == "NOOP":
        raise SystemExit(0)
    if mode == "BLOCK":
        print("simulated rollback lock", file=sys.stderr)
        raise SystemExit(75)

con = sqlite3.connect(db)
try:
    if normalized.startswith("SELECT"):
        rows = con.execute(query).fetchall()
        for row in rows:
            print("|".join("" if value is None else str(value) for value in row))
    else:
        con.executescript(query)
        con.commit()
finally:
    con.close()
'''


def make_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def row_count(db: Path) -> int:
    with sqlite3.connect(db) as con:
        return int(con.execute("SELECT COUNT(*) FROM study_units").fetchone()[0])


def run_case(*, delete_mode: str, export_success: bool) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="harvest-rollback-court-") as tmp_raw:
        tmp = Path(tmp_raw)
        db = tmp / "study.sqlite"
        with sqlite3.connect(db) as con:
            con.executescript(SCHEMA)

        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        make_executable(bin_dir / "sqlite3", SQLITE_SHIM)

        c17 = tmp / "clean_vtt"
        make_executable(c17, "#!/usr/bin/env bash\nset -euo pipefail\nprintf '%s\\n' 'cleaned verified quote'\n")

        export = tmp / "export_parquet.sh"
        if export_success:
            make_executable(export, "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")
        else:
            make_executable(export, "#!/usr/bin/env bash\nset -euo pipefail\nexit 42\n")

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                "HARVEST_SQLITE_DB": str(db),
                "HARVEST_EXPORT_SCRIPT": str(export),
                "HARVEST_C17_CLEAN_VTT": str(c17),
                "HARVEST_TEST_DELETE_MODE": delete_mode,
                "EXAM_BRANCH": "TEST",
                "SUBJECT": "Physics",
                "TOPIC": "Rollback authority",
                "TEACHER": "Fixture",
                "VIDEO_ID": f"fixture-{delete_mode}-{int(export_success)}",
                "TIMESTAMP_SPAN": "00:00-00:01",
                "EXACT_QUOTE": "fixture quote",
                "QUESTION_TEXT": "fixture question",
                "CORRECT_OPT": "A",
                "EXPLANATION": "fixture explanation",
                "SOURCE_VERIFIED": "true",
            }
        )
        proc = subprocess.run(
            ["node", str(HARVEST)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        proc.db_row_count = row_count(db)  # type: ignore[attr-defined]
        return proc


def assert_case(proc: subprocess.CompletedProcess[str], *, code: int, rows: int, marker: str) -> None:
    assert proc.returncode == code, (proc.returncode, proc.stdout, proc.stderr)
    assert getattr(proc, "db_row_count") == rows, (getattr(proc, "db_row_count"), proc.stdout, proc.stderr)
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert marker in combined, combined


def main() -> None:
    confirmed = run_case(delete_mode="NORMAL", export_success=False)
    assert_case(
        confirmed,
        code=1,
        rows=0,
        marker='"reason": "PARQUET_EXPORT_FAILED_ROLLBACK_CONFIRMED"',
    )

    zero_effect = run_case(delete_mode="NOOP", export_success=False)
    assert_case(
        zero_effect,
        code=2,
        rows=1,
        marker='"reason": "PARQUET_EXPORT_FAILED_ROLLBACK_UNVERIFIED"',
    )
    assert '"post_rollback_row_count": 1' in zero_effect.stderr, zero_effect.stderr

    blocked = run_case(delete_mode="BLOCK", export_success=False)
    assert_case(
        blocked,
        code=2,
        rows=1,
        marker='"reason": "PARQUET_EXPORT_FAILED_ROLLBACK_UNVERIFIED"',
    )

    success = run_case(delete_mode="NORMAL", export_success=True)
    assert_case(success, code=0, rows=1, marker='"status": "SUCCESS"')

    print(
        json.dumps(
            {
                "status": "PASS",
                "real_path": "node scripts/harvest_community.js",
                "fixtures": [
                    "EXPORT_FAIL_DELETE_CONFIRMED_ABSENT",
                    "EXPORT_FAIL_DELETE_MATCHES_ZERO_ROWS",
                    "EXPORT_FAIL_DELETE_BLOCKED",
                    "SUCCESSFUL_EXPORT_CONTROL",
                ],
                "kill_condition": "removing post-delete COUNT readback makes NOOP-delete fixture fail",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
