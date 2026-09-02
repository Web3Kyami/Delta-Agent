# Delta Master Plan

## Document ownership

This document owns Delta's stable product requirements, architecture, major design decisions, and minimum complete submission definition.

Implementation sequencing belongs in `IMPLEMENTATION_PLAN.md`. Live progress belongs in `STATE.md`. Security requirements belong in `SECURITY.md`. Current sources and unresolved API questions belong in `REFERENCES.md`.

## Status vocabulary

- **Verified fact**: confirmed from an official source as of the date recorded in `REFERENCES.md`.
- **Design decision**: a chosen approach for Delta.
- **Assumption to test**: plausible but not yet verified in the actual implementation environment.
- **Blocker**: something that prevents a required phase from completing safely.

## Product purpose

Delta helps developers revise paid agent work without treating every revision as a brand-new job.

A developer should be able to ask:

- Which completed outputs are still usable?
- Which paid jobs need to run again?
- Why is each step being reused or rerun?
- Which downstream decisions must wait for an upstream result?
- What additional service cost is expected before execution?
- What has already been spent?
- If a process died, is there an existing paid job that must be reconciled before a replacement is created?

Delta is not a new caching algorithm. Caching, selective reruns, checkpointing, and restart recovery already exist in mature workflow systems. Delta's product contribution is an integrated developer experience around revision planning, durable paid-work records, and continuity of external agent jobs.

## Intended users

Primary users are developers building workflows that call paid external agents or services where rerunning work has monetary cost and a remote lifecycle.

The first concrete ecosystem is Virtuals ACP because it exposes explicit provider offerings, job identities, budgets, escrow funding, deliverables, and terminal lifecycle states. The engine should remain provider-adapter based so the core revision model is not hard-coded to ACP.

## Core capabilities

### Revision preview

Before execution, Delta computes a plan for every step:

- `reuse`: a completed result is still valid.
- `rerun`: no valid reusable result exists for the effective input and policy.
- `pending_dependency`: an upstream step must finish before the downstream effective input can be known.

Each decision includes structured reason codes and a short human-readable explanation.

Where reliable information exists, the preview includes estimated additional service cost. Unknown prices remain `unknown`.

### Persistent work records

Delta preserves the information needed to understand and safely continue work across real process restarts:

- workflow and project scope
- meaningful effective input
- explicit dependencies
- implementation/version identity
- freshness policy
- canonical input signature
- output signature
- output or durable artifact reference
- provider and offering identity
- provider job identity
- chain identity
- execution attempt state
- cost estimate, quote, approved cap, and actual known cost
- transaction references where available
- failure and reconciliation state
- execution history

Sibyl Memory is authoritative for this state in the hackathon submission.

### Paid-job continuity

Before creating a new paid job, Delta checks for an existing nonterminal or ambiguous attempt for the same step and revision intent.

If a provider job ID is known, Delta reconciles that job first.

If an action may have created a job but no reliable job identity was captured, Delta does not blindly retry. It attempts conservative reconciliation and requires human intervention when identity cannot be established safely.

This is not an exactly-once guarantee.

## Initial demonstration workflow

The launch-package workflow contains three explicit steps.

### Product visual

Relevant inputs:

- `product_description`
- `visual_brief`

No workflow dependency.

### Announcement

Relevant inputs:

- `product_description`
- `launch_date`

No dependency on the visual.

### Translation

Relevant inputs:

- announcement output
- `target_language`

Explicit dependency on announcement.

The final live provider mapping is not locked until current ACP offerings are discovered and verified. The workflow concept remains the same if a service substitution is required.

## Required behavior

### Unchanged request

Reuse every successful, available, fresh result whose scope, effective input signature, and implementation identity still match.

### Launch date changes

Reuse visual.

Rerun announcement.

Mark translation `pending_dependency` before announcement completes if its final effective input is not yet known.

After announcement completes, recompute translation's effective input signature. If the new announcement output has the same output signature as the previous announcement, reuse translation when all other validity conditions still hold.

