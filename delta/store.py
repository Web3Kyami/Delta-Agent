"""Sibyl-backed persistence for Delta's durable execution records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from .core import (
    ArtifactReference,
    CostEstimate,
    DeltaValidationError,
    ExecutionAttempt,
    ExecutionEvent,
    ExternalExposure,
    ExternalJobRef,
    ExternalJobSettlement,
    RevisionPlan,
    Scope,
    StepDecision,
    WorkProvenance,
    WorkResult,
    canonical_json,
)


class SibylUnavailable(RuntimeError):
    """Raised when the optional Sibyl client is not installed."""


class SibylPersistenceError(RuntimeError):
    """Raised when Delta cannot safely persist or decode a Sibyl record."""


class SibylScopeError(SibylPersistenceError):
    """Raised when a record belongs to a different Delta scope."""


WORK_CATEGORY = "delta.work_result.v1"
ATTEMPT_CATEGORY = "delta.execution_attempt.v1"
PLAN_CATEGORY = "delta.revision_plan.v1"
HANDOFF_CATEGORY = "delta.handoff_record.v1"
RECEIPT_CATEGORY = "delta.reuse_receipt.v1"
ARTIFACT_REFERENCE_PREFIX = "delta/artifact/v1"
EVENT_RECORD_TYPE = "delta.execution_event.v1"
DEFAULT_MAX_INLINE_RECORD_BYTES = 64 * 1024


def _scope_payload(scope: Scope) -> dict[str, str]:
    return {"tenant_id": scope.tenant_id, "project_id": scope.project_id}


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _require_timestamp(value: str | None, label: str) -> datetime:
    parsed = _parse_timestamp(value)
    if parsed is None:
        raise SibylPersistenceError(f"persisted record is missing {label}")
    return parsed


def _cost_payload(cost: CostEstimate | None) -> dict[str, Any] | None:
    if cost is None:
        return None
    return {
        "amount": cost.amount,
        "currency": cost.currency,
        "source": cost.source,
        "quoted_at": _timestamp(cost.quoted_at),
    }


def _cost_from_payload(payload: dict[str, Any] | None) -> CostEstimate | None:
    if payload is None:
        return None
    return CostEstimate(
        amount=payload.get("amount"),
        currency=payload["currency"],
        source=payload["source"],
        quoted_at=_parse_timestamp(payload.get("quoted_at")),
    )


def _artifact_payload(artifact: ArtifactReference) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "content_hash": artifact.content_hash,
        "media_type": artifact.media_type,
        "byte_size": artifact.byte_size,
        "uri": artifact.uri,
        "available": artifact.available,
    }


def _artifact_from_payload(payload: dict[str, Any] | None) -> ArtifactReference | None:
    if payload is None:
        return None
    return ArtifactReference(
        artifact_id=payload["artifact_id"],
        content_hash=payload["content_hash"],
        media_type=payload["media_type"],
        byte_size=payload["byte_size"],
        uri=payload.get("uri"),
        available=payload["available"],
    )


def _external_job_payload(job: ExternalJobRef | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "provider_id": job.provider_id,
        "job_id": job.job_id,
        "chain_id": job.chain_id,
        "settlement_state": job.settlement_state.value,
        "transaction_hash": job.transaction_hash,
    }


def _external_job_from_payload(payload: dict[str, Any] | None) -> ExternalJobRef | None:
    if payload is None:
        return None
    return ExternalJobRef(
        provider_id=payload["provider_id"],
        job_id=payload["job_id"],
        chain_id=payload["chain_id"],
        settlement_state=ExternalJobSettlement(payload["settlement_state"]),
        transaction_hash=payload.get("transaction_hash"),
    )


def _provenance_payload(provenance: WorkProvenance | None) -> dict[str, Any] | None:
    if provenance is None:
        return None
    return {
        "record_version": "1",
        "source_agent_id": provenance.source_agent_id,
        "source_session_id": provenance.source_session_id,
        "source_provider_id": provenance.source_provider_id,
        "work_category": provenance.work_category,
        "external_exposure": provenance.external_exposure.value,
        "external_job": _external_job_payload(provenance.external_job),
        "recorded_at": _timestamp(provenance.recorded_at),
    }


def _provenance_from_payload(payload: dict[str, Any] | None) -> WorkProvenance | None:
    """Decode provenance. Unknown declared values are rejected, never guessed.

    A record written before provenance existed decodes to ``None``, which the
    handoff gate treats as untrusted rather than silently authorized.
    """

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise SibylPersistenceError("persisted provenance is not an object")
    try:
        exposure = ExternalExposure(payload["external_exposure"])
    except (KeyError, ValueError) as error:
        raise SibylPersistenceError(
            "persisted provenance has an unknown external exposure declaration"
        ) from error
    try:
        return WorkProvenance(
            source_agent_id=payload["source_agent_id"],
            source_session_id=payload["source_session_id"],
            source_provider_id=payload["source_provider_id"],
            work_category=payload["work_category"],
            external_exposure=exposure,
            external_job=_external_job_from_payload(payload.get("external_job")),
            recorded_at=_parse_timestamp(payload.get("recorded_at")),
        )
    except KeyError as error:
        raise SibylPersistenceError("persisted provenance is missing a required field") from error


def _key(kind: str, scope: Scope, **parts: str) -> str:
    identity = {"kind": kind, "scope": _scope_payload(scope), "parts": parts}
    suffix = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    return f"delta/{kind}/v1/{suffix}"


@dataclass(frozen=True)
class CorruptWorkRecord:
    """A persisted work record that could not be decoded into a `WorkResult`.

    Delta surfaces the anomaly instead of dropping the record silently, so the
    handoff gate can report an explicit untrusted verdict rather than reporting
    that no candidate work exists.
    """

    workflow_id: str | None
    step_id: str | None
    input_signature: str | None
    reason: str


class SibylStore:
    """Persist Delta state through Sibyl's documented tier APIs.

    Work, attempts, and plans use WARM entities. Active attempt heads use HOT
    state. Transition events use the COLD journal. Artifact bytes are never
    accepted here. Only REFERENCE metadata and durable artifact URIs are stored.
    """

    def __init__(
        self,
        client: Any,
        scope: Scope,
        *,
        max_inline_record_bytes: int = DEFAULT_MAX_INLINE_RECORD_BYTES,
    ) -> None:
        if max_inline_record_bytes <= 0:
            raise ValueError("max_inline_record_bytes must be positive")
        self.client = client
        self.scope = scope
        self.max_inline_record_bytes = max_inline_record_bytes
        set_tenant = getattr(client, "set_tenant", None)
        if callable(set_tenant):
            set_tenant(scope.tenant_id)
        try:
            from sibyl_memory_client import NotFoundError
        except ImportError:
            NotFoundError = type("NotFoundError", (Exception,), {})
        self._not_found_error = NotFoundError

    @classmethod
    def local(
        cls,
        path: str | Path,
        scope: Scope,
        *,
        tier: str = "free",
        max_inline_record_bytes: int = DEFAULT_MAX_INLINE_RECORD_BYTES,
    ) -> "SibylStore":
        try:
            from sibyl_memory_client import MemoryClient
        except ImportError as error:
            raise SibylUnavailable(
                "Sibyl is unavailable. Install sibyl-memory-client before using SibylStore.local()."
            ) from error
        client = MemoryClient.local(path, tenant_id=scope.tenant_id, tier=tier)
        return cls(client, scope, max_inline_record_bytes=max_inline_record_bytes)

    def _assert_scope(self, scope: Scope) -> None:
        if scope != self.scope:
            raise SibylScopeError("record scope does not match the store scope")

    def _get_entity(self, category: str, name: str) -> dict[str, Any] | None:
        try:
            return self.client.get_entity(category, name)
        except self._not_found_error:
            return None

    def _save_entity(
        self,
        category: str,
        name: str,
        payload: dict[str, Any],
        *,
        status: str,
    ) -> None:
        encoded_size = len(canonical_json(payload).encode("utf-8"))
        if encoded_size > self.max_inline_record_bytes:
            raise SibylPersistenceError(
                "record is too large for inline Sibyl storage; persist artifact bytes externally and store only its reference"
            )
        self.client.set_entity(category, name, payload, status=status)

    def save_work_result(self, result: WorkResult) -> None:
        self._assert_scope(result.scope)
        payload = {
            "record_type": "delta.work_result.v1",
            "scope": _scope_payload(result.scope),
            "workflow_id": result.workflow_id,
            "step_id": result.step_id,
            "implementation_id": result.implementation_id,
            "input_signature": result.input_signature,
            "output_signature": result.output_signature,
            "output": result.output,
            "completed_at": _timestamp(result.completed_at),
            "fresh_until": _timestamp(result.fresh_until),
            "successful_attempt_id": result.successful_attempt_id,
            "artifact": _artifact_payload(result.artifact) if result.artifact else None,
            "status": result.status,
            "provenance": _provenance_payload(result.provenance),
        }
        name = _key(
            "work_result",
            result.scope,
            workflow_id=result.workflow_id,
            step_id=result.step_id,
            input_signature=result.input_signature,
        )
        self._save_entity(WORK_CATEGORY, name, payload, status="completed")

    def get_work_result(
        self,
        workflow_id: str,
        step_id: str,
        input_signature: str,
    ) -> WorkResult | None:
        name = _key(
            "work_result",
            self.scope,
            workflow_id=workflow_id,
            step_id=step_id,
            input_signature=input_signature,
        )
        entity = self._get_entity(WORK_CATEGORY, name)
        if entity is None:
            return None
        payload = entity["body"]
        self._check_payload_scope(payload)
        return WorkResult(
            scope=self.scope,
            workflow_id=payload["workflow_id"],
            step_id=payload["step_id"],
            implementation_id=payload["implementation_id"],
            input_signature=payload["input_signature"],
            output_signature=payload["output_signature"],
            output=payload["output"],
            completed_at=_parse_timestamp(payload["completed_at"]),
            fresh_until=_parse_timestamp(payload.get("fresh_until")),
            successful_attempt_id=payload.get("successful_attempt_id"),
            artifact=_artifact_from_payload(payload.get("artifact")),
            status=payload["status"],
            provenance=_provenance_from_payload(payload.get("provenance")),
        )

    def list_work_results(self, workflow_id: str | None = None) -> list[WorkResult]:
        """Load persisted work results for this tenant and filter by project."""

        results, _ = self.list_work_records(workflow_id)
        return results

    def list_work_records(
        self,
        workflow_id: str | None = None,
    ) -> tuple[list[WorkResult], list[CorruptWorkRecord]]:
        """Load work results and report records that failed to decode.

        A record whose stored output no longer matches its signature cannot
        become a `WorkResult`. Returning it as a corrupt record keeps the
        anomaly visible to the handoff gate instead of making the candidate
        disappear, which would look identical to "no work exists".
        """

        results: list[WorkResult] = []
        corrupt: list[CorruptWorkRecord] = []
        for entity in self.client.list_entities(WORK_CATEGORY, limit=100000):
            payload = entity["body"]
            if workflow_id is not None and payload.get("workflow_id") != workflow_id:
                continue
            payload_scope = payload.get("scope") or {}
            if payload_scope.get("tenant_id") != self.scope.tenant_id:
                continue
            if payload_scope.get("project_id") != self.scope.project_id:
                continue
            self._check_payload_scope(payload)
            try:
                results.append(
                    WorkResult(
                        scope=self.scope,
                        workflow_id=payload["workflow_id"],
                        step_id=payload["step_id"],
                        implementation_id=payload["implementation_id"],
                        input_signature=payload["input_signature"],
                        output_signature=payload["output_signature"],
                        output=payload["output"],
                        completed_at=_require_timestamp(payload["completed_at"], "completed_at"),
                        fresh_until=_parse_timestamp(payload.get("fresh_until")),
                        successful_attempt_id=payload.get("successful_attempt_id"),
                        artifact=_artifact_from_payload(payload.get("artifact")),
                        status=payload["status"],
                        provenance=_provenance_from_payload(payload.get("provenance")),
                    )
                )
            except (DeltaValidationError, SibylPersistenceError, KeyError) as error:
                corrupt.append(
                    CorruptWorkRecord(
                        workflow_id=payload.get("workflow_id"),
                        step_id=payload.get("step_id"),
                        input_signature=payload.get("input_signature"),
                        reason=str(error),
                    )
                )
        return results, corrupt

    def save_attempt(self, attempt: ExecutionAttempt) -> None:
        self._assert_scope(attempt.scope)
        payload = {
            "record_type": "delta.execution_attempt.v1",
            "scope": _scope_payload(attempt.scope),
            "attempt_id": attempt.attempt_id,
            "workflow_id": attempt.workflow_id,
            "step_id": attempt.step_id,
            "status": attempt.status,
            "input_signature": attempt.input_signature,
            "provider_job_id": attempt.provider_job_id,
            "provider_chain_id": attempt.provider_chain_id,
            "error_code": attempt.error_code,
            "provider_id": attempt.provider_id,
            "offering_id": attempt.offering_id,
            "offering_name": attempt.offering_name,
            "requirements_signature": attempt.requirements_signature,
        }
        self._save_entity(
            ATTEMPT_CATEGORY,
            _key("attempt", attempt.scope, attempt_id=attempt.attempt_id),
            payload,
            status=attempt.status,
        )

    def get_attempt(self, attempt_id: str) -> ExecutionAttempt | None:
        entity = self._get_entity(
            ATTEMPT_CATEGORY,
            _key("attempt", self.scope, attempt_id=attempt_id),
        )
        if entity is None:
            return None
        payload = entity["body"]
        self._check_payload_scope(payload)
        return ExecutionAttempt(
            attempt_id=payload["attempt_id"],
            scope=self.scope,
            workflow_id=payload["workflow_id"],
            step_id=payload["step_id"],
            status=payload["status"],
            input_signature=payload["input_signature"],
            provider_job_id=payload.get("provider_job_id"),
            provider_chain_id=payload.get("provider_chain_id"),
            error_code=payload.get("error_code"),
            provider_id=payload.get("provider_id"),
            offering_id=payload.get("offering_id"),
            offering_name=payload.get("offering_name"),
            requirements_signature=payload.get("requirements_signature"),
        )

    def set_active_attempt(self, step_id: str, attempt_id: str | None) -> None:
        key = _key("active_attempt", self.scope, step_id=step_id)
        self.client.set_state(
            key,
            {
                "record_type": "delta.active_attempt.v1",
                "scope": _scope_payload(self.scope),
                "step_id": step_id,
                "attempt_id": attempt_id,
            },
        )

    def get_active_attempt(self, step_id: str) -> str | None:
        key = _key("active_attempt", self.scope, step_id=step_id)
        state = self.client.get_state(key)
        if state is None:
            return None
        payload = state["body"]
        self._check_payload_scope(payload)
        return payload.get("attempt_id")

    def save_plan(self, plan: RevisionPlan) -> None:
        self._assert_scope(plan.scope)
        payload = {
            "record_type": "delta.revision_plan.v1",
            "scope": _scope_payload(plan.scope),
            "plan_id": plan.plan_id,
            "workflow_id": plan.workflow_id,
            "workflow_version": plan.workflow_version,
            "decisions": [
                {
                    "step_id": decision.step_id,
                    "decision": decision.decision.value,
                    "reason_code": decision.reason_code,
                    "reason": decision.reason,
                    "effective_input": decision.effective_input,
                    "input_signature": decision.input_signature,
                    "estimated_cost": _cost_payload(decision.estimated_cost),
                }
                for decision in plan.decisions
            ],
        }
        self._save_entity(
            PLAN_CATEGORY,
            _key("plan", plan.scope, plan_id=plan.plan_id),
            payload,
            status="previewed",
        )

    def get_plan(self, plan_id: str) -> RevisionPlan | None:
        entity = self._get_entity(
            PLAN_CATEGORY,
            _key("plan", self.scope, plan_id=plan_id),
        )
        if entity is None:
            return None
        payload = entity["body"]
        self._check_payload_scope(payload)
        from .core import DecisionKind

        decisions = tuple(
            StepDecision(
                step_id=item["step_id"],
                decision=DecisionKind(item["decision"]),
                reason_code=item["reason_code"],
                reason=item["reason"],
                effective_input=item.get("effective_input"),
                input_signature=item.get("input_signature"),
                estimated_cost=_cost_from_payload(item.get("estimated_cost")),
            )
            for item in payload["decisions"]
        )
        return RevisionPlan(
            plan_id=payload["plan_id"],
            scope=self.scope,
            workflow_id=payload["workflow_id"],
            workflow_version=payload["workflow_version"],
            decisions=decisions,
        )

    def save_artifact_reference(
        self,
        workflow_id: str,
        step_id: str,
        artifact: ArtifactReference,
    ) -> None:
        key = _key(
            "artifact",
            self.scope,
            workflow_id=workflow_id,
            step_id=step_id,
            artifact_id=artifact.artifact_id,
        )
        self.client.set_reference(
            f"{ARTIFACT_REFERENCE_PREFIX}/{key.rsplit('/', 1)[-1]}",
            _artifact_payload(artifact),
            metadata={
                "scope": _scope_payload(self.scope),
                "workflow_id": workflow_id,
                "step_id": step_id,
            },
        )

    def get_artifact_reference(
        self,
        workflow_id: str,
        step_id: str,
        artifact_id: str,
    ) -> ArtifactReference | None:
        key = _key(
            "artifact",
            self.scope,
            workflow_id=workflow_id,
            step_id=step_id,
            artifact_id=artifact_id,
        )
        record = self.client.get_reference(
            f"{ARTIFACT_REFERENCE_PREFIX}/{key.rsplit('/', 1)[-1]}"
        )
        if record is None:
            return None
        metadata = record.get("metadata") or {}
        if metadata.get("scope") != _scope_payload(self.scope):
            raise SibylScopeError("artifact reference scope does not match the store scope")
        body = record["body"]
        if isinstance(body, str):
            body = json.loads(body)
        return _artifact_from_payload(body)

    def save_handoff_record(self, record: Any) -> None:
        """Persist a versioned handoff record with references and safe metadata."""

        self._assert_scope(record.scope)
        payload = {
            "record_type": HANDOFF_CATEGORY,
            "record_version": record.record_version,
            "scope": _scope_payload(record.scope),
            "handoff_id": record.handoff_id,
            "workflow_id": record.workflow_id,
            "workflow_version": record.workflow_version,
            "recipient": {
                "agent_id": record.recipient.agent_id,
                "session_id": record.recipient.session_id,
                "provider_id": record.recipient.provider_id,
            },
            "policy_ids": list(record.policy_ids),
            "created_at": _timestamp(record.created_at),
            "decisions": [decision.payload() for decision in record.decisions],
        }
        self._reject_untrusted_bodies(payload["decisions"])
        self._save_entity(
            HANDOFF_CATEGORY,
            _key("handoff", record.scope, handoff_id=record.handoff_id),
            payload,
            status="evaluated",
        )

    def get_handoff_record(self, handoff_id: str) -> Any | None:
        entity = self._get_entity(
            HANDOFF_CATEGORY,
            _key("handoff", self.scope, handoff_id=handoff_id),
        )
        if entity is None:
            return None
        payload = entity["body"]
        self._check_payload_scope(payload)
        from .handoff import HandoffRecord, _decode_decision
        from .core import AgentPrincipal

        recipient = payload["recipient"]
        return HandoffRecord(
            handoff_id=payload["handoff_id"],
            scope=self.scope,
            workflow_id=payload["workflow_id"],
            workflow_version=payload["workflow_version"],
            recipient=AgentPrincipal(
                agent_id=recipient["agent_id"],
                session_id=recipient["session_id"],
                provider_id=recipient["provider_id"],
            ),
            policy_ids=tuple(payload["policy_ids"]),
            decisions=tuple(_decode_decision(item) for item in payload["decisions"]),
            created_at=_require_timestamp(payload["created_at"], "handoff created_at"),
            record_version=payload["record_version"],
        )

    def save_reuse_receipt(self, receipt: Any) -> None:
        """Persist a versioned Reuse Receipt without copying untrusted output."""

        self._assert_scope(receipt.scope)
        payload = {
            "record_type": RECEIPT_CATEGORY,
            "record_version": receipt.record_version,
            "scope": _scope_payload(receipt.scope),
            "receipt_id": receipt.receipt_id,
            "handoff_id": receipt.handoff_id,
            "workflow_id": receipt.workflow_id,
            "recipient": {
                "agent_id": receipt.recipient.agent_id,
                "session_id": receipt.recipient.session_id,
                "provider_id": receipt.recipient.provider_id,
            },
            "counts": dict(receipt.counts),
            "estimate_status": receipt.estimate_status,
            "estimated_additional_service_cost": _cost_payload(
                receipt.estimated_additional_service_cost
            ),
            "summary": receipt.summary,
            "created_at": _timestamp(receipt.created_at),
            "entries": [entry.payload() for entry in receipt.entries],
        }
        self._reject_untrusted_bodies(payload["entries"])
        self._save_entity(
            RECEIPT_CATEGORY,
            _key("receipt", receipt.scope, receipt_id=receipt.receipt_id),
            payload,
            status="issued",
        )

    def get_reuse_receipt(self, receipt_id: str) -> Any | None:
        entity = self._get_entity(
            RECEIPT_CATEGORY,
            _key("receipt", self.scope, receipt_id=receipt_id),
        )
        if entity is None:
            return None
        payload = entity["body"]
        self._check_payload_scope(payload)
        from .handoff import ReuseReceipt, _decode_receipt_entry
        from .core import AgentPrincipal

        recipient = payload["recipient"]
        return ReuseReceipt(
            receipt_id=payload["receipt_id"],
            handoff_id=payload["handoff_id"],
            scope=self.scope,
            workflow_id=payload["workflow_id"],
            recipient=AgentPrincipal(
                agent_id=recipient["agent_id"],
                session_id=recipient["session_id"],
                provider_id=recipient["provider_id"],
            ),
            entries=tuple(_decode_receipt_entry(item) for item in payload["entries"]),
            counts=dict(payload["counts"]),
            estimated_additional_service_cost=_cost_from_payload(
                payload.get("estimated_additional_service_cost")
            ),
            estimate_status=payload["estimate_status"],
            summary=payload["summary"],
            created_at=_require_timestamp(payload["created_at"], "receipt created_at"),
            record_version=payload["record_version"],
        )

    def list_reuse_receipts(self, handoff_id: str | None = None) -> list[Any]:
        receipts = []
        for entity in self.client.list_entities(RECEIPT_CATEGORY, limit=100000):
            payload = entity["body"]
            if payload.get("scope") != _scope_payload(self.scope):
                continue
            if handoff_id is not None and payload.get("handoff_id") != handoff_id:
                continue
            receipt = self.get_reuse_receipt(payload["receipt_id"])
            if receipt is not None:
                receipts.append(receipt)
        return receipts

    def delete_scope_records(
        self,
        *,
        workflow_ids: set[str] | None = None,
        step_ids: set[str] | None = None,
    ) -> dict[str, int]:
        """Hard-delete this exact scope's entity records through Sibyl.

        Sibyl has no prefix or bulk delete. This method enumerates exact names
        first, filters by the persisted scope, and deletes one name at a time.
        Journal events are append-only and are intentionally retained. Active
        HOT heads are overwritten with ``None`` because Sibyl has no delete
        state operation.
        """

        workflow_ids = workflow_ids or set()
        step_ids = step_ids or set()
        categories = (WORK_CATEGORY, ATTEMPT_CATEGORY, PLAN_CATEGORY, HANDOFF_CATEGORY, RECEIPT_CATEGORY)
        deleted: dict[str, int] = {category: 0 for category in categories}
        target_scope = _scope_payload(self.scope)
        for category in categories:
            for entity in self.client.list_entities(category, limit=100000):
                payload = entity.get("body") or {}
                if payload.get("scope") != target_scope:
                    continue
                if workflow_ids and payload.get("workflow_id") not in workflow_ids:
                    continue
                if step_ids and payload.get("step_id") not in step_ids:
                    continue
                name = entity.get("name")
                if isinstance(name, str) and self.client.delete_entity(category, name):
                    deleted[category] += 1
        return deleted

    def reset_active_heads(self, step_ids: list[str] | tuple[str, ...]) -> None:
        """Clear HOT active-attempt heads for a reset scope."""

        for step_id in step_ids:
            self.set_active_attempt(step_id, None)

    def save_demo_marker(self, scenario_id: str, generation: str, *, initialized: bool = True) -> None:
        """Persist a small scenario initialization marker in Sibyl HOT state."""

        self.client.set_state(
            _key("demo_marker", self.scope, scenario_id=scenario_id),
            {
                "record_type": "delta.demo_marker.v1",
                "scope": _scope_payload(self.scope),
                "scenario_id": scenario_id,
                "generation": generation,
                "initialized": initialized,
            },
        )

    def get_demo_marker(self, scenario_id: str) -> dict[str, Any] | None:
        state = self.client.get_state(_key("demo_marker", self.scope, scenario_id=scenario_id))
        if state is None:
            return None
        payload = state.get("body") or {}
        self._check_payload_scope(payload)
        return payload

    @staticmethod
    def _reject_untrusted_bodies(items: Any) -> None:
        """Refuse to persist an output body inside a handoff or receipt record.

        Handoff and receipt records carry references, signatures, and safe
        metadata. Copying an untrusted output body into them would move blocked
        content into a record that other surfaces are allowed to read.
        """

        forbidden = {"output", "deliverable", "artifact_bytes", "content", "body"}
        stack = [items]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                present = forbidden.intersection(current)
                if present:
                    raise SibylPersistenceError(
                        "handoff records must not contain work output bodies: "
                        + ", ".join(sorted(present))
                    )
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)

    def append_event(self, event: ExecutionEvent) -> str:
        self._assert_scope(event.scope)
        extra = {
            "record_type": EVENT_RECORD_TYPE,
            "scope": _scope_payload(event.scope),
            "event_id": event.event_id,
            "attempt_id": event.attempt_id,
            "reason_code": event.reason_code,
            "state": event.state,
            "detail": event.detail,
            "recorded_at": _timestamp(event.recorded_at),
        }
        return self.client.write_event(
            evaluated={"attempt_id": event.attempt_id, "reason_code": event.reason_code},
            acted={"state": event.state},
            extra=extra,
            ts=_timestamp(event.recorded_at),
        )

    def read_events(
        self,
        attempt_id: str | None = None,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        events = []
        for record in self.client.read_events(limit=limit):
            extra = record.get("extra") or {}
            if extra.get("record_type") != EVENT_RECORD_TYPE:
                continue
            if extra.get("scope") != _scope_payload(self.scope):
                continue
            if attempt_id is not None and extra.get("attempt_id") != attempt_id:
                continue
            events.append(extra)
        return events

    def _check_payload_scope(self, payload: dict[str, Any]) -> None:
        if payload.get("scope") != _scope_payload(self.scope):
            raise SibylScopeError("persisted record scope does not match the store scope")
