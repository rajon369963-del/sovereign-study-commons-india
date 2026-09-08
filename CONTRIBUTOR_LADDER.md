# Contributor Ladder

This project should be easy to improve without requiring contributors to understand the whole data pipeline first. Start at the lowest rung that matches your skills and move upward only when the evidence and acceptance tests justify it.

## Ground rules at every rung

- Keep each contribution to one bounded effect.
- Prefer official, public-domain, or clearly licensed sources.
- Record source URL, publisher/teacher, retrieval date, and license/usage status when known.
- Do not add private learner data, harvested contacts, credentials, or secrets.
- Do not describe staged workflows, Hugging Face sync, Pages, dataset counts, or automation as live unless a newcomer can independently reproduce the claim.
- Check existing tools, libraries, actions, and repository code before introducing a new dependency.
- Treat a stored SHA-256 as evidence about exact bytes only. Do not infer semantic content identity or add a uniqueness constraint until the canonical payload fields/bytes, canonicalization rules, hash algorithm/version, and independent recomputation procedure are explicitly defined.
- For identity-bearing structured fields, canonicalize by semantic type before hashing or deduplication. A JSON object needs a deterministic semantic representation (for example RFC 8785/JCS when the domain fits); a timestamp/range needs explicitly parsed start/end values plus unit/timebase. Do not treat arbitrary display serialization, key order, whitespace, or formatting as semantic identity unless the contract explicitly declares representation-sensitive identity.

## Rung 0 — zero-code truth and documentation fixes

**Skills:** careful reading; no Git or coding expertise required.

Good contributions:
- Audit a README claim against the current public repository and endpoint state.
- Fix a broken link, ambiguous status label, typo, or stale setup instruction.
- Improve a glossary entry so a newcomer can understand a dataset field or exam branch.

Current small task: [Issue #1 — audit README live-status claims](https://github.com/rajon369963-del/sovereign-study-commons-india/issues/1).

**Acceptance test:** another person can follow the edited text and reach the same factual conclusion from public evidence.

## Rung 1 — provenance and metadata fixes

**Skills:** spreadsheets/CSV/Markdown; basic source checking.

Good contributions:
- Add or repair source provenance records.
- Classify license/usage status without copying copyrighted content into the repo.
- Add retrieval dates and source locators to a manifest.
- When recording hashes, state exactly what bytes were hashed and which algorithm/version produced the value; snapshot uniqueness alone is not a semantic identity contract.

Current small task: [Issue #2 — dataset manifest/provenance](https://github.com/rajon369963-del/sovereign-study-commons-india/issues/2).

**Acceptance test:** every changed row points to a retrievable source and has enough provenance for an independent reviewer to reproduce the classification. Hash-bearing rows additionally identify the hashed payload and algorithm/version so another reviewer can recompute the value.

## Rung 2 — reproducible query examples and smoke tests

**Skills:** basic SQL or command line.

Good contributions:
- Add a DuckDB smoke query for a checked-in Parquet asset.
- Turn a README example into a deterministic test fixture.
- Verify schema/column assumptions and report exact failures instead of silently adapting them.

Current small task: [Issue #3 — DuckDB smoke tests](https://github.com/rajon369963-del/sovereign-study-commons-india/issues/3).

**Acceptance test:** a clean environment can run the documented command against current `main` and get the documented schema/result class.

## Rung 3 — discoverability and contributor UX

**Skills:** GitHub basics; information architecture.

Good contributions:
- Propose evidence-backed repository topics that match artifacts already present on `main`.
- Connect README sections to examples, issue templates, provenance docs, roadmap entries, and contribution tasks.
- Improve issue templates so scope, source evidence, acceptance tests, and license risk are explicit.

Current small task: [Issue #4 — evidence-backed topics and discoverability glossary](https://github.com/rajon369963-del/sovereign-study-commons-india/issues/4).

**Acceptance test:** every discoverability term maps to a current repository artifact or documented supported branch; no keyword stuffing.

## Rung 4 — parser and data-pipeline contributions

**Skills:** Python/Node/C/C++/data engineering depending on the touched component.

Good contributions:
- Repair a parser on a frozen public fixture.
- Improve deduplication or schema validation with regression tests.
- Add a deterministic conversion step that preserves provenance and license metadata.
- Define a canonical content-identity contract before deduplication or schema-level uniqueness: payload fields/bytes, canonicalization, hash algorithm/version, and an independent recomputation test must be explicit first.
- Add paired adversarial SAME/DISTINCT fixtures for every structured identity-bearing field. Equivalent JSON key order/whitespace or equivalent range formatting should remain SAME when semantics are unchanged; changed option content or changed parsed range endpoints should be DISTINCT.

**Required before merge:** fixture-based regression test, failure case, rollback path, and maintainer review. Do not activate external sync or ingestion just because a parser test passes. Do not promote a uniqueness migration merely because the current snapshot happens to contain no duplicate hashes. For structured fields, the acceptance court must prove semantic invariance across alternate serializations and semantic separation across genuinely different values, unless the versioned identity contract explicitly chooses representation-sensitive identity.

## Rung 5 — CI, workflows, Pages, and external sync

**Skills:** GitHub Actions, deployment/security, data publishing.

Good contributions only after lower-level contracts exist:
- Promote a staged workflow into `.github/workflows/` with least-privilege permissions.
- Add CI for DuckDB/schema/provenance tests.
- Add or repair GitHub Pages build verification.
- Add Hugging Face sync only with explicit authorization, provenance gates, dry-run support, and an independently reproducible execution receipt.

**Acceptance test:** the workflow is present on `main`, its trigger and permissions are inspectable, a real run is independently reproducible, failures fail closed, and rollback is documented.

## Maintainer / verifier split

For claims that affect deployment, automation, dataset integrity, provenance, semantic identity, or learner-facing behavior, the producer should not be the final verifier. A second reviewer should reproduce the acceptance test from current public state before the claim is promoted from **STAGED/UNVERIFIED** to **VERIFIED**.

## How the repository surfaces connect

`README` → tells newcomers what is verified today and points to runnable examples.

`CONTRIBUTING` → defines evidence, license, scope, and PR rules.

`CONTRIBUTOR_LADDER` → routes contributors from zero-code fixes to advanced pipeline work.

`Issues / issue templates` → hold bounded tasks with acceptance tests and provenance context.

`DATASET_CARD` + provenance manifests → define dataset meaning, source lineage, usage constraints, and the payload identity contract used by any hashes or deduplication.

`ROADMAP` → separates staged work from verified capabilities.

`Tests / CI` → turn documented contracts into reproducible checks.

`Pages / Hugging Face` → distribution surfaces only after repository truth and automation gates are independently verified.
