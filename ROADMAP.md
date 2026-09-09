# Sovereign Study Commons India — Public Roadmap

_Last verified: 10 Sep 2026 against default-branch state after the first scheduled Pages-freshness proof and the later docs merge; exact main SHA must be re-read before promotion because `main` continues to advance._

This roadmap is truth-ranked. Current repository facts are separated from staged, unverified, and blocked work.

## Verified now

- The public repository exists on `main` and currently contains public UI files, SQLite and Parquet data assets, scripts, dataset documentation, contributor/governance files, issue templates, and **four** GitHub Actions workflows in `.github/workflows/`: `data-integrity.yml`, `sha256-idempotency-canary.yml`, `pages-endpoint-smoke.yml`, and `duckdb-cli-smoke.yml`.
- `main` is protected and currently requires the contexts `Data integrity` and `SHA256 idempotency canary` for non-admin merges. This is bounded governance evidence, not proof of an admin-proof/no-bypass policy.
- PR #33 merged through the normal protected path. Current workflow definitions emit both required integrity contexts on every pull request; path filters remain only for pushes to `main`.
- Default-branch repository bytes contain the evidence-first bug/data-integrity/provenance Issue Form, `config.yml` with blank issues disabled, the lecture-review form, and `SUPPORT.md` with privacy, copyright, issue-editability, and no-overclaim boundaries.
- The `Data integrity` workflow performs bounded SQLite/Parquet integrity checks, explicit FTS membership checks, key/provenance uniqueness checks where supported, and the canonicalization adversarial suite.
- The `SHA256 idempotency canary` exercises the isolated full-hash write-boundary canary. This does not prove persistent semantic-identity migration in the committed database.
- The `DuckDB CLI smoke` installs pinned DuckDB CLI `1.5.5`, verifies the downloaded archive SHA-256, and runs the existing regression harness against committed Parquet assets on relevant pull requests and pushes. This is bounded CLI/query-path evidence only; it does not prove dataset provenance, redistribution permission, GitHub↔HF↔Drive parity, or learner value.
- The `Pages endpoint smoke` has physically executed an unauthenticated external GET from GitHub Actions and passed HTTP 200, the stable public title marker, and stale unsafe-marker rejection. This is **`PUBLIC_ENDPOINT_REACHABILITY=PASS_BOUNDED_EXECUTED`** only; it is not browser E2E, mobile/accessibility, JavaScript-interaction, or learner-value proof.
- The Pages smoke 6-hour schedule physically executed as a genuine `schedule` event on default-branch SHA `6392f726e84cea44716a5f1c1a5c9f8c44740f03`; its public-endpoint job and endpoint assertion step succeeded. This establishes **`FIRST_SCHEDULED_EXECUTION=PASS_BOUNDED`** for that historical SHA. `main` later advanced to `a1a9f48a1fa9bb7cda3756f982f3885269f66549`, so **`CURRENT_MAIN_PERIODIC_FRESHNESS=STALE/PENDING_NEW_SCHEDULE`** until a newer genuine scheduled run succeeds on the then-current SHA. This is not an SLA or permanent freshness guarantee.
- Existing repaired SQLite evidence establishes a bounded source↔FTS membership state and transactional trigger synchronization on the tested artifact. It does not reconstruct historical causality by itself.
- The Spark daemon truth repair is merged: unsupported physical-verification claims were downgraded and daemon-side ambient Git commits were removed from that component.
- Issue #10 is a public opt-in pilot surface, but there are still zero verified non-founder same-human value events. Public availability alone is not learner-value or G3 evidence.

## Staged or independently unverified

- Repository bytes prove the structured issue-intake files exist on default branch, but independent public issue-chooser rendering and real triage usefulness remain UNVERIFIED until physically observed.
- A successful Pages endpoint smoke is not equivalent to independently verified learner-facing browser correctness or learner value.
- Current-main Pages periodic freshness is **STALE/PENDING_NEW_SCHEDULE** because the recorded successful scheduled run is bound to the prior SHA `6392f726e84cea44716a5f1c1a5c9f8c44740f03`, while `main` has advanced to `a1a9f48a1fa9bb7cda3756f982f3885269f66549`.
- Hugging Face activation and GitHub↔Hugging Face↔Drive exact snapshot parity remain unverified.
- Persistent semantic-identity migration, DB `UNIQUE`/upsert promotion, provenance referential integrity, real transcript/source ingestion, C17 Linux/x86 portability, and crash-safe Parquet replacement remain HOLD until their independent courts pass.
- Numerical learner gains remain UNVALIDATED. Fixed category retest intervals are `FIXED_DIAGNOSTIC_RETEST_CANARY`, not FSRS, and no neural-consolidation claim is made.

## P0 — Truth, safety, and reproducibility

1. Keep README, ROADMAP, UI, issue forms, and support docs synchronized with live repository state; historical claims must be clearly historical.
2. Preserve unconditional pull-request required-check emission and do not weaken branch protection to regain green status.
3. Preserve fail-closed SQLite/Parquet integrity, FTS membership, canonicalization, full-hash idempotency, privacy, rollback, and adversarial tests.
4. Replace direct canonical Parquet writes with temp → validate → atomic rename before calling export crash-safe.
5. Bind provenance/license status for externally sourced or derived assets before redistribution or parity promotion.
6. Keep semantic identity, persistent DB migration, and ingestion claims on HOLD until independent adversarial proof exists.
7. Keep Pages periodic-freshness claims SHA-bound: the first real scheduled proof covers `6392f726e84cea44716a5f1c1a5c9f8c44740f03`; current `main` is newer and remains stale until the next genuine `schedule` run and endpoint assertions succeed on the then-current SHA.

## P1 — Contributor usefulness

1. Independently verify the default-branch issue chooser renders both the evidence-defect form and the existing lecture-review form while blank issues remain disabled; keep real triage benefit UNVALIDATED until external traffic exists.
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
- Pages periodic-freshness remains SHA-bound: a successful genuine `schedule` event plus endpoint assertions establishes bounded freshness for that exact default-branch SHA, and a later `main` change requires a newer scheduled proof.
- Data assets have deterministic integrity/hash/provenance evidence and crash-safe export semantics.
- Contributor issues/forms reduce ambiguity without collecting unnecessary sensitive data.
- Real-user and external-contributor metrics are reported separately from owner-created activity.

## Historical note

Earlier September 2026 roadmap states referenced PR #5 as open/unmerged, `.github/workflows/` as absent from `main`, a two-workflow state before the Pages smoke, a three-workflow state before the real DuckDB CLI smoke, a configured-but-not-yet-periodically-verified Pages schedule, and then a first scheduled PASS bound to `6392f726e84cea44716a5f1c1a5c9f8c44740f03`. Those were valid snapshots of earlier phases; after `main` advanced to `a1a9f48a1fa9bb7cda3756f982f3885269f66549`, current-main periodic freshness became stale pending a newer scheduled run.