#!/usr/bin/env python3
from __future__ import annotations

import json
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

    print("PASS: dataset-card license claim parity court and hostile mixed-rights fixtures")


if __name__ == "__main__":
    main()
