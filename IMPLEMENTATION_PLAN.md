# Delta Implementation Plan

## Purpose

This document is the primary roadmap for Delta's approved migration from a launch-package revision demo to trusted handoff for agent work. Stable requirements belong in `MASTER_PLAN.md`, current truth in `STATE.md`, and security rules in `SECURITY.md`. Work proceeds one phase at a time. A phase is complete only after its exit gate passes.

## Product definition

Delta is a trusted handoff layer for agent work.

> Agents can inherit previous work without inheriting everything.

The product flow is:

1. Agent A completes work and Sibyl persists its result, provenance, artifacts, attempts, and external-job identity.
2. Agent A's session ends.
3. Agent B starts later with a distinct identity and session.
4. Delta recalls candidate work from Sibyl.
5. Delta deterministically evaluates validity, trust, authorization, dependencies, and external-job safety.
6. Blocked work stays outside Agent B's prompt and context. Approved work may cross the handoff.
7. Missing or invalid work executes through declared workflows.
8. Delta produces a Reuse Receipt explaining the decisions, evidence, and cost consequences.

Remembered work is not automatically trusted work. An LLM may consume approved context, but it never owns reuse eligibility, access control, dependency declarations, or paid-job safety decisions.

## Architectural direction

Preserve and extend the current Python engine:

- Keep developer-declared workflows, relevant inputs, dependencies, implementation identities, and freshness policies.
- Keep deterministic signatures, `WorkResult`, attempt lifecycle, `pending_dependency`, blocked states, artifact verification, and downstream reevaluation.
- Keep Sibyl authoritative for durable work, handoff, plan, receipt, attempt, and recovery state.
- Keep the ACP adapter, reconciliation boundaries, cumulative spending controls, and Base evidence handling.
- Add agent and session provenance, a minimal inheritance policy, candidate discovery, a deterministic handoff gate, approved-context construction, and Reuse Receipts.
- Add a provider-neutral LLM boundary only after the deterministic gate is verified.

The gate runs before prompt construction. A valid result may still be unauthorized. Blocked content must never be sent to an LLM with instructions to ignore it.

## Cross-phase rules and non-goals

- Work only on the current phase and record verified results in `STATE.md`.
- Preserve existing persisted records or migrate them explicitly. Legacy `WorkResult` records are not automatically authorized for cross-agent inheritance.
- Do not weaken ACP spending, settlement, reconciliation, artifact, or approval requirements.
- Do not claim that fixture, recorded, or historical evidence is a current live execution.
- Do not add a parallel database containing Delta's authoritative state or claim exactly-once execution.
- Do not add Sui, Walrus, Seal, a token, custom escrow, provider marketplace, workflow builder, distributed scheduler, or background queue.
- The public demo credential must never grant ACP, wallet, funding, settlement, or other valuable authority.
- Preserve honest loading, unavailable, blocked, ambiguous, stale, and error states.

## Scenario strategy

All scenarios use the same handoff, policy, persistence, execution, and receipt architecture.

### Primary: AI software-work handoff

Agent A completed several parts of a software task. Agent B takes over after a requirement or implementation constraint changes. The scenario must show valid and authorized work crossing the handoff, valid work blocked by policy, work that must rerun, downstream work waiting for a dependency, approved context passed without blocked content, and a final Reuse Receipt. It should show tangible software work without becoming a terminal or operations dashboard. Phase 2 will refine the exact work items from the Phase 1 engine contracts.

### General audience: Home repair handoff

A homeowner's repair task explains that existing, valid work can still be withheld. Candidate items may include a verified photo inventory, damage summary, repair scope, private note, and downstream insurer-facing summary.

### Paid path: Paid research handoff

A narrowly scoped paid research or content artifact demonstrates that verified ACP work can survive a later handoff and avoid an unnecessary replacement purchase. Final provider and offering selection follows current read-only discovery and cannot be invented or locked before verification.

## LLM rollout strategy

