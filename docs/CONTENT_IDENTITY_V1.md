# Content Identity v1 — Deterministic Fail-Closed Proposal

Status: **PROPOSED / NOT YET A DB UNIQUE CONSTRAINT**

REPO_TASK_ID: `SSC-R132-SEMANTIC-DECISION-ORACLE-FAIL-CLOSED-V1`
PRODUCT_TASK_ID: `R105_P0_5_JN_MOCK_REMEDIATION_MVP_V1`

## Why this exists
The repository already computes `study_units.sha256_hash` from `trim(exam_branch)::trim(video_id)::trim(question_text)::trim(exact_quote)`. That legacy formula is reproducible for the current repaired artifact, but reproducibility alone does not define safe learner-facing identity. The comparison gate must be mechanically recomputable from raw fields, and semantic ambiguity must stop automatic admission rather than inherit a fixture author's prose label.

The executable proposal is `scripts/content_identity_oracle.py`; adversarial inputs are in `fixtures/content_identity_v1_adversarial.json`.

## Decision model
The automatic output is exactly one of:

- `SAME`: canonical learner/source semantics are mechanically identical, or a single metadata correction is exactly backed by declared lineage.
- `DISTINCT`: both a canonical source locator and the evidence payload change. This is intentionally conservative.
- `CONFLICT_OR_INVALID`: malformed input, contradictory correctness, missing lineage, or insufficient evidence to prove `SAME`/`DISTINCT`.

When semantics cannot be decided from the declared fields, the result additionally carries `HUMAN_ADJUDICATION_REQUIRED`. This flag does **not** authorize Rajon busywork; it means automated hash/dedup admission must remain stopped until an authorized evidence-bearing adjudication exists.

## Deterministic canonicalization
Before comparison:

1. Text identity fields (`exam_branch`, `video_id`, `question_text`, `exact_quote`) are UTF-8 strings with edge whitespace trimmed only. No fuzzy matching, embeddings, paraphrase collapse, lowercase transform, or hidden Unicode normalization is used.
2. `options_json` must parse as a JSON object or array. Objects are compact-serialized with recursively sorted keys; array order is preserved. Invalid JSON fails closed.
3. `correct_opt` is edge-trimmed and must be an actual canonical option label. Object options use their keys. Array options use explicit 1-based position labels. An absent label fails closed.
4. `timestamp_span` must be a start/end range in `MM:SS` or `HH:MM:SS`. Whitespace and separators (`-`, en/em dash, `to`) are formatting only. Parsed endpoints become integer seconds. Invalid/reversed spans fail closed.
5. `explanation` is required but is **not** automatically interpreted for semantic compatibility. If only explanation text changes, automatic output is `CONFLICT_OR_INVALID` + `HUMAN_ADJUDICATION_REQUIRED`. This removes the prior false-green assumption that a machine can infer “compatible paraphrase” from unconstrained prose.

## Deterministic comparison rule
Let the canonical source/evidence fields be:

`exam_branch`, `video_id`, `timestamp_span`, `question_text`, `options_json`, `exact_quote`.

- If all six fields match and `correct_opt` differs: `CONFLICT_OR_INVALID`.
- If all six fields, `correct_opt`, and `explanation` match: `SAME`.
- If all six fields + `correct_opt` match but `explanation` changes: `CONFLICT_OR_INVALID` + `HUMAN_ADJUDICATION_REQUIRED`.
- If identity-bearing fields change, automatic `DISTINCT` is allowed only when at least one locator field (`exam_branch`, `video_id`, `timestamp_span`) **and** at least one payload field (`question_text`, `options_json`, `exact_quote`) change.
- Locator-only or payload-only changes are ambiguous and fail closed with `HUMAN_ADJUDICATION_REQUIRED`.

This rule deliberately prefers false-negative automation over silent false merges/splits.

## Metadata corrections
`teacher`, `subject`, and `topic` corrections are `SAME` only when exactly one metadata field changes and a lineage object contains non-empty `old_value`, `new_value`, `evidence`, and `causal_event_id`, with old/new values exactly matching the changed field. Multiple simultaneous metadata corrections or missing/mismatched lineage fail closed.

`drive_url` and `harvested_at` remain non-identity metadata, but this proposal does not silently rewrite them as provenance truth.

## Adversarial contract
The fixture set covers, at minimum:

- JSON key-order/whitespace equivalence;
- contradictory `correct_opt`;
- explanation-only ambiguity;
- apparently contradictory explanation without NLP guessing;
- genuine locator + payload change;
- lineage-backed teacher/topic corrections;
- attribution change without lineage;
- malformed JSON;
- nested JSON key canonicalization;
- option-array order change;
- `correct_opt` absent from options;
- cosmetic timestamp formatting;
- span-only movement ambiguity.

Expected labels in the fixture file are regression expectations only. They are **not** independent evidence. AIR10-05/Lane5 must derive decisions by executing or independently reimplementing the raw-input rule and may not use the stored `expected` field as certification.

## Migration gate
No stored-hash rewrite, `UNIQUE(...)`, `INSERT OR IGNORE`, upsert, committed SQLite migration, or production idempotency policy is authorized by this document or script. Before any migration:

1. AIR10-05/Lane5 independently recomputes the raw fixture decisions and attacks malformed/nested JSON, timestamp normalization, correctness membership, explanation ambiguity, and metadata lineage.
2. The accepted oracle must pass fresh-context adversaries without reading expected labels as truth.
3. The current dataset must be recomputed under the accepted versioned identity rule and every collision inspected.
4. Only then may a separate migration prove serial + concurrent idempotency, zero ghost/missing FTS rows, `PRAGMA integrity_check`, exact source↔FTS membership, rollback from preserved pre-migration bytes, and no unrelated data loss.

Until then: `HASH_MIGRATION=FORBIDDEN`, `DB_UNIQUENESS_IDEMPOTENCY=HOLD`.

## Boundaries
This proposal does not prove licensing, attribution accuracy, transcript authenticity, GitHub↔HF↔Drive parity, learner efficacy, score/rank gain, FSRS behavior, or neural consolidation. `FIXED_DIAGNOSTIC_RETEST_CANARY` remains distinct from FSRS. Numerical learner gains remain unvalidated until real cohort evidence exists.
