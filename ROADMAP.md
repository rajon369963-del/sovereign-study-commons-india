# Sovereign Study Commons India — Public Roadmap

_Last verified: 8 Sep 2026_

This roadmap is deliberately truth-ranked: shipped evidence is separated from planned or blocked work.

## Verified now

- Public GitHub repository exists on `main`.
- Root `index.html`, `cockpit/index.html`, Parquet assets, SQLite asset, C17 binary, scripts, dataset card, MIT license, issue templates, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTOR_LADDER.md`, and `CHANGELOG.md` are present.
- Four bounded beginner-friendly contribution issues remain open for README truth, dataset provenance manifest, DuckDB smoke verification, and discoverability/topics.
- Issue #6 identified a contributor-trust bug in the lecture-playlist Issue Form. Current `main` now truthfully labels submissions as review requests and explicitly says they do not trigger automatic C17 cleaning, deduplication, transcript extraction, or Hugging Face publishing.
- Pull request #7 is open and unmerged. It adds one declarative evidence-first PR template only; the current branch wording says contributors should provide only evidence that applies to their change and may mark/remove non-applicable checks. This closes the specific docs-only checklist ambiguity, but the template is still branch-only governance until reviewed and merged.
- Pull request #5 is open and unmerged. Its branch-only read-only data-integrity workflow previously produced a green canary, but the current head adds fail-closed FTS membership and duplicate-ID assertions and its latest run (`34230381135`) is **RED** at `Verify SQLite and Parquet integrity`. That red run is useful evidence that the gate is detecting a real source/index contract mismatch; it is not merge readiness and must not be weakened to recover green.
- Current bus/root-cause evidence binds the missing FTS member to one later source insert (`GATE-EE-COM-004` / rowid 11) that was not synchronized into the standalone/contentful FTS representation. This cause still needs independent repo-side reproduction before repair is promoted.
- Therefore `.github/workflows/` is still absent from `main`; PR #5 remains a **branch CI canary**, not live `main` automation.
- Pull request #8 is open and unmerged and is limited to UI truth-boundary wording; it is not provenance, efficacy, deployment, or learner-value evidence.
- GitHub→Hugging Face synchronization remains unverified until a real reviewed `main` workflow run succeeds and intended downstream artifacts are independently read back.

## P0 — Truth and safety

1. Complete the README live-vs-staged claim audit.
2. Verify GitHub Pages rendered content independently before calling the cockpit publicly deployed.
3. Document provenance/license status for every externally sourced or derived data asset.
4. Keep Issue #6 open until any staged parser/ingestion path also fails closed on malformed inputs, missing provenance, and C17 failures; the public Issue Form wording repair alone does not activate ingestion.
5. Preserve PR #5's fail-closed RED state until the exact source-vs-index mismatch is independently reproduced and repaired; also add dependency-hash reproducibility. Then require a successful branch rerun, reviewed merge, and a successful `main` run before calling CI live.
6. Keep PR #7's evidence-proportionality clarification intact; independently court privacy/licensing wording and maintainer burden before any merge decision. Treat its checklist as declarative governance only unless a separate verified enforcement mechanism is introduced.
7. Treat PR #8 only as a truth-boundary repair unless independent deployment/provenance/efficacy evidence is produced.

## P1 — Contributor funnel

1. Keep at least three honest, bounded contribution opportunities available whenever real work exists.
2. Add evidence-backed repository topics only when they map to current `main` content.
3. Track external PRs, merged external contributions, repeat contributors, and downstream users separately from owner-created activity.
4. Do not use bought stars, spam, mass unsolicited outreach, or manipulative growth tactics.

## P2 — Reproducible public data

1. Publish a machine-readable manifest containing asset path, byte size, row count, schema/version identifier, SHA-256, provenance class, and license/status.
2. Add deterministic validation that flags asset drift, duplicate IDs, malformed source URLs, missing attribution, schema drift, and unexplained FTS/index membership drift.
3. Add sample DuckDB queries that are tested against the committed assets.
4. Keep unknown provenance or redistribution status explicitly `UNKNOWN/REVIEW_REQUIRED`.

## P3 — Automation, only after proof

1. Merge a reviewed workflow into `.github/workflows/` only after dependency/action provenance, permissions, data-license/provenance, and data/index-integrity checks pass.
2. Require one successful `main` run before describing repository data-integrity CI as live.
3. Require artifact readback from both GitHub and Hugging Face before describing dual-hub sync as live.
4. Preserve a manual/offline-safe verification path when automation is unavailable.

## Success measures

- README, roadmap, and contributor forms contain zero deployment/automation claims that exceed independently verified state.
- 3+ contributor-ready issues exist with measurable outcomes.
- New data contributions carry provenance and license evidence.
- Any automation claim links to a successful relevant workflow run and verifiable output.
- External contributor/repeat-user metrics are reported separately from owner-generated repository activity.
