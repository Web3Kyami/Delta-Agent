from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from delta.core import (
    ApprovalValidationError,
    CostEstimate,
    DecisionKind,
    DependencyPending,
    InputSpec,
    InputValidationError,
    ProviderQuote,
    RevisionRequest,
    Scope,
    SpendApproval,
    Step,
    Workflow,
    WorkflowValidationError,
    WorkResult,
    build_revision_plan,
    canonical_json,
    extract_dependencies,
    input_signature,
    output_signature,
    resolve_step_input,
    step_output,
    topological_order,
    validate_inputs,
    validate_spend_approval,
    validate_workflow,
    workflow_input,
)
from delta.fixtures import FixtureExecutionError, launch_package_fixtures


def launch_workflow() -> Workflow:
    return Workflow(
        id="launch-package",
        version="1",
        inputs={
            "description": InputSpec("string"),
            "brief": InputSpec("string"),
            "launch_date": InputSpec("date"),
            "target_language": InputSpec("string"),
        },
        steps=(
            Step(
                "visual",
                "visual-fixture-v1",
                {"description": workflow_input("description"), "brief": workflow_input("brief")},
                estimated_cost=CostEstimate("0", source="fixture"),
            ),
            Step(
                "announcement",
                "announcement-fixture-v1",
                {
                    "description": workflow_input("description"),
                    "launch_date": workflow_input("launch_date"),
                },
                estimated_cost=CostEstimate("0", source="fixture"),
            ),
            Step(
                "translation",
                "translation-fixture-v1",
                {
                    "announcement": step_output("announcement"),
                    "target_language": workflow_input("target_language"),
                },
            ),
        ),
    )


class PhaseOneCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = Scope("tenant-a", "project-a")
        self.workflow = launch_workflow()
        self.inputs = {
            "description": "A compact solar charger",
            "brief": "Clean studio product shot",
            "launch_date": "2026-09-10",
            "target_language": "de",
        }

    def test_canonical_signatures_are_stable_and_input_key_order_is_ignored(self) -> None:
        first = canonical_json({"b": 2, "a": [1, {"z": True}]})
        second = canonical_json({"a": [1, {"z": True}], "b": 2})
        self.assertEqual(first, second)
        self.assertEqual(output_signature({"b": 2, "a": 1}), output_signature({"a": 1, "b": 2}))

    def test_implementation_and_project_changes_change_input_signature(self) -> None:
        step = self.workflow.steps[0]
        effective = {"description": self.inputs["description"], "brief": self.inputs["brief"]}
        baseline = input_signature(self.scope, self.workflow, step, effective)
        changed_implementation = input_signature(
            self.scope,
            self.workflow,
            Step(step.id, "visual-fixture-v2", step.bind),
            effective,
        )
        changed_project = input_signature(
            Scope("tenant-a", "project-b"), self.workflow, step, effective
        )
        self.assertNotEqual(baseline, changed_implementation)
        self.assertNotEqual(baseline, changed_project)

    def test_invalid_json_like_values_are_rejected(self) -> None:
        for value in ({1, 2}, float("nan"), float("inf"), object(), {1: "not a string key"}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    canonical_json(value)
        self.assertEqual(canonical_json(datetime(2026, 9, 2, tzinfo=timezone.utc)), '"2026-09-02T00:00:00+00:00"')

    def test_workflow_validation_extracts_explicit_dependencies_and_orders_steps(self) -> None:
        validate_workflow(self.workflow)
        self.assertEqual(extract_dependencies(self.workflow.steps[2]), ("announcement",))
        self.assertEqual(topological_order(self.workflow), ("visual", "announcement", "translation"))
        resolved = resolve_step_input(
            self.workflow.steps[2],
            validate_inputs(self.workflow, self.inputs),
            {"announcement": {"copy": "ready"}},
        )
        self.assertEqual(resolved["announcement"], {"copy": "ready"})

    def test_cycle_is_rejected(self) -> None:
        cyclic = Workflow(
            "cycle",
            "1",
            {},
            (Step("a", "a-v1", {"value": step_output("b")}), Step("b", "b-v1", {"value": step_output("a")})),
        )
        with self.assertRaises(WorkflowValidationError):
            validate_workflow(cyclic)

    def test_public_planner_accepts_valid_input_and_rejects_changed_or_invalid_input(self) -> None:
        plan = build_revision_plan(RevisionRequest(self.scope, self.workflow, self.inputs))
        self.assertEqual([decision.decision for decision in plan.decisions], [DecisionKind.RERUN, DecisionKind.RERUN, DecisionKind.PENDING_DEPENDENCY])
        changed = dict(self.inputs, launch_date="2026-09-11")
        changed_plan = build_revision_plan(RevisionRequest(self.scope, self.workflow, changed))
        self.assertNotEqual(plan.plan_id, changed_plan.plan_id)
        with self.assertRaises(InputValidationError):
            build_revision_plan(RevisionRequest(self.scope, self.workflow, dict(self.inputs, target_language=12)))

    def test_fresh_result_is_reused_only_for_the_same_scope_and_input(self) -> None:
        now = datetime(2026, 9, 2, tzinfo=timezone.utc)
        step = self.workflow.steps[0]
        effective = {"description": self.inputs["description"], "brief": self.inputs["brief"]}
        signature = input_signature(self.scope, self.workflow, step, effective)
        result = WorkResult(
            self.scope,
            self.workflow.id,
            step.id,
            step.implementation_id,
            signature,
            output_signature({"fixture": True}),
            {"fixture": True},
            now,
            fresh_until=now + timedelta(hours=1),
        )
        plan = build_revision_plan(RevisionRequest(self.scope, self.workflow, self.inputs), [result], now)
        self.assertEqual(plan.decisions[0].decision, DecisionKind.REUSE)
        other_scope_plan = build_revision_plan(
            RevisionRequest(Scope("tenant-a", "project-b"), self.workflow, self.inputs), [result], now
        )
        self.assertEqual(other_scope_plan.decisions[0].decision, DecisionKind.RERUN)

        expired = WorkResult(
            self.scope,
            self.workflow.id,
            step.id,
            step.implementation_id,
            signature,
            output_signature({"fixture": True}),
            {"fixture": True},
            now - timedelta(hours=2),
            fresh_until=now - timedelta(hours=1),
        )
        expired_plan = build_revision_plan(RevisionRequest(self.scope, self.workflow, self.inputs), [expired], now)
        self.assertEqual(expired_plan.decisions[0].decision, DecisionKind.RERUN)

    def test_provider_quote_and_result_signatures_are_bound_to_real_values(self) -> None:
        quote = ProviderQuote(
            "provider",
            "offering",
            8453,
            CostEstimate("0.25", source="read-only-provider-response"),
            {"description": {"type": "string"}},
            "image/png",
            True,
            sla_seconds=120,
        )
        self.assertEqual(quote.chain_id, 8453)
        with self.assertRaises(ValueError):
            WorkResult(
                self.scope,
                self.workflow.id,
                "visual",
                "visual-fixture-v1",
                "input:known",
                "output:predetermined",
                {"actual": "value"},
                datetime(2026, 9, 2, tzinfo=timezone.utc),
            )

    def test_incomplete_and_out_of_scope_spend_approval_values_are_rejected(self) -> None:
        now = datetime(2026, 9, 2, tzinfo=timezone.utc)
        plan = build_revision_plan(RevisionRequest(self.scope, self.workflow, self.inputs), now=now)
        with self.assertRaises(ApprovalValidationError):
            SpendApproval(
                "approval",
                plan.plan_id,
                self.scope,
                ("visual",),
                "",
                "offering",
                0,
                ("create_job",),
                "USDC",
                "1",
                None,
                now + timedelta(hours=1),
            )
        approval = SpendApproval(
            "approval",
            plan.plan_id,
            self.scope,
            ("visual",),
            "provider",
            "offering",
            8453,
            ("create_job",),
            "USDC",
            "1.00",
            "0.50",
            now + timedelta(hours=1),
        )
        with self.assertRaises(ApprovalValidationError):
            validate_spend_approval(approval, plan, step_id="visual", provider_id="provider", offering_id="offering", chain_id=8453, action="create_job", amount="1.01", currency="USDC", now=now)
        with self.assertRaises(ApprovalValidationError):
            validate_spend_approval(approval, plan, step_id="announcement", provider_id="provider", offering_id="offering", chain_id=8453, action="create_job", amount="0.10", currency="USDC", now=now)

    def test_fixture_services_are_labelled_input_sensitive_and_failure_observable(self) -> None:
        fixtures = launch_package_fixtures()
        visual = fixtures["visual"]
        self.assertTrue(visual.is_fixture)
        first = visual.execute({"description": "one", "brief": "brief"})
        second = visual.execute({"description": "two", "brief": "brief"})
        self.assertEqual(visual.call_count, 2)
        self.assertNotEqual(first, second)
        visual.fail_with("configured fixture failure")
        with self.assertRaises(FixtureExecutionError):
            visual.execute({"description": "three", "brief": "brief"})
        self.assertEqual(visual.call_count, 3)


if __name__ == "__main__":
    unittest.main()
