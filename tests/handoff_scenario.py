"""Shared deterministic handoff scenario for in-process and fresh-process tests.

Both the parent test process and the child processes launched by the exit-gate
test import this module, so Agent A and Agent B provably evaluate identical
workflow, policy, and input definitions.

Nothing here calls an LLM, a provider, or a network. Executors are the labelled
deterministic fixtures already used by the existing suite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from delta.core import (
    AgentPrincipal,
    CostEstimate,
    ExternalExposure,
    FreshnessPolicy,
    InputSpec,
    Scope,
    Step,
    WorkDeclaration,
    Workflow,
    step_output,
    workflow_input,
)
from delta.fixtures import DeterministicFixtureExecutor
from delta.handoff import (
    ExternalExposureRule,
    InheritancePolicy,
    PolicySet,
    ProviderRule,
)

TENANT = "22222222-2222-2222-2222-222222222222"
PROJECT = "software-handoff-a"
OTHER_PROJECT = "software-handoff-b"

#: A distinctive string that only ever appears inside internal-only work output.
#: Any test that finds it in an approved context, prompt payload, handoff
#: record, or receipt has found a real content leak.
PRIVATE_CANARY = "PRIVATE-NOTE-CANARY-7f3a2b91"

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)

AGENT_A = AgentPrincipal("agent-a-implementer", "session-a-1", "provider-alpha")
AGENT_B = AgentPrincipal("agent-b-successor", "session-b-1", "provider-alpha")
AGENT_B_OTHER_PROVIDER = AgentPrincipal("agent-b-successor", "session-b-1", "provider-beta")
AGENT_UNLISTED = AgentPrincipal("agent-z-outsider", "session-z-1", "provider-alpha")

INVENTORY_CATEGORY = "component_inventory"
PRIVATE_NOTE_CATEGORY = "private_note"
SUMMARY_CATEGORY = "external_summary"
SCOPE_CATEGORY = "repair_scope"


def scope(project_id: str = PROJECT) -> Scope:
    return Scope(TENANT, project_id)


def fixtures() -> dict[str, DeterministicFixtureExecutor]:
    """Deterministic executors whose outputs vary with their actual inputs."""

    return {
        "inventory": DeterministicFixtureExecutor(
            "deterministic-fixture:inventory:v1",
            lambda data: {
                "fixture": True,
                "kind": "component_inventory",
                "components": ["auth", "billing"],
                "description": data.get("description"),
            },
        ),
        "private_note": DeterministicFixtureExecutor(
            "deterministic-fixture:private-note:v1",
            lambda data: {
                "fixture": True,
                "kind": "private_note",
                "note": f"{PRIVATE_CANARY} internal reviewer note for {data.get('description')}",
            },
        ),
        "insurer_summary": DeterministicFixtureExecutor(
            "deterministic-fixture:insurer-summary:v1",
            lambda data: {
                "fixture": True,
                "kind": "external_summary",
                "derived_from": data.get("note"),
            },
        ),
        "repair_scope": DeterministicFixtureExecutor(
            "deterministic-fixture:repair-scope:v1",
            lambda data: {
                "fixture": True,
                "kind": "repair_scope",
                "revision": data.get("revision"),
            },
        ),
    }


def handoff_workflow(
    executors: Mapping[str, DeterministicFixtureExecutor] | None = None,
    *,
    inventory_implementation: str = "inventory-fixture-v1",
    inventory_freshness: FreshnessPolicy | None = None,
) -> Workflow:
    """The shared four-step workflow.

    ``inventory`` is declared shareable and is the item expected to cross the
    handoff. ``private_note`` is declared internal only. ``insurer_summary``
    depends on the private note, so it must wait when the note is withheld.
    ``repair_scope`` binds a revision input so a later revision changes its
    effective input.
    """

    executors = executors or {}
    return Workflow(
        id="software-handoff",
        version="1",
        inputs={
            "description": InputSpec("string"),
            "revision": InputSpec("string"),
        },
        steps=(
            Step(
                "inventory",
                inventory_implementation,
                {"description": workflow_input("description")},
                freshness=inventory_freshness or FreshnessPolicy(),
                estimated_cost=CostEstimate("0.10", source="deterministic-fixture"),
                executor=executors.get("inventory"),
                declaration=WorkDeclaration(INVENTORY_CATEGORY, ExternalExposure.SHAREABLE),
            ),
            Step(
                "private_note",
                "note-fixture-v1",
                {"description": workflow_input("description")},
                estimated_cost=CostEstimate("0.20", source="deterministic-fixture"),
                executor=executors.get("private_note"),
                declaration=WorkDeclaration(PRIVATE_NOTE_CATEGORY, ExternalExposure.INTERNAL_ONLY),
            ),
            Step(
                "insurer_summary",
                "summary-fixture-v1",
                {"note": step_output("private_note")},
                estimated_cost=CostEstimate("0.30", source="deterministic-fixture"),
                executor=executors.get("insurer_summary"),
                declaration=WorkDeclaration(SUMMARY_CATEGORY, ExternalExposure.SHAREABLE),
            ),
            Step(
                "repair_scope",
                "scope-fixture-v1",
                {
                    "description": workflow_input("description"),
                    "revision": workflow_input("revision"),
                },
                estimated_cost=CostEstimate("0.40", source="deterministic-fixture"),
                executor=executors.get("repair_scope"),
                declaration=WorkDeclaration(SCOPE_CATEGORY, ExternalExposure.SHAREABLE),
            ),
        ),
    )


def inputs(revision: str = "r1") -> dict[str, Any]:
    return {"description": "checkout service handoff", "revision": revision}


def policies(
    *,
    recipient_project: str = PROJECT,
    owning_project: str = PROJECT,
    provider_rule: ProviderRule = ProviderRule.SAME_PROVIDER,
    provider_allowlist: tuple[str, ...] | None = None,
    agent_allowlist: tuple[str, ...] | None = None,
    include_scope_policy: bool = True,
) -> PolicySet:
    """The developer-declared policy set for the shared scenario.

    ``private_note`` is governed by a shareable-only rule, so its internal-only
    work is withheld even though the result itself is valid.
    """

    owning = scope(owning_project)
    recipient = scope(recipient_project)
    declared = [
        InheritancePolicy(
            policy_id="policy-inventory",
            project_scope=owning,
            recipient_scope=recipient,
            work_category=INVENTORY_CATEGORY,
            provider_rule=provider_rule,
            provider_allowlist=provider_allowlist,
            agent_allowlist=agent_allowlist,
            external_exposure_rule=ExternalExposureRule.INTERNAL_ALLOWED,
        ),
        InheritancePolicy(
            policy_id="policy-private-note",
            project_scope=owning,
            recipient_scope=recipient,
            work_category=PRIVATE_NOTE_CATEGORY,
            provider_rule=provider_rule,
            provider_allowlist=provider_allowlist,
            agent_allowlist=agent_allowlist,
            external_exposure_rule=ExternalExposureRule.SHAREABLE_ONLY,
        ),
        InheritancePolicy(
            policy_id="policy-summary",
            project_scope=owning,
            recipient_scope=recipient,
            work_category=SUMMARY_CATEGORY,
            provider_rule=provider_rule,
            provider_allowlist=provider_allowlist,
            agent_allowlist=agent_allowlist,
            external_exposure_rule=ExternalExposureRule.INTERNAL_ALLOWED,
        ),
    ]
    if include_scope_policy:
        declared.append(
            InheritancePolicy(
                policy_id="policy-repair-scope",
                project_scope=owning,
                recipient_scope=recipient,
                work_category=SCOPE_CATEGORY,
                provider_rule=provider_rule,
                provider_allowlist=provider_allowlist,
                agent_allowlist=agent_allowlist,
                external_exposure_rule=ExternalExposureRule.INTERNAL_ALLOWED,
            )
        )
    return PolicySet(declared)
