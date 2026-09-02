# Delta Implementation Plan

## Purpose

This document owns implementation order, phase dependencies, acceptance criteria, and exit gates. Stable requirements are defined in `MASTER_PLAN.md`.

A phase is complete only when its exit gate is verified. Update `STATE.md` after each meaningful verification.

## Roadmap at a glance

The current workspace contains the planning package only. Build the reusable engine before the demonstration interface, and keep live spending last.

1. **Phase 0, discovery:** inspect the real implementation environment, verify current integration contracts, and discover suitable ACP offerings without spending.
2. **Phase 1, core engine:** implement schemas, explicit dependencies, signatures, freshness, fixture executors, and provider-neutral tests.
3. **Phase 2, persistence:** connect Sibyl as the authoritative store, keep artifacts outside Sibyl, and prove fresh-process recovery.
4. **Phase 3, revision behavior:** implement preview decisions, runtime downstream reevaluation, structured reasons, and the full deterministic scenario suite.
5. **Phase 4, paid-job safety:** add the narrow ACP adapter and fixture-based lifecycle reconciliation before any live transaction.
6. **Phase 5, demonstration UI:** expose the workflow inputs, decisions, costs, outputs, approvals, provider states, and recovery states in one responsive page.
7. **Phase 6, baseline:** build a fair LangGraph comparison and record measured overlap and added Delta behavior.
8. **Phase 7, live validation:** exercise one approved ACP service job and Base payment or settlement, then prove restart recovery from Sibyl.
9. **Phase 8, submission hardening:** run the complete verification path, remove secrets, pin versions, update the public documentation, and capture honest evidence.

The dependency chain is sequential through Phase 4. Phase 1 depends on foundation readiness, not on a paid ACP job or Base deployment. Phase 5 depends on the engine and persistence behavior. Phase 6 depends on deterministic Delta behavior. Phase 7 depends on live ACP readiness, Base qualification readiness, every earlier required foundation gate, and explicit user approval for the exact provider, chain, actions, and budget. Phase 8 depends on the evidence from all required paths.

## Project-wide exit-gate rule

Every phase exit gate requires behavioral evidence from the path that the phase claims to implement. A phase is not complete because files exist or a happy-path function returns a value. Where the phase exposes a meaningful capability, verification must cover the relevant path from user input or API request through the engine, adapter or service, real computation or state lookup, required persistence, returned result, and user-visible state. Include at least one positive case and one negative or changed-input case where practical.

Fixtures and deterministic services may support planned local tests, but they must be labelled and kept distinct from live adapters. Fixture output cannot prove a live integration. If a dependency is unavailable or the result cannot be verified, record an honest unverified, blocked, unavailable, ambiguous, or reconciliation state.

## Phase 0: Repository and live-integration discovery

### Goal

Confirm the actual workspace, preserve existing work, verify current APIs, and determine whether the launch-package services can be demonstrated with current ACP offerings.

### Work

1. Inspect repository structure, instructions, package files, current tests, existing UI, and current license.
2. Read installed skills relevant to Sibyl, ACP, Base, security, and the repository stack.
3. Verify the official sources listed in `REFERENCES.md` again at build time.
4. Verify installed or chosen versions of:
   - Python
   - Sibyl Memory client/CLI
   - Node.js
   - `@virtuals-protocol/acp-cli`
   - LangGraph used by the comparison harness
5. Verify the current ACP authentication path. For scripts or output-captured runners, use `acp configure start --json`, relay the returned URL to the user, then poll `acp configure complete --request-id <requestId> --json`. Do not run bare `acp configure` from a non-streaming runner.
6. Run read-only ACP discovery with machine-readable output after an active agent is available. Use `acp browse ... --json` and record the exact command output or the precise blocker.
7. Verify the live event requirement. Current ACP client guidance requires `acp events listen` before creating a job. Treat the listener as a live progress dependency, while using persisted job history, status queries, and Delta state as restart recovery sources.
8. Search for suitable online service-only offerings for:
   - image or visual generation
   - announcement/copy generation
   - translation
9. For each candidate record:
   - provider identity
   - offering identity
   - chain support
   - current price
   - SLA
   - requirements schema
   - deliverable format
   - online/availability status
   Treat an `--online online` filter as a query constraint when the response does not expose an independent online field. Do not upgrade that result to a provider heartbeat claim.
