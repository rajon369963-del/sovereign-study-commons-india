---
name: sovereign-full-yolo-factory
description: "Use when executing bounded MIGL/AIR10 repository or workspace tasks that already have a verified task ID, source lineage, safe permissions, and an explicit acceptance court."
---

# Sovereign Full YOLO Factory Engine

## Operating boundary
This skill coordinates existing verified wheels. It does not turn local inventory, private archives, model output, hashes, queue completion, or generated prose into proof of correctness.

Use this sequence:
`TASK_ID -> CURRENT_PHYSICAL_STATE -> EXISTING_WHEEL -> SMALLEST_SAFE_DELTA -> TEST -> PHYSICAL_READBACK -> RECEIPT -> NEXT_OWNER`

## Truth rules
- Treat transcript stores, local databases, tool inventories, Drive mounts, account pools, and workstation paths as `LOCAL_ONLY` unless the current runtime physically reads them through an authorized surface.
- Do not claim a corpus size, tool count, competitor count, verification result, deployment result, or learner effect without a current evidence receipt.
- Generated synthesis is `SYNTHESIZED_UNVERIFIED` until an independent verifier actually runs and records command/action, input artifact, assertion, exit/result state, evidence artifact/hash, timestamp, and verifier identity.
- A SHA-256 digest proves byte identity only. It does not prove factual, semantic, causal, pedagogical, or physical correctness.
- Never use multi-account routing to bypass quotas, rate limits, provider terms, permissions, or review gates. Authorized accounts may only be used within their own legitimate limits and permissions.
- Do not auto-commit generated artifacts to protected `main`. Use a bounded branch/PR path and the repository's current required checks unless an explicitly documented emergency rollback requires otherwise.
- Founder busywork stays zero unless a genuinely external owner-consent or irreversible publishing gate exists.

## Completion contract
A task is complete only when the requested effect is physically read back from the destination surface and the receipt records before/after state, tests, rollback, and next owner. If the requested effect is blocked, record the exact gate and work-steal another independent safe atom instead of inventing success.