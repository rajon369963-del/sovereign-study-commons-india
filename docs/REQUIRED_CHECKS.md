# Required checks and emergency rollback

`main` requires `Data integrity` and `SHA256 idempotency canary`, with the
branch up to date before merge. These are **job names**, not workflow titles.
Each name has exactly one producer; do not add a second bridge workflow with
the same names.

## Trigger coverage

Both workflows run on every pull request and every push to `main`, and support
manual dispatch. There are intentionally no workflow-level path filters.

| Changed path class | Required checks |
| --- | --- |
| Identity oracle, canonicalizer, provenance/hash repair scripts | Both |
| Content identity adversarial fixtures and any new fixtures | Both |
| SQLite, Parquet, manifest, and other `data_lake/**` artifacts | Both |
| Integrity, repair, idempotency scripts and dependency lock | Both |
| Any workflow or other CI configuration | Both |
| Documentation, README, UI, and all other paths | Both |

Documentation-only PRs intentionally run the full bounded checks. This trades
some runner time for an auditable guarantee that required checks are never
missing because of a path filter. Avoid commit-message CI skip directives;
GitHub leaves required checks pending when workflows are skipped. See
[GitHub's required-check guidance](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

`Data integrity` is an always-evaluated gate requiring **both** the data-lake
verification job (including identity adversaries and canonicalizer tests) and
the existing isolated FTS repair job to succeed. Failed, cancelled, or skipped
dependencies cannot produce a passing gate. All existing integrity assertions,
hash-locked dependencies, pinned actions, and the short-lived repair artifact
are retained. `SHA256 idempotency canary` runs the existing isolated full-hash
write-boundary proof. Neither workflow has secrets or permissions beyond
`contents: read`.

## Authorized emergency rollback

The live protection readback on 9 September 2026 had `enforce_admins=false`,
`allow_force_pushes=false`, and `allow_deletions=false`. This change does not
modify those settings. An authorized repository administrator therefore keeps
the existing emergency bypass; ordinary contributors remain subject to both
required checks. Read back current protection and the acting account's admin
permission before relying on this path, because repository rules can change.

Prefer a normal reviewed revert PR. If a broken CI configuration prevents an
urgent rollback, an authorized admin can use GitHub's admin override to merge
a minimal, reviewed revert of the CI change. Never force-push, delete `main`,
or broadly disable protection. Record the reason and commit, then verify
protection and required-check health again. A readback proves the configured
escape path; it is not evidence that an emergency bypass was exercised.

## Acceptance evidence

Before closing #13, retain links to a deliberately failing identity-only
canary PR run (required check red and merge blocked), its restored green run,
and a docs-only green run. Do not merge the canary. Confirm the final fix PR's
current head is green. Neither CI success nor this governance change proves
learner efficacy, data licensing, Pages deployment, or Hugging Face sync.
