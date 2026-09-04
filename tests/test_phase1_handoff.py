"""Phase 1 handoff-gate tests against the real Sibyl-backed store.

Every test in this module persists through `SibylStore.local`, so the evidence
is integration evidence for the authoritative store, not mock behavior. The
fresh-process exit gate lives in `test_phase1_handoff_exit_gate.py`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from delta.core import (
    ArtifactReference,
    ExternalExposure,
    ExternalJobRef,
    ExternalJobSettlement,
    DecisionKind,
    FreshnessPolicy,
    RevisionRequest,
    Scope,
    WorkDeclaration,
    WorkProvenance,
    WorkResult,
    input_signature,
    output_signature,
    resolve_step_input,
    validate_inputs,
)
from delta.execute import DeltaEngine
from delta.handoff import (
    ApprovedContext,
    ApprovedWorkItem,
    AuthorizationStatus,
    BlockedWorkNotice,
    DependencyStatus,
    ExternalJobStatus,
    HandoffDecision,
    HandoffGate,
    HandoffPolicyError,
    HandoffRequest,
    HandoffVerdicts,
    InheritancePolicy,
    PolicySet,
    ProviderRule,
    TrustStatus,
    ValidityStatus,
    Verdict,
    WorkEvidence,
)
from delta.store import SibylPersistenceError, SibylStore, WORK_CATEGORY

from tests import handoff_scenario as scenario

try:
    import sibyl_memory_client  # noqa: F401
except ImportError:  # pragma: no cover - exercised only without the SDK
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True


def _canary_in(value) -> bool:
    return scenario.PRIVATE_CANARY in json.dumps(value, sort_keys=True, default=str)


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for handoff persistence tests")
class HandoffGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="delta-phase1-handoff-")
        self.addCleanup(self._directory.cleanup)
        self.db_path = Path(self._directory.name) / "memory.db"
        self.scope = scenario.scope()
        self.store = SibylStore.local(self.db_path, self.scope)
        self.executors = scenario.fixtures()

    # -- helpers ------------------------------------------------------------

    def run_agent_a(self, revision: str = "r1", *, now: datetime | None = None) -> None:
        """Agent A executes the declared workflow and Sibyl persists the work."""

        workflow = scenario.handoff_workflow(self.executors)
        engine = DeltaEngine(self.store, principal=scenario.AGENT_A)
        report = engine.execute(
            RevisionRequest(self.scope, workflow, scenario.inputs(revision)),
            now=now or scenario.NOW,
        )
        executed = {
            decision.step_id
            for decision in report.decisions
            if decision.reason_code == "EXECUTED_SUCCESSFULLY"
        }
        self.assertEqual(executed, {"inventory", "private_note", "insurer_summary", "repair_scope"})

    def evaluate(
        self,
        *,
        recipient=None,
        policies=None,
        workflow=None,
        revision: str = "r1",
        now: datetime | None = None,
        store: SibylStore | None = None,
    ):
        gate = HandoffGate(store or self.store)
        request = HandoffRequest(
            scope=(store or self.store).scope,
            workflow=workflow or scenario.handoff_workflow(),
            inputs=scenario.inputs(revision),
            recipient=recipient or scenario.AGENT_B,
            policies=policies or scenario.policies(),
        )
        return gate.evaluate(request, now=now or scenario.NOW + timedelta(minutes=5))

    def stored_result(self, step_id: str) -> WorkResult:
        for result in self.store.list_work_results("software-handoff"):
            if result.step_id == step_id:
                return result
        raise AssertionError(f"no persisted work result for {step_id}")

    def signature_for(self, step_id: str, revision: str = "r1") -> str:
        workflow = scenario.handoff_workflow()
        step = next(step for step in workflow.steps if step.id == step_id)
        normalized = validate_inputs(workflow, scenario.inputs(revision))
        effective = resolve_step_input(step, normalized, {})
        return input_signature(self.scope, workflow, step, effective)

    # -- core behavior ------------------------------------------------------

    def test_authorized_work_is_inherited_and_internal_only_work_is_withheld(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()

        self.assertEqual(evaluation.decision_for("inventory").decision, DecisionKind.REUSE)
        self.assertEqual(evaluation.decision_for("repair_scope").decision, DecisionKind.REUSE)

        blocked = evaluation.decision_for("private_note")
        self.assertEqual(blocked.decision, DecisionKind.BLOCKED)
        self.assertEqual(blocked.reason_code, "BLOCKED_EXTERNAL_EXPOSURE_BLOCKED")
        # Validity and authorization are independent: the record itself is fine.
        self.assertEqual(blocked.verdicts.validity.status, ValidityStatus.VALID)
        self.assertEqual(blocked.verdicts.trust.status, TrustStatus.TRUSTED)
        self.assertEqual(blocked.verdicts.authorization.status, AuthorizationStatus.UNAUTHORIZED)

        waiting = evaluation.decision_for("insurer_summary")
        self.assertEqual(waiting.decision, DecisionKind.PENDING_DEPENDENCY)
        self.assertEqual(waiting.verdicts.dependency.status, DependencyStatus.PENDING)

        context = evaluation.approved_context
        self.assertEqual(set(context.approved_step_ids), {"inventory", "repair_scope"})
        self.assertEqual(set(context.blocked_step_ids), {"private_note", "insurer_summary"})

    def test_blocked_content_is_absent_from_every_agent_b_surface(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()

        # Control: the canary really is persisted and reachable, so its absence
        # below is a real exclusion rather than a vacuous assertion.
        self.assertTrue(_canary_in(self.stored_result("private_note").output))

        context = evaluation.approved_context
        self.assertFalse(_canary_in(context.prompt_payload()))
        self.assertFalse(_canary_in(context.inherited_outputs()))
        self.assertFalse(_canary_in([item.prompt_payload() for item in context.items]))
        self.assertFalse(_canary_in([notice.payload() for notice in context.blocked]))
        self.assertFalse(
            _canary_in([decision.payload() for decision in evaluation.record.decisions])
        )
        self.assertFalse(_canary_in([entry.payload() for entry in evaluation.receipt.entries]))
        self.assertFalse(_canary_in(evaluation.receipt.summary))

        HandoffGate(self.store).persist(evaluation)
        reloaded_record = self.store.get_handoff_record(evaluation.handoff_id)
        reloaded_receipt = self.store.get_reuse_receipt(evaluation.receipt.receipt_id)
        self.assertFalse(_canary_in([d.payload() for d in reloaded_record.decisions]))
        self.assertFalse(_canary_in([e.payload() for e in reloaded_receipt.entries]))

        # The blocked step is present by identity and reason only.
        notice = next(item for item in context.blocked if item.step_id == "private_note")
        self.assertEqual(notice.reason_code, "BLOCKED_EXTERNAL_EXPOSURE_BLOCKED")
        self.assertEqual(set(notice.payload()), {"step_id", "decision", "reason_code"})

    def test_stale_authorized_work_reruns_and_stays_authorized(self) -> None:
        self.run_agent_a()
        stale = replace(self.stored_result("inventory"), fresh_until=scenario.NOW + timedelta(hours=1))
        self.store.save_work_result(stale)

        evaluation = self.evaluate(now=scenario.NOW + timedelta(days=1))
        decision = evaluation.decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.RERUN)
        self.assertEqual(decision.reason_code, "RERUN_RESULT_EXPIRED")
        self.assertEqual(decision.verdicts.validity.status, ValidityStatus.INVALID)
        self.assertEqual(decision.verdicts.authorization.status, AuthorizationStatus.AUTHORIZED)
        self.assertTrue(decision.found_candidate)
        self.assertNotIn("inventory", evaluation.approved_context.approved_step_ids)

    def test_changed_input_and_changed_implementation_rerun(self) -> None:
        self.run_agent_a()

        changed_input = self.evaluate(revision="r2")
        scope_decision = changed_input.decision_for("repair_scope")
        self.assertEqual(scope_decision.decision, DecisionKind.RERUN)
        self.assertEqual(scope_decision.reason_code, "RERUN_INPUT_SIGNATURE_MISMATCH")
        self.assertTrue(scope_decision.found_candidate)
        # An unrelated valid item is not invalidated by the changed sibling.
        self.assertEqual(changed_input.decision_for("inventory").decision, DecisionKind.REUSE)

        changed_impl = self.evaluate(
            workflow=scenario.handoff_workflow(inventory_implementation="inventory-fixture-v2")
        )
        impl_decision = changed_impl.decision_for("inventory")
        self.assertEqual(impl_decision.decision, DecisionKind.RERUN)
        self.assertEqual(impl_decision.reason_code, "RERUN_IMPLEMENTATION_MISMATCH")

    def test_unavailable_artifact_prevents_reuse(self) -> None:
        self.run_agent_a()
        result = self.stored_result("inventory")
        missing = ArtifactReference(
            "artifact-inventory", "sha256:absent", "application/json", 128, None, False
        )
        self.store.save_work_result(replace(result, artifact=missing))

        decision = self.evaluate().decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.RERUN)
        self.assertEqual(decision.reason_code, "RERUN_ARTIFACT_UNAVAILABLE")
        self.assertEqual(decision.verdicts.authorization.status, AuthorizationStatus.AUTHORIZED)
        self.assertIs(decision.evidence.artifact_available, False)

    def test_no_candidate_work_reruns_without_a_policy_block(self) -> None:
        decision = self.evaluate().decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.RERUN)
        self.assertEqual(decision.reason_code, "RERUN_NO_CANDIDATE_WORK")
        self.assertFalse(decision.found_candidate)
        self.assertEqual(decision.verdicts.validity.status, ValidityStatus.NO_CANDIDATE)
        self.assertEqual(decision.verdicts.trust.status, TrustStatus.NO_CANDIDATE)
        self.assertEqual(decision.verdicts.authorization.status, AuthorizationStatus.NO_CANDIDATE)

    # -- policy rules -------------------------------------------------------

    def test_same_provider_rule_blocks_a_different_runtime_provider(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate(recipient=scenario.AGENT_B_OTHER_PROVIDER)
        decision = evaluation.decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_PROVIDER_RULE_SAME_PROVIDER_VIOLATED")
        self.assertEqual(decision.verdicts.validity.status, ValidityStatus.VALID)
        self.assertEqual(evaluation.approved_context.approved_step_ids, ())

    def test_provider_allowlist_rule_admits_only_listed_providers(self) -> None:
        self.run_agent_a()
        allowed = self.evaluate(
            recipient=scenario.AGENT_B_OTHER_PROVIDER,
            policies=scenario.policies(
                provider_rule=ProviderRule.PROVIDER_ALLOWLIST,
                provider_allowlist=("provider-beta",),
            ),
        )
        self.assertEqual(allowed.decision_for("inventory").decision, DecisionKind.REUSE)

        refused = self.evaluate(
            recipient=scenario.AGENT_B_OTHER_PROVIDER,
            policies=scenario.policies(
                provider_rule=ProviderRule.PROVIDER_ALLOWLIST,
                provider_allowlist=("provider-gamma",),
            ),
        )
        decision = refused.decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_PROVIDER_NOT_ALLOWLISTED")

    def test_agent_allowlist_blocks_an_unlisted_recipient(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate(
            recipient=scenario.AGENT_UNLISTED,
            policies=scenario.policies(agent_allowlist=(scenario.AGENT_B.agent_id,)),
        )
        decision = evaluation.decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_RECIPIENT_AGENT_NOT_ALLOWED")

    def test_work_category_without_a_policy_is_not_inheritable(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate(policies=scenario.policies(include_scope_policy=False))
        decision = evaluation.decision_for("repair_scope")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_NO_POLICY_FOR_WORK_CATEGORY")
        self.assertEqual(decision.verdicts.validity.status, ValidityStatus.VALID)

    def test_project_boundaries_prevent_cross_project_reuse(self) -> None:
        self.run_agent_a()
        other_scope = scenario.scope(scenario.OTHER_PROJECT)
        other_store = SibylStore.local(self.db_path, other_scope)

        evaluation = self.evaluate(
            store=other_store,
            policies=scenario.policies(recipient_project=scenario.OTHER_PROJECT),
        )
        self.assertEqual(evaluation.approved_context.approved_step_ids, ())
        self.assertFalse(_canary_in(evaluation.approved_context.prompt_payload()))
        for decision in evaluation.decisions:
            self.assertNotEqual(decision.decision, DecisionKind.REUSE)
            self.assertFalse(decision.found_candidate)

    def test_policy_recipient_scope_must_match_the_receiving_project(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate(
            policies=scenario.policies(recipient_project=scenario.OTHER_PROJECT)
        )
        decision = evaluation.decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_RECIPIENT_PROJECT_MISMATCH")

    # -- legacy and provenance ---------------------------------------------

    def test_legacy_work_without_provenance_is_not_automatically_authorized(self) -> None:
        """A pre-migration record has no provenance, so it can never be inherited."""

        workflow = scenario.handoff_workflow()
        signature = self.signature_for("inventory")
        legacy_output = {"fixture": True, "kind": "component_inventory", "legacy": True}
        legacy = WorkResult(
            scope=self.scope,
            workflow_id=workflow.id,
            step_id="inventory",
            implementation_id="inventory-fixture-v1",
            input_signature=signature,
            output_signature=output_signature(legacy_output),
            output=legacy_output,
            completed_at=scenario.NOW,
        )
        self.store.save_work_result(legacy)
        self.assertIsNone(self.stored_result("inventory").provenance)

        decision = self.evaluate().decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_PROVENANCE_MISSING")
        self.assertEqual(decision.verdicts.trust.status, TrustStatus.UNTRUSTED)
        self.assertEqual(decision.verdicts.authorization.status, AuthorizationStatus.UNEVALUATED)
        self.assertEqual(self.evaluate().approved_context.approved_step_ids, ())

    def test_persisted_record_missing_the_provenance_field_stays_untrusted(self) -> None:
        """A record written before the provenance field existed decodes as untrusted."""

        self.run_agent_a()
        entities = self.store.client.list_entities(WORK_CATEGORY, limit=1000)
        target = next(
            entity for entity in entities if entity["body"]["step_id"] == "inventory"
        )
        body = dict(target["body"])
        body.pop("provenance", None)
        self.store.client.set_entity(WORK_CATEGORY, target["name"], body, status="completed")

        decision = self.evaluate().decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_PROVENANCE_MISSING")

    def test_engine_without_a_principal_produces_unprovenanced_work(self) -> None:
        workflow = scenario.handoff_workflow(self.executors)
        DeltaEngine(self.store).execute(
            RevisionRequest(self.scope, workflow, scenario.inputs()),
            now=scenario.NOW,
        )
        self.assertIsNone(self.stored_result("inventory").provenance)
        decision = self.evaluate().decision_for("inventory")
        self.assertEqual(decision.reason_code, "BLOCKED_PROVENANCE_MISSING")

    def test_provenance_round_trips_through_sibyl(self) -> None:
        self.run_agent_a()
        fresh_store = SibylStore.local(self.db_path, self.scope)
        result = next(
            item
            for item in fresh_store.list_work_results("software-handoff")
            if item.step_id == "inventory"
        )
        provenance = result.provenance
        self.assertIsNotNone(provenance)
        self.assertEqual(provenance.source_agent_id, scenario.AGENT_A.agent_id)
        self.assertEqual(provenance.source_session_id, scenario.AGENT_A.session_id)
        self.assertEqual(provenance.source_provider_id, scenario.AGENT_A.provider_id)
        self.assertEqual(provenance.work_category, scenario.INVENTORY_CATEGORY)
        self.assertEqual(provenance.external_exposure, ExternalExposure.SHAREABLE)

    def test_tampered_output_body_is_reported_as_undecodable_and_withheld(self) -> None:
        """A record whose output no longer matches its signature must not vanish."""

        self.run_agent_a()
        entities = self.store.client.list_entities(WORK_CATEGORY, limit=1000)
        target = next(entity for entity in entities if entity["body"]["step_id"] == "inventory")
        body = dict(target["body"])
        body["output"] = {"fixture": True, "kind": "component_inventory", "tampered": True}
        self.store.client.set_entity(WORK_CATEGORY, target["name"], body, status="completed")

        results, corrupt = self.store.list_work_records("software-handoff")
        self.assertNotIn("inventory", {result.step_id for result in results})
        self.assertIn("inventory", {record.step_id for record in corrupt})

        decision = self.evaluate().decision_for("inventory")
        self.assertEqual(decision.decision, DecisionKind.BLOCKED)
        self.assertEqual(decision.reason_code, "BLOCKED_RECORD_UNDECODABLE")
        self.assertTrue(decision.found_candidate)
        self.assertEqual(decision.verdicts.trust.status, TrustStatus.UNTRUSTED)
        self.assertNotIn("inventory", self.evaluate().approved_context.approved_step_ids)

    # -- external job safety ------------------------------------------------

    def _set_external_job(self, step_id: str, settlement: ExternalJobSettlement) -> None:
        result = self.stored_result(step_id)
        provenance = result.provenance
        self.assertIsNotNone(provenance)
        job = ExternalJobRef(
            provider_id="0xProviderPublicAddress",
            job_id="75656",
            chain_id=8453,
            settlement_state=settlement,
            transaction_hash="0xdeadbeef",
        )
        self.store.save_work_result(
            replace(result, provenance=replace(provenance, external_job=job))
        )

    def test_external_job_settlement_states_gate_paid_work(self) -> None:
        self.run_agent_a()
        expectations = {
            ExternalJobSettlement.SETTLED: (
                DecisionKind.REUSE,
                "REUSE_APPROVED_BY_POLICY",
                ExternalJobStatus.SAFE,
            ),
            ExternalJobSettlement.RECONCILIATION_REQUIRED: (
                DecisionKind.BLOCKED,
                "BLOCKED_EXTERNAL_JOB_RECONCILIATION_REQUIRED",
                ExternalJobStatus.RECONCILIATION_REQUIRED,
            ),
            ExternalJobSettlement.UNSETTLED: (
                DecisionKind.BLOCKED,
                "BLOCKED_EXTERNAL_JOB_UNSETTLED",
                ExternalJobStatus.UNSAFE,
            ),
            ExternalJobSettlement.UNKNOWN: (
                DecisionKind.BLOCKED,
                "BLOCKED_EXTERNAL_JOB_STATE_UNKNOWN",
                ExternalJobStatus.RECONCILIATION_REQUIRED,
            ),
        }
        for settlement, (kind, reason_code, job_status) in expectations.items():
            with self.subTest(settlement=settlement.value):
                self._set_external_job("inventory", settlement)
                decision = self.evaluate().decision_for("inventory")
                self.assertEqual(decision.decision, kind)
                self.assertEqual(decision.reason_code, reason_code)
                self.assertEqual(decision.verdicts.external_job.status, job_status)
                self.assertEqual(decision.evidence.external_job_id, "75656")
                self.assertEqual(decision.evidence.external_job_chain_id, 8453)

    def test_work_without_an_external_job_reports_not_applicable(self) -> None:
        self.run_agent_a()
        decision = self.evaluate().decision_for("inventory")
        self.assertEqual(decision.verdicts.external_job.status, ExternalJobStatus.NOT_APPLICABLE)
        self.assertIsNone(decision.evidence.external_job_id)

    # -- receipts -----------------------------------------------------------

    def test_receipt_counts_and_reasons_match_gate_decisions(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()
        receipt = evaluation.receipt

        expected = {kind.value: 0 for kind in DecisionKind}
        for decision in evaluation.decisions:
            expected[decision.decision.value] += 1
        self.assertEqual(dict(receipt.counts), expected)
        self.assertEqual(expected["reuse"], 2)
        self.assertEqual(expected["blocked"], 1)
        self.assertEqual(expected["pending_dependency"], 1)

        by_step = {entry.step_id: entry for entry in receipt.entries}
        self.assertEqual(set(by_step), {decision.step_id for decision in evaluation.decisions})
        for decision in evaluation.decisions:
            entry = by_step[decision.step_id]
            self.assertEqual(entry.decision, decision.decision)
            self.assertEqual(entry.reason_code, decision.reason_code)
            self.assertEqual(entry.reason, decision.reason)
            self.assertEqual(entry.verdicts.payload(), decision.verdicts.payload())

        # Only work that must still run carries an estimated additional cost.
        self.assertEqual(receipt.estimate_status, "known")
        self.assertEqual(receipt.estimated_additional_service_cost.amount, "0.3")
        self.assertIn("2 inherited", receipt.summary)
        self.assertIn("1 withheld by policy", receipt.summary)

    def test_receipt_rejects_counts_that_do_not_match_its_entries(self) -> None:
        self.run_agent_a()
        receipt = self.evaluate().receipt
        with self.assertRaises(HandoffPolicyError):
            replace(receipt, counts={"reuse": 99, "rerun": 0, "pending_dependency": 0, "blocked": 0})

    def test_unknown_estimate_is_not_filled_with_a_number(self) -> None:
        workflow = scenario.handoff_workflow(self.executors)
        unpriced = replace(
            workflow,
            steps=tuple(
                replace(step, estimated_cost=None) if step.id == "repair_scope" else step
                for step in workflow.steps
            ),
        )
        gate = HandoffGate(self.store)
        evaluation = gate.evaluate(
            HandoffRequest(
                scope=self.scope,
                workflow=unpriced,
                inputs=scenario.inputs(),
                recipient=scenario.AGENT_B,
                policies=scenario.policies(),
            ),
            now=scenario.NOW,
        )
        self.assertEqual(evaluation.receipt.estimate_status, "unknown")
        self.assertIsNone(evaluation.receipt.estimated_additional_service_cost)
        self.assertIn("unknown", evaluation.receipt.summary)

    # -- approved-context boundary -----------------------------------------

    def _blocked_decision(self, evaluation) -> HandoffDecision:
        return evaluation.decision_for("private_note")

    def test_approved_context_refuses_an_unapproved_decision(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()
        blocked = self._blocked_decision(evaluation)
        result = self.stored_result("private_note")

        with self.assertRaises(HandoffPolicyError):
            ApprovedWorkItem(
                step_id=blocked.step_id,
                work_category=scenario.PRIVATE_NOTE_CATEGORY,
                output=result.output,
                output_signature=result.output_signature,
                source_agent_id=scenario.AGENT_A.agent_id,
                source_session_id=scenario.AGENT_A.session_id,
                decision=blocked,
            )

    def test_approved_context_refuses_content_smuggled_under_an_approved_decision(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()
        approved = evaluation.decision_for("inventory")
        blocked_output = self.stored_result("private_note").output

        with self.assertRaises(HandoffPolicyError):
            ApprovedWorkItem(
                step_id="inventory",
                work_category=scenario.INVENTORY_CATEGORY,
                output=blocked_output,
                output_signature=self.stored_result("inventory").output_signature,
                source_agent_id=scenario.AGENT_A.agent_id,
                source_session_id=scenario.AGENT_A.session_id,
                decision=approved,
            )

    def test_approved_context_refuses_a_step_that_is_both_approved_and_blocked(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()
        item = evaluation.approved_context.items[0]
        with self.assertRaises(HandoffPolicyError):
            ApprovedContext(
                handoff_id=evaluation.handoff_id,
                scope=self.scope,
                recipient=scenario.AGENT_B,
                items=(item,),
                blocked=(
                    BlockedWorkNotice(item.step_id, DecisionKind.BLOCKED, "BLOCKED_TEST"),
                ),
            )

    def test_blocked_notice_cannot_describe_an_approved_decision(self) -> None:
        with self.assertRaises(HandoffPolicyError):
            BlockedWorkNotice("inventory", DecisionKind.REUSE, "REUSE_APPROVED_BY_POLICY")

    def test_approved_context_re_checks_items_whose_decision_was_swapped(self) -> None:
        """Second-layer guard: ApprovedContext does not trust an item's own check.

        `ApprovedWorkItem` refuses an unapproved decision at construction, so
        this test bypasses that first layer with `object.__setattr__` and proves
        `ApprovedContext` independently rejects the item.
        """

        self.run_agent_a()
        evaluation = self.evaluate()
        item = evaluation.approved_context.items[0]
        blocked = evaluation.decision_for("private_note")
        object.__setattr__(item, "decision", blocked)
        self.assertFalse(item.decision.approved)

        with self.assertRaises(HandoffPolicyError):
            ApprovedContext(
                handoff_id=evaluation.handoff_id,
                scope=self.scope,
                recipient=scenario.AGENT_B,
                items=(item,),
            )

    def test_work_result_rejects_a_non_provenance_value(self) -> None:
        from delta.core import DeltaValidationError

        output = {"fixture": True}
        with self.assertRaises(DeltaValidationError):
            WorkResult(
                scope=self.scope,
                workflow_id="software-handoff",
                step_id="inventory",
                implementation_id="inventory-fixture-v1",
                input_signature=self.signature_for("inventory"),
                output_signature=output_signature(output),
                output=output,
                completed_at=scenario.NOW,
                provenance={"source_agent_id": "spoofed"},  # type: ignore[arg-type]
            )

    def test_decision_and_verdicts_must_agree(self) -> None:
        approving = HandoffVerdicts(
            validity=Verdict(ValidityStatus.VALID, "VALID_MATCHING_RESULT", "valid"),
            trust=Verdict(TrustStatus.TRUSTED, "PROVENANCE_COMPLETE", "trusted"),
            authorization=Verdict(AuthorizationStatus.AUTHORIZED, "POLICY_AUTHORIZED", "ok"),
            dependency=Verdict(DependencyStatus.SATISFIED, "DEPENDENCIES_SATISFIED", "ok"),
            external_job=Verdict(ExternalJobStatus.NOT_APPLICABLE, "NO_EXTERNAL_JOB", "none"),
        )
        blocking = replace(
            approving,
            authorization=Verdict(
                AuthorizationStatus.UNAUTHORIZED, "EXTERNAL_EXPOSURE_BLOCKED", "withheld"
            ),
        )
        with self.assertRaises(HandoffPolicyError):
            HandoffDecision(
                step_id="inventory",
                decision=DecisionKind.REUSE,
                reason_code="REUSE_APPROVED_BY_POLICY",
                reason="claimed reuse",
                verdicts=blocking,
                found_candidate=True,
                evidence=WorkEvidence(),
            )
        with self.assertRaises(HandoffPolicyError):
            HandoffDecision(
                step_id="inventory",
                decision=DecisionKind.BLOCKED,
                reason_code="BLOCKED_TEST",
                reason="claimed block",
                verdicts=approving,
                found_candidate=True,
                evidence=WorkEvidence(),
            )

    # -- persistence --------------------------------------------------------

    def test_handoff_record_and_receipt_persist_and_reload_through_sibyl(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()
        HandoffGate(self.store).persist(evaluation)

        reader = SibylStore.local(self.db_path, self.scope)
        record = reader.get_handoff_record(evaluation.handoff_id)
        receipt = reader.get_reuse_receipt(evaluation.receipt.receipt_id)

        self.assertEqual(record.record_version, "1")
        self.assertEqual(record.workflow_id, "software-handoff")
        self.assertEqual(record.recipient, scenario.AGENT_B)
        self.assertEqual(set(record.approved_step_ids), {"inventory", "repair_scope"})
        self.assertEqual(record.blocked_step_ids, ("private_note",))
        self.assertEqual(
            [decision.payload() for decision in record.decisions],
            [decision.payload() for decision in evaluation.record.decisions],
        )

        self.assertEqual(receipt.record_version, "1")
        self.assertEqual(dict(receipt.counts), dict(evaluation.receipt.counts))
        self.assertEqual(receipt.summary, evaluation.receipt.summary)
        self.assertEqual(
            [entry.payload() for entry in receipt.entries],
            [entry.payload() for entry in evaluation.receipt.entries],
        )
        self.assertEqual(
            [item.receipt_id for item in reader.list_reuse_receipts(evaluation.handoff_id)],
            [evaluation.receipt.receipt_id],
        )

    def test_store_refuses_to_persist_a_work_output_body_in_a_handoff_record(self) -> None:
        """Defense in depth at the persistence boundary.

        `HandoffDecision.payload()` cannot emit an output body, so this exercises
        the store guard directly with a stand-in record whose decision payload
        smuggles one. It proves the boundary rejects the write rather than
        proving the gate would ever produce such a payload.
        """

        self.run_agent_a()
        evaluation = self.evaluate()

        class LeakyDecision:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def payload(self) -> dict:
                return self._payload

        class LeakyRecord:
            def __init__(self, source, decisions) -> None:
                self.scope = source.scope
                self.record_version = source.record_version
                self.handoff_id = source.handoff_id
                self.workflow_id = source.workflow_id
                self.workflow_version = source.workflow_version
                self.recipient = source.recipient
                self.policy_ids = source.policy_ids
                self.created_at = source.created_at
                self.decisions = decisions

        leaky = LeakyRecord(
            evaluation.record,
            (
                LeakyDecision(
                    {
                        "step_id": "private_note",
                        "decision": "blocked",
                        "output": {"note": scenario.PRIVATE_CANARY},
                    }
                ),
            ),
        )
        with self.assertRaises(SibylPersistenceError):
            self.store.save_handoff_record(leaky)
        self.assertIsNone(self.store.get_handoff_record(evaluation.handoff_id))

    def test_real_decision_and_receipt_payloads_carry_no_output_field(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()
        forbidden = {"output", "deliverable", "content", "body", "artifact_bytes"}
        for decision in evaluation.record.decisions:
            self.assertFalse(forbidden.intersection(decision.payload()))
            self.assertFalse(forbidden.intersection(decision.payload()["evidence"]))
        for entry in evaluation.receipt.entries:
            self.assertFalse(forbidden.intersection(entry.payload()))

    def test_handoff_records_are_project_scoped(self) -> None:
        self.run_agent_a()
        evaluation = self.evaluate()
        HandoffGate(self.store).persist(evaluation)

        other = SibylStore.local(self.db_path, scenario.scope(scenario.OTHER_PROJECT))
        self.assertIsNone(other.get_handoff_record(evaluation.handoff_id))
        self.assertIsNone(other.get_reuse_receipt(evaluation.receipt.receipt_id))
        self.assertEqual(other.list_reuse_receipts(), [])

    def test_repeated_evaluation_is_deterministic(self) -> None:
        self.run_agent_a()
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(first.handoff_id, second.handoff_id)
        self.assertEqual(first.receipt.receipt_id, second.receipt.receipt_id)
        self.assertEqual(
            [decision.payload() for decision in first.decisions],
            [decision.payload() for decision in second.decisions],
        )

    def test_a_different_recipient_produces_a_different_handoff_identity(self) -> None:
        self.run_agent_a()
        first = self.evaluate()
        other = self.evaluate(recipient=scenario.AGENT_B_OTHER_PROVIDER)
        self.assertNotEqual(first.handoff_id, other.handoff_id)


class PolicyValidationTests(unittest.TestCase):
    """Policy shape rules need no persistence."""

    def test_provider_allowlist_rule_requires_an_allowlist(self) -> None:
        with self.assertRaises(HandoffPolicyError):
            InheritancePolicy(
                policy_id="policy-x",
                project_scope=Scope("t", "p"),
                recipient_scope=Scope("t", "p"),
                work_category="category",
                provider_rule=ProviderRule.PROVIDER_ALLOWLIST,
            )

    def test_allowlist_without_the_allowlist_rule_is_rejected(self) -> None:
        with self.assertRaises(HandoffPolicyError):
            InheritancePolicy(
                policy_id="policy-x",
                project_scope=Scope("t", "p"),
                recipient_scope=Scope("t", "p"),
                work_category="category",
                provider_rule=ProviderRule.SAME_PROVIDER,
                provider_allowlist=("provider-alpha",),
            )

    def test_duplicate_policies_for_one_category_are_rejected(self) -> None:
        policy = InheritancePolicy(
            policy_id="policy-x",
            project_scope=Scope("t", "p"),
            recipient_scope=Scope("t", "p"),
            work_category="category",
        )
        with self.assertRaises(HandoffPolicyError):
            PolicySet([policy, replace(policy, policy_id="policy-y")])

    def test_work_declaration_requires_a_declared_category(self) -> None:
        from delta.core import DeltaValidationError

        with self.assertRaises(DeltaValidationError):
            WorkDeclaration("")

    def test_provenance_requires_an_agent_principal(self) -> None:
        from delta.core import DeltaValidationError

        with self.assertRaises(DeltaValidationError):
            WorkProvenance.from_principal(
                "not-a-principal", WorkDeclaration("category")  # type: ignore[arg-type]
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
