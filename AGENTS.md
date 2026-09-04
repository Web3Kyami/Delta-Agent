# Delta Builder Instructions

## Purpose

Delta is a trusted handoff layer for agent work. It lets Agent B inherit only the previous work that Delta deterministically finds valid, trustworthy, authorized, dependency-safe, and externally safe. It also preserves paid-job identity so interrupted jobs are reconciled before a replacement can spend again.

This file is the operational instruction set for builders. Stable product and architecture requirements live in `MASTER_PLAN.md`. Ordered work and exit gates live in `IMPLEMENTATION_PLAN.md`. Live progress and blockers live in `STATE.md`.

## Required reading order

Before editing application files, read:

1. `AGENTS.md`
2. `MASTER_PLAN.md`
3. `IMPLEMENTATION_PLAN.md`
4. `SECURITY.md`
5. `STATE.md`
6. `REFERENCES.md`
7. `DEMO_RUNBOOK.md`
8. `HANDOFF.md`
9. `README.md`

Then inspect all other applicable repository instructions, including nested `AGENTS.md`, tool-specific instructions, package metadata, existing architecture notes, and installed skills.

## Non-negotiable scope

Build the trusted-handoff contracts and deterministic pre-prompt gate before demo identity, LLM integration, or interface redesign. Follow the five migration phases in `IMPLEMENTATION_PLAN.md`.

The existing launch-package workflow is legacy implementation history, not the approved product direction. New scenarios are AI software-work handoff, Home repair handoff, and Paid research handoff. Do not implement them before their assigned phase.

Dependencies are declared by developers. Never ask an LLM to infer the graph or relevant inputs.

Required completed-submission integrations:

- Sibyl Memory as authoritative persistent work and revision state.
- Virtuals ACP for genuine service jobs, deliverables, and lifecycle reconciliation.
- Base for actual onchain payment or settlement in the demonstrated workflow.

Do not quietly make a required integration optional. If it is genuinely blocked, record the blocker and stop that phase.

## Product boundaries

Do not add any of the following unless the user explicitly changes scope:

- token or token launch
- custom escrow
- provider marketplace
- autonomous buyer
- generic workflow builder
- irreversible business actions such as transfers, trading, purchases, bookings, or withdrawals outside the required service payment and settlement path
- distributed scheduler
- background queue infrastructure
- extra application database containing a complete copy of Delta state
- custom blockchain contract without a demonstrated requirement
- broad analytics dashboard
- chat-first UI

Following mature caching and persistence techniques is intentional. Do not invent a new caching algorithm or weaken a baseline comparison to make Delta look novel.

## Workspace discipline

Before editing:

- Inspect the repository root and current branch.
- Read existing project instructions.
- Preserve unrelated work.
- Do not rename, move, or delete existing modules without a concrete need.
- If the correct project destination is genuinely ambiguous, ask before creating a new application tree.
- Prefer the existing stack when it satisfies the plan.
- Do not introduce a framework merely because it is familiar.

If the repository already contains work that conflicts with these documents, identify the conflict before changing it. Stable requirements in `MASTER_PLAN.md` win unless a later user instruction supersedes them.

## Build process

Work phase by phase from `IMPLEMENTATION_PLAN.md`.

For every phase:

1. State the narrow goal.
2. Implement only what is required for that phase.
3. Run the specified verification.
4. Record exact results in `STATE.md`.
5. Do not mark work complete because code exists. Mark it complete only after the exit gate passes.
6. Commit or checkpoint work in a reviewable state if the repository workflow permits it.

Do not batch several unverified phases and then claim completion at the end.

## Documentation workflow

`MASTER_PLAN.md` owns stable requirements and architecture decisions.

`IMPLEMENTATION_PLAN.md` owns order, dependencies, acceptance criteria, and exit gates.

`STATE.md` owns current truth: completed, verified, unverified, blocked, next action.

`SECURITY.md` owns trust boundaries and spending safety requirements.

`REFERENCES.md` owns official sources, checked versions, prior-work notes, and unresolved integration questions.

`DEMO_RUNBOOK.md` owns the judge path and required evidence.

`HANDOFF.md` owns concise continuation context.

`README.md` is public-facing and must distinguish implemented behavior from planned behavior.

Avoid copying the same specification into every file. Link to the owning document instead.

## Verification rules

Never fabricate:

- integration success
- test results
- provider availability
- ACP pricing
- estimated savings
- actual costs
- transaction hashes
- Base settlement
- Sibyl restoration
- process restart behavior
- job lifecycle states
- completion percentages

Use clearly labelled deterministic fixtures for local tests.

The completed submission must also exercise genuine Sibyl, ACP, and Base paths. A fixture cannot be presented as a live partner integration.

## No simulated success

Delta must never appear to perform real work while returning a hardcoded, placeholder, fixture, mocked, or predetermined success result. This applies to the engine, integrations, API routes, UI, demo, tests, and future features.

Any user-visible success state must be derived from the real execution path it claims to represent. UI state must come from the backend result and the underlying provider, chain, artifact, revision, or persistence state that supports the claim. An unavailable dependency, failed authentication, provider error, or unverifiable result must produce an honest loading, error, unavailable, blocked, ambiguous, or reconciliation state.