### Visual brief changes

Rerun visual only. Announcement and translation remain reusable when valid.

### Product description changes

Rerun visual and announcement. Translation remains pending until the new announcement output is known, then is reevaluated from its actual effective input.

### Freshness expiration

An expired work result is not reusable. Expiration of one independent step does not invalidate unrelated work.

### Implementation/version change

Changing a step's developer-declared implementation identity invalidates previous work for that step even if the logical inputs are unchanged. Downstream work is reevaluated after the new output is known.

### Failure or incomplete execution

Failed, interrupted, ambiguous, or incomplete attempts are not reusable work results.

A previous valid successful result can remain reusable if a later failed attempt did not invalidate it for the current effective input and freshness policy.

## Architecture decision

### Use a small Python execution layer

**Design decision:** Delta's product runtime will use a small explicit DAG and revision engine rather than LangGraph.

Reasons:

1. The initial graph semantics are simple: explicit dependencies, topological planning, signature checks, and provider execution.
2. Delta's differentiating work is revision planning and remote paid-job continuity, not graph scheduling.
3. LangGraph would introduce another graph state and persistence model beside Sibyl, increasing the risk that Sibyl becomes decorative rather than authoritative.
4. Sibyl's documented local SDK is Python, so Python gives the core engine a direct persistence path.
5. Virtuals ACP's CLI is explicitly designed for scripted use and machine-readable JSON, so a Python subprocess adapter can integrate it without moving the whole engine to Node.

LangGraph remains useful as a baseline comparison and prior-work reference. It is not a dependency of the core product unless implementation evidence later demonstrates a concrete need.

### Proposed runtime stack

- Python 3.11 or newer, subject to repository constraints.
- Pydantic or dataclasses for explicit schemas. Prefer Pydantic if FastAPI is used.
- FastAPI for a minimal local web server if the repository has no suitable existing server framework.
- Server-rendered HTML plus minimal JavaScript unless an existing frontend stack should be preserved.
- Sibyl Memory Python client for authoritative persistent state.
- Virtuals ACP CLI invoked as a subprocess adapter with `--json`.
- A durable local artifact directory on a persistent filesystem for large binary outputs.
- Base JSON-RPC or a trusted Base client library for independent transaction-receipt verification when needed.

No separate SQL application database is planned.

## Component model

### `delta.core`

Owns stable workflow and step definitions, input binding, dependency validation, canonicalization, signatures, freshness checks, and revision planning.

### `delta.store`

Defines the persistence interface used by the engine and the Sibyl-backed implementation used by the submission.

The core engine must depend on this interface for work lookup, attempt history, active-job recovery, plan persistence, and execution updates.

### `delta.execute`

Coordinates plan execution, step readiness, provider adapters, cost approvals, result validation, downstream reevaluation, and failure state transitions.

### `delta.providers`

Provider-specific adapters. The first required live adapter is Virtuals ACP. Deterministic fixture adapters are used for automated tests.

### `delta.artifacts`

Stores and verifies large artifacts without becoming a second execution database.

### `delta.web`

Minimal demonstration API and page. It consumes the reusable engine and contains no independent revision logic.

### `baseline`

A separate comparison harness for correctly configured LangGraph caching and persistence. It is evidence, not a Delta runtime dependency.

## Developer-facing API

The developer experience should make relevant inputs and dependencies explicit in code.

Conceptual shape:

```python
workflow = Workflow(
    id="launch-package",
    version="1",
    inputs={
        "product_description": InputSpec(type="string"),
        "visual_brief": InputSpec(type="string"),
        "launch_date": InputSpec(type="date"),
        "target_language": InputSpec(type="string"),
    },
    steps=[
        Step(
            id="visual",
            implementation_id="visual-provider:v1",
            bind={
                "description": workflow_input("product_description"),
                "brief": workflow_input("visual_brief"),
            },
            executor=visual_executor,
            freshness=TTL(hours=24),
        ),
        Step(
            id="announcement",
            implementation_id="copy-provider:v1",
            bind={
                "description": workflow_input("product_description"),
                "launch_date": workflow_input("launch_date"),
            },
            executor=announcement_executor,
            freshness=TTL(hours=24),
        ),
        Step(
            id="translation",
            implementation_id="translation-provider:v1",
            bind={
                "text": step_output("announcement"),
                "language": workflow_input("target_language"),
            },
            executor=translation_executor,
            freshness=TTL(hours=24),
        ),
    ],
)

plan = delta.preview(
    workflow,
    scope=Scope(tenant_id="...", project_id="demo-a"),
    inputs={...},
)

execution = delta.execute(plan, approval=approval)
```

