# Delta product design

## Purpose and audience

Delta is a trusted handoff layer for agent work. Agent A completes work, its session ends, and Agent B arrives later. Delta decides what previous work may cross the handoff before any context reaches Agent B.

The primary audience is a developer building agents that need durable, controlled continuity. A secondary audience is a judge or nontechnical reviewer who needs to understand what crossed the handoff, what stopped, why new work ran, and what evidence supports the result.

## Durable product principles

- Agents can inherit previous work without inheriting everything.
- Remembered work is not automatically trusted or authorized work.
- Developers explicitly declare workflow steps, relevant inputs, dependencies, implementation versions, freshness policies, and provider adapters.
- Delta deterministically evaluates validity, trust, authorization, dependencies, and external-job safety.
- The gate runs before prompt or context construction. Blocked work never enters the receiving model's prompt and is not hidden through prompt instructions.
- The LLM may act as Agent A or Agent B, but it does not decide reuse eligibility or access control.
- The user should understand what previous work exists, what may cross, what is blocked, what must rerun, what must wait, and what the additional cost is where known.
- The UI uses the backend state that supports every claim.
- Fixture output is always labelled and never presented as live provider evidence.
- Unknown cost remains unknown. Estimate, quote, actual service cost, gas, and hypothetical avoided cost remain distinct.
- Paid actions require explicit authority separate from public demo access.
- Work artifacts and consequences have visual priority over infrastructure and provider branding.
- Accessibility is required: semantic structure, visible focus, keyboard operation, readable contrast, reduced motion, and deliberate responsive layouts.
- Motion may explain handoff causality or state change. It must not imply execution or progress that did not occur.

## Central interaction metaphor

The handoff boundary is the product's organizing idea:

`Agent A -> Delta boundary -> Agent B`

The interface should make the boundary observable:

- Candidate work approaches the boundary from Agent A and Sibyl recall.
- Approved work visibly crosses to Agent B.
- Blocked work visibly stops before Agent B.
- Invalid work is routed to new execution.
- Downstream work waits visibly for required new output.
- The final Reuse Receipt records what crossed, what did not, and why.

This can be communicated with sequence, spatial separation, labels, and restrained motion. It must not become a decorative node graph.

## Application architecture

The application is organized around the user's handoff journey:

1. Demo login and scenario selection
2. Agent A's completed work
3. Agent A session end
4. Agent B start
5. Sibyl recall and Delta gate
6. Reuse, blocked, rerun, waiting, or reconciliation decisions
7. Missing-work execution
8. Final result
9. Reuse Receipt
10. Scenario reset when needed

The application should be simpler than the backend. Users should not have to navigate persistence tiers, provider internals, or lifecycle machinery to operate the product.

Current Overview, Revisions, Runs, Continuity, Integrations, and launch-package routes are legacy implementation details. They may remain temporarily during migration, but they are not product requirements.

## Work-first presentation

Show the actual work and handoff consequence before technical metadata. The primary surface should answer:

- What did Agent A complete?
- What did Delta find?
- What may Agent B receive?
- What was blocked?
- What new work is needed?
- What is waiting?
- What did the handoff cost or avoid purchasing, if proven?

Signatures, provider identity, job IDs, Sibyl record identity, policies, hashes, chain evidence, and cost evidence belong in contextual details. Blocked content itself must never be exposed through those details to an unauthorized recipient.

## Reuse Receipt

The receipt is a first-class product result, not an infrastructure log.

Its first level should show consequence-first counts such as previous work found, reused, blocked, new work needed, and waiting. Each item should include a plain-language reason.

Progressive evidence may include source agent and session, Sibyl identity, dependency evidence, artifact integrity, policy decision, provider and ACP job identity, Base evidence, previous cost, and new cost only when the backend supports it.

## Application states and interaction

Support honest states for:

- signed out, invalid login, expired session, and signed in
- scenario uninitialized, initializing, ready, resetting, and reset failed
- Agent A working, completed, failed, and session ended
- Agent B not started, started, and failed
- recalling, no candidate found, candidate found, reusable, unauthorized, invalid, pending dependency, reconciliation required, and artifact unavailable
- executing, awaiting provider, ambiguous, completed, and failed
- stale generation, stale gate result, stale plan, and unavailable receipt
- public mode blocked from live spending

Do not use fake percentage progress. State-changing controls must have real busy, disabled, error, and recovery behavior.

## Public demo identity and isolation

The fixed public login is a guided entry experience, not a security claim. Show the supplied credentials on the login screen, show `Delta Dave` after login, and support sign out.

Authentication identity and workspace identity are separate. Each browser session receives an isolated workspace, and each scenario receives an isolated scope and generation. Reset affects only the selected workspace and scenario. The public login never grants live ACP, wallet, funding, completion, or settlement authority.

## Visual direction

The landing page will use a deliberate Delta-specific neo-brutalist language. Neo-brutalism should clarify the handoff rather than decorate it.

Use:

- the boundary as the primary visual device
- strong structural rules and exposed joins
- deliberate offsets that show movement across the gate
- decision stamps and direct state language
- restrained high-contrast color assigned to meaning
- large, direct display typography paired with highly readable interface typography
- borders and shadows only when they explain structure or state
- a vertical causal sequence on mobile

Avoid:

- random bright blocks
- arbitrary heavy shadows
- generic gradients or glass cards
- fake terminals and cyberpunk AI imagery
- dashboard metric walls
- decorative node graphs
- endless repeated cards
- random token values
- visual noise that obscures authorization or consequence

The application may be visually quieter than marketing. It should feel like operating the handoff, not inspecting an internal architecture dashboard.

## Legacy design material

The launch-package product visual, announcement, translation, solar-charger artwork, current landing composition, and existing route structure are not future requirements. They remain implementation history until the migration safely removes or replaces them.

Useful principles from the previous design remain active: work-first presentation, backend-derived state, progressive evidence, truthful fixture/live distinctions, artifact priority, accessibility, responsive behavior, and avoidance of generic developer dashboards.

## Content and trust rules

- Lead with the work, boundary decision, consequence, and next action.
- Use direct labels: reuse, blocked, rerun, waiting, reconciling, completed, failed, unavailable, and ambiguous.
- Keep implementation names in evidence details rather than repeating them throughout the journey.
- Never invent customers, testimonials, uptime, savings, job counts, transaction confirmation, or security certification.
- Escape provider and user content. Never render untrusted HTML.
- Never expose blocked work through summaries, receipts, logs, or technical evidence.

## Verification requirements

Interface work is complete only after the path from user action through the API, gate, engine, provider or deterministic service, Sibyl persistence, returned result, and rendered state is verified.

Exercise positive and negative cases, including valid authorized work, valid unauthorized work, changed inputs, pending dependencies, stale gate results, failed execution, unavailable artifacts, fresh-process recovery, workspace and scenario isolation, reset, ambiguous paid work, and public denial of spending.

Inspect major routes at 1440, 1024, 768, and 390 CSS pixels. Check purpose, primary action, overflow, focus order, keyboard operation, decision language, contrast, touch targets, reduced motion, and honest loading or failure behavior.

## Document ownership

`DESIGN.md` owns durable interaction and visual principles. `MASTER_PLAN.md` owns stable product and architecture requirements. `IMPLEMENTATION_PLAN.md` owns build order and exit gates. `STATE.md` owns current verified implementation status.

No actual new interface design has been implemented by this document update.
