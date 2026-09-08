# Contributing

Thank you for helping build a free, evidence-backed study commons for Indian learners.

## Best first contributions

Choose a small open issue with clear acceptance criteria. Prefer fixes to documentation, provenance, validation, examples, or metadata before adding new systems.

Use the [Contributor Ladder](CONTRIBUTOR_LADDER.md) to choose work that matches your current skill level—from zero-code truth/provenance fixes through reproducible DuckDB tests to advanced parser, CI, Pages, and publishing work.

## Evidence rules

- Do not upload copyrighted material unless redistribution rights are clear.
- Prefer official/public-domain/openly licensed sources and link the original source.
- Record provenance: source URL, title, publisher/teacher, retrieval date, and license/usage status when known.
- Do not include private learner data, harvested contacts, credentials, tokens, or secrets.
- Do not claim a workflow, deployment, Hugging Face sync, Pages site, or dataset count is live unless it can be independently reproduced.
- Provenance lineage does not authorize an arbitrary metadata rewrite. For correction workflows, define the exact allowed field set first; reject unknown, additional, or out-of-scope changed keys even when they carry plausible-looking lineage. If the metadata schema is JSON-shaped, prefer an explicit closed schema (for example declared `properties` plus `additionalProperties: false`, or the appropriate `unevaluatedProperties` rule when schemas are composed) and version the correction contract.

## Pull request checklist

- Scope is one bounded effect.
- Existing wheel/code was checked before introducing a new dependency.
- Tests or a reproducible verification command are included when applicable.
- Data/schema changes include provenance and license notes.
- Metadata-correction code proves at least one allowed-field case and one unknown/additional-field fail-closed case before merge.
- Documentation describes actual current state, not intended future state.
- No secrets or private data are committed.

## Data contributions

For playlists or study sources, use the issue template. Submission does **not** imply automatic ingestion. Maintainers review source legality, provenance, duplication, schema fit, and quality before accepting data.

## Community conduct

Be respectful, learner-first, evidence-first, and specific. Critique claims and artifacts rather than people. Spam, bought engagement, mass unsolicited outreach, and manipulative growth tactics are not welcome.
