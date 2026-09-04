# Delta Security and Spending Boundaries

## Purpose

Delta coordinates paid external agent work. Its main security risks are credential exposure, untrusted provider content, duplicate or unintended spending, ambiguous onchain outcomes, unsafe artifact handling, and cross-project state leakage.

This document owns security and spending requirements for the initial submission.

## Trust boundaries

### Trusted application code

Delta's core planner, persistence adapter, provider adapters, and UI server are trusted code.

Developer-declared workflow definitions are trusted configuration for the initial submission.

### Sibyl Memory

Sibyl is trusted as the authoritative persistent state mechanism for the hackathon proof, but stored data must still be treated as application data, not executable instructions.

### Virtuals ACP

ACP command output, offering metadata, provider messages, deliverables, URLs, prices, and status text are external data.

Do not treat any provider-controlled string as a command, filesystem path, HTML fragment, or trusted URL.

### Base RPC and explorers

RPC responses and explorer content are external evidence. Validate expected data shapes and match transaction identity, chain ID, sender where known, and expected status before using them as settlement evidence.

### Browser

The browser is untrusted input for workflow fields, project IDs, and actions. Validate all values on the server.

## Credential handling

Never store any of the following in source code, Sibyl Memory, fixtures, journal events, API responses, screenshots, logs, or demo evidence:

- private keys
- seed phrases
- wallet recovery material
- ACP OAuth tokens
- ACP keychain contents
- Sibyl credentials
- API keys
- session cookies
- bearer tokens
- user passwords

Use the supported secure credential stores of each integration.

Current ACP documentation states that authentication tokens and signer key material are stored through OS keychain-supported flows. Do not replace that with plaintext environment files for convenience.

Sibyl credentials documented under `~/.sibyl-memory/credentials.json` must not be copied into the repository.

Environment-variable documentation should name variables only, never include real values.

## Subprocess safety

The ACP integration must use a narrow command adapter.

Requirements:

- execute with argument arrays
- never use `shell=True`
- never build a command by concatenating user or provider text
- use `--json` when supported
- apply bounded timeouts
- capture stdout and stderr separately
- parse only expected JSON structures
- redact known secret patterns before logging
- preserve the raw exit classification internally when needed for reconciliation

Workflow inputs passed as ACP requirements must be encoded as data, not shell syntax.

## External content handling

Provider output is untrusted.

### Text

Render provider text as escaped text. Never inject it as HTML.

### Structured data

Validate against the expected schema before storing it as a successful result.

### URLs

Do not automatically fetch arbitrary provider URLs without validation.

For server-side artifact retrieval in the initial implementation:

- allow only `https` unless a specific provider requires another safe scheme
- reject credentials embedded in URLs
- resolve and reject loopback, link-local, private, multicast, and other non-public destinations
- apply the same checks after redirects
- limit redirect count
- enforce maximum response size
- enforce expected media types
- set network timeouts
- write to a generated artifact path
- hash bytes before marking the artifact available

If safe retrieval is not possible, preserve the external reference and mark the artifact as externally hosted rather than weakening URL checks.

Do not inline remote HTML, SVG with active content, scripts, or provider-supplied iframes in the application page.

For SVG fixture artifacts generated locally, sanitize or generate them from trusted deterministic code.

## Filesystem safety

Artifact paths must use generated IDs.

Never use raw project IDs, provider filenames, offering names, or URLs as filesystem paths.

Store artifacts outside the source tree and source-control ignore them.

Use an application-controlled root directory and prevent path traversal.

For local artifact verification, check file presence and optionally re-hash contents before reuse.

## State isolation

Every work record, plan, attempt, and active head must include project scope.

Sibyl tenant isolation is necessary but not sufficient for Delta's project isolation requirement.

Tests must prove that two projects with identical content cannot share reusable work.

Do not expose another project's work, job IDs, artifact paths, or history through API endpoints.

## Spending authority

### Principle

A revision plan describes possible future cost. It does not authorize it.

### Required approval data

Before any live action that can broadcast or spend, Delta or the builder must have explicit approval that identifies:

- project/plan
- network and chain ID
- provider and offering where known
- allowed step IDs
- maximum total service spend
- optional maximum per-job spend
- allowed transaction actions
- approval expiration

### Builder-specific rule

During implementation, the builder must stop and ask the user before:

- ACP job creation if it broadcasts
- wallet top-up
- escrow funding
- settlement/completion transaction
- separate Base transaction
- paid provider call

