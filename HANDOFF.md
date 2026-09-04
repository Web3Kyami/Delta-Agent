# Delta Handoff

## Current position

Phase 2 of the trusted-handoff migration is implemented and has passed its exit gate. The checkpoint is committed as `74ffd0e` on `main`. Verified commands and results are recorded in `STATE.md` under "Phase 2 verified results (2026-09-04)".

What exists now:

- `delta/handoff.py` owns the deterministic pre-prompt gate, candidate discovery, five separate verdicts, `ApprovedContext`, `HandoffRecord`, and `ReuseReceipt`.
- `delta/core.py` carries agent/session provenance and developer-declared work metadata.
- `delta/store.py` persists Phase 1 records and performs exact-scope Sibyl entity deletion for reset. HOT heads are overwritten because Sibyl has no state-delete operation. The append-only journal is retained audit history.
- `delta/session.py` owns signed public demo sessions, Delta Dave identity, expiry, and per-session CSRF.
- `delta/scenarios.py` defines the AI software-work, Home repair, and Paid research scenarios using one shared deterministic engine shape.
- `delta/web.py` exposes authenticated scenario listing, first-open initialization, handoff evaluation, reset, and public no-spend boundaries.
- `.venv/bin/python -m pytest -q` returned `128 passed`.
- `.venv/bin/python scripts/phase2_mutation_review.py` caught all 8 Phase 2 guard-removal mutations.

What still does not exist: a real LLM call, live ACP/Base action for the new handoff path, or the Phase 4 visual redesign. The existing launch-package UI remains legacy until those phases.

## Next task: Phase 3

Implement Phase 3 from `IMPLEMENTATION_PLAN.md` only:

- one real LLM provider with distinct Agent A and Agent B sessions
- approved-context construction before provider requests
- prompt, tool, log, trace, and browser leakage tests
- missing-work execution through the declared engine
- persisted Reuse Receipt derived from actual decisions

Do not begin Phase 4 or Phase 5 until the Phase 3 exit gate passes.

## Phase 2 proof and boundaries

- Two session cookies receive different workspace identities and composite project scopes.
- The three scenarios initialize through `DeltaEngine` and `SibylStore.local` and remain isolated.
- Handoff responses show reuse, blocked, rerun, and pending-dependency decisions without exposing the private canary.
- Scenario state withholds private and private-derived outputs from the browser; only browser-safe fixture outputs are serialized.
- Reset deletes exact-scope work, attempt, plan, handoff, and receipt entities, clears active heads, issues a new generation, and initializes fresh Agent A work. Journal history is retained and labeled as such.
- The old signed generation is tombstoned in Sibyl and rejected on later state or reset requests.
- Old generations are rejected with `stale_generation` when supplied to handoff or reset.
- Public sessions receive an unauthenticated or blocked response for live approval actions. No ACP job, wallet action, settlement, or Base transaction was run.

## Do not begin early

During Phase 3, do not:

- redesign the application or landing page
- add a second LLM provider
- run a live ACP job or Base transaction
- authorize legacy `WorkResult` records automatically
- weaken artifact, reconciliation, spending, or settlement safeguards
- claim any live provider, payment, or settlement success

## Approved phases and scenarios

1. Phase 1: handoff contracts and deterministic policy gate, complete
2. Phase 2: demo identity, workspace and scenario isolation, scenarios, and reset, complete
3. Phase 3: agent sessions, approved-context LLM execution, and Reuse Receipts
4. Phase 4: application UX and landing-page redesign
5. Phase 5: operator-gated live ACP/Base proof and submission hardening

Scenarios:

- AI software-work handoff, primary
- Home repair handoff, general audience
- Paid research handoff, ACP/Base and economic reuse

## Existing backend to preserve

- Small Python workflow and revision engine
- Developer-declared dependencies
- Deterministic input and output signatures
- Freshness and implementation identity
- `WorkResult`, attempts, blocked states, and `pending_dependency`
- Runtime downstream reevaluation
- Sibyl authoritative persistence
- Artifact integrity and availability checks
- ACP job identity and conservative reconciliation
- Spending approval and cumulative caps
- Base transaction evidence
- Honest fixture, recorded, and live distinctions
- Fair LangGraph baseline
- Phase 1 handoff contracts, verdicts, approved-context boundary, and receipts

## Current live limitation

The repository does not prove a complete Delta-managed paid execution to settled, verified, reusable `WorkResult` path. The recorded Aaga job `75656` remains external evidence. Job `75773` remains open and unfunded after a requirement-shape failure and must be reconciled before any replacement is considered.

No live job creation, funding, completion, settlement, wallet transfer, or other broadcast is authorized by this handoff document. Obtain explicit approval for the exact network, provider, offering, action scope, transaction types, and budget before Phase 5 spending.

## Reading order

1. `AGENTS.md`
2. `MASTER_PLAN.md`
3. `IMPLEMENTATION_PLAN.md`
4. `SECURITY.md`
5. `STATE.md`
6. `REFERENCES.md`
7. `DEMO_RUNBOOK.md`
8. `HANDOFF.md`
9. `README.md`

Use `IMPLEMENTATION_PLAN.md` as the authoritative phase roadmap and `STATE.md` as the source of current verified truth.
