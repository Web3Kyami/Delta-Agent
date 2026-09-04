"""Mutation review for Phase 1: remove each guard, prove a test fails.

Each mutation edits a real source file in place, runs a targeted test selection,
restores the file, and reports whether the suite caught the removal. A mutation
that leaves the suite green means the corresponding test is not evidence.

Run: .venv/bin/python scripts/phase1_mutation_review.py
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / ".venv" / "bin" / "python")

HANDOFF = ROOT / "delta" / "handoff.py"
STORE = ROOT / "delta" / "store.py"
CORE = ROOT / "delta" / "core.py"
EXECUTE = ROOT / "delta" / "execute.py"

GATE_TESTS = ["tests/test_phase1_handoff.py", "tests/test_phase1_handoff_exit_gate.py"]

# (label, file, old_text, new_text, tests to run)
MUTATIONS = [
    (
        "gate: external-exposure rule removed from authorization",
        HANDOFF,
        """        if (
            policy.external_exposure_rule is ExternalExposureRule.SHAREABLE_ONLY
            and provenance.external_exposure is not ExternalExposure.SHAREABLE
        ):""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "gate: same-provider rule removed",
        HANDOFF,
        """            if request.recipient.provider_id != provenance.source_provider_id:""",
        """            if False:""",
        GATE_TESTS,
    ),
    (
        "gate: provider allowlist check removed",
        HANDOFF,
        """            if request.recipient.provider_id not in allowlist:""",
        """            if False:""",
        GATE_TESTS,
    ),
    (
        "gate: agent allowlist check removed",
        HANDOFF,
        """        if policy.agent_allowlist is not None and request.recipient.agent_id not in policy.agent_allowlist:""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "gate: missing provenance treated as trusted",
        HANDOFF,
        """        if provenance is None:
            return Verdict(
                TrustStatus.UNTRUSTED,
                "PROVENANCE_MISSING",""",
        """        if False:
            return Verdict(
                TrustStatus.UNTRUSTED,
                "PROVENANCE_MISSING",""",
        GATE_TESTS,
    ),
    (
        "gate: unknown work category authorized by default",
        HANDOFF,
        """        if policy is None:
            return Verdict(
                AuthorizationStatus.UNAUTHORIZED,
                "NO_POLICY_FOR_WORK_CATEGORY",""",
        """        if False:
            return Verdict(
                AuthorizationStatus.UNAUTHORIZED,
                "NO_POLICY_FOR_WORK_CATEGORY",""",
        GATE_TESTS,
    ),
    (
        "gate: recipient project scope check removed",
        HANDOFF,
        """        if policy.recipient_scope != request.scope:""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "gate: freshness check removed from validity",
        HANDOFF,
        """        if not result.is_fresh(now):""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "gate: input-signature match dropped from validity",
        HANDOFF,
        """        if not matched_signature or result.input_signature != signature:""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "gate: implementation identity dropped from validity",
        HANDOFF,
        """        if result.implementation_id != step.implementation_id:""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "gate: unavailable artifact allowed to reuse",
        HANDOFF,
        """        if result.artifact is not None and not result.artifact.available:""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "gate: unsettled external job no longer blocks",
        HANDOFF,
        """        if verdicts.external_job.status in {
            ExternalJobStatus.RECONCILIATION_REQUIRED,
            ExternalJobStatus.UNSAFE,
        }:""",
        """        if False:""",
        GATE_TESTS,
    ),
    (
        "ApprovedWorkItem: approval re-check removed",
        HANDOFF,
        """        if not self.decision.approved or not self.decision.verdicts.approves_inheritance():
            raise HandoffPolicyError("approved work requires an approved handoff decision")""",
        """        pass""",
        GATE_TESTS,
    ),
    (
        "ApprovedWorkItem: output/signature agreement removed",
        HANDOFF,
        """        if output_signature(self.output) != self.output_signature:
            raise HandoffPolicyError("approved work output does not match its signature")""",
        """        pass""",
        GATE_TESTS,
    ),
    (
        "ApprovedContext: unapproved item admitted",
        HANDOFF,
        """            if not item.decision.approved:
                raise HandoffPolicyError("approved context rejected an unapproved decision")""",
        """            pass""",
        GATE_TESTS,
    ),
    (
        "ApprovedContext: approved+blocked overlap allowed",
        HANDOFF,
        """        if blocked_steps & set(approved_steps):
            raise HandoffPolicyError("a step cannot be both approved and blocked")""",
        """        pass""",
        GATE_TESTS,
    ),
    (
        "HandoffDecision: reuse without approving verdicts allowed",
        HANDOFF,
        """        if self.decision is DecisionKind.REUSE and not self.verdicts.approves_inheritance():
            raise HandoffPolicyError("a reuse decision requires every verdict to approve")""",
        """        pass""",
        GATE_TESTS,
    ),
    (
        "ReuseReceipt: count/entry agreement removed",
        HANDOFF,
        """        if dict(self.counts) != recomputed:
            raise HandoffPolicyError("receipt counts do not match its entries")""",
        """        pass""",
        GATE_TESTS,
    ),
    (
        "gate: undecodable record silently disappears",
        HANDOFF,
        """            if candidate_result is None and fallback is None and step.id in corrupt:""",
        """            if False:""",
        GATE_TESTS,
    ),
    (
        "store: output body allowed inside handoff records",
        STORE,
        """                if present:
                    raise SibylPersistenceError(""",
        """                if False:
                    raise SibylPersistenceError(""",
        GATE_TESTS,
    ),
    (
        "store: provenance not persisted with work results",
        STORE,
        """            "provenance": _provenance_payload(result.provenance),""",
        """            "provenance": None,""",
        GATE_TESTS,
    ),
    (
        "store: corrupt records swallowed instead of reported",
        STORE,
        """            except (DeltaValidationError, SibylPersistenceError, KeyError) as error:
                corrupt.append(""",
        """            except (DeltaValidationError, SibylPersistenceError, KeyError) as error:
                [].append(""",
        GATE_TESTS,
    ),
    (
        "engine: provenance never attached to new work",
        EXECUTE,
        """                    provenance=self._provenance_for(step, current_time),""",
        """                    provenance=None,""",
        GATE_TESTS,
    ),
    (
        "core: WorkResult accepts a non-WorkProvenance value",
        CORE,
        """        if self.provenance is not None and not isinstance(self.provenance, WorkProvenance):
            raise DeltaValidationError("provenance must be a WorkProvenance")""",
        """        pass""",
        GATE_TESTS,
    ),
]


def run_tests(tests: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        [PYTHON, "-m", "pytest", *tests, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0, completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""


def main() -> int:
    baseline_green, baseline_line = run_tests(GATE_TESTS)
    print(f"baseline: {'GREEN' if baseline_green else 'RED'} | {baseline_line}")
    if not baseline_green:
        print("baseline is not green; fix the suite before mutation review")
        return 1

    survived: list[str] = []
    for label, path, old, new, tests in MUTATIONS:
        original = path.read_text()
        if old not in original:
            print(f"SKIP  {label}: anchor text not found in {path.name}")
            survived.append(f"{label} (anchor missing)")
            continue
        try:
            path.write_text(original.replace(old, new, 1))
            green, line = run_tests(tests)
        finally:
            path.write_text(original)
        if green:
            print(f"SURVIVED  {label} | {line}")
            survived.append(label)
        else:
            print(f"caught    {label} | {line}")

    print()
    if survived:
        print(f"{len(survived)} mutation(s) SURVIVED — those guards are not covered:")
        for item in survived:
            print(f"  - {item}")
        return 1
    print(f"all {len(MUTATIONS)} mutations were caught by the test suite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
