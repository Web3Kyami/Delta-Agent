"""Persist the Phase 7 live ACP job 75656 into Delta's local Sibyl store.

Idempotent: deletes prior records under the same input_signature first, then saves
a fresh WorkResult + ExecutionAttempt and appends a transition event.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path("/root/projects/Delta")
sys.path.insert(0, str(PROJECT_ROOT))

from delta.core import (
    ArtifactReference,
    CostEstimate,
    ExecutionAttempt,
    ExecutionEvent,
    Scope,
    StepDecision,
    WorkResult,
    output_signature,
)
from delta.store import SibylStore
from sibyl_memory_client import MemoryClient

scope = Scope("delta-local-demo", "phase7-live-acp-75656")
db_path = PROJECT_ROOT / ".delta" / "demo-memory.db"
db_path.parent.mkdir(parents=True, exist_ok=True)

client = MemoryClient.local(str(db_path))
store = SibylStore(client, scope)

now = datetime.now(timezone.utc)

# --- Clean prior records (idempotent) ---
import sqlite3
conn = sqlite3.connect(str(db_path))
c = conn.cursor()
c.execute(
    "DELETE FROM entities WHERE category='delta.work_result.v1' AND body LIKE ?",
    ("%aaga-content-topic=ai-agents-in-defi-2026-09-02%",),
)
c.execute(
    "DELETE FROM entities WHERE category='delta.execution_attempt.v1' AND body LIKE ?",
    ("%attempt-75656%",),
)
# journal_events uses `extra` not `body` — clean any prior phase7 events there too.
c.execute(
    "DELETE FROM journal_events WHERE extra LIKE ?",
    ("%phase7-live-acp-75656%",),
)
conn.commit()
n_cleaned = c.rowcount
conn.close()
print(f"cleaned {n_cleaned} prior records")

# --- Work result ---
art = ArtifactReference(
    artifact_id="delta/artifact/v1/aaga-content-75656",
    content_hash="0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8",
    media_type="text/markdown",
    byte_size=2644,
    uri="acp://base/8453/job/75656/submit-tx/0xd393763b6560a80d49317f7f11edf9ab349835aa0420ee4c928e5dd1a1dda445",
    available=True,
)
cost = CostEstimate(
    amount="0.001",  # net cost (0.01 - 0.009 settled)
    currency="USDC",
    source="acp.base.8453",
    quoted_at=now,
)
output = {
    "title": "AI agents in DeFi - Blog post",
    "word_count": 159,
    "generation_method": "template",
    "tx_fund": "0xd1d284d10916bc90934b876cec1ee3242a27de026bbd2b8191d532071f48425d",
    "tx_settle": "0x1062a1b78bf8e5686894e9e091b4b857559b784bf8a24f8f0177067957788ff8",
    "onchain": {
        "chain_id": 8453,
        "base_url": "https://basescan.org/address/0x702Ab9EcFB9F87F52e79157b2EA6A929B60eC576",
        "funded_usdc": "0.01",
        "settled_to_provider_usdc": "0.009",
        "refunded_to_client_usdc": "0.001",
        "deliverable_hash_onchain": "0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8",
    },
}
wr = WorkResult(
    scope=scope,
    workflow_id="live-acp-aaga-content",
    step_id="content_generation",
    implementation_id="acp-v2@aaga/content_generation",
    input_signature="aaga-content-topic=ai-agents-in-defi-2026-09-02",
    output_signature=output_signature(output),  # computed from normalized output
    output=output,
    completed_at=now,
    fresh_until=None,  # not in cache; will refresh on next read
    successful_attempt_id="attempt-75656",
    artifact=art,
    status="completed",
)
store.save_work_result(wr)
print("saved work_result for job 75656")

# --- Execution attempt ---
attempt = ExecutionAttempt(
    scope=scope,
    attempt_id="attempt-75656",
    workflow_id="live-acp-aaga-content",
    step_id="content_generation",
    status="succeeded",
    input_signature="aaga-content-topic=ai-agents-in-defi-2026-09-02",
    provider_job_id="75656",
    provider_chain_id=8453,
    error_code=None,
)
store.save_attempt(attempt)
print("saved attempt for job 75656")

# --- Read back ---
wr2 = store.get_work_result(
    "live-acp-aaga-content",
    "content_generation",
    "aaga-content-topic=ai-agents-in-defi-2026-09-02",
)
print(f"read back work_result: present={wr2 is not None} status={wr2.status if wr2 else None}")
if wr2 and wr2.artifact:
    print(f"  artifact content_hash: {wr2.artifact.content_hash}")
    print(f"  artifact uri: {wr2.artifact.uri}")

att2 = store.get_attempt("attempt-75656")
print(
    f"read back attempt: present={att2 is not None} "
    f"status={att2.status if att2 else None} "
    f"job_id={att2.provider_job_id if att2 else None} "
    f"chain={att2.provider_chain_id if att2 else None}"
)

# --- Append event ---
ev = ExecutionEvent(
    event_id="event-75656-completed",
    scope=scope,
    attempt_id="attempt-75656",
    reason_code="acp.job.completed",
    state="succeeded",
    detail="acp://base/8453/job/75656 settle tx=0x1062a1b78bf8e5686894e9e091b4b857559b784bf8a24f8f0177067957788ff8 net_cost=0.001 USDC deliverable_hash=0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8",
    recorded_at=now,
)
store.append_event(ev)
print("appended event")

# --- Final state ---
conn = sqlite3.connect(str(db_path))
c = conn.cursor()
c.execute(
    "SELECT category, COUNT(*) FROM entities WHERE tenant_id=? GROUP BY category ORDER BY category",
    (scope.tenant_id,),
)
print(f"\nentities for tenant {scope.tenant_id}:")
for cat, n in c.fetchall():
    print(f"  {cat}: {n}")
conn.close()
