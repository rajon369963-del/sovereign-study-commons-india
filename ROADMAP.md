# Sovereign Study Commons India — Public Roadmap

_Last verified: 8 Sep 2026_

This roadmap is deliberately truth-ranked: shipped evidence is separated from planned or blocked work.

## Verified now

- Public GitHub repository exists on `main`.
- Root `index.html`, `cockpit/index.html`, Parquet assets, SQLite asset, C17 binary, scripts, dataset card, MIT license, issue template, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTOR_LADDER.md`, and `CHANGELOG.md` are present.
- Four bounded beginner-friendly contribution issues are open for README truth, dataset provenance manifest, DuckDB smoke verification, and discoverability/topics.
- Pull request #5 contains a read-only SQLite/Parquet data-integrity workflow and has a successful PR-branch Actions run.
- PR #5 remains unmerged. Therefore `.github/workflows/` is still absent from `main`; the successful PR run is a **branch CI canary**, not live `main` automation.
- GitHub→Hugging Face synchronization remains unverified until a real `main` workflow run succeeds and intended downstream artifacts are independently read back.

## P0 — Truth and safety

1. Complete the README live-vs-staged claim audit.
2. Verify GitHub Pages rendered content independently before calling the cockpit publicly deployed.
3. Document provenance/license status for every externally sourced or derived data asset.
4. Security-court PR #5 dependencies, workflow permissions, and data provenance before any merge decision; after merge, require a successful `main` run before calling CI live.

## P1 — Contributor funnel

1. Keep at least three honest, bounded contribution opportunities available whenever real work exists.
2. Add evidence-backed repository topics only when they map to current `main` content.
3. Track external PRs, merged external contributions, repeat contributors, and downstream users separately from owner-created activity.
4. Do not use bought stars, spam, mass unsolicited outreach, or manipulative growth tactics.

## P2 — Reproducible public data

1. Publish a machine-readable manifest containing asset path, byte size, row count, schema/version identifier, SHA-256, provenance class, and license/status.
2. Add deterministic validation that flags asset drift, duplicate IDs, malformed source URLs, missing attribution, or schema drift.
3. Add sample DuckDB queries that are tested against the committed assets.
4. Keep unknown provenance or redistribution status explicitly `UNKNOWN/REVIEW_REQUIRED`.

## P3 — Automation, only after proof

1. Merge a reviewed workflow into `.github/workflows/` only after dependency/action provenance, permissions, and data-license/provenance checks pass.
2. Require one successful `main` run before describing repository data-integrity CI as live.
3. Require artifact readback from both GitHub and Hugging Face before describing dual-hub sync as live.
4. Preserve a manual/offline-safe verification path when automation is unavailable.

## Success measures

- README contains zero deployment/automation claims that exceed independently verified state.
- 3+ contributor-ready issues exist with measurable outcomes.
- New data contributions carry provenance and license evidence.
- Any automation claim links to a successful relevant workflow run and verifiable output.
- External contributor/repeat-user metrics are reported separately from owner-generated repository activity.
