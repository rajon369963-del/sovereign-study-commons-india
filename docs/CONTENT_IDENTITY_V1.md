# Content Identity v1 — Fail-Closed Contract

Status: **PROPOSED / NOT YET A DB UNIQUE CONSTRAINT**

REPO_TASK_ID: `SSC-R126-CONTENT-IDENTITY-V1-BOUNDARY`

## Why this exists
The repository already computes `study_units.sha256_hash` from `trim(exam_branch)::trim(video_id)::trim(question_text)::trim(exact_quote)`. That formula is reproducible and independently matched the current repaired 11-row artifact, but reproducibility alone does not prove those four fields fully define one logical learner-facing study unit.

## Identity-bearing fields for v1
Changes to these fields create a distinct learner/source-semantic unit: `exam_branch`, `video_id`, `timestamp_span`, `question_text`, `options_json`, `correct_opt`, `explanation`, `exact_quote`.

Canonicalization: UTF-8 text after leading/trailing whitespace trim only. No lower-casing, punctuation stripping, Unicode folding, paraphrase matching, embeddings, or fuzzy matching.

Canonical proposed v1 payload order:
`exam_branch::video_id::timestamp_span::question_text::options_json::correct_opt::explanation::exact_quote`

No hash migration is authorized merely by this document.

## Metadata-only fields for v1
These may change without creating a new logical unit if the identity-bearing payload is identical: `teacher` (attribution/display metadata; source is bound by video + exact span), `subject`, `topic` (taxonomy), `drive_url` (storage locator), `harvested_at` (operational timestamp). If later evidence falsifies this classification, version-bump before migration.

## Adversarial decision table
Holding the legacy four hash fields fixed: `timestamp_span`, `options_json`, `correct_opt`, or `explanation` changes => DISTINCT. `teacher`, `subject`, `topic`, `drive_url`, or `harvested_at` alone => SAME. This is deliberately conservative: false merge is worse than temporary duplicate before migration.

## Migration gate
Before any `UNIQUE(...)`, `INSERT OR IGNORE`, or upsert policy: independently recompute proposed v1 identity for all rows; report collisions with differing fields; run serial and concurrent duplicate adversaries; prove one durable logical row for identical v1 content; prove zero ghost/missing FTS rows; rerun `PRAGMA integrity_check` and exact source↔FTS membership; preserve pre-migration DB bytes for rollback. Until all pass: `DB_UNIQUENESS_IDEMPOTENCY=HOLD`.

## Boundaries
This contract does not prove licensing, attribution accuracy, transcript authenticity, GitHub↔HF↔Drive parity, learner efficacy, score gain, FSRS behavior, or neural consolidation. `FIXED_DIAGNOSTIC_RETEST_CANARY` remains distinct from FSRS.
