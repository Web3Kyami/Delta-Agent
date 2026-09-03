from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from delta.artifacts import ArtifactResolution, ArtifactResolutionStatus
from delta.core import ArtifactReference, ExecutionAttempt, InputSpec, RevisionRequest, Scope, SpendApproval, Step, Workflow, build_revision_plan
from delta.providers.acp import (
    ACPAdapter,
    ACPAdapterError,
    ACPCommandResult,
    ACPCommandRunner,
    ACPCommandStatus,
    ACPDeliverableVerification,
    ACPObservationSource,
    ACPParseError,
    ACPSettlementEvidence,
    ACPSpendLedger,
    ChainEvidence,
    FundingOutcome,
    ReconciliationOutcome,
    UnsupportedLifecycle,
    canonical_requirements,
    match_reconciliation_candidates,
    parse_browse_response,
    parse_chain_evidence,
    parse_create_job_response,
    parse_job_record,
    reconcile_funding,
    redact_text,
)
from delta.store import SibylStore


try:
    import sibyl_memory_client  # noqa: F401
except ImportError:
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True


FIXTURES = Path(__file__).parent / "fixtures" / "acp" / "lifecycle"
NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)


class FixtureRunner:
    """Test-only transport that returns labelled sanitized ACP fixtures."""

    def __init__(self, responses, on_call=None):
        self.responses = list(responses)
        self.calls = []
        self.on_call = on_call

    def run_json(self, args, **kwargs):
        self.calls.append((tuple(args), kwargs))
        if self.on_call is not None:
            self.on_call(tuple(args), kwargs)
        return self.responses.pop(0)


def fixture_response(name: str) -> ACPCommandResult:
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    return ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture", name), data=data)