The exact public API can be refined during implementation, but these properties are required:

- dependencies derive from explicit `step_output` bindings
- effective inputs can be inspected
- implementations have explicit version identity
- freshness is explicit
- planning is separate from spending and execution
- a plan can be shown before any paid action
- provider-specific job identity is available through normalized attempt records

## Scoping model

Reuse is scoped by both tenant/user identity and project identity.

Sibyl provides tenant isolation. Delta adds explicit `project_id`, `workflow_id`, and `step_id` to every deterministic key.

A reusable result from one project must never satisfy another project's revision even when all content inputs are identical.

## Canonical signatures

### Supported input domain

The first implementation should accept JSON-compatible effective inputs only:

- strings
- booleans
- integers
- finite numbers
- null
- arrays
- objects with string keys
- dates and datetimes normalized to an agreed ISO representation before canonicalization

Reject NaN, Infinity, arbitrary Python objects, and unstable serialized forms.

### Input signature

Construct a deterministic canonical object containing at least:

- tenant scope identifier or stable tenant namespace
- project ID
- workflow ID
- step ID
- step implementation ID
- normalized effective input

Serialize with sorted object keys and deterministic separators, then hash with SHA-256.

The signature is for identity, not encryption.

Do not include credentials or private keys.

### Output signature

For inline JSON or text, hash the normalized output.

For binary artifacts, hash artifact bytes and record media type and size.

A downstream step uses the actual normalized upstream output or its content-derived representation as its bound input. It does not use only the fact that the upstream step executed.

This is what allows an upstream rerun with unchanged output to preserve downstream reuse.

## Freshness model

The minimum freshness policy is:

- no expiration
- TTL from successful completion time

A successful result records `completed_at` and `fresh_until` when a TTL applies.

A result is stale when current time is at or beyond `fresh_until`.

More complex provider-specific freshness policies are later enhancements.

## State ownership in Sibyl

**Verified fact as of 2026-09-02:** Sibyl exposes HOT state, WARM entities, COLD journal, REFERENCE records, and multi-tenant isolation. The installed client supports explicit tenant selection through `MemoryClient.local(..., tenant_id=...)` and the tier methods recorded in `REFERENCES.md`. Practical maximum size limits remain an implementation constraint to measure beyond the Phase 0 smoke-test record.

**Design decision:** use the tiers according to intent rather than duplicating the same full record across all tiers.

### Work result entity

Primary reusable result record, keyed deterministically by scope, workflow, step, implementation identity, and input signature.

Contains:

- work result ID
- scope
- workflow and step IDs
- implementation ID
- effective input summary or safe full value
- input signature
- output signature
- inline output or artifact reference
- completion time
- freshness data
- executor/provider identity
- successful attempt ID

Only a successful completed attempt can create or update a reusable work result.

### Attempt entity

One record per execution attempt.

Contains:

- attempt ID
- requested input signature
- provider adapter
- provider, offering, and chain
- provider job ID when known
- lifecycle state
- estimated cost and timestamp
- provider quote
- approval ID and cap
- actual known service cost
- transaction references
- deliverable metadata
- timestamps
- failure or ambiguity classification
- reconciliation evidence

### Current head state

A small HOT state record per project/workflow/step can point to the current active attempt and requested signature. It must not duplicate the full attempt.

This is used to find work that needs reconciliation after restart.

### Journal

Append concise transition events for auditability and demo evidence, for example:

- plan created
- decision changed after dependency output
- paid attempt created
- ACP job identity captured
- budget quoted
- funding confirmed
- deliverable submitted
- settlement confirmed
- attempt became ambiguous
- reconciliation resolved ambiguity

The journal is audit history, not the only source used for current-state decisions.

### Plan record

Persist revision plans that may lead to spending. A plan records the preview inputs, step decisions, estimates, matched reusable results, and approval state.

This allows a restart to explain what was intended before a transaction occurred.

## Artifact storage

Large artifacts should not consume Sibyl memory capacity unnecessarily.

### Initial artifact store

Use a generated artifact ID and a persistent local directory outside source control, for example a configurable `DELTA_ARTIFACT_DIR`.

Never construct a filesystem path directly from a project name or provider filename.

Store in Sibyl:

- artifact ID
- content hash
- media type
- byte size
- local durable path or external reference
- original provider reference when relevant
- availability status and last verification time

### Reuse rule

A result that requires an artifact is reusable only when the artifact is still available according to the configured artifact policy.

For local stored bytes, verify file presence and optionally content hash.

For an external-only reference, do not assume availability forever. If it cannot be safely verified, classify the result as unavailable or verification-blocked rather than silently rerunning a paid job.

### External deliverables

Treat ACP deliverables as untrusted.

Prefer storing small text deliverables inline.

For remote artifact URLs, validate scheme, destination, redirects, content type, and size before server-side download. Do not render arbitrary HTML from a provider.

## Revision planning algorithm

Delta uses ordinary deterministic DAG evaluation.

1. Validate workflow definition and reject cycles.
2. Resolve steps in topological order.
3. For a step whose dependency outputs are all known, derive its normalized effective input.
4. Compute the current input signature.
5. Look up a matching reusable result in Sibyl.
6. Check scope, implementation identity, successful status, freshness, and artifact availability.
7. Return `reuse` when all validity checks pass.
8. Return `rerun` with structured reasons when no valid reusable result exists and all effective inputs are known.
9. Return `pending_dependency` when one or more dependencies are scheduled to execute and their resulting outputs are not yet known.
10. During execution, after any upstream result is produced, recompute the effective inputs and signatures of newly ready downstream steps.
11. A downstream step may switch from `pending_dependency` to `reuse` if the new upstream output produces the same valid effective-input signature as an existing result.

No LLM participates in these decisions.

## Decision reason model

Use stable machine-readable reason codes plus human-readable explanations.

Examples:

- `MATCHING_RESULT`
- `INPUT_CHANGED`
- `NO_PRIOR_RESULT`
- `IMPLEMENTATION_CHANGED`
- `FRESHNESS_EXPIRED`
- `ARTIFACT_MISSING`
- `PRIOR_ATTEMPT_FAILED`
- `DEPENDENCY_OUTPUT_UNKNOWN`
- `PROJECT_SCOPE_MISMATCH`
- `PROVIDER_JOB_RECONCILIATION_REQUIRED`

A preview should explain the most relevant causes rather than dumping every internal check.

## Execution state model

### Local Delta attempt states

Minimum normalized states:

- `planned`
- `awaiting_approval`
- `submitting`
- `active`
- `awaiting_provider`
- `deliverable_ready`
- `awaiting_settlement_approval`
- `settling`
- `succeeded`
- `failed`
- `expired`
- `rejected`
- `ambiguous`
- `reconciliation_required`

Provider adapters map their lifecycle into these states while preserving the original provider status.

### Reusable result invariant

Only `succeeded` attempts with validated outputs create reusable work results.

A submitted deliverable awaiting settlement may be recoverable work, but it is not yet represented as a reusable completed result unless the workflow policy explicitly defines pre-settlement reuse. The initial ACP submission should require completed settlement before success to keep money and output state aligned.

## Virtuals ACP integration

### Verified current capabilities

Current ACP documentation describes:

