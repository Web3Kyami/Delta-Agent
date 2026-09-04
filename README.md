# Delta

> Working-name project for the Sibyl Labs hackathon.
> **Transitioning to trusted handoff for agent work.**

Delta's approved direction is a trusted handoff layer for agent work:

> Agents can inherit previous work without inheriting everything.

Agent A completes work and Sibyl persists it. When Agent B begins later, Delta will recall candidate work and deterministically evaluate validity, trust, authorization, dependencies, and external-job safety before constructing Agent B's context. Approved work may cross the handoff. Blocked work must stay outside the receiving model's prompt. Missing work executes, and a Reuse Receipt explains the outcome.

The trusted-handoff migration is underway. Phases 1 through 4 are implemented and
locally verified in the shared worktree; external model execution and live
settlement remain planned. The repository also retains the legacy launch-package
revision demonstration while it is migrated through
`IMPLEMENTATION_PLAN.md`.

## Status

**Current status: Phases 1 through 4 of the trusted-handoff roadmap are implemented and locally verified. The scenario-first handoff surface is primary; the existing launch-package surface remains legacy. Phase 5 live proof is blocked pending explicit operator approval and reconciliation of the known open ACP attempt.**

### Current capabilities

Implemented and verified:

- **Phase 1**: core engine, input/output signatures, dependency validation
- **Migration Phase 1**: trusted-handoff contracts and deterministic policy gate
- **Migration Phase 2**: signed demo identity, isolated workspaces and scenarios, scoped reset
- **Migration Phase 3**: distinct agent sessions, approved-context execution, provider boundary, and Reuse Receipts
- **Migration Phase 4**: handoff-first application journey and Delta-specific neo-brutalist landing story
- **Legacy Phase 2**: Sibyl Memory persistence (entities + journal + artifact references)
- **Legacy Phase 3**: deterministic execution engine, attempt lifecycle, blocked/failure states
- **Legacy Phase 4**: no-spend Virtuals ACP adapter (read-only history, JSON CLI, reconciliation)
- **Legacy Phase 5**: public product site and route-based local launch-package workspace (`run_demo.py` at `http://127.0.0.1:8000`)
- **Phase 6**: LangGraph comparison baseline (overlap measured, not claimed novel)
- **Phase 7**: live Aaga ACP history and Base transaction evidence, with the paid execution-to-reusable-work gap documented rather than claimed as complete.

The current non-spending Python test suite is **141 passing tests**, verified on
2026-09-04. See `STATE.md` for verified facts, onchain evidence, and the next action.

### Approved migration direction

- Phase 1: handoff contracts and deterministic policy gate
- Phase 2: demo identity, workspace and scenario isolation, scenarios, and reset
- Phase 3: distinct agent sessions, approved-context LLM execution, and Reuse Receipts
- Phase 4: handoff-first application and Delta-specific neo-brutalist landing redesign
- Phase 5: operator-gated live ACP/Base proof and submission hardening

The primary scenario will be AI software-work handoff. Home repair handoff will provide the general-audience explanation, and paid research handoff will carry the ACP/Base and economic-reuse story. One LLM provider comes first; a second provider is deferred. Public demo login will remain completely separate from live spending authority.

The latest approved live validation created Aaga ACP job `75773` on Base
`8453`, but the provider rejected the CLI-generated requirement envelope and
the job remains open and unfunded. This is recorded as a blocked live attempt,
not a successful provider run.

## Recorded external evidence — Phase 7

A real service-only content generation job ran against the Aaga provider on
Base mainnet (chain id 8453), was funded with USDC, was settled by the
evaluator, and emitted a deliverable hash in the ACP `Submitted` event. These
receipts are real external evidence. A current authenticated `acp job history`
read also returned the completed job and exact provider deliverable string.

| Field | Value |
|---|---|
| Provider | Aaga (ACP provider `0xb0aca700745a989a1cb859eecfe0fd9afbc066aa`) |
| Offering | `content_generation` (price 0.01 USDC, 5 min SLA) |
| Job ID | `75656` |
| Chain | Base mainnet, 8453 |
| Agent wallet (Privy-hosted) | `0x702Ab9EcFB9F87F52e79157b2EA6A929B60eC576` |
| Fund tx (USDC → escrow) | `0xd1d284d10916bc90934b876cec1ee3242a27de026bbd2b8191d532071f48425d` |
| Deliverable tx (provider → submit) | `0xd393763b6560a80d49317f7f11edf9ab349835aa0420ee4c928e5dd1a1dda445` |
| Settle tx (escrow → provider / refund) | `0x1062a1b78bf8e5686894e9e091b4b857559b784bf8a24f8f0177067957788ff8` |
| Deliverable hash (on-chain attestation) | `0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8` |
| USDC funded | 0.01 |
| USDC settled to provider | 0.009 |
| USDC returned to Delta | 0.0005 |
| USDC sent to another settlement recipient | 0.0005 |
| Net Delta wallet service outflow, before gas | 0.0095 |
| Escrow contract | `0x238e541bfefd82238730d00a2208e5497f1832e0` (ACP Core v2) |
| Native USDC on Base | `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913` (6 decimals) |

Transaction receipt status and token transfer amounts were independently read
from Base mainnet JSON-RPC (`https://mainnet.base.org`). The exact provider
deliverable string hashes to the attested value using the official ACP EVM rule,
`keccak256(UTF-8 deliverable bytes)`. Delta still does not mark the output
reusable: the live observation was intentionally recorded as
`reconciliation_required`, and the live paid execution, settlement ingestion,
and WorkResult/artifact persistence path has not run through Delta end to end.
The current `scripts/restart_test.py` and
`tests/test_phase7_live.py` inspect recorded data and are not live integration
proof. See `STATE.md` for the tracked evidence audit and current blockers.

## Implemented core

`delta.core` provides explicit workflow bindings, JSON normalization, deterministic input
and output signatures, dependency validation, freshness checks, revision previews, work and
attempt records, provider quote records, execution events, and spend-approval boundary
validation.

`delta.fixtures` contains clearly labelled deterministic test services for the launch-package
steps. Fixture output is input-sensitive and is never evidence of a live provider integration.

`delta.store.SibylStore` is the persistence path. Work results, attempts, and plans use Sibyl
WARM entities, active attempt heads use HOT state, transition events use the COLD journal, and
artifact metadata uses REFERENCE records.

`delta.execute.DeltaEngine` runs ready steps, persists attempt ownership before execution,
reevaluates downstream inputs from actual outputs, and returns honest blocked and failure
states. Its automated execution path uses clearly labelled deterministic fixtures. A
current read-only verification routes the real ACP history through the adapter and
persistence boundary, but does not create a reusable WorkResult or prove the paid
execution path.

`delta.providers.acp` provides a narrow ACP boundary for JSON CLI execution, read-only
history and watch operations, lifecycle parsing, intent persistence, cumulative approval
caps, timeout ambiguity, conservative candidate reconciliation, and fixture-only adapter
tests. `delta.artifacts` confines generated files, validates HTTPS-only remote references,
and verifies size and content hashes before an artifact can be marked available.

`delta.baseline` is a separate optional LangGraph comparison harness. Install it with
`.venv/bin/python -m pip install -e ".[baseline]"`, then run `.venv/bin/python -m delta.baseline`.
It measures a correctly configured SQLite cache and checkpoint path against the same
deterministic workflow inputs. The measured overlap is evidence that selective reuse, TTL,
and restart persistence are not unique Delta features.

## Legacy demonstration workflow

The currently implemented local workflow is a launch package:

1. Product visual from product description and visual brief.
2. Announcement from product description and launch date.
3. Translation from announcement output and target language.

Dependencies are explicit. Translation depends on the actual announcement output.

This workflow and its product surface are legacy migration material. They remain available only to document and verify the existing engine until the approved handoff scenarios replace them in later phases.

Example revision behavior:

- launch-date-only change: reuse visual, rerun announcement, then reevaluate translation
- visual-brief-only change: rerun visual only
- unchanged request: reuse all valid completed work
- upstream rerun with identical output: downstream work may remain reusable

## Run the local demo (no spend, no chain)

```bash
.venv/bin/python -m pip install -e ".[sibyl]"
.venv/bin/python run_demo.py
```

Then open `http://127.0.0.1:8000`. Use the primary call to action to enter the scenario
workspace at `/app/scenarios`. The default local store is `.delta/demo-memory.db`, which
is ignored by source control. This mode runs only deterministic fixtures — no live ACP job,
no spending approval, no settlement, no transaction.

The operator-gated `scripts/live_acp_validation.py` is separate from this local
demo. It uses the real ACP CLI and Sibyl store, and refuses funding until live
history reports the exact provider budget. It must not be presented as fixture
evidence or run without matching approval.

## Run the test suite

```bash
.venv/bin/python -m pytest
```

Last run: **141 passed, 19 subtests passed**. The three tests in
`tests/test_phase7_live.py` are labelled recorded-data persistence fixtures, not
live ACP tests. They include a genuinely new Python process that restores the
recorded observation from Sibyl.

## Inspect the recorded Phase 7 restart data

```bash
.venv/bin/python scripts/restart_test.py
```

This starts a fresh Python process and reads the locally persisted recorded
observation. It is useful for inspecting the stored identity, but it is not proof
that a live job was written through Delta or that the artifact is reusable. The
script intentionally exits with a blocked verdict. A clean clone does not contain
the ignored `.delta` database.

