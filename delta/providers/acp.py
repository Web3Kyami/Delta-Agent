"""Safe, narrow Virtuals ACP command and lifecycle adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import re
import subprocess
import threading
from typing import Any, Mapping, Sequence

from ..core import (
    ApprovalValidationError,
    ExecutionAttempt,
    ExecutionEvent,
    RevisionPlan,
    SpendApproval,
    canonical_json,
    validate_spend_approval,
)
from ..store import SibylStore


class ACPAdapterError(RuntimeError):
    """Base error for ACP command and response handling."""


class ACPParseError(ACPAdapterError):
    """Raised when a provider response cannot be decoded safely."""


class UnsupportedLifecycle(ACPAdapterError):
    """Raised when an ACP lifecycle state is not recognized."""


class ACPCommandStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PARSE_FAILED = "parse_failed"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ACPCommandResult:
    status: ACPCommandStatus
    args: tuple[str, ...]
    data: Any | None = None
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    error: str | None = None
    external_outcome_ambiguous: bool = False


def redact_text(value: str, secrets: Sequence[str] = ()) -> str:
    """Redact supplied secrets and common credential-shaped JSON fields."""

    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(
        r'(?i)("(?:private[_-]?key|seed(?:[_-]?phrase)?|mnemonic|api[_-]?key|access[_-]?token|secret)"\s*:\s*")[^"]*(")',
        r"\1[REDACTED]\2",
        redacted,
    )
    redacted = re.sub(
        r'(?i)((?:private[_-]?key|seed(?:[_-]?phrase)?|mnemonic|api[_-]?key|access[_-]?token|secret)\s*[=:]\s*)[^,\s]+',
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


class ACPCommandRunner:
    """Run ACP with argument arrays and machine-readable output only."""

    def __init__(self, *, secrets: Sequence[str] = ()) -> None:
        self.secrets = tuple(secrets)

    def run_json(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: float = 30,
        side_effecting: bool = False,
    ) -> ACPCommandResult:
        if not args or any(not isinstance(arg, str) or not arg for arg in args):
            raise ValueError("ACP args must be a non-empty sequence of strings")
        command = tuple(args) if "--json" in args else tuple(args) + ("--json",)
        safe_args = tuple(redact_text(arg, self.secrets) for arg in command)
        try:
            completed = subprocess.run(
                list(command),
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            stdout = redact_text(_partial_output(error.stdout), self.secrets)
            stderr = redact_text(_partial_output(error.stderr), self.secrets)
            return ACPCommandResult(
                status=ACPCommandStatus.TIMEOUT,
                args=safe_args,
                stdout=stdout,
                stderr=stderr,
                error="ACP command timed out",
                external_outcome_ambiguous=side_effecting,
            )
        except OSError as error:
            return ACPCommandResult(
                status=ACPCommandStatus.FAILED,
                args=safe_args,
                error=f"ACP command could not start: {type(error).__name__}",
            )

        stdout = redact_text(completed.stdout, self.secrets)
        stderr = redact_text(completed.stderr, self.secrets)
        if completed.returncode != 0:
            return ACPCommandResult(
                status=ACPCommandStatus.FAILED,
                args=safe_args,
                stdout=stdout,
                stderr=stderr,
                returncode=completed.returncode,
                error="ACP command returned a nonzero exit code",
            )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return ACPCommandResult(
                status=ACPCommandStatus.PARSE_FAILED,
                args=safe_args,
                stdout=stdout,
                stderr=stderr,
                returncode=completed.returncode,
                error="ACP command returned invalid JSON",
                external_outcome_ambiguous=side_effecting,
            )
        if not isinstance(data, (dict, list)):
            return ACPCommandResult(
                status=ACPCommandStatus.PARSE_FAILED,
                args=safe_args,
                stdout=stdout,
                stderr=stderr,
                returncode=completed.returncode,
                error="ACP command returned a JSON scalar where an object or array was required",
                external_outcome_ambiguous=side_effecting,
            )
        return ACPCommandResult(
            status=ACPCommandStatus.SUCCEEDED,
            args=safe_args,
            data=data,
            stdout=stdout,
            stderr=stderr,
            returncode=completed.returncode,
        )


def _partial_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _lifecycle_state(status: str) -> str:
    states = {
        "open": "awaiting_provider",
        "budget_set": "awaiting_approval",
        "funded": "awaiting_provider",
        "submitted": "deliverable_ready",
        "completed": "succeeded",
        "rejected": "rejected",
        "expired": "expired",
    }
    try:
        return states[status.lower()]
    except (KeyError, AttributeError) as error:
        raise UnsupportedLifecycle(f"unsupported ACP lifecycle state: {status!r}") from error


@dataclass(frozen=True)
class ACPJobRecord:
    job_id: str
    provider_id: str | None
    offering_id: str | None
    chain_id: int
    provider_status: str
    delta_state: str
    deliverable: Any | None = None
    transaction_hashes: tuple[str, ...] = ()
    fixture: bool = False
    created_at: datetime | None = None
    requirements_signature: str | None = None


@dataclass(frozen=True)
class ACPBrowseOffering:
    """A normalized offering returned by ACP marketplace browse."""

    offering_id: str
    provider_id: str | None
    name: str
    requirements: Any | None
    deliverable: Any | None
    sla_minutes: int | None
    price_type: str | None
    price_value: Decimal | None
    required_funds: bool | None
    is_hidden: bool | None


@dataclass(frozen=True)
class ACPBrowseAgent:
    """A normalized marketplace agent and its browse offerings."""

    provider_id: str
    name: str
    provider_address: str | None
    role: str | None
    cluster: str | None
    rating: str | None
    chain_ids: tuple[int, ...]
    offerings: tuple[ACPBrowseOffering, ...]


def parse_browse_response(payload: Mapping[str, Any]) -> tuple[ACPBrowseAgent, ...]:
    """Parse the live ACP browse envelope without inferring availability or success."""

    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
        raise ACPParseError("ACP browse response must contain a data array")
    agents: list[ACPBrowseAgent] = []
    for raw_agent in payload["data"]:
        if not isinstance(raw_agent, Mapping):
            raise ACPParseError("ACP browse agent must be an object")
        provider_id = raw_agent.get("id")
        name = raw_agent.get("name")
        if not isinstance(provider_id, str) or not provider_id:
            raise ACPParseError("ACP browse agent is missing provider identity")
        if not isinstance(name, str) or not name:
            raise ACPParseError("ACP browse agent is missing a name")
        wallet_address = raw_agent.get("walletAddress")
        if wallet_address is not None and (not isinstance(wallet_address, str) or not wallet_address):
            raise ACPParseError("ACP browse provider address is malformed")
        chains = raw_agent.get("chains", [])
        if not isinstance(chains, list):
            raise ACPParseError("ACP browse chains must be an array")
        chain_ids: list[int] = []
        for chain in chains:
            if not isinstance(chain, Mapping):
                raise ACPParseError("ACP browse chain must be an object")
            chain_id = chain.get("chainId", chain.get("chain_id"))
            if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
                raise ACPParseError("ACP browse chain ID is malformed")
            chain_ids.append(chain_id)
        raw_offerings = raw_agent.get("offerings", [])
        if not isinstance(raw_offerings, list):
            raise ACPParseError("ACP browse offerings must be an array")
        offerings = tuple(_parse_browse_offering(item, provider_id) for item in raw_offerings)
        agents.append(
            ACPBrowseAgent(
                provider_id=provider_id,
                name=name,
                provider_address=wallet_address,
                role=_optional_text(raw_agent.get("role")),
                cluster=_optional_text(raw_agent.get("cluster")),
                rating=_optional_text(raw_agent.get("rating")),
                chain_ids=tuple(chain_ids),
                offerings=offerings,
            )
        )
    return tuple(agents)


def _parse_browse_offering(payload: Any, provider_id: str) -> ACPBrowseOffering:
    if not isinstance(payload, Mapping):
        raise ACPParseError("ACP browse offering must be an object")
    offering_id = payload.get("id")
    name = payload.get("name")
    if not isinstance(offering_id, str) or not offering_id:
        raise ACPParseError("ACP browse offering is missing offering identity")
    if not isinstance(name, str) or not name:
        raise ACPParseError("ACP browse offering is missing a name")
    offering_provider_id = payload.get("agentId", payload.get("agent_id", provider_id))
    if offering_provider_id is not None and (not isinstance(offering_provider_id, str) or not offering_provider_id):
        raise ACPParseError("ACP browse offering provider identity is malformed")
    sla_minutes = payload.get("slaMinutes", payload.get("sla_minutes"))
    if sla_minutes is not None and (not isinstance(sla_minutes, int) or isinstance(sla_minutes, bool) or sla_minutes <= 0):
        raise ACPParseError("ACP browse SLA is malformed")
    price_value = payload.get("priceValue", payload.get("price_value"))
    parsed_price = None
    if price_value is not None:
        if isinstance(price_value, bool) or not isinstance(price_value, (int, float, str, Decimal)):
            raise ACPParseError("ACP browse price is malformed")
        try:
            parsed_price = Decimal(str(price_value))
        except (InvalidOperation, ValueError) as error:
            raise ACPParseError("ACP browse price is malformed") from error
    for field in ("requiredFunds", "isHidden"):
        value = payload.get(field)
        if value is not None and not isinstance(value, bool):
            raise ACPParseError(f"ACP browse {field} value is malformed")
    return ACPBrowseOffering(
        offering_id=offering_id,
        provider_id=offering_provider_id,
        name=name,
        requirements=payload.get("requirements"),
        deliverable=payload.get("deliverable"),
        sla_minutes=sla_minutes,
        price_type=_optional_text(payload.get("priceType", payload.get("price_type"))),
        price_value=parsed_price,
        required_funds=payload.get("requiredFunds"),
        is_hidden=payload.get("isHidden"),
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ACPParseError("ACP browse text metadata is malformed")
    return str(value)


class ReconciliationOutcome(str, Enum):
    ATTACH = "attach"
    MANUAL = "manual"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ReconciliationDecision:
    outcome: ReconciliationOutcome
    record: ACPJobRecord | None
    reason: str


class FundingOutcome(str, Enum):
    VERIFIED_FUNDED = "verified_funded"
    NOT_FUNDED = "not_funded"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ChainEvidence:
    status: str
    transaction_hash: str | None = None


@dataclass(frozen=True)
class FundingReconciliation:
    outcome: FundingOutcome
    reason: str


def parse_chain_evidence(payload: Mapping[str, Any] | None) -> ChainEvidence | None:
    """Parse a chain lookup result without inferring success from a hash alone."""

    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ACPParseError("chain evidence must be an object")
    status = payload.get("status")
    transaction_hash = payload.get("transactionHash", payload.get("transaction_hash"))
    if status not in {"succeeded", "failed", "unknown"}:
        raise ACPParseError("chain evidence has an unsupported status")
    if transaction_hash is not None and (not isinstance(transaction_hash, str) or not transaction_hash):
        raise ACPParseError("chain transaction identity is malformed")
    if status == "succeeded" and transaction_hash is None:
        raise ACPParseError("successful chain evidence is missing transaction identity")
    return ChainEvidence(status, transaction_hash)


def parse_job_record(payload: Mapping[str, Any]) -> ACPJobRecord:
    """Parse a provider response without treating fixture data as live evidence."""

    if not isinstance(payload, Mapping):
        raise ACPParseError("ACP job response must be an object")
    job_id = payload.get("jobId", payload.get("job_id"))
    status = payload.get("status", payload.get("state"))
    chain_id = payload.get("chainId", payload.get("chain_id"))
    if not isinstance(job_id, str) or not job_id:
        raise ACPParseError("ACP job response is missing job identity")
    if not isinstance(status, str):
        raise ACPParseError("ACP job response is missing lifecycle status")
    if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
        raise ACPParseError("ACP job response is missing a valid chain ID")
    provider_id = payload.get("providerId", payload.get("provider_id"))
    offering_id = payload.get("offeringId", payload.get("offering_id"))
    if provider_id is not None and (not isinstance(provider_id, str) or not provider_id):
        raise ACPParseError("ACP provider identity is malformed")
    if offering_id is not None and (not isinstance(offering_id, str) or not offering_id):
        raise ACPParseError("ACP offering identity is malformed")
    created_at = _parse_created_at(payload.get("createdAt", payload.get("created_at")))
    requirements_signature = payload.get("requirementsSignature", payload.get("requirements_signature"))
    if requirements_signature is not None and (not isinstance(requirements_signature, str) or not requirements_signature):
        raise ACPParseError("ACP requirements signature is malformed")
    tx_hashes = payload.get("transactionHashes", payload.get("transaction_hashes"))
    if tx_hashes is None and "transactionHash" in payload:
        tx_hashes = [payload["transactionHash"]]
    if tx_hashes is None:
        tx_hashes = []
    if not isinstance(tx_hashes, list) or any(not isinstance(item, str) for item in tx_hashes):
        raise ACPParseError("ACP transaction hash metadata is malformed")
    return ACPJobRecord(
        job_id=job_id,
        provider_id=provider_id,
        offering_id=offering_id,
        chain_id=chain_id,
        provider_status=status,
        delta_state=_lifecycle_state(status),
        deliverable=payload.get("deliverable"),
        transaction_hashes=tuple(tx_hashes),
        fixture=payload.get("fixture") is True,
        created_at=created_at,
        requirements_signature=requirements_signature,
    )


def _parse_created_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ACPParseError("ACP creation time is malformed")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ACPParseError("ACP creation time is malformed") from error


def match_reconciliation_candidates(
    candidates: Sequence[ACPJobRecord],
    *,
    provider_id: str,
    offering_id: str,
    chain_id: int,
    requirements_signature: str | None = None,
    expected_transaction_hashes: Sequence[str] = (),
) -> ReconciliationDecision:
    """Attach only one candidate with sufficient stable identity evidence."""

    if not candidates:
        return ReconciliationDecision(ReconciliationOutcome.MANUAL, None, "no plausible ACP job matched the persisted intent")
    mismatches = []
    plausible = []
    expected_transactions = set(expected_transaction_hashes)
    for candidate in candidates:
        if candidate.chain_id != chain_id:
            mismatches.append("chain")
            continue
        if candidate.provider_id is not None and candidate.provider_id != provider_id:
            mismatches.append("provider")
            continue
        if candidate.offering_id is not None and candidate.offering_id != offering_id:
            mismatches.append("offering")
            continue
        if requirements_signature is not None and candidate.requirements_signature not in {None, requirements_signature}:
            mismatches.append("requirements")
            continue
        if expected_transactions and candidate.transaction_hashes and not expected_transactions.intersection(candidate.transaction_hashes):
            mismatches.append("transaction")
            continue
        plausible.append(candidate)
    if not plausible:
        detail = ", ".join(sorted(set(mismatches))) or "identity"
        return ReconciliationDecision(ReconciliationOutcome.BLOCKED, None, f"ACP candidates conflict with persisted {detail} identity")
    if len(plausible) > 1:
        return ReconciliationDecision(ReconciliationOutcome.MANUAL, None, "multiple ACP jobs match the persisted intent")
    candidate = plausible[0]
    if candidate.provider_id is None or candidate.offering_id is None:
        return ReconciliationDecision(ReconciliationOutcome.MANUAL, None, "ACP response lacks provider or offering identity needed for safe attachment")
    return ReconciliationDecision(ReconciliationOutcome.ATTACH, candidate, "one ACP job matches provider, offering, chain, and available intent evidence")


def reconcile_funding(record: ACPJobRecord, chain: ChainEvidence | None) -> FundingReconciliation:
    """Require consistent provider and chain evidence before funding is trusted."""

    provider_not_funded = record.provider_status.lower() in {"open", "budget_set", "rejected", "expired"}
    provider_funded = record.provider_status.lower() in {"funded", "submitted", "completed"}
    chain_succeeded = chain is not None and chain.status == "succeeded" and bool(chain.transaction_hash)
    chain_failed = chain is not None and chain.status == "failed"
    if provider_funded and chain_succeeded:
        return FundingReconciliation(FundingOutcome.VERIFIED_FUNDED, "provider state and chain evidence agree")
    if provider_funded and chain_failed:
        return FundingReconciliation(FundingOutcome.BLOCKED, "provider reports funding but chain evidence reports failure")
    if provider_funded:
        return FundingReconciliation(FundingOutcome.AMBIGUOUS, "provider reports funding without verified chain success")
    if provider_not_funded and chain_succeeded:
        return FundingReconciliation(FundingOutcome.BLOCKED, "chain evidence reports success while provider state reports no funding")
    if provider_not_funded:
        return FundingReconciliation(FundingOutcome.NOT_FUNDED, "provider state reports that funding is not present")
    return FundingReconciliation(FundingOutcome.AMBIGUOUS, "provider state is not sufficient to determine funding")


def _spend_key(plan: RevisionPlan) -> str:
    identity = f"{plan.scope.tenant_id}:{plan.scope.project_id}:{plan.plan_id}".encode()
    return "delta/spend/v1/" + hashlib.sha256(identity).hexdigest()


_ACP_ACTION_LOCK = threading.RLock()
_ACTIVE_ATTEMPT_STATES = frozenset(
    {"planned", "submitting", "active", "awaiting_provider", "ambiguous", "reconciliation_required"}
)


class ACPSpendLedger:
    """Persist cumulative service-spend reservations in Sibyl HOT state."""

    _lock = threading.RLock()

    def __init__(self, store: SibylStore) -> None:
        self.store = store

    def committed(self, plan: RevisionPlan) -> str:
        state = self.store.client.get_state(_spend_key(plan))
        return (state or {}).get("body", {}).get("committed", "0")

    def reserve(
        self,
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
        reservation_id: str,
        now=None,
    ) -> None:
        validate_spend_approval(
            approval,
            plan,
            step_id=step_id,
            provider_id=provider_id,
            offering_id=offering_id,
            chain_id=chain_id,
            action=action,
            amount=amount,
            currency=currency,
            now=now,
        )
        try:
            requested = Decimal(amount)
            total_cap = Decimal(approval.max_total_service_spend)
        except (InvalidOperation, ValueError) as error:
            raise ApprovalValidationError("spend amount must be a decimal string") from error
        with self._lock:
            state = self.store.client.get_state(_spend_key(plan))
            body = (state or {}).get("body", {})
            if body and (
                body.get("plan_id") != plan.plan_id
                or body.get("currency") != currency
                or body.get("record_type") != "delta.spend_ledger.v1"
                or body.get("scope") != {"tenant_id": plan.scope.tenant_id, "project_id": plan.scope.project_id}
            ):
                raise ApprovalValidationError("persisted spend ledger identity does not match this plan")
            entries = body.get("entries", [])
            if any(entry.get("reservation_id") == reservation_id for entry in entries):
                return
            committed = Decimal(body.get("committed", "0"))
            if committed + requested > total_cap:
                raise ApprovalValidationError("cumulative committed service spend exceeds plan cap")
            entries = [*entries, {"reservation_id": reservation_id, "amount": amount, "currency": currency}]
            self.store.client.set_state(
                _spend_key(plan),
                {"record_type": "delta.spend_ledger.v1", "scope": {"tenant_id": plan.scope.tenant_id, "project_id": plan.scope.project_id}, "plan_id": plan.plan_id, "currency": currency, "committed": format(committed + requested, "f"), "entries": entries},
            )


class ACPAdapter:
    """Provider-neutral ACP operations with no implicit live or spending behavior."""

    def __init__(
        self,
        store: SibylStore,
        runner: ACPCommandRunner,
        *,
        ledger: ACPSpendLedger | None = None,
    ) -> None:
        self.store = store
        self.runner = runner
        self.ledger = ledger or ACPSpendLedger(store)

    def browse(
        self,
        query: str,
        *,
        top_k: int = 10,
        chain_id: int | None = None,
    ) -> ACPCommandResult:
        args = ["acp", "browse", query, "--top-k", str(top_k), "--online", "online", "--sort-by", "successRate"]
        if chain_id is not None:
            args.extend(["--chain-ids", str(chain_id)])
        return self.runner.run_json(args)

    def parse_browse_response(self, response: ACPCommandResult) -> tuple[ACPBrowseAgent, ...]:
        """Validate and normalize a successful ACP browse response."""

        if response.status != ACPCommandStatus.SUCCEEDED or not isinstance(response.data, Mapping):
            raise ACPAdapterError("ACP browse response is not a successful JSON object")
        return parse_browse_response(response.data)

    def job_history(self, job_id: str | None = None) -> ACPCommandResult:
        args = ["acp", "job", "history"]
        if job_id is not None:
            args.extend(["--job-id", job_id])
        return self.runner.run_json(args)

    def watch_job(self, job_id: str) -> ACPCommandResult:
        return self.runner.run_json(["acp", "job", "watch", "--job-id", job_id])

    def reconcile_known_job(self, job_id: str) -> ACPJobRecord:
        """Read and map the current provider record before any replacement."""

        return self.parse_response(self.job_history(job_id))

    def reconcile_attempt(self, step_id: str) -> ACPJobRecord:
        """Recover a persisted active attempt and reconcile its provider job."""

        attempt_id = self.store.get_active_attempt(step_id)
        if attempt_id is None:
            raise ACPAdapterError("no active ACP attempt is persisted for this step")
        attempt = self.store.get_attempt(attempt_id)
        if attempt is None or attempt.provider_job_id is None:
            raise ACPAdapterError("persisted ACP attempt has no provider job identity")
        record = self.reconcile_known_job(attempt.provider_job_id)
        if attempt.provider_chain_id is not None and record.chain_id != attempt.provider_chain_id:
            self._persist_reconciliation(attempt, "ambiguous", record, now=datetime.now(timezone.utc))
            raise ACPAdapterError("reconciled ACP job chain does not match persisted attempt")
        status = {
            "succeeded": "succeeded",
            "rejected": "rejected",
            "expired": "expired",
        }.get(record.delta_state, "active")
        self._persist_reconciliation(attempt, status, record, now=datetime.now(timezone.utc))
        return record

    def get_deliverable(self, job_id: str) -> Any:
        record = self.reconcile_known_job(job_id)
        if record.deliverable is None:
            raise ACPAdapterError("ACP job has no deliverable to retrieve")
        return record.deliverable

    def parse_response(self, response: ACPCommandResult) -> ACPJobRecord:
        if response.status != ACPCommandStatus.SUCCEEDED or not isinstance(response.data, Mapping):
            raise ACPAdapterError("ACP response is not a successful JSON object")
        return parse_job_record(response.data)

    def create_job(
        self,
        plan: RevisionPlan,
        approval: SpendApproval,
        *,
        step_id: str,
        input_signature: str,
        provider_id: str,
        offering_id: str,
        offering_name: str,
        requirements: Mapping[str, Any],
        chain_id: int,
        amount: str,
        attempt_id: str,
        now=None,
    ) -> ACPCommandResult:
        args = [
            "acp", "client", "create-job",
            "--provider", provider_id,
            "--offering-name", offering_name,
            "--requirements", canonical_requirements(requirements),
            "--chain-id", str(chain_id),
        ]
        with _ACP_ACTION_LOCK:
            self._reject_duplicate_active_attempt(step_id, input_signature)
            self._authorize(approval, plan, step_id, provider_id, offering_id, chain_id, "create_job", amount, now)
            self.ledger.reserve(approval, plan, step_id=step_id, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action="create_job", amount=amount, currency=approval.currency, reservation_id=attempt_id, now=now)
            self._persist_intent(plan, step_id, input_signature, attempt_id, "submitting", now=now)
        response = self.runner.run_json(args, side_effecting=True)
        if response.status == ACPCommandStatus.SUCCEEDED:
            try:
                record = self.parse_response(response)
            except ACPAdapterError:
                self._mark_attempt(plan, step_id, attempt_id, "ambiguous", now=now)
                return replace(response, status=ACPCommandStatus.AMBIGUOUS, external_outcome_ambiguous=True)
            if not self._create_response_matches_request(record, provider_id, offering_id, chain_id):
                self._mark_attempt(plan, step_id, attempt_id, "ambiguous", now=now)
                return replace(response, status=ACPCommandStatus.AMBIGUOUS, external_outcome_ambiguous=True, error="ACP create response identity did not match the requested scope")
            self._mark_attempt(plan, step_id, attempt_id, "active", provider_job_id=record.job_id, provider_chain_id=record.chain_id, now=now)
        elif response.external_outcome_ambiguous or response.status in {ACPCommandStatus.TIMEOUT, ACPCommandStatus.PARSE_FAILED, ACPCommandStatus.AMBIGUOUS}:
            self._mark_attempt(plan, step_id, attempt_id, "ambiguous", now=now)
        else:
            self._mark_attempt(plan, step_id, attempt_id, "failed", now=now)
        return response

    def fund_job(
        self,
        plan: RevisionPlan,
        approval: SpendApproval,
        *,
        step_id: str,
        input_signature: str,
        provider_id: str,
        offering_id: str,
        chain_id: int,
        job_id: str,
        amount: str,
        attempt_id: str,
        now=None,
    ) -> ACPCommandResult:
        return self._paid_action(
            plan, approval, step_id=step_id, input_signature=input_signature, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action="fund", amount=amount, attempt_id=attempt_id, args=["acp", "client", "fund", "--job-id", job_id, "--amount", amount], now=now,
        )

    def complete_job(
        self,
        plan: RevisionPlan,
        approval: SpendApproval,
        *,
        step_id: str,
        input_signature: str,
        provider_id: str,
        offering_id: str,
        chain_id: int,
        job_id: str,
        amount: str,
        reason: str,
        attempt_id: str,
        now=None,
    ) -> ACPCommandResult:
        return self._paid_action(
            plan, approval, step_id=step_id, input_signature=input_signature, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action="complete", amount=amount, attempt_id=attempt_id, args=["acp", "client", "complete", "--job-id", job_id, "--reason", reason], now=now,
        )

    def reject_job(
        self,
        plan: RevisionPlan,
        approval: SpendApproval,
        *,
        step_id: str,
        input_signature: str,
        provider_id: str,
        offering_id: str,
        chain_id: int,
        job_id: str,
        reason: str,
        attempt_id: str,
        now=None,
    ) -> ACPCommandResult:
        return self._paid_action(
            plan, approval, step_id=step_id, input_signature=input_signature, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action="reject", amount="0", attempt_id=attempt_id, args=["acp", "client", "reject", "--job-id", job_id, "--reason", reason], now=now,
        )

    def _paid_action(self, plan, approval, *, step_id, input_signature, provider_id, offering_id, chain_id, action, amount, attempt_id, args, now):
        with _ACP_ACTION_LOCK:
            self._reject_duplicate_active_attempt(
                step_id,
                input_signature,
                statuses={"submitting", "ambiguous", "reconciliation_required"},
            )
            self._authorize(approval, plan, step_id, provider_id, offering_id, chain_id, action, amount, now)
            self.ledger.reserve(approval, plan, step_id=step_id, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action=action, amount=amount, currency=approval.currency, reservation_id=f"{attempt_id}:{action}", now=now)
            self._persist_intent(plan, step_id, input_signature, attempt_id, "submitting", now=now)
        response = self.runner.run_json(args, side_effecting=True)
        if response.status == ACPCommandStatus.FAILED:
            status = "failed"
        elif response.status in {ACPCommandStatus.TIMEOUT, ACPCommandStatus.PARSE_FAILED, ACPCommandStatus.AMBIGUOUS} or response.external_outcome_ambiguous:
            status = "ambiguous"
        else:
            status = "active"
        self._mark_attempt(plan, step_id, attempt_id, status, now=now)
        return response

    @staticmethod
    def _authorize(approval, plan, step_id, provider_id, offering_id, chain_id, action, amount, now):
        validate_spend_approval(
            approval,
            plan,
            step_id=step_id,
            provider_id=provider_id,
            offering_id=offering_id,
            chain_id=chain_id,
            action=action,
            amount=amount,
            currency=approval.currency,
            now=now,
        )

    @staticmethod
    def _create_response_matches_request(record: ACPJobRecord, provider_id: str, offering_id: str, chain_id: int) -> bool:
        return (
            record.chain_id == chain_id
            and (record.provider_id is None or record.provider_id == provider_id)
            and (record.offering_id is None or record.offering_id == offering_id)
        )

    def _reject_duplicate_active_attempt(self, step_id: str, input_signature: str, statuses=None) -> None:
        active_id = self.store.get_active_attempt(step_id)
        if active_id is None:
            return
        active = self.store.get_attempt(active_id)
        active_statuses = _ACTIVE_ATTEMPT_STATES if statuses is None else statuses
        if active is not None and active.input_signature == input_signature and active.status in active_statuses:
            raise ACPAdapterError("an active or ambiguous ACP attempt already owns this input signature")

    def _persist_intent(self, plan, step_id, input_signature, attempt_id, status, *, now=None):
        attempt = ExecutionAttempt(attempt_id, plan.scope, plan.workflow_id, step_id, status, input_signature)
        self.store.save_attempt(attempt)
        self.store.set_active_attempt(step_id, attempt_id)
        self.store.append_event(ExecutionEvent(f"event-{attempt_id}", plan.scope, attempt_id, "ACP_INTENT_PERSISTED", status, "ACP action intent persisted before command execution.", now or datetime.now(timezone.utc)))

    def _mark_attempt(self, plan, step_id, attempt_id, status, *, provider_job_id=None, provider_chain_id=None, now=None):
        existing = self.store.get_attempt(attempt_id)
        if existing is None:
            raise ACPAdapterError("attempt intent was not found")
        updated = ExecutionAttempt(attempt_id, plan.scope, plan.workflow_id, step_id, status, existing.input_signature, provider_job_id or existing.provider_job_id, provider_chain_id or existing.provider_chain_id)
        self.store.save_attempt(updated)
        self.store.set_active_attempt(step_id, None if status in {"failed", "succeeded", "rejected", "expired"} else attempt_id)
        self.store.append_event(ExecutionEvent(f"event-{attempt_id}-{status}", plan.scope, attempt_id, f"ACP_{status.upper()}", status, "ACP command outcome recorded without asserting settlement evidence.", now or datetime.now(timezone.utc)))

    def _persist_reconciliation(self, attempt: ExecutionAttempt, status: str, record: ACPJobRecord, *, now: datetime) -> None:
        updated = replace(
            attempt,
            status=status,
            provider_job_id=record.job_id,
            provider_chain_id=record.chain_id,
        )
        self.store.save_attempt(updated)
        self.store.set_active_attempt(attempt.step_id, None if status in {"succeeded", "rejected", "expired"} else attempt.attempt_id)
        self.store.append_event(
            ExecutionEvent(
                f"event-{attempt.attempt_id}-reconciled",
                attempt.scope,
                attempt.attempt_id,
                "ACP_RECONCILED",
                status,
                "ACP provider state was reconciled from a persisted attempt without asserting settlement evidence.",
                now,
            )
        )


def canonical_requirements(requirements: Mapping[str, Any]) -> str:
    if not isinstance(requirements, Mapping):
        raise ACPParseError("ACP requirements must be an object")
    try:
        return canonical_json(dict(requirements))
    except ValueError as error:
        raise ACPParseError("ACP requirements are not valid JSON") from error
