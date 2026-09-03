# Delta State

## 2026-09-03 public landing redesign

- Replaced the rejected warm-paper editorial landing direction with a graphite, cold-white, orange, and violet execution system.
- Added an above-the-fold interactive workflow topology for launch date, visual brief, and product description scenarios, with illustrative artifacts and explicit reuse, rerun, and pending states.
- Added paid-job continuity, developer record, integration lifecycle, and compact final action sections. Application routes and engine behavior were not changed.
- Verified the complete test suite: `73 passed, 15 subtests passed`.
- Rendered the landing page at 1440, 1024, 768, and 390 CSS pixel widths. The hero visualization is visible without scrolling at desktop size, and the mobile workflow becomes a readable vertical dependency flow without horizontal overflow.

Last updated: 2026-09-03 (brand and product interface build)

## Completed

- Product direction finalized: revision planning, persistent paid-work records, and paid-job continuity.
- Planning architecture selected: small Python revision/DAG engine, Sibyl authoritative persistence, Virtuals ACP CLI adapter, Base settlement evidence, and a focused web operations workspace.
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
- Phase 5 demonstration interface implemented as a branded server-rendered operations workspace. It keeps the revision engine and Sibyl store on the server, labels deterministic fixture mode, and leaves live ACP actions unavailable until a real provider job is attached.
- Delta now has a documented product identity, code-native SVG logo and favicon, a public product site, and separate application routes for Overview, Revisions, Runs, Continuity, and Integrations. `DESIGN.md` owns the page map, brand system, interaction rules, information architecture, research basis, and staged interface roadmap.
- The public site has working calls to action and an interactive revision example labelled as illustrative. The example changes the visible keep, run-again, and waiting states without claiming provider execution. Application navigation changes server routes instead of scrolling through a long page.
- Runs renders the latest step decisions from the real state response. Continuity restores and lists actual saved outputs with output details behind progressive disclosure. Implementation names are kept on Integrations or inside technical evidence rather than repeated throughout the primary task.
- Revision metrics, run state, generated time, and memory status are derived from the same API payload as the plan. Busy controls use real request state, block duplicate activation, expose `aria-busy`, and respect reduced-motion preferences. No new live provider or chain success state was introduced.
- The Phase 5 interface supports project-scoped inputs, preview, execute, restore, decision reasons, cost separation, restart recovery messaging, escaped dynamic content, CSRF-protected state changes, and honest unavailable live-action responses.
- The interface now invalidates the current plan as soon as an input changes and explains that a fresh preview is required, while the server continues to reject stale or missing plans.
- When all current steps are reusable, the execute control stays disabled and explains that an input change plus a new preview is required before more work exists to run.
- Phase 6 comparison harness implemented in `delta.baseline` with current LangGraph `StateGraph`, node `CachePolicy`, SQLite cache, and SQLite checkpointer APIs. The harness is optional and separate from the Delta runtime.
- Phase 7 has independently checked external ACP and Base evidence for Aaga job `75656`. A fresh authenticated history read returned the completed job and exact provider deliverable. Delta parsed and persisted that live observation without creating a reusable work result. The paid execution-to-reusable-work path and settlement ingestion remain unverified, and settlement accounting was corrected during the audit.
- The ACP adapter now has an explicit reusable-work finalization boundary. It requires a non-fixture completed record, matching persisted job/provider/offering/chain/requirements identity, independently verified deliverable-hash evidence, a successful settlement receipt, and an available artifact resolution before saving a WorkResult. Fixture observations and completed status alone remain non-reusable.
- Phase 8 is not complete. The test suite and documentation have been audited, live history and protocol hash integrity are verified, but live paid-path wiring, tracked evidence, and submission packaging remain open.

## Phase status

