# ⚡ Sovereign Study Commons India (सार्वजनिक अध्ययन महा-ज्ञानकोश)

> भारत के छात्रों के लिए एक public, open study-data commons. Repository truth is preferred over intended future state.

## Live truth status — verified 8 Sep 2026

- **GitHub repository:** public and readable.
- **Dataset artifacts:** repository contains study-data artifacts; counts and branch coverage should be independently recomputed from the files before being quoted externally.
- **Community submissions:** an issue-template path exists for proposing sources. Submission does **not** mean automatic ingestion; maintainers must review legality, provenance, duplication, schema fit and quality.
- **Automation:** `workflows_template/auto_harvest_and_hf_sync.yml` is a **staged template**, not an active GitHub Actions workflow. There is currently no `.github/workflows/` directory on the default branch.
- **Hugging Face:** the staged template contains optional HF sync logic, but this README does **not** claim that a live dataset sync has been independently verified.
- **Deployment:** repository artifacts are not, by themselves, proof that GitHub Pages or any other browser deployment works end-to-end.

## Quick local query

If you have DuckDB installed, query a local Parquet artifact directly:

```sql
SELECT exam_branch, COUNT(*) AS units_count
FROM 'data_lake/parquet/universal_study_lake.parquet'
GROUP BY exam_branch;
```

This command is intentionally local/reproducible; it does not imply a verified remote HTTP endpoint.

## Cockpit

A standalone HTML artifact is available at [`cockpit/index.html`](cockpit/index.html). Treat it as source until its clean-browser/mobile deployment is independently verified.

## Contributing

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md). Prefer small evidence-backed fixes to documentation, provenance, validation, examples or metadata before adding systems.

For playlist/study-source proposals, use the repository issue template. Maintainers review submissions before ingestion. Do not upload copyrighted material unless redistribution rights are clear, and never include private learner data, harvested contacts, credentials, tokens or secrets.

## Automation safety gate

The staged harvest/Hugging Face workflow must **not** be copied into `.github/workflows/` until all of these are verified: YAML syntax, event filtering, least-privilege permissions, untrusted issue-body handling, dependency/version pinning, token/secret gating, dry-run behavior, rollback, and a bounded canary. In particular, a staged workflow is not a live workflow.

## Data-quality principles

1. **Reuse before rebuild:** use/fork/adapt proven wheels before inventing another system.
2. **Provenance first:** record source URL, title, publisher/teacher, retrieval date and license/usage status when known.
3. **No synthetic-to-human promotion:** synthetic fixtures can test mechanics; they do not prove learner value.
4. **No private-data harvesting:** no harvested contacts, credentials or unsolicited learner outreach.
5. **Truth-correct docs:** claims about counts, deployments, syncs or performance require reproducible evidence.

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE).