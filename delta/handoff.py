"""Deterministic trusted-handoff contracts and the pre-prompt policy gate.

This module decides what previous work may cross a handoff into a receiving
agent's context. It runs *before* any prompt, message, tool argument, trace, or
provider request is constructed.

Design rules enforced here:

- Validity and authorization are independent. A fresh, intact, matching result
  can still be unauthorized, and an authorized result can still be stale.
- Every candidate carries five separately inspectable verdicts: validity,
  trust, authorization, dependency, and external job.
- Blocked work cannot enter :class:`ApprovedContext`. The type refuses it at
  construction time, so a later prompt builder cannot be handed blocked content
  by mistake.
- Dependencies come from developer-declared bindings only. Nothing in this
  module asks a model to infer the graph, the relevant inputs, or eligibility.
- Receipts and handoff records carry references and safe metadata. They never
  copy untrusted output bodies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
from typing import Any, Iterable, Mapping, Sequence

from .core import (
    AgentPrincipal,
    ArtifactReference,
    CostEstimate,
    DecisionKind,
    DependencyPending,
    DeltaValidationError,
    ExternalExposure,
    ExternalJobRef,
    ExternalJobSettlement,
    Scope,
    Step,
    Workflow,
    WorkProvenance,
    WorkResult,
    canonical_json,
    extract_dependencies,
    input_signature,
    normalize_json,
    output_signature,
    resolve_step_input,
    topological_order,
    validate_inputs,
    validate_workflow,
)

HANDOFF_RECORD_VERSION = "1"
REUSE_RECEIPT_VERSION = "1"


class HandoffPolicyError(DeltaValidationError):
    """Raised when handoff policy or approved-context boundaries are violated."""


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise HandoffPolicyError(f"{label} must be a non-empty trimmed string")
    return value


def _digest(payload: Any, prefix: str) -> str:
    return f"{prefix}:{hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()}"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class ProviderRule(str, Enum):
    """How the receiving agent's runtime provider is constrained."""

    ANY_PROVIDER = "any_provider"
    SAME_PROVIDER = "same_provider"
    PROVIDER_ALLOWLIST = "provider_allowlist"


class ExternalExposureRule(str, Enum):
    """What content sensitivity the receiving agent may inherit."""

    INTERNAL_ALLOWED = "internal_allowed"
    SHAREABLE_ONLY = "shareable_only"


@dataclass(frozen=True)
class InheritancePolicy:
    """A minimal, developer-declared rule for one work category.

    ``project_scope`` is the project that owns the work. ``recipient_scope`` is
    the project the receiving agent is operating in. Both must match for
    inheritance, which is what stops cross-project reuse.
    """

    policy_id: str
    project_scope: Scope
    recipient_scope: Scope
    work_category: str
    provider_rule: ProviderRule = ProviderRule.SAME_PROVIDER
    external_exposure_rule: ExternalExposureRule = ExternalExposureRule.INTERNAL_ALLOWED
    agent_allowlist: tuple[str, ...] | None = None
    provider_allowlist: tuple[str, ...] | None = None
    version: str = "1"

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        _identifier(self.work_category, "work_category")
        _identifier(self.version, "policy version")
        if not isinstance(self.project_scope, Scope) or not isinstance(self.recipient_scope, Scope):
            raise HandoffPolicyError("policy scopes must be Scope values")
        if not isinstance(self.provider_rule, ProviderRule):
            raise HandoffPolicyError("provider_rule must be a ProviderRule")
        if not isinstance(self.external_exposure_rule, ExternalExposureRule):
            raise HandoffPolicyError("external_exposure_rule must be an ExternalExposureRule")
        for allowlist, label in (
            (self.agent_allowlist, "agent_allowlist"),
            (self.provider_allowlist, "provider_allowlist"),
        ):
            if allowlist is None:
                continue
            if not isinstance(allowlist, tuple) or not allowlist:
                raise HandoffPolicyError(f"{label} must be a non-empty tuple or None")
            if any(not isinstance(item, str) or not item for item in allowlist):
                raise HandoffPolicyError(f"{label} contains an invalid identity")
        if self.provider_rule is ProviderRule.PROVIDER_ALLOWLIST and self.provider_allowlist is None:
            raise HandoffPolicyError("provider allowlist rule requires provider_allowlist")
        if self.provider_rule is not ProviderRule.PROVIDER_ALLOWLIST and self.provider_allowlist is not None:
            raise HandoffPolicyError("provider_allowlist is only valid with the allowlist rule")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "project_scope": {
                "tenant_id": self.project_scope.tenant_id,
                "project_id": self.project_scope.project_id,
            },
            "recipient_scope": {
                "tenant_id": self.recipient_scope.tenant_id,
                "project_id": self.recipient_scope.project_id,
            },
            "work_category": self.work_category,
            "provider_rule": self.provider_rule.value,
            "external_exposure_rule": self.external_exposure_rule.value,
            "agent_allowlist": list(self.agent_allowlist) if self.agent_allowlist else None,
            "provider_allowlist": list(self.provider_allowlist) if self.provider_allowlist else None,
        }


class PolicySet:
    """A deterministic lookup of inheritance policies by work category."""

    def __init__(self, policies: Iterable[InheritancePolicy] = ()) -> None:
        by_category: dict[str, InheritancePolicy] = {}
        for policy in policies:
            if not isinstance(policy, InheritancePolicy):
                raise HandoffPolicyError("policy set accepts InheritancePolicy values only")
            if policy.work_category in by_category:
                raise HandoffPolicyError(
                    f"duplicate inheritance policy for work category {policy.work_category!r}"
                )
            by_category[policy.work_category] = policy
        self._by_category = by_category

    def for_category(self, work_category: str | None) -> InheritancePolicy | None:
        if work_category is None:
            return None
        return self._by_category.get(work_category)

    def policy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(policy.policy_id for policy in self._by_category.values()))

    def identity_payload(self) -> list[dict[str, Any]]:
        return [
            self._by_category[category].identity_payload()
            for category in sorted(self._by_category)
        ]

    def __len__(self) -> int:
        return len(self._by_category)


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


class ValidityStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    NO_CANDIDATE = "no_candidate"
    UNEVALUATED = "unevaluated"


class TrustStatus(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    NO_CANDIDATE = "no_candidate"
    UNEVALUATED = "unevaluated"


class AuthorizationStatus(str, Enum):
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    NO_CANDIDATE = "no_candidate"
    UNEVALUATED = "unevaluated"


class DependencyStatus(str, Enum):
    SATISFIED = "satisfied"
    PENDING = "pending"


class ExternalJobStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    SAFE = "safe"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    UNSAFE = "unsafe"
    UNEVALUATED = "unevaluated"


@dataclass(frozen=True)
class Verdict:
    """One inspectable verdict: a status, a stable reason code, and prose."""

    status: ValidityStatus | TrustStatus | AuthorizationStatus | DependencyStatus | ExternalJobStatus
    reason_code: str
    reason: str

    def __post_init__(self) -> None:
        _identifier(self.reason_code, "reason_code")
        _identifier(self.reason, "reason")

    def payload(self) -> dict[str, str]:
        return {"status": self.status.value, "reason_code": self.reason_code, "reason": self.reason}


@dataclass(frozen=True)
class HandoffVerdicts:
    """The five separate verdicts computed for one candidate work item."""

    validity: Verdict
    trust: Verdict
    authorization: Verdict
    dependency: Verdict
    external_job: Verdict

    def __post_init__(self) -> None:
        expected = (
            (self.validity, ValidityStatus, "validity"),
            (self.trust, TrustStatus, "trust"),
            (self.authorization, AuthorizationStatus, "authorization"),
            (self.dependency, DependencyStatus, "dependency"),
            (self.external_job, ExternalJobStatus, "external_job"),
        )
        for verdict, status_type, label in expected:
            if not isinstance(verdict, Verdict) or not isinstance(verdict.status, status_type):
                raise HandoffPolicyError(f"{label} verdict has the wrong status type")

    def payload(self) -> dict[str, dict[str, str]]:
        return {
            "validity": self.validity.payload(),
            "trust": self.trust.payload(),
            "authorization": self.authorization.payload(),
            "dependency": self.dependency.payload(),
            "external_job": self.external_job.payload(),
        }

    def approves_inheritance(self) -> bool:
        """True only when every verdict permits content to cross the handoff."""

        return (
            self.dependency.status is DependencyStatus.SATISFIED
            and self.external_job.status
            in {ExternalJobStatus.NOT_APPLICABLE, ExternalJobStatus.SAFE}
            and self.trust.status is TrustStatus.TRUSTED
            and self.authorization.status is AuthorizationStatus.AUTHORIZED
            and self.validity.status is ValidityStatus.VALID
        )


# ---------------------------------------------------------------------------
# Candidate discovery and decisions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkEvidence:
    """Safe references for a candidate. Never the untrusted output body."""

    record_key: str | None = None
    output_signature: str | None = None
    artifact_id: str | None = None
    artifact_hash: str | None = None
    artifact_available: bool | None = None
    source_agent_id: str | None = None
    source_session_id: str | None = None
    source_provider_id: str | None = None
    work_category: str | None = None
    external_exposure: str | None = None
    external_job_provider_id: str | None = None
    external_job_id: str | None = None
    external_job_chain_id: int | None = None
    external_job_settlement: str | None = None
    external_job_transaction_hash: str | None = None
    completed_at: str | None = None
    fresh_until: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "record_key": self.record_key,
            "output_signature": self.output_signature,
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "artifact_available": self.artifact_available,
            "source_agent_id": self.source_agent_id,
            "source_session_id": self.source_session_id,
            "source_provider_id": self.source_provider_id,
            "work_category": self.work_category,
            "external_exposure": self.external_exposure,
            "external_job_provider_id": self.external_job_provider_id,
            "external_job_id": self.external_job_id,
            "external_job_chain_id": self.external_job_chain_id,
            "external_job_settlement": self.external_job_settlement,
            "external_job_transaction_hash": self.external_job_transaction_hash,
            "completed_at": self.completed_at,
            "fresh_until": self.fresh_until,
        }


def _evidence_for(result: WorkResult | None, record_key: str | None = None) -> WorkEvidence:
    if result is None:
        return WorkEvidence(record_key=record_key)
    provenance = result.provenance
    external_job = provenance.external_job if provenance else None
    artifact: ArtifactReference | None = result.artifact
    return WorkEvidence(
        record_key=record_key,
        output_signature=result.output_signature,
        artifact_id=artifact.artifact_id if artifact else None,
        artifact_hash=artifact.content_hash if artifact else None,
        artifact_available=artifact.available if artifact else None,
        source_agent_id=provenance.source_agent_id if provenance else None,
        source_session_id=provenance.source_session_id if provenance else None,
        source_provider_id=provenance.source_provider_id if provenance else None,
        work_category=provenance.work_category if provenance else None,
        external_exposure=provenance.external_exposure.value if provenance else None,
        external_job_provider_id=external_job.provider_id if external_job else None,
        external_job_id=external_job.job_id if external_job else None,
        external_job_chain_id=external_job.chain_id if external_job else None,
        external_job_settlement=external_job.settlement_state.value if external_job else None,
        external_job_transaction_hash=external_job.transaction_hash if external_job else None,
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        fresh_until=result.fresh_until.isoformat() if result.fresh_until else None,
    )


@dataclass(frozen=True)
class HandoffDecision:
    """The deterministic outcome for one workflow step."""

    step_id: str
    decision: DecisionKind
    reason_code: str
    reason: str
    verdicts: HandoffVerdicts
    found_candidate: bool
    evidence: WorkEvidence
    input_signature: str | None = None
    estimated_cost: CostEstimate | None = None

    def __post_init__(self) -> None:
        _identifier(self.step_id, "step_id")
        _identifier(self.reason_code, "reason_code")
        _identifier(self.reason, "reason")
        if not isinstance(self.decision, DecisionKind):
            raise HandoffPolicyError("decision must be a DecisionKind")
        if not isinstance(self.verdicts, HandoffVerdicts):
            raise HandoffPolicyError("decision requires HandoffVerdicts")
        if not isinstance(self.found_candidate, bool):
            raise HandoffPolicyError("found_candidate must be a boolean")
        if not isinstance(self.evidence, WorkEvidence):
            raise HandoffPolicyError("decision requires WorkEvidence")
        if self.decision is DecisionKind.REUSE and not self.verdicts.approves_inheritance():
            raise HandoffPolicyError("a reuse decision requires every verdict to approve")
        if self.decision is not DecisionKind.REUSE and self.verdicts.approves_inheritance():
            raise HandoffPolicyError("fully approved verdicts must produce a reuse decision")

    @property
    def approved(self) -> bool:
        return self.decision is DecisionKind.REUSE

    def payload(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "found_candidate": self.found_candidate,
            "input_signature": self.input_signature,
            "verdicts": self.verdicts.payload(),
            "evidence": self.evidence.payload(),
            "estimated_cost": None
            if self.estimated_cost is None
            else {
                "amount": self.estimated_cost.amount,
                "currency": self.estimated_cost.currency,
                "source": self.estimated_cost.source,
            },
        }


@dataclass(frozen=True)
class HandoffCandidate:
    """A discovered candidate plus its decision.

    ``result`` is retained in memory for approved-context construction only.
    It is never persisted here and never copied into a record or receipt.
    """

    step_id: str
    result: WorkResult | None
    decision: HandoffDecision

    def __post_init__(self) -> None:
        if self.result is not None and not isinstance(self.result, WorkResult):
            raise HandoffPolicyError("candidate result must be a WorkResult")
        if self.decision.step_id != self.step_id:
            raise HandoffPolicyError("candidate decision step identity does not match")
        if self.decision.approved and self.result is None:
            raise HandoffPolicyError("an approved decision requires a discovered result")


# ---------------------------------------------------------------------------
# Approved context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovedWorkItem:
    """Approved inheritable content for exactly one step.

    Construction re-checks the decision, so an unapproved item cannot become an
    approved work item even if a caller builds one directly.
    """

    step_id: str
    work_category: str
    output: Any
    output_signature: str
    source_agent_id: str
    source_session_id: str
    decision: HandoffDecision
    artifact: ArtifactReference | None = None

    def __post_init__(self) -> None:
        _identifier(self.step_id, "step_id")
        _identifier(self.work_category, "work_category")
        _identifier(self.output_signature, "output_signature")
        _identifier(self.source_agent_id, "source_agent_id")
        _identifier(self.source_session_id, "source_session_id")
        if not isinstance(self.decision, HandoffDecision):
            raise HandoffPolicyError("approved work requires a HandoffDecision")
        if self.decision.step_id != self.step_id:
            raise HandoffPolicyError("approved work step identity does not match its decision")
        if not self.decision.approved or not self.decision.verdicts.approves_inheritance():
            raise HandoffPolicyError("approved work requires an approved handoff decision")
        object.__setattr__(self, "output", normalize_json(self.output))
        if output_signature(self.output) != self.output_signature:
            raise HandoffPolicyError("approved work output does not match its signature")

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "work_category": self.work_category,
            "source_agent_id": self.source_agent_id,
            "source_session_id": self.source_session_id,
            "output": self.output,
            "output_signature": self.output_signature,
            "artifact_id": self.artifact.artifact_id if self.artifact else None,
        }