- Phase 0: Partially complete. Foundation readiness and live ACP marketplace readiness are verified. Base qualification evidence is still absent, so the separate Base gate remains unverified.
- Phase 1: Verified. Core schemas, deterministic planning, and provider-neutral tests pass without Sibyl, ACP, or Base dependencies.
- Phase 2: Verified. The real Sibyl client is authoritative for the persisted records exercised by the recovery tests.
- Phase 3: Verified. Runtime behavior passes through the real Sibyl store with clearly labelled deterministic executors. No live provider or payment path is claimed.
- Phase 4: Verified for the no-spend implementation gate. The adapter, browse response normalization, artifact safeguards, conservative reconciliation, and real Sibyl restart path pass labelled fixture tests. Live job lifecycle, provider execution, and payment evidence remain separately unverified.
- Phase 5: Partially complete. The branded local interface and Sibyl-backed preview, execution, changed-input, error, unavailable-action, fresh-process serializer, responsive, and keyboard paths are verified. Live provider, approval, reconciliation, and settlement states remain unverified and cannot be established by fixtures.
- Phase 6: Verified. The reproducible LangGraph baseline matches Delta's measured call counts for the configured comparison cases. It does not claim Delta has unique selective caching, TTL, or restart persistence.
- **Phase 7: Partially verified and blocked.** Base receipts confirm job `75656` creation, funding of 0.01 USDC, provider submission, and settlement. The receipts show 0.009 USDC to the provider, 0.0005 USDC to Delta, and 0.0005 USDC to another recipient. A fresh authenticated ACP history read returned the same completed job, and the exact provider deliverable string matched the onchain hash under the official ACP EVM Keccak rule. Delta parsed and persisted the live observation in a disposable Sibyl scope as `reconciliation_required`, without creating a reusable WorkResult. Live paid execution through Delta, settlement ingestion, and reusable artifact persistence remain unverified.
- **Phase 8: Partially complete and blocked.** The current suite passes with 73 tests and 15 subtests. Live ACP history, adapter observation capture, protocol hash verification, and the explicit local finalization safety boundary now pass. Reproducible tracked evidence, live paid execution-to-reusable-work proof, and final submission packaging remain incomplete.

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
- A fresh child process recovered a recorded ACP observation from Sibyl. The observation was parsed and persisted through the adapter boundary, while the fixture remained explicitly marked as fixture evidence and no reusable work result was created.
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

## Phase 7 funding gate (2026-09-02 22:15 UTC)

- Delta agent EVM wallet `0x702ab9ecfb9f87f52e79157b2ea6a929b60ec576` was funded with `0.0005 ETH` for gas (no transaction history observed — appears to be a pre-allocated balance from the ACP wallet provider).
- **USDC funding verified at block 50799003, 2026-09-02 22:15 UTC.** Owner provided tx `0xbb3625fca92c1aba3099f052da2037cfa4996e258712da728c883e7cb049f222` confirmed via `eth_getTransactionReceipt`: status `0x1` (success), block 50799743, log from `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913` (native USDC on Base) transferring `100000` (6-decimal) to the Delta wallet.
- Native USDC balance: **0.10 USDC** (verified with correct checksum `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913`; an earlier check used a wrong USDC address and returned 0x).
- USDC.e (`0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6ca`): 0.
- Phase 7 ready: gas + USDC both present. Live `acp client create-job` is no longer blocked.
- Wallet is **Privy-hosted** (`"provider":"PRIVY"` per `acp agent whoami`). The raw private key is not on this machine; outbound moves go through `acp client transfer` (Privy signing) or via the Privy dashboard directly.

## Phase 7 external evidence (2026-09-02 23:00 to 23:13 UTC)

