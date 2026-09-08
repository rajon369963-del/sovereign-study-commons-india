# Content Identity v1 — Tri-State Fail-Closed Contract

Status: **PROPOSED / NOT YET A DB UNIQUE CONSTRAINT**

REPO_TASK_ID: `SSC-R128-CONTENT-IDENTITY-TRISTATE-CANONICALIZATION-V1`
PRODUCT_TASK_ID: `R105_P0_5_JN_MOCK_REMEDIATION_MVP_V1`

## Why this exists
The repository already computes `study_units.sha256_hash` from `trim(exam_branch)::trim(video_id)::trim(question_text)::trim(exact_quote)`. That legacy formula is reproducible for the current repaired artifact, but a reproducible hash is not by itself a safe learner-facing identity contract. In particular, contradictory answer truth must never become a second ordinary valid unit.

## Decision model
Every comparison is classified as exactly one of:

- `SAME`: the learner/source-semantic unit is unchanged after deterministic canonicalization.
- `DISTINCT`: evidence proves a genuinely different source/version/question unit.
- `CONFLICT_OR_INVALID`: the records claim incompatible correctness/provenance for what otherwise appears to be the same evidence-bound unit, or required evidence is insufficient. This state must stop automatic dedup/admission and require adjudication.

`CONFLICT_OR_INVALID` is not a synonym for `DISTINCT`.

## Deterministic canonicalization
Before comparison:

1. Text fields: UTF-8; trim leading/trailing whitespace only. Do not lower-case, strip punctuation, fuzzy-match, embed, paraphrase-collapse, or Unicode-fold beyond the stored representation without a separately versioned contract.
2. `options_json`: parse as JSON. Reject invalid JSON. Recursively sort object keys, preserve array order, and serialize compactly with JSON string escaping and no insignificant whitespace. Key order or formatting differences alone therefore remain `SAME`.
3. `correct_opt`: trim only, then compare against the canonicalized option set. If two records have the same evidence-bound source/question/options but incompatible `correct_opt`, classify `CONFLICT_OR_INVALID` unless a distinct source/version context is independently proven.
4. `timestamp_span`: normalize only whitespace around the stored span. A changed span is `DISTINCT` only when it binds a genuinely different evidence segment/version; a cosmetic representation change without source change is `SAME` after a future explicitly versioned span normalizer, not guessed here.
5. `explanation`: explanation text is versioned content, not the primary unit key. A compatible paraphrase/improvement is `SAME` with an explanation-version delta. An explanation that contradicts the canonical answer/evidence is `CONFLICT_OR_INVALID`.

## Field roles
Primary evidence/source anchor candidates: `exam_branch`, `video_id`, `timestamp_span`, `question_text`, `options_json`, `exact_quote`.

Correctness-bearing field: `correct_opt`. A disagreement under the same canonical evidence/question/options is `CONFLICT_OR_INVALID` by default.

Versioned learner-content field: `explanation`. Compatible changes do not create a second ordinary unit; contradictory changes fail closed.

Metadata/taxonomy/locator fields: `teacher`, `subject`, `topic`, `drive_url`, `harvested_at`. These do not change learner identity by themselves, but every correction must preserve provenance lineage: old value, new value, evidence/reason, actor/process, and causal event or receipt ID when available. A metadata correction may not silently rewrite source identity.

## Adversarial decision table
The machine-readable fixtures live in `fixtures/content_identity_v1_adversarial.json` and are normative for this proposal.

Minimum required outcomes:

| Adversary | Expected |
| --- | --- |
| `options_json` key-order / insignificant whitespace only | `SAME` |
| same evidence/question/options, contradictory `correct_opt` | `CONFLICT_OR_INVALID` |
| compatible explanation paraphrase/improvement | `SAME` with versioned explanation delta |
| explanation contradicts canonical answer/evidence | `CONFLICT_OR_INVALID` |
| evidence-bound source/version genuinely changes | `DISTINCT` |
| teacher correction only, lineage preserved | `SAME` |
| subject/topic correction only, lineage preserved | `SAME` |
| attribution change without evidence lineage | `CONFLICT_OR_INVALID` |

## Migration gate
No stored-hash rewrite, `UNIQUE(...)`, `INSERT OR IGNORE`, upsert, or concurrent idempotency policy is authorized by this document. Before any migration:

1. AIR10-05/Lane5 independently recomputes every fixture from raw fields, ignoring expected-result prose as evidence.
2. All `SAME` / `DISTINCT` / `CONFLICT_OR_INVALID` adversaries pass with deterministic canonical bytes.
3. The current dataset is independently recomputed under the accepted versioned identity contract and collisions are inspected field-by-field.
4. Only then may a separate migration prove serial + concurrent idempotency, zero ghost/missing FTS rows, `PRAGMA integrity_check`, exact source↔FTS membership, rollback from preserved pre-migration bytes, and no unrelated data loss.

Until all of those pass: `HASH_MIGRATION=FORBIDDEN`, `DB_UNIQUENESS_IDEMPOTENCY=HOLD`.

## Boundaries
This proposal does not prove licensing, attribution accuracy, transcript authenticity, GitHub↔HF↔Drive parity, learner efficacy, score/rank gain, FSRS behavior, or neural consolidation. `FIXED_DIAGNOSTIC_RETEST_CANARY` remains distinct from FSRS. Numerical learner gains remain unvalidated until real cohort evidence exists.
