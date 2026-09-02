# Delta State

Last updated: 2026-09-02

## Completed

- Product direction finalized: revision planning, persistent paid-work records, and paid-job continuity.
- Planning architecture selected: small Python revision/DAG engine, Sibyl authoritative persistence, Virtuals ACP CLI adapter, Base settlement evidence, minimal web demonstration.
- Official starting references reviewed for hackathon rules, submissions, Sibyl Memory, Virtuals ACP, LangGraph caching/persistence, and Base network documentation.
- Repository planning package drafted.
- Phase 0 workspace review found only planning documents, with no application source, package metadata, tests, selected framework, or license file at that time.
- Applicable development, writing, product design, and UI/UX guidance reviewed for the implementation roadmap.
- Implementation plan hardened with explicit gates for approval scope, cumulative spending, single-writer execution, Sibyl deletion proof, hostile provider output, artifact safety, cost semantics, and interface-state verification.
- Project-wide no-simulated-success and end-to-end verification rules added to the builder instructions and phase-owned documentation.
- Phase 0 ACP identity and Sibyl setup completed within the authorized non-spending scope.
- Phase 1 provider-neutral core implemented with explicit bindings, deterministic signatures, workflow validation, revision preview decisions, freshness checks, approval boundaries, and labelled deterministic fixtures.
- Phase 2 Sibyl-backed store implemented for work results, attempts, revision plans, active attempt heads, execution events, and artifact references.
- Phase 3 deterministic runtime implemented for ready-step execution, persisted attempt ownership, downstream reevaluation, failure and blocked states, cost semantics, and single-writer duplicate suppression.
- Phase 4 ACP adapter contract implemented with argument-array execution, JSON parsing, redaction, timeout ambiguity, persisted action intent, cumulative spend reservations, lifecycle mapping, and sanitized fixture transport tests.
- Phase 4 no-spend implementation gate completed with safe artifact handling, conservative ambiguous-job matching, and provider versus chain funding reconciliation fixtures.
- ACP CLI `1.0.34` was reauthenticated and inspected without approving the pending request. `agent whoami --json`, `agent signer-policy --json`, `policy global --json`, `policy list --json`, and `wallet address --json` completed successfully.
- The Delta signer policy was changed through the owner-approved dashboard flow from `DENY_ALL` to the official restricted `ACP_ONLY` preset. Verification returned policy ID `he16pbgn1s3uthpd6rbskclm` without exposing signer material.
- Read-only ACP discovery succeeded under `ACP_ONLY` for image generation, announcement and marketing copywriting, and translation, both without a chain filter and with Base chain ID `8453`. No job or transaction command was run.
- The live browse response shape is `{data: [...]}` with agent identity, public EVM address, role, cluster, rating, nested chain records, and nested offering records containing IDs, requirements, deliverable, SLA, pricing, funding flag, and hidden flag. The `--online online` filter returned records, but the response has no separate online-status field.
- `delta.providers.acp` now normalizes that browse shape, accepts both object and string requirement schemas observed live, preserves explicit unknown availability, and defaults ordinary browse to no chain filter. A labelled marketplace fixture and malformed-shape tests cover the contract.
- Phase 5 demonstration interface implemented as a minimal server-rendered WSGI page. It keeps the revision engine and Sibyl store on the server, labels deterministic fixture mode, and leaves live ACP actions unavailable until a real provider job is attached.
- The Phase 5 interface supports project-scoped inputs, preview, execute, restore, decision reasons, cost separation, restart recovery messaging, escaped dynamic content, CSRF-protected state changes, and honest unavailable live-action responses.
- The interface now invalidates the current plan as soon as an input changes and explains that a fresh preview is required, while the server continues to reject stale or missing plans.
- When all current steps are reusable, the execute control stays disabled and explains that an input change plus a new preview is required before more work exists to run.
- Phase 6 comparison harness implemented in `delta.baseline` with current LangGraph `StateGraph`, node `CachePolicy`, SQLite cache, and SQLite checkpointer APIs. The harness is optional and separate from the Delta runtime.

## Phase status

