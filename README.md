# Delta

> Working-name project for the Sibyl Labs hackathon.
> **Live ACP service job on Base mainnet, end-to-end, verified onchain.**

Delta is a developer library for revising paid agent work. Given a completed
workflow and a revised request, Delta tells you:

- what completed work remains reusable
- what needs another execution
- what must wait for an upstream result
- why each decision was made
- the known or estimated additional service cost before execution
- the identity and state of existing paid agent jobs
- whether an interrupted job must be reconciled before a replacement can be created

Delta does not claim a new caching algorithm — mature workflow systems already
provide input-based caching, selective execution, TTL policies, and persistence.
Delta's contribution is the integrated developer experience around revision
planning, persistent paid-work records, cost/approval state, and continuity of
external paid agent jobs.

## Status

**Current status: Phases 1–7 verified on Base mainnet; Phase 8 evidence bundle complete.**

Implemented and verified:

- **Phase 1**: core engine, input/output signatures, dependency validation
- **Phase 2**: Sibyl Memory persistence (entities + journal + artifact references)
- **Phase 3**: deterministic execution engine, attempt lifecycle, blocked/failure states
- **Phase 4**: no-spend Virtuals ACP adapter (read-only history, JSON CLI, reconciliation)
- **Phase 5**: local one-page web demonstration (`run_demo.py` → `http://127.0.0.1:8000`)
- **Phase 6**: LangGraph comparison baseline (overlap measured, not claimed novel)
- **Phase 7**: **live ACP service-only job against the Aaga provider on Base mainnet, USDC funded, settled, and persisted to Delta's Sibyl store. A fresh-process restart test re-reads the completed job purely from disk + DB.**

The Python test suite is **60 passed, 15 subtests passed** in ~24 s. See
`STATE.md` for verified facts, onchain evidence, and the next action.

## Live evidence — Phase 7

A real service-only content generation job ran against the Aaga provider on
Base mainnet (chain id 8453), was funded with USDC, was settled by the
evaluator, and the resulting artifact hash was verified against the on-chain
`Submitted` event.

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
| USDC refund to Delta (platform fee) | 0.001 |
| Escrow contract | `0x238e541bfefd82238730d00a2208e5497f1832e0` (ACP Core v2) |
| Native USDC on Base | `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913` (6 decimals) |

Every value above is verified by reading the Base mainnet JSON-RPC
(`https://mainnet.base.org`) directly — not from a log or a provider claim.
The verifier script lives at `scripts/restart_test.py`; it is also wrapped
as a pytest in `tests/test_phase7_live.py`.

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
states. Its automated execution path uses clearly labelled deterministic fixtures; the live
ACP integration is exercised in `scripts/persist_phase7.py` + `scripts/restart_test.py` and
in the hermetic `tests/test_phase7_live.py`.

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

## Initial demonstration workflow

The first workflow is a launch package:

1. Product visual from product description and visual brief.
2. Announcement from product description and launch date.
3. Translation from announcement output and target language.

Dependencies are explicit. Translation depends on the actual announcement output.

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

Then open `http://127.0.0.1:8000`. The default local store is `.delta/demo-memory.db`, which
is ignored by source control. This mode runs only deterministic fixtures — no live ACP job,
no spending approval, no settlement, no transaction.

## Run the test suite

```bash
.venv/bin/python -m pytest
```

Last run: **60 passed, 15 subtests passed in ~24 s**, including 3 Phase 7 tests in
`tests/test_phase7_live.py`.

## Run the Phase 7 restart test (proves paid work survives a process restart)

```bash
.venv/bin/python scripts/restart_test.py
```

A fresh Python process, no in-memory cache, reads the completed Phase 7 job from disk and
the on-chain artifact hash from Delta's local Sibyl DB. The expected output ends with
`VERDICT: PASS — engine can resume and recall paid work`.

## Architecture

- small Python DAG/revision engine
- Sibyl Memory as authoritative persistent work and revision state
- persistent artifact directory for large output bytes
- Virtuals ACP JSON CLI adapter for genuine service jobs and lifecycle reconciliation
- Base mainnet payment/settlement evidence for the demonstrated paid work
- minimal one-page web demonstration
- separate LangGraph comparison harness for honest baseline validation

See `MASTER_PLAN.md` for the complete architecture.

## Required integrations

### Sibyl Memory

Sibyl is the critical path for reusable work lookup, revision state, execution attempts, and
paid-job recovery after a real process restart. The read and write paths are implemented
in `delta/store.py` and exercised by `tests/test_phase2_sibyl.py` and `tests/test_phase7_live.py`.

### Virtuals ACP

A real service-only job was executed end-to-end against the Aaga provider on Base mainnet.
Read-only discovery verified the current Base-supported candidates; the Aaga offering
was selected for Phase 7 because it is the cheapest live option (0.01 USDC) and provides
deterministic, hash-attested deliverables. Live prices and schemas are recorded in
`REFERENCES.md` and `STATE.md`.

### Base

The live path is a Virtuals ACP service-only job on Base mainnet, with actual USDC
funding/settlement evidence. The on-chain transactions are listed in the **Live evidence**
section above. The escrow contract is `0x238e541bfefd82238730d00a2208e5497f1832e0` (ACP Core v2).

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
