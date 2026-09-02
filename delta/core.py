"""Core schemas and deterministic planning for Delta.

This module deliberately has no network, wallet, or persistence dependency.
It describes work and validates the boundaries that later adapters must obey.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence


class DeltaValidationError(ValueError):
    """Base error for invalid Delta inputs."""


class WorkflowValidationError(DeltaValidationError):
    """Raised when a workflow is incomplete or not acyclic."""


class InputValidationError(DeltaValidationError):
    """Raised when workflow inputs are missing, unknown, or wrong-shaped."""


class DependencyPending(DeltaValidationError):
    """Raised when a step output is needed but is not available yet."""


class ApprovalValidationError(DeltaValidationError):
    """Raised when an approval cannot authorize a particular action."""


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise DeltaValidationError(f"{label} must be a non-empty trimmed string")
    return value


def normalize_json(value: Any) -> Any:
    """Return a JSON-compatible value or reject it explicitly.

    Dates are normalized to ISO strings because they are valid workflow input
    values but are not JSON primitives. Non-finite numbers and opaque Python
    objects are rejected so signatures cannot silently change meaning.
    """

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DeltaValidationError("non-finite floats are not valid JSON values")
        return value
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DeltaValidationError("JSON object keys must be strings")
            normalized[key] = normalize_json(item)
        return normalized
    raise DeltaValidationError(
        f"value of type {type(value).__name__} is not JSON-compatible"
    )


def canonical_json(value: Any) -> str:
    """Encode a JSON value deterministically for hashing and persistence."""

    return json.dumps(
        normalize_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _signature(value: Any, prefix: str) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    project_id: str

    def __post_init__(self) -> None:
        _identifier(self.tenant_id, "tenant_id")
        _identifier(self.project_id, "project_id")


@dataclass(frozen=True)
class InputSpec:
    kind: str = "json"
    required: bool = True

    def __post_init__(self) -> None:
        allowed = {"json", "string", "date", "boolean", "integer", "number"}
        if self.kind not in allowed:
            raise DeltaValidationError(f"unsupported input kind: {self.kind}")
        if not isinstance(self.required, bool):
            raise DeltaValidationError("required must be a boolean")


@dataclass(frozen=True)
class FreshnessPolicy:
    ttl_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.ttl_seconds is not None and (
            not isinstance(self.ttl_seconds, (int, float))
            or isinstance(self.ttl_seconds, bool)
            or not math.isfinite(self.ttl_seconds)
            or self.ttl_seconds <= 0
        ):
            raise DeltaValidationError("ttl_seconds must be a finite positive number")

    def fresh_until(self, completed_at: datetime) -> datetime | None:
        if self.ttl_seconds is None:
            return None
        return completed_at + timedelta(seconds=self.ttl_seconds)


@dataclass(frozen=True)
class CostEstimate:
    amount: str | None = None
    currency: str = "USDC"
    source: str = "unknown"
    quoted_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.amount is not None:
            _money(self.amount, "amount")
        if not isinstance(self.currency, str) or not self.currency:
            raise DeltaValidationError("currency must be a non-empty string")
        _identifier(self.source, "source")


@dataclass(frozen=True)
class ProviderQuote:
    """Read-only provider facts captured for later approval and reconciliation."""

    provider_id: str
    offering_id: str
    chain_id: int
    price: CostEstimate
    requirements_schema: Mapping[str, Any]
    deliverable_format: str
    online: bool
    sla_seconds: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            _identifier(self.provider_id, "provider_id")
            _identifier(self.offering_id, "offering_id")
        except DeltaValidationError as error:
            raise DeltaValidationError(str(error)) from error
        if not isinstance(self.chain_id, int) or isinstance(self.chain_id, bool) or self.chain_id <= 0:
            raise DeltaValidationError("chain_id must be a positive integer")
        if not isinstance(self.price, CostEstimate):
            raise DeltaValidationError("price must be a CostEstimate")
        if not isinstance(self.requirements_schema, Mapping):
            raise DeltaValidationError("requirements_schema must be an object")
        _identifier(self.deliverable_format, "deliverable_format")
        if not isinstance(self.online, bool):
            raise DeltaValidationError("online must be a boolean")
        if self.sla_seconds is not None and (
            not isinstance(self.sla_seconds, int)
            or isinstance(self.sla_seconds, bool)
            or self.sla_seconds < 0
        ):
            raise DeltaValidationError("sla_seconds must be a non-negative integer")
        object.__setattr__(self, "requirements_schema", normalize_json(dict(self.requirements_schema)))
        object.__setattr__(self, "metadata", normalize_json(dict(self.metadata)))


@dataclass(frozen=True)
class WorkflowInputRef:
    name: str

    def __post_init__(self) -> None:
        _identifier(self.name, "workflow input name")


@dataclass(frozen=True)
class StepOutputRef:
    step_id: str

    def __post_init__(self) -> None:
        _identifier(self.step_id, "step output step_id")


def workflow_input(name: str) -> WorkflowInputRef:
    return WorkflowInputRef(name)


def step_output(step_id: str) -> StepOutputRef:
    return StepOutputRef(step_id)


@dataclass(frozen=True)
class Step:
    id: str
    implementation_id: str
    bind: Mapping[str, Any] = field(default_factory=dict)
    freshness: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    estimated_cost: CostEstimate | None = None
    executor: Any = None

    def __post_init__(self) -> None:
        _identifier(self.id, "step id")
        _identifier(self.implementation_id, "implementation_id")
        if not isinstance(self.bind, Mapping):
            raise DeltaValidationError("step bind must be an object")
        if any(not isinstance(key, str) for key in self.bind):
            raise DeltaValidationError("step binding keys must be strings")
        if self.executor is not None and not (
            callable(self.executor) or callable(getattr(self.executor, "execute", None))
        ):
            raise DeltaValidationError("executor must be callable or expose execute()")
        object.__setattr__(self, "bind", dict(self.bind))


@dataclass(frozen=True)
class Workflow:
    id: str
    version: str
    inputs: Mapping[str, InputSpec]
    steps: Sequence[Step]

    def __post_init__(self) -> None:
        _identifier(self.id, "workflow id")
        _identifier(self.version, "workflow version")
        if not isinstance(self.inputs, Mapping):
            raise DeltaValidationError("workflow inputs must be an object")
        if any(not isinstance(key, str) for key in self.inputs):
            raise DeltaValidationError("workflow input names must be strings")
        if any(not isinstance(spec, InputSpec) for spec in self.inputs.values()):
            raise DeltaValidationError("workflow inputs must use InputSpec values")
        object.__setattr__(self, "inputs", dict(self.inputs))
        object.__setattr__(self, "steps", tuple(self.steps))


def _walk_bindings(value: Any) -> Iterable[WorkflowInputRef | StepOutputRef]:
    if isinstance(value, (WorkflowInputRef, StepOutputRef)):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_bindings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_bindings(item)


def extract_dependencies(step: Step) -> tuple[str, ...]:
    """Return explicitly declared upstream step IDs in stable order."""

    seen: set[str] = set()
    dependencies: list[str] = []
    for reference in _walk_bindings(step.bind):
        if isinstance(reference, StepOutputRef) and reference.step_id not in seen:
            seen.add(reference.step_id)
            dependencies.append(reference.step_id)
    return tuple(dependencies)


def validate_workflow(workflow: Workflow) -> None:
    """Validate identifiers, references, and the declared dependency graph."""

    if not workflow.steps:
        raise WorkflowValidationError("workflow must contain at least one step")
    step_ids = [step.id for step in workflow.steps]
    if len(step_ids) != len(set(step_ids)):
        raise WorkflowValidationError("step IDs must be unique")
    input_names = set(workflow.inputs)
    for step in workflow.steps:
        for reference in _walk_bindings(step.bind):
            if isinstance(reference, WorkflowInputRef) and reference.name not in input_names:
                raise WorkflowValidationError(
                    f"step {step.id} references unknown workflow input {reference.name}"
                )
            if isinstance(reference, StepOutputRef) and reference.step_id not in step_ids:
                raise WorkflowValidationError(
                    f"step {step.id} references unknown step {reference.step_id}"
                )
            if isinstance(reference, StepOutputRef) and reference.step_id == step.id:
                raise WorkflowValidationError(f"step {step.id} cannot depend on itself")
    topological_order(workflow)


def topological_order(workflow: Workflow) -> tuple[str, ...]:
    """Return a deterministic topological order or reject a cycle."""

    step_ids = [step.id for step in workflow.steps]
    by_id = {step.id: step for step in workflow.steps}
    dependencies = {step.id: set(extract_dependencies(step)) for step in workflow.steps}
    if any(dep not in by_id for deps in dependencies.values() for dep in deps):
        raise WorkflowValidationError("dependency references an unknown step")
    order: list[str] = []
    remaining = set(step_ids)
    while remaining:
        ready = [step_id for step_id in step_ids if step_id in remaining and not (dependencies[step_id] & remaining)]
        if not ready:
            raise WorkflowValidationError("workflow contains a dependency cycle")
        order.extend(ready)
        remaining.difference_update(ready)
    return tuple(order)


def validate_inputs(workflow: Workflow, supplied: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the request inputs declared by a workflow."""

    if not isinstance(supplied, Mapping):
        raise InputValidationError("workflow inputs must be an object")
    unknown = set(supplied) - set(workflow.inputs)
    if unknown:
        raise InputValidationError(f"unknown workflow inputs: {sorted(unknown)}")
    normalized: dict[str, Any] = {}
    for name, spec in workflow.inputs.items():
        if name not in supplied:
            if spec.required:
                raise InputValidationError(f"missing required workflow input: {name}")
            continue
        value = normalize_json(supplied[name])
        if spec.kind == "string" and not isinstance(value, str):
            raise InputValidationError(f"input {name} must be a string")
        if spec.kind == "date":
            if not isinstance(value, str):
                raise InputValidationError(f"input {name} must be a date")
            try:
                date.fromisoformat(value[:10])
            except ValueError as error:
                raise InputValidationError(f"input {name} must be an ISO date") from error
        if spec.kind == "boolean" and not isinstance(value, bool):
            raise InputValidationError(f"input {name} must be a boolean")
        if spec.kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise InputValidationError(f"input {name} must be an integer")
        if spec.kind == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise InputValidationError(f"input {name} must be a number")
        normalized[name] = value
    return normalized


