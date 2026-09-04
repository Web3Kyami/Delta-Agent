# Delta Demo Runbook

> **Migration notice:** The launch-package paths in this runbook document the currently implemented legacy demo and historical integration evidence. They are not the approved product direction or the final judge story. The trusted-handoff runbook will replace them during Phases 2 through 5 of `IMPLEMENTATION_PLAN.md`. Until then, do not present the legacy flow as the new Agent A to Agent B handoff product.

## Purpose

This runbook defines the reproducible judge path and the evidence needed to support Delta's claims. It must never instruct the presenter to fake completion, cost, provider state, or partner integration.

The approved future judge path uses AI software-work handoff as the primary scenario, Home repair handoff for a general audience, and Paid research handoff for ACP/Base evidence. It must prove that blocked work stays outside Agent B's context and that the Reuse Receipt reflects persisted gate decisions. None of that new behavior is implemented yet.

The hackathon demo is limited to 2 to 5 minutes, so full live provider execution may need to be prepared in advance while still showing a genuine fresh-session recall and genuine integration evidence.

## Evidence integrity

Every visible success must come from the real path the demo claims to show. Do not hardcode provider output, job state, transaction evidence, artifact state, revision decisions, or completion results. Keep UI state tied to the returned API and persisted state.

Deterministic fixtures are allowed for local planner and failure-state demonstrations only. Label every fixture or deterministic test service clearly, keep its path distinct from live adapters, and never present fixture behavior as live ACP, Sibyl, Base, provider, wallet, job, or transaction evidence. If a live dependency is unavailable or a result cannot be verified, show the honest unavailable, error, blocked, ambiguous, or reconciliation state.

## Local Phase 5 demonstration

Start the server with `.venv/bin/python run_demo.py`, then open `http://127.0.0.1:8000`. The public page contains a clearly labelled illustrative revision. Open `/app/revisions` through the primary call to action for the working demonstration. The application is marked `Demo mode`. Preview, execute, and restore use the real Delta engine and Sibyl store, while the launch-package services are input-sensitive deterministic fixtures. Their outputs, source labels, and cost status must remain visible as fixture evidence. Do not describe this path as live ACP, provider, wallet, job, or Base evidence. Paid provider actions stay unavailable until a separately approved live integration is attached.

## Current recording path

Until the live ACP capture and artifact checks are complete, record the local
product walkthrough rather than presenting it as a completed partner demo.

Use a fresh project ID such as `video-walkthrough` or point
`DELTA_DEMO_MEMORY_PATH` at a new local database. Start the server, open the
printed URL, and show these beats in one session:

1. The public product story, its `Illustrative revision` label, and the working `Open workspace` call to action.
2. The application `Demo mode` badge and editable launch-package inputs at `/app/revisions`.
3. Preview with the initial values. Show `Rerun` for the first two steps and
   `Pending dependency` for translation.
4. Execute the deterministic workflow. Show the input-sensitive fixture
   outputs, the zero live spend, and the persisted result labels.
5. Change only the launch date and preview again. Show visual `Reuse`,
   announcement `Rerun`, and translation waiting for the new announcement.
6. Execute the revised workflow, then open Runs to show the saved step states.
7. Open Continuity and use `Restore saved work` to show persisted outputs.
8. Open Integrations and point out that provider actions are unavailable in demo mode.

If external ACP or Base evidence is shown separately, label it as recorded
external evidence and do not imply that it completed during this local UI
segment. The live Phase 7 and final submission gates remain separate.

## Phase 6 baseline evidence

Run `.venv/bin/python -m delta.baseline` to generate a fresh comparison from disposable SQLite state. The harness uses current LangGraph APIs with project-scoped, relevant-input cache keys, implementation identity, TTL, and a persistent checkpointer. Keep this output labelled as deterministic baseline evidence. It measures overlap with Delta and does not prove any live provider, wallet, ACP, or Base behavior.

## Preconditions for a submission demo

Do not record the final judge demo until:

- required deterministic tests pass
- real process restart test passes
- a genuine ACP service job has completed successfully
- Base payment/settlement evidence is available
- actual known costs are stored
- the live provider and offering remain identifiable
- secrets have been removed from UI/log output
- README points to Sibyl critical read/write paths
- `STATE.md` accurately states remaining limitations
- no known open ACP attempt remains unresolved. The current Aaga job `75773`
  is open and unfunded because the provider rejected the installed CLI's
  requirement envelope, so it must be reconciled before any replacement run.

## Required evidence bundle

Keep a local evidence directory outside source control unless artifacts are sanitized for public inclusion.

Evidence should include:

- application commit hash used for the demo
- test summary
- Sibyl health output with secrets excluded
- ACP CLI version
- public ACP job ID and chain ID
- public provider/offering identity
- sanitized job lifecycle output or history
- Base transaction hash for the demonstrated payment/settlement
- Base transaction receipt status
- actual funded/settled USDC amount
- gas amount if available
- deterministic baseline comparison output
- timestamps for the restart demonstration

Never include OAuth tokens, private keys, seed phrases, keychain contents, or Sibyl credentials.

For every meaningful capability shown, retain evidence for one positive path and one changed-input or negative path where practical. A screenshot or fixture output alone does not establish that the capability works.

## Pre-demo setup

For the current ACP client workflow, start the event listener before any live job creation and keep its local event file outside source control. When scripts or output-captured runners drive authentication, use the split `acp configure start --json` and `acp configure complete --request-id ... --json` flow. Use persisted Delta state and ACP history for restart recovery.

1. Checkout the exact demo commit.
2. Activate the documented Python environment.
3. Confirm Node and ACP CLI versions.
4. Run `sibyl health` and verify the expected tenant/database.
5. Confirm the ACP agent identity and wallet address without exposing secrets.
6. Confirm the intended Base chain is 8453 for mainnet demonstration.
7. Confirm the approved demo spending cap has already been granted by the user.
8. Confirm the selected provider/offering price still fits the cap.
9. Confirm artifact directory is persistent and available.
10. Run the fast automated test subset needed for confidence.

## Full validation path before recording

This path can take longer than the video.

### A. Initial live run

Use the launch-package workflow or the documented substituted service mapping.

Start and verify the required ACP event listener before creating the job.

1. Create a new project ID, for example `judge-live-a`.
2. Enter initial product description, visual brief, launch date, and target language.
3. Preview.
4. Verify no previous work is reusable.
5. Verify all live paid steps show a current estimate or `unknown`.
6. Approve only within the preauthorized cap.
7. Execute.
8. Confirm ACP job identity is persisted immediately.
9. Confirm quoted budget before funding.
10. Fund only within approval.
11. Wait/reconcile for provider submission.
12. Validate deliverable safely.
13. Approve settlement according to the authorized scope.
14. Confirm terminal completed state.
15. Confirm actual known service cost and Base receipt evidence.

If a provider is slow, do not invent progress. Leave the state as awaiting provider and continue validation when the provider actually responds.

### B. Real restart

1. Note the current time and project ID on screen.
2. Stop the Delta application process completely.
3. Start a fresh process.
4. Reload the same project without relying on browser local storage.
5. Confirm outputs, job identity, cost state, and execution history restore from Sibyl.
6. Preview the unchanged request.
7. Confirm all valid completed work is reusable and additional service cost is zero for reusable paid steps.

This is the critical Sibyl cold-start recall beat.

### C. Revision

Change only the launch date.

Expected preview:

- visual: reuse
- announcement: rerun
- translation: pending dependency until announcement output exists

Execute within approved budget.

After announcement returns:

- if announcement output changed, translation reruns
- if announcement output signature is unchanged, translation reuses prior completed work

Show the final reason beside translation.

### D. Recovery evidence

For a separate controlled validation, stop the application after a real ACP job ID is known but before the job becomes terminal.

Restart and show that Delta loads the same job identity from Sibyl and reconciles provider state before doing anything that could create a replacement.

Do not deliberately cause an unknown-job ambiguous payment state with real funds just for the demo. The ambiguous path can be demonstrated through sanitized deterministic fixtures.

