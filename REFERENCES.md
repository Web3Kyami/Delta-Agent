# Delta References and Verification Notes

Access date for the planning review: 2026-09-02.

## Phase 0 environment

Verified on 2026-09-02:

- Python 3.12.3 is available.
- Node.js 26.7.0 and npm 11.19.0 are available.
- `acp` is not installed as a local project command and is invoked through the current npm package. The Sibyl CLI is available as `.venv/bin/sibyl` in the project-local virtual environment.
- Sibyl CLI `0.4.0` and `sibyl-memory-client` `0.8.0` are installed in `.venv`. LangGraph `1.2.11`, `langgraph-checkpoint` `4.2.0`, and `langgraph-checkpoint-sqlite` `3.1.1` are installed for the Phase 6 baseline. FastAPI is not installed.
- The Phase 0 workspace review found no application package metadata, tests, selected framework, license file, or usable Git repository metadata at that time.
- npm registry metadata reports `@virtuals-protocol/acp-cli` 1.0.34, with the `acp` binary and Node `>=20.19.0` engine requirement.
- Split ACP authentication completed successfully. ACP agent `Delta` was created and confirmed active by `agent list --json` and `agent whoami --json`.

This document owns official sources, observed versions, prior-work notes, licensing notes, and unresolved integration questions.

## Hackathon

### Sibyl Labs Hackathon Rules

URL: https://hack.sibyllabs.org/rules

Verified during planning:

- Build window: September 1 through September 10, 2026.
- All deadlines are UTC.
- Sibyl Memory must be load-bearing.
- Cold-start recall must appear in the demo video.
- README must point judges to critical memory reads and writes.
- Public GitHub repository must use an OSI-approved license, with MIT or Apache-2.0 given as examples.
- Demo video length is 2 to 5 minutes.
- Base partner evidence requires an executed onchain action for the bonus.
- Virtuals partner evidence can be an ACP job or another exercised Virtuals-native integration.
- Partner stacks count only when they do real work in the demo.

Implementation consequence:

Delta must demonstrate that deleting Sibyl materially breaks cross-run revision planning and paid-job recovery.

### Sibyl Labs Submissions

URL: https://hack.sibyllabs.org/submissions

Verified during planning:

- Submission is managed from the registered build page.
- Finished submission includes public repo, 2 to 5 minute demo, team/partner stacks, and memory implementation note.
- Submission deadline shown as September 10, 23:59 UTC.

## Sibyl Memory

### Concepts

URL: https://docs.sibyllabs.org/memory/concepts

Last-updated date shown by source during planning: 2026-06-29.

Verified:

- HOT state uses `set_state` / `get_state`.
- WARM entities use `set_entity` / `get_entity`.
- COLD journal uses `write_event` / `read_events`.
- REFERENCE records use `set_reference` / `get_reference`.
- Archive operations exist.
- Local SDK example uses `MemoryClient.local(...)`.
- Entity uniqueness is enforced within tenant/category/name.
- Reads and writes are tenant-scoped.

Planned use:

- WARM entities for work results and attempt records.
- HOT state for small current-head pointers.
- COLD journal for concise transition history.
- REFERENCE tier may be used for artifact metadata if the installed API proves appropriate, otherwise artifact metadata stays in the work entity.

Unresolved:

- practical maximum safe entity/reference body size on the hackathon environment

These must be verified before final store schema is frozen.

### Install

URL: https://docs.sibyllabs.org/memory/install

Last-updated date shown by source during planning: 2026-06-29.

Verified:

- Requires Python 3.10 or newer.
- The full CLI installation is `sibyl-memory-cli[mcp]`; the local SDK can also be installed separately as `sibyl-memory-client`.
- `sibyl-memory-client` can be installed directly for SDK use.
- `sibyl init` handles account initialization.
- Credentials are stored under the user's Sibyl directory with restrictive file mode according to the docs.
- `sibyl status` and `sibyl health` are available for verification.

Observed during Phase 0 on 2026-09-02:

- `sibyl init` completed through browser activation.
- `sibyl status` reported the FREE tier, and `sibyl health` reported schema version `4` with a real tenant ID.
- A disposable smoke test passed across separate Python processes using `MemoryClient.local(path, tenant_id=...)`.
- Verified persistence methods are `set_state` / `get_state`, `set_entity` / `get_entity`, `write_event` / `read_events`, `set_reference` / `get_reference`, and `list_entities`.
- Work metadata of `421` bytes was written and recovered. A second tenant could not read the first tenant's state, entity, event, or reference.
- `get_reference` returns the body as a JSON string and metadata as a structured object. This serialization detail must be handled by the Delta adapter.