1. Complete the deterministic gate first.
2. Add one real provider with distinct Agent A and Agent B sessions.
3. Retain a clearly labelled deterministic runner for tests and public fallback.
4. Treat LLM output as untrusted until validated.
5. Defer a second provider until the one-provider path is stable.

## Public demo identity and isolation

- Provide one fixed public account with its email and password shown on the login page, no signup, and no user database.
- Show `Delta Dave`, support sign out, and describe the login as guided demo access rather than strong security.
- Use a signed, HttpOnly, SameSite session cookie and per-session CSRF token.
- Create a random server-controlled workspace for each browser session. Authentication identity and workspace identity remain separate.
- Scope state by workspace, scenario, and generation so judges and scenarios cannot share mutable state.
- Initialize a scenario through real engine and Sibyl paths when it is first opened.
- Reset only the selected workspace and scenario. Use safe scoped deletion if the official Sibyl API supports it, otherwise rotate generations and label old records archived.
- Reject stale generation, preview, gate, handoff, and receipt identities.

## Current live ACP limitation

The repository contains real external ACP and Base evidence, but it does not prove a complete Delta-managed path from paid execution through settlement and artifact verification to a reusable `WorkResult`, fresh-process recall, and authorized Agent B inheritance.

Known job `75773` remains open and unfunded after a provider requirement-shape failure. Reconcile it before considering a replacement. This limitation remains unchanged until Phase 5 produces new evidence.

## Phase 1: Handoff contracts and deterministic policy gate

### Objective

Establish the trusted-handoff model and deterministic pre-prompt gate while leaving the current UI and live adapters unchanged.

### Major files and subsystems

- `delta/core.py`, `delta/store.py`, and `delta/execute.py`
- A focused new handoff or policy module
- Core, execution, and Sibyl tests

### Required work

- Add `AgentPrincipal` with stable agent, session, and provider identity.
- Add source-agent and source-session provenance to new completed work.
- Add a minimal `InheritancePolicy`: project scope, recipient scope, optional agent allowlist, provider rule, optional provider allowlist, external-exposure rule, and developer-declared work category.
- Add candidate discovery that distinguishes no work, invalid work, untrusted work, unauthorized work, and reusable work.
- Add separate validity, trust, authorization, dependency, and external-job verdicts.
- Add `HandoffRecord`, `ReuseReceipt`, and per-item receipt entries.
- Add `HandoffGate` and an `ApprovedContext` type that can contain only approved work.
- Persist versioned handoff and receipt records in Sibyl.
- Store technical evidence as references and safe metadata, not copied untrusted bodies.

### Required tests

- Valid authorized work reuses; valid unauthorized work blocks.
- Authorized stale or mismatched work reruns.
- Missing or invalid artifacts prevent reuse.
- Same-provider and provider-allowlist rules work.
- Project boundaries prevent cross-reuse.
- Legacy work is not automatically authorized.
- Receipt counts and reasons match gate decisions.
- Blocked content is absent from `ApprovedContext`.
- A fresh process produces the same gate result.
- Existing ACP, artifact, spending, execution, and baseline tests still pass.

### Acceptance criteria

- Every candidate has separate inspectable verdicts.
- Validity and authorization remain independent.
- Future prompt construction accepts only approved context.
- Gate decisions and receipts persist through Sibyl.
- Existing backend behavior remains intact.

### Explicit non-goals

No login, replacement scenarios, LLM calls, UI redesign, live ACP/Base action, second provider, or general IAM system.

### Exit gate

Process A persists Agent A work and exits. Process B starts with a distinct Agent B session, recalls the work from Sibyl, produces at least one `reuse` and one `blocked` result, and constructs approved context that provably excludes blocked content.

## Phase 2: Demo identity, workspace and scenario isolation, scenarios, and reset

### Objective

Build trustworthy demo state and the three shared-architecture scenarios before real LLM execution or major visual work.

### Major files and subsystems

- `delta/demo.py`, `delta/fixtures.py`, `delta/store.py`, and `delta/web.py`
- New scenario, session, and reset modules
- Web and integration tests

### Required work

