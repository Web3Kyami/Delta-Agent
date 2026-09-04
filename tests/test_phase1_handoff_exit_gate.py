"""Phase 1 exit gate: fresh-process handoff from Agent A to Agent B.

The exit gate requires that Process A persists Agent A's work and exits, then a
separate Process B starts with a distinct Agent B session, recalls the work from
Sibyl, produces at least one `reuse` and one `blocked` result, and constructs
approved context that provably excludes blocked content.

Every assertion below is made against the child processes' real stdout. The
child scripts are launched with `subprocess`, so no Python object, cached
result, or in-memory state can cross from Agent A's process into Agent B's.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests import handoff_scenario as scenario

try:
    import sibyl_memory_client  # noqa: F401
except ImportError:  # pragma: no cover - exercised only without the SDK
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True

ROOT = Path(__file__).resolve().parents[1]

WRITER = r'''
import json, os, sys
from datetime import datetime, timezone

from delta.core import RevisionRequest
from delta.execute import DeltaEngine
from delta.store import SibylStore

from tests import handoff_scenario as scenario

db_path = sys.argv[1]
scope = scenario.scope()
store = SibylStore.local(db_path, scope)
workflow = scenario.handoff_workflow(scenario.fixtures())
engine = DeltaEngine(store, principal=scenario.AGENT_A)
report = engine.execute(
    RevisionRequest(scope, workflow, scenario.inputs()),
    now=scenario.NOW,
)
persisted = sorted(result.step_id for result in store.list_work_results(workflow.id))
print(json.dumps({
    "pid": os.getpid(),
    "agent": scenario.AGENT_A.agent_id,
    "session": scenario.AGENT_A.session_id,
    "decisions": {d.step_id: d.reason_code for d in report.decisions},
    "persisted_steps": persisted,
    "canary_persisted": any(
        scenario.PRIVATE_CANARY in json.dumps(result.output, sort_keys=True)
        for result in store.list_work_results(workflow.id)
    ),
}))
'''

READER = r'''
import json, os, sys

from delta.handoff import HandoffGate, HandoffRequest
from delta.store import SibylStore

from tests import handoff_scenario as scenario

db_path = sys.argv[1]
scope = scenario.scope()
store = SibylStore.local(db_path, scope)
gate = HandoffGate(store)
request = HandoffRequest(
    scope=scope,
    workflow=scenario.handoff_workflow(),
    inputs=scenario.inputs(),
    recipient=scenario.AGENT_B,
    policies=scenario.policies(),
)
evaluation = gate.evaluate(request, now=scenario.NOW)
gate.persist(evaluation)

context = evaluation.approved_context
prompt_payload = context.prompt_payload()
# The entire serialized surface Agent B could ever read from this handoff.
agent_b_surface = json.dumps(
    {
        "prompt_payload": prompt_payload,
        "inherited_outputs": context.inherited_outputs(),
        "record": [d.payload() for d in evaluation.record.decisions],
        "receipt": [e.payload() for e in evaluation.receipt.entries],
        "summary": evaluation.receipt.summary,
    },
    sort_keys=True,
)

reloaded_record = store.get_handoff_record(evaluation.handoff_id)
reloaded_receipt = store.get_reuse_receipt(evaluation.receipt.receipt_id)
reloaded_surface = json.dumps(
    {
        "record": [d.payload() for d in reloaded_record.decisions],
        "receipt": [e.payload() for e in reloaded_receipt.entries],
    },
    sort_keys=True,
)

print(json.dumps({
    "pid": os.getpid(),
    "agent": scenario.AGENT_B.agent_id,
    "session": scenario.AGENT_B.session_id,
    "handoff_id": evaluation.handoff_id,
    "receipt_id": evaluation.receipt.receipt_id,
    "decisions": {d.step_id: d.decision.value for d in evaluation.decisions},
    "reason_codes": {d.step_id: d.reason_code for d in evaluation.decisions},
    "verdicts": {d.step_id: d.verdicts.payload() for d in evaluation.decisions},
    "approved_steps": list(context.approved_step_ids),
    "blocked_steps": list(context.blocked_step_ids),
    "counts": dict(evaluation.receipt.counts),
    "summary": evaluation.receipt.summary,
    "canary_in_agent_b_surface": scenario.PRIVATE_CANARY in agent_b_surface,
    "canary_in_reloaded_records": scenario.PRIVATE_CANARY in reloaded_surface,
    "source_sessions": sorted(
        item["source_session_id"] for item in prompt_payload["approved_work"]
    ),
    "candidate_work_visible": sorted(
        result.step_id for result in store.list_work_results("software-handoff")
    ),
    "canary_reachable_in_store": any(
        scenario.PRIVATE_CANARY in json.dumps(result.output, sort_keys=True)
        for result in store.list_work_results("software-handoff")
    ),
}))
'''


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for the exit gate")
class PhaseOneExitGateTests(unittest.TestCase):
    def run_child(self, script: str, db_path: Path) -> dict:
        completed = subprocess.run(
            [sys.executable, "-c", script, str(db_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_fresh_process_handoff_excludes_blocked_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-phase1-exit-") as directory:
            db_path = Path(directory) / "memory.db"

            # Process A: Agent A completes work, Sibyl persists it, process exits.
            writer = self.run_child(WRITER, db_path)
            self.assertEqual(writer["agent"], "agent-a-implementer")
            self.assertEqual(
                sorted(writer["persisted_steps"]),
                ["insurer_summary", "inventory", "private_note", "repair_scope"],
            )
            self.assertTrue(
                writer["canary_persisted"],
                "control: internal-only content must really be persisted",
            )

            # Process B: distinct process, distinct Agent B session.
            reader = self.run_child(READER, db_path)
            self.assertNotEqual(writer["pid"], reader["pid"], "Agent B must run in a fresh process")
            self.assertEqual(reader["agent"], "agent-b-successor")
            self.assertNotEqual(writer["session"], reader["session"])

            # Agent B genuinely recalled Agent A's work from Sibyl.
            self.assertEqual(
                sorted(reader["candidate_work_visible"]),
                ["insurer_summary", "inventory", "private_note", "repair_scope"],
            )
            self.assertTrue(
                reader["canary_reachable_in_store"],
                "control: Agent B's process can read the blocked content from the store",
            )

            # At least one reuse and one blocked result.
            decisions = reader["decisions"]
            self.assertGreaterEqual(reader["counts"]["reuse"], 1)
            self.assertGreaterEqual(reader["counts"]["blocked"], 1)
            self.assertEqual(decisions["inventory"], "reuse")
            self.assertEqual(decisions["private_note"], "blocked")
            self.assertEqual(
                reader["reason_codes"]["private_note"],
                "BLOCKED_EXTERNAL_EXPOSURE_BLOCKED",
            )

            # Validity and authorization stayed independent for the blocked item.
            private_verdicts = reader["verdicts"]["private_note"]
            self.assertEqual(private_verdicts["validity"]["status"], "valid")
            self.assertEqual(private_verdicts["trust"]["status"], "trusted")
            self.assertEqual(private_verdicts["authorization"]["status"], "unauthorized")

            # The approved context provably excludes the blocked content.
            self.assertIn("private_note", reader["blocked_steps"])
            self.assertNotIn("private_note", reader["approved_steps"])
            self.assertFalse(
                reader["canary_in_agent_b_surface"],
                "blocked content leaked into a surface Agent B can read",
            )
            self.assertFalse(
                reader["canary_in_reloaded_records"],
                "blocked content leaked into the persisted handoff record or receipt",
            )

            # Inherited work carries Agent A's session provenance.
            self.assertEqual(set(reader["source_sessions"]), {writer["session"]})

            # A second fresh process reaches the identical gate result.
            repeat = self.run_child(READER, db_path)
            self.assertNotEqual(reader["pid"], repeat["pid"])
            self.assertEqual(reader["handoff_id"], repeat["handoff_id"])
            self.assertEqual(reader["receipt_id"], repeat["receipt_id"])
            self.assertEqual(reader["decisions"], repeat["decisions"])
            self.assertEqual(reader["reason_codes"], repeat["reason_codes"])
            self.assertEqual(reader["counts"], repeat["counts"])
            self.assertEqual(reader["summary"], repeat["summary"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