Observed during Phase 2 on 2026-09-02:

- The installed Python import is `sibyl_memory_client`; it exposes `MemoryClient` and `NotFoundError`.
- `SibylStore` uses `MemoryClient.local(path, tenant_id=..., tier=...)`, then uses `set_entity` / `get_entity` for WARM records, `set_state` / `get_state` for HOT active-attempt heads, `write_event` / `read_events` for COLD transition events, and `set_reference` / `get_reference` for artifact metadata.
- A real fresh-process test recovered work, attempts, plans, active state, events, and artifact metadata. Deleting the disposable memory database prevented recovery in a new process, and a second project scope could not retrieve the first project's work result.
- The adapter uses hashed, scope-bound keys and validates the persisted scope before decoding records. Inline records are limited to 64 KiB; large artifact bytes must remain outside Sibyl.
- Exact-key Delta work, attempt, and plan lookups are implemented as hashed WARM entity names. Active attempt heads use hashed HOT state keys.

## Virtuals ACP

### ACP Overview

URL: https://os.virtuals.io/acp/overview/

Verified:

- Current ACP is described as the reference implementation of ERC-8183.
- Current ACP supports multi-chain jobs.
- Current agent roles are Client, Provider, and optional Evaluator.
- Developer interfaces include Node SDK and CLI.
- CLI is positioned for shell-based agents, scripted workflows, and human-operated job management.
- Every CLI command supports `--json` for machine-readable output.
- Current docs list ACP Core on Base mainnet.

### Core Concepts and Job Lifecycle

URL: https://os.virtuals.io/acp/concepts

Verified:

- Offerings include pricing, SLA, requirements, and deliverable description.
- Jobs are onchain smart-contract engagements.
- Service-only jobs exist.
- Documented lifecycle is `open -> budget_set -> funded -> submitted -> completed`, with rejected and expired terminal alternatives.
- Funding locks USDC in escrow.
- Completion releases escrow to provider.
- Rejection returns escrow to client.
- Deliverables can be carried as job messages.

Implementation consequence:

Delta must preserve provider job ID, chain ID, lifecycle state, quote, deliverable, and settlement evidence so a restart can reconcile before any replacement spend.

### Client Workflow

URL: https://os.virtuals.io/acp/cli/client-workflow

Verified:

- Current examples show `acp client create-job` with `--chain-id 8453`.
- Requirements are validated against offering schema for standard offering jobs.
- Client funding uses the provider budget.
- Client completion releases escrow.
- Job watch can block until the job needs action.
- Exit codes distinguish completed, rejected, expired, and errors/timeouts.
- The current client workflow requires `acp events listen` before creating a job.
- The documented read-only discovery path uses `acp browse ... --json`.

Important observation:

The current docs require an event listener for the event-driven workflow, while `job watch` is offered as a simpler single-job alternative. Delta must run the listener for live progress when required, but must not make it the only persistence or recovery mechanism. Persisted Delta state and ACP job history remain authoritative for restart reconciliation.

### ACP Architecture

URL: https://os.virtuals.io/acp/architecture

Verified:

- Jobs use smart contracts with escrow/state management.
- An event system streams typed state transitions.

### ACP CLI repository

URL: https://github.com/Virtual-Protocol/acp-cli

Observed during planning:

- CLI supports machine-readable JSON output according to project documentation.
- Current repository documents `acp job history`, `acp job watch`, event streaming, wallet policies, and Base chain examples.
- Current repository documents `acp configure start --json` and `acp configure complete --request-id ... --json` as the split authentication flow for scripts and output-captured runners.
- Current repository identifies `acp skill print` and `acp skill check` as version-matched operating guidance.
- Repository license: ISC.

### ACP CLI package

URL: https://www.npmjs.com/package/@virtuals-protocol/acp-cli

Observed during Phase 0 on 2026-09-02:

- npm registry metadata reports package version `1.0.34`.
- The package exposes the `acp` binary.
- The package engine requirement is Node `>=20.19.0`.
- `acp skill check --against 1.0.28 --json` reported installed CLI version `1.0.34` and `upToDate: false`; the authoritative bundled `SKILL.md` at the returned path was read before continuing.
- Split authentication completed on 2026-09-02 and returned an authenticated public wallet identity.
- ACP agent `Delta` was created first without a signer. After authorized signer setup, `agent list --json` returned one agent, and `agent whoami --json` confirmed the same active agent.
- Non-secret agent identity: ID `01a0625f-cdf0-75e4-8f4f-f8d85c3adede`, role `HYBRID`, public EVM wallet `0x702ab9ecfb9f87f52e79157b2ea6a929b60ec576`.
- The active agent has no offerings. A P256 signer was registered and, after owner approval through `acp agent set-signer-policy`, its policy was changed from `DENY_ALL` to the official restricted `ACP_ONLY` preset. Verification returned policy ID `he16pbgn1s3uthpd6rbskclm` without exposing key material.
- Under `ACP_ONLY`, ordinary read-only browse succeeded for image generation, announcement and marketing copywriting, and translation. Base-filtered repeats using `--chain-ids 8453` also succeeded. No job or transaction command was run.
- The local workspace has Node `26.7.0`, which satisfies the package requirement.
- The package is not installed globally in the workspace.

Observed during the Phase 7 no-spend preflight refresh on 2026-09-02:

- The split authentication completion returned `authenticated` for the public Delta wallet identity.
- The default native keychain path returned `KeyRevoked` before API access. Running the official CLI with `TS_KEYRING_BACKEND=file` used the package's encrypted file backend and allowed read-only identity, signer-policy, and browse checks to complete. No signer secret was printed or persisted in project files.
- `agent whoami --json` confirmed the active Delta agent, and `agent signer-policy --json` returned `ACP_ONLY` with signer ID `yvzs8yrj90oaz4qnspe87ncx` and policy ID `he16pbgn1s3uthpd6rbskclm`.
- Ordinary browse and `--chain-ids 8453` browse each returned 5 agents for image generation, 5 for announcement and marketing copywriting, and 5 for translation. The corresponding offering counts were 46, 33, and 67. No job or transaction command was run.
- The live browse envelope and offering fields matched the adapter fixture contract. Current records expose provider and offering identity, chain records, requirements, deliverable, `slaMinutes`, `priceType`, `priceValue`, `requiredFunds`, and `isHidden`. They do not expose a separate online heartbeat, job identity, transaction identity, or lifecycle state.

Observed during Phase 4 adapter verification on 2026-09-02:

- `delta.providers.acp` uses argument-array subprocess execution with `shell=False`, appends `--json`, redacts credential-shaped output, and records command failure, parse failure, timeout, and ambiguous side-effect outcomes separately.
- The adapter uses the documented `acp browse`, `acp job history`, `acp job watch`, `acp client create-job`, `acp client fund`, `acp client complete`, and `acp client reject` command shapes. Live verification in this task covered browse only. No job or transaction command was run.
- ACP action intent and cumulative service-spend reservations are written through the real Sibyl store before the adapter invokes a side-effecting transport call.
- Sanitized lifecycle fixtures cover open, budget-set, funded, submitted, completed, rejected, and expired states. They are explicitly marked as fixtures and are not provider or settlement evidence.
- Phase 4 artifact tests cover generated local identifiers, root confinement, missing files, HTTPS-only remote references, timeout and transport errors, size limits, and content-hash mismatch before availability.
- Phase 4 reconciliation tests cover exact attachment, zero and multiple candidate manual states, provider/offering/transaction conflicts, ambiguous paid-action retry blocking, and provider versus chain funding disagreement.
- The Phase 4 test suite passed with 26 tests, and the complete project suite passed with 49 tests using the project-local Sibyl environment.
- A fresh Phase 4 ACP session was reauthenticated through the official split flow. `agent whoami --json` returned the active Delta identity with top-level identity, wallet, role, provider, chain, offering, resource, and social collections. After the owner-approved policy change, ordinary and Base-filtered browse returned provider data without a transaction prompt.
- Additional read-only CLI inspection returned version `1.0.34`, active Delta identity, signer policy `ACP_ONLY`, zero custom policies, the standard Ethereum `DENY_ALL` and `ACP_ONLY` presets plus their Solana counterparts, and the Delta EVM wallet address. No spending policy or monetary action was authorized.
- Installed browse help exposes the documented query, `--chain-ids`, `--sort-by`, `--top-k`, `--online`, `--cluster`, `--mode`, and `--legacy` options. The bundled version-matched guidance says authenticated users can browse without onchain signing, while marketplace job actions require a signer. This matches the successful `ACP_ONLY` discovery.
- The official issue index was checked on 2026-09-02. No exact browse-policy issue was found. Related open issue: `Dashboard returns HTTP 500 when approving restricted signer`. The issue index is at https://github.com/Virtual-Protocol/acp-cli/issues.
- The real browse envelope is `{data: [...]}`. Each agent record contains `id`, `name`, `walletAddress`, `role`, `cluster`, `rating`, `chains`, and `offerings`. Each offering contains `id`, `agentId`, `name`, `requirements`, `deliverable`, `slaMinutes`, `priceType`, `priceValue`, `requiredFunds`, and `isHidden`. The live response accepts both object requirements and string requirements, and has no separate online-status field.
- Ordinary browse counts were 5 agents and 46 offerings for image generation, 5 agents and 33 offerings for announcement and marketing copywriting, and 5 agents and 67 offerings for translation. Base-filtered repeats returned the same counts, with active Base chain records in the returned results.
- Best observed launch-package candidates: Syeollanga-claw `ai_image_generation` (`019e524e-dbdc-7690-a771-6f70d44600f8`), provider `019e524e-befb-7693-8f66-7d0856b2ca96`, public address `0x3e2b694d4a02b275d2b63cfb72586a99a8830577`, fixed price `0.05`, Base support, prompt required with optional width, height, and negativePrompt, string deliverable, 5 minute SLA; Aaga `content_generation` (`019d7c71-44c9-7329-bcf6-3edb953d6711`), provider `019d7c71-1c9a-7969-ac65-c36b597519b7`, public address `0xb0aca700745a989a1cb859eecfe0fd9afbc066aa`, fixed price `0.01`, Base support, topic and content_type required, publication-ready content deliverable, 5 minute SLA; OpenClaw Chile `Translation Service EN/ES/PT` (`01a0541e-e520-7c8c-90ce-b0b593c2b419`), provider `01a029a8-926b-7400-bf8b-c0104e5595a5`, public address `0x1d6b626b26926534983599681956cf0ee342159c`, fixed price `8`, Base support, string requirements `{source_lang,target_lang,words,format}`, Markdown plus supporting files deliverable, 1440 minute SLA.