- **Job created** against Aaga `content_generation` (`019d7c71-44c9-7329-bcf6-3edb953d6711`), Base 8453, `requirements` envelope shape `{"name":"content_generation","requirement":{"topic":"AI agents in DeFi","content_type":"blog_post",...}}`. Job ID `75656`. Tx `0x7cad...` at block 50799657.
- **Budget set** to 0.01 USDC by the provider. Tx `0x6b86...` at block 50799739.
- **Funded** by Delta. Tx `0xd1d284d10916bc90934b876cec1ee3242a27de026bbd2b8191d532071f48425d` at block 50799772, USDC `Transfer(10000)` from Delta to ACP Core v2 escrow `0x238e541bfefd82238730d00a2208e5497f1832e0`.
- **Delivered** by the provider. Tx `0xd393763b6560a80d49317f7f11edf9ab349835aa0420ee4c928e5dd1a1dda445` at block 50799774. The `Submitted` event data field carries the deliverable hash `0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8`. The deliverable was a 159-word blog post.
- **Settled** by the evaluator. Tx `0x1062a1b78bf8e5686894e9e091b4b857559b784bf8a24f8f0177067957788ff8` at block 50800070: USDC `Transfer(9000)` escrow to provider, `Transfer(500)` escrow to Delta, and `Transfer(500)` escrow to another recipient, plus a `JobCompleted` event. Delta's wallet service outflow was 0.0095 USDC before gas. The prior 0.001 USDC Delta refund claim was incorrect.
- **Stored locally** under scope `delta-local-demo/phase7-live-acp-75656` by a manual metadata-persistence script. The script does not call ACP or Base, and its record is not live Delta-path evidence.
- **Restart check limitation**: a fresh Python process can read the recorded observation from the local database, but that does not prove that the live job was captured through Delta or that the artifact is reusable. The updated script now reports this state as blocked.
- **CLI limitation**: `acp client complete` returned `SESSION_NOT_FOUND` in a fresh process. The job later settled through a bundled SDK call outside the tracked Delta adapter path. This is an integration reproducibility blocker, not a verified Delta completion path.

## Audit correction (2026-09-03)

- Independent Base receipt reads confirm the recorded transaction sequence and the provider-attested deliverable hash in the ACP `Submitted` event.
- The local generic SHA-256 digest recorded in `.evidence/08_deliverable_hash.txt` differs from the provider-attested ACP Keccak hash. This is an algorithm distinction, not a provider-byte mismatch. The exact provider deliverable string now matches the attestation under the official ACP EVM hash rule, but Delta must still keep it non-reusable until the live execution, settlement, artifact, and WorkResult paths are exercised together.
- `scripts/persist_phase7.py` and `tests/test_phase7_live.py` use sanitized recorded response-shape fixtures. The script now routes create and history data through the ACP parser and observation boundary, writes no WorkResult, and does not establish a live integration.
- `.evidence/` and `.delta/` are ignored by Git. A clean clone contains neither the evidence bundle nor the local database that the old README described as proof.
- The implementation has been extended to parse the observed compact create receipt and nested history fields, and paid ACP command arguments now carry the requested chain ID. These changes are fixture-tested, not live execution evidence.
- Persisted ACP attempts now retain provider ID, offering ID and name, chain identity, and a requirements signature. Restart reconciliation blocks when returned provider, offering, job, chain, requirements, or source identity conflicts with the stored intent.
- ACP `completed` provider status now maps to local `reconciliation_required` until deliverable and settlement evidence are independently validated. It cannot create a reusable result by status alone.
- Follow-up verification passed with `72 passed, 15 subtests passed` in `14.42s`. The adapter tests cover the provider requirement-envelope correction, reusable-work finalization boundary, and HTTPS-only artifact redirects. Recorded observation import writes only an active ACP attempt and journal event, and the fresh-process reader returns `BLOCKED` as intended.

## Live ACP and artifact verification (2026-09-03)

