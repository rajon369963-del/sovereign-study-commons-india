---
language:
- hi
- en
license: other
task_categories:
- question-answering
- multiple-choice
- text-retrieval
tags:
- education
- stem
- upsc
- gate
- neet
- engineering
- medical
- civil-services
- duckdb
- parquet
- india
size_categories:
- 10K<n<100K
pretty_name: Sovereign Study Commons India (सार्वजनिक अध्ययन महा-ज्ञानकोश)
---

# Dataset Card for Sovereign Study Commons India

## Dataset Summary
**Sovereign Study Commons India** is a public, open-source, multi-branch educational dataset and knowledge lake designed to democratize exam preparation across India. It aggregates verified PYQs, lecture transcripts, exact teacher timestamp spans, Socratic misconception traps, and step-by-step derivations across:
- **GATE Electrical Engineering (EE)**
- **UPSC Civil Services (Polity & Constitution)**
- **NEET-UG (Biology & Chemistry)**
- **State AE/JE & RRB/SSC JE**

The dataset is stored in compressed **ZSTD Parquet** format and optimized for sub-millisecond HTTP range queries via **DuckDB**, eliminating the need for students to download gigabytes of raw data.

## Supported Tasks and Leaderboards
- `question-answering`: Socratic multi-stage evaluation.
- `multiple-choice`: High-speed exam drill and misconception diagnostic.
- `text-retrieval`: Teacher lecture quote and timestamp verification.

## Languages
The dataset contains bilingual text in **English** and **Hindi (Devanagari)**, reflecting the actual pedagogical style of leading Indian educators.

## Dataset Structure

### Data Instances
A sample instance from the dataset:
```json
{
  "unit_id": "GATE-EE-LF-001",
  "exam_branch": "GATE_EE",
  "subject": "Power Systems",
  "topic": "Gauss-Seidel vs Newton-Raphson Load Flow Analysis",
  "teacher": "NPTEL / Gate Academy",
  "video_id": "PLbRMhDVUMngcf7v2sC0V8BSt9fE3_8YVf",
  "timestamp_span": "180s-420s",
  "exact_quote": "In Gauss-Seidel method, the number of iterations increases with the number of buses, whereas in Newton-Raphson it remains virtually constant.",
  "question_text": "In load flow studies of a power system, why is the Newton-Raphson method preferred over the Gauss-Seidel method for large systems?",
  "correct_opt": "B",
  "explanation": "Newton-Raphson exhibits quadratic convergence (independent of bus count), requiring only 3-5 iterations, whereas Gauss-Seidel exhibits linear convergence.",
  "sha256_hash": "b2f6c91a...71e",
  "drive_url": "https://drive.google.com/open?id=drive_gate-ee-lf-001"
}
```

## How to Use with DuckDB
Query remote or local Parquet files in zero seconds:

```python
import duckdb

con = duckdb.connect()
df = con.execute("""
    SELECT exam_branch, topic, teacher, timestamp_span 
    FROM 'data/universal_study_lake.parquet'
    LIMIT 10
""").df()
print(df)
```

## Maintenance & Ingestion
The dataset is continuously expanded via GitHub Issues and GitHub Actions using the Zero Duplicate Invariant (SHA-256 validation).

## Licensing
Repository code and maintainer-owned documentation may be covered by the repository `LICENSE`, but bundled dataset assets have **per-asset rights status** recorded in `data_lake/dataset_manifest.json`. Assets marked `UNKNOWN/REVIEW_REQUIRED` remain unresolved and are **not** promoted by this Dataset Card to a categorical permissive license. The `license: other` metadata above is therefore a bounded claim-parity marker for the current mixed/partly unresolved release surface, not a legal determination or redistribution authorization. Per-asset rights may be promoted only when independent evidence updates the manifest.