def resolve_step_input(
    step: Step,
    workflow_inputs: Mapping[str, Any],
    available_outputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve only explicitly declared bindings for a step."""

    def resolve(value: Any) -> Any:
        if isinstance(value, WorkflowInputRef):
            if value.name not in workflow_inputs:
                raise DependencyPending(f"workflow input {value.name} is unavailable")
            return workflow_inputs[value.name]
        if isinstance(value, StepOutputRef):
            if value.step_id not in available_outputs:
                raise DependencyPending(f"step output {value.step_id} is unavailable")
            return available_outputs[value.step_id]
        if isinstance(value, Mapping):
            return {key: resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve(item) for item in value]
        return normalize_json(value)

    return normalize_json(resolve(step.bind))


def input_signature(
    scope: Scope,
    workflow: Workflow,
    step: Step,
    effective_input: Mapping[str, Any],
) -> str:
    return _signature(
        {
            "tenant_id": scope.tenant_id,
            "project_id": scope.project_id,
            "workflow_id": workflow.id,
            "workflow_version": workflow.version,
            "step_id": step.id,
            "implementation_id": step.implementation_id,
            "effective_input": effective_input,
        },
        "input",
    )


def output_signature(output: Any) -> str:
    return _signature(output, "output")


@dataclass(frozen=True)
class ArtifactReference:
    artifact_id: str
    content_hash: str
    media_type: str
    byte_size: int
    uri: str | None = None
    available: bool = True

    def __post_init__(self) -> None:
        _identifier(self.artifact_id, "artifact_id")
        _identifier(self.content_hash, "content_hash")
        _identifier(self.media_type, "media_type")
        if not isinstance(self.byte_size, int) or isinstance(self.byte_size, bool) or self.byte_size < 0:
            raise DeltaValidationError("byte_size must be a non-negative integer")
        if not isinstance(self.available, bool):
            raise DeltaValidationError("available must be a boolean")


@dataclass(frozen=True)
class WorkResult:
    scope: Scope
    workflow_id: str
    step_id: str
    implementation_id: str
    input_signature: str
    output_signature: str
    output: Any
    completed_at: datetime
    fresh_until: datetime | None = None
    successful_attempt_id: str | None = None
    artifact: ArtifactReference | None = None
    status: str = "completed"

    def __post_init__(self) -> None:
        _identifier(self.workflow_id, "workflow_id")
        _identifier(self.step_id, "step_id")
        _identifier(self.implementation_id, "implementation_id")
        _identifier(self.input_signature, "input_signature")
        _identifier(self.output_signature, "output_signature")
        if self.status != "completed":
            raise DeltaValidationError("WorkResult must represent completed work")
        object.__setattr__(self, "output", normalize_json(self.output))
        if self.output_signature != output_signature(self.output):
            raise DeltaValidationError("output_signature does not match output")

    def is_fresh(self, now: datetime | None = None) -> bool:
        if self.fresh_until is None:
            return True
        return (now or datetime.now(timezone.utc)) < self.fresh_until

    def matches(
        self,
        scope: Scope,
        workflow: Workflow,
        step: Step,
        expected_input_signature: str,
        now: datetime | None = None,
    ) -> bool:
        return (
            self.scope == scope
            and self.workflow_id == workflow.id
            and self.step_id == step.id
            and self.implementation_id == step.implementation_id
            and self.input_signature == expected_input_signature
            and self.is_fresh(now)
            and (self.artifact is None or self.artifact.available)
        )


@dataclass(frozen=True)
class ExecutionAttempt:
    attempt_id: str
    scope: Scope
    workflow_id: str
    step_id: str
    status: str
    input_signature: str
    provider_job_id: str | None = None
    provider_chain_id: int | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.attempt_id, "attempt_id")
        _identifier(self.workflow_id, "workflow_id")
        _identifier(self.step_id, "step_id")
        _identifier(self.status, "status")
        _identifier(self.input_signature, "input_signature")
        if self.provider_chain_id is not None and (
            not isinstance(self.provider_chain_id, int) or isinstance(self.provider_chain_id, bool) or self.provider_chain_id <= 0
        ):
            raise DeltaValidationError("provider_chain_id must be a positive integer")


@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    scope: Scope
    attempt_id: str
    reason_code: str
    state: str
    detail: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, label in (
            (self.event_id, "event_id"),
            (self.attempt_id, "attempt_id"),
            (self.reason_code, "reason_code"),
            (self.state, "state"),
            (self.detail, "detail"),
        ):
            _identifier(value, label)


class DecisionKind(str, Enum):
    REUSE = "reuse"
    RERUN = "rerun"
    PENDING_DEPENDENCY = "pending_dependency"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RevisionRequest:
    scope: Scope
    workflow: Workflow
    inputs: Mapping[str, Any]
    requested_at: datetime | None = None


@dataclass(frozen=True)
class StepDecision:
    step_id: str
    decision: DecisionKind
    reason_code: str
    reason: str
    effective_input: Mapping[str, Any] | None = None
    input_signature: str | None = None
    estimated_cost: CostEstimate | None = None

    def __post_init__(self) -> None:
        _identifier(self.step_id, "step_id")
        _identifier(self.reason_code, "reason_code")
        _identifier(self.reason, "reason")
        if self.effective_input is not None:
            object.__setattr__(self, "effective_input", normalize_json(dict(self.effective_input)))


@dataclass(frozen=True)
class RevisionPlan:
    plan_id: str
    scope: Scope
    workflow_id: str
    workflow_version: str
    decisions: tuple[StepDecision, ...]

    def __post_init__(self) -> None:
        _identifier(self.plan_id, "plan_id")
        _identifier(self.workflow_id, "workflow_id")
        _identifier(self.workflow_version, "workflow_version")


def build_revision_plan(
    request: RevisionRequest,
    reusable_results: Iterable[WorkResult] = (),
    now: datetime | None = None,
) -> RevisionPlan:
    """Build a provider-neutral preview from real inputs and supplied results."""

    validate_workflow(request.workflow)
    normalized_inputs = validate_inputs(request.workflow, request.inputs)
    reusable = tuple(reusable_results)
    outputs: dict[str, Any] = {}
    decisions: list[StepDecision] = []
    steps_by_id = {step.id: step for step in request.workflow.steps}

    for step_id in topological_order(request.workflow):
        step = steps_by_id[step_id]
        try:
            effective = resolve_step_input(step, normalized_inputs, outputs)
        except DependencyPending as error:
            decisions.append(
                StepDecision(
                    step_id=step.id,
                    decision=DecisionKind.PENDING_DEPENDENCY,
                    reason_code="PENDING_DEPENDENCY_OUTPUT",
                    reason=str(error),
                    estimated_cost=step.estimated_cost,
                )
            )
            continue
        signature = input_signature(request.scope, request.workflow, step, effective)
        reusable_result = next(
            (
                result
                for result in reusable
                if result.matches(request.scope, request.workflow, step, signature, now)
            ),
            None,
        )
        if reusable_result is not None:
            outputs[step.id] = reusable_result.output
            decisions.append(
                StepDecision(
                    step_id=step.id,
                    decision=DecisionKind.REUSE,
                    reason_code="REUSE_VALID_RESULT",
                    reason="A completed result matches the project, implementation, input signature, and freshness policy.",
                    effective_input=effective,
                    input_signature=signature,
                )
            )
        else:
            decisions.append(
                StepDecision(
                    step_id=step.id,
                    decision=DecisionKind.RERUN,
                    reason_code="RERUN_NO_VALID_RESULT",
                    reason="No fresh completed result matches this project, implementation, and effective input.",
                    effective_input=effective,
                    input_signature=signature,
                    estimated_cost=step.estimated_cost,
                )
            )

    plan_payload = {
        "scope": {"tenant_id": request.scope.tenant_id, "project_id": request.scope.project_id},
        "workflow_id": request.workflow.id,
        "workflow_version": request.workflow.version,
        "inputs": normalized_inputs,
        "decisions": [
            {
                "step_id": decision.step_id,
                "decision": decision.decision.value,
                "input_signature": decision.input_signature,
            }
            for decision in decisions
        ],
    }
    return RevisionPlan(
        plan_id=_signature(plan_payload, "plan"),
        scope=request.scope,
        workflow_id=request.workflow.id,
        workflow_version=request.workflow.version,
        decisions=tuple(decisions),
    )


def _money(value: str, label: str) -> Decimal:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ApprovalValidationError(f"{label} must be a trimmed decimal string")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ApprovalValidationError(f"{label} must be a decimal string") from error
    if not amount.is_finite() or amount < 0:
        raise ApprovalValidationError(f"{label} must be finite and non-negative")
    return amount


@dataclass(frozen=True)
class SpendApproval:
    approval_id: str
    plan_id: str
    scope: Scope
    allowed_steps: tuple[str, ...]
    provider_id: str
    offering_id: str
    chain_id: int
    action_scope: tuple[str, ...]
    currency: str
    max_total_service_spend: str
    max_per_job_spend: str | None
    expires_at: datetime

    def __post_init__(self) -> None:
        _identifier(self.approval_id, "approval_id")
        _identifier(self.plan_id, "plan_id")
        if not self.allowed_steps:
            raise ApprovalValidationError("allowed_steps cannot be empty")
        if any(not isinstance(step, str) or not step for step in self.allowed_steps):
            raise ApprovalValidationError("allowed_steps contains an invalid step")
        if not self.action_scope:
            raise ApprovalValidationError("action_scope cannot be empty")
        if any(not isinstance(action, str) or not action for action in self.action_scope):
            raise ApprovalValidationError("action_scope contains an invalid action")
        if not isinstance(self.currency, str) or not self.currency:
            raise ApprovalValidationError("currency is required")
        try:
            _identifier(self.provider_id, "provider_id")
            _identifier(self.offering_id, "offering_id")
        except DeltaValidationError as error:
            raise ApprovalValidationError(str(error)) from error
        total = _money(self.max_total_service_spend, "max_total_service_spend")
        if self.max_per_job_spend is not None and _money(self.max_per_job_spend, "max_per_job_spend") > total:
            raise ApprovalValidationError("max_per_job_spend cannot exceed total service spend")
        if not isinstance(self.chain_id, int) or isinstance(self.chain_id, bool) or self.chain_id <= 0:
            raise ApprovalValidationError("chain_id must be a positive integer")
        if not isinstance(self.expires_at, datetime):
            raise ApprovalValidationError("expires_at must be a datetime")


def validate_spend_approval(
    approval: SpendApproval,
    plan: RevisionPlan,
    *,
    step_id: str,
    provider_id: str,
    offering_id: str,
    chain_id: int,
    action: str,
    amount: str,
    currency: str,
    now: datetime | None = None,
) -> None:
    """Reject any paid action outside the exact approved plan boundary."""

    if approval.plan_id != plan.plan_id:
        raise ApprovalValidationError("approval plan identity does not match")
    if approval.scope != plan.scope:
        raise ApprovalValidationError("approval project scope does not match")
    if step_id not in approval.allowed_steps:
        raise ApprovalValidationError("step is outside the approved steps")
    if approval.provider_id != provider_id:
        raise ApprovalValidationError("provider scope does not match")
    if approval.offering_id != offering_id:
        raise ApprovalValidationError("offering scope does not match")
    if approval.chain_id != chain_id:
        raise ApprovalValidationError("chain scope does not match")
    if action not in approval.action_scope:
        raise ApprovalValidationError("action is outside the approved action scope")
    if approval.expires_at <= (now or datetime.now(timezone.utc)):
        raise ApprovalValidationError("spend approval has expired")
    if approval.currency != currency:
        raise ApprovalValidationError("currency does not match the approval")
    requested = _money(amount, "amount")
    if requested > _money(approval.max_total_service_spend, "max_total_service_spend"):
        raise ApprovalValidationError("amount exceeds total service-spend cap")
    if approval.max_per_job_spend is not None and requested > _money(approval.max_per_job_spend, "max_per_job_spend"):
        raise ApprovalValidationError("amount exceeds per-job service-spend cap")
