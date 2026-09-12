#!/usr/bin/env python3
"""Bind Hugging Face publication claims to exact provider revision + byte evidence.

This helper never uploads. It verifies that the exact expected dataset object at the
exact upload-returned provider revision has the same SHA-256 as the local data object.
Even a bounded PASS does not prove logical-unit queryability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

PASS_BOUNDED = "PASS_BOUNDED_REMOTE_OBJECT_BYTE_PARITY"
HOLD_SKIPPED = "HOLD_HF_SYNC_SKIPPED"
HOLD_READBACK = "HOLD_REMOTE_READBACK_UNVERIFIED"


@dataclass(frozen=True)
class PublicationEvidence:
    decision: str
    sync_attempted: bool
    repo_id: str
    expected_path: str
    local_commit_sha: str = ""
    local_data_sha256: str = ""
    provider_revision: str = ""
    remote_object_sha256: str = ""
    remote_object_present: bool = False
    remote_unit_queryable: bool = False
    reason: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_remote_object(
    *,
    repo_id: str,
    expected_path: str,
    token: str,
    local_commit_sha: str,
    local_data_sha256: str,
    provider_revision: str,
    download_factory: Optional[Callable[..., str]] = None,
) -> PublicationEvidence:
    """Verify byte parity for one local generation at one exact HF revision."""

    common = dict(
        repo_id=repo_id,
        expected_path=expected_path,
        local_commit_sha=local_commit_sha,
        local_data_sha256=local_data_sha256,
        provider_revision=provider_revision,
    )

    if not token:
        return PublicationEvidence(
            decision=HOLD_SKIPPED,
            sync_attempted=False,
            reason="HF token unavailable; remote sync/readback not attempted",
            **common,
        )

    if not local_commit_sha or not local_data_sha256:
        return PublicationEvidence(
            decision=HOLD_READBACK,
            sync_attempted=True,
            reason="local generation identity incomplete",
            **common,
        )

    if not provider_revision:
        return PublicationEvidence(
            decision=HOLD_READBACK,
            sync_attempted=True,
            reason="exact upload-created provider revision unavailable",
            **common,
        )

    if download_factory is None:
        from huggingface_hub import hf_hub_download

        download_factory = hf_hub_download

    try:
        remote_path = download_factory(
            repo_id=repo_id,
            filename=expected_path,
            repo_type="dataset",
            revision=provider_revision,
            token=token,
        )
        remote_sha = sha256_file(remote_path)
    except Exception as exc:  # fail closed at external authority boundary
        return PublicationEvidence(
            decision=HOLD_READBACK,
            sync_attempted=True,
            reason=f"exact-revision remote readback failed: {type(exc).__name__}",
            **common,
        )

    if remote_sha != local_data_sha256:
        return PublicationEvidence(
            decision=HOLD_READBACK,
            sync_attempted=True,
            remote_object_sha256=remote_sha,
            remote_object_present=True,
            reason="remote object bytes do not match current local data generation",
            **common,
        )

    return PublicationEvidence(
        decision=PASS_BOUNDED,
        sync_attempted=True,
        remote_object_sha256=remote_sha,
        remote_object_present=True,
        remote_unit_queryable=False,
        reason="exact upload revision remote bytes match current local data SHA-256; unit queryability not proven",
        **common,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--expected-path", required=True)
    parser.add_argument("--local-commit-sha", required=True)
    parser.add_argument("--local-data-path", required=True)
    parser.add_argument("--provider-revision", default="")
    parser.add_argument("--output", default="hf_sync_result.json")
    args = parser.parse_args()

    local_sha = sha256_file(args.local_data_path)
    evidence = verify_remote_object(
        repo_id=args.repo_id,
        expected_path=args.expected_path,
        token=os.environ.get("HF_TOKEN", ""),
        local_commit_sha=args.local_commit_sha,
        local_data_sha256=local_sha,
        provider_revision=args.provider_revision,
    )
    Path(args.output).write_text(evidence.to_json() + "\n", encoding="utf-8")
    print(evidence.to_json())
    return 0 if evidence.decision == PASS_BOUNDED else 2


if __name__ == "__main__":
    raise SystemExit(main())