@dataclass(frozen=True)
class BlockedWorkNotice:
    """Identity and reason only. Blocked content never appears here."""

    step_id: str
    decision: DecisionKind
    reason_code: str

    def __post_init__(self) -> None:
        _identifier(self.step_id, "step_id")
        _identifier(self.reason_code, "reason_code")
        if not isinstance(self.decision, DecisionKind):
            raise HandoffPolicyError("blocked notice requires a DecisionKind")
        if self.decision is DecisionKind.REUSE:
            raise HandoffPolicyError("an approved decision cannot be a blocked notice")

    def payload(self) -> dict[str, str]:
        return {
            "step_id": self.step_id,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class ApprovedContext:
    """The only container a prompt builder may consume.

    It can hold approved work items exclusively. Every item is re-validated on
    construction, and blocked work is represented by identity and reason code
    with no content.
    """

    handoff_id: str
    scope: Scope
    recipient: AgentPrincipal
    items: tuple[ApprovedWorkItem, ...] = ()
    blocked: tuple[BlockedWorkNotice, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.handoff_id, "handoff_id")
        if not isinstance(self.scope, Scope):
            raise HandoffPolicyError("approved context requires a Scope")
        if not isinstance(self.recipient, AgentPrincipal):
            raise HandoffPolicyError("approved context requires an AgentPrincipal")
        if not isinstance(self.items, tuple) or not isinstance(self.blocked, tuple):
            raise HandoffPolicyError("approved context collections must be tuples")
        for item in self.items:
            if not isinstance(item, ApprovedWorkItem):
                raise HandoffPolicyError("approved context accepts ApprovedWorkItem values only")
            if not item.decision.approved:
                raise HandoffPolicyError("approved context rejected an unapproved decision")
        for notice in self.blocked:
            if not isinstance(notice, BlockedWorkNotice):
                raise HandoffPolicyError("blocked notices must be BlockedWorkNotice values")
        approved_steps = [item.step_id for item in self.items]
        if len(set(approved_steps)) != len(approved_steps):
            raise HandoffPolicyError("approved context contains duplicate steps")
        blocked_steps = {notice.step_id for notice in self.blocked}
        if blocked_steps & set(approved_steps):
            raise HandoffPolicyError("a step cannot be both approved and blocked")

    @property
    def approved_step_ids(self) -> tuple[str, ...]:
        return tuple(item.step_id for item in self.items)

    @property
    def blocked_step_ids(self) -> tuple[str, ...]:
        return tuple(notice.step_id for notice in self.blocked)

    def inherited_outputs(self) -> dict[str, Any]:
        """Approved outputs keyed by step, for downstream input resolution."""

        return {item.step_id: item.output for item in self.items}

    def prompt_payload(self) -> dict[str, Any]:
        """The complete serializable payload a prompt builder may read."""

        return {
            "handoff_id": self.handoff_id,
            "recipient": {
                "agent_id": self.recipient.agent_id,
                "session_id": self.recipient.session_id,
                "provider_id": self.recipient.provider_id,
            },
            "approved_work": [item.prompt_payload() for item in self.items],
            "excluded_work": [notice.payload() for notice in self.blocked],
        }


# ---------------------------------------------------------------------------
# Handoff record and reuse receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HandoffRecord:
    """A persisted, versioned record of one gate evaluation."""

    handoff_id: str
    scope: Scope
    workflow_id: str
    workflow_version: str
    recipient: AgentPrincipal
    policy_ids: tuple[str, ...]
    decisions: tuple[HandoffDecision, ...]
    created_at: datetime
    record_version: str = HANDOFF_RECORD_VERSION

    def __post_init__(self) -> None:
        _identifier(self.handoff_id, "handoff_id")
        _identifier(self.workflow_id, "workflow_id")
        _identifier(self.workflow_version, "workflow_version")
        _identifier(self.record_version, "record_version")
        if not isinstance(self.scope, Scope):
            raise HandoffPolicyError("handoff record requires a Scope")
        if not isinstance(self.recipient, AgentPrincipal):
            raise HandoffPolicyError("handoff record requires an AgentPrincipal")
        if not isinstance(self.created_at, datetime):
            raise HandoffPolicyError("created_at must be a datetime")
        if any(not isinstance(decision, HandoffDecision) for decision in self.decisions):
            raise HandoffPolicyError("handoff record decisions must be HandoffDecision values")

    @property
    def approved_step_ids(self) -> tuple[str, ...]:
        return tuple(decision.step_id for decision in self.decisions if decision.approved)

    @property
    def blocked_step_ids(self) -> tuple[str, ...]:
        return tuple(
            decision.step_id
            for decision in self.decisions
            if decision.decision is DecisionKind.BLOCKED
        )


@dataclass(frozen=True)
class ReuseReceiptEntry:
    """Per-item receipt entry with references only, never output bodies."""

    step_id: str
    decision: DecisionKind
    reason_code: str
    reason: str
    verdicts: HandoffVerdicts
    evidence: WorkEvidence
    estimated_cost: CostEstimate | None = None

    def __post_init__(self) -> None:
        _identifier(self.step_id, "step_id")
        _identifier(self.reason_code, "reason_code")
        _identifier(self.reason, "reason")
        if not isinstance(self.decision, DecisionKind):
            raise HandoffPolicyError("receipt entry requires a DecisionKind")
        if not isinstance(self.verdicts, HandoffVerdicts):
            raise HandoffPolicyError("receipt entry requires HandoffVerdicts")
        if not isinstance(self.evidence, WorkEvidence):
            raise HandoffPolicyError("receipt entry requires WorkEvidence")

    @classmethod
    def from_decision(cls, decision: HandoffDecision) -> "ReuseReceiptEntry":
        return cls(
            step_id=decision.step_id,
            decision=decision.decision,
            reason_code=decision.reason_code,
            reason=decision.reason,
            verdicts=decision.verdicts,
            evidence=decision.evidence,
            estimated_cost=decision.estimated_cost,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "verdicts": self.verdicts.payload(),
            "evidence": self.evidence.payload(),
            "estimated_cost": None
            if self.estimated_cost is None
            else {
                "amount": self.estimated_cost.amount,
                "currency": self.estimated_cost.currency,
                "source": self.estimated_cost.source,
            },
        }


@dataclass(frozen=True)
class ReuseReceipt:
    """A persisted explanation of what crossed the handoff and why."""

    receipt_id: str
    handoff_id: str
    scope: Scope
    workflow_id: str
    recipient: AgentPrincipal
    entries: tuple[ReuseReceiptEntry, ...]
    counts: Mapping[str, int]
    estimated_additional_service_cost: CostEstimate | None
    estimate_status: str
    summary: str
    created_at: datetime
    record_version: str = REUSE_RECEIPT_VERSION

    def __post_init__(self) -> None:
        _identifier(self.receipt_id, "receipt_id")
        _identifier(self.handoff_id, "handoff_id")
        _identifier(self.workflow_id, "workflow_id")
        _identifier(self.summary, "summary")
        _identifier(self.record_version, "record_version")
        if self.estimate_status not in {"known", "unknown"}:
            raise HandoffPolicyError("estimate_status must be known or unknown")
        if any(not isinstance(entry, ReuseReceiptEntry) for entry in self.entries):
            raise HandoffPolicyError("receipt entries must be ReuseReceiptEntry values")
        recomputed = _decision_counts(entry.decision for entry in self.entries)
        if dict(self.counts) != recomputed:
            raise HandoffPolicyError("receipt counts do not match its entries")
        object.__setattr__(self, "counts", recomputed)


def _decision_counts(decisions: Iterable[DecisionKind]) -> dict[str, int]:
    counts = {kind.value: 0 for kind in DecisionKind}
    for decision in decisions:
        counts[decision.value] += 1
    return counts


_STATUS_TYPES: dict[str, Any] = {
    "validity": ValidityStatus,
    "trust": TrustStatus,
    "authorization": AuthorizationStatus,
    "dependency": DependencyStatus,
    "external_job": ExternalJobStatus,
}


def _decode_verdicts(payload: Mapping[str, Any]) -> HandoffVerdicts:
    decoded: dict[str, Verdict] = {}
    for name, status_type in _STATUS_TYPES.items():
        item = payload[name]
        decoded[name] = Verdict(
            status=status_type(item["status"]),
            reason_code=item["reason_code"],
            reason=item["reason"],
        )
    return HandoffVerdicts(**decoded)


def _decode_evidence(payload: Mapping[str, Any]) -> WorkEvidence:
    return WorkEvidence(**{key: payload.get(key) for key in WorkEvidence().payload()})


def _decode_cost(payload: Mapping[str, Any] | None) -> CostEstimate | None:
    if payload is None:
        return None
    return CostEstimate(
        amount=payload.get("amount"),
        currency=payload["currency"],
        source=payload["source"],
    )


def _decode_decision(payload: Mapping[str, Any]) -> HandoffDecision:
    """Rebuild a decision from a persisted record.

    ``HandoffDecision.__post_init__`` re-checks decision/verdict consistency, so
    a tampered record cannot decode into an approved decision unless every
    verdict in that record also approves.
    """

    return HandoffDecision(
        step_id=payload["step_id"],
        decision=DecisionKind(payload["decision"]),
        reason_code=payload["reason_code"],
        reason=payload["reason"],
        verdicts=_decode_verdicts(payload["verdicts"]),
        found_candidate=payload["found_candidate"],
        evidence=_decode_evidence(payload["evidence"]),
        input_signature=payload.get("input_signature"),
        estimated_cost=_decode_cost(payload.get("estimated_cost")),
    )


def _decode_receipt_entry(payload: Mapping[str, Any]) -> ReuseReceiptEntry:
    return ReuseReceiptEntry(
        step_id=payload["step_id"],
        decision=DecisionKind(payload["decision"]),
        reason_code=payload["reason_code"],
        reason=payload["reason"],
        verdicts=_decode_verdicts(payload["verdicts"]),
        evidence=_decode_evidence(payload["evidence"]),
        estimated_cost=_decode_cost(payload.get("estimated_cost")),
    )


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HandoffRequest:
    """Everything the gate needs. No model output participates in this."""

    scope: Scope
    workflow: Workflow
    inputs: Mapping[str, Any]
    recipient: AgentPrincipal
    policies: PolicySet
    requested_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise HandoffPolicyError("handoff request requires a Scope")
        if not isinstance(self.workflow, Workflow):
            raise HandoffPolicyError("handoff request requires a Workflow")
        if not isinstance(self.recipient, AgentPrincipal):
            raise HandoffPolicyError("handoff request requires an AgentPrincipal")
        if not isinstance(self.policies, PolicySet):
            raise HandoffPolicyError("handoff request requires a PolicySet")


@dataclass(frozen=True)
class HandoffEvaluation:
    """The gate result: candidates, record, receipt, and approved context."""

    handoff_id: str
    candidates: tuple[HandoffCandidate, ...]
    record: HandoffRecord
    receipt: ReuseReceipt
    approved_context: ApprovedContext

    @property
    def decisions(self) -> tuple[HandoffDecision, ...]:
        return tuple(candidate.decision for candidate in self.candidates)

    def decision_for(self, step_id: str) -> HandoffDecision:
        for candidate in self.candidates:
            if candidate.step_id == step_id:
                return candidate.decision
        raise KeyError(step_id)


class HandoffGate:
    """Deterministically decide what previous work may cross a handoff.

    The gate reads candidate work from the Sibyl-backed store, computes five
    verdicts per step, and returns an approved context that contains approved
    work only. It performs no network calls, no model calls, and no writes
    unless :meth:`persist` is called.
    """

    #: Verdict precedence. Money safety first, then trust, then authorization,
    #: then validity. A blocked item never contributes content, so ordering
    #: only changes the reported reason, never whether content is excluded.
    def __init__(self, store: Any) -> None:
        self.store = store

    # -- public API ---------------------------------------------------------

    def evaluate(self, request: HandoffRequest, *, now: datetime | None = None) -> HandoffEvaluation:
        validate_workflow(request.workflow)
        normalized_inputs = validate_inputs(request.workflow, request.inputs)
        current_time = now or request.requested_at or datetime.now(timezone.utc)

        persisted = self._load_candidates(request)
        corrupt = self._load_corrupt(request)
        steps_by_id = {step.id: step for step in request.workflow.steps}
        inherited_outputs: dict[str, Any] = {}
        candidates: list[HandoffCandidate] = []

        for step_id in topological_order(request.workflow):
            step = steps_by_id[step_id]
            try:
                effective_input = resolve_step_input(step, normalized_inputs, inherited_outputs)
            except DependencyPending as error:
                candidates.append(
                    self._pending_candidate(step, str(error), inherited_outputs)
                )
                continue

            signature = input_signature(request.scope, request.workflow, step, effective_input)
            candidate_result = persisted.get((step.id, signature))
            fallback = None
            if candidate_result is None:
                fallback = self._latest_for_step(persisted, step.id)
            if candidate_result is None and fallback is None and step.id in corrupt:
                candidates.append(
                    self._undecodable_candidate(step, signature, corrupt[step.id])
                )
                continue
            candidate = self._evaluate_candidate(
                request=request,
                step=step,
                signature=signature,
                result=candidate_result or fallback,
                matched_signature=candidate_result is not None,
                now=current_time,
            )
            candidates.append(candidate)
            if candidate.decision.approved and candidate.result is not None:
                inherited_outputs[step.id] = candidate.result.output

        handoff_id = self._handoff_id(request, candidates)
        record = HandoffRecord(
            handoff_id=handoff_id,
            scope=request.scope,
            workflow_id=request.workflow.id,
            workflow_version=request.workflow.version,
            recipient=request.recipient,
            policy_ids=request.policies.policy_ids(),
            decisions=tuple(candidate.decision for candidate in candidates),
            created_at=current_time,
        )
        approved_context = self._build_approved_context(handoff_id, request, candidates)
        receipt = self._build_receipt(handoff_id, request, candidates, current_time)
        return HandoffEvaluation(
            handoff_id=handoff_id,
            candidates=tuple(candidates),
            record=record,
            receipt=receipt,
            approved_context=approved_context,
        )

    def persist(self, evaluation: HandoffEvaluation) -> None:
        """Persist the versioned handoff record and receipt through Sibyl."""

        self.store.save_handoff_record(evaluation.record)
        self.store.save_reuse_receipt(evaluation.receipt)

    # -- discovery ----------------------------------------------------------

    def _load_candidates(self, request: HandoffRequest) -> dict[tuple[str, str], WorkResult]:
        results = self.store.list_work_results(request.workflow.id)
        indexed: dict[tuple[str, str], WorkResult] = {}
        for result in results:
            key = (result.step_id, result.input_signature)
            existing = indexed.get(key)
            if existing is None or _completed_after(result, existing):
                indexed[key] = result
        return indexed

    def _load_corrupt(self, request: HandoffRequest) -> dict[str, str]:
        """Report work records that could not be decoded, keyed by step.

        Without this, a record whose stored output no longer matches its
        signature would simply vanish from discovery and the gate would report
        "no candidate work" — the same answer it gives for a genuinely empty
        store. An undecodable record is a distinct, reportable state.
        """

        lister = getattr(self.store, "list_work_records", None)
        if not callable(lister):
            return {}
        loaded: Any = lister(request.workflow.id)
        _results, corrupt = loaded
        return {record.step_id: record.reason for record in corrupt if record.step_id}

    def _undecodable_candidate(
        self,
        step: Step,
        signature: str,
        reason: str,
    ) -> HandoffCandidate:
        verdicts = HandoffVerdicts(
            validity=Verdict(
                ValidityStatus.INVALID,
                "RECORD_UNDECODABLE",
                "A persisted record for this step could not be decoded safely.",
            ),
            trust=Verdict(
                TrustStatus.UNTRUSTED,
                "RECORD_UNDECODABLE",
                "A record that cannot be decoded cannot be trusted for inheritance.",
            ),
            authorization=Verdict(
                AuthorizationStatus.UNEVALUATED,
                "AUTHORIZATION_REQUIRES_TRUSTED_PROVENANCE",
                "Authorization is not evaluated for a record that cannot be decoded.",
            ),
            dependency=Verdict(
                DependencyStatus.SATISFIED,
                "DEPENDENCIES_SATISFIED",
                "Every declared upstream output needed for this step is available.",
            ),
            external_job=Verdict(
                ExternalJobStatus.UNEVALUATED,
                "EXTERNAL_JOB_REQUIRES_CANDIDATE",
                "External job safety is not evaluated for a record that cannot be decoded.",
            ),
        )
        decision = HandoffDecision(
            step_id=step.id,
            decision=DecisionKind.BLOCKED,
            reason_code="BLOCKED_RECORD_UNDECODABLE",
            reason="A persisted record exists for this step but could not be decoded, so it is withheld.",
            verdicts=verdicts,
            found_candidate=True,
            evidence=WorkEvidence(),
            input_signature=signature,
            estimated_cost=step.estimated_cost,
        )
        return HandoffCandidate(step_id=step.id, result=None, decision=decision)

    @staticmethod
    def _latest_for_step(
        persisted: Mapping[tuple[str, str], WorkResult],
        step_id: str,
    ) -> WorkResult | None:
        best: WorkResult | None = None
        for (candidate_step, _signature), result in sorted(persisted.items()):
            if candidate_step != step_id:
                continue
            if best is None or _completed_after(result, best):
                best = result
        return best

    # -- verdicts -----------------------------------------------------------

    def _pending_candidate(
        self,
        step: Step,
        detail: str,
        inherited_outputs: Mapping[str, Any],
    ) -> HandoffCandidate:
        missing = tuple(
            dependency
            for dependency in extract_dependencies(step)
            if dependency not in inherited_outputs
        )
        reason = (
            "Upstream output "
            + ", ".join(missing)
            + " has not crossed the handoff, so this step's effective input is unknown."
            if missing
            else detail
        )
        verdicts = HandoffVerdicts(
            validity=Verdict(
                ValidityStatus.UNEVALUATED,
                "VALIDITY_REQUIRES_EFFECTIVE_INPUT",
                "Validity cannot be judged before the effective input is known.",
            ),
            trust=Verdict(
                TrustStatus.UNEVALUATED,
                "TRUST_REQUIRES_EFFECTIVE_INPUT",
                "Trust cannot be judged before a candidate is identified.",
            ),
            authorization=Verdict(
                AuthorizationStatus.UNEVALUATED,
                "AUTHORIZATION_REQUIRES_EFFECTIVE_INPUT",
                "Authorization cannot be judged before a candidate is identified.",
            ),
            dependency=Verdict(
                DependencyStatus.PENDING,
                "DEPENDENCY_OUTPUT_UNAVAILABLE",
                reason,
            ),
            external_job=Verdict(
                ExternalJobStatus.UNEVALUATED,
                "EXTERNAL_JOB_REQUIRES_CANDIDATE",
                "External job safety cannot be judged before a candidate is identified.",
            ),
        )
        decision = HandoffDecision(
            step_id=step.id,
            decision=DecisionKind.PENDING_DEPENDENCY,
            reason_code="PENDING_DEPENDENCY_OUTPUT",
            reason=reason,
            verdicts=verdicts,
            found_candidate=False,
            evidence=WorkEvidence(),
            estimated_cost=step.estimated_cost,
        )
        return HandoffCandidate(step_id=step.id, result=None, decision=decision)

    def _evaluate_candidate(
        self,
        *,
        request: HandoffRequest,
        step: Step,
        signature: str,
        result: WorkResult | None,
        matched_signature: bool,
        now: datetime,
    ) -> HandoffCandidate:
        dependency = Verdict(
            DependencyStatus.SATISFIED,
            "DEPENDENCIES_SATISFIED",
            "Every declared upstream output needed for this step is available.",
        )
        evidence = _evidence_for(
            result,
            None
            if result is None
            else self._record_key(request, result.step_id, result.input_signature),
        )

        if result is None:
            verdicts = HandoffVerdicts(
                validity=Verdict(
                    ValidityStatus.NO_CANDIDATE,
                    "NO_CANDIDATE_WORK",
                    "No persisted work exists for this project, step, and effective input.",
                ),
                trust=Verdict(
                    TrustStatus.NO_CANDIDATE,
                    "NO_CANDIDATE_WORK",
                    "There is no candidate record whose provenance could be trusted.",
                ),
                authorization=Verdict(
                    AuthorizationStatus.NO_CANDIDATE,
                    "NO_CANDIDATE_WORK",
                    "There is no candidate record to authorize.",
                ),
                dependency=dependency,
                external_job=Verdict(
                    ExternalJobStatus.NOT_APPLICABLE,
                    "NO_EXTERNAL_JOB",
                    "No external paid job is attached to this step.",
                ),
            )
            decision = HandoffDecision(
                step_id=step.id,
                decision=DecisionKind.RERUN,
                reason_code="RERUN_NO_CANDIDATE_WORK",
                reason="No previous work was found for this step, so it must run.",
                verdicts=verdicts,
                found_candidate=False,
                evidence=evidence,
                input_signature=signature,
                estimated_cost=step.estimated_cost,
            )
            return HandoffCandidate(step_id=step.id, result=None, decision=decision)

        validity = self._validity_verdict(request, step, signature, result, matched_signature, now)
        trust = self._trust_verdict(result)
        authorization = self._authorization_verdict(request, result, trust)
        external_job = self._external_job_verdict(result)
        verdicts = HandoffVerdicts(
            validity=validity,
            trust=trust,
            authorization=authorization,
            dependency=dependency,
            external_job=external_job,
        )

        decision_kind, reason_code, reason = self._decide(verdicts)
        decision = HandoffDecision(
            step_id=step.id,
            decision=decision_kind,
            reason_code=reason_code,
            reason=reason,
            verdicts=verdicts,
            found_candidate=True,
            evidence=evidence,
            input_signature=signature,
            estimated_cost=None if decision_kind is DecisionKind.REUSE else step.estimated_cost,
        )
        return HandoffCandidate(step_id=step.id, result=result, decision=decision)

    def _validity_verdict(
        self,
        request: HandoffRequest,
        step: Step,
        signature: str,
        result: WorkResult,
        matched_signature: bool,
        now: datetime,
    ) -> Verdict:
        if result.status != "completed":
            return Verdict(
                ValidityStatus.INVALID,
                "WORK_NOT_COMPLETED",
                "The persisted record does not represent completed work.",
            )
        if result.scope != request.scope:
            return Verdict(
                ValidityStatus.INVALID,
                "PROJECT_SCOPE_MISMATCH",
                "The persisted work belongs to a different project scope.",
            )
        if result.workflow_id != request.workflow.id:
            return Verdict(
                ValidityStatus.INVALID,
                "WORKFLOW_MISMATCH",
                "The persisted work belongs to a different workflow.",
            )
        if result.step_id != step.id:
            return Verdict(
                ValidityStatus.INVALID,
                "STEP_MISMATCH",
                "The persisted work belongs to a different step.",
            )
        if result.implementation_id != step.implementation_id:
            return Verdict(
                ValidityStatus.INVALID,
                "IMPLEMENTATION_MISMATCH",
                "The step implementation identity changed since this work completed.",
            )
        if not matched_signature or result.input_signature != signature:
            return Verdict(
                ValidityStatus.INVALID,
                "INPUT_SIGNATURE_MISMATCH",
                "The effective input changed, so this result no longer describes the requested work.",
            )
        if not result.is_fresh(now):
            return Verdict(
                ValidityStatus.INVALID,
                "RESULT_EXPIRED",
                "The result is outside its declared freshness policy.",
            )
        if result.artifact is not None and not result.artifact.available:
            return Verdict(
                ValidityStatus.INVALID,
                "ARTIFACT_UNAVAILABLE",
                "The referenced artifact is unavailable, so the result cannot be reused.",
            )
        return Verdict(
            ValidityStatus.VALID,
            "VALID_MATCHING_RESULT",
            "A completed result matches this project, step, implementation, input, and freshness policy.",
        )

    def _trust_verdict(self, result: WorkResult) -> Verdict:
        provenance = result.provenance
        if provenance is None:
            return Verdict(
                TrustStatus.UNTRUSTED,
                "PROVENANCE_MISSING",
                "The record carries no source agent or session provenance, so it is not inheritable.",
            )
        if output_signature(result.output) != result.output_signature:
            return Verdict(
                TrustStatus.UNTRUSTED,
                "OUTPUT_SIGNATURE_MISMATCH",
                "The stored output does not match its recorded signature.",
            )
        return Verdict(
            TrustStatus.TRUSTED,
            "PROVENANCE_COMPLETE",
            "The record identifies its source agent, session, provider, and declared work category.",
        )

    def _authorization_verdict(
        self,
        request: HandoffRequest,
        result: WorkResult,
        trust: Verdict,
    ) -> Verdict:
        provenance = result.provenance
        if provenance is None or trust.status is not TrustStatus.TRUSTED:
            return Verdict(
                AuthorizationStatus.UNEVALUATED,
                "AUTHORIZATION_REQUIRES_TRUSTED_PROVENANCE",
                "Authorization is not evaluated for a record without trusted provenance.",
            )
        policy = request.policies.for_category(provenance.work_category)
        if policy is None:
            return Verdict(
                AuthorizationStatus.UNAUTHORIZED,
                "NO_POLICY_FOR_WORK_CATEGORY",
                "No inheritance policy authorizes this declared work category.",
            )
        if policy.project_scope != result.scope:
            return Verdict(
                AuthorizationStatus.UNAUTHORIZED,
                "POLICY_PROJECT_MISMATCH",
                "The policy governs a different owning project than this work.",
            )
        if policy.recipient_scope != request.scope:
            return Verdict(
                AuthorizationStatus.UNAUTHORIZED,
                "RECIPIENT_PROJECT_MISMATCH",
                "The policy does not authorize this receiving project scope.",
            )
        if policy.agent_allowlist is not None and request.recipient.agent_id not in policy.agent_allowlist:
            return Verdict(
                AuthorizationStatus.UNAUTHORIZED,
                "RECIPIENT_AGENT_NOT_ALLOWED",
                "The receiving agent is not on the inheritance allowlist for this work.",
            )
        if policy.provider_rule is ProviderRule.SAME_PROVIDER:
            if request.recipient.provider_id != provenance.source_provider_id:
                return Verdict(
                    AuthorizationStatus.UNAUTHORIZED,
                    "PROVIDER_RULE_SAME_PROVIDER_VIOLATED",
                    "This work may only be inherited by an agent on the same runtime provider.",
                )
        elif policy.provider_rule is ProviderRule.PROVIDER_ALLOWLIST:
            allowlist = policy.provider_allowlist or ()
            if request.recipient.provider_id not in allowlist:
                return Verdict(
                    AuthorizationStatus.UNAUTHORIZED,
                    "PROVIDER_NOT_ALLOWLISTED",
                    "The receiving agent's provider is not on the policy provider allowlist.",
                )
        if (
            policy.external_exposure_rule is ExternalExposureRule.SHAREABLE_ONLY
            and provenance.external_exposure is not ExternalExposure.SHAREABLE
        ):
            return Verdict(
                AuthorizationStatus.UNAUTHORIZED,
                "EXTERNAL_EXPOSURE_BLOCKED",
                "This work is declared internal only and the receiving context may expose content externally.",
            )
        return Verdict(
            AuthorizationStatus.AUTHORIZED,
            "POLICY_AUTHORIZED",
            f"Inheritance policy {policy.policy_id} authorizes this recipient, provider, and exposure level.",
        )

    def _external_job_verdict(self, result: WorkResult) -> Verdict:
        provenance = result.provenance
        external_job: ExternalJobRef | None = provenance.external_job if provenance else None
        if external_job is None:
            return Verdict(
                ExternalJobStatus.NOT_APPLICABLE,
                "NO_EXTERNAL_JOB",
                "No external paid job is attached to this work.",
            )
        if external_job.settlement_state is ExternalJobSettlement.SETTLED:
            return Verdict(
                ExternalJobStatus.SAFE,
                "EXTERNAL_JOB_SETTLED",
                f"External job {external_job.job_id} is recorded as settled on chain {external_job.chain_id}.",
            )
        if external_job.settlement_state is ExternalJobSettlement.RECONCILIATION_REQUIRED:
            return Verdict(
                ExternalJobStatus.RECONCILIATION_REQUIRED,
                "EXTERNAL_JOB_RECONCILIATION_REQUIRED",
                f"External job {external_job.job_id} must be reconciled before its work can be inherited.",
            )
        if external_job.settlement_state is ExternalJobSettlement.UNSETTLED:
            return Verdict(
                ExternalJobStatus.UNSAFE,
                "EXTERNAL_JOB_UNSETTLED",
                f"External job {external_job.job_id} is not settled, so its work is not safe to inherit.",
            )
        return Verdict(
            ExternalJobStatus.RECONCILIATION_REQUIRED,
            "EXTERNAL_JOB_STATE_UNKNOWN",
            f"External job {external_job.job_id} has an unknown settlement state and must be reconciled.",
        )

    @staticmethod
    def _decide(verdicts: HandoffVerdicts) -> tuple[DecisionKind, str, str]:
        """Map five verdicts onto one decision.

        Precedence, and why:

        1. Dependency pending. The effective input is not knowable yet, so no
           other verdict can be trusted for this step.
        2. External job safety. An unsettled or unreconciled paid job must
           block before Delta can report a rerun, because rerunning a paid step
           with an open job is the duplicate-spend risk.
        3. Validity. When no candidate matches the requested work, the honest
           consequence is a rerun, not a policy block.
        4. Trust, then authorization. A matching, valid result that lacks
           provenance or falls outside its inheritance policy is blocked, and
           its content stays out of the approved context.

        Only a fully approving set of verdicts produces ``reuse``. Every other
        decision yields identity and reason codes with no content attached.
        """

        if verdicts.dependency.status is DependencyStatus.PENDING:
            return (
                DecisionKind.PENDING_DEPENDENCY,
                "PENDING_DEPENDENCY_OUTPUT",
                verdicts.dependency.reason,
            )
        if verdicts.external_job.status in {
            ExternalJobStatus.RECONCILIATION_REQUIRED,
            ExternalJobStatus.UNSAFE,
        }:
            return (
                DecisionKind.BLOCKED,
                f"BLOCKED_{verdicts.external_job.reason_code}",
                verdicts.external_job.reason,
            )
        if verdicts.validity.status is ValidityStatus.NO_CANDIDATE:
            return (
                DecisionKind.RERUN,
                "RERUN_NO_CANDIDATE_WORK",
                verdicts.validity.reason,
            )
        if verdicts.validity.status is not ValidityStatus.VALID:
            return (
                DecisionKind.RERUN,
                f"RERUN_{verdicts.validity.reason_code}",
                verdicts.validity.reason,
            )
        if verdicts.trust.status is not TrustStatus.TRUSTED:
            return (
                DecisionKind.BLOCKED,
                f"BLOCKED_{verdicts.trust.reason_code}",
                verdicts.trust.reason,
            )
        if verdicts.authorization.status is not AuthorizationStatus.AUTHORIZED:
            return (
                DecisionKind.BLOCKED,
                f"BLOCKED_{verdicts.authorization.reason_code}",
                verdicts.authorization.reason,
            )
        return (
            DecisionKind.REUSE,
            "REUSE_APPROVED_BY_POLICY",
            "The result is valid, trusted, authorized, dependency-safe, and externally safe.",
        )

    # -- outputs ------------------------------------------------------------

    def _build_approved_context(
        self,
        handoff_id: str,
        request: HandoffRequest,
        candidates: Sequence[HandoffCandidate],
    ) -> ApprovedContext:
        items: list[ApprovedWorkItem] = []
        blocked: list[BlockedWorkNotice] = []
        for candidate in candidates:
            decision = candidate.decision
            if not decision.approved:
                blocked.append(
                    BlockedWorkNotice(
                        step_id=decision.step_id,
                        decision=decision.decision,
                        reason_code=decision.reason_code,
                    )
                )
                continue
            result = candidate.result
            provenance = result.provenance if result else None
            if result is None or provenance is None:
                raise HandoffPolicyError("approved candidate lost its result or provenance")
            items.append(
                ApprovedWorkItem(
                    step_id=decision.step_id,
                    work_category=provenance.work_category,
                    output=result.output,
                    output_signature=result.output_signature,
                    source_agent_id=provenance.source_agent_id,
                    source_session_id=provenance.source_session_id,
                    decision=decision,
                    artifact=result.artifact,
                )
            )
        return ApprovedContext(
            handoff_id=handoff_id,
            scope=request.scope,
            recipient=request.recipient,
            items=tuple(items),
            blocked=tuple(blocked),
        )

    def _build_receipt(
        self,
        handoff_id: str,
        request: HandoffRequest,
        candidates: Sequence[HandoffCandidate],
        created_at: datetime,
    ) -> ReuseReceipt:
        entries = tuple(
            ReuseReceiptEntry.from_decision(candidate.decision) for candidate in candidates
        )
        counts = _decision_counts(entry.decision for entry in entries)
        cost, estimate_status = _aggregate_cost(entries)
        summary = _receipt_summary(counts, cost, estimate_status)
        receipt_id = _digest(
            {
                "handoff_id": handoff_id,
                "entries": [entry.payload() for entry in entries],
                "counts": counts,
                "estimate_status": estimate_status,
            },
            "receipt",
        )
        return ReuseReceipt(
            receipt_id=receipt_id,
            handoff_id=handoff_id,
            scope=request.scope,
            workflow_id=request.workflow.id,
            recipient=request.recipient,
            entries=entries,
            counts=counts,
            estimated_additional_service_cost=cost,
            estimate_status=estimate_status,
            summary=summary,
            created_at=created_at,
        )

    @staticmethod
    def _handoff_id(request: HandoffRequest, candidates: Sequence[HandoffCandidate]) -> str:
        return _digest(
            {
                "scope": {
                    "tenant_id": request.scope.tenant_id,
                    "project_id": request.scope.project_id,
                },
                "workflow_id": request.workflow.id,
                "workflow_version": request.workflow.version,
                "recipient": {
                    "agent_id": request.recipient.agent_id,
                    "session_id": request.recipient.session_id,
                    "provider_id": request.recipient.provider_id,
                },
                "policies": request.policies.identity_payload(),
                "decisions": [candidate.decision.payload() for candidate in candidates],
            },
            "handoff",
        )

    @staticmethod
    def _record_key(request: HandoffRequest, step_id: str, signature: str) -> str:
        return _digest(
            {
                "scope": {
                    "tenant_id": request.scope.tenant_id,
                    "project_id": request.scope.project_id,
                },
                "workflow_id": request.workflow.id,
                "step_id": step_id,
                "input_signature": signature,
            },
            "work_result",
        )


def _completed_after(candidate: WorkResult, existing: WorkResult) -> bool:
    if candidate.completed_at is None:
        return False
    if existing.completed_at is None:
        return True
    if candidate.completed_at != existing.completed_at:
        return candidate.completed_at > existing.completed_at
    return candidate.output_signature > existing.output_signature


def _aggregate_cost(entries: Sequence[ReuseReceiptEntry]) -> tuple[CostEstimate | None, str]:
    """Aggregate estimated additional service cost for work that must still run."""

    chargeable = [
        entry
        for entry in entries
        if entry.decision in {DecisionKind.RERUN, DecisionKind.PENDING_DEPENDENCY}
    ]
    if not chargeable:
        return CostEstimate("0", source="delta-handoff-gate"), "known"
    estimates = [entry.estimated_cost for entry in chargeable]
    if any(estimate is None or estimate.amount is None for estimate in estimates):
        return None, "unknown"
    known = [estimate for estimate in estimates if estimate is not None and estimate.amount is not None]
    currencies = {estimate.currency for estimate in known}
    if len(currencies) > 1:
        return None, "unknown"
    total = sum((Decimal(str(estimate.amount)) for estimate in known), Decimal("0"))
    return (
        CostEstimate(
            format(total.normalize(), "f"),
            currency=currencies.pop(),
            source="delta-handoff-gate",
        ),
        "known",
    )


def _receipt_summary(
    counts: Mapping[str, int],
    cost: CostEstimate | None,
    estimate_status: str,
) -> str:
    inherited = counts[DecisionKind.REUSE.value]
    blocked = counts[DecisionKind.BLOCKED.value]
    rerun = counts[DecisionKind.RERUN.value]
    waiting = counts[DecisionKind.PENDING_DEPENDENCY.value]
    if estimate_status == "known" and cost is not None:
        cost_text = f"estimated additional service cost {cost.amount} {cost.currency}"
    else:
        cost_text = "estimated additional service cost unknown"
    return (
        f"{inherited} inherited, {blocked} withheld by policy, {rerun} to run again, "
        f"{waiting} waiting on a dependency; {cost_text}."
    )


__all__ = [
    "ApprovedContext",
    "ApprovedWorkItem",
    "AuthorizationStatus",
    "BlockedWorkNotice",
    "DependencyStatus",
    "ExternalExposureRule",
    "ExternalJobStatus",
    "HandoffCandidate",
    "HandoffDecision",
    "HandoffEvaluation",
    "HandoffGate",
    "HandoffPolicyError",
    "HandoffRecord",
    "HandoffRequest",
    "HandoffVerdicts",
    "HANDOFF_RECORD_VERSION",
    "InheritancePolicy",
    "PolicySet",
    "ProviderRule",
    "REUSE_RECEIPT_VERSION",
    "ReuseReceipt",
    "ReuseReceiptEntry",
    "TrustStatus",
    "ValidityStatus",
    "Verdict",
    "WorkEvidence",
]
