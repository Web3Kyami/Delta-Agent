# Delta Handoff

## Current position

Delta's product direction is fixed. Do not reopen ideation unless the user explicitly changes the product.

Delta helps developers revise paid agent work by previewing reuse/rerun decisions and additional cost, persisting work and remote job identity, and reconciling interrupted paid jobs before replacement.

**Phase 7 is complete and verified end-to-end on Base mainnet.** Live Aaga `content_generation` job 75656 was funded with 0.01 USDC, delivered, and settled (0.009 to provider, 0.001 refund). Deliverable hash `0x5c970be4...` matches the on-chain `Submitted` event. Delta's local Sibyl store persists the completed work, and `scripts/restart_test.py` + `tests/test_phase7_live.py` prove a fresh process can re-read it without any in-memory cache.

**Phase 8 is complete.** Evidence bundle in `.evidence/phase7_evidence.md`, README rewritten to reflect the implemented/live state, pinned versions in `REFERENCES.md`, this `HANDOFF.md` is current. The remaining work is the user-driven submission step: push to a public GitHub repo, record the 2-5 minute demo video per `DEMO_RUNBOOK.md`, and submit by 2026-09-10 23:59 UTC.

## Reading order

1. `AGENTS.md`
2. `MASTER_PLAN.md`
3. `IMPLEMENTATION_PLAN.md`
4. `SECURITY.md`
5. `STATE.md` (current truth — what is actually verified)
6. `REFERENCES.md` (versions, sources, Phase 7 API surface)
7. `DEMO_RUNBOOK.md` (judge path)
8. `README.md` (current state, live evidence table)
9. `.evidence/phase7_evidence.md` (canonical Phase 7 evidence)

## Architecture in one page

- Core runtime: small Python DAG/revision engine.
- Runtime does not depend on LangGraph.
- LangGraph is a fair comparison baseline only.
- Dependencies and relevant inputs are developer-declared.
- Input and output identities use deterministic content signatures.
- Sibyl Memory is authoritative for reusable results, attempts, active-job recovery, revision plans, and execution history.
- Large artifact bytes live in a persistent artifact directory, with hashes and references in Sibyl.
- Virtuals ACP integrates through a narrow JSON CLI adapter (with a documented internal `acp-node-v2` SDK fallback for paths the CLI's per-process session map cannot reach, e.g. `complete` across a process boundary).
- Base mainnet is the chain for ACP service payment/settlement evidence.
- Preview-time downstream state can be `pending_dependency`.
- After an upstream rerun, downstream effective inputs are recomputed from the actual new output.
- Known or ambiguous paid work is reconciled before any replacement job is created.
- No exactly-once claim.
- Initial concurrency guarantee is one writer process.
- One-page launch-package UI demonstrates the reusable engine through a clearly labelled local fixture path.
- Never present fixture, mocked, placeholder, or predetermined output as real success. Mark missing or unverifiable paths honestly and require end-to-end evidence before marking a capability or phase complete.

## Next action: submission (user-driven, not implementation)

Implementation, tests, live evidence, and docs are all done. The next step is not builder work — it is the user pushing the repo to GitHub and recording the demo video. The exact path is in `DEMO_RUNBOOK.md`. Summary:

1. `git remote add origin git@github.com:Web3Kyami/Delta.git` (or wherever the user wants the public repo).
2. `git push -u origin main`.
3. Record the 2-5 minute video following the beat list in `DEMO_RUNBOOK.md`. The onchain evidence is in `.evidence/phase7_evidence.md`; the local demo runs with `.venv/bin/python run_demo.py` and opens at `http://127.0.0.1:8000`.
4. Submit by **2026-09-10 23:59 UTC**.

If a live re-run is desired for the video:

- Aaga `content_generation` is still the cheapest live provider (0.01 USDC, 5 min SLA, Base 8453). Same offering ID `019d7c71-44c9-7329-bcf6-3edb953d6711`.
- The full procedure is in `STATE.md` → "Phase 7 execution". The CLI gotcha is that `acp client complete` returns `SESSION_NOT_FOUND` across separate processes; the proven path is to call `agent.internalComplete(...)` via the bundled SDK. See `REFERENCES.md` for the API surface notes.
- Before any new live funding, get explicit per-action approval (this is the same RED gate that released Phase 7).

## Money boundary

No job creation, wallet funding, escrow funding, settlement, or other broadcast is authorized by this handoff.

The only currently approved live action is the Aaga announcement at 0.01 USDC on Base 8453, which has already executed (job 75656) and is settled. Any further live action needs fresh explicit approval of the exact provider, offering, chain, cap, and broadcast actions.

The Delta wallet currently holds (verified 2026-09-03):

- 0.0005 ETH (gas) — pre-allocated
- 0.001 USDC — leftover refund from the Phase 7 settlement

If the user wants to drain the wallet, the only safe path is `acp client transfer --to <ADDR> --token USDC --amount 0.001 --chain-id 8453` (Privy signing through the CLI) or the Privy dashboard. **Never paste a raw key in chat.**

## Current important unknowns

- Whether the judges will accept one ACP-on-Base flow as evidence for both the Virtuals and Base partner stacks. (Not something we can resolve from here; raise the question in the submission form.)
- The exact official rationale for `acp client complete` returning `SESSION_NOT_FOUND` across separate CLI invocations. The workaround (`agent.internalComplete` via the bundled SDK) is the only path we found that works deterministically; an upstream issue would be nice to know about for the README.

These are not reasons to redesign Delta. They are submission-time checkpoints.

## Documentation discipline

- Stable product/architecture: `MASTER_PLAN.md`
- Ordered execution: `IMPLEMENTATION_PLAN.md`
- Live truth: `STATE.md`
- Security/spending: `SECURITY.md`
- Sources/version questions: `REFERENCES.md`
- Judge path: `DEMO_RUNBOOK.md`

Update `STATE.md` continuously. Avoid rewriting the master plan to record routine progress.