10. Prefer Base mainnet chain ID 8453 for live service jobs when supported.
11. Confirm whether ACP job creation, funding, and completion JSON expose transaction hashes or enough identifiers for Base receipt evidence.
12. Verify with current hackathon or partner guidance whether the planned deployment and one ACP-on-Base service flow satisfy the current Base and Virtuals partner criteria.
13. If not, identify the smallest separate product-relevant Base action that meets the rule without adding speculative infrastructure.

### No-spend boundary

Phase 0 discovery is read-only, with authorized non-spending ACP identity and signer registration as the only setup exceptions. Do not create jobs, top up wallets, fund escrow, approve spending, or broadcast any transaction.

### Foundation readiness gate

Foundation readiness may be marked `Verified` when:

- repository destination is unambiguous
- current source versions are recorded
- Sibyl initialization, status, health, exact persistence APIs, tenant selection, and a fresh-process smoke test are verified
- ACP authentication, agent identity, and any required non-spending signer setup are verified
- the read-only discovery command has been attempted with machine-readable output, with any CLI or policy blocker recorded exactly
- the current ACP authentication and event-listener requirements are recorded
- unresolved JSON/API questions that affect money safety are narrowed enough for fixture implementation
- no funds have moved

### Live ACP readiness gate

Live ACP readiness passes only when at least one suitable live ACP service offering is returned by read-only discovery with its provider, offering, chain, price, requirements, deliverable, availability, timing, and reconciliation metadata recorded. A signer, authentication result, or CLI command that returns no provider data does not satisfy this gate.

The verification must exercise the real browse path and include either a changed query or an explicit chain-filter comparison where the CLI supports it. A successful command with a fixed or fixture response is not evidence of live marketplace readiness.

### Base partner qualification gate

Base partner qualification is tracked separately from foundation readiness. Record the planned live Base action, deployment requirement, and unresolved partner-evidence question, but do not block the provider-agnostic engine solely because no Base deployment or transaction exists yet. Base evidence remains required before claiming the completed live integration or final submission.

### Phase 0 status rule

Foundation readiness may unlock Phase 1. If live ACP readiness or Base partner qualification is incomplete, mark Phase 0 `Partially complete` and keep those later gates blocked or unverified. Authentication and signer setup alone do not establish marketplace availability or Base qualification.

If suitable launch-package offerings are not available, adjust the demo service mapping while preserving Delta's core purpose. Record the substitution and reason in `STATE.md` and `DEMO_RUNBOOK.md`.

## Phase 1: Core schemas and deterministic execution model

### Goal

Establish the provider-neutral data model and deterministic planning behavior without network calls.

### Work

Implement the minimum conceptual schemas from `MASTER_PLAN.md`:

- `Scope`
- `Workflow`
- `Step`
- workflow input binding
- step output binding
- freshness policy
- revision request
- revision plan and per-step decision
- work result
- execution attempt
- artifact reference
- cost estimate and provider quote
- spend approval
- execution event/reason code

Implement:

- workflow validation
- cycle detection
- topological order
- JSON-only normalization
- deterministic input signatures
- output signatures
- freshness evaluation
- project-scope checks
- decision explanations
- spend-approval validation against plan identity, project scope, allowed steps, provider scope, chain, action scope, expiration, currency, and service-spend caps

Create deterministic fixture executors for visual, announcement, and translation. They must expose call counters and configurable failure/output behavior.

### Required tests

- canonical signature stability
- input key order does not change signatures
- implementation ID changes signatures
- project ID changes signatures
- invalid JSON-like values are rejected
- cycle detection
- explicit dependency extraction
- invalid or incomplete spend-approval values are rejected

### Exit gate

Phase 1 passes when all core schema, signature, workflow-validation, and approval-value tests pass without Sibyl, ACP, or Base dependencies, and the public engine path proves both an accepted valid case and rejected invalid or changed-input cases. No test success may come from an unlabelled fixture or a bypass around the engine.

## Phase 2: Sibyl authoritative persistence

### Goal

Make persistent work lookup and recovery depend on real Sibyl Memory.

### Work

1. Confirm exact current Python SDK methods and tenant selection behavior.
2. Implement the Sibyl-backed store according to the tier mapping in `MASTER_PLAN.md`.
3. Persist:
   - reusable work results
   - attempts
   - active step heads
   - revision plans
   - concise transition journal events
4. Ensure large fixture artifacts are stored outside Sibyl with references and content hashes.
5. Ensure removal of the Sibyl store prevents cross-process reuse and recovery.
6. Add project isolation to every key.

### Required tests

