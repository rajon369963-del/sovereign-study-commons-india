#!/usr/bin/env python3
"""Bounded hostile court for AIR10 benchmark signer authority.

Positive control: the repository's real signed receipt verifies under the pinned root.
Negative control: a receipt that supplies a different fresh/public key must be rejected
before its self-supplied signature can confer authority.
"""

import json
import tempfile
from pathlib import Path

from verify_receipt import AUTHORITATIVE_SIGNER_PUBKEY_HEX, verify


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent

    if not verify(repo_root):
        raise AssertionError("positive control failed: current repository receipt must verify")

    hostile_key = "11" * 32
    if hostile_key == AUTHORITATIVE_SIGNER_PUBKEY_HEX:
        raise AssertionError("fixture error: hostile key unexpectedly equals pinned root")

    with tempfile.TemporaryDirectory(prefix="air10-untrusted-signer-") as td:
        hostile_root = Path(td)
        (hostile_root / "db").mkdir(parents=True)
        hostile_receipt = {
            "fixture": "self-supplied-untrusted-signer",
            "provenance": {
                "canonical_payload_sha256": "00" * 32,
                "signature_ed25519_hex": "00" * 64,
                "signer_public_key_hex": hostile_key,
                "signer_identity": "UNTRUSTED_FIXTURE",
            },
        }
        (hostile_root / "db" / "STRESS_BENCHMARK_REAL_WHEELS.json").write_text(
            json.dumps(hostile_receipt, indent=2), encoding="utf-8"
        )

        if verify(hostile_root):
            raise AssertionError(
                "FALSE_GREEN: receipt-controlled signer key was accepted as authoritative"
            )

    print("PASS: pinned signer authority rejects a receipt-controlled foreign key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
