from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tests.test_phase5_web import WebClient
from delta.web import DeltaWebApp


try:
    import sibyl_memory_client  # noqa: F401
except ImportError:
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for the Phase 3 web path")
class PhaseThreeWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="delta-phase3-web-")
        self.app = DeltaWebApp(memory_path=Path(self.tempdir.name) / "memory.db")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_agent_run_endpoint_gates_context_executes_missing_work_and_persists_receipt(self) -> None:
        client = WebClient(self.app)
        status, _, _ = client.json("/api/login", "POST", {"email": "demo@delta.local", "password": "delta-demo"})
        self.assertEqual(status, "200 OK")
        state = client.json("/api/scenarios/software")[1]
        status, payload, _ = client.json(
            "/api/scenarios/software/agent-run",
            "POST",
            {
                "task": "Summarize the approved implementation context.",
                "brief": "Add a safe handoff boundary to the checkout service",
                "revision": "constraint-change",
                "generation": state["generation"],
            },
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["agent_run"]["status"], "succeeded")
        self.assertEqual(payload["agent_run"]["response"]["fixture"], True)
        self.assertNotIn("PRIVATE-CANARY", json.dumps(payload, sort_keys=True))
        self.assertEqual(payload["approved_context"]["approved_work"][0]["step_id"], "shared_context")
        outcomes = {entry["step_id"]: entry["outcome"] for entry in payload["receipt"]["entries"]}
        self.assertEqual(outcomes["shared_context"], "reused")
        self.assertEqual(outcomes["private_notes"], "blocked")
        self.assertEqual(outcomes["revision_output"], "executed")
        self.assertEqual(payload["execution"]["mode"], "deterministic_fixture")

    def test_agent_run_rejects_stale_generation(self) -> None:
        client = WebClient(self.app)
        client.json("/api/login", "POST", {"email": "demo@delta.local", "password": "delta-demo"})
        state = client.json("/api/scenarios/software")[1]
        client.json("/api/scenarios/software/reset", "POST", {"generation": state["generation"]})
        status, payload, _ = client.json(
            "/api/scenarios/software/agent-run",
            "POST",
            {"task": "This must not run.", "generation": state["generation"]},
        )
        self.assertEqual(status, "409 Conflict")
        self.assertEqual(payload["status"], "stale_generation")


if __name__ == "__main__":
    unittest.main()
