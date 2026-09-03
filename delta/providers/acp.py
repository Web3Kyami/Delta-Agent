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

from ..artifacts import ArtifactResolution, ArtifactResolutionStatus
from ..core import (
    ApprovalValidationError,
    ArtifactReference,
    ExecutionAttempt,
    ExecutionEvent,
    RevisionPlan,
    SpendApproval,
    WorkResult,
    canonical_json,
    output_signature,
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


class ACPObservationSource(str, Enum):
    """Identify whether an observation came from ACP or a labelled fixture."""

    LIVE = "live"
    RECORDED_FIXTURE = "recorded_fixture"


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

    def __init__(
        self,
        *,
        secrets: Sequence[str] = (),
        command_prefix: Sequence[str] | None = None,
    ) -> None:
        self.secrets = tuple(secrets)
        self.command_prefix = tuple(command_prefix or ())
        if any(not isinstance(arg, str) or not arg for arg in self.command_prefix):
            raise ValueError("ACP command prefix must contain non-empty strings")

    def run_json(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: float = 30,
        side_effecting: bool = False,
    ) -> ACPCommandResult:
        if not args or any(not isinstance(arg, str) or not arg for arg in args):
            raise ValueError("ACP args must be a non-empty sequence of strings")
        command = tuple(args)
        if self.command_prefix:
            if command[0] != "acp":
                raise ValueError("configured ACP command prefix requires args to start with 'acp'")
            command = self.command_prefix + command[1:]
        if "--json" not in command:
            command = command + ("--json",)
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
        "completed": "reconciliation_required",
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
    offering_name: str | None = None
    deliverable_hash: str | None = None


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


@dataclass(frozen=True)
class ACPDeliverableVerification:
    """Evidence that provider bytes match the provider-attested hash."""

    algorithm: str
    claimed_hash: str
    computed_hash: str
    matches: bool

    def __post_init__(self) -> None:
        for value, label in (
            (self.algorithm, "algorithm"),
            (self.claimed_hash, "claimed_hash"),
            (self.computed_hash, "computed_hash"),
        ):
            if not isinstance(value, str) or not value:
                raise ACPAdapterError(f"{label} is required")
        if not isinstance(self.matches, bool):
            raise ACPAdapterError("deliverable verification match must be boolean")
        if self.matches and self.claimed_hash != self.computed_hash:
            raise ACPAdapterError("deliverable verification cannot claim a hash match with different hashes")


@dataclass(frozen=True)
class ACPSettlementEvidence:
    """A separately verified successful Base receipt for settlement."""

    chain_id: int
    transaction_hash: str
    receipt_status: str

    def __post_init__(self) -> None:
        if not isinstance(self.chain_id, int) or isinstance(self.chain_id, bool) or self.chain_id <= 0:
            raise ACPAdapterError("settlement chain ID must be a positive integer")
        if not isinstance(self.transaction_hash, str) or not self.transaction_hash:
            raise ACPAdapterError("settlement transaction identity is required")
        if self.receipt_status != "succeeded":
            raise ACPAdapterError("settlement evidence must have a succeeded receipt")


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
    """Parse a provider history or job response without inferring success."""

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
    offering_name = payload.get("offeringName", payload.get("offering_name"))
    deliverable = payload.get("deliverable")
    deliverable_hash = payload.get("deliverableHash", payload.get("deliverable_hash"))
    entries = payload.get("entries", [])
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise ACPParseError("ACP job entries must be an array")
    (
        history_provider,
        history_offering,
        history_created_at,
        history_deliverable,
        history_hash,
        history_transactions,
        history_requirements_signature,
    ) = _history_fields(entries)
    if provider_id is None:
        provider_id = history_provider
    if offering_name is None:
        offering_name = history_offering
    created_at = _parse_created_at(payload.get("createdAt", payload.get("created_at"))) or history_created_at
    if deliverable is None:
        deliverable = history_deliverable
    if deliverable_hash is None:
        deliverable_hash = history_hash
    if provider_id is not None and (not isinstance(provider_id, str) or not provider_id):
        raise ACPParseError("ACP provider identity is malformed")
    if offering_id is not None and (not isinstance(offering_id, str) or not offering_id):
        raise ACPParseError("ACP offering identity is malformed")
    requirements_signature = payload.get("requirementsSignature", payload.get("requirements_signature"))
    if requirements_signature is not None and (not isinstance(requirements_signature, str) or not requirements_signature):
        raise ACPParseError("ACP requirements signature is malformed")
    if requirements_signature is None:
        requirements_signature = history_requirements_signature
    tx_hashes = payload.get("transactionHashes", payload.get("transaction_hashes"))
    if tx_hashes is None and "transactionHash" in payload:
        tx_hashes = [payload["transactionHash"]]
    if tx_hashes is None:
        tx_hashes = history_transactions
    if not isinstance(tx_hashes, list) or any(not isinstance(item, str) for item in tx_hashes):
        raise ACPParseError("ACP transaction hash metadata is malformed")
    return ACPJobRecord(
        job_id=job_id,
        provider_id=provider_id,
        offering_id=offering_id,
        chain_id=chain_id,
        provider_status=status,
        delta_state=_lifecycle_state(status),
        deliverable=deliverable,
        transaction_hashes=tuple(tx_hashes),
        fixture=payload.get("fixture") is True,
        created_at=created_at,
        requirements_signature=requirements_signature,
        offering_name=_optional_record_text(offering_name, "ACP offering name is malformed"),
        deliverable_hash=_optional_record_text(deliverable_hash, "ACP deliverable hash is malformed"),
    )


def parse_create_job_response(payload: Mapping[str, Any], *, chain_id: int) -> ACPJobRecord:
    """Parse the compact create-job receipt returned by ACP v2.

    The observed receipt returns the job ID, provider address, and offering
    name, but not lifecycle or chain fields. The chain is therefore carried
    from the explicitly requested command argument and is not treated as an
    independent provider assertion.
    """

    if not isinstance(payload, Mapping):
        raise ACPParseError("ACP create response must be an object")
    if payload.get("success") is not True:
        raise ACPParseError("ACP create response does not confirm success")
    job_id = payload.get("jobId", payload.get("job_id"))
    provider_id = payload.get("provider", payload.get("providerId", payload.get("provider_id")))
    offering_name = payload.get("offering", payload.get("offeringName", payload.get("offering_name")))
    if not isinstance(job_id, str) or not job_id:
        raise ACPParseError("ACP create response is missing job identity")
    if not isinstance(provider_id, str) or not provider_id:
        raise ACPParseError("ACP create response is missing provider identity")
    if not isinstance(offering_name, str) or not offering_name:
        raise ACPParseError("ACP create response is missing offering identity")
    if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
        raise ACPParseError("requested ACP chain ID is invalid")
    status = payload.get("status", "open")
    if not isinstance(status, str):
        raise ACPParseError("ACP create response lifecycle status is malformed")
    return ACPJobRecord(
        job_id=job_id,
        provider_id=provider_id,
        offering_id=None,
        chain_id=chain_id,
        provider_status=status,
        delta_state=_lifecycle_state(status),
        fixture=payload.get("fixture") is True,
        offering_name=offering_name,
    )


def _history_fields(
    entries: list[Any],
) -> tuple[str | None, str | None, datetime | None, Any | None, str | None, list[str], str | None]:
    provider_id = None
    offering_name = None
    created_at = None
    deliverable = None
    deliverable_hash = None
    transactions: list[str] = []
    requirements_sig = None
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ACPParseError("ACP job entry must be an object")
        timestamp = entry.get("timestamp")
        event = entry.get("event")
        if event is not None and not isinstance(event, Mapping):
            raise ACPParseError("ACP job event must be an object")
        if isinstance(event, Mapping):
            provider = event.get("provider", event.get("providerId", event.get("provider_id")))
            if provider_id is None and isinstance(provider, str) and provider:
                provider_id = provider
            if event.get("type") == "job.created" and created_at is None:
                created_at = _parse_created_at(timestamp)
            if event.get("type") == "job.submitted":
                if "deliverable" in event:
                    deliverable = event["deliverable"]
                if isinstance(event.get("deliverableHash"), str):
                    deliverable_hash = event["deliverableHash"]
            for key in ("transactionHash", "transaction_hash", "txHash", "tx_hash"):
                value = event.get(key)
                if isinstance(value, str) and value:
                    transactions.append(value)
        content = entry.get("content")
        if entry.get("contentType") == "requirement" and isinstance(content, str):
            try:
                decoded = json.loads(content)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, Mapping):
                requirements_sig = _requirements_signature(decoded)
        if isinstance(content, str):
            match = re.search(r"Malformed requirement for ([A-Za-z0-9_.:-]+)", content)
            if match:
                offering_name = match.group(1).rstrip(".,;:")
        for key in ("transactionHash", "transaction_hash", "txHash", "tx_hash"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                transactions.append(value)
    return (
        provider_id,
        offering_name,
        created_at,
        deliverable,
        deliverable_hash,
        list(dict.fromkeys(transactions)),
        requirements_sig,
    )


def _optional_record_text(value: Any, message: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ACPParseError(message)
    return value


def _same_identity(left: str, right: str) -> bool:
    """Compare opaque IDs exactly and EVM addresses without case sensitivity."""

    if left == right:
        return True
    address_pattern = r"^0x[0-9a-fA-F]{40}$"
    return bool(re.fullmatch(address_pattern, left) and re.fullmatch(address_pattern, right) and left.lower() == right.lower())


def _parse_created_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise ACPParseError("ACP creation time is malformed") from error
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
    offering_id: str | None,
    chain_id: int,
    requirements_signature: str | None = None,
    expected_transaction_hashes: Sequence[str] = (),
    offering_name: str | None = None,
    expected_job_id: str | None = None,
) -> ReconciliationDecision:
    """Attach only one candidate with sufficient stable identity evidence."""

    if not candidates:
        return ReconciliationDecision(ReconciliationOutcome.MANUAL, None, "no plausible ACP job matched the persisted intent")
    mismatches = []
    plausible = []
    expected_transactions = set(expected_transaction_hashes)
    for candidate in candidates:
        if expected_job_id is not None and candidate.job_id != expected_job_id:
            mismatches.append("job")
            continue
        if candidate.chain_id != chain_id:
            mismatches.append("chain")
            continue
        if candidate.provider_id is not None and not _same_identity(candidate.provider_id, provider_id):
            mismatches.append("provider")
            continue
        if offering_id is not None and candidate.offering_id is not None and candidate.offering_id != offering_id:
            mismatches.append("offering")
            continue
        if offering_name is not None and candidate.offering_name is not None and candidate.offering_name != offering_name:
            mismatches.append("offering")
            continue
        if requirements_signature is not None and candidate.requirements_signature not in {None, requirements_signature}:
            mismatches.append("requirements")
            continue
        if expected_transactions and candidate.transaction_hashes and not any(
            _same_identity(candidate_hash, expected_hash)
            for candidate_hash in candidate.transaction_hashes
            for expected_hash in expected_transactions
        ):
            mismatches.append("transaction")
            continue
        plausible.append(candidate)
    if not plausible:
        detail = ", ".join(sorted(set(mismatches))) or "identity"
        return ReconciliationDecision(ReconciliationOutcome.BLOCKED, None, f"ACP candidates conflict with persisted {detail} identity")
    if len(plausible) > 1:
        return ReconciliationDecision(ReconciliationOutcome.MANUAL, None, "multiple ACP jobs match the persisted intent")
    candidate = plausible[0]
    offering_matches = (
        offering_id is not None and candidate.offering_id == offering_id
    ) or (
        candidate.offering_id is None
        and offering_name is not None
        and candidate.offering_name == offering_name
    )
    if candidate.provider_id is None or not offering_matches:
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


def _requirements_signature(requirements: Mapping[str, Any]) -> str:
    comparable = requirements.get("requirement") if (
        isinstance(requirements, Mapping)
        and isinstance(requirements.get("requirement"), Mapping)
    ) else requirements
    return "requirements:" + hashlib.sha256(canonical_json(dict(comparable)).encode("utf-8")).hexdigest()


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

    def job_history(self, job_id: str | None = None, *, chain_id: int | None = None) -> ACPCommandResult:
        args = ["acp", "job", "history"]
        if job_id is not None:
            args.extend(["--job-id", job_id])
        if chain_id is not None:
            args.extend(["--chain-id", str(chain_id)])
        return self.runner.run_json(args)

    def watch_job(self, job_id: str, *, chain_id: int | None = None) -> ACPCommandResult:
        args = ["acp", "job", "watch", "--job-id", job_id]
        if chain_id is not None:
            args.extend(["--chain-id", str(chain_id)])
        return self.runner.run_json(args)

    def send_requirement(
        self,
        job_id: str,
        *,
        chain_id: int,
        offering_name: str,
        requirements: Mapping[str, Any],
    ) -> ACPCommandResult:
        """Send an offering-shaped requirement envelope after provider feedback.

        Some ACP providers require the offering name around the requirements
        object, while the installed CLI's create command sends only the inner
        object. This explicit corrective action keeps that discrepancy visible
        and treats a side-effecting timeout as ambiguous.
        """

        _optional_record_text(offering_name, "ACP offering name is required")
        content = canonical_json(
            {"name": offering_name, "requirement": json.loads(canonical_requirements(requirements))}
        )
        return self.runner.run_json(
            [
                "acp",
                "message",
                "send",
                "--job-id",
                job_id,
                "--chain-id",
                str(chain_id),
                "--content-type",
                "requirement",
                "--content",
                content,
            ],
            side_effecting=True,
        )

    def reconcile_known_job(self, job_id: str, *, chain_id: int | None = None) -> ACPJobRecord:
        """Read and map the current provider record before any replacement."""

        return self.parse_response(self.job_history(job_id, chain_id=chain_id))

    def reconcile_attempt(
        self,
        step_id: str,
        *,
        source: ACPObservationSource | str = ACPObservationSource.LIVE,
    ) -> ACPJobRecord:
        """Recover a persisted active attempt and reconcile its provider job."""

        attempt_id = self.store.get_active_attempt(step_id)
        if attempt_id is None:
            raise ACPAdapterError("no active ACP attempt is persisted for this step")
        attempt = self.store.get_attempt(attempt_id)
        if attempt is None or attempt.provider_job_id is None:
            raise ACPAdapterError("persisted ACP attempt has no provider job identity")
        record = self.reconcile_known_job(attempt.provider_job_id, chain_id=attempt.provider_chain_id)
        return self.record_observation(attempt.attempt_id, record, source=source)

    def record_observation(
        self,
        attempt_id: str,
        record: ACPJobRecord,
        *,
        source: ACPObservationSource | str = ACPObservationSource.LIVE,
        now: datetime | None = None,
    ) -> ACPJobRecord:
        """Persist an ACP observation without manufacturing work completion.

        A live response may update the persisted job attempt. A recorded fixture
        may exercise the same parser and persistence boundary only when its
        source is explicitly labelled. Neither path creates a WorkResult or
        makes an artifact reusable.
        """

        source_value = source.value if isinstance(source, ACPObservationSource) else source
        valid_sources = {item.value for item in ACPObservationSource}
        if source_value not in valid_sources:
            raise ACPAdapterError("ACP observation source must be live or recorded_fixture")
        attempt = self.store.get_attempt(attempt_id)
        if attempt is None:
            raise ACPAdapterError("persisted ACP attempt was not found")
        timestamp = now or datetime.now(timezone.utc)
        if record.fixture != (source_value == ACPObservationSource.RECORDED_FIXTURE.value):
            self._persist_reconciliation(attempt, "blocked", record, now=timestamp, source=source_value)
            raise ACPAdapterError("ACP observation source does not match the response fixture marker")
        mismatches: list[str] = []
        if attempt.provider_job_id is not None and attempt.provider_job_id != record.job_id:
            mismatches.append("job")
        if attempt.provider_chain_id is not None and attempt.provider_chain_id != record.chain_id:
            mismatches.append("chain")
        if attempt.provider_id is not None and record.provider_id is not None and not _same_identity(attempt.provider_id, record.provider_id):
            mismatches.append("provider")
        if attempt.offering_id is not None and record.offering_id is not None and attempt.offering_id != record.offering_id:
            mismatches.append("offering")
        if attempt.offering_name is not None and record.offering_name is not None and attempt.offering_name != record.offering_name:
            mismatches.append("offering")
        if (
            attempt.requirements_signature is not None
            and record.requirements_signature is not None
            and attempt.requirements_signature != record.requirements_signature
        ):
            mismatches.append("requirements")
        if mismatches:
            detail = ", ".join(sorted(set(mismatches)))
            self._persist_reconciliation(attempt, "blocked", record, now=timestamp, source=source_value)
            raise ACPAdapterError(f"reconciled ACP observation conflicts with persisted {detail} identity")
        status = {
            "completed": "reconciliation_required",
            "rejected": "rejected",
            "expired": "expired",
        }.get(record.provider_status.lower(), "active")
        self._persist_reconciliation(attempt, status, record, now=timestamp, source=source_value)
        return record

    def get_deliverable(self, job_id: str) -> Any:
        record = self.reconcile_known_job(job_id)
        if record.deliverable is None:
            raise ACPAdapterError("ACP job has no deliverable to retrieve")
        return record.deliverable

    def finalize_completed_work(
        self,
        plan: RevisionPlan,
        *,
        step_id: str,
        implementation_id: str,
        input_signature: str,
        attempt_id: str,
        record: ACPJobRecord,
        artifact_resolution: ArtifactResolution,
        deliverable_verification: ACPDeliverableVerification,
        settlement: ACPSettlementEvidence,
        fresh_until: datetime | None = None,
        now: datetime | None = None,
    ) -> WorkResult:
        """Persist reusable work only after independent live evidence checks.

        ACP history, provider bytes, a verified artifact, and a successful chain
        receipt are passed in explicitly. Recorded fixtures and an ACP
        ``completed`` state alone can never reach the reusable-work boundary.
        """

        if not isinstance(record, ACPJobRecord):
            raise ACPAdapterError("ACP finalization requires an ACPJobRecord")
        if not isinstance(deliverable_verification, ACPDeliverableVerification):
            raise ACPAdapterError("ACP finalization requires deliverable verification evidence")
        if not isinstance(settlement, ACPSettlementEvidence):
            raise ACPAdapterError("ACP finalization requires settlement evidence")
        if record.fixture:
            raise ACPAdapterError("recorded ACP fixtures cannot finalize reusable work")
        if record.provider_status.lower() != "completed":
            raise ACPAdapterError("ACP job is not in the completed lifecycle state")
        if record.deliverable is None:
            raise ACPAdapterError("completed ACP job has no deliverable")
        if not record.deliverable_hash:
            raise ACPAdapterError("completed ACP job has no provider deliverable hash")
        if not deliverable_verification.matches:
            raise ACPAdapterError("provider deliverable hash verification did not succeed")
        if not (
            deliverable_verification.claimed_hash == record.deliverable_hash
            and deliverable_verification.computed_hash == record.deliverable_hash
        ):
            raise ACPAdapterError("provider deliverable hash evidence conflicts with ACP history")
        if settlement.chain_id != record.chain_id:
            raise ACPAdapterError("settlement chain does not match the ACP job chain")
        if not isinstance(artifact_resolution, ArtifactResolution):
            raise ACPAdapterError("artifact finalization requires an ArtifactResolution")
        if artifact_resolution.status is not ArtifactResolutionStatus.AVAILABLE:
            raise ACPAdapterError("artifact is not available and verified for reuse")
        artifact = artifact_resolution.reference
        if artifact is None or not artifact.available:
            raise ACPAdapterError("artifact resolution did not return a reusable artifact reference")
        if not isinstance(implementation_id, str) or not implementation_id:
            raise ACPAdapterError("implementation identity is required to finalize work")

        attempt = self.store.get_attempt(attempt_id)
        if attempt is None:
            raise ACPAdapterError("persisted ACP attempt was not found")
        if attempt.scope != plan.scope or attempt.workflow_id != plan.workflow_id:
            raise ACPAdapterError("ACP attempt does not belong to the requested plan")
        if attempt.step_id != step_id or attempt.input_signature != input_signature:
            raise ACPAdapterError("ACP attempt does not match the requested workflow step and input")
        if attempt.provider_job_id != record.job_id:
            raise ACPAdapterError("ACP job identity does not match the persisted attempt")
        if attempt.provider_chain_id != record.chain_id:
            raise ACPAdapterError("ACP chain identity does not match the persisted attempt")
        if attempt.status not in {"active", "reconciliation_required"}:
            raise ACPAdapterError("ACP attempt is not awaiting verified completion")
        if not attempt.provider_id or not record.provider_id or not _same_identity(attempt.provider_id, record.provider_id):
            raise ACPAdapterError("ACP provider identity is missing or conflicting")
        if attempt.offering_id and record.offering_id and attempt.offering_id != record.offering_id:
            raise ACPAdapterError("ACP offering identity conflicts with the persisted attempt")
        if attempt.offering_name and record.offering_name and attempt.offering_name != record.offering_name:
            raise ACPAdapterError("ACP offering name conflicts with the persisted attempt")
        if not (
            (attempt.offering_id and record.offering_id == attempt.offering_id)
            or (attempt.offering_name and record.offering_name == attempt.offering_name)
        ):
            raise ACPAdapterError("ACP response lacks the offering identity needed for finalization")
        if not attempt.requirements_signature or record.requirements_signature != attempt.requirements_signature:
            raise ACPAdapterError("ACP requirements identity is missing or conflicting")
        if record.transaction_hashes and not any(
            transaction.lower() == settlement.transaction_hash.lower()
            for transaction in record.transaction_hashes
        ):
            raise ACPAdapterError("settlement transaction conflicts with ACP transaction identity")

        timestamp = now or datetime.now(timezone.utc)
        result = WorkResult(
            scope=plan.scope,
            workflow_id=plan.workflow_id,
            step_id=step_id,
            implementation_id=implementation_id,
            input_signature=input_signature,
            output_signature=output_signature(record.deliverable),
            output=record.deliverable,
            completed_at=timestamp,
            fresh_until=fresh_until,
            successful_attempt_id=attempt_id,
            artifact=artifact,
        )
        self.store.save_artifact_reference(plan.workflow_id, step_id, artifact)
        self.store.save_work_result(result)
        self.store.save_attempt(
            replace(
                attempt,
                status="succeeded",
                provider_id=record.provider_id,
                offering_id=attempt.offering_id or record.offering_id,
                offering_name=attempt.offering_name or record.offering_name,
            )
        )
        self.store.set_active_attempt(step_id, None)
        self.store.append_event(
            ExecutionEvent(
                f"event-{attempt_id}-work-finalized",
                plan.scope,
                attempt_id,
                "ACP_WORK_FINALIZED",
                "succeeded",
                f"ACP completed job {record.job_id} with independently verified deliverable and settlement; reusable work persisted.",
                timestamp,
            )
        )
        return result

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
            self._persist_intent(
                plan,
                step_id,
                input_signature,
                attempt_id,
                "submitting",
                provider_id=provider_id,
                offering_id=offering_id,
                offering_name=offering_name,
                requirements_signature=_requirements_signature(requirements),
                chain_id=chain_id,
                now=now,
            )
        response = self.runner.run_json(args, side_effecting=True)
        if response.status == ACPCommandStatus.SUCCEEDED:
            try:
                if isinstance(response.data, Mapping) and ("chainId" in response.data or "chain_id" in response.data):
                    record = self.parse_response(response)
                else:
                    record = parse_create_job_response(response.data, chain_id=chain_id)
            except ACPAdapterError:
                self._mark_attempt(plan, step_id, attempt_id, "ambiguous", now=now)
                return replace(response, status=ACPCommandStatus.AMBIGUOUS, external_outcome_ambiguous=True)
            if not self._create_response_matches_request(record, provider_id, offering_id, offering_name, chain_id):
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
            plan, approval, step_id=step_id, input_signature=input_signature, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action="fund", amount=amount, attempt_id=attempt_id, args=["acp", "client", "fund", "--job-id", job_id, "--amount", amount, "--chain-id", str(chain_id)], now=now,
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
            plan, approval, step_id=step_id, input_signature=input_signature, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action="complete", amount=amount, attempt_id=attempt_id, args=["acp", "client", "complete", "--job-id", job_id, "--chain-id", str(chain_id), "--reason", reason], now=now,
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
            plan, approval, step_id=step_id, input_signature=input_signature, provider_id=provider_id, offering_id=offering_id, chain_id=chain_id, action="reject", amount="0", attempt_id=attempt_id, args=["acp", "client", "reject", "--job-id", job_id, "--chain-id", str(chain_id), "--reason", reason], now=now,
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
            self._persist_intent(
                plan,
                step_id,
                input_signature,
                attempt_id,
                "submitting",
                provider_id=provider_id,
                offering_id=offering_id,
                chain_id=chain_id,
                now=now,
            )
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
    def _create_response_matches_request(record: ACPJobRecord, provider_id: str, offering_id: str, offering_name: str, chain_id: int) -> bool:
        return (
            record.chain_id == chain_id
            and (record.provider_id is None or _same_identity(record.provider_id, provider_id))
            and (record.offering_id is None or record.offering_id == offering_id)
            and (record.offering_name is None or record.offering_name == offering_name)
        )

    def _reject_duplicate_active_attempt(self, step_id: str, input_signature: str, statuses=None) -> None:
        active_id = self.store.get_active_attempt(step_id)
        if active_id is None:
            return
        active = self.store.get_attempt(active_id)
        active_statuses = _ACTIVE_ATTEMPT_STATES if statuses is None else statuses
        if active is not None and active.input_signature == input_signature and active.status in active_statuses:
            raise ACPAdapterError("an active or ambiguous ACP attempt already owns this input signature")

    def _persist_intent(self, plan, step_id, input_signature, attempt_id, status, *, provider_id=None, offering_id=None, offering_name=None, requirements_signature=None, chain_id=None, now=None):
        attempt = ExecutionAttempt(
            attempt_id,
            plan.scope,
            plan.workflow_id,
            step_id,
            status,
            input_signature,
            provider_chain_id=chain_id,
            provider_id=provider_id,
            offering_id=offering_id,
            offering_name=offering_name,
            requirements_signature=requirements_signature,
        )
        self.store.save_attempt(attempt)
        self.store.set_active_attempt(step_id, attempt_id)
        self.store.append_event(ExecutionEvent(f"event-{attempt_id}", plan.scope, attempt_id, "ACP_INTENT_PERSISTED", status, "ACP action intent persisted before command execution.", now or datetime.now(timezone.utc)))

    def _mark_attempt(self, plan, step_id, attempt_id, status, *, provider_job_id=None, provider_chain_id=None, now=None):
        existing = self.store.get_attempt(attempt_id)
        if existing is None:
            raise ACPAdapterError("attempt intent was not found")
        updated = ExecutionAttempt(
            attempt_id,
            plan.scope,
            plan.workflow_id,
            step_id,
            status,
            existing.input_signature,
            provider_job_id or existing.provider_job_id,
            provider_chain_id or existing.provider_chain_id,
            existing.error_code,
            existing.provider_id,
            existing.offering_id,
            existing.offering_name,
            existing.requirements_signature,
        )
        self.store.save_attempt(updated)
        self.store.set_active_attempt(step_id, None if status in {"failed", "succeeded", "rejected", "expired"} else attempt_id)
        self.store.append_event(ExecutionEvent(f"event-{attempt_id}-{status}", plan.scope, attempt_id, f"ACP_{status.upper()}", status, "ACP command outcome recorded without asserting settlement evidence.", now or datetime.now(timezone.utc)))

    def _persist_reconciliation(
        self,
        attempt: ExecutionAttempt,
        status: str,
        record: ACPJobRecord,
        *,
        now: datetime,
        source: str = ACPObservationSource.LIVE.value,
    ) -> None:
        updated = replace(
            attempt,
            status=status,
            provider_job_id=record.job_id,
            provider_chain_id=record.chain_id,
            provider_id=attempt.provider_id or record.provider_id,
            offering_name=attempt.offering_name or record.offering_name,
            requirements_signature=attempt.requirements_signature or record.requirements_signature,
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
                f"ACP {source} observation recorded for job {record.job_id} at lifecycle {record.provider_status}; no settlement or artifact reuse was asserted.",
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