- service offerings with price, SLA, requirements, and deliverable definition
- service-only jobs
- onchain job lifecycle
- USDC escrow funding
- submitted deliverables
- completion that releases escrow
- rejection that returns escrow
- Base chain selection using chain ID 8453 in current CLI examples
- JSON output for CLI commands
- job history, job watch, and event streams

### Adapter approach

Use the ACP CLI through a narrow subprocess adapter because it is documented for shell/scripted workflows and exposes machine-readable output.

The adapter should expose provider-neutral operations such as:

- discover offerings
- inspect offering and current price
- create service job
- get job history/status
- fund quoted budget
- obtain submitted deliverable
- complete or reject job
- reconcile known job

Do not expose arbitrary CLI execution to application inputs.

### Job creation safety

Before job creation:

- persist an attempt intent record in Sibyl
- persist provider, offering, chain, effective input signature, and approval reference
- mark the attempt `submitting`

After successful CLI response:

- persist job ID and chain immediately
- persist any returned transaction hash
- transition to the mapped provider state

If the subprocess exits, times out, or disconnects after a transaction may have been broadcast but before a reliable job ID is stored, mark the attempt `ambiguous`.

Do not automatically create a replacement.

### Reconciliation

For a known `job_id` and `chain_id`, query current ACP job history and state before deciding the next action.

Expected mappings:

- `open`: existing job, wait for provider budget
- `budget_set`: existing job, compare quote to approval before funding
- `funded`: existing paid job, wait for provider output
- `submitted`: retrieve deliverable and await settlement decision
- `completed`: verify deliverable and settlement evidence, then finalize result
- `rejected`: terminal failure, no reuse
- `expired`: terminal failure, no reuse

For an unknown job ID after an ambiguous create, attempt conservative discovery using client identity, provider, offering, chain, requirements fingerprint, and a bounded creation-time window if the current API exposes enough data.

Automatically bind the attempt to a discovered job only when identity is unambiguous.

If zero or multiple plausible jobs remain, require manual reconciliation. This is a deliberate spending-safety boundary.

### Events and polling

The current ACP client workflow requires `acp events listen` before creating a live job and uses it for event-driven progress. Do not rely solely on the listener because a process restart can interrupt it. Persist Delta state independently and reconcile through provider job history or status after restart.

For the initial single-workflow demo, `job watch` can simplify waiting for action-needed states, while job history and status queries remain the recovery primitives. The UI can poll Delta's own status endpoint while the backend periodically reconciles provider state.

A scalable event consumer is a later enhancement.

## Base integration

### Intended path

Use ACP service jobs on Base mainnet, chain ID 8453, so the demonstrated paid work includes actual USDC funding and settlement on Base.

Record and verify Base transaction evidence for the paid flow. Where transaction hashes are available, independently verify receipts through a Base RPC endpoint and include them in the execution record and demo evidence.

### Qualification uncertainty

The hackathon rules list Base and Virtuals as separate partner stacks. They state that Base requires an executed onchain action for the bonus and Virtuals requires an exercised ACP-native integration.

The current rules also describe Base deployment as the eligibility floor when claiming that partner stack. Confirm the deployment requirement before the live phase and do not claim the stack without meeting it.

It is not yet verified that the same ACP-on-Base funding/settlement flow is accepted as evidence for both partner stacks.

Do not claim both multipliers from the same action until the organizers or partner guidance confirms it.

If a distinct Base action is required, add only the smallest product-relevant action after confirmation. Do not invent a token, custom contract, or unrelated payment solely for optics.

## Cost model

Delta separates four concepts.

### Estimated additional service cost

Known before execution only when a current provider offering or pricing endpoint supplies a reliable amount.

Store:

- amount
- currency
- source
- retrieval timestamp
- provider/offering identity

If unavailable, use `unknown`.

### Provider quote

For ACP, the provider's `budget_set` amount is the authoritative quote before funding.

If it differs from the preview estimate, show the difference and re-check approval.

### Actual service cost

For the initial ACP integration, record the amount actually funded and the terminal settlement result. Do not call an estimated price actual.

### Network fees

