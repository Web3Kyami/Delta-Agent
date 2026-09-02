# Delta Handoff

## Current position

Delta's product direction is fixed. Do not reopen ideation unless the user explicitly changes the product.

Delta helps developers revise paid agent work by previewing reuse/rerun decisions and additional cost, persisting work and remote job identity, and reconciling interrupted paid jobs before replacement.

The provider-neutral Phase 1 core, Phase 2 Sibyl persistence, Phase 3 deterministic runtime, Phase 4 no-spend ACP implementation, and Phase 6 LangGraph baseline are verified. Read-only ACP marketplace discovery is also verified under the restricted signer policy. Phase 5 local interface work is partially complete because live provider and settlement states remain unverified. Phase 7 no-spend preflight is complete. Live ACP execution and Base evidence remain staged work.

## Reading order

1. `AGENTS.md`
2. `MASTER_PLAN.md`
3. `IMPLEMENTATION_PLAN.md`
4. `SECURITY.md`
5. `STATE.md`
6. `REFERENCES.md`
7. `DEMO_RUNBOOK.md`
8. `README.md`

## Architecture in one page

- Core runtime: small Python DAG/revision engine.
- Runtime does not depend on LangGraph.
- LangGraph is a fair comparison baseline only.
- Dependencies and relevant inputs are developer-declared.
- Input and output identities use deterministic content signatures.
- Sibyl Memory is authoritative for reusable results, attempts, active-job recovery, revision plans, and execution history.
- Large artifact bytes live in a persistent artifact directory, with hashes and references in Sibyl.
- Virtuals ACP integrates through a narrow JSON CLI adapter.
- Base mainnet is the intended chain for ACP service payment/settlement evidence.
- Preview-time downstream state can be `pending_dependency`.
- After an upstream rerun, downstream effective inputs are recomputed from the actual new output.
- Known or ambiguous paid work is reconciled before any replacement job is created.
- No exactly-once claim.
- Initial concurrency guarantee is one writer process.
- One-page launch-package UI demonstrates the reusable engine through a clearly labelled local fixture path.
- Never present fixture, mocked, placeholder, or predetermined output as real success. Mark missing or unverifiable paths honestly and require end-to-end evidence before marking a capability or phase complete.

## Next implementation action

The Phase 5 keyboard-only and recovery-action audit is complete for the local interface. Its remaining work is live provider, approval, reconciliation, and settlement state verification. Phase 6's fair LangGraph comparison harness is verified in `delta/baseline.py`. The Phase 7 read-only preflight confirmed the active Delta identity, `ACP_ONLY` signer policy, and Base marketplace candidates. Before live validation, verify the selected job command and lifecycle response shapes, then request explicit approval for one exact paid job scope and budget.

The local demonstration can be started with `.venv/bin/python run_demo.py` and opened at `http://127.0.0.1:8000`. It runs input-sensitive deterministic fixtures through the real Sibyl store. The page labels fixture mode and does not present fixture output as live ACP or Base evidence.

## Money boundary

No job creation, wallet funding, escrow funding, settlement, or other broadcast is authorized by this handoff.

When Phase 7 is reached, stop and request explicit approval containing the exact provider, offering, chain, maximum service spend, and broadcast actions.

## Current important unknowns

- exact current ACP job and lifecycle JSON result shapes
- whether one ACP-on-Base flow counts for both partner stacks
- existing license
- Base balance and spending budget
- live ACP job execution and reconciliation behavior

These are not reasons to redesign Delta. They are implementation checkpoints. Read-only discovery did not authorize a paid job or any monetary action. The next live step requires explicit approval of the exact provider, offering, Base chain, service cap, wallet-funding requirement, and broadcast actions.

## Documentation discipline

- Stable product/architecture: `MASTER_PLAN.md`
- Ordered execution: `IMPLEMENTATION_PLAN.md`
- Live truth: `STATE.md`
- Security/spending: `SECURITY.md`
- Sources/version questions: `REFERENCES.md`
- Judge path: `DEMO_RUNBOOK.md`

Update `STATE.md` continuously. Avoid rewriting the master plan to record routine progress.