Fixtures and deterministic services are allowed for planned local tests only. Label them as fixtures or deterministic test services, keep their execution path distinct from live adapters, and never use them as evidence that a live integration works. Do not use a fixture or fallback to manufacture success when a real dependency is unavailable.

## End-to-end verification principle

A meaningful capability or phase is not complete because a UI exists or a happy-path function returns a value. Verify the complete path from user input through the UI or API handler, Delta engine, relevant adapter or service, real computation or state lookup, required persistence, returned result, and UI representation. Where practical, include one positive case and one negative or changed-input case. Validation must reject invalid input, revision planning must show `rerun` and `pending_dependency` where appropriate, and a `verified` or `reuse` state must be backed by the state it claims to inspect. If the real path cannot be proven, record it as unverified or blocked.

## Money and transaction rules

Do not spend money, fund a wallet, approve a paid job, create an onchain job, fund ACP escrow, release escrow, or broadcast any transaction without explicit approval covering the exact scope and budget.

Read-only discovery is allowed when it does not spend or broadcast.

Before a live paid phase, present:

- network and chain ID
- provider and offering
- expected service price or `unknown`
- maximum approved service spend
- expected transaction types
- whether gas is expected and whether its fiat value is known
- exact steps that will broadcast

If a provider quote exceeds the approved limit, stop before funding.

An interrupted or ambiguous paid action must be reconciled before retry. Never assume a failed command means no transaction or job was created.

Do not claim exactly-once execution. Delta provides reconciliation and conservative retry boundaries, not universal exactly-once semantics.

## Virtuals ACP operating rules

Use current official ACP documentation and the installed ACP skill when available.

For scripted or agent-driven authentication, current ACP CLI guidance requires the split configuration flow rather than a blocking interactive command. Follow the current CLI skill output and docs at implementation time.

Prefer machine-readable JSON output. Invoke CLI commands with argument arrays, not shell interpolation.

Persist ACP job identity and chain as soon as they are known. Before creating a replacement job, reconcile any existing nonterminal or ambiguous attempt using provider job history and current onchain state.

Do not rely on an event listener as the only source of truth across process restarts.

## Sibyl rules

Sibyl must be on the critical path for cross-run revision behavior.

Do not maintain a complete alternative execution database and mirror logs to Sibyl.

Large artifact bytes may live outside Sibyl. Sibyl must retain the durable artifact reference, work identity, signatures, job identity, state, and information required to decide whether work is reusable or requires reconciliation.

The final README must point judges directly to the critical Sibyl read and write paths.

## Security rules

Follow `SECURITY.md`.

At minimum:

- Never commit credentials.
- Never store private keys, OAuth tokens, API keys, seed phrases, or wallet secrets in Sibyl.
- Never include secrets in fixtures, screenshots, demo evidence, logs, or error payloads.
- Treat provider deliverables and metadata as untrusted data.
- Do not render untrusted HTML.
- Do not interpolate provider content into commands.
- Validate artifact paths and external URLs.
- Keep spending approvals separate from provider-provided data.

## UI expectations

The demonstration should make the engine behavior obvious rather than looking like a generic agent dashboard.

It must expose:

- Agent A's completed work and ended session
- Agent B's distinct receiving session
- candidate recall and pre-prompt gate decisions
- reuse, blocked, rerun, pending dependency, and reconciliation states
- a concrete reason beside each decision
- a Reuse Receipt
- estimated additional cost where known
- actual cost separately after execution
- provider and job status for paid work
- recovery and ambiguous-outcome states
- outputs or safe artifact references
- explicit execution and spending approval actions

Use real loading, error, blocked, and restart-recovery states. Never show fake progress.

## Required tests

At minimum verify:

- unchanged candidate work
- changed requirement or implementation constraint
- valid but unauthorized work
- blocked content never reaches Agent B context
- expired result
- implementation/version change
- failed step and retry
- real process restart and restoration
- isolation between two projects
- upstream rerun producing unchanged output
- interrupted known ACP job and reconciliation
- ambiguous ACP submission that cannot be safely retried
- spending approval limit enforcement
- artifact unavailable handling
- browser workspace and scenario isolation
- Reset Demo and stale generation handling

The baseline comparison must use correctly configured LangGraph caching and persistence. Its purpose is to keep product claims honest, not to force Delta to invent a new caching mechanism.

## Stop conditions

Stop the current phase and report a genuine blocker when any of these occurs:

- no safe or suitable live ACP offering can be verified for the planned demo task
- required live ACP authentication or signer setup is unavailable
- a transaction would exceed or fall outside approved budget or scope
- ACP state is ambiguous and cannot be reconciled safely
- the Base qualification path cannot be verified
- Sibyl cannot be made authoritative without duplicating state elsewhere
- a required API contract differs materially from the plan and proceeding would risk funds or corrupt persistent state
- repository destination is ambiguous and choosing one would risk unrelated work

Do not stop for routine implementation choices that can be resolved safely from these documents and official sources.
