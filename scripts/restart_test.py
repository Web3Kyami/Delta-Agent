"""Inspect the recorded ACP observation from a genuinely fresh process.

Run this after ``scripts/persist_phase7.py``. It reads only the persisted
attempt and journal event. A readable record is not live integration proof and
this script exits with status 2 until a real Delta ACP path and verified
artifact are recorded.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from delta.core import Scope
from delta.store import SibylStore


SCOPE = Scope("delta-local-demo", "phase7-live-acp-75656")
DB_PATH = PROJECT_ROOT / ".delta" / "phase7-recorded-observation.db"
ATTEMPT_ID = "attempt-75656"


def main() -> int:
    store = SibylStore.local(DB_PATH, SCOPE)
    attempt = store.get_attempt(ATTEMPT_ID)
    events = store.read_events(attempt_id=ATTEMPT_ID, limit=50)
    latest = events[-1] if events else None

    print("=" * 70)
    print("RECORDED ACP OBSERVATION CHECK - fresh process")
    print("=" * 70)
    print(f"  scope:       {SCOPE.tenant_id} / {SCOPE.project_id}")
    print(f"  attempt:     {attempt.status if attempt else None}")
    print(f"  job_id:      {attempt.provider_job_id if attempt else None}")
    print(f"  chain_id:    {attempt.provider_chain_id if attempt else None}")
    print(f"  events:      {len(events)}")
    print(f"  latest:      {latest.get('state') if latest else None}")
    print(f"  source:      {'recorded_fixture' if latest and 'recorded_fixture observation' in latest.get('detail', '') else 'unknown'}")
    print("  live proof:  not established")
    print("  artifact:    not verified")
    print("=" * 70)
    print("VERDICT: BLOCKED - persistence is readable, but this is not live ACP evidence")
    print("=" * 70)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
