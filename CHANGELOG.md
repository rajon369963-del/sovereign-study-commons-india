# Changelog

This file records material public-repository changes. It does not convert staged, branch-only, synthetic, or unverified effects into deployment claims.

## 2026-09-08

### Added
- `ROADMAP.md` with truth-ranked shipped/planned separation.
- `CONTRIBUTING.md` and `SECURITY.md` contributor/safety guidance.
- `CONTRIBUTOR_LADDER.md` mapping beginner-to-advanced contribution rungs.
- `CODE_OF_CONDUCT.md` for community participation expectations.
- Beginner-friendly public issues covering README truth audit, dataset provenance manifest, DuckDB smoke verification, and discoverability/topics.

### Verification / CI
- Pull request #5 introduces a read-only SQLite/Parquet data-integrity workflow on its branch.
- The PR workflow has a successful branch/PR Actions run, but PR #5 is still unmerged at the time of this entry.
- Therefore `.github/workflows/` is **not yet present on `main`**, and repository automation must not be described as live on `main`.

### Still unverified or pending
- GitHub-to-Hugging-Face synchronization and artifact parity.
- Independent GitHub Pages rendered-content verification.
- Drive backup/sharing parity.
- Complete machine-readable dataset provenance/license manifest.
- External contributor conversion, repeat-user evidence, and learner value signals.

## Changelog rule

Only record an item as live/deployed after the corresponding public artifact or workflow is present on `main` and independently read back. Unknown provenance or license status remains `UNKNOWN/REVIEW_REQUIRED` until evidenced.
