# ⚡ Sovereign Study Commons India (सार्वजनिक अध्ययन महा-ज्ञानकोश)

> भारत के छात्रों के लिए एक public, open study-data commons. Repository truth is strictly preferred over intended future state.

## Live truth status — verified 9 Sep 2026

Every operational and dataset claim is explicitly classified:

- **`[VERIFIED]` GitHub repository:** public and readable at `https://github.com/rajon369963-del/sovereign-study-commons-india`.
- **`[VERIFIED]` Dataset assets & manifest:** committed Parquet and SQLite lake assets match physical SHA-256 hashes and row counts verified via [`data_lake/dataset_manifest.json`](data_lake/dataset_manifest.json) and [`scripts/verify_dataset_manifest.py`](scripts/verify_dataset_manifest.py).
- **`[VERIFIED]` Integrity CI automation:** `.github/workflows/data-integrity.yml` and `.github/workflows/sha256-idempotency-canary.yml` are active on the default branch and passing on `main`. These read-only checks enforce SQLite schema integrity and SHA-256 byte boundaries.
- **`[VERIFIED]` Review-only intake boundary:** `.github/ISSUE_TEMPLATE/ingest_lecture_playlist.yml` creates a maintainer review request only; it does not trigger automatic ingestion.
- **`[STAGED]` Harvest & Hugging Face automation:** `workflows_template/auto_harvest_and_hf_sync.yml` remains a **staged template**, not an active GitHub Actions workflow.
- **`[UNVERIFIED]` Remote Hugging Face sync:** live automated syncing to Hugging Face datasets remains unverified until end-to-end authenticated API runs succeed.
- **`[UNVERIFIED]` Browser / Cockpit production deployment:** repository artifacts and CI checks do not imply that external web hosting or mobile deployments are independently verified beyond local file inspection.

## Try it now (< 60 seconds)

Prerequisites: `python3` and the DuckDB CLI must already be available in `PATH`. Then run these three local verification commands; they do not upload data or require a hosted service:

```bash
# 1. Run DuckDB smoke queries against committed Parquet assets
./scripts/duckdb_smoke_test.sh

# 2. Verify physical SHA-256 hashes and row counts against dataset manifest
python3 scripts/verify_dataset_manifest.py

# 3. Verify fail-closed content identity decisions against adversarial fixtures
python3 scripts/content_identity_oracle.py --check-expected fixtures/content_identity_v1_adversarial.json
```

## Quick local query (DuckDB)

If you have DuckDB installed, query a local Parquet artifact directly:

```sql
SELECT exam_branch, COUNT(*) AS units_count
FROM 'data_lake/parquet/universal_study_lake.parquet'
GROUP BY exam_branch;
```

This command is intentionally local and reproducible; it does not depend on remote endpoints.

## Cockpit

A standalone HTML artifact is available at [`cockpit/index.html`](cockpit/index.html). It operates as a demo interface with explicit truth boundaries.

## Contributing

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/CONTENT_IDENTITY_V1.md`](docs/CONTENT_IDENTITY_V1.md). All pull requests require evidence-backed verification per [`.github/pull_request_template.md`](.github/pull_request_template.md).

For playlist/study-source proposals, use the repository issue template. Maintainers review submissions before ingestion. Do not upload copyrighted material unless redistribution rights are clear, and never include private learner data, harvested contacts, credentials, tokens, or secrets.

## Automation safety gate

The staged harvest/Hugging Face workflow must **not** be moved into `.github/workflows/` until all of the following are verified: YAML syntax, event filtering, least-privilege permissions, untrusted issue-body handling, dependency/version pinning, token/secret gating, dry-run behavior, rollback, and a bounded canary.

## Data-quality principles

1. **Reuse before rebuild:** use/fork/adapt proven wheels before inventing another system.
2. **Provenance first:** record source URL, title, publisher/teacher, retrieval date, and license/usage status when known.
3. **No synthetic-to-human promotion:** synthetic fixtures can test mechanics; they do not prove learner value.
4. **No private-data harvesting:** zero harvested contacts, credentials, or unsolicited learner outreach.
5. **Truth-correct docs:** claims about counts, deployments, syncs, or performance require reproducible evidence.

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE).