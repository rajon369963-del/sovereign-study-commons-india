#!/usr/bin/env python3
"""Mechanism-sensitive receipt verifier court for Issue #99.

The existing adversarial canary only checks a non-zero verifier exit after mutating
signed receipt fields. That can false-green at an earlier payload/signature gate.
This court keeps the original signed bytes authoritative for payload/signature
verification, injects a hostile telemetry view only after the first parse, and
requires the exact intended validator's rejection marker.

Kill condition: removing/bypassing the targeted commit/tree/script validator must
make its fixture fail this test because the expected stage marker disappears,
even if a different later validator also rejects.
"""

import copy
import contextlib
import io
import subprocess
from pathlib import Path

import scripts.verify_receipt as verifier


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_with_post_auth_view(mutator):
    """Run production verify() with valid signed bytes but mutated post-auth data view."""
    real_loads = verifier.json.loads
    real_check_call = verifier.subprocess.check_call
    real_default_bench = verifier.DEFAULT_BENCH_FILE
    calls = {"loads": 0}

    def staged_loads(payload, *args, **kwargs):
        calls["loads"] += 1
        parsed = real_loads(payload, *args, **kwargs)
        if calls["loads"] == 1:
            hostile = copy.deepcopy(parsed)
            mutator(hostile)
            return hostile
        return parsed

    def bounded_check_call(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and len(cmd) > 1 and cmd[0] == "git" and cmd[1] == "fetch":
            raise subprocess.CalledProcessError(1, cmd)
        return real_check_call(cmd, *args, **kwargs)

    verifier.json.loads = staged_loads
    verifier.subprocess.check_call = bounded_check_call
    verifier.DEFAULT_BENCH_FILE = "__air10_no_live_benchmark_for_discriminator__"
    try:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            ok = verifier.verify(REPO_ROOT)
        return ok, stream.getvalue()
    finally:
        verifier.json.loads = real_loads
        verifier.subprocess.check_call = real_check_call
        verifier.DEFAULT_BENCH_FILE = real_default_bench


def test_positive_control_authorized_receipt_still_passes_static_court():
    real_default_bench = verifier.DEFAULT_BENCH_FILE
    verifier.DEFAULT_BENCH_FILE = "__air10_no_live_benchmark_for_discriminator__"
    try:
        assert verifier.verify(REPO_ROOT) is True
    finally:
        verifier.DEFAULT_BENCH_FILE = real_default_bench


def test_fake_commit_reaches_commit_reachability_validator():
    def mutate(data):
        data["hardware_telemetry"]["benchmarked_source_commit_sha"] = "0" * 40

    ok, output = _run_with_post_auth_view(mutate)
    assert ok is False
    assert "Canonical payload hash mismatch" not in output
    assert "Cryptographic signature verification failed" not in output
    assert "is NOT reachable in git history" in output


def test_fake_tree_reaches_exact_tree_validator():
    def mutate(data):
        data["hardware_telemetry"]["benchmarked_source_tree_sha"] = "f" * 40

    ok, output = _run_with_post_auth_view(mutate)
    assert ok is False
    assert "Canonical payload hash mismatch" not in output
    assert "Cryptographic signature verification failed" not in output
    assert "Commit tree mismatch against signed receipt" in output


def test_tampered_script_digest_reaches_script_digest_validator():
    def mutate(data):
        data["hardware_telemetry"]["benchmark_script_sha256"] = "1" * 64

    ok, output = _run_with_post_auth_view(mutate)
    assert ok is False
    assert "Canonical payload hash mismatch" not in output
    assert "Cryptographic signature verification failed" not in output
    assert "Benchmark script SHA-256 mismatch against signed receipt" in output
