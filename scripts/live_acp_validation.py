"""Run one explicitly approved Aaga ACP validation through Delta's adapter.

This operator script is intentionally narrow. It uses live ACP responses and
Sibyl persistence, and it requires a separate explicit approval flag before
any state-changing ACP command. Local evidence remains outside source control.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any
from decimal import Decimal, InvalidOperation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from delta.core import (
    CostEstimate,
    InputSpec,
    RevisionRequest,
    Scope,
    SpendApproval,
    Step,
    Workflow,
    build_revision_plan,
    workflow_input,
)
from delta.providers.acp import ACPAdapter, ACPCommandRunner, ACPCommandStatus
from delta.store import SibylStore


CHAIN_ID = 8453
PROVIDER_ADDRESS = "0xb0aca700745a989a1cb859eecfe0fd9afbc066aa"
OFFERING_ID = "019d7c71-44c9-7329-bcf6-3edb953d6711"
OFFERING_NAME = "content_generation"
SCOPE = Scope("delta-live-20260903", "aaga-content-validation")
WORKFLOW_ID = "launch-announcement-live"
STEP_ID = "announcement"
ATTEMPT_ID = "attempt-aaga-live-20260903"
REQUIREMENTS: dict[str, Any] = {
    "topic": "Delta revision planning with Sibyl continuity",
    "content_type": "press_release",
    "tone": "professional",
    "audience": "developers",
    "word_count": 250,
}
MEMORY_PATH = PROJECT_ROOT / ".delta" / "live-aaga-20260903.db"
CLI_PREFIX = ("npx", "-p", "@virtuals-protocol/acp-cli@1.0.34", "acp")


def live_context() -> tuple[SibylStore, ACPAdapter, Any, Any, str]:
    os.environ.setdefault("TS_KEYRING_BACKEND", "file")
    now = datetime.now(timezone.utc)
    workflow = Workflow(
        WORKFLOW_ID,
        "1",
        {name: InputSpec("number" if name == "word_count" else "string") for name in REQUIREMENTS},
        (
            Step(
                STEP_ID,
                "acp-v2@aaga/content_generation",
                {name: workflow_input(name) for name in REQUIREMENTS},
                estimated_cost=CostEstimate("0.01", "USDC", "live_acp_browse", now),
            ),
        ),
    )
    plan = build_revision_plan(RevisionRequest(SCOPE, workflow, REQUIREMENTS), now=now)
    decision = plan.decisions[0]
    if decision.input_signature is None:
        raise RuntimeError("live plan did not produce an input signature")
    store = SibylStore.local(MEMORY_PATH, SCOPE)
    store.save_plan(plan)
    approval = SpendApproval(
        "approval-aaga-live-20260903",
        plan.plan_id,
        SCOPE,
        (STEP_ID,),
        PROVIDER_ADDRESS,
        OFFERING_ID,
        CHAIN_ID,
        ("create_job", "fund", "complete"),
        "USDC",
        "0.01",
        "0.01",
        now + timedelta(hours=2),
    )
    adapter = ACPAdapter(store, ACPCommandRunner(command_prefix=CLI_PREFIX))
    return store, adapter, plan, approval, decision.input_signature


def require_approval(args: argparse.Namespace) -> None:
    if not args.approve:
        raise SystemExit("This command needs --approve-aaga-content-job after external approval.")


def print_result(label: str, result: Any) -> None:
    print(
        json.dumps(
            {
                "label": label,
                "status": result.status.value,
                "data": result.data,
                "error": result.error,
                "stderr": result.stderr,
                "external_outcome_ambiguous": result.external_outcome_ambiguous,
            },
            sort_keys=True,
        )
    )


def history_payload(adapter: ACPAdapter, job_id: str) -> dict[str, Any]:
    response = adapter.job_history(job_id, chain_id=CHAIN_ID)
    if response.status != ACPCommandStatus.SUCCEEDED or not isinstance(response.data, dict):
        raise SystemExit(f"ACP history could not be read safely: {response.error or response.stderr}")
    return response.data


def budget_from_history(payload: dict[str, Any]) -> str | None:
    for entry in payload.get("entries", []):
        event = entry.get("event") if isinstance(entry, dict) else None
        if isinstance(event, dict) and event.get("type") == "budget.set":
            amount = event.get("amount")
            if isinstance(amount, (str, int, float)) and not isinstance(amount, bool):
                try:
                    return format(Decimal(str(amount)), "f")
                except (InvalidOperation, ValueError):
                    return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the approved Aaga ACP validation in phases.")
    parser.add_argument("action", choices=("create", "message", "fund", "complete", "reconcile", "status"))
    parser.add_argument("--approve", action="store_true", help="confirm the exact approved Aaga validation scope")
    parser.add_argument("--amount", help="exact provider budget amount returned by ACP")
    parser.add_argument("--job-id", help="job identity when it is not yet persisted")
    args = parser.parse_args()

    store, adapter, plan, approval, input_signature = live_context()
    if args.action == "status":
        attempt = store.get_attempt(ATTEMPT_ID)
        print(
            json.dumps(
                {
                    "attempt_id": ATTEMPT_ID,
                    "status": attempt.status if attempt else None,
                    "provider_job_id": attempt.provider_job_id if attempt else None,
                    "provider_chain_id": attempt.provider_chain_id if attempt else None,
                    "provider_id": attempt.provider_id if attempt else None,
                    "offering_id": attempt.offering_id if attempt else None,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.action == "reconcile":
        attempt = store.get_attempt(ATTEMPT_ID)
        if attempt is None or not attempt.provider_job_id:
            raise SystemExit("No persisted ACP job identity is available for reconciliation.")
        record = adapter.reconcile_attempt(STEP_ID)
        print(
            json.dumps(
                {
                    "attempt_id": ATTEMPT_ID,
                    "job_id": record.job_id,
                    "chain_id": record.chain_id,
                    "provider_id": record.provider_id,
                    "offering_id": record.offering_id,
                    "offering_name": record.offering_name,
                    "provider_status": record.provider_status,
                    "delta_state": record.delta_state,
                    "fixture": record.fixture,
                    "transaction_hashes": list(record.transaction_hashes),
                    "deliverable_present": record.deliverable is not None,
                    "message": "Read-only provider history was reconciled into the persisted attempt. No replacement or payment was attempted.",
                },
                sort_keys=True,
            )
        )
        return 0

    require_approval(args)
    if args.action == "create":
        response = adapter.create_job(
            plan,
            approval,
            step_id=STEP_ID,
            input_signature=input_signature,
            provider_id=PROVIDER_ADDRESS,
            offering_id=OFFERING_ID,
            offering_name=OFFERING_NAME,
            requirements=REQUIREMENTS,
            chain_id=CHAIN_ID,
            amount="0",
            attempt_id=ATTEMPT_ID,
        )
    else:
        attempt = store.get_attempt(ATTEMPT_ID)
        job_id = args.job_id or (attempt.provider_job_id if attempt else None)
        if not job_id:
            raise SystemExit("No persisted ACP job identity is available.")
        if args.action == "message":
            response = adapter.send_requirement(
                job_id,
                chain_id=CHAIN_ID,
                offering_name=OFFERING_NAME,
                requirements=REQUIREMENTS,
            )
        elif args.action == "fund":
            if args.amount is None:
                raise SystemExit("Funding requires the exact budget amount returned by ACP.")
            history = history_payload(adapter, job_id)
            if history.get("status") != "budget_set":
                raise SystemExit("Funding is blocked until ACP history reports budget_set.")
            provider_amount = budget_from_history(history)
            if provider_amount is None:
                raise SystemExit("Funding is blocked because ACP did not expose a valid budget amount.")
            try:
                requested_amount = Decimal(args.amount)
                expected_amount = Decimal(provider_amount)
            except InvalidOperation as error:
                raise SystemExit("Funding amount is not a valid decimal.") from error
            if requested_amount != expected_amount:
                raise SystemExit("Funding is blocked because the requested amount does not match ACP budget.set.")
            response = adapter.fund_job(
                plan,
                approval,
                step_id=STEP_ID,
                input_signature=input_signature,
                provider_id=PROVIDER_ADDRESS,
                offering_id=OFFERING_ID,
                chain_id=CHAIN_ID,
                job_id=job_id,
                amount=args.amount,
                attempt_id=ATTEMPT_ID,
            )
        else:
            history = history_payload(adapter, job_id)
            if history.get("status") != "submitted":
                raise SystemExit("Completion is blocked until ACP history reports submitted.")
            submitted = any(
                isinstance(entry, dict)
                and isinstance(entry.get("event"), dict)
                and entry["event"].get("type") == "job.submitted"
                and entry["event"].get("deliverable") is not None
                and isinstance(entry["event"].get("deliverableHash"), str)
                for entry in history.get("entries", [])
            )
            if not submitted:
                raise SystemExit("Completion is blocked because ACP did not expose a submitted deliverable and hash.")
            response = adapter.complete_job(
                plan,
                approval,
                step_id=STEP_ID,
                input_signature=input_signature,
                provider_id=PROVIDER_ADDRESS,
                offering_id=OFFERING_ID,
                chain_id=CHAIN_ID,
                job_id=job_id,
                amount="0",
                reason="Approved against the requested Delta launch-package output.",
                attempt_id=ATTEMPT_ID,
            )
    print_result(args.action, response)
    return 0 if response.status == ACPCommandStatus.SUCCEEDED else 2


if __name__ == "__main__":
    raise SystemExit(main())
