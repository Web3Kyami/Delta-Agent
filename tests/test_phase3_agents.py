from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from delta.agents import (
    AgentHandoffService,
    AgentOutputError,
    AgentRequest,
    AgentResponse,
    AgentRunnerError,
    AgentRunnerUnavailable,
    AgentUsage,
    DeterministicAgentRunner,
    OpenAIResponsesRunner,
    build_agent_messages,
)
from delta.core import AgentPrincipal, RevisionRequest
from delta.execute import DeltaEngine
from delta.handoff import HandoffGate, HandoffRequest
from delta.store import SibylStore

from tests import handoff_scenario as scenario


try:
    import sibyl_memory_client  # noqa: F401
except ImportError:
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for Phase 3 agent tests")
class PhaseThreeAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="delta-phase3-agents-")
        self.db_path = Path(self.tempdir.name) / "memory.db"
        self.scope = scenario.scope()
        self.store = SibylStore.local(self.db_path, self.scope)
        self.executors = scenario.fixtures()
        self.workflow = scenario.handoff_workflow(self.executors)
        DeltaEngine(self.store, principal=scenario.AGENT_A).execute(
            RevisionRequest(self.scope, self.workflow, scenario.inputs()),
            now=NOW,
        )
        self.request = HandoffRequest(
            scope=self.scope,
            workflow=self.workflow,
            inputs=scenario.inputs(),
            recipient=scenario.AGENT_B,
            policies=scenario.policies(),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_service_persists_distinct_agent_sessions_and_receipt(self) -> None:
        runner = DeterministicAgentRunner()
        result = AgentHandoffService(self.store, runner).run(
            self.request,
            task="Prepare a safe implementation handoff.",
            trace_id="trace-phase3-1",
            now=NOW,
        )
        self.assertEqual(result.run.status, "succeeded")
        self.assertEqual(result.run.response.mode, "deterministic_fixture")
        sessions = self.store.list_agent_sessions()
        self.assertEqual({item["session_id"] for item in sessions}, {"session-a-1", "session-b-1"})
        self.assertEqual({item["role"] for item in sessions}, {"agent_a", "agent_b"})
        self.assertEqual(result.run.handoff_id, result.evaluation.receipt.handoff_id)
        persisted = self.store.get_agent_run(result.run.run_id)
        self.assertEqual(persisted["status"], "succeeded")
        self.assertEqual(persisted["response"]["session_id"], "session-b-1")
        receipt = self.store.get_reuse_receipt(result.evaluation.receipt.receipt_id)
        outcomes = {entry.step_id: entry.outcome for entry in receipt.entries}
        self.assertEqual(outcomes, {"inventory": "reused", "private_note": "blocked", "insurer_summary": "pending_dependency", "repair_scope": "reused"})

    def test_missing_declared_work_runs_through_engine_and_receipt_links_attempt(self) -> None:
        changed_request = HandoffRequest(
            scope=self.scope,
            workflow=self.workflow,
            inputs=scenario.inputs("r2"),
            recipient=scenario.AGENT_B,
            policies=scenario.policies(),
        )
        result = AgentHandoffService(self.store, DeterministicAgentRunner()).run(
            changed_request,
            task="Apply the changed revision to approved work.",
            trace_id="trace-phase3-missing",
            now=NOW,
        )
        execution = {decision.step_id: decision for decision in result.execution.decisions}
        self.assertEqual(execution["repair_scope"].reason_code, "EXECUTED_SUCCESSFULLY")
        receipt = self.store.get_reuse_receipt(result.evaluation.receipt.receipt_id)
        entry = next(item for item in receipt.entries if item.step_id == "repair_scope")
        self.assertEqual(entry.outcome, "executed")
        self.assertEqual(entry.attempt_id, next(attempt.attempt_id for attempt in result.execution.attempts if attempt.step_id == "repair_scope"))
        self.assertEqual(self.store.get_attempt(entry.attempt_id).status, "succeeded")

    def test_only_approved_context_reaches_fixture_and_contains_no_canary(self) -> None:
        runner = DeterministicAgentRunner()
        result = AgentHandoffService(self.store, runner).run(
            self.request,
            task="Summarize the approved implementation context.",
            trace_id="trace-phase3-2",
            now=NOW,
        )
        self.assertEqual(set(runner.requests[0].approved_context.approved_step_ids), {"inventory", "repair_scope"})
        surface = json.dumps(runner.requests[0].approved_context.prompt_payload(), sort_keys=True)
        self.assertNotIn(scenario.PRIVATE_CANARY, surface)
        response = result.run.response.output
        self.assertEqual(set(response["approved_steps"]), {"inventory", "repair_scope"})
        self.assertNotIn(scenario.PRIVATE_CANARY, json.dumps(response, sort_keys=True))

    def test_openai_runner_builds_inspectable_real_request_with_supported_usage(self) -> None:
        calls = []

        def post(endpoint, headers, body, timeout):
            calls.append((endpoint, headers, json.loads(body), timeout))
            return json.dumps({
                "id": "resp_phase3_1",
                "model": "gpt-test",
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "Approved implementation summary."}]}],
                "usage": {"input_tokens": 21, "output_tokens": 8, "total_tokens": 29},
            }).encode()

        evaluation = HandoffGate(self.store).evaluate(self.request, now=NOW)
        runner = OpenAIResponsesRunner(api_key="sk-test-only", model="gpt-test", http_post=post)
        response = runner.run(AgentRequest(scenario.AGENT_B, evaluation.approved_context, "Summarize approved work.", "trace-phase3-openai"))
        self.assertEqual(response.provider_id, "openai")
        self.assertEqual(response.mode, "real_provider")
        self.assertEqual(response.usage.total_tokens, 29)
        self.assertIsNone(response.cost)
        self.assertEqual(response.provider_response_id, "resp_phase3_1")
        self.assertEqual(calls[0][0], "https://api.openai.com/v1/responses")
        self.assertEqual(calls[0][1]["Authorization"], "Bearer sk-test-only")
        request_payload = calls[0][2]
        self.assertFalse(request_payload["store"])
        self.assertEqual(request_payload["metadata"]["delta_session_id"], scenario.AGENT_B.session_id)
        self.assertNotIn(scenario.PRIVATE_CANARY, json.dumps(request_payload, sort_keys=True))

    def test_distinct_sessions_are_bound_to_provider_requests(self) -> None:
        evaluation = HandoffGate(self.store).evaluate(self.request, now=NOW)
        runner = DeterministicAgentRunner()
        runner.run(AgentRequest(scenario.AGENT_B, evaluation.approved_context, "One", "trace-b"))
        other = AgentPrincipal("agent-b-successor", "session-b-2", "provider-alpha")
        other_request = HandoffRequest(self.scope, self.workflow, scenario.inputs(), other, scenario.policies())
        other_evaluation = HandoffGate(self.store).evaluate(other_request, now=NOW)
        runner.run(AgentRequest(other, other_evaluation.approved_context, "Two", "trace-b2"))
        self.assertEqual([request.principal.session_id for request in runner.requests], ["session-b-1", "session-b-2"])

    def test_failed_provider_response_is_recorded_failed_and_not_reusable(self) -> None:
        class FailingRunner:
            provider_id = "openai"

            def run(self, request):
                raise AgentOutputError("provider returned an empty output")

        result = AgentHandoffService(self.store, FailingRunner()).run(
            self.request,
            task="Produce a summary.",
            trace_id="trace-phase3-failed",
            now=NOW,
        )
        self.assertEqual(result.run.status, "failed")
        self.assertIsNone(result.run.response)
        persisted = self.store.get_agent_run(result.run.run_id)
        self.assertEqual(persisted["status"], "failed")
        self.assertIsNone(persisted["response"])
        self.assertEqual(self.store.list_work_results(self.workflow.id)[0].provenance.source_session_id, "session-a-1")

    def test_provider_output_session_mismatch_fails_closed(self) -> None:
        class WrongSessionRunner:
            provider_id = "openai"

            def run(self, request):
                return AgentResponse("openai", "gpt-test", "other-session", "unsafe", "real_provider")

        result = AgentHandoffService(self.store, WrongSessionRunner()).run(
            self.request,
            task="Produce a summary.",
            trace_id="trace-phase3-mismatch",
            now=NOW,
        )
        self.assertEqual(result.run.status, "failed")
        self.assertEqual(self.store.get_agent_run(result.run.run_id)["error_code"], "AgentOutputError")

    def test_real_runner_without_credentials_is_unavailable_and_fixture_is_explicit(self) -> None:
        with self.assertRaises(AgentRunnerUnavailable):
            OpenAIResponsesRunner(api_key=None).run(
                AgentRequest(
                    scenario.AGENT_B,
                    HandoffGate(self.store).evaluate(self.request, now=NOW).approved_context,
                    "No network call should happen.",
                    "trace-phase3-unavailable",
                )
            )
        self.assertEqual(DeterministicAgentRunner.mode, "deterministic_fixture")


if __name__ == "__main__":
    unittest.main()