- write and read reusable result
- write and read attempt
- current active-attempt recovery
- journal event append
- two project IDs cannot cross-reuse
- missing artifact invalidates reuse according to policy
- real fresh Python process restores the same work from the same Sibyl memory path
- removing or disconnecting a disposable Sibyl test store prevents restoration and proves no hidden application database can reconstruct the authoritative state

### Restart test

Use a parent test or script that:

1. starts process A
2. executes deterministic workflow and exits
3. starts process B with fresh application objects
4. reconnects to the same Sibyl memory
5. plans the unchanged request
6. proves zero fixture service calls are made in process B

Browser local storage or module globals do not count.

### Critical-path deletion test

Use a disposable Sibyl store created only for this test:

1. complete the restart test successfully
2. stop every test process using that store
3. remove the disposable store or make it unavailable
4. start process C with fresh application objects
5. verify that prior work results, plans, attempts, and active-job identity cannot be restored
6. verify that no separate application database or local cache reconstructs the missing authoritative state

Never run this test against shared Sibyl data, user credentials, or a non-test memory path.

### Exit gate

Phase 2 passes only when both the real process-restart test and the disposable-store deletion test pass through fresh application processes. Sibyl must be demonstrably authoritative for cross-process reuse and recovery, and the deletion or unavailable-store case must fail honestly rather than restore a predetermined success.

## Phase 3: Revision planner and runtime downstream reevaluation

### Goal

Complete the revision semantics that distinguish preview-time uncertainty from final runtime reuse.

### Work

Implement preview logic for:

- `reuse`
- `rerun`
- `pending_dependency`

Implement structured reasons and cost placeholders.

Implement execution scheduling for ready steps.

Implement the single-writer boundary with an in-process lock around execution decisions and attempt creation. An existing active or ambiguous attempt for the same project, workflow, step, and desired input signature must block duplicate execution.

Implement cost aggregation so reused work contributes zero additional service cost, known rerun estimates are summed, and any unknown estimate remains explicitly unknown. Keep estimate, provider quote, actual service cost, and network gas separate.

After every completed upstream execution:

1. persist the successful result
2. recompute newly ready downstream effective inputs
3. recompute signatures
4. look for matching reusable work
5. either reuse or execute

### Required tests

1. Unchanged request.
   - all reused
   - zero additional fixture calls
2. Launch date only.
   - visual reused
   - announcement reruns
   - translation pending before announcement finishes
   - translation reruns only when actual announcement output changes
3. Visual brief only.
   - visual reruns
   - announcement and translation reused
4. Product description change.
   - visual and announcement rerun
   - translation reevaluated after announcement
5. Expired result.
   - expired step reruns
   - independent step remains reusable
6. Implementation/version change.
   - target step reruns
   - downstream reevaluated from actual output
7. Upstream rerun with unchanged output.
   - upstream executes
   - downstream reuses existing valid result
8. Failed step and retry.
   - failed attempt recorded
   - no failed output becomes reusable
   - independent valid results remain reusable
9. Project isolation.
   - identical requests under two projects do not cross-reuse
10. Cost and reason semantics.
   - reused work contributes zero additional service cost
   - known rerun estimates are included once
   - an unknown rerun estimate is not displayed or aggregated as zero
   - estimate, provider quote, actual service cost, and gas remain separate values
   - stable reason codes accompany every decision
11. Single-writer execution.
   - two concurrent requests for the same desired step input produce one fixture executor call
   - the second request observes the active attempt instead of creating another attempt
   - different independent steps can still progress according to the scheduler

### Exit gate

Phase 3 passes when all required deterministic revision tests pass through the real Sibyl store, including unchanged, changed-input, rerun, pending-dependency, failed, and blocked outcomes. The results must be derived from the planner and persisted state, not hardcoded scenario responses.

## Phase 4: ACP adapter contract and reconciliation with fixtures

### Goal

Implement paid-job continuity safely before any live spending.

### Work

Build a narrow ACP CLI runner that:

- invokes an executable with argument arrays
- never uses shell interpolation
- requests JSON output
- captures stdout/stderr safely
- redacts known sensitive values
- applies timeouts
- distinguishes command failure from ambiguous external outcome

For live job creation, start and maintain the ACP event listener required by the current client workflow before creating a job. Do not use that listener as the only recovery source. Persist Delta attempt state immediately and reconcile with ACP job history or status after restart.

Build provider-neutral ACP adapter methods for:

