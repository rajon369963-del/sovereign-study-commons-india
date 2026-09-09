# Sovereign Study Commons India — Public Roadmap

_Last verified: 9 Sep 2026 against `main` at `c7189e5054f919d81cbb535457df7c940f7cc217`._

This roadmap is truth-ranked. Current repository facts are separated from staged, unverified, and blocked work.

## Verified now

- The public repository exists on `main` and currently contains public UI files, SQLite and Parquet data assets, scripts, dataset documentation, contributor/governance files, issue templates, and two GitHub Actions workflows in `.github/workflows/`.
- `main` is protected and currently requires the contexts `Data integrity` and `SHA256 idempotency canary` for non-admin merges. This is bounded governance evidence, not proof of an admin-proof/no-bypass policy.
- PR #33 merged through the normal protected path. On its exact head, both required workflows completed successfully. Current workflow definitions now emit both required contexts on every pull request; path filters remain only for pushes to `main`.
- The `Data integrity` workflow performs bounded SQLite/Parquet integrity checks, explicit FTS membership checks, key/provenance uniqueness checks where supported, and the canonicalization adversarial suite.
- The `SHA256 idempotency canary` exercises the isolated full-hash write-boundary canary. This does not prove persistent semantic-identity migration in the committed database.
- Existing repaired SQLite evidence establishes a bounded source↔FTS membership state and transactional trigger synchronization on the tested artifact. It does not reconstruct historical causality by itself.
- The Spark daemon truth repair is merged: unsupported physical-verification claims were downgraded and daemon-side ambient Git commits were removed from that component.
- Issue #10 is a public opt-in pilot surface, but there are still zero verified non-founder same-human value events. Public availability alone is not learner-value or G3 evidence.

## Staged or independently unverified

- Structured issue intake and support-routing changes remain staged until refreshed from current `main`, required checks pass on the refreshed exact head, and default-branch rendering is independently read back.
- GitHub Pages availability or successful deployment workflow is not equivalent to independently verified learner-facing browser correctness.
- Hugging Face activation and GitHub↔Hugging Face↔Drive exact snapshot parity remain unverified.
- Persistent semantic-identity migration, DB `UNIQUE`/upsert promotion, provenance referential integrity, real transcript/source ingestion, and crash-safe Parquet replacement remain HOLD until their independent courts pass.
- Numerical learner gains remain UNVALIDATED. Fixed category retest intervals are `FIXED_DIAGNOSTIC_RETEST_CANARY`, not FSRS, and no neural-consolidation claim is made.

## P0 — Truth, safety, and reproducibility

1. Keep README, ROADMAP, UI, issue forms, and support docs synchronized with live repository state; historical claims must be clearly historical.
2. Preserve unconditional pull-request required-check emission and do not weaken branch protection to regain green status.
3. Preserve fail-closed SQLite/Parquet integrity, FTS membership, canonicalization, full-hash idempotency, privacy, rollback, and adversarial tests.
4. Replace direct canonical Parquet writes with temp → validate → atomic rename before calling export crash-safe.
5. Bind provenance/license status for externally sourced or derived assets before redistribution or parity promotion.
6. Keep semantic identity, persistent DB migration, and ingestion claims on HOLD until independent adversarial proof exists.

## P1 — Contributor usefulness

1. Refresh the native structured defect Issue Form, `SUPPORT.md`, and chooser config onto current protected `main` without adding bots, CRM, or third-party triage automation.
2. Keep a small set of honest `good first issue` / `help wanted` tasks tied to real user or maintainer value.
3. Require reproduction, expected/observed behavior, tests/screenshots/logs/rationale as applicable while minimizing private or copyrighted content.
4. Track external contributors, repeat contributors, real downstream users, and owner-created activity separately.
5. Do not use bought stars, fake engagement, spam, or mass unsolicited outreach.

## P2 — Reproducible public data

1. Maintain machine-readable asset metadata with byte size, row count, schema/version, SHA-256, provenance class, and license/status.
2. Add deterministic drift checks across SQLite/Parquet and any future GitHub↔HF↔Drive copies before claiming parity.
3. Keep sample queries/tests bound to committed assets.
4. Keep unknown provenance or redistribution status explicitly `UNKNOWN/REVIEW_REQUIRED`.

## P3 — Real ingestion and distribution, only after proof

1. Do not call synthetic/default-generating harvest logic real source extraction until transcript/source/license evidence is physically retrieved and bound.
2. Require fail-closed C17 execution proof on a supported Linux/x86 environment before promoting that path.
3. Require independently read-back GitHub and Hugging Face artifacts with matching hashes before calling dual-hub sync live.
4. Preserve manual/offline-safe verification and rollback paths.
5. Promote learner value only from real same-human pain → action → useful-result → measurement events.

## Success measures

- Current docs contain zero deployment, automation, provenance, parity, or learner-value claims that exceed physical evidence.
- Required checks appear on fresh pull requests and normal protected merges are blocked when a required context is red.
- Data assets have deterministic integrity/hash/provenance evidence and crash-safe export semantics.
- Contributor issues/forms reduce ambiguity without collecting unnecessary sensitive data.
- Real-user and external-contributor metrics are reported separately from owner-created activity.

## Historical note

Earlier September 2026 roadmap states referenced PR #5 as open/unmerged, `.github/workflows/` as absent from `main`, and a zero-job dependency hash-lock frontier. Those were valid snapshots of an earlier phase but are superseded by the current verified state above.
