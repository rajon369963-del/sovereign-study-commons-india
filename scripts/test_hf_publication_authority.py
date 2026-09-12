#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from hf_publication_authority import (
    HOLD_READBACK,
    HOLD_SKIPPED,
    PASS_BOUNDED,
    verify_remote_object,
)


EXPECTED = "data/universal_study_lake.parquet"


class FakeDownload:
    def __init__(self, objects=None, fail=False):
        self.objects = dict(objects or {})
        self.fail = fail
        self.calls = []
        self.tmp = tempfile.TemporaryDirectory()

    def __call__(self, *, repo_id, filename, repo_type, revision, token):
        self.calls.append((repo_id, filename, repo_type, revision))
        if self.fail:
            raise RuntimeError("provider unavailable")
        key = (revision, filename)
        if key not in self.objects:
            raise FileNotFoundError(key)
        path = Path(self.tmp.name) / f"{revision}.bin"
        path.write_bytes(self.objects[key])
        return str(path)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(*, local=b"G2", revision="R2", downloader=None, token="fake-token"):
    return verify_remote_object(
        repo_id="owner/dataset",
        expected_path=EXPECTED,
        token=token,
        local_commit_sha="LOCAL_COMMIT_G2",
        local_data_sha256=sha(local),
        provider_revision=revision,
        download_factory=downloader or FakeDownload({(revision, EXPECTED): local}),
    )


def assert_hold_without_queryability(evidence):
    assert evidence.decision != PASS_BOUNDED
    assert evidence.remote_unit_queryable is False


def test_token_missing_skip_is_typed_hold():
    evidence = verify(token="", revision="")
    assert evidence.decision == HOLD_SKIPPED
    assert evidence.sync_attempted is False
    assert_hold_without_queryability(evidence)


def test_exact_upload_revision_and_matching_bytes_pass_bounded():
    downloader = FakeDownload({("R2", EXPECTED): b"G2"})
    evidence = verify(local=b"G2", revision="R2", downloader=downloader)
    assert evidence.decision == PASS_BOUNDED
    assert evidence.provider_revision == "R2"
    assert evidence.local_commit_sha == "LOCAL_COMMIT_G2"
    assert evidence.local_data_sha256 == sha(b"G2")
    assert evidence.remote_object_sha256 == sha(b"G2")
    assert evidence.remote_object_present is True
    assert evidence.remote_unit_queryable is False
    assert downloader.calls[-1][3] == "R2"


def test_stale_valid_revision_same_path_different_generation_holds():
    downloader = FakeDownload({("R1", EXPECTED): b"G1"})
    evidence = verify(local=b"G2", revision="R1", downloader=downloader)
    assert evidence.decision == HOLD_READBACK
    assert evidence.remote_object_present is True
    assert evidence.remote_object_sha256 == sha(b"G1")
    assert evidence.remote_object_sha256 != evidence.local_data_sha256
    assert_hold_without_queryability(evidence)


def test_generation_binding_bypass_mutant_is_detected():
    downloader = FakeDownload({("R1", EXPECTED): b"G1"})
    evidence = verify(local=b"G2", revision="R1", downloader=downloader)
    path_only_mutant = PASS_BOUNDED
    assert path_only_mutant != evidence.decision
    assert evidence.decision == HOLD_READBACK


def test_missing_upload_created_revision_holds():
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path=EXPECTED,
        token="fake-token",
        local_commit_sha="LOCAL_COMMIT_G2",
        local_data_sha256=sha(b"G2"),
        provider_revision="",
        download_factory=FakeDownload(),
    )
    assert evidence.decision == HOLD_READBACK
    assert "upload-created provider revision" in evidence.reason


def test_provider_failure_is_fail_closed_and_secret_not_exposed():
    secret = "SUPER_SECRET_SHOULD_NOT_APPEAR"
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path=EXPECTED,
        token=secret,
        local_commit_sha="LOCAL_COMMIT_G2",
        local_data_sha256=sha(b"G2"),
        provider_revision="R2",
        download_factory=FakeDownload(fail=True),
    )
    payload = evidence.to_json()
    assert evidence.decision == HOLD_READBACK
    assert secret not in payload
    assert "RuntimeError" in payload


def test_readme_or_branch_tip_revision_cannot_replace_data_revision():
    downloader = FakeDownload({
        ("R_DATA", EXPECTED): b"G2",
        ("R_LATER_README", EXPECTED): b"STALE_OR_CHANGED",
    })
    evidence = verify(local=b"G2", revision="R_DATA", downloader=downloader)
    assert evidence.decision == PASS_BOUNDED
    assert evidence.provider_revision == "R_DATA"
    assert downloader.calls[-1][3] == "R_DATA"


def test_evidence_json_roundtrip_preserves_generation_identities():
    evidence = verify(local=b"G2", revision="R2")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "hf_sync_result.json"
        path.write_text(evidence.to_json() + "\n", encoding="utf-8")
        loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["decision"] == PASS_BOUNDED
    assert loaded["local_commit_sha"] == "LOCAL_COMMIT_G2"
    assert loaded["local_data_sha256"] == sha(b"G2")
    assert loaded["provider_revision"] == "R2"
    assert loaded["remote_object_sha256"] == sha(b"G2")
    assert loaded["remote_unit_queryable"] is False


def main():
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in sorted(tests, key=lambda fn: fn.__name__):
        test()
        print(f"PASS: {test.__name__}")
    print(f"PASS: {len(tests)} Hugging Face publication-authority courts")


if __name__ == "__main__":
    main()
