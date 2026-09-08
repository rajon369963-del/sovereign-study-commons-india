# Content Identity v1 — Fail-Closed Contract

Status: **PROPOSED / NOT YET A DB UNIQUE CONSTRAINT**

REPO_TASK_ID: `SSC-R126-CONTENT-IDENTITY-V1-BOUNDARY`

## Why this exists

The repository already computes `study_units.sha256_hash` from:

`trim(exam_branch)::trim(video_id)::trim(question_text)::trim(exact_quote)`

That formula is reproducible and independently matched the current repaired 11-row artifact, but reproducibility alone does not prove that those four fields fully define one logical learner-facing study unit. A deduplication key must not silently collapse two units whose learner-visible meaning differs.

## Identity-bearing fields for v1

The following fields are treated as identity-bearing because changing any one can change the learner-facing unit, the answer contract, or the exact source span being evidenced:

- `exam_branch`
- `video_id`
- `timestamp_span`
- `question_text`
- `options_json`
- `correct_opt`
- `explanation`
- `exact_quote`

Canonicalization rule for text fields: UTF-8 text after leading/trailing whitespace trim only. No lower-casing, punctuation stripping, Unicode folding, paraphrase matching, semantic embeddings, or fuzzy matching is allowed in v1.

Canonical v1 payload order:

`exam_branch::video_id::timestamp_span::question_text::options_json::correct_opt::explanation::exact_quote`

A future implementation may hash this exact payload with SHA-256, but no migration is authorized merely by this document. Stored hashes must first be recomputed on a disposable copy and independently adjudicated.

## Metadata-only fields for v1

These may change without creating a new logical study unit, provided the identity-bearing payload above remains identical:

- `teacher`: attribution/display metadata; `video_id` + exact source span carries source identity for this contract.
- `subject`: taxonomy/navigation metadata.
- `topic`: taxonomy/navigation metadata.
- `drive_url`: storage locator; moving the same content must not create a duplicate study unit.
- `harvested_at`: ingestion timestamp; operational metadata only.

If later evidence shows any metadata-only field changes learner meaning or provenance identity, this contract must be version-bumped before migration.

## Adversarial decision table

Hold all current four legacy hash fields fixed and vary one field at a time:

- `timestamp_span` changed -> **DISTINCT**
- `options_json` changed -> **DISTINCT**
- `correct_opt` changed -> **DISTINCT**
- `explanation` changed -> **DISTINCT**
- `teacher` changed only -> **SAME**
- `subject` changed only -> **SAME**
- `topic` changed only -> **SAME**
- `drive_url` changed only -> **SAME**
- `harvested_at` changed only -> **SAME**

This is deliberately conservative: a false merge is more dangerous than an extra duplicate during the pre-migration phase.

## Migration gate

Before any `UNIQUE(...)`, `INSERT OR IGNORE`, or conflict-upsert policy is applied:

1. Independently recompute the proposed v1 payload/hash for every current row.
2. Report collisions with full row IDs and the differing fields.
3. Run serial duplicate insertion and concurrent duplicate insertion adversaries.
4. Prove exactly one durable logical row remains for identical v1 content.
5. Prove FTS contains no ghost duplicate and no missing source row after conflict handling.
6. Re-run `PRAGMA integrity_check` and exact source↔FTS membership.
7. Keep rollback to the pre-migration DB bytes.

Until all seven pass: `DB_UNIQUENESS_IDEMPOTENCY=HOLD`.

## Boundaries

This contract does **not** prove source licensing, teacher attribution accuracy, transcript authenticity, GitHub↔HF↔Drive parity, learner efficacy, score gain, FSRS behavior, or neural consolidation. `FIXED_DIAGNOSTIC_RETEST_CANARY` remains distinct from FSRS.
