# Sovereign Study Commons India — Public Roadmap

_Last verified: 9 Sep 2026 against `main` at `127b24038b991e8b424b801bb1e25feab9dd4149`._

This roadmap is truth-ranked. Current repository facts are separated from staged, unverified, and blocked work.

## Verified now

- The public repository exists on `main` and currently contains root/public UI files, SQLite and Parquet data assets, scripts, dataset documentation, contributor/governance files, issue templates, and two GitHub Actions workflows in `.github/workflows/`.
- `main` is protected and currently requires the contexts `Data integrity` and `SHA256 idempotency canary` for non-admin merges. This is not proof of an admin-proof/no-bypass ruleset.
- The data-integrity workflow performs bounded SQLite/Parquet integrity checks, explicit FTS membership checks, provenance/key uniqueness checks where supported, and the canonicalization adversarial suite.
- The SHA256 idempotency workflow exercises the isolated full-hash write-boundary canary. These checks are repository-integrity evidence only; they are not learner-efficacy, provenance/license, deployment, or downstream-parity proof.
- Earlier repaired SQLite evidence established a bounded 11-row source↔FTS membership state with no missing/extra rowids and transactional trigger synchronization on the repaired artifact. That does not reconstruct the historical causal sequence by itself.
- Identity/canonicalization protections have advanced beyond the old PR #5 frontier; old PR/head/run descriptions belong to history, not current-state claims.
- Issue #10 is a public opt-in pilot surface, but there are currently zero verified non-founder same-human value events. Public availability alone is not G3 evidence.

## Staged or independently unverified

- PR #33 removes only the two `pull_request.paths` filters from the branch-required workflows so required contexts cannot be skipped on docs/governance PRs. Its trigger-only diff has independent bounded review, but final merge authority requires a fresh integration-candidate run bound to current `main` and normal protected merge without bypass.
- PR #37 stages structured issue intake and support-routing improvements. Real triage benefit remains unvalidated until real issue traffic exists.
- GitHub Pages public-body readback is not promoted here without a fresh independent HTTP/readback proof.
- Hugging Face activation and GitHub↔Hugging Face↔Drive exact snapshot parity remain unverified.
- Persistent semantic-identity migration, DB `UNIQUE`/upsert promotion, and provenance referential integrity remain HOLD until their independent courts pass.
- Numerical learner gains remain UNVALIDATED. Fixed category retest intervals are `FIXED_DIAGNOSTIC_RETEST_CANARY`, not FSRS, and no neural-consolidation claim is made.

## P0 — Truth, safety, and reproducibility

1. Complete PR #33 only through normal protected merge after exact-head/current-base required contexts are physically green. Do not use admin bypass as evidence.
2. Keep README, ROADMAP, UI, issue forms, and support docs synchronized with live repository state; historical claims must be clearly historical.
3. Preserve fail-closed SQLite/Parquet integrity, FTS membership, canonicalization, full-hash idempotency, privacy, rollback, and adversarial tests.
4. Replace direct canonical Parquet writes with temp → validate → atomic rename before calling export crash-safe.
5. Bind provenance/license status for externally sourced or derived assets before redistribution/parity promotion.
6. Keep semantic identity, persistent DB migration, and ingestion claims on HOLD until independent adversarial proof exists.

## P1 — Contributor usefulness

1. Keep a small set of honest `good first issue` / `help wanted` tasks tied to real user or maintainer value.
2. Use native GitHub forms/templates/support routing before adding bots, CRMs, or third-party automation.
3. Require reproduction, expected/observed behavior, tests/screenshots/logs/rationale as applicable while minimizing private or copyrighted content.
4. Track external contributors, repeat contributors, real downstream users, and owner-created activity separately.
5. Do not use bought stars, fake engagement, spam, or mass unsolicited outreach.

## P2 — Reproducible public data

1. Maintain machine-readable asset metadata with byte size, row count, schema/version, SHA-256, provenance class, and license/status.
2. Add deterministic drift checks across SQLite/Parquet and any future GitHub↔HF↔Drive copies before claiming parity.
3. Keep sample queries/tests bound to committed assets.
4. Keep unknown provenance or redistribution status explicitly `UNKNOWN/REVIEW_REQUIRED`.

## P3 — Real ingestion and distribution, only after proof

1. Do not call `harvest_community.js` real source extraction while it synthesizes defaults instead of physically retrieving and binding transcript/source/license evidence.
2. Require fail-closed C17 execution proof on a supported Linux/x86 environment before promoting that path.
3. Require independently read-back GitHub and Hugging Face artifacts with matching hashes before calling dual-hub sync live.
4. Preserve manual/offline-safe verification and rollback paths.
5. Promote learner value only from real same-human pain → action → useful-result → measurement events.

## Success measures

- Current docs contain zero deployment, automation, provenance, parity, or learner-value claims that exceed physical evidence.
- Required checks appear and enforce normal protected merges for relevant PRs without path-filter deadlocks.
- Data assets have deterministic integrity/hash/provenance evidence and crash-safe export semantics.
- Contributor issues/forms reduce ambiguity without collecting unnecessary sensitive data.
- Real-user and external-contributor metrics are reported separately from owner-created activity.

## Historical note

Earlier September 2026 roadmap states referenced PR #5 as open/unmerged, `.github/workflows/` as absent from `main`, and a zero-job dependency hash-lock frontier. Those were valid snapshots of an earlier phase but are superseded by the current verified state above.