Builder requirement:

Record and pin the version actually used during final validation. Re-check the package metadata and the installed `acp skill check --json` result before live work.

### Live ACP questions that remain unresolved

These require authenticated read-only discovery or local CLI verification:

1. Which currently online offerings can provide the launch-package visual, announcement, and translation tasks?
2. What are their actual prices, SLAs, requirement schemas, and deliverable formats?
3. Which support Base mainnet service jobs?
4. What exact JSON fields are returned by create, fund, complete, history, and watch in the chosen CLI version?
5. Are transaction hashes directly returned for every relevant action?
6. Does job history expose enough information to conservatively identify a job after an ambiguous create when the local process did not capture `job_id`?
7. Does the provider offering use fixed pricing or can the eventual budget differ from discovery metadata?
8. What exact JSON fields do create, fund, complete, history, and watch return in the selected CLI version, and what stable identities are available for restart reconciliation?

Do not lock provider IDs in source until these are verified.

## Base

### Base network overview

URL: https://docs.base.org/get-started/base

Verified:

- Base is an Ethereum Layer 2 network.
- Official documentation includes agent and payment guidance.

### Base RPC overview

URL: https://docs.base.org/base-chain/api-reference/rpc-overview

Verified:

- Base mainnet chain ID: 8453.
- Base Sepolia chain ID: 84532.
- Current hackathon rules describe Base deployment as the eligibility floor and an executed onchain action as the Base partner bonus evidence.
- Standard public RPC endpoints are documented for both networks.
- Ethereum JSON-RPC transaction and receipt methods are supported.

### Transaction troubleshooting/finality

URL: https://docs.base.org/base-chain/network-information/troubleshooting-transactions

Verified:

- Base documentation distinguishes fast preconfirmation, L2 inclusion, and later L1 finality levels.
- Transaction receipts and explorers can be used for execution evidence.

### Planned Base evidence

Primary plan:

Use a real ACP service-only job on Base mainnet and preserve funding/settlement transaction evidence. Verify receipts independently using Base RPC where transaction hashes are exposed.

Unresolved qualification question:

Hackathon rules describe Base and Virtuals as separate partner stacks. It is not yet confirmed that the same ACP-on-Base transaction can be credited to both stacks. Obtain explicit partner/hackathon confirmation before making that claim.

If a distinct Base action is required, choose the smallest action directly tied to Delta's paid-work lifecycle. Do not add a token or unrelated contract.

## LangGraph prior work and baseline

### Graph API

URL: https://docs.langchain.com/oss/python/langgraph/graph-api

Verified:

- Node caching is based on node input.
- Cache policy supports custom `key_func`.
- Cache policy supports TTL.

Implication:

Correctly configured LangGraph caching can already avoid rerunning unaffected nodes and can reuse a downstream node when its actual input is unchanged.

