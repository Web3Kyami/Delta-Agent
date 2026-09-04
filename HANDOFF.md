# Delta Handoff

## Current position

The trusted-handoff migration plan is approved and recorded in the governing documents.

Delta is now defined as a trusted handoff layer for agent work:

> Agents can inherit previous work without inheriting everything.

The approved flow is Agent A completion, Sibyl persistence, Agent A session end, later Agent B session, deterministic validity/trust/authorization/dependency/external-job gating, approved-context construction, missing-work execution, and a Reuse Receipt.

Documentation migration is complete. Trusted-handoff product implementation has not begun. The current code and UI still implement the legacy launch-package revision demonstration.

## Next task

Implement Phase 1 only: handoff contracts and the deterministic policy gate.

Phase 1 must add and verify:

- agent and session identity
- source provenance for new work
- a minimal inheritance policy
- candidate-work discovery
- separate validity, trust, authorization, dependency, and external-job verdicts
- deterministic gate decisions
- an approved-context type that cannot contain blocked work
- handoff and Reuse Receipt schemas
- Sibyl persistence for the new records
- a fresh-process test proving blocked content never reaches Agent B's approved context

Phase 1 must pass its exit gate before Phase 2 begins.

## Do not begin early

During Phase 1, do not:

- redesign the application or landing page
- add login, workspace isolation, Reset Demo, or replacement scenarios
- call an LLM
- add a second LLM provider
- run a live ACP job or Base transaction
- alter the public demo to claim handoff functionality exists
- authorize legacy `WorkResult` records automatically
- weaken artifact, reconciliation, spending, or settlement safeguards

## Approved later phases

1. Phase 1: handoff contracts and deterministic policy gate
2. Phase 2: demo identity, workspace and scenario isolation, scenarios, and reset
3. Phase 3: agent sessions, approved-context LLM execution, and Reuse Receipts
4. Phase 4: application UX and landing-page redesign
5. Phase 5: operator-gated live ACP/Base proof and submission hardening

Approved scenarios:

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