- Add fixed public login, Delta Dave identity, signed session, sign out, and per-session CSRF.
- Generate a server-controlled workspace per browser.
- Add the AI software-work, home repair, and paid research scenario registry.
- Scope state by workspace, scenario, and generation.
- Initialize each scenario on first open through the engine and Sibyl.
- Refine AI software-work items against Phase 1 contracts.
- Add input-sensitive, clearly labelled deterministic scenario services.
- Add Reset Demo with a project-scoped manifest.
- Verify official Sibyl deletion behavior and use deletion or generation rotation accordingly.
- Reject stale identities and keep live paid actions inaccessible to public sessions.

### Required tests

- Login, failed login, sign out, and session expiry
- Public denial of live actions
- Two browsers receive separate workspaces and cannot cross-read or cross-reuse
- Three scenarios remain isolated
- Reset affects only one workspace and scenario
- Concurrent resets are serialized or rejected safely
- Old generations and plans return stale-state responses
- A fresh process restores the active workspace and scenario from Sibyl

### Acceptance criteria

Concurrent judges cannot see or mutate one another's work. Reset semantics are exact and honest. All scenarios use the same gate and receipt model. The public account has no path to spending authority.

### Explicit non-goals

No real LLM, second provider, major landing redesign, live paid execution, user database, signup, or distributed multi-writer guarantee.

### Exit gate

Login, workspace isolation, scenario isolation, reset, stale-generation, concurrent-judge, no-spend, and fresh-process tests pass through the real Sibyl path.

## Phase 3: Agent sessions, approved-context LLM execution, and Reuse Receipts

### Objective

Add one real LLM provider with distinct Agent A and Agent B sessions, then connect approved context, missing-work execution, and receipts.

### Major files and subsystems

- New provider-neutral `delta/agents` boundary
- Handoff gate and context assembly
- `delta/execute.py`, scenario definitions, `delta/web.py`, receipt serialization, and tests

### Required work

- Define an `AgentRunner` interface and persist distinct sessions.
- Send only `ApprovedContext` to the provider.
- Validate and persist outputs without treating them as trusted instructions.
- Record provider, model, session, usage, and cost only when supported by the response.
- Execute missing work through declared workflows.
- Finalize the Reuse Receipt from actual decisions and outcomes.
- Keep deterministic and real-provider modes separate and preserve unknown cost as unknown.

### Required tests

- Distinct Agent A and Agent B session identities
- Sentinel blocked values absent from prompts, messages, tool arguments, logs, traces, and unauthorized browser payloads
- Approved work reaches Agent B and affects its result
- Failed LLM output never becomes reusable
- Changed input or policy makes a gate result stale
- Receipt entries match persisted attempts
- Fixture and real modes cannot be confused

### Acceptance criteria

One provider supports separate sessions. Blocked work is excluded before provider request construction. Missing work uses the engine, not scenario shortcuts. The receipt is reproducible from persisted state.

### Explicit non-goals

No second provider, broad policy language, public paid execution, or major visual redesign before contracts stabilize.

### Exit gate

An end-to-end test and inspectable provider request prove that Agent B received approved work, never received blocked work, executed only missing work, and produced a receipt consistent with Sibyl.

## Phase 4: Application UX and landing-page redesign

### Objective

Replace the revision-centric launch-package experience with the handoff journey and a deliberate Delta-specific neo-brutalist landing story.

### Major files and subsystems

- Templates, application and landing JavaScript, CSS, static assets, routes, and web tests

### Required work

- Center the app on scenario selection, Agent A work, session end, Agent B start, gate decisions, execution, result, and receipt.
- Put work, consequences, and decisions before infrastructure.
- Place signatures, Sibyl identity, policy, provider, ACP job, Base, and cost evidence behind progressive disclosure.
- Render every state from backend data.
- Build the landing story around Agent A, the boundary, Agent B, approved work crossing, blocked work stopping, and the receipt.
- Use structural rules, offsets, stamps, and high-contrast typography to explain causality.
- Keep the application quieter than marketing and use a vertical sequence on mobile.

### Required tests and review