- browse/discover
- inspect offering
- create job
- query job history/status
- wait/watch when appropriate
- fund
- obtain deliverable
- complete
- reject
- reconcile

Create sanitized fixture JSON for each relevant ACP lifecycle state.

Persist intent before any simulated side-effecting action.

Before simulated create, fund, or complete actions, validate the stored approval against the persisted plan and current provider state. Check project and plan identity, allowed steps, provider and offering, chain, action scope, expiration, currency, maximum total service spend, and any per-job cap. A changed spend-relevant plan requires a new approval.

Track approved and committed service spend per plan so several individually valid jobs cannot exceed the total cap.

Reject malformed JSON, unexpected response structures, unsupported lifecycle values, and deliverables that fail their expected schema. Preserve enough failure classification for reconciliation without storing secrets.

Treat provider deliverables and references as untrusted. Validate generated artifact paths and, when remote downloads are enabled, validate URL scheme, destination, redirects, content type, response size, and content hash before marking an artifact available.

### Reconciliation rules to implement

Known job ID:

- query existing job first
- never create replacement while nonterminal
- map `open`, `budget_set`, `funded`, `submitted`, `completed`, `rejected`, `expired`

Unknown job ID after ambiguous create:

- attempt discovery only if current APIs expose enough identity fields
- bind automatically only when exactly one job is unambiguously matched
- otherwise enter `reconciliation_required`

### Required tests

- normal job lifecycle fixture
- quote above approval blocks funding
- expired approval blocks create, fund, and complete actions
- changed plan or mismatched project, step, provider, offering, chain, currency, or action scope blocks the paid action
- cumulative committed service spend cannot exceed the plan cap across several jobs
- unavailable or differently denominated quotes require a new approval
- process restarts with known funded job and resumes reconciliation
- command timeout with known job ID does not create replacement
- concurrent submissions for the same desired input invoke the simulated provider create action once
- ambiguous create with zero matches blocks retry
- ambiguous create with multiple matches blocks retry
- ambiguous create with one verified match resumes the matched job
- ambiguous fund reconciles before any second fund attempt
- ambiguous complete reconciles before any second settlement attempt
- rejected and expired jobs do not become reusable results
- submitted deliverable is not silently treated as completed settlement
- malformed JSON, unexpected schema, and unsupported lifecycle values fail closed
- nonzero exit, timeout, parse failure, and ambiguous external outcome remain distinguishable
- secret-like fixture values are redacted from logs and error payloads
- provider filenames and project IDs cannot escape the generated artifact root
- unsafe remote URLs, redirects, media types, and oversized responses are rejected when remote retrieval is enabled

### Exit gate

Phase 4 passes when clearly labelled fixture tests exercise the adapter contract and prove approval scope and cap enforcement, single-writer attempt creation, hostile-output handling, safe artifact resolution, conservative candidate matching, and money-sensitive reconciliation behavior. The evidence must include a positive lifecycle, a changed or conflicting provider response, and fresh-process recovery of persisted job identity. Each success and failure must be derived from the fixture response through the adapter path, and no fixture may be presented as live ACP evidence. No live transaction may have been sent. Live marketplace response verification remains a separate readiness record and must not be replaced by fixtures.

## Phase 5: Minimal demonstration interface

### Goal

Expose the deterministic engine and reconciliation states clearly before live partner execution.

### Work

Create one page using the repository's existing web stack or the minimal FastAPI/server-rendered approach from `MASTER_PLAN.md`.

Keep revision logic in the engine. Validate project scope and action prerequisites on the server for every read and state-changing request. Render user and provider content as escaped text. If the interface is exposed beyond localhost, add CSRF protection appropriate to the selected stack.

When live ACP or Base dependencies are unavailable, the local interface may use the explicitly labelled deterministic fixture path to verify planner, persistence, changed-input, error, and unavailable-action behavior. Fixture mode must remain visibly distinct from live integrations, must not show live provider or transaction success, and cannot satisfy the live provider, approval, reconciliation, or settlement portions of this gate.

Required UI:

- project ID
- four workflow inputs
- preview action
- three workflow steps
- decision and reason per step
- estimated cost or unknown
- current output
- provider/job fields when available
- actual cost separate from estimate
- execute action
- explicit spending confirmation surface
- reconcile action
- settlement approval action
- restart recovery banner/state
- source timestamps, chain, units, and freshness where they affect interpretation

Required visual states:

