# Delta product design

## Product position

Delta is revision control for paid agent work. A user changes a request, previews the impact, and runs only the work that no longer matches. Delta preserves usable output and keeps interrupted paid jobs from being purchased twice.

The primary audience is a developer or technical operator building workflows that include paid external agents. The secondary audience is a hackathon judge who must understand the product in a few minutes.

## Product architecture

Delta has two connected surfaces with different jobs.

### Public site

The public site explains the product, demonstrates the revision model, answers the main trust questions, and leads to one action: open the workspace.

Routes and sections:

- `/`: product story, interactive revision example, core capabilities, execution model, integration context, and final call to action
- The primary call to action opens `/app/revisions`
- Product navigation links move to meaningful sections on the public page

### Application

The application uses real routes. Sidebar navigation changes the current page instead of scrolling a long document.

- `/app/overview`: project status, current revision summary, and the next useful action
- `/app/revisions`: edit the request, preview impact, and execute the approved local path
- `/app/runs`: inspect current run and step-level states
- `/app/continuity`: recover saved work and inspect reusable outputs
- `/app/integrations`: inspect persistence, provider, and settlement connections

The current release has one launch-package project. A project switcher must not imply multiple projects until project selection exists.

## Main user journeys

### First visit

1. Understand that Delta avoids repeating paid work after a request changes.
2. Interact with a launch-date, visual-brief, or product-description change example.
3. Open the workspace.

### Revision

1. Edit the launch-package request.
2. Preview the exact input set.
3. Review reuse, rerun, waiting, reason, and estimated added cost.
4. Execute the deterministic local path or see an honest blocked state.
5. Inspect the resulting run or recover it later.

### Recovery

1. Open Continuity.
2. Restore the project scope.
3. See which outputs were recovered and whether each artifact is available.
4. Return to Revisions with the recovered context intact.

## Brand direction

The Delta mark represents controlled change. Three sides form a stable system and one colored segment identifies the part that changes. The name is lowercase in the wordmark and sentence case in prose.

The public site feels like a kinetic execution system: precise, technical, high contrast, and visibly shaped by Delta's revision model. Deep graphite is the main field, cold white creates section contrast, orange marks changed or rerun work, cool violet marks unresolved dependencies, and muted neutral marks preserved work. Solid color, geometry, topology, and purposeful motion carry the identity. The rejected warm-paper editorial direction must not be recreated.

### Marketing composition

- Purpose: establish the category and make the mechanism understandable
- Focal point: a completed three-step workflow with believable illustrative artifacts and a changed input entering the dependency topology
- Layout gravity: concise promise beside a product visualization that is visible without scrolling on a typical desktop viewport
- Typography: Manrope for strong technical hierarchy and DM Mono only for state, signatures, IDs, cost, and metadata
- Palette: graphite and cold white fields, Delta orange for changed or rerun work, restrained violet for unresolved dependencies, and neutral green-gray for preserved work
- Surfaces: compact technical planes, small radii, crisp borders, and connected paths. No paper shadows, glass, decorative gradients, or generic card grids
- Motion: the Delta change signal travels through affected declared dependencies, then node states settle. Reduced motion exposes the same final state immediately.
- Mobile: the workflow becomes a deliberate vertical dependency flow with full text state and early access to the primary action

### Application composition

- Purpose: complete a revision quickly and inspect evidence when needed
- Focal point: the revision result, not the navigation or storage provider
- Layout gravity: compact sidebar, calm content header, task-specific main pane
- Typography: moderate scale, clear labels, tabular values for cost and identifiers
- Surfaces: low-radius panels used only for grouped controls or state
- Motion: request loading, result transitions, and navigation drawer only
- Mobile: each page becomes one deliberate task with a compact header and drawer

## Content rules

- Lead with the user's work, change, cost, and next action.
- Do not mention Sibyl on general product surfaces. Show it on Integrations or inside technical evidence.
- Use `saved work`, `continuity`, and `recovery` in the normal interface.
- Reveal project ID rules only while the field is focused or invalid.
- Keep required markers quiet. Native validation and clear labels carry the main burden.
- Never present fixture output as a live provider result.
- Never invent customers, testimonials, uptime, savings, job counts, or security certification.

