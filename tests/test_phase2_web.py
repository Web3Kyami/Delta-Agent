from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest

from tests.test_phase5_web import WebClient
from delta.demo import workspace_scope
from delta.session import DemoSession, SessionCodec, SessionError
from delta.store import SibylStore
from delta.web import DeltaWebApp


class PhaseTwoWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="delta-phase2-web-")
        self.addCleanup(self.directory.cleanup)
        self.app = DeltaWebApp(memory_path=Path(self.directory.name) / "memory.db")

    def login(self) -> WebClient:
        client = WebClient(self.app)
        status, payload, headers = client.json("/api/login", "POST", {"email": "demo@delta.local", "password": "delta-demo"})
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["display_name"], "Delta Dave")
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertTrue(client.csrf)
        return client

    def test_login_is_required_and_wrong_credentials_fail(self) -> None:
        client = WebClient(self.app)
        status, _, headers = client.request("/app/scenarios")
        self.assertEqual(status, "302 Found")
        self.assertEqual(headers["Location"], "/login")
        status, payload, _ = client.json("/api/login", "POST", {"email": "wrong", "password": "wrong"})
        self.assertEqual(status, "401 Error")
        self.assertIn("incorrect", payload["message"])
        status, body, _ = client.request("/login")
        self.assertEqual(status, "200 OK")
        self.assertIn("demo@delta.local", body.decode())
        self.assertIn("delta-demo", body.decode())

    def test_session_signature_and_expiry_are_verified(self) -> None:
        codec = SessionCodec("phase2-test-signing-secret")
        issued = datetime(2026, 9, 4, tzinfo=timezone.utc)
        session = DemoSession.create(now=issued)
        cookie = codec.encode(session)
        body, signature = cookie.split(".", 1)
        tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        with self.assertRaises(SessionError):
            codec.decode(f"{body}.{tampered_signature}")
        with self.assertRaises(SessionError):
            codec.decode(cookie, now=issued + timedelta(seconds=session.expires_at - session.issued_at))

    def test_sign_out_invalidates_the_session(self) -> None:
        client = self.login()
        status, payload, _ = client.json("/api/logout", "POST", {})
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["status"], "signed_out")
        status, payload, _ = client.json("/api/scenarios")
        self.assertEqual(status, "401 Error")
        self.assertEqual(payload["status"], "unauthenticated")

    def test_scenarios_initialize_in_isolated_workspace_and_scope(self) -> None:
        first = self.login()
        second = self.login()
        first_state = first.json("/api/scenarios/software")[1]
        second_state = second.json("/api/scenarios/software")[1]
        self.assertNotEqual(first_state["workspace_id"], second_state["workspace_id"])
        self.assertNotEqual(first_state["project_id"], second_state["project_id"])
        self.assertTrue(first_state["steps"][0]["current_output"])
        self.assertIsNone(first_state["steps"][1]["current_output"])
        self.assertEqual(first_state["steps"][1]["visibility"], "withheld")
        self.assertEqual(first.json("/api/scenarios")[1]["scenarios"][0]["opened"], True)

    def test_composite_scope_keeps_same_generation_workspaces_distinct(self) -> None:
        first = workspace_scope("a" * 32, "software", "g123456789ab")
        second = workspace_scope("b" * 32, "software", "g123456789ab")
        self.assertNotEqual(first.project_id, second.project_id)

    def test_legacy_surface_binds_state_to_the_signed_workspace(self) -> None:
        first = self.login()
        second = self.login()
        payload = {
            "project_id": "browser-chosen-but-ignored",
            "description": "A compact solar charger for remote workdays",
            "brief": "Clean studio product shot, warm daylight",
            "launch_date": "2026-09-10",
            "target_language": "de",
        }
        status, preview, _ = first.json("/api/preview", "POST", payload)
        self.assertEqual(status, "200 OK")
        status, _, _ = first.json("/api/execute", "POST", dict(payload, plan_id=preview["plan_id"]))
        self.assertEqual(status, "200 OK")
        status, second_preview, _ = second.json("/api/preview", "POST", payload)
        self.assertEqual(status, "200 OK")
        self.assertEqual([step["decision"] for step in second_preview["steps"]], ["rerun", "rerun", "pending_dependency"])

    def test_three_scenarios_share_engine_but_do_not_cross_reuse(self) -> None:
        client = self.login()
        states = {scenario_id: client.json(f"/api/scenarios/{scenario_id}")[1] for scenario_id in ("software", "repair", "research")}
        self.assertEqual(set(states), {"software", "repair", "research"})
        self.assertEqual(len({state["project_id"] for state in states.values()}), 3)
        self.assertEqual(len({state["workflow_id"] for state in states.values()}), 3)
        for state in states.values():
            self.assertEqual(state["mode"], "deterministic_fixture")
            self.assertEqual(state["steps"][0]["source"], "deterministic fixture")
            self.assertEqual(state["steps"][1]["visibility"], "withheld")

    def test_handoff_exposes_decisions_and_never_private_canary(self) -> None:
        client = self.login()
        state = client.json("/api/scenarios/software")[1]
        status, payload, _ = client.json(
            "/api/scenarios/software/handoff",
            "POST",
            {"brief": "Add a safe handoff boundary to the checkout service", "revision": "constraint-change", "generation": state["generation"]},
        )
        self.assertEqual(status, "200 OK")
        handoff = payload["handoff"]
        decisions = {item["step_id"]: item for item in handoff["decisions"]}
        self.assertEqual(decisions["shared_context"]["decision"], "reuse")
        self.assertEqual(decisions["private_notes"]["decision"], "blocked")
        self.assertEqual(decisions["revision_output"]["decision"], "rerun")
        self.assertEqual(decisions["dependent_summary"]["decision"], "pending_dependency")
        encoded = json.dumps(handoff, sort_keys=True)
        self.assertNotIn("PRIVATE-CANARY", encoded)
        self.assertEqual(handoff["approved_context"]["excluded_work"][0]["decision"], "blocked")

    def test_reset_deletes_scope_entities_retains_journal_and_rejects_stale_generation(self) -> None:
        client = self.login()
        before = client.json("/api/scenarios/repair")[1]
        old_generation = before["generation"]
        old_cookie = client.cookie
        old_csrf = client.csrf
        # Use the full signed workspace identity from the session cookie to
        # address the exact old scope, then verify reset clears this HOT head.
        session = self.app.sessions.decode(client.cookie.split("=", 1)[1])
        old_scope = workspace_scope(session.workspace_id, "repair", old_generation)
        old_store = SibylStore.local(self.app.memory_path, old_scope)
        old_store.set_active_attempt("shared_context", "attempt-before-reset")
        client.json("/api/scenarios/repair/handoff", "POST", {"generation": old_generation})
        status, reset, _ = client.json("/api/scenarios/repair/reset", "POST", {"generation": old_generation})
        self.assertEqual(status, "200 OK")
        self.assertEqual(reset["reset"]["journal_history"], "retained_append_only")
        self.assertEqual(sum(reset["reset"]["deleted_entities"].values()), 11)
        self.assertNotEqual(reset["generation"], old_generation)
        self.assertIsNone(old_store.get_active_attempt("shared_context"))
        stale_client = WebClient(self.app)
        stale_client.cookie = old_cookie
        stale_client.csrf = old_csrf
        status, stale_state, _ = stale_client.json("/api/scenarios/repair")
        self.assertEqual(status, "409 Conflict")
        self.assertEqual(stale_state["status"], "stale_generation")
        status, stale, _ = client.json("/api/scenarios/repair/handoff", "POST", {"generation": old_generation})
        self.assertEqual(status, "409 Conflict")
        self.assertEqual(stale["status"], "stale_generation")
        after = client.json("/api/scenarios/repair")[1]
        self.assertEqual(after["generation"], reset["generation"])
        self.assertTrue(after["steps"][0]["current_output"])
        self.assertIsNone(after["steps"][1]["current_output"])

    def test_reset_one_scenario_does_not_change_another(self) -> None:
        client = self.login()
        repair = client.json("/api/scenarios/repair")[1]
        research = client.json("/api/scenarios/research")[1]
        status, _, _ = client.json("/api/scenarios/repair/reset", "POST", {"generation": repair["generation"]})
        self.assertEqual(status, "200 OK")
        research_after = client.json("/api/scenarios/research")[1]
        self.assertEqual(research_after["generation"], research["generation"])
        self.assertEqual(research_after["project_id"], research["project_id"])

    def test_concurrent_resets_are_serialized_within_the_process(self) -> None:
        owner = self.login()
        state = owner.json("/api/scenarios/software")[1]
        clients = []
        for _ in range(2):
            client = WebClient(self.app)
            client.cookie = owner.cookie
            client.csrf = owner.csrf
            clients.append(client)

        def reset(client: WebClient):
            return client.json("/api/scenarios/software/reset", "POST", {"generation": state["generation"]})

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reset, clients))
        self.assertEqual(sorted(status for status, _, _ in results), ["200 OK", "409 Conflict"])
        successful = next(payload for status, payload, _ in results if status == "200 OK")
        rejected = next(payload for status, payload, _ in results if status == "409 Conflict")
        self.assertEqual(sum(successful["reset"]["deleted_entities"].values()), 9)
        self.assertEqual(rejected["status"], "stale_generation")

    def test_fresh_process_restores_workspace_and_scenario(self) -> None:
        client = self.login()
        original = client.json("/api/scenarios/software")[1]
        other = self.login()
        other_state = other.json("/api/scenarios/software")[1]
        self.assertNotEqual(other_state["project_id"], original["project_id"])
        child = """
import io, json, sys
from delta.web import DeltaWebApp

app = DeltaWebApp(memory_path=sys.argv[1])
captured = {}
def start_response(status, headers, _exc_info=None):
    captured['status'] = status
body = b''.join(app({
    'REQUEST_METHOD': 'GET',
    'PATH_INFO': '/api/scenarios/software',
    'QUERY_STRING': '',
    'CONTENT_LENGTH': '0',
    'wsgi.input': io.BytesIO(b''),
    'HTTP_COOKIE': sys.argv[2],
}, start_response))
if captured['status'] != '200 OK':
    raise SystemExit(captured['status'])
print(json.dumps(json.loads(body), sort_keys=True))
"""
        completed = subprocess.run(
            [sys.executable, "-c", child, str(self.app.memory_path), client.cookie],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
        restored = json.loads(completed.stdout)
        self.assertEqual(restored["workspace_id"], original["workspace_id"])
        self.assertEqual(restored["project_id"], original["project_id"])
        self.assertEqual(restored["generation"], original["generation"])
        self.assertTrue(restored["steps"][0]["current_output"])
        self.assertIsNone(restored["steps"][1]["current_output"])

        other_process = subprocess.run(
            [sys.executable, "-c", child, str(self.app.memory_path), other.cookie],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
        other_restored = json.loads(other_process.stdout)
        self.assertEqual(other_restored["project_id"], other_state["project_id"])
        self.assertNotEqual(other_restored["project_id"], restored["project_id"])

    def test_public_session_cannot_invoke_live_action(self) -> None:
        client = WebClient(self.app)
        status, payload, _ = client.json("/api/approve", "POST", {})
        self.assertEqual(status, "401 Error")
        self.assertEqual(payload["status"], "unauthenticated")
        client = self.login()
        status, payload, _ = client.json("/api/approve", "POST", {})
        self.assertEqual(status, "409 Conflict")
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("unavailable", payload["message"])


if __name__ == "__main__":
    unittest.main()