- idle
- preview loading
- reuse
- rerun
- pending dependency
- awaiting approval
- awaiting quote
- funded/awaiting provider
- deliverable ready
- awaiting settlement
- complete
- failure
- expired
- rejected
- ambiguous
- reconciliation required
- artifact unavailable

Do not invent progress percentages.

### Accessibility and responsive requirements

- keyboard-accessible controls
- visible focus states
- semantic labels and status text, not color-only communication
- associated labels, inline field errors, and a focusable error summary after failed submission
- async status updates announced without moving focus during ordinary progress
- user input preserved across recoverable errors and reconciliation attempts
- paid and settlement actions visually and semantically distinct from read-only actions
- disabled actions explain the unmet prerequisite
- touch targets and spacing suitable for mobile use
- reduced-motion behavior for nonessential transitions
- readable at 375, 768, 1024, and 1440 CSS pixel widths without unintended horizontal scrolling
- long job IDs and hashes wrap without breaking layout
- live state updates use appropriate accessible status regions

### Exit gate

Phase 5 passes only when:

- the full deterministic revision and restart flow can be demonstrated from the UI using real Sibyl persistence
- the UI result for each demonstrated capability is derived from the API, engine, and persistence path that produced it
- every required visual state is exercised through labelled deterministic fixtures or real state transitions
- at least one changed-input or negative action produces an honest rerun, error, unavailable, blocked, or reconciliation state where applicable
- preview, execute, reconcile, approval, and settlement actions are enabled only in valid states
- a keyboard-only pass completes the primary workflow and reaches all recovery actions
- validation errors are announced, focus is moved to the error summary after failed submission, and field input is preserved
- the page is inspected at 375, 768, 1024, and 1440 CSS pixel widths for overflow, wrapping, hierarchy, touch access, and action reachability
- visible focus, contrast, status announcements, and reduced-motion behavior are verified
- cross-project requests and invalid action-state requests are rejected by the server
- user and provider content is rendered as escaped text, and state-changing requests have appropriate CSRF protection when exposed beyond localhost
- no dead control, placeholder link, fake progress, unsupported claim, or provider-supplied HTML remains

The Phase 5 status is `Partially complete` when the local fixture-backed interface and its real Sibyl path are verified but live provider, approval, reconciliation, or settlement states remain unverified. Do not promote the phase to `Verified` from screenshots, fixture output, or a happy-path response alone.

## Phase 6: Fair LangGraph baseline

### Goal

Validate claims against ordinary correctly configured caching and persistence.

### Work

Build a separate comparison harness using current LangGraph APIs.

The current harness lives in `delta/baseline.py` and is installed through the optional `baseline` dependency group. It uses SQLite-backed LangGraph cache and checkpoint implementations so the comparison can measure real cache hits, TTL expiry, project isolation, and fresh-process recovery without making LangGraph a Delta runtime dependency.

Configure:

- relevant node inputs only
- custom cache identity where required
- equivalent TTL
- project scope
- implementation version identity
- persistent checkpointer/cache for restart comparison when supported

Compare at least:

- unchanged request
- launch date only
- visual brief only
- product description change
- expired result
- implementation change
- upstream rerun with unchanged output
- restart

Record factual call counts and behavior.

Assess what Delta adds in practice:

- pre-execution plan explanations
- persisted paid-work provenance
- provider job lifecycle continuity
- cost quote and approval state
- conservative reconciliation behavior
- developer code required to obtain the same experience

Do not claim node-level selective execution as unique.

### Exit gate

Phase 6 passes when the comparison is reproducible from the public harness, includes unchanged and changed or negative cases, and README language can state the overlap honestly. Measured results must come from executed comparison paths rather than predetermined counts.

## Phase 7: Live Virtuals ACP and Base integration

### Goal

Exercise genuine service work and real onchain settlement without exceeding approved scope.

### Preconditions

All prior phases must pass.

The user must approve:

- exact provider and offering
- chain
- maximum service spend
- wallet funding requirement if any
- which actions may broadcast
- whether settlement approval will be a separate confirmation

If the submission claims the Base partner stack, confirm that the selected deployment meets the current eligibility floor before live evidence is captured.

Do not start this phase without explicit approval.

Read-only Phase 7 preflight is allowed before that approval. It may refresh the authenticated identity, signer policy, marketplace offerings, and response shapes, but it must stop before job creation, funding, settlement, or any other broadcast action.

### Work

