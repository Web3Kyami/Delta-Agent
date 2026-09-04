"""Mutation review for Phase 2 demo identity, isolation, and reset guards.

Each mutation edits one real source guard in place, runs the focused Phase 2
tests, restores the source, and reports whether the test suite caught it.

Run: .venv/bin/python scripts/phase2_mutation_review.py
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / ".venv" / "bin" / "python")
SESSION = ROOT / "delta" / "session.py"
DEMO = ROOT / "delta" / "demo.py"
WEB = ROOT / "delta" / "web.py"
TESTS = ["tests/test_phase2_web.py"]

# (label, file, old text, replacement text)
MUTATIONS = [
    (
        "session: signature verification removed",
        SESSION,
        "        if not hmac.compare_digest(actual, expected):\n            raise SessionError(\"The demo session signature is invalid.\")",
        "        if False:\n            raise SessionError(\"The demo session signature is invalid.\")",
    ),
    (
        "session: expiry verification removed",
        SESSION,
        "        if current >= session.expires_at:\n            raise SessionError(\"The demo session has expired. Sign in again.\")",
        "        if False:\n            raise SessionError(\"The demo session has expired. Sign in again.\")",
    ),
    (
        "demo: workspace digest collapsed to one shared scope",
        DEMO,
        "    workspace_digest = hashlib.sha256(workspace_id.encode(\"utf-8\")).hexdigest()[:12]",
        "    workspace_digest = \"shared-workspace\"",
    ),
    (
        "web: stale handoff generation accepted",
        WEB,
        "        if requested_generation is not None and requested_generation != generation:\n            return self._json(start_response, {\"status\": \"stale_generation\", \"message\": \"This handoff belongs to an older scenario generation. Reload the current scenario.\"}, 409)",
        "        if False:\n            return self._json(start_response, {\"status\": \"stale_generation\", \"message\": \"This handoff belongs to an older scenario generation. Reload the current scenario.\"}, 409)",
    ),
    (
        "web: reset deletion skipped",
        WEB,
        "            deleted = store.delete_scope_records(workflow_ids={definition.workflow_id})",
        "            deleted = {}",
    ),
    (
        "web: reset active heads not cleared",
        WEB,
        "            store.reset_active_heads([\"shared_context\", \"private_notes\", \"dependent_summary\", \"revision_output\"])",
        "            pass",
    ),
    (
        "web: legacy payload allowed to select the Sibyl workspace",
        WEB,
        "        return RevisionRequest(demo_scope(session.workspace_id), request.workflow, request.inputs)",
        "        return request",
    ),
    (
        "web: retired generation tombstone ignored",
        WEB,
        "        if marker is not None and marker.get(\"generation\") != generation:\n            raise StaleScenarioError(\"This scenario generation is no longer active. Reload the current scenario.\")",
        "        if False:\n            raise StaleScenarioError(\"This scenario generation is no longer active. Reload the current scenario.\")",
    ),
]


def run_tests() -> tuple[bool, str]:
    completed = subprocess.run(
        [PYTHON, "-m", "pytest", *TESTS, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    output = completed.stdout.strip().splitlines()
    if output:
        return completed.returncode == 0, output[-1]
    errors = completed.stderr.strip().splitlines()
    return completed.returncode == 0, errors[-1] if errors else ""


def main() -> int:
    baseline_green, baseline_line = run_tests()
    print(f"baseline: {'GREEN' if baseline_green else 'RED'} | {baseline_line}")
    if not baseline_green:
        print("baseline is not green; fix the suite before mutation review")
        return 1

    survived: list[str] = []
    for label, path, old, new in MUTATIONS:
        original = path.read_text()
        if old not in original:
            print(f"SKIP  {label}: anchor text not found in {path.name}")
            survived.append(f"{label} (anchor missing)")
            continue
        try:
            path.write_text(original.replace(old, new, 1))
            green, line = run_tests()
        finally:
            path.write_text(original)
        if green:
            print(f"SURVIVED  {label} | {line}")
            survived.append(label)
        else:
            print(f"caught    {label} | {line}")

    print()
    if survived:
        print(f"{len(survived)} mutation(s) SURVIVED: those guards are not covered:")
        for item in survived:
            print(f"  - {item}")
        return 1
    print(f"all {len(MUTATIONS)} mutations were caught by the test suite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