- The official `@virtuals-protocol/acp-cli@1.0.34` was invoked through Delta's configured argument-array `npx` transport with `TS_KEYRING_BACKEND=file`. The active Delta agent remained on the restricted `ACP_ONLY` signer policy.
- `ACPAdapter.job_history("75656", chain_id=8453)` returned the real completed ACP job. The parsed record contained job `75656`, Base chain `8453`, Aaga provider `0xB0aCA700745a989A1CB859eeCfE0fD9Afbc066AA`, offering `content_generation`, the provider deliverable, and its attested hash.
- The live record was persisted through `ACPAdapter.record_observation(..., source=ACPObservationSource.LIVE)` in a disposable real Sibyl scope. The attempt restored as `reconciliation_required` and no WorkResult was created. This proves live observation capture, not live paid execution or reusable-work completion.
- The exact 2,650-byte UTF-8 deliverable string returned by ACP was hashed with the official ACP EVM implementation rule, `keccak256(toHex(deliverable))`. The computed hash matched both the ACP history hash and the onchain `Submitted` event hash.
- The generic local artifact-store SHA-256 digest remains recorded separately. Its difference from the ACP Keccak hash is expected and must not be reported as a provider-byte mismatch.
- A fresh Base-filtered browse through the same adapter returned current candidates for image generation and announcement. A dedicated translation offering was not identified in the current `translation` or `translate text` result sets, so translation mapping remains unverified.
- Current Base-filtered browse counts were `5 agents / 46 offerings` for `image generation` with `--top-k 5`, `5 / 35` for `content writing` with `--top-k 5`, `6 / 49` for `translation` with `--top-k 20`, and `20 / 167` for `translate text` with `--top-k 20`. The latter two result sets surfaced no dedicated translation offering. Search ranking is dynamic, so these are dated observations rather than hardcoded provider configuration.
- Current credible Base candidates are Syeollanga-claw (`019e524e-befb-7693-8f66-7d0856b2ca96`, `0x3e2b694d4a02b275d2b63cfb72586a99a8830577`) `ai_image_generation` (`019e524e-dbdc-7690-a771-6f70d44600f8`) at `0.05` USDC fixed with a required `prompt` and optional `width`, `height`, and `negativePrompt`, SLA 5 minutes; Artelier (`019dca55-e2d8-7234-9617-1deb6f8b48ae`, `0xdfb85530b68ca280a95beff117fd1ea7b1bb1038`) `super_image_gen` (`019dca56-1078-7d34-a619-965ad14efabd`) at `0.5` USDC fixed with required `prompt`, SLA 5 minutes; and Aaga (`019d7c71-1c9a-7969-ac65-c36b597519b7`, `0xb0aca700745a989a1cb859eecfe0fd9afbc066aa`) `content_generation` (`019d7c71-44c9-7329-bcf6-3edb953d6711`) at `0.01` USDC fixed with required `topic` and `content_type`, publication-ready content output, SLA 5 minutes. GSB Thread Writer (`019d7565-5b56-778e-8550-66ec4b179a81`, `0x2c281b4ba71e79dd91e3a9d78ed5348bc5774df9`) `write_thread` (`019d780b-0b26-7966-b540-28ea9c05a0b7`) appeared at `0.1` USDC fixed with required `topic`, array-of-tweets output, and a 5-minute SLA.

## Live validation attempt (2026-09-03)

- The approved live scope was one Aaga `content_generation` job on Base `8453`, with a maximum service amount of `0.01 USDC` plus gas. The read-only preflight confirmed signer policy `ACP_ONLY`, wallet balance `0.0905 USDC`, and the same fixed-price offering.
- Delta created ACP v2 job `75773` through `ACPAdapter.create_job`. The real receipt returned `success: true`, `protocol: "v2"`, provider `0xb0aca700745a989a1cb859eecfe0fd9afbc066aa`, offering `content_generation`, chain `8453`, and no transaction hash in the compact response.
- The installed official CLI sent the first requirement as `contentType: "requirement"` but without the required outer `name`. Aaga returned the real error `Malformed requirement for content_generation`. The same envelope was then sent through the official message command as `text`, `structured`, and runtime-supported `requirement` content types. History recorded all three corrections, but the provider did not emit `budget.set` or advance the job beyond `open` during the bounded wait.
- The current history response is `{jobId, chainId, protocol, status, entryCount, entries}`. Job `75773` remains `open` with six entries, no budget, no funding, no deliverable, and no transaction hashes. No USDC moved and no completion command was run.
- Delta reconciled job `75773` through the real history path and persisted the attempt as `active` with the job and chain identity in the disposable Sibyl scope. No WorkResult or artifact was created.
- The installed `acp job watch` help documents `--job-id` and `--timeout`, but passing the documented history chain flag to `job watch` returned `unknown option '--chain-id'`. The live validation wrapper now uses history for chain-scoped recovery and blocks funding unless history reports `budget_set` with a valid matching amount.
- `scripts/live_acp_validation.py` is an operator-gated, real-ACP validation helper. Its `create`, `fund`, and `complete` paths require an explicit approval flag, and funding and completion are blocked until the required live history states exist.
- The negative funding guard was exercised against real job `75773` with the requested `0.01` amount. It returned `Funding is blocked until ACP history reports budget_set` before invoking the funding transport.

