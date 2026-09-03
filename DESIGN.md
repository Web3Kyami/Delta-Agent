# Delta product design

## Purpose and audience

Delta is revision control for paid agent work. A developer changes a request, previews what remains usable, and runs only the work that no longer matches. Delta preserves usable output and keeps interrupted paid jobs from being purchased twice.

The primary audience is a developer or technical operator building workflows that include paid external agents. A secondary audience is a judge or reviewer who needs to understand the mechanism quickly and inspect the evidence behind it.

## Durable product principles

- Developers explicitly declare workflow steps, relevant inputs, dependencies, implementation versions, freshness policies, and provider adapters.
- Delta never asks an LLM to infer a dependency graph from a repository or from vague context.
- The user must be able to understand what existing work remains usable, what must rerun, why, and what additional cost is known.
- The UI must use the real backend state that supports the claim it presents.
- Fixture output is always labelled as fixture output. It is never presented as a live provider result.
- Unknown cost remains unknown. Estimates and actual cost are separate values.
- Editing revision inputs invalidates a stale preview. Execution requires a current preview for the exact input set.
- Paid actions require an explicit spending boundary. Ambiguous paid work is reconciled before replacement execution is offered.
- Work artifacts and revision decisions have visual priority over infrastructure and provider branding.
- The interface exposes honest loading, empty, unavailable, blocked, failure, recovery, and ambiguous states.
- Accessibility is required: semantic structure, visible focus, keyboard operation, readable contrast, reduced-motion behavior, and deliberate responsive layouts.
- Motion explains causality, such as an upstream change affecting a declared downstream dependency. It does not decorate the interface or imply progress that did not occur.

## Application architecture

The application is organized around the user's revision journey:

1. Existing completed work
2. Change request
3. Revision preview
4. Approval, when spending is applicable
5. Execution
6. Result
7. History and recovery when needed

The exact routes, navigation model, template boundaries, and component choices are implementation decisions. Existing routes may remain temporarily for compatibility. Their presence must not become a permanent product requirement.

Revision is primarily an action performed on existing work. Continuity and reconciliation are states associated with an interrupted or ambiguous run. They do not require permanent top-level navigation unless later testing shows that this helps users. Runs and integrations may exist as supporting views, but they must not obscure the primary journey.

## Work-first principle

The application should show the actual work before showing system metadata. For the launch-package workflow, the primary view should make these outputs understandable:

- product visual
- announcement
- translation

Signatures, provider identity, job IDs, persistence tiers, chain evidence, and similar metadata should appear contextually when useful. They should not dominate the first view. The primary action should be obvious and should move the user to the next stage of the revision journey.

## Application states and interaction

The application may use a contextual stage indicator for the journey from work to result. It should communicate location and available next actions rather than act as decorative progress.

The completed-work state should establish that work already exists and show the current outputs or honest empty state. If a deterministic demo has no completed work, initialization must call the real Delta planner and persistence path, then render the resulting state. It must not inject successful HTML.

The change state should keep the workflow identity in route context, show saved values beside editable values, offer human-readable controls, and make changed values visible. Nothing executes while the user edits.

The preview state should lead with the actual dependency sequence and the planner's decisions. Each decision must include its reason and distinguish reuse, rerun, pending dependency, and other supported states. Known additional cost, unknown cost, approval limits, prior cost, and actual cost must not be conflated.

The execution state should be driven by backend state and show a chronological sequence. It may include provider, offering, job, chain, quote, and actual cost only when those values are real. Downstream signature reevaluation should be visible when an upstream execution finishes.

The result state should show the resulting work, what was reused or newly executed, the previous output or revision reference when available, actual known cost, and safe next actions. It must never describe theoretical savings as actual savings.

History should be chronological and useful for selecting a prior run or result. It should show only the records the backend can support, including changed inputs, decisions, executions, costs, status, and timestamp. Recovery and reconciliation should show persisted Delta identity separately from current provider or chain evidence and should never offer an unsafe replacement for an ambiguous paid outcome.

