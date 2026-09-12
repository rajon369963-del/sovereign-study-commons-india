#!/usr/bin/env python3
"""Bounded hostile court for AIR10 benchmark signer authority.

Positive control: the repository's real signed receipt verifies under the pinned root.
Negative control: a fully valid receipt signed by a fresh attacker-controlled Ed25519
key must still be rejected because the signer is not the pinned authority.

Kill condition: an implementation that trusts signer_public_key_hex from the receipt
and verifies with that receipt-controlled key would accept the hostile fixture.
"""

import hashlib
import json
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from verify_receipt import AUTHORITATIVE_SIGNER_PUBKEY_HEX, verify


def build_hostile_self_signed_receipt() -> dict:
    attacker_private = ed25519.Ed25519PrivateKey.generate()
    attacker_public_hex = attacker_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    if attacker_public_hex == AUTHORITATIVE_SIGNER_PUBKEY_HEX:
        raise AssertionError("fixture error: generated attacker key equals pinned root")

    receipt = {
        "fixture": "valid-self-signed-untrusted-signer",
        "metric": 999_000_000,
        "provenance": {
            "signer_public_key_hex": attacker_public_hex,
            "signer_identity": "UNTRUSTED_FIXTURE",
        },
    }

    # Match verify_receipt.py's exact canonicalization contract: the signed payload
    # contains provenance identity/key fields but not hash/signature fields.
    canonical_bytes = json.dumps(receipt, indent=2).encode("utf-8")
    receipt["provenance"]["canonical_payload_sha256"] = hashlib.sha256(
        canonical_bytes
    ).hexdigest()
    receipt["provenance"]["signature_ed25519_hex"] = attacker_private.sign(
        canonical_bytes
    ).hex()
    return receipt


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent

    # Positive discriminator: the real repository receipt must remain accepted.
    if not verify(repo_root):
        raise AssertionError("positive control failed: current repository receipt must verify")

    with tempfile.TemporaryDirectory(prefix="air10-untrusted-signer-") as td:
        hostile_root = Path(td)
        (hostile_root / "db").mkdir(parents=True)
        hostile_receipt = build_hostile_self_signed_receipt()
        (hostile_root / "db" / "STRESS_BENCHMARK_REAL_WHEELS.json").write_text(
            json.dumps(hostile_receipt, indent=2), encoding="utf-8"
        )

        if verify(hostile_root):
            raise AssertionError(
                "FALSE_GREEN: valid attacker self-signature conferred signer authority"
            )

    print("PASS: valid attacker self-signed receipt rejected by pinned signer authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
