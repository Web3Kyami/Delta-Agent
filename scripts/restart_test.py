"""Real restart test: prove Delta's local Sibyl store can recall a completed job
from a fresh process. Reads back the work result and attempt that were persisted
in scripts/persist_phase7.py and prints a summary that confirms onchain provenance.

Run from a fresh `python scripts/restart_test.py` invocation — no module-level
caches, no in-memory state. Pure disk + DB read.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path("/root/projects/Delta")
sys.path.insert(0, str(PROJECT_ROOT))

from delta.core import Scope
from delta.store import SibylStore
from sibyl_memory_client import MemoryClient

# Use the same scope that persist_phase7.py used.
scope = Scope("delta-local-demo", "phase7-live-acp-75656")
db_path = PROJECT_ROOT / ".delta" / "demo-memory.db"
client = MemoryClient.local(str(db_path))
store = SibylStore(client, scope)

input_signature = "aaga-content-topic=ai-agents-in-defi-2026-09-02"
workflow_id = "live-acp-aaga-content"
step_id = "content_generation"

wr = store.get_work_result(workflow_id, step_id, input_signature)
att = store.get_attempt("attempt-75656")

# Check journal for completion event.
events = store.read_events(attempt_id="attempt-75656", limit=200)
recent_event = events[-1] if events else None

print("=" * 70)
print("RESTART TEST — fresh process, no in-memory cache")
print("=" * 70)
print(f"  scope:                 {scope.tenant_id} / {scope.project_id}")
print(f"  workflow_id:           {workflow_id}")
print(f"  step_id:               {step_id}")
print(f"  input_signature:       {input_signature}")
print()
print(f"  work_result present:   {wr is not None}")
print(f"  work_result status:    {wr.status if wr else None}")
if wr and wr.artifact:
    print(f"  artifact hash:         {wr.artifact.content_hash}")
    print(f"  artifact uri:          {wr.artifact.uri}")
if wr and wr.output:
    out = wr.output
    print(f"  output.tx_fund:        {out.get('tx_fund')}")
    print(f"  output.tx_settle:      {out.get('tx_settle')}")
    oc = out.get("onchain", {})
    print(f"  output.onchain.funded:    {oc.get('funded_usdc')} USDC")
    print(f"  output.onchain.settled:   {oc.get('settled_to_provider_usdc')} USDC")
    print(f"  output.onchain.refunded:  {oc.get('refunded_to_client_usdc')} USDC")
print()
print(f"  attempt present:       {att is not None}")
print(f"  attempt status:        {att.status if att else None}")
print(f"  provider_job_id:       {att.provider_job_id if att else None}")
print(f"  provider_chain_id:     {att.provider_chain_id if att else None}")
print()
print(f"  events for attempt:    {len(events)}")
if recent_event:
    print(f"  latest event reason:   {recent_event.get('reason_code')}")
    print(f"  latest event state:    {recent_event.get('state')}")
    detail = recent_event.get("detail", "")
    print(f"  latest event detail:   {detail[:100]}{'...' if len(detail) > 100 else ''}")
print()
# Verdict
ok = (
    wr is not None
    and wr.status == "completed"
    and wr.artifact is not None
    and wr.artifact.content_hash == "0x5c970be48a64875341e4596c4f6d3b8c34c2df2680d9f0a2d6a6cc96c2ec29f8"
    and att is not None
    and att.provider_job_id == "75656"
    and att.provider_chain_id == 8453
    and recent_event is not None
    and recent_event.get("state") == "succeeded"
)
print("=" * 70)
print("VERDICT:", "PASS — engine can resume and recall paid work" if ok else "FAIL")
print("=" * 70)
sys.exit(0 if ok else 1)