## Unverified

- Exact live JSON fields are now verified for browse and history, including the current nested history entries. Funding and completion response shapes, direct transaction-hash fields, and a live adapter round trip through paid Delta execution remain unverified.
- The browse response does not provide an independent online-status field. The records are evidence that the authenticated query with `--online online` returned them, not proof of a separately reported provider heartbeat.
- Base qualification is still separate from this ACP receipt evidence. No Delta deployment exists, and the hackathon's final acceptance of this single ACP-on-Base flow for both partner stacks remains unconfirmed.
- It is not confirmed that one ACP job funded/settled on Base will be accepted by hackathon judges as evidence for both the Virtuals and Base partner stacks.
- Practical maximum safe entity/reference body sizes beyond the tested `421` byte work record remain unverified.
- Apache-2.0 is present in `LICENSE` and is the selected OSI-approved license.
- The final ACP provider mapping for the launch-package workflow is not locked.
- The recorded job used an owner-funded wallet. No new transaction or spending action is approved by the current audit.
- The ACP CLI is not installed as a project command and is being invoked through the current npm package. LangGraph and FastAPI are not installed in the workspace. Python 3.12.3 and Node 26.7.0 are available.
- Live provider execution, paid ACP lifecycle reconciliation, settlement ingestion, reusable WorkResult persistence, and network-cost evidence are not yet connected end to end to the runtime. Provider deliverable hash integrity is verified separately.
- The new live job `75773` does not provide a usable provider budget or deliverable. It is an open, unfunded attempt blocked by the CLI/provider requirement-envelope discrepancy. It must be reconciled before any replacement job is considered.
- The live validation attempt did not reach artifact verification, funding, completion, settlement, or live reusable-work persistence. The only verified deliverable artifact remains the separately recorded external job `75656`.
- Phase 4 live provider and offering consistency checks against requested create-job inputs are not yet verified. The adapter-level chain mismatch case is covered by a fixture test.
- Live funded-job reconciliation and chain receipt ingestion remain unverified in the runtime. The no-spend suite covers labelled fixtures and safe failure behavior; the recorded response shape now passes through the adapter, but not through a live Delta engine execution or chain receipt importer.
- Phase 4 real ACP browse, create receipt, and history shapes are represented by labelled sanitized fixtures, and the current browse/history transport has also been exercised live. This does not prove a live paid job lifecycle round trip.
- The recorded provider deliverable passes protocol-level hash verification. Runtime reusable-artifact verification remains unverified because the live observation path intentionally does not create a WorkResult and Delta's generic artifact store uses SHA-256 references.
- The pending approval request exposed only a wallet approval URL, approval ID, and `RPC request denied due to policy violation` in CLI output. Chain, destination, method, value, token amount, and gas were not exposed by the CLI, and the dashboard page could not be safely inspected through the available browser tool. No approval was opened.
- The earlier `RPC request denied due to policy violation` browse discrepancy was resolved for discovery by the owner-approved `ACP_ONLY` policy change. No exact official issue was found for the earlier behavior. No further investigation is needed for Phase 4.
- Phase 5 focused tests passed with 5 tests, including a genuinely new Python process that restored the UI state serializer from the same Sibyl store. Chromium inspection covered 375, 768, 1024, and 1440 CSS pixel widths; no unintended horizontal overflow was observed.
- The rebuilt Phase 5 interface was rechecked on 2026-09-03 at 390, 768, 1024, and 1440 CSS pixel widths. The public site, product illustration, SVG identity, favicon, application routes, compact navigation, Overview, Revisions, Runs, Continuity, and Integrations screens rendered without observed horizontal overflow. Both JavaScript files passed syntax validation, the 6 focused web tests passed, and the full suite passed with 73 tests plus 15 subtests.
- A browser-level route and interaction audit selected the Visual brief example on the public site and observed `Run again`, `Keep`, `Keep`. In Revisions, a fresh project preview returned `Rerun`, `Rerun`, `Pending dependency`; execution returned three labelled fixture outputs and disabled repeat execution; changing only the launch date invalidated the old plan and returned `Reuse`, `Rerun`, `Pending dependency`; Continuity restored three saved outputs. These states came from the running UI and real local API path.
- The Phase 5 UI positive path ran preview, deterministic execution, persisted outputs, and restore. A changed launch date produced visual reuse, announcement rerun, and translation pending dependency. Invalid project input and missing CSRF produced honest errors, and reconcile, spending approval, and settlement returned blocked or unavailable responses.
- A local Chromium keyboard audit passed the primary workflow. Tab reached the page controls, Enter activated Preview and Execute, an invalid required field moved focus to `error-summary`, and Enter on Restore loaded the persisted Sibyl state. The audit used no live or paid action.
- Phase 7 no-spend preflight was completed on 2026-09-02 with the official ACP CLI `1.0.34`. The split `configure complete` command returned `authenticated`. The default native keychain path first returned `KeyRevoked`, so the CLI was run with its supported encrypted file keychain backend, `TS_KEYRING_BACKEND=file`. This changed local credential storage selection only. It did not bypass signer policy or authorize spending.
- With that backend, `agent whoami --json` returned the active Delta identity and `agent signer-policy --json` returned `ACP_ONLY`. Ordinary and Base-filtered `acp browse ... --json` commands then completed successfully without an approval prompt. No job, funding, settlement, or transaction command was attempted.
- LangGraph `1.2.11`, `langgraph-checkpoint` `4.2.0`, and `langgraph-checkpoint-sqlite` `3.1.1` are installed in the project environment. The official SQLite cache and checkpointer paths were exercised with the current API imports.
- The measured Phase 6 matrix matched Delta's per-run fixture calls: unchanged `1,1,1` then `0,0,0`; launch-date-only `0,1,1`; visual-brief-only `1,0,0`; description change `1,1,1`; implementation change `1,0,0`; and upstream rerun with unchanged output `0,1,0`.
- The LangGraph baseline's one-second TTL expired and reran all three nodes, a second project did not reuse the first project's cache, and a genuinely fresh Python process restored checkpoint state while reusing the persistent cache with zero node calls.

