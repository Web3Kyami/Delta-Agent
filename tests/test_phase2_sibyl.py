from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from delta.store import SibylStore

try:
    import sibyl_memory_client  # noqa: F401
except ImportError:
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True

ROOT = Path(__file__).resolve().parents[1]
TENANT = "11111111-1111-1111-1111-111111111111"


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for the real Sibyl test")
class PhaseTwoSibylTests(unittest.TestCase):
    def run_child(self, script: str, db_path: Path) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, "-c", script, str(db_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_fresh_process_recovery_project_isolation_and_store_deletion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-phase2-") as directory:
            db_path = Path(directory) / "memory.db"
            writer_script = r'''
import json, sys
from datetime import datetime, timedelta, timezone
from delta.core import ArtifactReference, ExecutionAttempt, ExecutionEvent, RevisionRequest, Scope, Step, Workflow, WorkResult, build_revision_plan, output_signature
from delta.store import SibylStore

scope = Scope("11111111-1111-1111-1111-111111111111", "project-a")
store = SibylStore.local(sys.argv[1], scope)
now = datetime(2026, 9, 2, tzinfo=timezone.utc)
result = WorkResult(scope, "launch-package", "announcement", "announcement-fixture-v1", "input:phase2-announcement", output_signature({"fixture": True, "copy": "ready"}), {"fixture": True, "copy": "ready"}, now, now + timedelta(hours=1), "attempt-phase2")
attempt = ExecutionAttempt("attempt-phase2", scope, "launch-package", "announcement", "completed", result.input_signature, "provider-job-phase2", 8453)
event = ExecutionEvent("event-phase2", scope, attempt.attempt_id, "RESULT_PERSISTED", "completed", "Representative Phase 2 smoke-test record.", now)
artifact = ArtifactReference("artifact-phase2", "sha256:artifact", "text/plain", 421, "https://example.invalid/delta/artifact-phase2", True)
missing_artifact = ArtifactReference("artifact-missing", "sha256:missing", "text/plain", 128, "https://example.invalid/delta/missing", False)
workflow = Workflow("phase2", "1", {}, (Step("only", "only-v1"),))
artifact_workflow = Workflow("artifact-check", "1", {}, (Step("visual", "visual-fixture-v1"),))
artifact_result = WorkResult(scope, "artifact-check", "visual", "visual-fixture-v1", "input:artifact", output_signature({"fixture": True, "image": "metadata"}), {"fixture": True, "image": "metadata"}, now, now + timedelta(hours=1), artifact=missing_artifact)
store.save_work_result(result)
store.save_work_result(artifact_result)
store.save_attempt(attempt)
store.save_plan(build_revision_plan(RevisionRequest(scope, workflow, {})))
store.set_active_attempt("announcement", attempt.attempt_id)
store.append_event(event)
store.save_artifact_reference("launch-package", "announcement", artifact)
print(json.dumps({"record_bytes": len(json.dumps(store.client.list_entities("delta.work_result.v1")[0]["body"], sort_keys=True).encode()), "saved": True}))
'''
            first = self.run_child(writer_script, db_path)
            self.assertTrue(first["saved"])
            self.assertGreater(first["record_bytes"], 0)

            reader_script = r'''
import json, sys
from delta.core import Scope, Step, Workflow
from delta.fixtures import launch_package_fixtures
from delta.store import SibylStore

scope = Scope("11111111-1111-1111-1111-111111111111", "project-a")
store = SibylStore.local(sys.argv[1], scope)
result = store.get_work_result("launch-package", "announcement", "input:phase2-announcement")
attempt = store.get_attempt("attempt-phase2")
plan = store.get_plan(store.client.list_entities("delta.revision_plan.v1")[0]["body"]["plan_id"])
fixture = launch_package_fixtures()["announcement"]
artifact = store.get_artifact_reference("launch-package", "announcement", "artifact-phase2")
missing = store.get_work_result("artifact-check", "visual", "input:artifact")
artifact_workflow = Workflow("artifact-check", "1", {}, (Step("visual", "visual-fixture-v1"),))
artifact_reusable = missing.matches(scope, artifact_workflow, artifact_workflow.steps[0], "input:artifact") if missing else True
project_b = SibylStore.local(sys.argv[1], Scope("11111111-1111-1111-1111-111111111111", "project-b"))
events = store.read_events("attempt-phase2")
print(json.dumps({"result": result.output if result else None, "attempt": attempt.provider_job_id if attempt else None, "plan": plan is not None, "active": store.get_active_attempt("announcement"), "events": len(events), "artifact": artifact.artifact_id if artifact else None, "artifact_reusable": artifact_reusable, "project_b_result": project_b.get_work_result("launch-package", "announcement", "input:phase2-announcement") is not None, "fixture_calls": fixture.call_count}))
'''
            second = self.run_child(reader_script, db_path)
            self.assertEqual(second["result"], {"fixture": True, "copy": "ready"})
            self.assertEqual(second["attempt"], "provider-job-phase2")
            self.assertTrue(second["plan"])
            self.assertEqual(second["active"], "attempt-phase2")
            self.assertEqual(second["events"], 1)
            self.assertEqual(second["artifact"], "artifact-phase2")
            self.assertFalse(second["artifact_reusable"])
            self.assertFalse(second["project_b_result"])
            self.assertEqual(second["fixture_calls"], 0)

            db_path.unlink()
            empty_reader_script = r'''
import json, sys
from delta.core import Scope
from delta.store import SibylStore
store = SibylStore.local(sys.argv[1], Scope("11111111-1111-1111-1111-111111111111", "project-a"))
print(json.dumps({"restored": store.get_work_result("launch-package", "announcement", "input:phase2-announcement") is not None, "active": store.get_active_attempt("announcement")}))
'''
            third = self.run_child(empty_reader_script, db_path)
            self.assertFalse(third["restored"])
            self.assertIsNone(third["active"])


if __name__ == "__main__":
    unittest.main()
