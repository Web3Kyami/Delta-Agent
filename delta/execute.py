"""Deterministic runtime execution on top of the core planner and Sibyl store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import threading
import uuid
from typing import Any, Mapping

from .core import (
    CostEstimate,
    DecisionKind,
    DependencyPending,
    ExecutionAttempt,
    ExecutionEvent,
    RevisionPlan,
    RevisionRequest,
    Scope,
    Step,
    StepDecision,
    WorkResult,
    build_revision_plan,
    input_signature,
    normalize_json,
    output_signature,
    resolve_step_input,
    topological_order,
    validate_inputs,
    validate_workflow,
)
from .store import SibylStore


class ExecutionBlocked(RuntimeError):
    """Raised only for an invalid engine invocation, never for provider failure."""


_EXECUTION_LOCK = threading.RLock()
_ACTIVE_ATTEMPT_STATES = frozenset(
    {"planned", "submitting", "active", "awaiting_provider", "ambiguous", "reconciliation_required"}
)


def _attempt_id() -> str:
    return f"attempt-{uuid.uuid4().hex}"


def _event_id() -> str:
    return f"event-{uuid.uuid4().hex}"


@dataclass(frozen=True)
class CostSummary:
    """Keep estimates, actual service costs, and network gas separate."""

    estimated_additional_service_cost: CostEstimate | None
    estimate_status: str
    actual_service_cost: CostEstimate | None = None
    network_gas_cost: CostEstimate | None = None


@dataclass(frozen=True)
class ExecutionReport:
    scope: Scope
    workflow_id: str
    decisions: tuple[StepDecision, ...]
    attempts: tuple[ExecutionAttempt, ...]
    outputs: Mapping[str, Any]
    costs: CostSummary


class DeltaEngine:
    """Execute ready workflow steps while keeping decisions and state honest."""

    def __init__(self, store: SibylStore) -> None:
        self.store = store

    def preview(self, request: RevisionRequest, *, now: datetime | None = None) -> RevisionPlan:
        """Preview persisted reusable work without executing a provider."""

        validate_workflow(request.workflow)
        return build_revision_plan(
            request,
            reusable_results=self.store.list_work_results(request.workflow.id),
            now=now,
        )

    def execute(
        self,
        request: RevisionRequest,
        *,
        now: datetime | None = None,
    ) -> ExecutionReport:
        """Run ready steps and reevaluate downstream inputs from actual outputs."""

        validate_workflow(request.workflow)
        normalized_inputs = validate_inputs(request.workflow, request.inputs)
        current_time = now or datetime.now(timezone.utc)
        self.store.save_plan(
            self.preview(request, now=current_time)
        )
        outputs: dict[str, Any] = {}
        failed_steps: set[str] = set()
        blocked_steps: set[str] = set()
        decisions: list[StepDecision] = []
        attempts: list[ExecutionAttempt] = []
        steps_by_id = {step.id: step for step in request.workflow.steps}

        for step_id in topological_order(request.workflow):
            step = steps_by_id[step_id]
            try:
                effective_input = resolve_step_input(step, normalized_inputs, outputs)
            except DependencyPending as error:
                dependencies = set(self._dependencies(step))
                blocked = dependencies & (failed_steps | blocked_steps)
                decision_kind = DecisionKind.BLOCKED if blocked else DecisionKind.PENDING_DEPENDENCY
                reason_code = "DEPENDENCY_FAILED" if blocked else "DEPENDENCY_OUTPUT_UNKNOWN"
                decisions.append(
                    StepDecision(
                        step_id=step.id,
                        decision=decision_kind,
                        reason_code=reason_code,
                        reason=str(error),
                        estimated_cost=step.estimated_cost,
                    )
                )
                blocked_steps.add(step.id)
                continue

            signature = input_signature(request.scope, request.workflow, step, effective_input)
            reusable = self.store.get_work_result(request.workflow.id, step.id, signature)
            if reusable is not None and reusable.matches(
                request.scope, request.workflow, step, signature, current_time
            ):
                outputs[step.id] = reusable.output
                decisions.append(
                    StepDecision(
                        step_id=step.id,
                        decision=DecisionKind.REUSE,
                        reason_code="MATCHING_RESULT",
                        reason="A persisted fresh result matches the current scope, implementation, and effective input.",
                        effective_input=effective_input,
                        input_signature=signature,
                    )
                )
                continue

            existing = self._active_attempt(step.id, signature)
            if existing is not None:
                blocked_steps.add(step.id)
                decisions.append(
                    StepDecision(
                        step_id=step.id,
                        decision=DecisionKind.BLOCKED,
                        reason_code="ACTIVE_ATTEMPT_EXISTS",
                        reason="An active or ambiguous attempt already owns this project, step, and input signature.",
                        effective_input=effective_input,
                        input_signature=signature,
                        estimated_cost=step.estimated_cost,
                    )
                )
                continue

            executor = step.executor
            if executor is None:
                blocked_steps.add(step.id)
                decisions.append(
                    StepDecision(
                        step_id=step.id,
                        decision=DecisionKind.BLOCKED,
                        reason_code="EXECUTOR_UNAVAILABLE",
                        reason="No executor is configured for this step, so Delta cannot claim a result.",
                        effective_input=effective_input,
                        input_signature=signature,
                        estimated_cost=step.estimated_cost,
                    )
                )
                continue

            attempt = self._start_attempt(request, step.id, signature)
            if attempt is None:
                blocked_steps.add(step.id)
                decisions.append(
                    StepDecision(
                        step_id=step.id,
                        decision=DecisionKind.BLOCKED,
                        reason_code="ACTIVE_ATTEMPT_EXISTS",
                        reason="An active or ambiguous attempt appeared before execution ownership could be created.",
                        effective_input=effective_input,
                        input_signature=signature,
                        estimated_cost=step.estimated_cost,
                    )
                )
                continue
            attempts.append(attempt)
            try:
                produced = self._call_executor(executor, effective_input)
                produced = normalize_json(produced)
                result = WorkResult(
                    scope=request.scope,
                    workflow_id=request.workflow.id,
                    step_id=step.id,
                    implementation_id=step.implementation_id,
                    input_signature=signature,
                    output_signature=output_signature(produced),
                    output=produced,
                    completed_at=current_time,
                    fresh_until=step.freshness.fresh_until(current_time),
                    successful_attempt_id=attempt.attempt_id,
                )
                with _EXECUTION_LOCK:
                    self.store.save_work_result(result)
                    succeeded = ExecutionAttempt(
                        attempt_id=attempt.attempt_id,
                        scope=attempt.scope,
                        workflow_id=attempt.workflow_id,
                        step_id=attempt.step_id,
                        status="succeeded",
                        input_signature=attempt.input_signature,
                        provider_job_id=attempt.provider_job_id,
                        provider_chain_id=attempt.provider_chain_id,
                        provider_id=attempt.provider_id,
                        offering_id=attempt.offering_id,
                        offering_name=attempt.offering_name,
                        requirements_signature=attempt.requirements_signature,
                    )
                    self.store.save_attempt(succeeded)
                    self.store.set_active_attempt(step.id, None)
                    self.store.append_event(
                        ExecutionEvent(
                            event_id=_event_id(),
                            scope=request.scope,
                            attempt_id=attempt.attempt_id,
                            reason_code="RESULT_PERSISTED",
                            state="succeeded",
                            detail="Step output was validated and persisted before downstream reevaluation.",
                            recorded_at=current_time,
                        )
                    )
                outputs[step.id] = result.output
                attempts[-1] = succeeded
                decisions.append(
                    StepDecision(
                        step_id=step.id,
                        decision=DecisionKind.RERUN,
                        reason_code="EXECUTED_SUCCESSFULLY",
                        reason="No reusable result matched, so the configured executor ran and its output was persisted.",
                        effective_input=effective_input,
                        input_signature=signature,
                        estimated_cost=step.estimated_cost,
                    )
                )
            except Exception as error:
                failed_steps.add(step.id)
                with _EXECUTION_LOCK:
                    failed = ExecutionAttempt(
                        attempt_id=attempt.attempt_id,
                        scope=attempt.scope,
                        workflow_id=attempt.workflow_id,
                        step_id=attempt.step_id,
                        status="failed",
                        input_signature=attempt.input_signature,
                        provider_job_id=attempt.provider_job_id,
                        provider_chain_id=attempt.provider_chain_id,
                        error_code="EXECUTOR_FAILED",
                        provider_id=attempt.provider_id,
                        offering_id=attempt.offering_id,
                        offering_name=attempt.offering_name,
                        requirements_signature=attempt.requirements_signature,
                    )
                    self.store.save_attempt(failed)
                    self.store.set_active_attempt(step.id, None)
                    self.store.append_event(
                        ExecutionEvent(
                            event_id=_event_id(),
                            scope=request.scope,
                            attempt_id=attempt.attempt_id,
                            reason_code="EXECUTION_FAILED",
                            state="failed",
                            detail=f"Configured executor failed: {type(error).__name__}.",
                            recorded_at=current_time,
                        )
                    )
                attempts[-1] = failed
                decisions.append(
                    StepDecision(
                        step_id=step.id,
                        decision=DecisionKind.RERUN,
                        reason_code="EXECUTION_FAILED",
                        reason="The executor failed; no reusable result was created.",
                        effective_input=effective_input,
                        input_signature=signature,
                        estimated_cost=step.estimated_cost,
                    )
                )

        return ExecutionReport(
            scope=request.scope,
            workflow_id=request.workflow.id,
            decisions=tuple(decisions),
            attempts=tuple(attempts),
            outputs=outputs,
            costs=self._cost_summary(decisions),
        )

    def _active_attempt(self, step_id: str, signature: str) -> ExecutionAttempt | None:
        with _EXECUTION_LOCK:
            active_id = self.store.get_active_attempt(step_id)
            if active_id is None:
                return None
            attempt = self.store.get_attempt(active_id)
            if attempt is None:
                return None
            if attempt.input_signature == signature and attempt.status in _ACTIVE_ATTEMPT_STATES:
                return attempt
            return None

    def _start_attempt(
        self,
        request: RevisionRequest,
        step_id: str,
        signature: str,
    ) -> ExecutionAttempt | None:
        with _EXECUTION_LOCK:
            existing = self._active_attempt(step_id, signature)
            if existing is not None:
                return None
            attempt = ExecutionAttempt(
                attempt_id=_attempt_id(),
                scope=request.scope,
                workflow_id=request.workflow.id,
                step_id=step_id,
                status="active",
                input_signature=signature,
            )
            self.store.save_attempt(attempt)
            self.store.set_active_attempt(step_id, attempt.attempt_id)
            self.store.append_event(
                ExecutionEvent(
                    event_id=_event_id(),
                    scope=request.scope,
                    attempt_id=attempt.attempt_id,
                    reason_code="ATTEMPT_STARTED",
                    state="active",
                    detail="Execution ownership was persisted before calling the executor.",
                    recorded_at=request.requested_at or datetime.now(timezone.utc),
                )
            )
            return attempt

    @staticmethod
    def _call_executor(executor: Any, effective_input: Mapping[str, Any]) -> Any:
        execute = getattr(executor, "execute", None)
        if callable(execute):
            return execute(effective_input)
        if callable(executor):
            return executor(effective_input)
        raise ExecutionBlocked("configured executor is not callable")

    @staticmethod
    def _dependencies(step: Step) -> tuple[str, ...]:
        from .core import extract_dependencies

        return extract_dependencies(step)

    @staticmethod
    def _cost_summary(decisions: list[StepDecision]) -> CostSummary:
        reruns = [decision for decision in decisions if decision.decision == DecisionKind.RERUN]
        if not reruns:
            return CostSummary(CostEstimate("0", source="delta-runtime"), "known")
        if any(decision.estimated_cost is None or decision.estimated_cost.amount is None for decision in reruns):
            return CostSummary(None, "unknown")
        total = sum(
            (Decimal(decision.estimated_cost.amount) for decision in reruns if decision.estimated_cost),
            Decimal("0"),
        )
        return CostSummary(
            CostEstimate(format(total.normalize(), "f"), source="delta-runtime"),
            "known",
        )