- Complete fixture handoff journey
- Login, sign out, reset, and stale-session behavior
- Loading, empty, blocked, unauthorized, pending, ambiguous, recovery, reset, and failure states
- Keyboard operation, focus, announcements, contrast, reduced motion, and touch targets
- Responsive inspection at 1440, 1024, 768, and 390 CSS pixels
- No overflow or unsupported savings, provider, transaction, or security claims
- Evidence surfaces never expose blocked content

### Acceptance criteria

A first-time visitor can explain what crossed the handoff and why. Navigation serves the product journey. Approved work visibly crosses and blocked work stops. Every displayed success, cost, and evidence item comes from backend state.

### Explicit non-goals

No gate changes for visual convenience, weakened persistence or spending controls, decorative terminal, node graph, metric wall, random bright blocks, generic gradients, glass-card system, or live claim based on recorded evidence.

### Exit gate

The full handoff experience passes functional, accessibility, responsive, and evidence-integrity review across all scenarios.

## Phase 5: Operator-gated live ACP/Base proof and submission hardening

### Objective

Close the live paid path safely and connect genuine evidence to a later authorized handoff. Preserve the exact blocker if it cannot be verified.

### Major files and subsystems

- `delta/providers/acp.py`, `delta/artifacts.py`, operator tooling, live finalization, receipt evidence, demo runbook, and submission tests

### Preconditions

- Phases 1 through 4 passed.
- Existing nonterminal or ambiguous ACP work is reconciled.
- Provider, offering, requirements, deliverable, SLA, price, and Base support are refreshed through read-only discovery.
- The user explicitly approved the chain, provider, offering, transaction types, service cap, and action scope.
- Public demo sessions cannot satisfy operator authorization.

### Required work

- Run one suitable paid research or content job through Delta's real adapter.
- Persist intent and job identity at the earliest safe boundary.
- Reconcile before retrying an ambiguous action.
- Verify deliverable shape, artifact, provider hash, settlement receipt, and Base evidence.
- Create reusable work only through `ACPAdapter.finalize_completed_work` or its verified successor.
- Restore the completed work in a fresh process and evaluate it for Agent B.
- Purchase only genuinely missing work under a new explicit approval.
- Add real, sanitized evidence to the receipt and complete secret, version, claim, and evidence audits.

### Required tests and evidence

- Public-session denial for every live action
- Quote-over-cap, wrong-chain, wrong-provider, expired-approval, and cumulative-cap rejection
- Ambiguous create, fund, and completion reconciliation
- Artifact unavailable and hash mismatch
- Fixture or recorded evidence cannot create reusable live work
- Fresh-process paid-work recall
- Unauthorized paid work stays out of Agent B context
- Receipt separates estimate, quote, actual service cost, gas, and hypothetical avoided cost

### Acceptance criteria

A real paid ACP result is settled, verified, persisted in Sibyl, recalled by a fresh process, evaluated for a different receiving agent, and reused only when authorized. Only missing work is eligible for purchase. If the live path is blocked, the product reports that honestly.

### Explicit non-goals

No autonomous buyer, public spending control, unrelated Base transaction, custom contract, custom escrow, exactly-once claim, or second LLM provider without separate approval.

### Exit gate

The paid-to-reusable-to-authorized-handoff path is verified end to end with explicit approval and reproducible evidence, or Phase 5 is recorded as blocked and public claims remain limited to proven behavior.

## Global verification matrix

Before submission verify unchanged and changed work, expired work, valid but unauthorized work, unavailable artifacts, upstream rerun with unchanged output, pending dependencies, failed work and retry, fresh-process restoration, project/scenario/browser isolation, reset and stale generations, policy leakage prevention, ACP reconciliation, ambiguous-outcome blocking, spending limits, honest evidence classification, and responsive accessible UI behavior.

## Stop conditions

Stop the active phase if Sibyl cannot remain authoritative, safe reset semantics cannot be achieved, blocked content cannot be proven absent from provider requests, a provider contract risks funds or state, ACP identity remains ambiguous, a transaction is outside approval, no suitable paid offering exists, Base evidence cannot be verified, or public demo access can reach valuable authority.
