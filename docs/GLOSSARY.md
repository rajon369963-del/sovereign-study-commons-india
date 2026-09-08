# Sovereign Study Commons Discoverability Glossary

This document maps all repository discoverability terms and GitHub topics directly to verified code, schemas, and physical assets on `main`.

## Retained GitHub Topics

Each retained topic is grounded in an existing, reproducible file or capability:

| Topic | Verified Repository Evidence | Concrete Use Case / File Pointer |
| :--- | :--- | :--- |
| `gate-ee` | `data_lake/parquet/gate_ee_5k_questions.parquet` | 5,000 Electrical Engineering questions and Socratic units in `universal_study_lake.sqlite`. |
| `upsc` | `data_lake/parquet/upsc_polity_5k_videos.parquet` | 5,000 Indian Polity video metadata records for UPSC CSE preparation. |
| `neet` | `data_lake/sqlite/universal_study_lake.sqlite` | Biology and Physics Socratic mastery units classified under `NEET_UG`. |
| `parquet` | `data_lake/parquet/` directory | Columnar datasets queryable via DuckDB and PyArrow. |
| `duckdb` | `scripts/duckdb_smoke_test.sh` | Deterministic CLI smoke tests executing analytical aggregation in < 1 second. |
| `sqlite` | `data_lake/sqlite/universal_study_lake.sqlite` | Embedded database with FTS5 full-text search and canonical hash verification. |
| `study-data` | `data_lake/dataset_manifest.json` | Machine-readable manifest tracking file byte sizes, SHA-256 hashes, and schemas. |
| `india-education` | `README.md`, `cockpit/index.html` | Public educational study commons tailored for national examinations in India. |

---

## Terms on HOLD (Excluded from Topics)

The following terms were audited and intentionally excluded from public topics to prevent misleading discovery:

- **`open-data` (HOLD)**: Excluded because community examination banks (`gate_ee_5k_questions.parquet`, `upsc_polity_5k_videos.parquet`) have license status `UNKNOWN/REVIEW_REQUIRED` pending provenance verification.
- **`knowledge-lake` (HOLD)**: Excluded until automated semantic ingestion and distributed vector indexing are fully operational on default branch.
- **`ai-tutor` / `edtech` (REJECTED)**: Generic buzzwords that do not reflect the current deterministic study-commons data repository.
