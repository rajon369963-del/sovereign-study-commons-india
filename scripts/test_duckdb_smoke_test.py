#!/usr/bin/env python3
"""Exercise the smoke harness with an isolated PATH; requires a real DuckDB CLI.

The Python-only case simulates a successful module import. The CLI prerequisite
must reject it without executing Python or touching any dataset.

The harness supervisor deliberately owns a new process session so a timeout can
terminate the whole bash -> duckdb descendant tree instead of only the parent.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "scripts" / "duckdb_smoke_test.sh"


class HarnessProcessTreeTimeout(RuntimeError):
    """Typed timeout after process-group cleanup and reap."""


class SmokePrerequisitesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="duckdb-smoke-")
        self.addCleanup(self.temp.cleanup)
        self.bin = Path(self.temp.name)
        for command in ("dirname", "stat", "sleep"):
            executable = shutil.which(command)
            self.assertIsNotNone(executable, f"Missing test prerequisite: {command}")
            (self.bin / command).symlink_to(executable)
        self.env = {**os.environ, "PATH": str(self.bin)}
        self.bash = shutil.which("bash")
        self.assertIsNotNone(self.bash, "Missing test prerequisite: bash")

    def run_harness(self, *, timeout=60, term_grace=1.0):
        process = subprocess.Popen(
            [self.bash, str(HARNESS)],
            env=self.env,
            cwd=self.bin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # The process was started in a fresh session, so its PID is also the
            # process-group ID for the bash -> duckdb descendant tree.
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=term_grace)
            except subprocess.TimeoutExpired:
                # A child/grandchild may ignore TERM or keep captured pipes open.
                # Escalate to KILL for the same process group, then reap the root.
                os.killpg(pgid, signal.SIGKILL)
                stdout, stderr = process.communicate(timeout=5)
            raise HarnessProcessTreeTimeout(
                f"DuckDB smoke harness exceeded {timeout}s; descendant group {pgid} terminated"
            ) from exc
        return subprocess.CompletedProcess(
            process.args,
            process.returncode,
            stdout=stdout,
            stderr=stderr,
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

    def test_timeout_kills_child_and_grandchild_and_drains_inherited_pipes(self):
        marker = self.bin / "grandchild-survived"
        cli = self.bin / "duckdb"
        cli.write_text(
            "#!/bin/sh\n"
            f"marker='{marker}'\n"
            "(\n"
            "  trap '' TERM\n"
            "  (\n"
            "    trap '' TERM\n"
            "    sleep 1.2\n"
            "    printf 'survived\\n' > \"$marker\"\n"
            "  ) &\n"
            "  while :; do sleep 10; done\n"
            ") &\n"
            "while :; do sleep 10; done\n"
        )
        cli.chmod(0o755)

        started = time.monotonic()
        with self.assertRaises(HarnessProcessTreeTimeout):
            self.run_harness(timeout=0.2, term_grace=0.2)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.0, "timeout cleanup must remain bounded")

        # Wait past the hostile grandchild's delayed side-effect point. If only
        # the root process died, this marker would appear after the test timeout.
        time.sleep(1.4)
        self.assertFalse(marker.exists(), "grandchild survived process-group timeout cleanup")


if __name__ == "__main__":
    unittest.main(verbosity=2)