## Visual direction

Do not lock Delta into a generated aesthetic, a fixed palette, a fixed font family, or a fixed shell. A future visual direction should be selected from the product's trust level, work artifacts, audience, and observed task performance.

Durable visual principles:

- clear hierarchy and a calm operational tone
- work artifacts have visual priority
- revision states are unmistakable without relying on color alone
- dependency relationships are understandable
- operational UI is quieter than marketing UI
- use open layouts, dividers, timelines, artifact surfaces, and tables where they clarify the work
- use containers only when grouping has a semantic purpose
- avoid endless card walls, generic metric dashboards, decorative AI styling, gradients used as decoration, and fake terminal aesthetics

### Rejected exploration 1: warm-paper editorial marketing

This direction used beige or paper surfaces, oversized serif treatment, and editorial framing. It is recorded as an exploration and is not a requirement for the product or application.

### Rejected exploration 2: generic developer-tool application

This direction used a persistent dark sidebar, an admin or dashboard shell, repeated rounded panels, metric-card layouts, and tiny technical metadata everywhere. It is rejected as the default application structure.

A generic dark console or grid treatment was also explored for the public site. It must not become Delta's default visual identity.

## Public site

The public site and application are separate surfaces with different jobs. The public site should explain the product quickly, demonstrate revision causality with tangible work, answer trust questions, and lead into the application. It should not be forced to share one exact hero composition, route, palette, or layout with the application.

The current artifact-canvas landing exploration is a documented experiment, not a permanent requirement. Future landing changes must preserve truthful claims, clear calls to action, and the distinction between illustrative examples and live execution.

## Content and trust rules

- Lead with the user's work, the change, the cost boundary, and the next action.
- Keep implementation names and persistence details in context, such as evidence or integration detail, rather than repeating them on every screen.
- Use direct labels for states: reuse, rerun, pending, executing, reconciling, completed, failed, blocked, unavailable, and ambiguous.
- Keep required markers quiet and reveal formatting guidance when it is useful.
- Never invent customers, testimonials, uptime, savings, job counts, transaction confirmation, or security certification.
- Treat provider deliverables and metadata as untrusted data. Escape dynamic content and do not render untrusted HTML.

## Verification requirements

Interface work is not complete because templates exist. Verify the complete path from user input through the UI, API handler, Delta engine, adapter or deterministic service, persistence, returned result, and UI representation.

For each meaningful release, exercise positive and negative cases, including unchanged input, changed launch date, changed visual brief, shared description change, stale preview, failed execution, unavailable artifact, recovery after a fresh process, project isolation, and ambiguous paid work. Inspect every major application route at 1440, 1024, 768, and 390 CSS pixel widths. Check purpose, primary action, overflow, focus order, keyboard operation, readable state language, reduced motion, and honest loading or failure behavior.

## Research history

The following references informed structural questions only. They are inspiration and research history, not implementation requirements or brand direction:

- Relevance AI Workforce, connected workflow topology: https://relevanceai.com/workforce
- Lindy, tangible work artifacts and persistent product access: https://www.lindy.ai/
- Browser Use, direct product framing and dense technical storytelling: https://browser-use.com/
- Inngest, durable execution states and code-to-record storytelling: https://www.inngest.com/
- Radix accessibility guidance for focus and keyboard behavior: https://www.radix-ui.com/primitives/docs/overview/accessibility
- Component Gallery and Web Interface Guidelines, interface anatomy and interaction review: https://component.gallery/ and https://interfaces.rauno.me/

## Document ownership

`DESIGN.md` owns durable interaction and visual principles.

`MASTER_PLAN.md` owns stable product and technical architecture.

`IMPLEMENTATION_PLAN.md` owns build order and acceptance gates.

`STATE.md` owns current verified implementation status.

Temporary route structures, page compositions, palettes, typography choices, and component decisions must not become permanent requirements merely because they exist in the current implementation.
