"""The three Phase 2 handoff scenarios.

These are deterministic local services for the no-spend demo. They share one
workflow shape and the same Delta gate, so the scenarios exercise one product
contract instead of three separate applications.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .core import (
    CostEstimate,
    ExternalExposure,
    InputSpec,
    Scope,
    Step,
    WorkDeclaration,
    Workflow,
    step_output,
    workflow_input,
)
from .fixtures import DeterministicFixtureExecutor
from .handoff import ExternalExposureRule, InheritancePolicy, PolicySet, ProviderRule


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    title: str
    audience: str
    description: str
    workflow_id: str
    work_labels: Mapping[str, str]
    initial_inputs: Mapping[str, str]

    def workflow(self, executors: Mapping[str, Any] | None = None) -> Workflow:
        active = executors or scenario_fixtures(self.scenario_id)
        prefix = self.scenario_id
        return Workflow(
            id=self.workflow_id,
            version="1",
            inputs={
                "brief": InputSpec("string"),
                "revision": InputSpec("string"),
            },
            steps=(
                Step(
                    "shared_context",
                    f"{prefix}-context-v1",
                    {"brief": workflow_input("brief")},
                    estimated_cost=CostEstimate("0.10", source="deterministic-fixture"),
                    executor=active["shared_context"],
                    declaration=WorkDeclaration("shared_context", ExternalExposure.SHAREABLE),
                ),
                Step(
                    "private_notes",
                    f"{prefix}-private-v1",
                    {"brief": workflow_input("brief")},
                    estimated_cost=CostEstimate("0.20", source="deterministic-fixture"),
                    executor=active["private_notes"],
                    declaration=WorkDeclaration("private_notes", ExternalExposure.INTERNAL_ONLY),
                ),
                Step(
                    "dependent_summary",
                    f"{prefix}-summary-v1",
                    {"notes": step_output("private_notes")},
                    estimated_cost=CostEstimate("0.30", source="deterministic-fixture"),
                    executor=active["dependent_summary"],
                    declaration=WorkDeclaration("dependent_summary", ExternalExposure.SHAREABLE),
                ),
                Step(
                    "revision_output",
                    f"{prefix}-revision-v1",
                    {"brief": workflow_input("brief"), "revision": workflow_input("revision")},
                    estimated_cost=CostEstimate("0.40", source="deterministic-fixture"),
                    executor=active["revision_output"],
                    declaration=WorkDeclaration("revision_output", ExternalExposure.SHAREABLE),
                ),
            ),
        )

    def policies(
        self,
        scope: Scope,
        recipient_scope: Scope | None = None,
        *,
        provider_rule: ProviderRule = ProviderRule.SAME_PROVIDER,
        provider_allowlist: tuple[str, ...] | None = None,
    ) -> PolicySet:
        recipient_scope = recipient_scope or scope
        policies = []
        for category in ("shared_context", "private_notes", "dependent_summary", "revision_output"):
            policies.append(
                InheritancePolicy(
                    policy_id=f"{self.scenario_id}-{category}-policy",
                    project_scope=scope,
                    recipient_scope=recipient_scope,
                    work_category=category,
                    provider_rule=provider_rule,
                    provider_allowlist=provider_allowlist,
                    external_exposure_rule=(
                        ExternalExposureRule.SHAREABLE_ONLY
                        if category == "private_notes"
                        else ExternalExposureRule.INTERNAL_ALLOWED
                    ),
                )
            )
        return PolicySet(policies)


def scenario_fixtures(scenario_id: str) -> dict[str, DeterministicFixtureExecutor]:
    canary = f"PRIVATE-CANARY-{scenario_id}-do-not-cross"
    return {
        "shared_context": DeterministicFixtureExecutor(
            f"deterministic-fixture:{scenario_id}:shared-context:v1",
            lambda data: {"fixture": True, "kind": "shared_context", "brief": data.get("brief")},
        ),
        "private_notes": DeterministicFixtureExecutor(
            f"deterministic-fixture:{scenario_id}:private-notes:v1",
            lambda data: {"fixture": True, "kind": "private_notes", "note": f"{canary}: {data.get('brief')}"},
        ),
        "dependent_summary": DeterministicFixtureExecutor(
            f"deterministic-fixture:{scenario_id}:dependent-summary:v1",
            lambda data: {"fixture": True, "kind": "dependent_summary", "source": data.get("notes")},
        ),
        "revision_output": DeterministicFixtureExecutor(
            f"deterministic-fixture:{scenario_id}:revision-output:v1",
            lambda data: {"fixture": True, "kind": "revision_output", "brief": data.get("brief"), "revision": data.get("revision")},
        ),
    }


SCENARIOS: dict[str, ScenarioDefinition] = {
    "software": ScenarioDefinition(
        "software",
        "AI software-work handoff",
        "Developer-native",
        "Agent A completed a software task. Agent B inherits the safe implementation context while a changed constraint sends only the necessary work back through Delta.",
        "software-handoff",
        {
            "shared_context": "Implementation context",
            "private_notes": "Agent A private notes",
            "dependent_summary": "Updated test summary",
            "revision_output": "Constraint-bound output",
        },
        {"brief": "Add a safe handoff boundary to the checkout service", "revision": "initial"},
    ),
    "repair": ScenarioDefinition(
        "repair",
        "Home repair handoff",
        "General audience",
        "Agent A organized a home repair case. Agent B receives verified work, while a private note remains behind the handoff boundary.",
        "home-repair-handoff",
        {
            "shared_context": "Photo inventory",
            "private_notes": "Private homeowner note",
            "dependent_summary": "Insurer summary",
            "revision_output": "Updated repair scope",
        },
        {"brief": "Document storm damage to a kitchen roof", "revision": "initial"},
    ),
    "research": ScenarioDefinition(
        "research",
        "Paid research handoff",
        "ACP and Base evidence",
        "Agent A completed a research brief with an external evidence slot. Agent B can reuse verified work without purchasing the same evidence again.",
        "paid-research-handoff",
        {
            "shared_context": "Verified research evidence",
            "private_notes": "Agent A private notes",
            "dependent_summary": "Evidence synthesis",
            "revision_output": "Audience-specific brief",
        },
        {"brief": "Compare battery recycling options for a procurement brief", "revision": "initial"},
    ),
}


def scenario_definition(scenario_id: str) -> ScenarioDefinition:
    try:
        return SCENARIOS[scenario_id]
    except KeyError as error:
        raise ValueError("Unknown demo scenario.") from error