1. Re-run read-only offering discovery immediately before spending.
2. Confirm price, SLA, requirements, deliverable, chain, and online status.
3. Create a live revision plan and store it in Sibyl.
4. Record the approved cap.
5. Start and verify the required ACP event listener before creating the job. Persist its local event file outside source control if the selected CLI flow uses one.
6. Create the ACP job on Base only within the approved action scope.
7. Persist job ID and transaction identity immediately when available.
8. Reconcile until quote is available.
9. Compare quote with approval.
10. Fund only when within cap and approved.
11. Persist funding evidence.
12. Reconcile until deliverable is submitted.
13. Validate and safely ingest the deliverable.
14. Require settlement approval according to the approved scope.
15. Complete and verify terminal job state.
16. Verify Base transaction receipt evidence independently where possible.
17. Persist actual known service cost and gas evidence separately.
18. Restart the Delta process and prove the completed work and job history restore from Sibyl.
19. Run a revision that reuses at least one paid result and reruns at least one affected step when budget permits.

### Interrupted-job demonstration

If safe and practical, perform a controlled process stop after a known job ID has been persisted, then restart and reconcile the same job. Do not intentionally create an ambiguous payment state for a live wallet merely to demonstrate failure handling.

The ambiguous path can remain fixture-tested if deliberately inducing it would risk duplicate spend.

### Exit gate

Phase 7 passes only when:

- at least one genuine ACP service job completes
- a genuine deliverable is captured
- actual onchain Base payment or settlement is evidenced
- Sibyl restores the real job/work record after restart
- actual known costs are recorded honestly
- no unapproved spend occurred
- the displayed provider, job, deliverable, cost, and chain states are derived from the real ACP and Base responses, not fixtures or constants

If Base partner qualification requires an additional distinct action, execute it only after separate explicit approval.

## Phase 8: Submission hardening and evidence

### Goal

Make the repository reproducible, honest, and judge-ready.

### Work

1. Run the full automated test suite from a clean environment.
2. Run the restart test again.
3. Run the baseline comparison.
4. Verify secrets are absent from repository history and fixtures.
5. Verify generated artifacts and memory databases are excluded from source control unless intentionally sanitized.
6. Update README with:
   - implemented capabilities only
   - exact setup
   - exact run commands
   - Sibyl critical read/write paths
   - deletion-test explanation
   - Virtuals and Base integration paths
   - prior-work declaration
7. Update `REFERENCES.md` with pinned versions actually used.
8. Update `STATE.md` with final verified and blocked items.
9. Execute `DEMO_RUNBOOK.md` from start to finish.
10. Capture exact evidence required by the runbook.
11. Confirm repository has an OSI-approved license. Preserve an existing compliant license. If none exists, use Apache-2.0 unless the user specifies another approved license.
12. Confirm public repository, demo-video, deployment, and partner-evidence requirements from the current hackathon submission page.

### Exit gate

The project is submission-ready only when every minimum-complete-submission item in `MASTER_PLAN.md` is either verified with end-to-end evidence or explicitly blocked with the user aware that the submission is incomplete. No fixture, mocked response, placeholder, or predetermined result may be presented as live evidence.

## Global acceptance criteria

The finished system must be able to prove:

- revision decisions are deterministic and explainable
- work survives a real process restart because Sibyl restores it
- a changed independent input does not rerun unrelated work
- a changed upstream output invalidates downstream effective input
- an unchanged upstream output can preserve downstream reuse even after upstream execution
- failed attempts never masquerade as reusable successes
- project scopes are isolated
- provider job identity survives restart
- an existing or ambiguous paid job is reconciled before replacement
- estimates, quotes, actual service cost, and gas evidence are distinct
- approval identity, scope, expiration, per-job cap, and total spending limits are enforced
- simultaneous local execution requests cannot create duplicate attempts for the same desired paid work
- removing the disposable Sibyl test store prevents authoritative cross-process recovery
- malformed provider output and unsafe artifact references fail closed
- genuine ACP and Base integrations are exercised in the completed submission
- baseline claims are accurate

## Genuine blockers that justify stopping

Stop the affected phase when:

- live ACP service discovery produces no suitable safe offering
- ACP authentication/signer setup cannot be completed
- provider price or chain differs from approved scope
- a job outcome is ambiguous and cannot be safely reconciled
- the Base action needed for the submission cannot be verified
- Sibyl APIs cannot represent authoritative work state within practical limits
- security constraints conflict with a required provider deliverable format
- the repository's existing architecture makes the planned destination ambiguous and there is no safe default
