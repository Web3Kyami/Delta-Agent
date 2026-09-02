"""Debug read_events for the Phase 7 attempt."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path("/root/projects/Delta")
sys.path.insert(0, str(PROJECT_ROOT))

from delta.core import Scope
from delta.store import SibylStore, _scope_payload
from sibyl_memory_client import MemoryClient

scope = Scope("delta-local-demo", "phase7-live-acp-75656")
db_path = PROJECT_ROOT / ".delta" / "demo-memory.db"
client = MemoryClient.local(str(db_path))
store = SibylStore(client, scope)

print("scope:", scope)
print("scope payload:", _scope_payload(scope))

raw_events = client.read_events(limit=200)
print(f"\nraw events from client: {len(raw_events)}")
for r in raw_events[:5]:
    e = r.get("extra") or {}
    print(f"  id={r['id'][:8]} scope={e.get('scope')} attempt={e.get('attempt_id')} state={e.get('state')}")

filtered = store.read_events(attempt_id="attempt-75656", limit=200)
print(f"\nfiltered for attempt-75656: {len(filtered)}")
for f in filtered:
    print(f"  {f.get('reason_code')} state={f.get('state')} attempt={f.get('attempt_id')}")