- Phase 0: Partially complete. Foundation readiness and live ACP marketplace readiness are verified. Base qualification evidence is still absent, so the separate Base gate remains unverified.
- Phase 1: Verified. Core schemas, deterministic planning, and provider-neutral tests pass without Sibyl, ACP, or Base dependencies.
- Phase 2: Verified. The real Sibyl client is authoritative for the persisted records exercised by the recovery tests.
- Phase 3: Verified. Runtime behavior passes through the real Sibyl store with clearly labelled deterministic executors. No live provider or payment path is claimed.
- Phase 4: Verified for the no-spend implementation gate. The adapter, browse response normalization, artifact safeguards, conservative reconciliation, and real Sibyl restart path pass labelled fixture tests. Live job lifecycle, provider execution, and payment evidence remain separately unverified.
- Phase 5: Partially complete. The local deterministic interface and Sibyl-backed preview, execution, changed-input, error, unavailable-action, fresh-process serializer, responsive, and keyboard paths are verified. Live provider, approval, reconciliation, and settlement states remain unverified and cannot be established by fixtures.
- Phase 6: Verified. The reproducible LangGraph baseline matches Delta's measured call counts for the configured comparison cases. It does not claim Delta has unique selective caching, TTL, or restart persistence.

## Verified

- Sibyl hackathon build window is September 1 through September 10, 2026, with submission due September 10 at 23:59 UTC.
- Hackathon gate requires Sibyl Memory to be load-bearing. The demo must show cold-start recall and the README must point to critical memory reads/writes.
- A public GitHub repository under an OSI-approved license and a 2 to 5 minute demo are required.
- Base and Virtuals are separate partner-stack opportunities. Rules require an executed onchain action for Base bonus evidence and an exercised ACP-native integration for Virtuals.
- Sibyl Memory documents a local Python SDK, five memory tiers, and tenant isolation. The install docs require Python 3.10 or newer.
- LangGraph supports node caching based on node input, custom `key_func`, TTL, checkpoint persistence, cross-thread stores, and persistent SQLite/Postgres checkpointers.
- Current ACP v2 documentation describes service offerings, service-only jobs, USDC escrow, deterministic job phases, deliverable submission, completion/rejection, and multi-chain job selection.
- Current ACP examples use Base mainnet chain ID 8453 for job creation/funding/completion.
- ACP CLI documents JSON output, job history, `job watch`, and event streams.
- Current ACP guidance requires `acp events listen` before live job creation and documents `acp browse ... --json` for read-only discovery.
- Current ACP guidance documents split authentication for scripts: `acp configure start --json` followed by `acp configure complete --request-id ... --json`.
- ACP split authentication completed successfully and returned an authenticated public wallet identity.
- ACP agent `Delta` was created and confirmed active by both `agent list --json` and `agent whoami --json`. Non-secret identity: agent ID `01a0625f-cdf0-75e4-8f4f-f8d85c3adede`, role `HYBRID`, public EVM wallet `0x702ab9ecfb9f87f52e79157b2ea6a929b60ec576`.
- The active Delta agent has no offerings. Its signer is configured with the official restricted `ACP_ONLY` policy. No spending authorization was granted.
- Sibyl CLI `0.4.0` and client `0.8.0` are installed in the project-local `.venv`.
- `sibyl init` completed through browser activation. `sibyl status` reported the FREE tier and `sibyl health` reported all green with schema version `4` and a real tenant ID.
- The Sibyl smoke test passed in a disposable local database across separate Python processes. Process A wrote representative work metadata, HOT state, a COLD journal event, and REFERENCE artifact metadata. Process B recovered the same values, and a second tenant retrieved none of them. The work metadata was `421` bytes after canonical JSON encoding.
- The planned Sibyl tier model matches the installed API. Verified methods are `MemoryClient.local`, `set_state` / `get_state`, `set_entity` / `get_entity`, `write_event` / `read_events`, and `set_reference` / `get_reference`, with explicit `tenant_id` selection. `get_reference` returns the body as a JSON string and metadata as a structured object.
- npm registry metadata reports `@virtuals-protocol/acp-cli` version 1.0.34 with the `acp` binary and Node `>=20.19.0` engine requirement. Local Node 26.7.0 satisfies it.
- Base official docs identify Base mainnet chain ID 8453 and Base Sepolia chain ID 84532.
- Current hackathon rules identify Base deployment as the eligibility floor and an executed onchain action as Base partner bonus evidence.
- The implementation order is now summarized in `IMPLEMENTATION_PLAN.md`, with the reusable engine and persistence preceding the demonstration interface and live spending.
- `delta.core` now validates explicit workflow bindings, rejects cycles and invalid JSON-like values, computes scope and implementation-sensitive signatures, evaluates freshness, previews reuse/rerun/pending-dependency decisions, and validates spend approvals against plan, scope, provider, offering, chain, action, expiry, currency, and caps.
- `delta.fixtures` exposes input-sensitive, clearly labelled deterministic services for visual, announcement, and translation tests, with call counters and configurable failures.
- Phase 1 verification passed with 10 tests using `python3 -m unittest discover -s tests -v`, plus Python bytecode compilation. The tests include positive and changed or invalid cases.
- `delta.store.SibylStore` uses the documented Sibyl client import `sibyl_memory_client`, explicit `MemoryClient.local(..., tenant_id=...)`, WARM entities for work, attempts, and plans, HOT state for active attempt heads, the COLD journal for events, and REFERENCE records for artifact metadata.
- The real Sibyl-enabled suite passed with 11 tests using `.venv/bin/python -m unittest discover -s tests -v`. The Phase 2 test used separate child processes for write, recovery, and post-deletion reads.
- The fresh process recovered the representative work output, provider job identity, plan, active attempt, event, and artifact reference. A second project could not retrieve the first project's result, and a newly initialized client after deleting the disposable Sibyl database restored nothing.
- The same real-store test recovered a result whose artifact was marked unavailable and confirmed that the core reuse check rejected it.
- The persisted representative work record was measured from the real Sibyl entity body. Artifact bytes were not written to Sibyl; only a content hash, size, media type, availability, and durable reference URI were persisted.
- `delta.execute.DeltaEngine` persists a plan before execution, claims an active attempt before calling an executor, persists successful output before downstream reevaluation, and records failed or blocked states without creating reusable results.
- The real Sibyl-backed Phase 3 suite passed with 23 tests using `.venv/bin/python -m unittest discover -s tests -v`. It covers unchanged reuse, launch-date, visual-brief, shared-description, expiry, implementation, unchanged upstream output, failure and retry, project isolation, cost and reason semantics, pending dependencies, and concurrent duplicate suppression.
- Concurrent requests for the same desired step input produced one fixture call. The second request observed the persisted active attempt and returned `blocked`. Independent steps continued through the scheduler.
- Phase 4 verification passed with 26 tests, and the complete suite passed with 49 tests using `.venv/bin/python -m unittest discover -s tests -v`.
- ACP runner tests verified argument arrays with `shell=False`, forced JSON output, safe redaction, nonzero failure, parse failure, and side-effect timeout ambiguity.
- ACP lifecycle fixtures for open, budget-set, funded, submitted, completed, rejected, and expired states mapped through the adapter. Fixtures are marked `fixture: true`; completed fixture data contains no transaction hashes and is not settlement evidence.
- ACP create-job fixture execution persisted the action intent in Sibyl before the transport call, recorded provider job identity without claiming completion, and blocked concurrent duplicate attempts for the same step and input signature.
- A create response with a mismatched chain is recorded as ambiguous rather than accepted as the requested job.
- ACP spend reservations were persisted in Sibyl and cumulative caps, scope, currency, and action checks blocked before the transport call where approval was invalid.
- Read-only history, watch, deliverable lookup, and known-job reconciliation tests consumed returned fixture response data rather than constants.
- A fresh child process recovered a funded-state ACP attempt from Sibyl, queried its persisted provider job ID through the adapter, and recorded the returned lifecycle state. The fixture was still explicitly marked as fixture evidence.
- Artifact handling now creates generated local identifiers, confines local files to the configured artifact root, permits only credential-free HTTPS for remote resolution, enforces size and timeout limits, and verifies content hashes before returning an available reference.
- Reconciliation matching now returns `attach`, `manual`, or `blocked`. It never selects the first candidate when there are zero, multiple, missing-identity, or conflicting provider, offering, chain, requirements, or transaction matches.
- The installed ACP guidance and browse help describe browse as a marketplace search operation with `--chain-ids` filtering and state that authenticated users can browse without onchain signing. Under the owner-approved `ACP_ONLY` policy, the same CLI returned live browse data without a transaction prompt.