def phase4_context():
    scope = Scope("33333333-3333-3333-3333-333333333333", "phase4-project")
    workflow = Workflow("phase4-workflow", "1", {}, (Step("visual", "visual-v1"),))
    plan = build_revision_plan(RevisionRequest(scope, workflow, {}), now=NOW)
    approval = SpendApproval(
        "approval-phase4",
        plan.plan_id,
        scope,
        ("visual",),
        "fixture-provider",
        "fixture-offering",
        8453,
        ("create_job", "fund", "complete", "reject"),
        "USDC",
        "1.00",
        "1.00",
        NOW + timedelta(hours=1),
    )
    return scope, workflow, plan, approval


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for Phase 4 verification")
class PhaseFourACPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="delta-phase4-")
        self.scope, self.workflow, self.plan, self.approval = phase4_context()
        self.store = SibylStore.local(Path(self.tempdir.name) / "memory.db", self.scope)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_runner_uses_argument_arrays_json_output_and_redacts_secrets(self) -> None:
        secret = "do-not-store-this"
        script = 'import json; print(json.dumps({"privateKey": "do-not-store-this", "ok": True}))'
        result = ACPCommandRunner(secrets=(secret,)).run_json([sys.executable, "-c", script])
        self.assertEqual(result.status, ACPCommandStatus.SUCCEEDED)
        self.assertEqual(result.data["privateKey"], "[REDACTED]")
        self.assertTrue(result.data["ok"])
        self.assertIn("--json", result.args)
        self.assertIn("[REDACTED]", result.stdout)
        self.assertNotIn(secret, result.stdout)
        self.assertNotIn(secret, result.args[2])

    def test_runner_can_replace_acp_executable_with_pinned_argument_prefix(self) -> None:
        script = "import json, sys; print(json.dumps({'argv': sys.argv[1:]}))"
        runner = ACPCommandRunner(command_prefix=(sys.executable, "-c", script))
        result = runner.run_json(["acp", "browse", "image generation"])
        self.assertEqual(result.status, ACPCommandStatus.SUCCEEDED)
        self.assertEqual(result.data["argv"], ["browse", "image generation", "--json"])
        self.assertEqual(result.args[:3], (sys.executable, "-c", script))

    def test_runner_distinguishes_nonzero_parse_failure_and_side_effect_timeout(self) -> None:
        failed = ACPCommandRunner().run_json([sys.executable, "-c", "raise SystemExit(3)"])
        self.assertEqual(failed.status, ACPCommandStatus.FAILED)
        invalid = ACPCommandRunner().run_json([sys.executable, "-c", "print('not json')"])
        self.assertEqual(invalid.status, ACPCommandStatus.PARSE_FAILED)
        timed_out = ACPCommandRunner().run_json(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            timeout_seconds=0.05,
            side_effecting=True,
        )
        self.assertEqual(timed_out.status, ACPCommandStatus.TIMEOUT)
        self.assertTrue(timed_out.external_outcome_ambiguous)

    def test_history_and_watch_can_include_the_required_chain_id(self) -> None:
        runner = FixtureRunner([fixture_response("submitted"), fixture_response("submitted")])
        adapter = ACPAdapter(self.store, runner)
        adapter.job_history("fixture-job-42", chain_id=8453)
        adapter.watch_job("fixture-job-42", chain_id=8453)
        self.assertEqual(
            runner.calls[0][0],
            ("acp", "job", "history", "--job-id", "fixture-job-42", "--chain-id", "8453"),
        )
        self.assertEqual(
            runner.calls[1][0],
            ("acp", "job", "watch", "--job-id", "fixture-job-42", "--chain-id", "8453"),
        )

    def test_requirement_correction_uses_the_provider_envelope(self) -> None:
        runner = FixtureRunner([ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data={"success": True})])
        adapter = ACPAdapter(self.store, runner)
        adapter.send_requirement(
            "fixture-job-42",
            chain_id=8453,
            offering_name="content_generation",
            requirements={"topic": "fixture", "content_type": "blog_post"},
        )
        args = runner.calls[0][0]
        self.assertEqual(
            args[:9],
            ("acp", "message", "send", "--job-id", "fixture-job-42", "--chain-id", "8453", "--content-type", "requirement"),
        )
        self.assertEqual(
            json.loads(args[10]),
            {"name": "content_generation", "requirement": {"content_type": "blog_post", "topic": "fixture"}},
        )
        self.assertTrue(runner.calls[0][1]["side_effecting"])

    def test_lifecycle_fixtures_map_through_adapter_and_completed_is_not_settlement_evidence(self) -> None:
        expected = {
            "open": "awaiting_provider",
            "budget_set": "awaiting_approval",
            "funded": "awaiting_provider",
            "submitted": "deliverable_ready",
            "completed": "reconciliation_required",
            "rejected": "rejected",
            "expired": "expired",
        }
        for name, state in expected.items():
            with self.subTest(name=name):
                record = parse_job_record(json.loads((FIXTURES / f"{name}.json").read_text()))
                self.assertTrue(record.fixture)
                self.assertEqual(record.delta_state, state)
        completed = parse_job_record(json.loads((FIXTURES / "completed.json").read_text()))
        self.assertTrue(completed.fixture)
        self.assertEqual(completed.transaction_hashes, ())
        with self.assertRaises(UnsupportedLifecycle):
            parse_job_record({"fixture": True, "jobId": "x", "chainId": 8453, "status": "unknown"})

    def test_malformed_job_and_requirements_are_rejected(self) -> None:
        with self.assertRaises(ACPParseError):
            parse_job_record({"fixture": True, "jobId": "x", "chainId": 8453})
        with self.assertRaises(ACPParseError):
            parse_job_record({"fixture": True, "jobId": "x", "chainId": 8453, "status": "completed", "transactionHashes": "not a list"})
        with self.assertRaises(ACPParseError):
            parse_job_record({"fixture": True, "jobId": "x", "chainId": 8453, "status": "completed", "providerId": {"unexpected": "object"}})
        self.assertEqual(canonical_requirements({"b": 2, "a": 1}), '{"a":1,"b":2}')
        with self.assertRaises(ACPParseError):
            canonical_requirements({"bad": {1, 2}})

    def test_browse_and_history_are_read_only_json_operations(self) -> None:
        runner = FixtureRunner([
            ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data=[]),
            ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data=[]),
        ])
        adapter = ACPAdapter(self.store, runner)
        adapter.browse("product visual", chain_id=8453)
        adapter.job_history("fixture-job-42")
        browse_args = runner.calls[0][0]
        history_args = runner.calls[1][0]
        self.assertEqual(browse_args[:3], ("acp", "browse", "product visual"))
        self.assertIn("--chain-ids", browse_args)
        self.assertEqual(history_args, ("acp", "job", "history", "--job-id", "fixture-job-42"))

    def test_live_browse_shape_fixture_is_normalized_without_claiming_online_status(self) -> None:
        payload = json.loads((Path(__file__).parent / "fixtures" / "acp" / "marketplace" / "image_generation.json").read_text())
        self.assertTrue(payload["fixture"])
        records = parse_browse_response(payload)
        self.assertEqual(len(records), 1)
        provider = records[0]
        self.assertEqual(provider.provider_id, "fixture-provider-image")
        self.assertEqual(provider.provider_address, "0x1111111111111111111111111111111111111111")
        self.assertEqual(provider.chain_ids, (8453,))
        self.assertEqual(provider.offerings[0].name, "ai_image_generation")
        self.assertEqual(provider.offerings[0].price_value, Decimal("0.05"))
        self.assertEqual(provider.offerings[0].requirements["required"], ["prompt"])
        self.assertEqual(provider.offerings[1].requirements, "Required source image HTTPS URL and user instruction")

    def test_browse_defaults_to_unfiltered_read_only_discovery(self) -> None:
        runner = FixtureRunner([ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data={"data": []})])
        adapter = ACPAdapter(self.store, runner)
        response = adapter.browse("translation")
        self.assertEqual(response.status, ACPCommandStatus.SUCCEEDED)
        self.assertNotIn("--chain-ids", runner.calls[0][0])
        self.assertEqual(adapter.parse_browse_response(response), ())

    def test_malformed_browse_shape_is_rejected(self) -> None:
        with self.assertRaises(ACPParseError):
            parse_browse_response({"data": [{"id": "provider", "name": "Provider", "chains": [{"chainId": "8453"}], "offerings": []}]})
        with self.assertRaises(ACPParseError):
            parse_browse_response({"data": [{"id": "provider", "name": "Provider", "chains": [], "offerings": [{"id": "offering", "name": "image", "priceValue": "not-a-price"}]}]})

    def test_recorded_live_create_and_history_shapes_are_normalized(self) -> None:
        create_payload = json.loads((FIXTURES / "recorded_create_receipt.json").read_text())
        created = parse_create_job_response(create_payload, chain_id=8453)
        self.assertTrue(created.fixture)
        self.assertEqual(created.job_id, "recorded-job-75656")
        self.assertEqual(created.provider_id, "0xb0aca700745a989a1cb859eecfe0fd9afbc066aa")
        self.assertIsNone(created.offering_id)
        self.assertEqual(created.offering_name, "content_generation")
        self.assertEqual(created.provider_status, "open")

        history_payload = json.loads((FIXTURES / "recorded_history_submitted.json").read_text())
        history = parse_job_record(history_payload)
        self.assertEqual(history.provider_status, "submitted")
        self.assertEqual(history.delta_state, "deliverable_ready")
        self.assertEqual(history.provider_id, created.provider_id)
        self.assertIsNone(history.offering_id)
        self.assertEqual(history.offering_name, "content_generation")
        self.assertIsNotNone(history.requirements_signature)
        self.assertEqual(history.deliverable_hash, "0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8")
        self.assertIn('"word_count":159', history.deliverable)
        self.assertEqual(history.transaction_hashes, ())
        with self.assertRaises(ACPParseError):
            parse_create_job_response({"success": False, "jobId": "recorded-job-75656"}, chain_id=8453)

    def test_compact_create_receipt_persists_job_identity(self) -> None:
        compact = json.loads((FIXTURES / "recorded_create_receipt.json").read_text())
        compact.update({"provider": "fixture-provider", "offering": "Fixture Visual"})
        runner = FixtureRunner([ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data=compact)])
        adapter = ACPAdapter(self.store, runner)
        result = adapter.create_job(
            self.plan,
            self.approval,
            step_id="visual",
            input_signature="input:compact-create",
            provider_id="fixture-provider",
            offering_id="fixture-offering",
            offering_name="Fixture Visual",
            requirements={"description": "fixture product"},
            chain_id=8453,
            amount="0.25",
            attempt_id="attempt-compact-create",
            now=NOW,
        )
        self.assertEqual(result.status, ACPCommandStatus.SUCCEEDED)
        attempt = self.store.get_attempt("attempt-compact-create")
        self.assertEqual(attempt.status, "active")
        self.assertEqual(attempt.provider_job_id, "recorded-job-75656")
        self.assertEqual(attempt.provider_chain_id, 8453)
        self.assertIsNotNone(attempt.requirements_signature)

    def test_watch_and_known_job_reconciliation_use_provider_response(self) -> None:
        runner = FixtureRunner([
            fixture_response("submitted"),
            fixture_response("submitted"),
            fixture_response("submitted"),
        ])
        adapter = ACPAdapter(self.store, runner)
        record = adapter.reconcile_known_job("fixture-job-42")
        self.assertEqual(record.provider_status, "submitted")
        self.assertEqual(adapter.get_deliverable("fixture-job-42")["type"], "text")
        watched = adapter.watch_job("fixture-job-42")
        self.assertEqual(watched.status, ACPCommandStatus.SUCCEEDED)
        self.assertEqual(runner.calls[-1][0], ("acp", "job", "watch", "--job-id", "fixture-job-42"))

    def test_create_persists_intent_before_fixture_response_and_never_claims_settlement(self) -> None:
        observed = []

        def on_call(args, _kwargs):
            observed.append(self.store.get_active_attempt("visual"))

        runner = FixtureRunner([fixture_response("completed")], on_call=on_call)
        adapter = ACPAdapter(self.store, runner)
        response = adapter.create_job(
            self.plan,
            self.approval,
            step_id="visual",
            input_signature="input:phase4",
            provider_id="fixture-provider",
            offering_id="fixture-offering",
            offering_name="Fixture Visual",
            requirements={"description": "fixture product"},
            chain_id=8453,
            amount="0.25",
            attempt_id="attempt-create",
            now=NOW,
        )
        self.assertEqual(response.status, ACPCommandStatus.SUCCEEDED)
        self.assertEqual(observed, ["attempt-create"])
        record = adapter.parse_response(response)
        self.assertTrue(record.fixture)
        attempt = self.store.get_attempt("attempt-create")
        self.assertEqual(attempt.status, "active")
        self.assertEqual(attempt.provider_job_id, "fixture-job-42")
        self.assertEqual(attempt.provider_id, "fixture-provider")
        self.assertEqual(attempt.offering_id, "fixture-offering")
        self.assertEqual(attempt.offering_name, "Fixture Visual")
        self.assertNotEqual(attempt.status, "succeeded")

    def test_ambiguous_create_is_persisted_and_not_retried_implicitly(self) -> None:
        runner = FixtureRunner([
            ACPCommandResult(
                ACPCommandStatus.PARSE_FAILED,
                ("fixture",),
                error="fixture parse failure",
                external_outcome_ambiguous=True,
            )
        ])
        adapter = ACPAdapter(self.store, runner)
        response = adapter.create_job(
            self.plan,
            self.approval,
            step_id="visual",
            input_signature="input:ambiguous",
            provider_id="fixture-provider",
            offering_id="fixture-offering",
            offering_name="Fixture Visual",
            requirements={"description": "fixture product"},
            chain_id=8453,
            amount="0.25",
            attempt_id="attempt-ambiguous",
            now=NOW,
        )
        self.assertEqual(response.status, ACPCommandStatus.PARSE_FAILED)
        self.assertTrue(response.external_outcome_ambiguous)
        self.assertEqual(self.store.get_attempt("attempt-ambiguous").status, "ambiguous")
        self.assertEqual(len(runner.calls), 1)

    def test_create_identity_mismatch_is_ambiguous(self) -> None:
        response = fixture_response("open")
        mismatched = dict(response.data)
        mismatched["chainId"] = 84532
        runner = FixtureRunner([ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data=mismatched)])
        adapter = ACPAdapter(self.store, runner)
        result = adapter.create_job(
            self.plan, self.approval, step_id="visual", input_signature="input:mismatch",
            provider_id="fixture-provider", offering_id="fixture-offering", offering_name="Fixture Visual",
            requirements={"description": "fixture product"}, chain_id=8453, amount="0.25",
            attempt_id="attempt-mismatch", now=NOW,
        )
        self.assertEqual(result.status, ACPCommandStatus.AMBIGUOUS)
        self.assertTrue(result.external_outcome_ambiguous)
        self.assertEqual(self.store.get_attempt("attempt-mismatch").status, "ambiguous")

    def test_reconcile_attempt_recovers_persisted_job_in_a_fresh_process(self) -> None:
        runner = FixtureRunner([fixture_response("funded")])
        adapter = ACPAdapter(self.store, runner)
        adapter.create_job(
            self.plan, self.approval, step_id="visual", input_signature="input:restart",
            provider_id="fixture-provider", offering_id="fixture-offering", offering_name="Fixture Visual",
            requirements={"description": "fixture product"}, chain_id=8453, amount="0.25",
            attempt_id="attempt-restart", now=NOW,
        )
        child = """
import json
import sys
from pathlib import Path
from delta.core import Scope
from delta.providers.acp import ACPAdapter, ACPCommandResult, ACPCommandStatus, ACPObservationSource
from delta.store import SibylStore

class Runner:
    def run_json(self, args, **kwargs):
        return ACPCommandResult(
            ACPCommandStatus.SUCCEEDED,
            tuple(args),
            data=json.loads(Path(sys.argv[4]).read_text()),
        )

scope = Scope(sys.argv[2], sys.argv[3])
store = SibylStore.local(Path(sys.argv[1]), scope)
record = ACPAdapter(store, Runner()).reconcile_attempt("visual", source=ACPObservationSource.RECORDED_FIXTURE)
attempt = store.get_attempt("attempt-restart")
print(json.dumps({"job_id": record.job_id, "status": attempt.status, "fixture": record.fixture}))
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                child,
                str(Path(self.tempdir.name) / "memory.db"),
                self.scope.tenant_id,
                self.scope.project_id,
                str(FIXTURES / "funded.json"),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        recovered = json.loads(result.stdout)
        self.assertEqual(recovered, {"job_id": "fixture-job-42", "status": "active", "fixture": True})

    def test_reconcile_attempt_blocks_provider_identity_conflict(self) -> None:
        attempt = ExecutionAttempt(
            "attempt-provider-conflict",
            self.scope,
            self.plan.workflow_id,
            "visual",
            "ambiguous",
            "input:provider-conflict",
            provider_job_id="fixture-job-42",
            provider_chain_id=8453,
            provider_id="fixture-provider",
            offering_id="fixture-offering",
            offering_name="Fixture Visual",
        )
        self.store.save_attempt(attempt)
        self.store.set_active_attempt("visual", attempt.attempt_id)
        response = fixture_response("open")
        response.data["providerId"] = "different-provider"
        adapter = ACPAdapter(self.store, FixtureRunner([response]))
        with self.assertRaises(ACPAdapterError):
            adapter.reconcile_attempt("visual", source=ACPObservationSource.RECORDED_FIXTURE)
        self.assertEqual(self.store.get_attempt(attempt.attempt_id).status, "blocked")
        self.assertEqual(self.store.get_attempt(attempt.attempt_id).provider_id, "fixture-provider")

    def test_concurrent_create_for_same_input_is_called_once(self) -> None:
        first_started = threading.Event()
        release = threading.Event()

        def on_call(_args, _kwargs):
            if len(runner.calls) == 1:
                first_started.set()
                release.wait(timeout=5)

        runner = FixtureRunner([fixture_response("open")], on_call=on_call)
        adapter = ACPAdapter(self.store, runner)
        errors = []

        def create(attempt_id):
            try:
                adapter.create_job(
                    self.plan, self.approval, step_id="visual", input_signature="input:concurrent",
                    provider_id="fixture-provider", offering_id="fixture-offering", offering_name="Fixture Visual",
                    requirements={"description": "fixture product"}, chain_id=8453, amount="0.25",
                    attempt_id=attempt_id, now=NOW,
                )
            except Exception as error:
                errors.append(error)

        first = threading.Thread(target=create, args=("attempt-concurrent-1",))
        second = threading.Thread(target=create, args=("attempt-concurrent-2",))
        first.start()
        self.assertTrue(first_started.wait(timeout=5))
        second.start()
        second.join(timeout=5)
        release.set()
        first.join(timeout=5)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ACPAdapterError)

    def test_fund_and_complete_commands_require_approval_and_use_exact_shapes(self) -> None:
        runner = FixtureRunner([
            ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data={"ok": True}),
            ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data={"ok": True}),
        ])
        adapter = ACPAdapter(self.store, runner)
        fund = adapter.fund_job(
            self.plan, self.approval, step_id="visual", input_signature="input:fund",
            provider_id="fixture-provider", offering_id="fixture-offering", chain_id=8453,
            job_id="fixture-job-42", amount="0.25", attempt_id="attempt-fund", now=NOW,
        )
        complete = adapter.complete_job(
            self.plan, self.approval, step_id="visual", input_signature="input:fund",
            provider_id="fixture-provider", offering_id="fixture-offering", chain_id=8453,
            job_id="fixture-job-42", amount="0.25", reason="Fixture review",
            attempt_id="attempt-complete", now=NOW,
        )
        self.assertEqual(fund.status, ACPCommandStatus.SUCCEEDED)
        self.assertEqual(complete.status, ACPCommandStatus.SUCCEEDED)
        self.assertEqual(runner.calls[0][0][-6:], ("--job-id", "fixture-job-42", "--amount", "0.25", "--chain-id", "8453"))
        self.assertEqual(runner.calls[1][0][-6:], ("--job-id", "fixture-job-42", "--chain-id", "8453", "--reason", "Fixture review"))

        with self.assertRaises(Exception):
            adapter.fund_job(
                self.plan, self.approval, step_id="visual", input_signature="input:cap",
                provider_id="fixture-provider", offering_id="fixture-offering", chain_id=8453,
                job_id="fixture-job-42", amount="1.01", attempt_id="attempt-cap", now=NOW,
            )
        self.assertEqual(len(runner.calls), 2)

    def test_ambiguous_paid_actions_block_a_second_attempt(self) -> None:
        timeout = ACPCommandResult(
            ACPCommandStatus.TIMEOUT,
            ("fixture",),
            error="fixture timeout",
            external_outcome_ambiguous=True,
        )
        runner = FixtureRunner([timeout, timeout, timeout])
        adapter = ACPAdapter(self.store, runner)
        for action in ("fund", "complete", "reject"):
            with self.subTest(action=action):
                if action == "fund":
                    call = lambda attempt_id: adapter.fund_job(
                        self.plan, self.approval, step_id="visual", input_signature=f"input:{action}",
                        provider_id="fixture-provider", offering_id="fixture-offering", chain_id=8453,
                        job_id="fixture-job-42", amount="0.25", attempt_id=attempt_id, now=NOW,
                    )
                elif action == "complete":
                    call = lambda attempt_id: adapter.complete_job(
                        self.plan, self.approval, step_id="visual", input_signature=f"input:{action}",
                        provider_id="fixture-provider", offering_id="fixture-offering", chain_id=8453,
                        job_id="fixture-job-42", amount="0.25", reason="Fixture completion", attempt_id=attempt_id, now=NOW,
                    )
                else:
                    call = lambda attempt_id: adapter.reject_job(
                        self.plan, self.approval, step_id="visual", input_signature=f"input:{action}",
                        provider_id="fixture-provider", offering_id="fixture-offering", chain_id=8453,
                        job_id="fixture-job-42", reason="Fixture rejection", attempt_id=attempt_id, now=NOW,
                    )
                call(f"attempt-{action}-one")
                with self.assertRaises(ACPAdapterError):
                    call(f"attempt-{action}-two")
        self.assertEqual(len(runner.calls), 3)

    def test_reconciliation_matching_never_picks_the_first_candidate(self) -> None:
        base = {
            "jobId": "job-1",
            "providerId": "provider-a",
            "offeringId": "offering-a",
            "chainId": 8453,
            "status": "funded",
            "requirementsSignature": "req-1",
            "transactionHashes": ["tx-1"],
        }
        candidate = parse_job_record(base)
        attached = match_reconciliation_candidates(
            [candidate], provider_id="provider-a", offering_id="offering-a", chain_id=8453,
            requirements_signature="req-1", expected_transaction_hashes=("tx-1",),
        )
        self.assertEqual(attached.outcome, ReconciliationOutcome.ATTACH)
        self.assertEqual(attached.record.job_id, "job-1")
        self.assertEqual(match_reconciliation_candidates([], provider_id="provider-a", offering_id="offering-a", chain_id=8453).outcome, ReconciliationOutcome.MANUAL)
        duplicate = parse_job_record({**base, "jobId": "job-2"})
        self.assertEqual(match_reconciliation_candidates([candidate, duplicate], provider_id="provider-a", offering_id="offering-a", chain_id=8453).outcome, ReconciliationOutcome.MANUAL)
        provider_mismatch = parse_job_record({**base, "providerId": "provider-b"})
        self.assertEqual(match_reconciliation_candidates([provider_mismatch], provider_id="provider-a", offering_id="offering-a", chain_id=8453).outcome, ReconciliationOutcome.BLOCKED)
        offering_mismatch = parse_job_record({**base, "offeringId": "offering-b"})
        self.assertEqual(match_reconciliation_candidates([offering_mismatch], provider_id="provider-a", offering_id="offering-a", chain_id=8453).outcome, ReconciliationOutcome.BLOCKED)
        transaction_mismatch = parse_job_record({**base, "transactionHashes": ["tx-2"]})
        self.assertEqual(match_reconciliation_candidates([transaction_mismatch], provider_id="provider-a", offering_id="offering-a", chain_id=8453, expected_transaction_hashes=("tx-1",)).outcome, ReconciliationOutcome.BLOCKED)

    def test_reconciliation_can_use_known_job_and_offering_name_when_id_is_missing(self) -> None:
        candidate = parse_job_record({
            "jobId": "known-job",
            "providerId": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "chainId": 8453,
            "status": "submitted",
            "offeringName": "content_generation",
        })
        decision = match_reconciliation_candidates(
            [candidate],
            provider_id="0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            offering_id="known-offering-id",
            offering_name="content_generation",
            chain_id=8453,
            expected_job_id="known-job",
        )
        self.assertEqual(decision.outcome, ReconciliationOutcome.ATTACH)
        self.assertEqual(decision.record.job_id, "known-job")

    def test_record_observation_persists_fixture_provenance_without_work_success(self) -> None:
        attempt = ExecutionAttempt(
            "attempt-observation",
            self.scope,
            self.plan.workflow_id,
            "visual",
            "active",
            "input:observation",
            provider_job_id="recorded-job-75656",
            provider_chain_id=8453,
            provider_id="0xb0aca700745a989a1cb859eecfe0fd9afbc066aa",
            offering_id="recorded-offering",
            offering_name="content_generation",
        )
        self.store.save_attempt(attempt)
        self.store.set_active_attempt("visual", attempt.attempt_id)
        payload = json.loads((FIXTURES / "recorded_history_submitted.json").read_text())
        adapter = ACPAdapter(self.store, FixtureRunner([]))
        record = adapter.parse_response(ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("recorded_fixture",), data=payload))
        adapter.record_observation(attempt.attempt_id, record, source=ACPObservationSource.RECORDED_FIXTURE, now=NOW)
        stored = self.store.get_attempt(attempt.attempt_id)
        self.assertEqual(stored.status, "active")
        self.assertEqual(stored.provider_job_id, "recorded-job-75656")
        self.assertIsNone(self.store.get_work_result(self.plan.workflow_id, "visual", "input:observation"))
        event = self.store.read_events(attempt_id=attempt.attempt_id, limit=10)[-1]
        self.assertIn("recorded_fixture observation", event["detail"])

    def test_live_observation_rejects_fixture_marked_response(self) -> None:
        attempt = ExecutionAttempt(
            "attempt-live-fixture",
            self.scope,
            self.plan.workflow_id,
            "visual",
            "active",
            "input:live-fixture",
            provider_job_id="recorded-job-75656",
            provider_chain_id=8453,
            provider_id="0xb0aca700745a989a1cb859eecfe0fd9afbc066aa",
            offering_name="content_generation",
        )
        self.store.save_attempt(attempt)
        self.store.set_active_attempt("visual", attempt.attempt_id)
        payload = json.loads((FIXTURES / "recorded_history_submitted.json").read_text())
        record = parse_job_record(payload)
        with self.assertRaises(ACPAdapterError):
            ACPAdapter(self.store, FixtureRunner([])).record_observation(attempt.attempt_id, record)
        self.assertEqual(self.store.get_attempt(attempt.attempt_id).status, "blocked")

    def test_recorded_fixture_cannot_cross_the_reusable_work_boundary(self) -> None:
        attempt = ExecutionAttempt(
            "attempt-fixture-finalize",
            self.scope,
            self.plan.workflow_id,
            "visual",
            "reconciliation_required",
            "input:fixture-finalize",
            provider_job_id="fixture-job-42",
            provider_chain_id=8453,
            provider_id="fixture-provider",
            offering_id="fixture-offering",
            offering_name="Fixture Visual",
            requirements_signature="requirements:fixture",
        )
        self.store.save_attempt(attempt)
        self.store.set_active_attempt("visual", attempt.attempt_id)
        record = parse_job_record(
            {
                "fixture": True,
                "jobId": "fixture-job-42",
                "providerId": "fixture-provider",
                "offeringId": "fixture-offering",
                "offeringName": "Fixture Visual",
                "chainId": 8453,
                "status": "completed",
                "requirementsSignature": "requirements:fixture",
                "deliverable": {"text": "Fixture output"},
                "deliverableHash": "provider-hash-fixture",
            }
        )
        resolution = ArtifactResolution(
            ArtifactResolutionStatus.AVAILABLE,
            ArtifactReference("artifact-fixture", "sha256:fixture", "text/plain", 13, "file:///tmp/artifact-fixture.bin"),
            "labelled fixture artifact",
        )
        adapter = ACPAdapter(self.store, FixtureRunner([]))
        with self.assertRaises(ACPAdapterError):
            adapter.finalize_completed_work(
                self.plan,
                step_id="visual",
                implementation_id="visual-v1",
                input_signature="input:fixture-finalize",
                attempt_id=attempt.attempt_id,
                record=record,
                artifact_resolution=resolution,
                deliverable_verification=ACPDeliverableVerification(
                    "provider-keccak256", "provider-hash-fixture", "provider-hash-fixture", True
                ),
                settlement=ACPSettlementEvidence(8453, "0xfixture-settlement", "succeeded"),
                now=NOW,
            )
        self.assertIsNone(self.store.get_work_result(self.plan.workflow_id, "visual", "input:fixture-finalize"))
        self.assertEqual(self.store.get_attempt(attempt.attempt_id).status, "reconciliation_required")

    def test_finalization_rejects_an_unavailable_artifact(self) -> None:
        attempt = ExecutionAttempt(
            "attempt-artifact-unavailable",
            self.scope,
            self.plan.workflow_id,
            "visual",
            "reconciliation_required",
            "input:artifact-unavailable",
            provider_job_id="provider-job-1",
            provider_chain_id=8453,
            provider_id="provider-a",
            offering_id="offering-a",
            offering_name="Fixture Visual",
            requirements_signature="requirements:provider",
        )
        self.store.save_attempt(attempt)
        self.store.set_active_attempt("visual", attempt.attempt_id)
        record = parse_job_record(
            {
                "jobId": "provider-job-1",
                "providerId": "provider-a",
                "offeringName": "Fixture Visual",
                "chainId": 8453,
                "status": "completed",
                "requirementsSignature": "requirements:provider",
                "deliverable": {"text": "Provider output"},
                "deliverableHash": "provider-hash",
            }
        )
        adapter = ACPAdapter(self.store, FixtureRunner([]))
        with self.assertRaises(ACPAdapterError):
            adapter.finalize_completed_work(
                self.plan,
                step_id="visual",
                implementation_id="visual-v1",
                input_signature="input:artifact-unavailable",
                attempt_id=attempt.attempt_id,
                record=record,
                artifact_resolution=ArtifactResolution(
                    ArtifactResolutionStatus.UNAVAILABLE,
                    None,
                    "provider artifact is unavailable",
                ),
                deliverable_verification=ACPDeliverableVerification(
                    "provider-keccak256", "provider-hash", "provider-hash", True
                ),
                settlement=ACPSettlementEvidence(8453, "0xprovider-settlement", "succeeded"),
                now=NOW,
            )
        self.assertIsNone(self.store.get_work_result(self.plan.workflow_id, "visual", "input:artifact-unavailable"))

    def test_funding_requires_agreement_between_provider_and_chain_evidence(self) -> None:
        funded = parse_job_record({"fixture": True, "jobId": "job-funded", "providerId": "provider-a", "offeringId": "offering-a", "chainId": 8453, "status": "funded"})
        not_funded = parse_job_record({"fixture": True, "jobId": "job-open", "providerId": "provider-a", "offeringId": "offering-a", "chainId": 8453, "status": "open"})
        self.assertEqual(reconcile_funding(funded, ChainEvidence("succeeded", "tx-1")).outcome, FundingOutcome.VERIFIED_FUNDED)
        self.assertEqual(reconcile_funding(funded, ChainEvidence("failed", "tx-1")).outcome, FundingOutcome.BLOCKED)
        self.assertEqual(reconcile_funding(funded, None).outcome, FundingOutcome.AMBIGUOUS)
        self.assertEqual(reconcile_funding(not_funded, ChainEvidence("failed", "tx-1")).outcome, FundingOutcome.NOT_FUNDED)
        self.assertEqual(reconcile_funding(not_funded, ChainEvidence("succeeded", "tx-1")).outcome, FundingOutcome.BLOCKED)
        self.assertEqual(reconcile_funding(not_funded, None).outcome, FundingOutcome.NOT_FUNDED)
        self.assertEqual(parse_chain_evidence({"status": "succeeded", "transactionHash": "tx-2"}), ChainEvidence("succeeded", "tx-2"))
        with self.assertRaises(ACPParseError):
            parse_chain_evidence({"status": "succeeded"})

    def test_cumulative_spend_is_persisted_and_cannot_exceed_the_plan_cap(self) -> None:
        ledger = ACPSpendLedger(self.store)
        ledger.reserve(
            self.approval, self.plan, step_id="visual", provider_id="fixture-provider",
            offering_id="fixture-offering", chain_id=8453, action="fund", amount="0.60",
            currency="USDC", reservation_id="reserve-1", now=NOW,
        )
        with self.assertRaises(Exception):
            ledger.reserve(
                self.approval, self.plan, step_id="visual", provider_id="fixture-provider",
                offering_id="fixture-offering", chain_id=8453, action="fund", amount="0.50",
                currency="USDC", reservation_id="reserve-2", now=NOW,
            )
        self.assertEqual(ledger.committed(self.plan), "0.60")

    def test_direct_scope_and_currency_mismatches_block_paid_actions(self) -> None:
        runner = FixtureRunner([ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data={"ok": True})])
        adapter = ACPAdapter(self.store, runner)
        with self.assertRaises(Exception):
            adapter.reject_job(
                self.plan, self.approval, step_id="visual", input_signature="input:reject",
                provider_id="other-provider", offering_id="fixture-offering", chain_id=8453,
                job_id="fixture-job-42", reason="Fixture rejection", attempt_id="attempt-reject", now=NOW,
            )
        self.assertEqual(len(runner.calls), 0)

    def test_redaction_handles_fixture_credentials_without_exposing_them(self) -> None:
        text = '{"private_key":"secret-value","access_token":"token-value","visible":"ok"}'
        redacted = redact_text(text, ("secret-value", "token-value"))
        self.assertNotIn("secret-value", redacted)
        self.assertNotIn("token-value", redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn('"visible":"ok"', redacted)


if __name__ == "__main__":
    unittest.main()
