"""Recorded ACP evidence persistence contract, not a live integration test.

These tests route sanitized response-shaped fixtures through the ACP parser and
observation boundary. They prove that a provider observation can be persisted
and restored by a genuinely new Python process without creating a reusable
WorkResult. They do not prove that Delta created, funded, settled, or captured
the recorded external job.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

from delta.core import DecisionKind, ExecutionAttempt, InputSpec, RevisionRequest, Scope, Step, Workflow
from delta.execute import DeltaEngine
from delta.providers.acp import (
    ACPAdapter,
    ACPCommandResult,
    ACPCommandStatus,
    ACPObservationSource,
    parse_create_job_response,
)
from delta.store import SibylStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "acp" / "lifecycle"
NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)
JOB_ID = "recorded-job-75656"
CHAIN_ID = 8453
PROVIDER_ID = "0xb0aca700745a989a1cb859eecfe0fd9afbc066aa"
OFFERING_NAME = "content_generation"
SCOPE = Scope("delta-test-tenant", "phase7-test-7b3f9e1a")
WORKFLOW_ID = "live-acp-aaga-content"
STEP_ID = "content_generation"
INPUT_SIGNATURE = "recorded-input-signature"
ATTEMPT_ID = "attempt-recorded-75656"


def _persist_recorded_observation(db_path: Path) -> None:
    store = SibylStore.local(db_path, SCOPE)
    adapter = ACPAdapter(store, runner=object())

    create_payload = json.loads((FIXTURES / "recorded_create_receipt.json").read_text())
    created = parse_create_job_response(create_payload, chain_id=CHAIN_ID)
    history_payload = json.loads((FIXTURES / "recorded_history_submitted.json").read_text())
    history_response = ACPCommandResult(
        ACPCommandStatus.SUCCEEDED,
        ("recorded-fixture", "history"),
        data=history_payload,
    )
    record = adapter.parse_response(history_response)
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
        requirements_signature=record.requirements_signature,
    )
    store.save_attempt(attempt)
    store.set_active_attempt(STEP_ID, ATTEMPT_ID)

    adapter.record_observation(
        ATTEMPT_ID,
        record,
        source=ACPObservationSource.RECORDED_FIXTURE,
        now=NOW,
    )


class PhaseSevenRecordedEvidenceTests(unittest.TestCase):
    def test_recorded_observation_round_trips_from_a_new_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-phase7-") as directory:
            db_path = Path(directory) / "memory.db"
            _persist_recorded_observation(db_path)
            child = """
import json
import sys
from pathlib import Path
from delta.core import Scope
from delta.store import SibylStore

scope = Scope(sys.argv[2], sys.argv[3])
store = SibylStore.local(Path(sys.argv[1]), scope)
attempt = store.get_attempt("attempt-recorded-75656")
events = store.read_events(attempt_id="attempt-recorded-75656", limit=10)
print(json.dumps({
    "status": attempt.status if attempt else None,
    "job_id": attempt.provider_job_id if attempt else None,
    "chain_id": attempt.provider_chain_id if attempt else None,
    "events": len(events),
    "source": "recorded_fixture" if events and "recorded_fixture observation" in events[-1]["detail"] else None,
}))
"""
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    child,
                    str(db_path),
                    SCOPE.tenant_id,
                    SCOPE.project_id,
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "status": "active",
                    "job_id": JOB_ID,
                    "chain_id": CHAIN_ID,
                    "events": 1,
                    "source": "recorded_fixture",
                },
            )

    def test_recorded_observation_never_creates_reusable_work(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-phase7-") as directory:
            db_path = Path(directory) / "memory.db"
            _persist_recorded_observation(db_path)
            store = SibylStore.local(db_path, SCOPE)
            self.assertIsNone(store.get_work_result(WORKFLOW_ID, STEP_ID, INPUT_SIGNATURE))
            attempt = store.get_attempt(ATTEMPT_ID)
            self.assertIsNotNone(attempt)
            self.assertEqual(attempt.status, "active")
            self.assertEqual(attempt.provider_job_id, JOB_ID)
            self.assertEqual(attempt.provider_chain_id, CHAIN_ID)
            event = store.read_events(attempt_id=ATTEMPT_ID, limit=10)[-1]
            self.assertEqual(event["state"], "active")
            self.assertIn("no settlement or artifact reuse was asserted", event["detail"])
            workflow = Workflow(WORKFLOW_ID, "1", {}, (Step(STEP_ID, "acp-v2@aaga/content_generation"),))
            plan = DeltaEngine(store).preview(RevisionRequest(SCOPE, workflow, {}), now=NOW)
            self.assertEqual(plan.decisions[0].decision, DecisionKind.RERUN)

    def test_recorded_provider_hash_is_metadata_until_bytes_are_verified(self) -> None:
        payload = json.loads((FIXTURES / "recorded_history_submitted.json").read_text())
        adapter = ACPAdapter(store=object(), runner=object())
        record = adapter.parse_response(ACPCommandResult(ACPCommandStatus.SUCCEEDED, ("fixture",), data=payload))
        self.assertTrue(record.fixture)
        self.assertIsNotNone(record.requirements_signature)
        self.assertEqual(record.deliverable_hash, "0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8")
        self.assertIsNotNone(record.deliverable)
        self.assertEqual(record.transaction_hashes, ())


if __name__ == "__main__":
    unittest.main()
