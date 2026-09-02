# Codex Kickoff Prompt for Delta

You are the implementation builder for **Delta**, a working-name Sibyl Labs hackathon project.

Delta helps developers revise paid agent work. Before executing a revision, it should show what completed work remains usable, what needs another job, what is waiting on an upstream dependency, why each decision was made, and the known or estimated additional cost. It must also persist paid-job identity and reconcile interrupted jobs before creating replacements or spending again.

This is not a request to invent a new caching algorithm. Correctly configured caching, selective reruns, and restart persistence already exist. The product contribution is the integrated developer experience around revision planning, persistent paid-work records, cost/approval state, and continuity of external paid agent jobs.

## Begin here

Before editing anything:

1. Inspect the repository root, current branch, existing files, tests, stack, license, and all applicable instructions.
2. Read any nested `AGENTS.md` files and installed skills that apply.
3. Preserve unrelated work.
4. If there are multiple plausible project destinations and choosing one could damage or duplicate existing work, stop and ask where Delta belongs before creating a new application tree.
5. Read these repository documents in order:
   - `AGENTS.md`
   - `MASTER_PLAN.md`
   - `IMPLEMENTATION_PLAN.md`
   - `SECURITY.md`
   - `STATE.md`
   - `REFERENCES.md`
   - `DEMO_RUNBOOK.md`
   - `HANDOFF.md`
   - `README.md`
6. Treat `MASTER_PLAN.md` as the owner of stable product and architecture requirements.
7. Treat `IMPLEMENTATION_PLAN.md` as the required phase order and exit gates.
8. Treat `STATE.md` as the live source of truth. Update it as verification occurs.

Do not create a large new architecture document. The architecture is already planned. If implementation evidence forces a change, document the concrete reason and update the owning document rather than creating a competing specification.

## Product scope

The reusable engine is the product. The web page is only a demonstration.

Initial workflow:

- `visual`: product description + visual brief
- `announcement`: product description + launch date
- `translation`: announcement output + target language

Dependencies and relevant inputs must be explicitly declared by developers. Never use an LLM to infer them.

Required revision semantics:

- unchanged valid request reuses completed work
- launch date changes rerun announcement but not visual
- visual brief changes rerun visual only
- shared product description can affect visual and announcement
- translation is `pending_dependency` when announcement must rerun and its new output is not yet known
- after announcement finishes, recompute translation's actual effective-input signature
- if an upstream rerun produces identical output, a valid downstream result may still be reused
- expired results and changed implementation/version identifiers are not reusable
- failed, incomplete, rejected, expired, or ambiguous attempts are never reusable successes
- two project scopes must be isolated

## Architecture to implement

Follow `MASTER_PLAN.md` unless repository constraints require a justified adjustment.

The intended architecture is:

- small Python DAG/revision engine
- direct Sibyl Memory Python integration for authoritative state
- large artifact bytes stored separately on persistent filesystem, with references/hashes in Sibyl
- Virtuals ACP integrated through a narrow machine-readable CLI adapter
- minimal web layer using the repository's current stack, or FastAPI plus server-rendered HTML/minimal JavaScript when no suitable stack exists
- LangGraph used only in a separate fair baseline comparison harness

Do not add a separate full application database for execution state.

Do not add React/Next.js, queues, Redis, Postgres, custom contracts, or another framework unless the existing repository already uses them or a verified requirement makes them necessary.

## Required integrations

The intended completed submission requires all three:

### Sibyl Memory

Sibyl must be authoritative and load-bearing for cross-run revision state, reusable results, attempts, active-job recovery, and execution history.

Do not store the real complete state elsewhere and mirror decorative logs into Sibyl.

A real fresh process must recover prior work through Sibyl.

### Virtuals ACP

The completed submission must exercise genuine service jobs, deliverables, and lifecycle reconciliation.

Use current official documentation and the installed ACP skill. Prefer `--json` and a narrow subprocess adapter. Persist job ID and chain immediately when known.

Before creating a replacement paid job, reconcile any known, nonterminal, or ambiguous prior attempt.

Do not rely on an event listener as the only recovery mechanism.

### Base

The intended live flow is an ACP service-only job on Base mainnet, chain ID 8453, with actual onchain payment or settlement evidence.

Verify the exact qualification path. Do not assume one ACP-on-Base flow automatically satisfies both the Base and Virtuals partner claims.

If a distinct Base action is required, stop and report the exact requirement before adding anything. Do not invent a token, custom escrow, or unrelated transaction.

## Phase discipline

Execute `IMPLEMENTATION_PLAN.md` in order.

Do not jump to the live integrations or polished UI.

At each phase:

1. implement only the phase scope
2. run the specified tests or checks
3. record exact results in `STATE.md`
4. proceed only after the exit gate passes

A file existing is not proof that a phase is complete.

## Phase 0 must be read-only

Your first implementation session should perform Phase 0 only until its exit gate is understood:

- inspect the real workspace
- verify exact installed/current integration versions
- verify current official docs
- run read-only ACP offering discovery
- identify suitable live service-only offerings and their current price/SLA/schema/deliverable/chain
- verify current ACP JSON output shapes needed for safe reconciliation
- verify how Base transaction evidence will be captured
- verify whether the same ACP-on-Base flow can be claimed for both partner stacks

Do not create a job, fund a wallet, add funds, sign a transaction, broadcast, or spend during Phase 0.

If no suitable ACP offering exists for one launch-package task, adjust the demonstration service mapping while preserving Delta's core purpose. Record the substitution. Do not redesign the product around marketplace availability.

## Money and transaction safety

No spending authority is included in this prompt.

Before any live paid or onchain action, stop and obtain explicit user approval that covers:

- provider and offering
- chain/network
- exact or maximum service spend
- which steps may spend
- which actions will broadcast
- whether wallet funding is required
- settlement/completion scope

Do not infer approval from the fact that the user asked you to build the project.

If price is unknown, changed, or over the cap, stop before funding.

Never fund a wallet or increase the budget to make the demo work without approval.

## Paid-job continuity requirements

Persist an attempt intent before a side-effecting provider action.

If the ACP response yields job ID and transaction identity, persist them immediately.

If a command times out or fails after a job or transaction may have been accepted, classify the outcome as ambiguous.

Do not automatically retry create, fund, or settlement in that state.

Reconcile provider history and Base evidence first.

Known ACP lifecycle states should be mapped and preserved. The current planned lifecycle includes open, budget set, funded, submitted, completed, rejected, and expired.

If an ambiguous create has no reliable job ID, only attach it to a discovered job when the current APIs let you identify exactly one matching job with high confidence. If zero or multiple matches remain, enter manual reconciliation and stop replacement spending.

Do not claim exactly-once behavior.

## Security requirements

Read and follow `SECURITY.md` before implementing the ACP adapter.

At minimum:

- no credentials in source, Sibyl, logs, fixtures, screenshots, or demo evidence
- no shell interpolation of user/provider content
- provider output is untrusted
- no untrusted HTML rendering
- external artifact URLs require safe validation before server-side retrieval
- artifact paths use generated IDs
- project scope is checked server-side
- cost approval data cannot be supplied or changed by provider-controlled content

## Deterministic tests before live integration

Use clearly labelled fixture services and ACP fixture JSON.

The required test suite includes:

- unchanged request
- launch date only
- visual brief only
- product description change
- expired result
- implementation version change
- failed step and retry
- real process restart
- two-project isolation
- upstream rerun with unchanged output
- known interrupted ACP job reconciliation
- ambiguous create with no safe match
- ambiguous create with multiple matches
- ambiguous create with one verified match
- ambiguous fund/settlement reconciliation
- quote above approval cap
- unavailable artifact behavior

Do not present fixtures as live integrations.

## Baseline comparison

After deterministic Delta behavior works, build a separate correct LangGraph baseline.

Use narrow relevant node inputs, equivalent TTL, project scope, implementation identity, and persistent storage where appropriate.

Use the comparison to keep claims honest.

Do not intentionally weaken LangGraph and do not demand that Delta invent a new caching technique.

Report overlap clearly. Delta's defensible advantage must come from the integrated revision plan, paid-work record, cost/approval state, provider job continuity, and developer experience actually demonstrated by the implementation.

## UI

Build the engine first.

The final demonstration is one workflow-focused page, not a generic dashboard or chat app.

It must show:

- editable inputs
- three workflow steps
- reuse/rerun/pending decision and reason
- estimated cost or unknown
- actual cost separately
- outputs/artifact references
- provider/offering/job identity for live work
- real loading and waiting states
- restart recovery
- ambiguous/reconciliation states
- explicit execute and spending approval actions
- explicit settlement action when required

Do not display fake progress percentages or invented savings.

## Documentation maintenance

Keep `STATE.md` current throughout implementation.

Update `README.md` only with behavior that is actually implemented and verified.

Update `REFERENCES.md` with exact versions used by the final demo.

Keep `HANDOFF.md` concise and usable after each major session.

Do not duplicate the complete master specification across files.

## Stop for a genuine blocker when

- repository destination is ambiguous
- live ACP discovery finds no suitable offering
- ACP authentication/signer setup is unavailable
- an action would exceed or fall outside approved spending scope
- provider/job/transaction state is ambiguous and cannot be safely reconciled
- Base qualification cannot be verified
- Sibyl cannot serve as authoritative state without an alternative database becoming the real source of truth
- an API mismatch would make a money-sensitive operation unsafe

For routine implementation decisions, make the safest reasonable choice, document it, test it, and continue.

## Completion standard

Do not report the project complete until the minimum complete submission in `MASTER_PLAN.md` is verified.

The final report must state:

- what is implemented
- exact test results
- where Sibyl critical reads and writes are located
- how real process restart recovery works
- live ACP provider/job evidence
- Base transaction/settlement evidence
- estimated, quoted, and actual known costs separately
- baseline comparison result
- strongest remaining limitation
- any blocked required item

Never fabricate partner integrations, test success, cost savings, transaction status, or completion.