## Blocked

- Phase 1 is complete for the provider-neutral core. Phases 2 and 3 are verified for Sibyl-backed deterministic execution. The recorded external ACP/Base run does not make the live Delta execution path verified.
- No further live ACP job or Base transaction can be performed without explicit user approval of exact provider, chain, action scope, and budget (the same RED gate that released Phase 7).
- The project has local Git history and an Apache-2.0 license, but no configured public remote. Public repository setup, the demo video, and required public posts remain outstanding.
- Phase 7 and Phase 8 remain blocked until the live paid execution path, reusable-work persistence, evidence packaging, and submission requirements are handled honestly.
- ACP job `75773` is a known open job with no monetary outcome. Do not create a replacement or attempt funding until the provider requirement state is resolved through an officially supported path.

## Next

When the user dispatches the builder:

1. Finish the live-path audit fixes before calling Phase 7 or Phase 8 complete. The current findings are recorded in this file and the existing local `.evidence/PHASE7_STEP_BY_STEP.md` record. Live read-only capture and protocol hash verification are complete; the remaining gap is live paid execution through Delta with honest settlement and reusable-work persistence.
2. If the user wants a second live job (e.g. to extend the demo with a visual or a translation step), Aaga `content_generation` is still the cheapest live provider (0.01 USDC). Get explicit approval per RED gate before any new funding.
3. Keep the live/fixture split honest: do not let any new fixture or test service be presented as a live ACP, Base, or wallet result. The `restart_test.py` and `test_phase7_live.py` patterns are the templates for any future live evidence.
4. If the user asks to drain the remaining wallet, run a read-only balance check first and require explicit per-action approval before any transfer. Never put a raw key in chat.