Record native gas amount and transaction receipts when obtainable.

Do not convert gas to a fiat amount unless a verified price source and timestamp are available. It is acceptable to show service cost in USDC plus gas in native units separately.

## Approval model

A revision preview never grants spending authority.

A `SpendApproval` should bind at minimum:

- plan ID
- tenant/project
- allowed step IDs
- chain ID
- maximum total service spend in USDC
- optional maximum per job
- allowed provider/offering identities if known
- allowed action scope, such as create, fund, settle
- expiration time
- approving user/action evidence

A provider quote above the cap blocks funding.

A new or changed plan requires a new approval if it changes spend-relevant scope.

For the hackathon builder, no live approval object may be created on behalf of the user without explicit user authorization of the exact budget and transaction scope.

## Failure and recovery boundaries

### Safe automatic retry

Automatic retry is allowed for local pure operations where execution is known not to have external side effects.

### Provider read retry

Read-only provider status calls can be retried with bounded backoff.

### Paid action retry

Do not retry job creation, funding, or settlement merely because the local command failed.

First reconcile current provider and chain state.

### Ambiguous settlement

If a settlement command result is ambiguous, query job history and Base receipt state before any further action.

### Artifact unavailable

Do not create a replacement paid job automatically because a remote artifact URL is temporarily unavailable. Surface the state and allow the user to choose after verification or recovery attempts.

## Concurrency model

### Initial submission guarantee

Support one active writer process per Delta state store.

Use an in-process lock to prevent duplicate concurrent execution inside that process and persist active-attempt identity in Sibyl for restart recovery.

Do not claim multi-process mutual exclusion unless a real atomic lease mechanism is implemented and tested.

If two processes can access the same Sibyl database concurrently, this remains a documented unsupported mode for the initial submission.

### Per-step rule

Never intentionally maintain two active paid attempts for the same project, workflow, step, and desired input signature.

An existing active or ambiguous attempt blocks replacement until reconciled.

## Minimal web demonstration

One page is sufficient.

### Layout

Use a clear workflow-focused layout rather than a dashboard shell.

Top section:

- project ID
- product description
- visual brief
- launch date
- target language
- revision preview action or automatic preview after edits
- total estimated additional service cost
- approved budget state

Workflow section:

Three vertically ordered step rows with simple dependency indication between announcement and translation.

Each step shows:

- step name
- decision: reuse, rerun, or pending dependency
- reason
- estimated step cost or unknown
- current output preview or artifact link
- provider/offering when live
- job ID and chain when created
- live normalized state
- actual service cost when known

### Actions

- `Preview revision`
- `Execute revision`
- an explicit spend confirmation when paid work is required
- `Reconcile` when an existing job needs recovery
- `Approve deliverable and settle` when settlement requires a distinct confirmation

Keep the settlement action explicit in the initial version because it releases escrow.

### Recovery states

The interface must visibly support:

- restored after restart
- awaiting provider quote
- awaiting funding approval
- awaiting provider deliverable
- awaiting settlement approval
- failed
- expired
- rejected
- ambiguous provider outcome
- manual reconciliation required
- artifact unavailable

No fake percentage progress.

## Baseline comparison

Build a small LangGraph baseline after Delta's deterministic planner and persistence tests pass.

Configure the baseline fairly:

- node cache keys use only relevant inputs
- TTL matches Delta
- project scope is included
- implementation version is included where needed
- persistent checkpointer/cache is used for restart comparisons when supported
- failed work is not intentionally treated as successful cache

Compare behavior, not marketing claims.

Expected overlap includes selective node reuse, TTL-based invalidation, custom cache keys, and persistent recovery.

Delta's claim should be limited to what the implementation demonstrates around integrated revision preview, persistent paid-work records, provider job reconciliation, cost/approval state, and developer ergonomics.

Do not claim that Delta invented selective reruns.

## Testing strategy

### Deterministic engine tests

Use fixture executors with explicit call counters and configurable output stability/failure.

Test every revision behavior without network or money.

### Sibyl integration tests