## Latest ACP discovery

- On 2026-09-02, ordinary read-only browse under `ACP_ONLY` returned 5 agents for each query. The image-generation query returned 46 offerings, announcement and marketing copywriting returned 33, and translation returned 67. All returned offerings had `isHidden: false` in these responses.
- The same three queries with `--chain-ids 8453` returned the same counts. Every returned agent had an active chain record for Base in the filtered results.
- Product visual candidates include Syeollanga-claw `ai_image_generation` (`019e524e-dbdc-7690-a771-6f70d44600f8`), 0.05 USDC fixed, 5 minutes, and Artelier `super_image_gen` (`019dca56-1078-7d34-a619-965ad14efabd`), 0.50 USDC fixed, 5 minutes. Both support Base. The former requires `prompt` and accepts optional `width`, `height`, and `negativePrompt`.
- Announcement candidates include Aaga `content_generation` (`019d7c71-44c9-7329-bcf6-3edb953d6711`), 0.01 USDC fixed, 5 minutes, and GSB Thread Writer `write_thread` (`019d780b-0b26-7966-b540-28ea9c05a0b7`), 0.10 USDC fixed, 5 minutes. Both support Base. Aaga requires `topic` and `content_type`, with `press_release`, `social_media_post`, and `marketing_copy` among the declared content types.
- Translation returned OpenClaw Chile `Translation Service EN/ES/PT` (`01a0541e-e520-7c8c-90ce-b0b593c2b419`), 8 USDC fixed, 1440 minutes, with Base support. Its live requirements are the string schema `{"source_lang,target_lang,words,format}` and its deliverable is `{"format":"MD + supporting files","fields":["main","variants"]}`.
- Provider public wallet addresses, offering IDs, chain IDs, prices, requirement schemas, deliverables, SLA values, `requiredFunds`, and `isHidden` were read from the live response. The response did not expose a separate online flag, transaction identity, job identity, or lifecycle data.

