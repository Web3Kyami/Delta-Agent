from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import unittest

from delta.core import (
    CostEstimate,
    DecisionKind,
    FreshnessPolicy,
    InputSpec,
    RevisionRequest,
    Scope,
    Step,
    Workflow,
    output_signature,
    step_output,
    workflow_input,
)
from delta.execute import DeltaEngine
from delta.fixtures import DeterministicFixtureExecutor, launch_package_fixtures
from delta.store import SibylStore

try:
    import sibyl_memory_client  # noqa: F401
except ImportError:
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True


NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)


def launch_workflow(
    fixtures: dict[str, DeterministicFixtureExecutor],
    *,
    announcement_implementation: str = "announcement-fixture-v1",
    visual_freshness: FreshnessPolicy | None = None,
    costs: bool = False,
) -> Workflow:
    estimate = lambda amount: CostEstimate(amount, source="deterministic-fixture") if costs else None
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
                freshness=visual_freshness or FreshnessPolicy(),
                estimated_cost=estimate("0.25"),
                executor=fixtures["visual"],
            ),
            Step(
                "announcement",
                announcement_implementation,
                {"description": workflow_input("description"), "launch_date": workflow_input("launch_date")},
                estimated_cost=estimate("0.50"),
                executor=fixtures["announcement"],
            ),
            Step(
                "translation",
                "translation-fixture-v1",
                {"announcement": step_output("announcement"), "target_language": workflow_input("target_language")},
                estimated_cost=None if not costs else None,
                executor=fixtures["translation"],
            ),
        ),
    )