Use a real local Sibyl store, not a mock, for persistence tests.

A restart test must use a new process that reconnects to the same Sibyl memory and successfully restores work state.

### ACP adapter contract tests

Use a fake CLI executable or captured sanitized JSON fixtures to test parsing, lifecycle mapping, ambiguity, and reconciliation without broadcasting.

### Live ACP and Base validation

Run only after explicit budget approval.

Verify at least one real service job end to end, including provider deliverable and terminal settlement.

Record job ID, chain ID, known costs, and Base transaction evidence.

### Project isolation

Use two project IDs under the same tenant and identical workflow inputs. Neither project's work result may satisfy the other.

## Deployment requirements

The initial submission can be a local runnable demonstration.

The simplest reliable environment is a single persistent Linux or macOS workstation or VM with:

- Python environment
- Node.js 20.19 or newer for the current ACP CLI package
- Sibyl local memory installed and authenticated
- ACP CLI installed and authenticated
- ACP signing setup completed through supported secure key storage
- persistent artifact directory
- network access to Virtuals and Base

Avoid ephemeral serverless hosting for the initial proof because Sibyl's local database, ACP OS keychain state, and restart demonstration all benefit from stable local storage.

If hosted later, use one durable instance with an encrypted persistent volume and a secure interactive process for wallet/signer provisioning.

## Minimum complete submission

The submission is not complete at the deterministic proof milestone.

Minimum complete submission requires:

1. Reusable Delta engine with explicit workflow definitions.
2. Revision preview with reasons and cost estimates where known.
3. Sibyl as authoritative persistent work, attempt, and plan state.
4. Real process restart recovery from Sibyl.
5. Correct downstream reevaluation after upstream execution.
6. Deterministic tests for all required revision and failure cases.
7. Conservative interrupted-job reconciliation behavior.
8. A genuine Virtuals ACP service job with a real deliverable.
9. Actual Base onchain payment or settlement evidence in the demonstrated workflow.
10. Explicit spend approval and cap enforcement.
11. Minimal one-page web demonstration with real recovery/error states.
12. Fair LangGraph baseline comparison.
13. Honest documentation and judge runbook.
14. Public repository requirements satisfied, including an OSI-approved license and required README disclosures.
15. Demo evidence showing fresh-session Sibyl recall on the critical path.

## Later enhancements

Not required for the hackathon submission:

- additional provider adapters
- hosted multi-tenant service
- object-store artifact backend
- atomic distributed leases
- event-stream worker for many concurrent jobs
- policy plugins beyond TTL
- richer SDK ergonomics
- CLI package distribution
- provider quote aggregation
- automated artifact recovery
- multiple currencies

These must not distract from the minimum complete submission.

## Strongest known limitations

1. Initial concurrency is single-writer and does not guarantee distributed exclusivity.
2. If an ACP create or payment action becomes ambiguous before a reliable job or transaction identity is captured, Delta may require manual reconciliation.
3. Provider offering availability, price, and SLA can change between preview and execution.
4. External artifact references can disappear even when work was completed successfully.
5. Delta cannot prevent duplicate provider billing when the provider protocol itself lacks a usable idempotency or reconciliation primitive and the original job cannot be identified.
6. The exact claim that one ACP-on-Base flow qualifies as both partner integrations remains unverified until confirmed.

## Major decisions

- Build a small Python DAG/revision engine rather than using LangGraph in the runtime.
- Use LangGraph only as a fair baseline and prior-work comparison.
- Make Sibyl the authoritative work and revision state store.
- Store large artifacts separately and only persist durable references plus hashes in Sibyl.
- Use the Virtuals ACP CLI JSON interface behind a narrow adapter.
- Prefer ACP service-only jobs on Base mainnet for the live workflow.
- Require explicit approval before every live spending phase and enforce a maximum cap.
- Treat ambiguous paid outcomes as reconciliation problems, not retry triggers.
- Support one writer process in the initial submission and document the boundary.
- Keep the launch-package UI small and workflow-focused.
