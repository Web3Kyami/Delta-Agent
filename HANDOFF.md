# Delta Handoff

## Current position

Delta's product direction is fixed. Do not reopen ideation unless the user explicitly changes the product.

Delta helps developers revise paid agent work by previewing reuse/rerun decisions and additional cost, persisting work and remote job identity, and reconciling interrupted paid jobs before replacement.

The provider-neutral Phase 1 core, Phase 2 Sibyl persistence, Phase 3 deterministic runtime, Phase 4 no-spend ACP implementation, and Phase 6 LangGraph baseline are verified. Read-only ACP marketplace discovery is also verified under the restricted signer policy. Phase 5 local interface work is partially complete because live provider and settlement states remain unverified. Phase 7 no-spend preflight is complete. Phase 7 live execution is **blocked at the wallet-funding gate** — Delta agent wallet `0x702ab9ecfb9f87f52e79157b2ea6a929b60ec576` has 0.0005 ETH (gas) but 0 USDC and 0 USDC.e on Base 8453. No live transaction can be funded until USDC lands.

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

Phase 7 funding gate is now clear. Delta agent wallet `0x702ab9ecfb9f87f52e79157b2ea6a929b60ec576` has 0.0005 ETH gas and **0.10 USDC** at block 50799003. Funding tx `0xbb3625fca92c1aba3099f052da2037cfa4996e258712da728c883e7cb049f222` is verified successful. Native USDC contract: `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913`.

Proceed with Aaga `content_generation` (`019d7c71-44c9-7329-bcf6-3edb953d6711`), fixed 0.01 USDC, Base 8453, max service cap 0.02 USDC, broadcast actions: create-job + fund + complete (settlement is a separate confirmation). Steps:

1. Persist Phase 7 plan + approval in Sibyl.
2. `acp events listen` in background; capture local event file outside source control.
3. `acp client create-job --chain-id 8453 --offering-id 019d7c71-44c9-7329-bcf6-3edb953d6711 --requirements '<JSON>' --json`.
4. Persist returned job ID and tx hash immediately.
5. Reconcile until `budget_set`, verify quote within cap.
6. `acp client fund --job-id ... --amount 0.01 --json`.
7. Persist funding tx hash + amount + block.
8. Reconcile until `submitted`, fetch deliverable, hash-validate, mark available.
9. `acp client complete --job-id ... --json` (settlement approval gate before this).
10. Verify Base receipt independently (`eth_getTransactionReceipt`).
11. Stop Delta process; start fresh process; reload same project; prove Sibyl restores the paid work and job identity.
12. Update STATE.md to Phase 7 verified; pin versions in REFERENCES.md; commit evidence bundle to `.evidence/` outside source control.

The local demonstration can still be started with `.venv/bin/python run_demo.py` and opened at `http://127.0.0.1:8000`. It runs input-sensitive deterministic fixtures through the real Sibyl store. The page labels fixture mode and does not present fixture output as live ACP or Base evidence.

## Money boundary

No job creation, wallet funding, escrow funding, settlement, or other broadcast is authorized by this handoff.

The current approval for Phase 7 (Aaga announcement at 0.01 USDC, Base 8453, with broadcast for create/fund/settle) is contingent on USDC landing at the Delta wallet first.

## Current important unknowns

- why the prior USDC funding did not appear at the Delta wallet (wrong asset? wrong address? tx not yet broadcast?)
- exact current ACP job and lifecycle JSON result shapes
- whether one ACP-on-Base flow counts for both partner stacks
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