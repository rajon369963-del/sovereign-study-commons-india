#!/usr/bin/env python3
"""Physical kill-mutant court for Issue #99 / PR #101.

The discriminator court is only mechanism-sensitive if bypassing the named
commit/tree/script validator makes the corresponding existing test go RED.
This meta-court loads three temporary copies of the production verifier, bypasses
exactly one target guard at a time, and requires the original discriminator test
to raise AssertionError against that mutant.

No production signer secret is used. Signed receipt bytes stay untouched.
"""

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFIER_PATH = REPO_ROOT / "scripts" / "verify_receipt.py"
DISCRIMINATOR_PATH = REPO_ROOT / "tests" / "test_receipt_validator_discriminator.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_mutant(tmp_path: Path, needle: str, replacement: str, name: str):
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    assert source.count(needle) == 1, f"Expected one target guard for {name!r}"
    mutated = source.replace(needle, replacement, 1)
    mutant_path = tmp_path / f"verify_receipt_{name}.py"
    mutant_path.write_text(mutated, encoding="utf-8")
    return _load_module(mutant_path, f"air10_{name}_mutant")


def _assert_existing_test_goes_red(mutant_verifier, target_test_name: str):
    discriminator = _load_module(DISCRIMINATOR_PATH, f"air10_discriminator_{target_test_name}")
    production_verifier = discriminator.verifier
    discriminator.verifier = mutant_verifier
    try:
        with pytest.raises(AssertionError):
            getattr(discriminator, target_test_name)()
    finally:
        discriminator.verifier = production_verifier


def test_commit_reachability_guard_bypass_kills_commit_discriminator(tmp_path):
    mutant = _load_mutant(
        tmp_path,
        "        if not fetched:\n",
        "        if False:  # KILL MUTANT: bypass commit-reachability rejection\n",
        "commit_reachability_bypass",
    )
    _assert_existing_test_goes_red(
        mutant,
        "test_fake_commit_reaches_commit_reachability_validator",
    )


def test_exact_tree_guard_bypass_kills_tree_discriminator(tmp_path):
    mutant = _load_mutant(
        tmp_path,
        "        if actual_tree != expected_tree:\n",
        "        if False:  # KILL MUTANT: bypass exact-tree rejection\n",
        "tree_equality_bypass",
    )
    _assert_existing_test_goes_red(
        mutant,
        "test_fake_tree_reaches_exact_tree_validator",
    )


def test_script_digest_guard_bypass_kills_script_discriminator(tmp_path):
    mutant = _load_mutant(
        tmp_path,
        "    if actual_script_sha != expected_script_sha:\n",
        "    if False:  # KILL MUTANT: bypass benchmark-script digest rejection\n",
        "script_digest_bypass",
    )
    _assert_existing_test_goes_red(
        mutant,
        "test_tampered_script_digest_reaches_script_digest_validator",
    )
