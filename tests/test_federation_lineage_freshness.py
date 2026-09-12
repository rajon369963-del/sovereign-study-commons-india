#!/usr/bin/env python3
"""Hostile real-git court for Study Issue #103.

Lineage currentness is directional. Given A -> B -> C -> D and canonical C:
- C is exact PASS;
- D is a forward descendant PASS;
- B/A are stale ancestors and MUST NOT PASS;
- an unrelated commit must FAIL_UNRELATED.

The old symmetric ancestry mutant deliberately accepts stale B/A, so the court
also proves why reverse-ancestry acceptance is unsafe.
"""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_federation_manifest.py"

spec = importlib.util.spec_from_file_location("air10_federation_verifier", VERIFIER)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
classify_branch_lineage = module.classify_branch_lineage


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def commit(repo: Path, value: str) -> str:
    (repo / "state.txt").write_text(value, encoding="utf-8")
    subprocess.check_call(["git", "add", "state.txt"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", f"state-{value}"], cwd=repo, stdout=subprocess.DEVNULL)
    return git(repo, "rev-parse", "HEAD")


def build_dag(repo: Path):
    subprocess.check_call(["git", "init", "-q"], cwd=repo)
    git(repo, "config", "user.email", "air10-court@example.invalid")
    git(repo, "config", "user.name", "AIR10 Court")
    a = commit(repo, "A")
    b = commit(repo, "B")
    c = commit(repo, "C")
    d = commit(repo, "D")
    subprocess.check_call(["git", "checkout", "--orphan", "unrelated"], cwd=repo, stdout=subprocess.DEVNULL)
    for path in repo.iterdir():
        if path.name != ".git" and path.is_file():
            path.unlink()
    unrelated = commit(repo, "U")
    return a, b, c, d, unrelated


def old_symmetric_mutant_accepts(repo: Path, expected: str, actual: str) -> bool:
    if actual == expected:
        return True
    expected_to_actual = subprocess.run(["git", "merge-base", "--is-ancestor", expected, actual], cwd=repo).returncode == 0
    actual_to_expected = subprocess.run(["git", "merge-base", "--is-ancestor", actual, expected], cwd=repo).returncode == 0
    return expected_to_actual or actual_to_expected


class FederationLineageFreshnessCourt(unittest.TestCase):
    def test_directional_lineage_and_reverse_ancestry_mutant(self):
        with tempfile.TemporaryDirectory(prefix="air10-study-lineage-") as tmp:
            repo = Path(tmp)
            a, b, c, d, unrelated = build_dag(repo)
            self.assertEqual(classify_branch_lineage(repo, c, c), "PASS_EXACT")
            self.assertEqual(classify_branch_lineage(repo, c, d), "PASS_DESCENDANT")
            self.assertEqual(classify_branch_lineage(repo, c, b), "STALE_ANCESTOR")
            self.assertEqual(classify_branch_lineage(repo, c, a), "STALE_ANCESTOR")
            self.assertEqual(classify_branch_lineage(repo, c, unrelated), "FAIL_UNRELATED")
            self.assertTrue(old_symmetric_mutant_accepts(repo, c, b))
            self.assertTrue(old_symmetric_mutant_accepts(repo, c, a))


if __name__ == "__main__":
    unittest.main(verbosity=2)