### Persistence

URL: https://docs.langchain.com/oss/python/langgraph/persistence

Verified:

- Checkpointers persist graph/thread state.
- Stores persist application-defined data across threads.
- Persistent `SqliteSaver` and `PostgresSaver` are documented alternatives to in-memory persistence.

Product-claim consequence:

Delta must not claim that selective reruns, input-keyed caching, TTL, or restart recovery are new. The comparison should focus on Delta's integrated revision preview, paid-work records, provider job continuity, approval/cost state, and the amount of custom application code needed to obtain those behaviors.

### Phase 6 implementation observation

The baseline uses the documented `StateGraph`, per-node `CachePolicy`, `langgraph.cache.sqlite.SqliteCache`, and `langgraph.checkpoint.sqlite.SqliteSaver` APIs. Its measured harness is in `delta/baseline.py` and its verification is in `tests/test_phase6_baseline.py`. The baseline uses project and relevant-input cache keys, implementation identity, a one-second TTL test, and a persistent thread checkpoint. Results are local deterministic fixture evidence, not provider evidence.

## Licensing and reuse

Hackathon requirement:

Use an OSI-approved license for the public repository.

Plan:

- Preserve an existing compliant repository license.
- If the repository has no license, use Apache-2.0 unless the user chooses another approved license.
- The ACP CLI repository is ISC licensed. Prefer consuming the package/CLI rather than copying its implementation.
- Do not copy substantial code or documentation from third parties into Delta. Link and paraphrase instead.
- Record any reused snippets and required notices if implementation later imports third-party code directly.

## Version-recording policy

Captured from the build environment that ran Phase 7 (live ACP on Base mainnet):

| Component | Version | Source |
|---|---|---|
| Python | 3.12.3 | `.venv/bin/python --version` |
| Sibyl memory client | 0.8.0 | `sibyl-memory-client` PyPI |
| Sibyl memory CLI | 0.4.0 | `sibyl-memory-cli` PyPI |
| Node.js | 26.7.0 | `node --version` |
| ACP CLI (`@virtuals-protocol/acp-cli`) | 1.0.34 | installed via `npx -p @virtuals-protocol/acp-cli` |
| LangGraph | 1.2.11 | optional baseline dependency |
| langgraph-checkpoint-sqlite | 3.1.1 | baseline dependency |
| pytest | 9.1.1 | dev dep |
| pytest-asyncio | 1.4.0 | dev dep |
| uvicorn | 0.52.4 | local web demo |

Notable API surface (from Phase 7 live run, recorded against `@virtuals-protocol/acp-cli@1.0.34`):

- `acp client create-job` validates the `--requirements` JSON against the offering's local schema
  in the CLI. The schema lives at the `properties` layer (`topic`, `content_type` are required for
  the Aaga `content_generation` offering) and the CLI rejects payloads that do not list those
  required fields. Aaga's on-chain job handler, however, expects the **envelope** shape
  `{"name": "<offering_name>", "requirement": {<actual fields>}}`. The proven Phase 7 pattern is:
  create the job with the flat shape, then immediately send an additional `requirement`-typed
  message to the resulting job ID using the envelope shape.
- `acp client fund` accepts `--amount <human-readable>` (e.g. `0.01` for 0.01 USDC). The CLI
  converts internally to the 6-decimal USDC base unit before sending the escrow transaction.
- `acp client complete` looks the job up via the in-process session map. Across separate CLI
  invocations the session is not always populated, so `client complete` can return
  `SESSION_NOT_FOUND` even when the job is alive onchain. The proven Phase 7 workaround is to
  complete the job via the underlying SDK (`@virtuals-protocol/acp-node-v2`) with
  `agent.internalComplete(...)`. This was the path that actually settled job 75656.
- The escrow contract on Base mainnet is `0x238e541bfefd82238730d00a2208e5497f1832e0` (ACP Core
  v2). All funding, settlement, refund, and `JobCompleted` events for live service jobs
  on Base mainnet are emitted from this contract.
- The native USDC contract on Base is `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913` (6 decimals).
- Base mainnet chain ID is 8453; the public RPC at `https://mainnet.base.org` accepts the
  standard Ethereum JSON-RPC and was used to verify every transaction in Phase 7.
- The Delta agent wallet (Privy-hosted, ACP-signer-only — no raw key on this machine) is
  `0x702Ab9EcFB9F87F52e79157b2EA6A929B60eC576`. See `SECURITY.md` for the spend rules.

The final demo and any code in the repository must use the same pinned versions listed above or
explicitly explain the difference.
