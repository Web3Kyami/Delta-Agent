from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from delta.baseline import DEFAULT_INPUTS, LangGraphBaseline, run_comparison_matrix, run_once


class PhaseSixBaselineTests(unittest.TestCase):
    def test_measured_langgraph_overlap_matches_delta_for_changed_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-phase6-matrix-") as directory:
            evidence = run_comparison_matrix(directory)
        for name, case in evidence.items():
            baseline_calls = [run["calls"] for run in case["langgraph"]]
            delta_calls = [run["calls"] for run in case["delta"]]
            self.assertEqual(baseline_calls, delta_calls, name)
        self.assertEqual(evidence["launch_date_only"]["langgraph"][1]["calls"]["visual"], 0)
        self.assertEqual(evidence["launch_date_only"]["langgraph"][1]["calls"]["announcement"], 1)
        self.assertEqual(evidence["visual_brief_only"]["langgraph"][1]["calls"]["visual"], 1)
        self.assertEqual(evidence["visual_brief_only"]["langgraph"][1]["calls"]["announcement"], 0)
        self.assertEqual(evidence["upstream_rerun_same_output"]["langgraph"][1]["calls"]["announcement"], 1)
        self.assertEqual(evidence["upstream_rerun_same_output"]["langgraph"][1]["calls"]["translation"], 0)

    def test_sqlite_cache_expires_and_project_scope_isolated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-phase6-ttl-") as directory:
            baseline = LangGraphBaseline(directory, ttl_seconds=1)
            first = baseline.run("project-a", DEFAULT_INPUTS)
            self.assertEqual(first.calls, {"visual": 1, "announcement": 1, "translation": 1})
            time.sleep(1.1)
            expired = baseline.run("project-a", DEFAULT_INPUTS)
            other_project = baseline.run("project-b", DEFAULT_INPUTS)
        self.assertEqual(expired.calls, {"visual": 1, "announcement": 1, "translation": 1})
        self.assertEqual(other_project.calls, {"visual": 1, "announcement": 1, "translation": 1})

    def test_fresh_process_restores_checkpoint_and_reuses_persistent_cache(self) -> None:
        with tempfile.TemporaryDirectory(prefix="delta-phase6-restart-") as directory:
            first = run_once(directory, "restart-project", DEFAULT_INPUTS)
            script = """
import json
import sys
from dataclasses import asdict
from delta.baseline import DEFAULT_INPUTS, run_once

result = run_once(sys.argv[1], "restart-project", DEFAULT_INPUTS)
print(json.dumps(asdict(result)))
"""
            child = subprocess.run(
                [sys.executable, "-c", script, directory],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
            )
            recovered = json.loads(child.stdout)
        self.assertEqual(first.calls, {"visual": 1, "announcement": 1, "translation": 1})
        self.assertEqual(recovered["calls"], {"visual": 0, "announcement": 0, "translation": 0})
        self.assertEqual(recovered["persisted_state"]["project_id"], "restart-project")
        self.assertTrue(recovered["persisted_state"]["translation"]["fixture"])


if __name__ == "__main__":
    unittest.main()
