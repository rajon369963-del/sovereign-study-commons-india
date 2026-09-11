#!/usr/bin/env python3
"""Bound dataset-card license claims by committed per-asset rights evidence.

This is a claim-parity court, not legal advice and not a rights adjudicator.
It only prevents a categorical whole-dataset permissive claim from exceeding
what the committed manifest currently says about bundled assets.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

UNKNOWN_MARKERS = ("UNKNOWN", "REVIEW_REQUIRED", "UNVERIFIED")
CATEGORICAL_LICENSES = {"mit", "apache-2.0", "cc-by-4.0", "cc0-1.0", "bsd-3-clause"}
WHOLE_DATASET_PERMISSIVE_PATTERNS = (
    re.compile(r"\bthis\s+dataset\s+is\s+distributed\s+under\s+the\s+\*\*?mit\s+license", re.I),
    re.compile(r"\bentire\s+dataset\b.{0,80}\bmit\b", re.I | re.S),
    re.compile(r"\ball\s+dataset\s+(?:content|assets|files)\b.{0,80}\bmit\b", re.I | re.S),
)


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return "" if end < 0 else text[4:end]


def card_license_id(text: str) -> str | None:
    fm = _frontmatter(text)
    m = re.search(r"(?m)^license:\s*([^#\n]+?)\s*$", fm)
    if not m:
        return None
    return m.group(1).strip().strip("'\"").lower()


def unresolved_assets(manifest: dict) -> list[dict]:
    out = []
    for asset in manifest.get("assets", []):
        license_status = str(asset.get("license_status", "")).upper()
        verification_status = str(asset.get("verification_status", "")).upper()
        if any(marker in license_status for marker in UNKNOWN_MARKERS) or any(
            marker in verification_status for marker in UNKNOWN_MARKERS
        ):
            out.append(
                {
                    "path": asset.get("path"),
                    "license_status": asset.get("license_status"),
                    "verification_status": asset.get("verification_status"),
                }
            )
    return out


def categorical_body_claim(text: str) -> bool:
    return any(p.search(text) for p in WHOLE_DATASET_PERMISSIVE_PATTERNS)


def evaluate(card_text: str, manifest: dict) -> dict:
    unresolved = unresolved_assets(manifest)
    license_id = card_license_id(card_text)
    body_is_categorical = categorical_body_claim(card_text)
    yaml_is_categorical = license_id in CATEGORICAL_LICENSES

    reasons: list[str] = []
    if unresolved and yaml_is_categorical:
        reasons.append(
            f"dataset-card YAML license={license_id!r} exceeds unresolved per-asset rights evidence"
        )
    if unresolved and body_is_categorical:
        reasons.append("dataset-card prose makes a categorical whole-dataset permissive license claim")

    decision = "HOLD" if reasons else "PASS_BOUNDED"
    return {
        "decision": decision,
        "card_license_id": license_id,
        "unresolved_assets": unresolved,
        "categorical_body_claim": body_is_categorical,
        "reasons": reasons,
        "claim_ceiling": (
            "claim-parity only; no ownership, infringement, redistribution permission, or legal-compliance conclusion"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", default="DATASET_CARD.md")
    parser.add_argument("--manifest", default="data_lake/dataset_manifest.json")
    args = parser.parse_args()

    card = Path(args.card).read_text(encoding="utf-8")
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    result = evaluate(card, manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "PASS_BOUNDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
