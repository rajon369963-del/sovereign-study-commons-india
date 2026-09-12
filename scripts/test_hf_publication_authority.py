#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hf_publication_authority import (
    HOLD_READBACK,
    HOLD_SKIPPED,
    PASS_BOUNDED,
    verify_remote_object,
)


class RepoInfo:
    def __init__(self, sha: str):
        self.sha = sha


class FakeApi:
    def __init__(self, *, revision: str = "rev-good", files=None, fail=False):
        self.revision = revision
        self.files = list(files or [])
        self.fail = fail
        self.calls = []

    def repo_info(self, *, repo_id, repo_type):
        self.calls.append(("repo_info", repo_id, repo_type))
        if self.fail:
            raise RuntimeError("provider unavailable")
        return RepoInfo(self.revision)

    def list_repo_files(self, *, repo_id, repo_type, revision):
        self.calls.append(("list_repo_files", repo_id, repo_type, revision))
        if self.fail:
            raise RuntimeError("provider unavailable")
        return self.files


def factory(api):
    return lambda _token: api


def assert_hold_without_queryability(evidence):
    assert evidence.decision != PASS_BOUNDED
    assert evidence.remote_unit_queryable is False


def test_token_missing_skip_is_typed_hold():
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path="data/universal_study_lake.parquet",
        token="",
        api_factory=factory(FakeApi(files=["data/universal_study_lake.parquet"])),
    )
    assert evidence.decision == HOLD_SKIPPED
    assert evidence.sync_attempted is False
    assert_hold_without_queryability(evidence)


def test_upload_narration_without_remote_object_readback_holds():
    api = FakeApi(revision="rev-upload-returned", files=["README.md"])
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path="data/universal_study_lake.parquet",
        token="fake-token",
        api_factory=factory(api),
    )
    assert evidence.decision == HOLD_READBACK
    assert evidence.provider_revision == "rev-upload-returned"
    assert evidence.remote_object_present is False
    assert_hold_without_queryability(evidence)


def test_provider_readback_requires_exact_revision_and_object():
    api = FakeApi(
        revision="rev-exact",
        files=["README.md", "data/universal_study_lake.parquet"],
    )
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path="data/universal_study_lake.parquet",
        token="fake-token",
        api_factory=factory(api),
    )
    assert evidence.decision == PASS_BOUNDED
    assert evidence.provider_revision == "rev-exact"
    assert evidence.remote_object_present is True
    assert evidence.remote_unit_queryable is False
    assert api.calls[-1] == (
        "list_repo_files",
        "owner/dataset",
        "dataset",
        "rev-exact",
    )


def test_stale_or_missing_revision_cannot_promote_remote_success():
    api = FakeApi(revision="", files=["data/universal_study_lake.parquet"])
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path="data/universal_study_lake.parquet",
        token="fake-token",
        api_factory=factory(api),
    )
    assert evidence.decision == HOLD_READBACK
    assert_hold_without_queryability(evidence)


def test_provider_failure_is_fail_closed_and_secret_not_exposed():
    secret = "SUPER_SECRET_SHOULD_NOT_APPEAR"
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path="data/universal_study_lake.parquet",
        token=secret,
        api_factory=factory(FakeApi(fail=True)),
    )
    payload = evidence.to_json()
    assert evidence.decision == HOLD_READBACK
    assert secret not in payload
    assert "RuntimeError" in payload


def test_local_success_forces_remote_success_mutant_is_detectable():
    """Known-bad mutant: local success must not overwrite a remote HOLD."""
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path="data/universal_study_lake.parquet",
        token="",
        api_factory=factory(FakeApi()),
    )
    local_ingest_success = True
    bad_mutant_decision = PASS_BOUNDED if local_ingest_success else evidence.decision
    assert bad_mutant_decision != evidence.decision, "court must distinguish local-green/remote-HOLD mutant"
    assert evidence.decision == HOLD_SKIPPED


def test_evidence_json_roundtrip_preserves_remote_ceiling():
    evidence = verify_remote_object(
        repo_id="owner/dataset",
        expected_path="data/universal_study_lake.parquet",
        token="fake-token",
        api_factory=factory(FakeApi(revision="rev-1", files=["data/universal_study_lake.parquet"])),
    )
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "hf_sync_result.json"
        path.write_text(evidence.to_json() + "\n", encoding="utf-8")
        loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["decision"] == PASS_BOUNDED
    assert loaded["remote_object_present"] is True
    assert loaded["remote_unit_queryable"] is False


def main():
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in sorted(tests, key=lambda fn: fn.__name__):
        test()
        print(f"PASS: {test.__name__}")
    print(f"PASS: {len(tests)} Hugging Face publication-authority courts")


if __name__ == "__main__":
    main()