## Components and states

### Navigation

- Public navigation: Product, How it works, Integrations, Open workspace
- Application navigation: Overview, Revisions, Runs, Continuity, Integrations, Back to site
- Active application navigation reflects the current URL
- Mobile navigation is a dialog-like drawer with focus return and Escape handling

### Revision form

- Required labels stay visible
- Helper text appears on focus where it is only formatting guidance
- Preview is the dominant action
- Execution stays disabled until the exact inputs have a current preview
- Editing any field invalidates the preview immediately

### Workflow map

- Marketing mode is labelled `Illustrative preview`
- Application mode is derived from API state
- State always includes text and shape, not color alone
- Motion explains signal direction and state change

### Feedback

- Buttons keep a stable width while loading
- Busy operations set `aria-busy` and prevent duplicate activation
- Errors explain the next action and move focus to the summary
- Unknown cost remains `Unknown`
- Unavailable provider or chain state remains `Not connected` or `Unavailable`

## Delivery plan

### 1. Product structure

Create the public route, five application routes, shared application shell, and route tests.

### 2. Public story

Build the landing page and an interactive, clearly illustrative revision map. Add working calls to action to the revision workspace.

### 3. Core workspace

Move the existing preview and execution path into Revisions. Keep the server, CSRF, validation, persistence, and stale-plan checks unchanged.

### 4. Operational pages

Build Overview, Runs, Continuity, and Integrations from current API state. Do not add dead controls or imply unavailable backend behavior.

### 5. Interaction and accessibility

Add route-aware navigation, mobile drawer behavior, progressive field help, loading states, focus management, reduced motion, and responsive layouts.

### 6. Verification

Exercise landing calls to action, every application route, preview, execute, changed input, recovery, error, empty, loading, and unavailable states. Inspect at 390, 768, 1024, and 1440 CSS pixels. Run the full suite.

## Research basis

Checked on 2026-09-03:

- Relevance AI Workforce brings the visual canvas and connected agent topology close to the main promise. Delta uses this structural lesson to show its real three-step dependency model immediately: https://relevanceai.com/workforce
- Lindy makes concrete product artifacts carry the story and keeps primary product access persistent in navigation. Delta uses compact visual, announcement, and translation artifacts instead of abstract agent artwork: https://www.lindy.ai/
- Browser Use leads with an unusually direct product statement and keeps technical product concepts visually dense. Delta applies that directness while retaining its own execution-record language: https://browser-use.com/
- Inngest explains developer infrastructure through durable execution states and code-to-record storytelling. Delta uses a compact workflow definition paired with its resulting work record: https://www.inngest.com/
- Radix documents accessible focus, keyboard, and state behavior: https://www.radix-ui.com/primitives/docs/overview/accessibility
- Component Gallery and Web Interface Guidelines informed component anatomy and interaction review: https://component.gallery/ and https://interfaces.rauno.me/

These references provide structural evidence only. Delta does not copy their branding, claims, code, or interface.

### Landing redesign implementation note

Useful structural ideas are: put the behavior above the fold, use the topology itself as the hero artifact, let motion show causality, place real-looking but clearly illustrative output inside nodes, alternate dense dark execution fields with cold-white explanatory fields, simplify the topology into a vertical flow on mobile, and keep navigation actions literal. Delta's identity remains its controlled change signal, explicit reuse/rerun/pending decisions, paid-job reconciliation, and inspectable work record.

### Hero exploration record, 2026-09-03

Three spatial directions were considered before implementation:

- Artifact canvas: a completed launch package arranged on overlapping planes, with the changed input entering the composition.
- Before and revision: preserved, updated, and waiting artifacts compared as layered states.
- Production line: three tangible outputs moving through a linear revision boundary.

The artifact canvas won because it communicates Delta within five seconds, keeps all completed work perceptible, and gives the change a physical path without turning the hero into a schematic node graph. The chosen hero uses an original local product-campaign image at `delta/static/solar-charger-campaign.png`, generated specifically as a fictional launch-package visual with no logos, text, or external imagery. The announcement and translation are designed document artifacts and are labelled illustrative in the scene.
