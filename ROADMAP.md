# Sovereign Study Commons India — Public Roadmap

_Last verified: 8 Sep 2026_

This roadmap is deliberately truth-ranked: shipped evidence is separated from planned or blocked work.

## Verified now

- Public GitHub repository exists on `main`.
- Root `index.html`, `cockpit/index.html`, Parquet assets, SQLite asset, C17 binary, scripts, dataset card, MIT license, and an issue template are present.
- The repository currently has **no `.github/workflows/` directory**. The workflow YAML lives under `workflows_template/` only.
- Therefore GitHub Actions ingestion and GitHub→Hugging Face synchronization are **not live/verified automation** yet.
- Hugging Face linkage must be treated as planned/unverified until a real workflow exists, a run succeeds, and intended artifacts are independently read back.

## P0 — Truth and safety

1. Remove or qualify README statements that describe staged automation as live.
2. Verify GitHub Pages independently before calling the cockpit publicly deployed.
3. Document provenance/license rules for every externally sourced transcript, question, video metadata, and derived study unit.
4. Add reproducible integrity checks for Parquet/SQLite row counts, schema, hashes, and source references.

## P1 — Contributor funnel

1. Add beginner-friendly issues with bounded acceptance criteria.
2. Add `CONTRIBUTING.md` and `SECURITY.md`.
3. Add a Code of Conduct before inviting broad community participation.
4. Keep at least three honest, small contribution opportunities available whenever real work exists.

## P2 — Reproducible public data

1. Publish a machine-readable manifest containing asset path, row count, schema version, SHA-256, provenance class, and license status.
2. Add deterministic validation scripts that fail on duplicate IDs, malformed source URLs, missing attribution, or schema drift.
3. Add sample DuckDB queries that are tested against the committed assets.

## P3 — Automation, only after authorization and proof

1. Move a reviewed workflow into `.github/workflows/` only when GitHub Actions permissions/secrets are explicitly authorized.
2. Require one successful run before describing ingestion as automated.
3. Require artifact readback from both GitHub and Hugging Face before describing dual-hub sync as live.
4. Preserve a manual/offline-safe path when automation is unavailable.

## Success measures

- README contains zero deployment/automation claims that exceed independently verified state.
- 3+ contributor-ready issues exist with measurable outcomes.
- New data contributions carry provenance and license evidence.
- Any future automation claim links to a successful workflow run and verifiable output.
