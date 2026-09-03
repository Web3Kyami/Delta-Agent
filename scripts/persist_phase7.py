"""Persist a labelled ACP observation for local restart inspection.

This script intentionally reads sanitized, tracked response-shape fixtures. It
does not call ACP, Base, a provider, or a wallet. The response is parsed by the
same adapter used for live history, then persisted as an active observation.
It never writes a WorkResult, marks an artifact reusable, or presents fixture
data as live evidence.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from delta.core import ExecutionAttempt, Scope
from delta.providers.acp import (
    ACPAdapter,
    ACPCommandResult,
    ACPCommandStatus,
    ACPObservationSource,
    parse_create_job_response,
)
from delta.store import SibylStore


SCOPE = Scope("delta-local-demo", "phase7-live-acp-75656")
DB_PATH = PROJECT_ROOT / ".delta" / "phase7-recorded-observation.db"
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "acp" / "lifecycle"
ATTEMPT_ID = "attempt-75656"
WORKFLOW_ID = "live-acp-aaga-content"
STEP_ID = "content_generation"
INPUT_SIGNATURE = "aaga-content-topic=ai-agents-in-defi-2026-09-02"


def _fixture_payload(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def main() -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = SibylStore.local(DB_PATH, SCOPE)
    adapter = ACPAdapter(store, runner=object())
    now = datetime.now(timezone.utc)

    created = parse_create_job_response(
        _fixture_payload("recorded_create_receipt.json"),
        chain_id=8453,
    )
    attempt = ExecutionAttempt(
        ATTEMPT_ID,
        SCOPE,
        WORKFLOW_ID,
        STEP_ID,
        "active",
        INPUT_SIGNATURE,
        provider_job_id=created.job_id,
        provider_chain_id=created.chain_id,
        provider_id=created.provider_id,
        offering_name=created.offering_name,
    )
    store.save_attempt(attempt)
    store.set_active_attempt(STEP_ID, ATTEMPT_ID)

    response = ACPCommandResult(
        ACPCommandStatus.SUCCEEDED,
        ("recorded-fixture", "history"),
        data=_fixture_payload("recorded_history_submitted.json"),
    )
    record = adapter.parse_response(response)
    adapter.record_observation(
        ATTEMPT_ID,
        record,
        source=ACPObservationSource.RECORDED_FIXTURE,
        now=now,
    )

    stored = store.get_attempt(ATTEMPT_ID)
    events = store.read_events(attempt_id=ATTEMPT_ID, limit=10)
    print("recorded ACP observation persisted")
    print(f"  source:       {ACPObservationSource.RECORDED_FIXTURE.value}")
    print(f"  job_id:       {stored.provider_job_id if stored else None}")
    print(f"  chain_id:     {stored.provider_chain_id if stored else None}")
    print(f"  attempt:      {stored.status if stored else None}")
    print(f"  work_result:  {store.get_work_result(WORKFLOW_ID, STEP_ID, INPUT_SIGNATURE) is not None}")
    print(f"  events:       {len(events)}")
    print("  live proof:   not established")
    print("  artifact:     unavailable until provider bytes are independently verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
