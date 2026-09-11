#!/usr/bin/env python3
"""Exercise the smoke harness with an isolated PATH; requires a real DuckDB CLI.

The Python-only case simulates a successful module import. The CLI prerequisite
must reject it without executing Python or touching any dataset.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "scripts" / "duckdb_smoke_test.sh"


class SmokePrerequisitesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="duckdb-smoke-")
        self.addCleanup(self.temp.cleanup)
        self.bin = Path(self.temp.name)
        for command in ("dirname", "stat"):
            executable = shutil.which(command)
            self.assertIsNotNone(executable, f"Missing test prerequisite: {command}")
            (self.bin / command).symlink_to(executable)
        self.env = {**os.environ, "PATH": str(self.bin)}
        # Noninteractive Bash otherwise sources host code that can replace PATH
        # and silently bypass the missing/failing executable fixtures.
        self.env.pop("BASH_ENV", None)
        self.env.pop("ENV", None)
        self.bash = shutil.which("bash")
        self.assertIsNotNone(self.bash, "Missing test prerequisite: bash")

    def run_harness(self):
        return subprocess.run(
            [self.bash, str(HARNESS)], env=self.env, cwd=self.bin,
            capture_output=True, text=True, timeout=60,
        )

    def assert_missing_cli(self):
        result = self.run_harness()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("DuckDB CLI is required", result.stderr)
        self.assertIn("Install the DuckDB CLI", result.stderr)
        self.assertNotIn("Verified file existence", result.stdout)
        self.assertNotIn("[+] Using", result.stdout)
        self.assertNotIn("PASS:", result.stdout)

    def test_cli_only_runs_real_parquet_queries(self):
        executable = shutil.which("duckdb")
        self.assertIsNotNone(executable, "Install DuckDB CLI before running this suite")
        (self.bin / "duckdb").symlink_to(executable)
        result = self.run_harness()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[✓] PASS:", result.stdout)
        for asset in ("universal_study_lake", "gate_ee_5k_questions", "upsc_polity_5k_videos"):
            self.assertIn(asset, result.stdout)
        self.assertIn("=== 4. Bounded Query 3:", result.stdout)

    def test_python_module_only_fails_before_probing_python(self):
        marker = self.bin / "python-was-invoked"
        python = self.bin / "python3"
        python.write_text('#!/bin/sh\n: > "$(dirname "$0")/python-was-invoked"\nexit 0\n')
        python.chmod(0o755)
        self.assert_missing_cli()
        self.assertFalse(marker.exists(), "CLI-only harness must not probe Python")

    def test_neither_engine_fails_before_dataset_work(self):
        self.assert_missing_cli()

    def test_cli_query_error_is_not_reported_as_success(self):
        cli = self.bin / "duckdb"
        cli.write_text("#!/bin/sh\necho 'synthetic query failure' >&2\nexit 42\n")
        cli.chmod(0o755)
        result = self.run_harness()
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertIn("synthetic query failure", result.stderr)
        self.assertNotIn("PASS:", result.stdout)
        self.assertNotIn("=== 2. Bounded Query 1:", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