## Architecture

- small Python DAG/revision engine
- Sibyl Memory as authoritative persistent work and revision state
- persistent artifact directory for large output bytes
- Virtuals ACP JSON CLI adapter for service jobs and lifecycle reconciliation
- Independently checked recorded Base payment and settlement evidence
- branded server-rendered operations workspace for revisions, runs, memory, integrations, and safety
- separate LangGraph comparison harness for honest baseline validation

See `MASTER_PLAN.md` for the complete architecture.

## Product interface

The currently implemented legacy public site explains revision planning through an illustrative example and leads to the launch-package workspace. The application uses separate routes for Overview, Revisions, Runs, Continuity, and Integrations. These routes and this composition will be replaced during the approved handoff migration and are not requirements for the future product.

The revision API response drives the plan, summary metrics, run state, and continuity results. Storage and provider implementation details stay on the Integrations page or inside technical evidence rather than appearing throughout the normal workflow.

`DESIGN.md` owns the Delta identity, visual system, information architecture, interaction rules, source research, and interface roadmap. The interface uses local HTML, CSS, JavaScript, and SVG assets without a runtime design-library dependency.

## Required integrations

### Sibyl Memory

Sibyl is the critical path for reusable work lookup, revision state, execution attempts, and
paid-job recovery after a real process restart. The read and write paths are implemented
in `delta/store.py` and exercised by the deterministic Sibyl tests. The Phase 7 restart
script reads a recorded observation through a fresh process and is not live-path evidence.

### Virtuals ACP

Read-only discovery verified current Base-supported candidates. A recorded Aaga
service-only job exists on Base mainnet. The adapter now accepts the observed create
and history shapes and persists an explicit observation state, but the repository does
not claim that this old job was captured through a live Delta execution. Live prices
and schemas are recorded in `REFERENCES.md` and `STATE.md`.

### Base

The recorded external path is a Virtuals ACP service-only job on Base mainnet, with
independently checked USDC funding and settlement receipts. The transactions are
listed in the **Recorded external evidence** section above. The escrow contract is
`0x238e541bfefd82238730d00a2208e5497f1832e0` (ACP Core v2). Delta does not yet
claim a verified live Base integration in its runtime.

## Planned developer experience

A workflow definition explicitly declares:

- workflow inputs
- steps
- relevant input bindings
- dependency output bindings
- implementation/version identity
- freshness policy
- provider executor

The application can then preview a revision before execution and return `reuse`, `rerun`, or
`pending_dependency` with structured reasons and cost information where known.

See `MASTER_PLAN.md` for the conceptual API.

## Setup

Local prerequisites:

- Python 3.10 or newer (the Phase 7 build used 3.12.3)
- Node.js 20.19 or newer (Phase 7 used 26.7.0)
- Sibyl Memory installed (`pip install sibyl-memory-client==0.8.0`)
- Virtuals ACP CLI installed (`npx -p @virtuals-protocol/acp-cli@1.0.34 acp --help`)
- ACP signer configured securely for live onchain actions (Privy is the supported hosted signer)
- network access to Virtuals and Base
- `.env` populated per `.env.example` (not committed)

**No credential values belong in this repository.** See `SECURITY.md`.

## Documentation

Recommended reading order:

1. `AGENTS.md` for builder rules.
2. `MASTER_PLAN.md` for product and architecture.
3. `IMPLEMENTATION_PLAN.md` for phase order and exit gates.
4. `SECURITY.md` for trust and spending boundaries.
5. `STATE.md` for current truth.
6. `REFERENCES.md` for official sources, pinned versions, and the Phase 7 API surface.
7. `DEMO_RUNBOOK.md` for the judge path.
8. `HANDOFF.md` for continuation context.

## Requirements ownership

Stable requirements and architecture are owned by `MASTER_PLAN.md`.
Live progress is owned by `STATE.md`.
Do not use README status text as a substitute for `STATE.md` during development.

## Baseline and prior work

LangGraph's official documentation describes node input caching with custom cache keys and
TTL, plus persistent checkpoint/store options. The Phase 6 baseline measures overlap against
a correctly configured LangGraph harness and confirms that selective reruns, input-keyed
caching, TTL, and restart recovery are not unique to Delta.

See `REFERENCES.md` for sources.

## Security and spending

No live paid action is authorized by this repository documentation alone.
Builders must obtain explicit user approval before any wallet funding, ACP job creation
that broadcasts, escrow funding, settlement, or other onchain transaction.
Interrupted paid work must be reconciled before retry.
Delta will not claim universal exactly-once execution.

See `SECURITY.md`.

## License

Apache-2.0 — see `LICENSE`.
