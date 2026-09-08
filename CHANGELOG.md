# Changelog

This file records material public-repository changes. It does not convert staged, branch-only, synthetic, or unverified effects into deployment claims.

## 2026-09-08

### Added
- `ROADMAP.md` with truth-ranked shipped/planned separation.
- `CONTRIBUTING.md` and `SECURITY.md` contributor/safety guidance.
- `CONTRIBUTOR_LADDER.md` mapping beginner-to-advanced contribution rungs.
- `CODE_OF_CONDUCT.md` for community participation expectations.
- Beginner-friendly public issues covering README truth audit, dataset provenance manifest, DuckDB smoke verification, and discoverability/topics.

### Contributor-truth repair
- Issue #6 reproduced a false automation promise in `.github/ISSUE_TEMPLATE/ingest_lecture_playlist.yml`.
- Current `main` now states that playlist/video submissions create review requests only and do not automatically run C17 cleaning, deduplication, transcript extraction, or Hugging Face publishing.
- This wording repair does **not** activate ingestion; staged parser/ingestion fail-closed semantics remain a separate evidence gate.

### Verification / CI
- Pull request #5 introduces a read-only SQLite/Parquet data-integrity workflow on its branch.
- The PR workflow has a successful branch/PR Actions run, but independent review found a material evidence gap: `study_units=11` while several FTS tables report 10, and the workflow does not yet enforce intended FTS membership, duplicate/collision constraints, or dependency hash pinning.
- PR #5 is still unmerged. Therefore `.github/workflows/` is **not yet present on `main`**, and repository automation must not be described as live on `main`.
- Pull request #7 is open and unmerged with a single declarative evidence-first PR template. It adds no workflow, bot, dependency, permission expansion, or automated enforcement.

### Still unverified or pending
- GitHub-to-Hugging-Face synchronization and artifact parity.
- Independent GitHub Pages rendered-content verification.
- Drive backup/sharing parity.
- Complete machine-readable dataset provenance/license manifest.
- PR #5 full FTS/index-integrity semantics and supply-chain reproducibility repair.
- PR #7 independent contributor-burden/privacy/licensing court and merge decision.
- External contributor conversion, repeat-user evidence, and learner value signals.

## Changelog rule

Only record an item as live/deployed after the corresponding public artifact or workflow is present on `main` and independently read back. Unknown provenance or license status remains `UNKNOWN/REVIEW_REQUIRED` until evidenced.