Approval of planning or code is not approval to spend.

### Runtime rule

The application must compare the provider quote against the stored approval before funding.

If the quote is higher, changed, unavailable, or denominated differently, block and request a new approval.

## Cost integrity

Keep these values separate:

- preview estimate
- provider quote
- actual service amount funded/settled
- network gas amount

Never fill an unknown value with an estimate.

Never claim savings that were not measured from comparable actual or quoted costs.

## Transaction safety

### Before broadcast

Persist an attempt intent with:

- unique local attempt ID
- desired step/input signature
- provider/offering
- chain
- approved cap reference
- intended action

### After response

Persist job ID and transaction hash immediately when available.

### Ambiguous response

A timeout, connection loss, CLI crash, or parsing error can occur after a provider or blockchain accepted an action.

Therefore:

- do not infer "not submitted" from local failure
- mark the attempt ambiguous
- reconcile provider state and chain evidence first
- do not broadcast a replacement until identity and state are known

### Funding

For an ACP job at `budget_set`, verify the quote matches the job and is within approval before funding.

Do not accept a funding amount directly from browser input without matching provider state.

### Settlement

Completion releases escrow. Treat it as an explicit money-affecting action.

In the initial UI, require a clear settlement action or ensure the prior approval explicitly covered settlement for the identified job and cap.

If completion result is ambiguous, query job history and chain evidence before retry.

## Exactly-once claims

Do not claim exactly-once job creation, payment, execution, or settlement.

Delta's guarantee is narrower:

- durable attempt intent
- durable provider job identity when known
- reconciliation before replacement or retry
- conservative blocking when identity remains ambiguous

This reduces duplicate-spend risk but cannot eliminate it when the external protocol does not expose enough idempotency or reconciliation information.

## Concurrency boundary

Initial submission supports one writer process.

An in-process lock prevents two local execution requests from acting on the same step concurrently.

Persisted active-attempt state supports restart discovery but does not provide an atomic distributed lease.

Do not deploy multiple writers against the same store and claim safety.

## Logging and evidence

Logs may contain:

- local attempt IDs
- project IDs if non-sensitive
- workflow/step IDs
- provider public address
- offering ID/name
- job ID
- chain ID
- public transaction hash
- normalized status
- known cost amounts
- reason codes

Logs must not contain credentials or full sensitive user inputs unless explicitly required and safe.

Sanitize provider messages before including them in screenshots.

Demo evidence should show public transaction/job identifiers only.

## Browser protections

- escape all provider and user text
- use CSRF protection appropriate to the chosen stack for state-changing actions if the app is exposed beyond localhost
- use secure cookies if sessions are introduced
- do not put secrets in browser storage
- do not rely on localStorage for authoritative recovery state
- use `rel="noopener noreferrer"` for external links
- apply a restrictive Content Security Policy if practical

The trusted-handoff public demo uses one fixed, visibly supplied credential as guided entry, not as production authentication. It requires signed, HttpOnly, SameSite sessions, per-session CSRF protection, and isolated server-controlled workspace identities. The public credential must never authorize live ACP spending, wallet actions, funding, completion, settlement, or other valuable permissions.

Delta must enforce inheritance policy before constructing an LLM prompt, message, tool argument, trace, or provider request. Blocked work content must not be exposed to the receiving model and must not leak through receipt summaries, logs, errors, or unauthorized browser payloads.

## Dependency and supply-chain safety

Pin major integration versions used for the final demonstration.

Prefer official packages and repositories.

Record package versions in `REFERENCES.md`.

Do not copy third-party source code unnecessarily. Respect its license and preserve required notices if code is reused.

## Security verification checklist

Before live spending:

- [ ] repository secret scan is clean
- [ ] ACP CLI authentication uses supported secure flow
- [ ] signer policy is reviewed
- [ ] wallet balance is sufficient but not excessive for approved demo
- [ ] provider/offering is verified
- [ ] chain is verified
- [ ] user approved exact cap and action scope
- [ ] intent persistence is verified
- [ ] reconciliation fixture tests pass

Before submission:

- [ ] no secrets in git history or evidence
- [ ] project isolation test passes
- [ ] path traversal tests pass
- [ ] external URL validation tests pass if remote downloads are enabled
- [ ] ambiguous create/fund/settle tests pass
- [ ] quote-over-cap test passes
- [ ] restart reconciliation test passes
- [ ] public transaction evidence is consistent with recorded job state
