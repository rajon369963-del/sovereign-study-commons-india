#!/usr/bin/env python3
"""Bound Hugging Face publication claims to provider-side readback evidence.

This helper does not upload anything. It verifies that an expected object is visible
at a concrete provider revision and emits a bounded JSON evidence envelope. A
successful local ingest or upload API return is never promoted to remote unit
queryability by this module.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional


PASS_BOUNDED = "PASS_BOUNDED_REMOTE_OBJECT_READBACK"
HOLD_SKIPPED = "HOLD_HF_SYNC_SKIPPED"
HOLD_READBACK = "HOLD_REMOTE_READBACK_UNVERIFIED"


@dataclass(frozen=True)
class PublicationEvidence:
    decision: str
    sync_attempted: bool
    repo_id: str
    expected_path: str
    provider_revision: str = ""
    remote_object_present: bool = False
    remote_unit_queryable: bool = False
    reason: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def verify_remote_object(
    *,
    repo_id: str,
    expected_path: str,
    token: str,
    api_factory: Optional[Callable[[str], Any]] = None,
) -> PublicationEvidence:
    """Verify provider-side revision + expected object presence.

    The evidence ceiling is intentionally narrow: even PASS_BOUNDED only proves
    provider readback of the expected object path at a concrete repository
    revision. It does not prove that a newly ingested logical unit is queryable
    inside that object.
    """
    if not token:
        return PublicationEvidence(
            decision=HOLD_SKIPPED,
            sync_attempted=False,
            repo_id=repo_id,
            expected_path=expected_path,
            reason="HF token unavailable; remote sync/readback not attempted",
        )

    if api_factory is None:
        from huggingface_hub import HfApi  # imported only on authorized path

        api_factory = lambda supplied_token: HfApi(token=supplied_token)

    try:
        api = api_factory(token)
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
        revision = str(getattr(info, "sha", "") or "")
        if not revision:
            return PublicationEvidence(
                decision=HOLD_READBACK,
                sync_attempted=True,
                repo_id=repo_id,
                expected_path=expected_path,
                reason="provider repo_info returned no revision identity",
            )
        files = api.list_repo_files(
            repo_id=repo_id,
            repo_type="dataset",
            revision=revision,
        )
        present = expected_path in set(files or [])
        if not present:
            return PublicationEvidence(
                decision=HOLD_READBACK,
                sync_attempted=True,
                repo_id=repo_id,
                expected_path=expected_path,
                provider_revision=revision,
                reason="expected remote object absent at provider revision",
            )
        return PublicationEvidence(
            decision=PASS_BOUNDED,
            sync_attempted=True,
            repo_id=repo_id,
            expected_path=expected_path,
            provider_revision=revision,
            remote_object_present=True,
            remote_unit_queryable=False,
            reason="provider revision and expected object path read back; unit-level queryability not proven",
        )
    except Exception as exc:  # fail closed at external authority boundary
        return PublicationEvidence(
            decision=HOLD_READBACK,
            sync_attempted=True,
            repo_id=repo_id,
            expected_path=expected_path,
            reason=f"provider readback failed: {type(exc).__name__}",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--expected-path", required=True)
    parser.add_argument("--output", default="hf_sync_result.json")
    args = parser.parse_args()

    evidence = verify_remote_object(
        repo_id=args.repo_id,
        expected_path=args.expected_path,
        token=os.environ.get("HF_TOKEN", ""),
    )
    Path(args.output).write_text(evidence.to_json() + "\n", encoding="utf-8")
    print(evidence.to_json())
    return 0 if evidence.decision == PASS_BOUNDED else 2


if __name__ == "__main__":
    raise SystemExit(main())