## Recommended 2 to 5 minute video path

The video should be concise and truthful.

### Beat 1: Problem and product, about 30 seconds

Explain:

- paid agent workflows are often revised
- rerunning everything can create unnecessary jobs and spending
- Delta previews reuse/rerun decisions, persists paid-work identity, and reconciles interrupted work

Do not claim a new caching algorithm.

### Beat 2: Show completed real integration evidence, about 30 to 45 seconds

Show one completed project record containing:

- genuine ACP job ID
- provider/offering
- Base chain 8453
- actual service cost
- public Base transaction evidence

Explain that this is real paid service work from the validation run.

### Beat 3: Cold-start restart, about 45 seconds

In one continuous segment:

1. stop the app process
2. start a fresh process
3. reload the same project
4. show restored outputs and job identity
5. show unchanged preview reusing completed work

Keep an on-screen timestamp or commit hash as required by the hackathon rules.

### Beat 4: Revision preview, about 45 seconds

Change launch date only.

Show:

- visual reused
- announcement rerun
- translation pending dependency
- additional estimated cost only for work currently expected to rerun

Explain that final translation choice waits for the actual new announcement output.

### Beat 5: Selective execution and continuity, about 45 to 90 seconds

If the live provider response is fast enough, execute and show the final result.

If the provider response is not reliably fast enough for a 2 to 5 minute recording, do not fake a completion. Instead:

- show the real newly created job and its persisted ID if the approved budget permits a new live run
- show Delta's genuine waiting state
- then show a previously completed real revision record from the same build as historical evidence, clearly labelled as an earlier completed run

The video must not imply that historical evidence completed during the current live segment.

### Beat 6: Close, about 20 seconds

State the narrow product claim:

Delta packages revision preview, durable paid-work records, and external-job reconciliation around established caching/persistence techniques.

Mention the strongest current limitation from `STATE.md`.

## Deterministic judge fallback

If a live ACP provider is offline during judging:

1. Do not claim the fixture is live ACP.
2. Show the previously captured real ACP/Base evidence from the validated run.
3. Run the local deterministic workflow to demonstrate planner semantics and restart behavior.
4. Show the current provider error/offline state honestly.
5. Point to the live integration test record and transaction/job identifiers.

This fallback is acceptable only if the submission already exercised genuine integrations before recording/submission. It is not a substitute for completing the required live validation phase.

## Required scenario evidence outside the short video

Automated tests or reproducible scripts must cover:

- unchanged request
- launch date only
- visual brief only
- shared product description
- expired result
- implementation version change
- failed step and retry
- real restart
- two-project isolation
- upstream rerun with unchanged output
- known interrupted ACP job reconciliation
- ambiguous ACP create fixture
- ambiguous fund fixture
- quote over approval
- unavailable artifact

README should link to the command that runs this suite.

## Judge questions to prepare for

### Why not just LangGraph caching?

Answer with the measured comparison. Acknowledge that LangGraph already handles selective caching and persistence. Explain Delta's integrated plan explanations, paid-work records, job reconciliation, and cost/approval continuity only where the implementation actually demonstrates them.

### Why Sibyl?

Show that the fresh process cannot reconstruct completed work, plan state, or active ACP job continuity if the Sibyl layer is removed.

### What prevents double payment?

Do not say "exactly once." Explain that Delta persists attempt intent and job identity, reconciles provider/chain state before replacement, and blocks when identity remains ambiguous.

### Where is Base used?

Show the real onchain funding or settlement transaction on Base and the corresponding ACP job record.

### What happens if an artifact disappears?

Explain that artifact availability is part of reuse validity. Delta does not automatically spend again when a paid artifact is temporarily unavailable; it surfaces recovery/reconciliation state.

## Demo stop rules

Stop and explain rather than improvising if:

- wallet balance is insufficient
- price exceeds approved cap
- provider changes offering terms
- ACP job state is ambiguous
- chain does not match the approved chain
- a required transaction would exceed approval
- credentials appear in terminal output
- live provider is unavailable

Never fund a wallet or increase a budget during the demo without prior approval.
