# Delta

> Working-name project for the Sibyl Labs hackathon. Core engine, Sibyl persistence, deterministic runtime, no-spend ACP adapter contract, and a local fixture-backed demonstration interface are implemented; live integrations remain staged.

Delta is a developer library for revising paid agent work.

Given a completed workflow and a revised request, Delta is intended to show:

- what completed work remains reusable
- what needs another execution
- what must wait for an upstream result
- why each decision was made
- the known or estimated additional service cost before execution
- the identity and state of existing paid agent jobs
- whether an interrupted job must be reconciled before a replacement can be created

Delta does not claim a new caching algorithm. Mature workflow systems already provide input-based caching, selective execution, TTL policies, and persistence. Delta's planned contribution is the integrated developer experience around revision planning, persistent paid-work records, cost/approval state, and continuity of external paid agent jobs.

## Status

**Current status: Phases 1 to 4 no-spend implementation verified; Phase 5 local interface partially complete; Phase 6 baseline verified.**

The provider-neutral core, Sibyl-backed persistence, deterministic runtime, narrow ACP adapter, artifact safeguards, conservative reconciliation, and local demonstration interface are implemented and tested. Live ACP work and Base evidence are not claimed. No live ACP job, wallet funding, or Base transaction has occurred.

See `STATE.md` for verified facts, assumptions, blockers, and the next action.

## Implemented core

`delta.core` provides explicit workflow bindings, JSON normalization, deterministic input and output signatures, dependency validation, freshness checks, revision previews, work and attempt records, provider quote records, execution events, and spend-approval boundary validation.

`delta.fixtures` contains clearly labelled deterministic test services for the launch-package steps. Fixture output is input-sensitive and is never evidence of a live provider integration.

The Phase 1 verification command is:

```text
python3 -m unittest discover -s tests -v
```

The local demonstration interface runs the real revision and Sibyl paths with clearly labelled deterministic fixtures. It does not represent fixture output as live provider evidence.

Start it with:

```text
.venv/bin/python run_demo.py
```

Then open `http://127.0.0.1:8000`. The default local store is `.delta/demo-memory.db`, which is ignored by source control. No live ACP job, spending approval, settlement, or transaction is available from this local mode.

`delta.store.SibylStore` is the current persistence path. Work results, attempts, and plans use Sibyl WARM entities, active attempt heads use HOT state, transition events use the COLD journal, and artifact metadata uses REFERENCE records. The Phase 2 tests exercise these paths with fresh processes and a disposable store.

`delta.execute.DeltaEngine` runs ready steps, persists attempt ownership before execution, reevaluates downstream inputs from actual outputs, and returns honest blocked and failure states. Its automated execution path uses only clearly labelled deterministic fixtures until live providers are qualified.

`delta.providers.acp` provides a narrow, no-spend ACP boundary for JSON CLI execution, read-only history and watch operations, lifecycle parsing, intent persistence, cumulative approval caps, timeout ambiguity, conservative candidate reconciliation, and fixture-only adapter tests. `delta.artifacts` confines generated files, validates HTTPS-only remote references, and verifies size and content hashes before an artifact can be marked available. Fixture responses are labelled and cannot be presented as live provider evidence.

`delta.baseline` is a separate optional LangGraph comparison harness. Install it with `.venv/bin/python -m pip install -e ".[baseline]"`, then run `.venv/bin/python -m delta.baseline`. It measures a correctly configured SQLite cache and checkpoint path against the same deterministic workflow inputs. The measured overlap is evidence that selective reuse, TTL, and restart persistence are not unique Delta features.

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

## Planned architecture

- small Python DAG/revision engine
- Sibyl Memory as authoritative persistent work and revision state
- persistent artifact directory for large output bytes
- Virtuals ACP JSON CLI adapter for genuine service jobs and lifecycle reconciliation
- Base mainnet payment/settlement evidence for the demonstrated paid work
- minimal one-page web demonstration
- separate LangGraph comparison harness for honest baseline validation, verified in Phase 6

See `MASTER_PLAN.md` for the complete architecture.

## Required integrations for the intended submission

### Sibyl Memory

Sibyl is on the critical path for reusable work lookup, revision state, execution attempts, and paid-job recovery after a real process restart. The current read and write paths are implemented in `delta/store.py`.

The finished README must point directly to the implemented critical read and write paths once they exist.

### Virtuals ACP

The completed submission must exercise genuine service jobs, deliverables, and lifecycle reconciliation.

Read-only discovery has verified current Base-supported candidates, but the demo mapping remains provisional until one exact live job scope is approved. The current candidates are Syeollanga-claw `ai_image_generation` for visuals, Aaga `content_generation` for announcement copy, and OpenClaw Chile `Translation Service EN/ES/PT` for translation. Their live prices and schemas are recorded in `STATE.md` and `REFERENCES.md`.

### Base

The intended live path is a Virtuals ACP service-only job on Base mainnet, with actual USDC funding/settlement evidence.

Whether that same flow is accepted as separate Base and Virtuals partner evidence is still unverified and must be confirmed before claiming both partner stacks.

## Planned developer experience

A workflow definition explicitly declares:

- workflow inputs
- steps
- relevant input bindings
- dependency output bindings
- implementation/version identity
- freshness policy
- provider executor

The application can then preview a revision before execution and return `reuse`, `rerun`, or `pending_dependency` with structured reasons and cost information where known.

See `MASTER_PLAN.md` for the conceptual API.

## Planned setup outline

Exact commands will be added only after implementation exists.

Expected local prerequisites:

- Python 3.11 or newer, subject to repository constraints
- Node.js 20.19 or newer for the current ACP CLI package
- Sibyl Memory installed and initialized
- Virtuals ACP CLI installed and authenticated through its supported split flow for scripted use
- ACP signer configured securely for live onchain actions
- persistent artifact directory
- network access to Virtuals and Base

No credential values belong in this repository.

## Documentation

Recommended reading order:

1. `AGENTS.md` for builder rules.
2. `MASTER_PLAN.md` for product and architecture.
3. `IMPLEMENTATION_PLAN.md` for phase order and exit gates.
4. `SECURITY.md` for trust and spending boundaries.
5. `STATE.md` for current truth.
6. `REFERENCES.md` for official sources and unresolved API questions.
7. `DEMO_RUNBOOK.md` for the judge path.
8. `HANDOFF.md` for continuation context.

## Requirements ownership

Stable requirements and architecture are owned by `MASTER_PLAN.md`.

Live progress is owned by `STATE.md`.

Do not use README status text as a substitute for `STATE.md` during development.

## Baseline and prior work

LangGraph's official documentation describes node input caching with custom cache keys and TTL, plus persistent checkpoint/store options.

Delta will compare against a correctly configured baseline and will not claim selective reruns or restart persistence as novel.

See `REFERENCES.md` for sources.

## Security and spending

No live paid action is authorized by this repository documentation alone.

Builders must obtain explicit user approval before any wallet funding, ACP job creation that broadcasts, escrow funding, settlement, or other onchain transaction.

Interrupted paid work must be reconciled before retry.

Delta will not claim universal exactly-once execution.

See `SECURITY.md`.

## License

The hackathon requires an OSI-approved license for the public repository.

Preserve an existing compliant repository license. If the project has no license when implementation begins, the current plan is to use Apache-2.0 unless the user specifies another approved license.
