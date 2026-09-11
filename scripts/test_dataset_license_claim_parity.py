#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from verify_dataset_license_claims import evaluate


def assert_hold(card: str, manifest: dict, label: str) -> None:
    result = evaluate(card, manifest)
    assert result["decision"] == "HOLD", (label, result)


def assert_pass(card: str, manifest: dict, label: str) -> None:
    result = evaluate(card, manifest)
    assert result["decision"] == "PASS_BOUNDED", (label, result)


def main() -> None:
    mixed = {
        "assets": [
            {
                "path": "asset_a.parquet",
                "license_status": "MIT/VERIFIED",
                "verification_status": "VERIFIED_LOCAL_CANARY",
            },
            {
                "path": "asset_b.parquet",
                "license_status": "UNKNOWN/REVIEW_REQUIRED",
                "verification_status": "UNVERIFIED_COMMUNITY_ASSET",
            },
        ]
    }
    all_verified = {
        "assets": [
            {
                "path": "owned_a.parquet",
                "license_status": "MIT/VERIFIED",
                "verification_status": "VERIFIED_LOCAL_CANARY",
            },
            {
                "path": "owned_b.parquet",
                "license_status": "MIT/VERIFIED",
                "verification_status": "VERIFIED_LOCAL_CANARY",
            },
        ]
    }

    bad_yaml_and_body = """---\nlicense: mit\n---\n# Card\nThis dataset is distributed under the **MIT License**.\n"""
    bad_yaml_only = """---\nlicense: mit\n---\n# Card\nRights are tracked per asset in the committed manifest.\n"""
    bad_body_only = """---\nlicense: other\n---\n# Card\nThis dataset is distributed under the **MIT License**.\n"""
    bounded = """---\nlicense: other\n---\n# Card\nRepository code/docs licensing does not resolve bundled asset rights. Per-asset rights are tracked in the committed manifest; unresolved assets remain UNKNOWN/REVIEW_REQUIRED.\n"""

    assert_hold(bad_yaml_and_body, mixed, "mixed-rights categorical YAML+body mutant")
    assert_hold(bad_yaml_only, mixed, "mixed-rights categorical YAML mutant")
    assert_hold(bad_body_only, mixed, "mixed-rights categorical body mutant")
    assert_pass(bounded, mixed, "mixed-rights bounded card")
    assert_pass(bad_yaml_and_body, all_verified, "all-verified synthetic positive control")

    # Real repository object: exact card + exact manifest must be bounded after the repair.
    root = Path(__file__).resolve().parents[1]
    real_card = (root / "DATASET_CARD.md").read_text(encoding="utf-8")
    real_manifest = json.loads((root / "data_lake/dataset_manifest.json").read_text(encoding="utf-8"))
    assert_pass(real_card, real_manifest, "committed dataset-card/manifest parity")

    # A parser/build-only green is deliberately insufficient: materialize the known-bad
    # pair and prove the court rejects it despite both files being syntactically valid.
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "DATASET_CARD.md").write_text(bad_yaml_and_body, encoding="utf-8")
        (p / "manifest.json").write_text(json.dumps(mixed), encoding="utf-8")
        parsed_card = (p / "DATASET_CARD.md").read_text(encoding="utf-8")
        parsed_manifest = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
        assert parsed_card.startswith("---\n")
        assert len(parsed_manifest["assets"]) == 2
        assert_hold(parsed_card, parsed_manifest, "syntax-green mixed-rights mutant")

    # Exact CLI/output path hostile court: 10k unresolved assets must still drive the
    # full HOLD decision while stdout stays bounded and commits to all evidence via
    # total+digest+exact manifest digest/reference. The sample is diagnostic only.
    huge_manifest = {
        "assets": [
            {
                "path": f"community_{i:05d}.parquet",
                "license_status": "UNKNOWN/REVIEW_REQUIRED",
                "verification_status": "UNVERIFIED_COMMUNITY_ASSET",
            }
            for i in range(10_000)
        ]
    }
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        card_path = p / "DATASET_CARD.md"
        manifest_path = p / "manifest.json"
        card_path.write_text(bad_yaml_and_body, encoding="utf-8")
        manifest_text = json.dumps(huge_manifest, sort_keys=True)
        manifest_path.write_text(manifest_text, encoding="utf-8")
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent / "verify_dataset_license_claims.py"),
            "--card",
            str(card_path),
            "--manifest",
            str(manifest_path),
            "--evidence-sample-limit",
            "20",
        ]
        run = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert run.returncode == 2, run.stderr or run.stdout
        assert len(run.stdout.encode("utf-8")) < 20_000, len(run.stdout.encode("utf-8"))
        payload = json.loads(run.stdout)
        evidence = payload["unresolved_assets"]
        assert payload["decision"] == "HOLD"
        assert evidence["total"] == 10_000
        assert len(evidence["sample"]) == 20
        assert evidence["sample_truncated"] is True
        assert evidence["full_evidence_reference"]["manifest_path"] == str(manifest_path)
        assert evidence["full_evidence_reference"]["manifest_sha256"] == hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()

        first_digest = evidence["sha256"]
        # Change only the last, unsampled asset. A silent sample-only implementation
        # would miss this; a full-evidence digest must change while the sample stays same.
        huge_manifest["assets"][-1]["path"] = "community_LAST_MUTATED.parquet"
        manifest_path.write_text(json.dumps(huge_manifest, sort_keys=True), encoding="utf-8")
        rerun = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert rerun.returncode == 2, rerun.stderr or rerun.stdout
        payload2 = json.loads(rerun.stdout)
        evidence2 = payload2["unresolved_assets"]
        assert evidence2["sample"] == evidence["sample"]
        assert evidence2["sha256"] != first_digest

    print("PASS: dataset-card license claim parity court, hostile mixed-rights fixtures, and bounded 10k evidence envelope")


if __name__ == "__main__":
    main()
