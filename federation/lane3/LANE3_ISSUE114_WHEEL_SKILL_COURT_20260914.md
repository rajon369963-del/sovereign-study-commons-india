# Lane 3 Wheel + Shared-Skill Court — Study #114

Date: 2026-09-14
Base: `ebedcee5c99dfa88078b13d890d7f8c006f9e857`
Issue: #114

## Evidence-bound gap
Current `scripts/test_dataset_manifest_sensitivity.py` contains the six required negative cases in a mutable local `mutants` list and iterates only that list. Therefore the current source has a candidate acceptance-inventory authority seam: removing one required mutant from that same list can shrink semantic coverage while the remaining cases still execute. This is source-level evidence only until the hosted physical removal mutant is run.

## Champion composition
`CHAKKA JODO, CHAKKA MAT BANAO`: reuse the existing Study sensitivity court, `hashlib.sha256`, JSON/text contract primitives, existing required `Data integrity` workflow, and the already-proven sibling frozen-authority mechanism from CIVEX. No new service, daemon, mutation framework, or bulk install.

Smallest adapter after Lane4 proves the old hosted false-green: a separate versioned frozen contract containing the exact six required mutant IDs and an expected inventory digest. The runtime court computes its observed inventory and fails closed on mismatch before executing cases. Contract migration must be explicit/versioned rather than silently co-edited with the implementation.

## Oracles
Positive: exact six-mutant current inventory + existing no-op verifier ablation stays GREEN and every real known-bad fixture is rejected by the production verifier.

Targeted negative: remove only `WRONG_ROWCOUNT_MANIFEST` (or one other required ID) while the frozen authority remains unchanged. Old/current path is the required pre-repair probe; after repair this mutant MUST RED specifically at inventory-authority validation. A coordinated implementation-only rename/removal without an explicit contract migration must also RED/HOLD.

Rollback: revert the bounded contract/test adapter; production manifest verifier behavior remains unchanged unless independently justified.

Claim ceiling: `BOUNDED_MANIFEST_SENSITIVITY_ACCEPTANCE_INVENTORY_AUTHORITY_ONLY`.

## Wheel decisions
- Existing pytest/Python/SQLite/DuckDB and current sensitivity court: ADOPT/REUSE.
- Native SHA-256 + JSON/text frozen contract: ADOPT.
- `mutmut`: REJECT for #114. One named physical removal mutant is cheaper and more causal than broad automated mutation search.
- Hypothesis: REJECT/HOLD for #114. The gap is a deterministic finite acceptance inventory, not generative input discovery.
- actionlint/zizmor: HOLD as separate workflow-supply-chain probes; not a fix for #114.
- Syft + one of Grype/OSV, gitleaks, attest/cosign/SLSA/in-toto, Renovate, pre-commit, hyperfine: no adoption delta for #114; orthogonal or duplicate capability.

## Shared Skill Registry candidate
`SKILL_ID=FROZEN-ACCEPTANCE-INVENTORY-AUTHORITY-V1`

- SOURCE_REPO+SHA: `civex-progressive-bridge` PR47/PR49 proof lineage, adapted to Study `ebedcee5c99dfa88078b13d890d7f8c006f9e857`
- PROBLEM_CLASS: a co-editable/self-declared acceptance inventory can shrink while the court remains green for surviving cases
- MECHANISM: independent versioned frozen inventory + digest, runtime observed-inventory comparison, one-at-a-time removal mutant
- INVARIANT: `GREEN_COURT + SELF_DECLARED_ACCEPTANCE_LIST != PROOF_REQUIRED_ACCEPTANCE_SET_WAS_EXERCISED`
- PREREQUISITES: finite named required inventory, stable canonical ordering/normalization, existing deterministic court
- FAILURE_BOUNDARY: acceptance-inventory authority only; does not prove dataset provenance/license/semantic correctness
- TARGET_REPO: Study
- TRANSFER_VERDICT: ADAPT_CANDIDATE
- MINIMAL_ADAPTER: separate reviewed contract + SHA-256 comparison in existing sensitivity court
- POSITIVE_ORACLE: exact frozen six-ID inventory passes and all six known-bad cases remain causally rejected
- TARGETED_NEGATIVE_OR_ABLATION_ORACLE: one required ID removed/renamed without contract migration
- MUTANT_KILL_CONDITION: inventory authority gate turns RED/HOLD before a reduced set can claim PASS
- ROLLBACK: revert contract/test adapter
- CLAIM_CEILING: `BOUNDED_ACCEPTANCE_INVENTORY_AUTHORITY_ONLY`
- FRESHNESS_TRIGGER: mutant set, test file, production verifier, required workflow, contract version
- VERIFIER_RECEIPT: Study #114 exact current source readback + CIVEX PR47/PR49 source evidence from issue contract
- STATUS: NOT SHAREABLE from this transfer alone. Parent mechanism has sibling evidence, but Study still requires target-specific hosted positive+negative proof.

## Negative knowledge
Do not install `mutmut` merely because this is mutation-sensitive testing. Do not let the implementation list and frozen authority be the same co-editable object. Do not treat a digest stored beside a simultaneously mutable list as independent authority without an explicit reviewed/versioned contract boundary. Do not inherit CIVEX PASS onto Study. Do not change the six-case contract silently to make a removal mutant green.

## Lane4 route
Fresh-read Study main and #114; acquire isolated ownership; run the exact hosted one-ID removal mutant first. Only if it stays green, implement the smallest frozen authority in the existing court/workflow. Require removal mutant RED, restore GREEN, all six real mutants still rejected, existing required contexts GREEN.

## Lane5 route
Independent exact-object recourt: verify frozen contract bytes/digest, known-good exact six-ID PASS, one-at-a-time removal/rename RED/HOLD, restore and rerun all six production-verifier negatives plus no-op ablation. Reject any unrelated earlier failure as a mutant kill.

HUMAN_GATE=NONE
RAJON_ACTION=NONE
MERGE_AUTHORIZED=NO
RELEASE_AUTHORIZED=NO
REAL_MONEY_EFFECTS=FORBIDDEN