## Unverified

- Exact JSON response fields for current ACP job creation, funding, completion, history, and transaction hashes remain unverified. The live response verification covered marketplace browse only.
- The browse response does not provide an independent online-status field. The records are evidence that the authenticated query with `--online online` returned them, not proof of a separately reported provider heartbeat.
- Base qualification findings remain limited to the documented chain and hackathon requirements. No deployment or transaction evidence exists.
- It is not confirmed that one ACP job funded/settled on Base will be accepted by hackathon judges as evidence for both the Virtuals and Base partner stacks.
- Practical maximum safe entity/reference body sizes beyond the tested `421` byte work record remain unverified.
- No OSI-approved license file has been selected yet.
- The final ACP provider mapping for the launch-package workflow is not locked.
- No Base balance or spending budget has been verified. The Delta ACP agent and restricted signer identity are configured, but no transaction authorization or monetary action is approved.
- The ACP CLI is not installed as a project command and is being invoked through the current npm package. LangGraph and FastAPI are not installed in the workspace. Python 3.12.3 and Node 26.7.0 are available.
- Live provider execution, ACP lifecycle reconciliation, and network-cost evidence are not yet connected to the runtime.
- Phase 4 live provider and offering consistency checks against requested create-job inputs are not yet verified. The adapter-level chain mismatch case is covered by a fixture test.
- Live funded-job reconciliation and chain receipt evidence remain unverified. The no-spend suite covers a known funded fixture after a fresh process, malformed and conflicting provider records, safe artifact paths and URLs, and zero or multiple matching replacement candidates.
- Phase 4 real ACP browse response shape is verified under `ACP_ONLY`. Real history and job response shapes remain unverified because no paid job was created.
- The pending approval request exposed only a wallet approval URL, approval ID, and `RPC request denied due to policy violation` in CLI output. Chain, destination, method, value, token amount, and gas were not exposed by the CLI, and the dashboard page could not be safely inspected through the available browser tool. No approval was opened.
- The earlier `RPC request denied due to policy violation` browse discrepancy was resolved for discovery by the owner-approved `ACP_ONLY` policy change. No exact official issue was found for the earlier behavior. No further investigation is needed for Phase 4.
- Phase 5 focused tests passed with 5 tests, including a genuinely new Python process that restored the UI state serializer from the same Sibyl store. Chromium inspection covered 375, 768, 1024, and 1440 CSS pixel widths; no unintended horizontal overflow was observed.
- The Phase 5 UI positive path ran preview, deterministic execution, persisted outputs, and restore. A changed launch date produced visual reuse, announcement rerun, and translation pending dependency. Invalid project input and missing CSRF produced honest errors, and reconcile, spending approval, and settlement returned blocked or unavailable responses.
- A local Chromium keyboard audit passed the primary workflow. Tab reached the page controls, Enter activated Preview and Execute, an invalid required field moved focus to `error-summary`, and Enter on Restore loaded the persisted Sibyl state. The audit used no live or paid action.
- Phase 7 no-spend preflight was completed on 2026-09-02 with the official ACP CLI `1.0.34`. The split `configure complete` command returned `authenticated`. The default native keychain path first returned `KeyRevoked`, so the CLI was run with its supported encrypted file keychain backend, `TS_KEYRING_BACKEND=file`. This changed local credential storage selection only. It did not bypass signer policy or authorize spending.
- With that backend, `agent whoami --json` returned the active Delta identity and `agent signer-policy --json` returned `ACP_ONLY`. Ordinary and Base-filtered `acp browse ... --json` commands then completed successfully without an approval prompt. No job, funding, settlement, or transaction command was attempted.
- LangGraph `1.2.11`, `langgraph-checkpoint` `4.2.0`, and `langgraph-checkpoint-sqlite` `3.1.1` are installed in the project environment. The official SQLite cache and checkpointer paths were exercised with the current API imports.
- The measured Phase 6 matrix matched Delta's per-run fixture calls: unchanged `1,1,1` then `0,0,0`; launch-date-only `0,1,1`; visual-brief-only `1,0,0`; description change `1,1,1`; implementation change `1,0,0`; and upstream rerun with unchanged output `0,1,0`.
- The LangGraph baseline's one-second TTL expired and reran all three nodes, a second project did not reuse the first project's cache, and a genuinely fresh Python process restored checkpoint state while reusing the persistent cache with zero node calls.