def request(scope: Scope, workflow: Workflow, *, launch_date: str = "2026-09-10", brief: str = "Clean studio product shot", description: str = "A compact solar charger", language: str = "de") -> RevisionRequest:
    return RevisionRequest(
        scope,
        workflow,
        {
            "description": description,
            "brief": brief,
            "launch_date": launch_date,
            "target_language": language,
        },
        requested_at=NOW,
    )


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for Phase 3 verification")
class PhaseThreeExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="delta-phase3-")
        self.scope = Scope("22222222-2222-2222-2222-222222222222", "project-a")
        self.store = SibylStore.local(Path(self.tempdir.name) / "memory.db", self.scope)
        self.fixtures = launch_package_fixtures()
        self.workflow = launch_workflow(self.fixtures)
        self.engine = DeltaEngine(self.store)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def seed(self, workflow: Workflow | None = None, **kwargs: str) -> None:
        active_workflow = workflow or self.workflow
        self.engine.execute(request(self.scope, active_workflow, **kwargs), now=NOW)

    def decisions(self, report):
        return {decision.step_id: decision for decision in report.decisions}

    def test_unchanged_request_reuses_everything_without_fixture_calls(self) -> None:
        self.seed()
        counts = {name: fixture.call_count for name, fixture in self.fixtures.items()}
        report = self.engine.execute(request(self.scope, self.workflow), now=NOW + timedelta(minutes=1))
        self.assertEqual([decision.decision for decision in report.decisions], [DecisionKind.REUSE] * 3)
        self.assertEqual(counts, {name: fixture.call_count for name, fixture in self.fixtures.items()})
        self.assertEqual(report.costs.estimated_additional_service_cost.amount, "0")

    def test_launch_date_change_reruns_announcement_and_translation(self) -> None:
        self.seed()
        report = self.engine.execute(request(self.scope, self.workflow, launch_date="2026-09-11"), now=NOW)
        decisions = self.decisions(report)
        self.assertEqual(decisions["visual"].decision, DecisionKind.REUSE)
        self.assertEqual(decisions["announcement"].decision, DecisionKind.RERUN)
        self.assertEqual(decisions["translation"].decision, DecisionKind.RERUN)
        self.assertEqual(self.fixtures["visual"].call_count, 1)
        self.assertEqual(self.fixtures["announcement"].call_count, 2)
        self.assertEqual(self.fixtures["translation"].call_count, 2)

    def test_preview_marks_translation_pending_before_upstream_output_exists(self) -> None:
        preview = self.engine.preview(request(self.scope, self.workflow), now=NOW)
        decisions = self.decisions_from_plan(preview)
        self.assertEqual(decisions["visual"], DecisionKind.RERUN)
        self.assertEqual(decisions["announcement"], DecisionKind.RERUN)
        self.assertEqual(decisions["translation"], DecisionKind.PENDING_DEPENDENCY)
        self.assertEqual(sum(fixture.call_count for fixture in self.fixtures.values()), 0)

    def decisions_from_plan(self, plan):
        return {decision.step_id: decision.decision for decision in plan.decisions}

    def test_visual_brief_change_reruns_visual_only(self) -> None:
        self.seed()
        report = self.engine.execute(request(self.scope, self.workflow, brief="Outdoor product scene"), now=NOW)
        decisions = self.decisions(report)
        self.assertEqual(decisions["visual"].decision, DecisionKind.RERUN)
        self.assertEqual(decisions["announcement"].decision, DecisionKind.REUSE)
        self.assertEqual(decisions["translation"].decision, DecisionKind.REUSE)

    def test_description_change_reruns_shared_upstream_steps_and_downstream(self) -> None:
        self.seed()
        report = self.engine.execute(request(self.scope, self.workflow, description="A foldable solar charger"), now=NOW)
        self.assertEqual([decision.decision for decision in report.decisions], [DecisionKind.RERUN] * 3)

    def test_expired_independent_result_reruns_while_other_step_reuses(self) -> None:
        self.workflow = launch_workflow(self.fixtures, visual_freshness=FreshnessPolicy(3600))
        self.seed()
        report = self.engine.execute(request(self.scope, self.workflow), now=NOW + timedelta(hours=2))
        decisions = self.decisions(report)
        self.assertEqual(decisions["visual"].decision, DecisionKind.RERUN)
        self.assertEqual(decisions["announcement"].decision, DecisionKind.REUSE)
        self.assertEqual(decisions["translation"].decision, DecisionKind.REUSE)

    def test_implementation_change_reruns_target_and_reevaluates_actual_output(self) -> None:
        self.seed()
        changed_workflow = launch_workflow(self.fixtures, announcement_implementation="announcement-fixture-v2")
        report = self.engine.execute(request(self.scope, changed_workflow), now=NOW)
        decisions = self.decisions(report)
        self.assertEqual(decisions["announcement"].decision, DecisionKind.RERUN)
        self.assertEqual(decisions["translation"].decision, DecisionKind.REUSE)

    def test_upstream_rerun_with_unchanged_output_reuses_downstream(self) -> None:
        self.seed()
        changed_workflow = launch_workflow(self.fixtures, announcement_implementation="announcement-fixture-v2")
        report = self.engine.execute(request(self.scope, changed_workflow), now=NOW)
        self.assertEqual(self.fixtures["announcement"].call_count, 2)
        self.assertEqual(self.fixtures["translation"].call_count, 1)
        self.assertEqual(self.decisions(report)["translation"].decision, DecisionKind.REUSE)

    def test_failed_step_is_persisted_and_retry_can_succeed(self) -> None:
        self.seed()
        self.fixtures["announcement"].fail_with("planned test failure")
        failed = self.engine.execute(request(self.scope, self.workflow, launch_date="2026-09-11"), now=NOW)
        failed_decisions = self.decisions(failed)
        self.assertEqual(failed_decisions["announcement"].reason_code, "EXECUTION_FAILED")
        self.assertEqual(failed_decisions["translation"].decision, DecisionKind.BLOCKED)
        failed_attempt = next(attempt for attempt in failed.attempts if attempt.step_id == "announcement")
        self.assertEqual(failed_attempt.status, "failed")
        self.assertIsNone(self.store.get_work_result("launch-package", "announcement", failed_decisions["announcement"].input_signature))
        self.fixtures["announcement"].clear_failure()
        retried = self.engine.execute(request(self.scope, self.workflow, launch_date="2026-09-11"), now=NOW)
        self.assertEqual(self.decisions(retried)["announcement"].reason_code, "EXECUTED_SUCCESSFULLY")
        self.assertEqual(self.decisions(retried)["translation"].decision, DecisionKind.RERUN)

    def test_project_isolation_requires_execution_in_second_project(self) -> None:
        self.seed()
        project_b = Scope(self.scope.tenant_id, "project-b")
        engine_b = DeltaEngine(SibylStore.local(Path(self.tempdir.name) / "memory.db", project_b))
        report = engine_b.execute(request(project_b, self.workflow), now=NOW)
        self.assertEqual(sum(decision.decision == DecisionKind.RERUN for decision in report.decisions), 3)
        self.assertEqual(self.fixtures["visual"].call_count, 2)

    def test_costs_reasons_and_unknown_estimates_are_honest(self) -> None:
        costed = launch_workflow(self.fixtures, costs=True)
        first = self.engine.execute(request(self.scope, costed), now=NOW)
        self.assertEqual(first.costs.estimate_status, "unknown")
        self.assertIsNone(first.costs.estimated_additional_service_cost)
        unchanged = self.engine.execute(request(self.scope, costed), now=NOW)
        self.assertEqual(unchanged.costs.estimate_status, "known")
        self.assertEqual(unchanged.costs.estimated_additional_service_cost.amount, "0")
        changed_visual = self.engine.execute(request(self.scope, costed, brief="Outdoor product scene"), now=NOW)
        self.assertEqual(changed_visual.costs.estimate_status, "known")
        self.assertEqual(changed_visual.costs.estimated_additional_service_cost.amount, "0.25")
        self.assertIsNone(changed_visual.costs.actual_service_cost)
        self.assertIsNone(changed_visual.costs.network_gas_cost)
        self.assertTrue(all(decision.reason_code for decision in changed_visual.decisions))

    def test_single_writer_prevents_duplicate_fixture_calls(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def slow_output(data):
            started.set()
            release.wait(timeout=5)
            return {"fixture": True, "value": data["value"]}

        slow = DeterministicFixtureExecutor("deterministic-fixture:slow:v1", slow_output)
        workflow = Workflow("single-step", "1", {"value": InputSpec("string")}, (Step("only", "slow-v1", {"value": workflow_input("value")}, executor=slow),))
        single_request = RevisionRequest(self.scope, workflow, {"value": "same"}, requested_at=NOW)
        reports = []

        def run():
            reports.append(self.engine.execute(single_request, now=NOW))

        first = threading.Thread(target=run)
        second = threading.Thread(target=run)
        first.start()
        self.assertTrue(started.wait(timeout=5))
        second.start()
        second.join(timeout=5)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].decisions[0].decision, DecisionKind.BLOCKED)
        release.set()
        first.join(timeout=5)
        self.assertEqual(len(reports), 2)
        self.assertEqual(slow.call_count, 1)
        self.assertEqual(reports[1].decisions[0].decision, DecisionKind.RERUN)
        self.assertEqual(reports[1].attempts[0].status, "succeeded")


if __name__ == "__main__":
    unittest.main()
