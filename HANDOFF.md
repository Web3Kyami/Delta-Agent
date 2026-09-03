# Delta Handoff

The local interface now has a public product site and separate application routes for Overview, Revisions, Runs, Continuity, and Integrations. `DESIGN.md` owns the page map, visual system, content rules, and staged interface roadmap. Preserve its honest live-versus-fixture states when connecting future ACP and Base behavior.

## Current position

Delta's product direction is fixed. Do not reopen ideation unless the user explicitly changes the product.

Delta helps developers revise paid agent work by previewing reuse/rerun decisions and additional cost, persisting work and remote job identity, and reconciling interrupted paid jobs before replacement.

**Phase 7 is partially verified and blocked.** Independent Base receipt reads and a fresh authenticated ACP history read confirm Aaga `content_generation` job 75656, 0.01 USDC funded, 0.009 USDC paid to the provider, 0.0005 USDC returned to Delta, and 0.0005 USDC sent to another recipient. The exact provider deliverable string matches the onchain hash under the official ACP EVM Keccak rule. Delta's adapter now parsed and persisted the live observation in a disposable Sibyl scope, but did not create a reusable WorkResult by design.

**Phase 8 is partially complete and blocked.** The deterministic suite passes, documentation claims are being corrected, and the existing local evidence has been audited. Live ACP history, adapter observation capture, and provider hash verification now pass. Reproducible evidence packaging, live paid execution-to-reusable-work proof, and final submission materials remain open.

The approved live validation attempt created Aaga job `75773` on Base `8453` at the quoted `0.01 USDC` service price. The provider rejected the CLI-generated requirement as malformed, and the job remains `open` and unfunded after the exact envelope was resent through the available official message content types. No additional money moved. Delta persisted the known job as an active attempt and did not create a WorkResult or artifact.

## Reading order

1. `AGENTS.md`
2. `MASTER_PLAN.md`
3. `IMPLEMENTATION_PLAN.md`
4. `SECURITY.md`
5. `STATE.md` (current truth — what is actually verified)
6. `REFERENCES.md` (versions, sources, Phase 7 API surface)
7. `DEMO_RUNBOOK.md` (judge path)
8. `README.md` (current state, live evidence table)
9. The existing local step-by-step record was used during the audit, but is not part of the public repository.

## Architecture in one page

- Core runtime: small Python DAG/revision engine.
- Runtime does not depend on LangGraph.
- LangGraph is a fair comparison baseline only.
- Dependencies and relevant inputs are developer-declared.
- Input and output identities use deterministic content signatures.
- Sibyl Memory is authoritative for reusable results, attempts, active-job recovery, revision plans, and execution history.
- Large artifact bytes live in a persistent artifact directory, with hashes and references in Sibyl.
- Virtuals ACP has a narrow JSON CLI adapter. The recorded job used an SDK workaround after the official `complete` command returned `SESSION_NOT_FOUND`; that workaround is not connected to the Delta runtime.
- `scripts/live_acp_validation.py` is the operator-gated live path. It records the real create receipt, uses chain-scoped history for recovery, and refuses funding or completion until the provider reports the required lifecycle state.
- `ACPAdapter.finalize_completed_work` is the explicit reusable-work gate. It persists a result only after live identity, deliverable hash, settlement receipt, and bounded artifact verification agree.
- Base mainnet is the chain for the recorded ACP payment and settlement evidence.
- Preview-time downstream state can be `pending_dependency`.
- After an upstream rerun, downstream effective inputs are recomputed from the actual new output.
- Known or ambiguous paid work is reconciled before any replacement job is created.
- No exactly-once claim.
- Initial concurrency guarantee is one writer process.
- One-page launch-package UI demonstrates the reusable engine through a clearly labelled local fixture path.
- Never present fixture, mocked, placeholder, or predetermined output as real success. Mark missing or unverifiable paths honestly and require end-to-end evidence before marking a capability or phase complete.

## Next action: live-path correction, then submission

The next work is implementation and verification. Do not submit the current live claims yet. After the audit blockers are resolved, use `DEMO_RUNBOOK.md` for the final judge path. Summary:

1. Resolve the official ACP requirement-envelope discrepancy for the known open job `75773`, or keep the paid integration explicitly blocked. The current live path accepts and persists real job data without creating a reusable result until budget, deliverable, settlement, and artifact evidence agree.
2. Keep protocol hash verification separate from generic artifact-store hashing, and only mark a deliverable reusable after the live Delta, settlement, artifact, and persistence checks pass together.
3. Make the recorded evidence reproducible from sanitized tracked inputs or public transaction links.
4. Run the full suite and the true fresh-process path again.
5. Push to a public GitHub repo, record the 2 to 5 minute video, and submit by **2026-09-10 23:59 UTC**.

If a live re-run is desired for the video, it requires fresh explicit approval:

- Aaga `content_generation` is still the cheapest live provider (0.01 USDC, 5 min SLA, Base 8453). Same offering ID `019d7c71-44c9-7329-bcf6-3edb953d6711`.
- The existing run showed that `acp client complete` returned `SESSION_NOT_FOUND` across separate processes. Do not present the bundled SDK workaround as a verified Delta path until it is implemented, tested, and documented safely.
- Before any new live funding, get explicit per-action approval (this is the same RED gate that released Phase 7).

## Money boundary

No job creation, wallet funding, escrow funding, settlement, or other broadcast is authorized by this handoff.

The earlier Aaga run `75656` completed before this Delta live-path audit. The newer approved validation job `75773` was created but remains open and unfunded. Do not create a replacement or fund it until the provider requirement state is resolved and the exact next action is approved.

The Delta wallet currently holds (verified 2026-09-03):

- 0.0005 ETH (gas) - pre-allocated
- 0.0005 USDC returned to Delta in the Phase 7 settlement. Another 0.0005 USDC went to an unidentified settlement recipient.

If the user wants to drain the known Delta refund, the only safe path is a read-only balance check followed by explicit approval for `acp client transfer --to <ADDR> --token USDC --amount 0.0005 --chain-id 8453` (Privy signing through the CLI) or the Privy dashboard. The other 0.0005 USDC recipient is not identified here. **Never paste a raw key in chat.**

## Current important unknowns

- Whether the judges will accept one ACP-on-Base flow as evidence for both the Virtuals and Base partner stacks. Raise this in the submission form.
- The exact official rationale for `acp client complete` returning `SESSION_NOT_FOUND` across separate CLI invocations, and whether the SDK workaround is acceptable for a reproducible Delta adapter.

These are not reasons to redesign Delta. They are submission-time checkpoints.

## Documentation discipline

- Stable product/architecture: `MASTER_PLAN.md`
- Ordered execution: `IMPLEMENTATION_PLAN.md`
- Live truth: `STATE.md`
- Security/spending: `SECURITY.md`
- Sources/version questions: `REFERENCES.md`
- Judge path: `DEMO_RUNBOOK.md`

Update `STATE.md` continuously. Avoid rewriting the master plan to record routine progress.