## Blocked

- Phase 1 is complete for the provider-neutral core. Phase 2 and Phase 3 are verified for Sibyl-backed deterministic execution; live external execution remains future work.
- No live ACP job or Base transaction can be performed without explicit user approval of exact provider, chain, action scope, and budget.
- Repository-local documentation cannot be merged because no project repository is available in this environment. The planning files are provided as a standalone package for later copy-in.
- Phase 0 foundation readiness and live ACP marketplace readiness are verified. Overall Phase 0 remains `Partially complete` because Base qualification evidence is not exercised.
- Phase 1 through Phase 4 no-spend implementation work is verified. Phase 5 local implementation is partially complete because live provider, approval, reconciliation, and settlement states remain unverified. Phase 6 baseline verification is complete. Live ACP and Base gates remain separate prerequisites for final submission readiness.
- Phase 7 preflight is complete. Live paid execution remains blocked until the user approves one exact provider, offering, chain, maximum service spend, wallet-funding requirement, and broadcast action scope.

## Next

When the user dispatches the builder:

1. Keep Phase 5's live-state gap explicit: do not present fixture UI states as provider or settlement evidence.
2. Keep the selected first live validation candidate staged as Aaga `content_generation` on Base, with a maximum service cap of `0.01 USDC` unless the user approves a different scope.
3. Before any paid action, request explicit approval for the exact provider, offering, chain, cap, wallet-funding requirement, broadcast actions, and whether settlement is separate.
4. Verify live ACP job JSON contracts and the Base qualification path during the approved run. Do not broadcast or fund anything before that approval.
