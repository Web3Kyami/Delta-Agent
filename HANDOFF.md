# Delta Handoff

## Current position

Phase 4 of the trusted-handoff migration is implemented and locally verified. Phase 5 hardening is present but blocked at the required live boundary. The Phase 1 and 2 checkpoint is `74ffd0e`, followed by the Phase 3 checkpoint and the Phase 4 checkpoint. Verified commands and results are recorded in `STATE.md`.

What exists now:

- `delta/handoff.py` owns the deterministic pre-prompt gate, candidate discovery, five separate verdicts, `ApprovedContext`, `HandoffRecord`, and `ReuseReceipt`.
- `delta/core.py` carries agent/session provenance and developer-declared work metadata.
- `delta/store.py` persists Phase 1 records and performs exact-scope Sibyl entity deletion for reset. HOT heads are overwritten because Sibyl has no state-delete operation. The append-only journal is retained audit history.
- `delta/session.py` owns signed public demo sessions, Delta Dave identity, expiry, and per-session CSRF.
- `delta/scenarios.py` defines the AI software-work, Home repair, and Paid research scenarios using one shared deterministic engine shape.
- `delta/web.py` exposes authenticated scenario listing, first-open initialization, handoff evaluation, reset, and public no-spend boundaries.
- `delta/agents` owns the provider-neutral AgentRunner contract, deterministic fixture runner, OpenAI Responses adapter, agent-session/run records, approved-context request construction, and post-execution receipt finalization.
- `delta/templates/scenario-list.html` and `delta/templates/scenario-detail.html` provide the handoff-first application journey. `delta/static/scenario.css` and `delta/static/scenario.js` provide the responsive, accessible scenario interface.
- The landing page now leads with the Agent A to Delta to Agent B boundary and the Reuse Receipt. Legacy launch-package routes remain available but are no longer the primary product path.
- `.venv/bin/python -m pytest -rA` returned `141 passed, 19 subtests passed`.
- `scripts/live_acp_validation.py status` confirmed the known ACP job `75773` remains `active`, open, and unfunded on Base `8453`.
- `scripts/live_acp_validation.py reconcile` is now available as a read-only provider-history reconciliation path. It must run successfully before a replacement is considered.
- With explicit approval, reconciliation ran and confirmed job `75773` is still `open` with no funding, transaction hashes, or deliverable. The approved corrective requirements message returned `success: true`; a follow-up history read still reports `open`.
- The linked Virtuals agent-profile ACP tab is empty for jobs, offerings, resources, and subscriptions. Treat this as a UI visibility mismatch, not cancellation. The ACP history endpoint remains authoritative for `75773`; do not create a replacement until the open attempt is resolved.
- A read-only ACP marketplace browse failed locally with `KeyRevoked` from the OS secret store before any marketplace request. Reauthenticate the ACP CLI using the split configure flow, then refresh offering and job history. Do not work around this by adding offerings to the Delta agent profile.
- Authentication was restored and the live Base browse succeeds, but Aaga and its approved `content_generation` offering are absent from current results. Other providers are discoverable, but switching would require new approval. Phase 5 is blocked on the approved provider becoming available.
- `.venv/bin/python scripts/phase2_mutation_review.py` caught all 8 Phase 2 guard-removal mutations.

What remains unverified: an external OpenAI call and live ACP/Base action for the new handoff path. No external model call was made because credentials and API-spend approval were not available. Phase 5 owns live proof and submission hardening.

## Next task: unblock Phase 5

Continue Phase 5 from `IMPLEMENTATION_PLAN.md` only after the live preconditions are satisfied:

- operator-gated live ACP/Base proof and submission hardening
- preserve the Phase 4 scenario journey and no-spend public boundary
- reconcile any known or ambiguous ACP attempt before considering a replacement
- refresh the provider and offering through read-only discovery
- obtain explicit approval for Base `8453`, the selected provider and offering, the allowed step, transaction actions, service cap, and expiry
- Current approved envelope: one Aaga `content_generation` step, up to `0.01 USDC` service spend, up to `$0.05` estimated gas, expiring `2026-09-04T05:00:00Z`. The operator script requires a supplied gas estimate at or below the ceiling before any transaction action.

Do not claim live provider, payment, settlement, or reusable-work success until the Phase 5 exit gate passes. The public demo remains no-spend.

## Phase 2 proof and boundaries

- Two session cookies receive different workspace identities and composite project scopes.
- The three scenarios initialize through `DeltaEngine` and `SibylStore.local` and remain isolated.
- Handoff responses show reuse, blocked, rerun, and pending-dependency decisions without exposing the private canary.
- Scenario state withholds private and private-derived outputs from the browser; only browser-safe fixture outputs are serialized.
- Reset deletes exact-scope work, attempt, plan, handoff, and receipt entities, clears active heads, issues a new generation, and initializes fresh Agent A work. Journal history is retained and labeled as such.
- The old signed generation is tombstoned in Sibyl and rejected on later state or reset requests.
- Old generations are rejected with `stale_generation` when supplied to handoff or reset.
- Public sessions receive an unauthenticated or blocked response for live approval actions. No ACP job, wallet action, settlement, or Base transaction was run.
- Phase 3 end-to-end tests prove Agent B receives only approved context, missing work runs through the declared engine, failed provider output is not persisted as reusable work, and finalized receipt entries link executed work to Sibyl attempts.

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
