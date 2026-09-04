from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlencode

from delta.web import DeltaWebApp


try:
    import sibyl_memory_client  # noqa: F401
except ImportError:
    SIBYL_AVAILABLE = False
else:
    SIBYL_AVAILABLE = True


class WebClient:
    def __init__(self, app: DeltaWebApp):
        self.app = app
        self.cookie = ""
        self.csrf = ""

    def request(self, path: str, method: str = "GET", payload: dict | None = None):
        body = json.dumps(payload).encode() if payload is not None else b""
        captured = {}

        def start_response(status, headers, _exc_info=None):
            captured["status"] = status
            captured["headers"] = headers

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path.split("?", 1)[0],
            "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
            "HTTP_COOKIE": self.cookie,
            "HTTP_X_CSRF_TOKEN": self.csrf,
        }
        response_body = b"".join(self.app(environ, start_response))
        for key, value in captured["headers"]:
            if key.lower() == "set-cookie":
                self.cookie = value.split(";", 1)[0]
            if key.lower() == "x-delta-csrf":
                self.csrf = value
        return captured["status"], response_body, dict(captured["headers"])

    def json(self, path: str, method: str = "GET", payload: dict | None = None):
        status, body, headers = self.request(path, method, payload)
        return status, json.loads(body), headers


@unittest.skipUnless(SIBYL_AVAILABLE, "sibyl-memory-client is required for the Phase 5 web path")
class PhaseFiveWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="delta-phase5-web-")
        self.app = DeltaWebApp(memory_path=Path(self.tempdir.name) / "memory.db")
        self.client = WebClient(self.app)
        self.client.json("/api/login", "POST", {"email": "demo@delta.local", "password": "delta-demo"})
        self.payload = {
            "project_id": "web-project-a",
            "description": "A compact solar charger for remote workdays",
            "brief": "Clean studio product shot, warm daylight",
            "launch_date": "2026-09-10",
            "target_language": "de",
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_server_renders_accessible_page_and_static_assets(self) -> None:
        status, body, headers = self.client.request("/")
        document = body.decode()
        self.assertEqual(status, "200 OK")
        self.assertIn("Change the request.", document)
        self.assertIn('href="/app/revisions"', document)
        self.assertIn('aria-label="Illustrative revision preview"', document)
        self.assertIn("/static/landing.css", document)
        self.assertIn("/static/favicon.svg", document)
        self.assertIn("no-store", headers["Cache-Control"])
        app_status, app_body, _ = self.client.request("/app/revisions")
        app_document = app_body.decode()
        self.assertEqual(app_status, "200 OK")
        self.assertIn("<label for=\"description\">", app_document)
        self.assertIn("Demo mode", app_document)
        self.assertIn("aria-live=\"polite\"", app_document)
        self.assertIn("/static/styles.css", app_document)
        self.assertIn('id="revision-lab"', app_document)
        self.assertIn('aria-busy="false"', app_document)
        self.assertIn('href="/app/runs"', app_document)
        css_status, css_body, _ = self.client.request("/static/styles.css")
        self.assertEqual(css_status, "200 OK")
        self.assertIn("prefers-reduced-motion", css_body.decode())
        js_status, js_body, _ = self.client.request("/static/app.js")
        self.assertEqual(js_status, "200 OK")
        self.assertIn("Inputs changed. Preview the current inputs again", js_body.decode())
        self.assertIn("Nothing new needs to run for these inputs", js_body.decode())
        self.assertIn("This page session expired. Refresh the page", js_body.decode())
        self.assertIn("nav-visible", js_body.decode())
        logo_status, logo_body, logo_headers = self.client.request("/static/logo.svg")
        self.assertEqual(logo_status, "200 OK")
        self.assertIn("image/svg+xml", logo_headers["Content-Type"])
        self.assertIn("<svg", logo_body.decode())

    def test_application_routes_have_distinct_active_pages(self) -> None:
        expected = {
            "/app/overview": "Launch Package",
            "/app/revisions": "What changed?",
            "/app/runs": "Runs",
            "/app/continuity": "Reconciliation context",
            "/app/integrations": "Runtime and evidence",
        }
        for path, heading in expected.items():
            status, body, _ = self.client.request(path)
            document = body.decode()
            self.assertEqual(status, "200 OK")
            self.assertIn(heading, document)
            self.assertIn('aria-current="page"', document)
            self.assertNotIn("{{", document)

        status, _, headers = self.client.request("/app")
        self.assertEqual(status, "302 Found")
        self.assertEqual(headers["Location"], "/app/overview")

    def test_workflow_routes_keep_the_progressive_flow(self) -> None:
        expected = {
            "/app/workflows/launch-package": "Workflow",
            "/app/workflows/launch-package/revise": "Change request",
            "/app/revisions/latest/preview": "Revision preview",
            "/app/revisions/latest/execute": "Execution",
            "/app/revisions/latest": "Revision complete",
            "/app/workflows/launch-package/history": "Workflow history",
            "/app/jobs/75656": "Reconciliation",
        }
        for path, title in expected.items():
            status, body, _ = self.client.request(path)
            document = body.decode()
            self.assertEqual(status, "200 OK")
            self.assertIn(f"<title>{title} | Delta</title>", document)
            self.assertNotIn("{{", document)

    def test_state_changes_require_csrf_and_valid_inputs(self) -> None:
        saved_csrf = self.client.csrf
        self.client.csrf = ""
        status, response, _ = self.client.json("/api/preview", "POST", self.payload)
        self.assertEqual(status, "422 Unprocessable Entity")
        self.assertIn("CSRF", response["message"])
        self.client.csrf = saved_csrf
        self.client.request("/")
        invalid = dict(self.payload, project_id="../other-project")
        status, response, _ = self.client.json("/api/preview", "POST", invalid)
        self.assertEqual(status, "422 Unprocessable Entity")
        self.assertIn("Project ID", response["message"])

    def test_preview_execute_and_changed_input_are_derived_from_sibyl(self) -> None:
        self.client.request("/")
        status, preview, _ = self.client.json("/api/preview", "POST", self.payload)
        self.assertEqual(status, "200 OK")
        self.assertEqual([step["decision"] for step in preview["steps"]], ["rerun", "rerun", "pending_dependency"])
        self.assertTrue(preview["live_actions"]["available"] is False)

        execute_payload = dict(self.payload, plan_id=preview["plan_id"])
        status, executed, _ = self.client.json("/api/execute", "POST", execute_payload)
        self.assertEqual(status, "200 OK")
        self.assertEqual(executed["execution"]["mode"], "deterministic_fixture")
        self.assertIsNone(executed["execution"]["actual_service_cost"])
        self.assertTrue(all(step["current_output"]["fixture"] for step in executed["steps"]))

        changed = dict(self.payload, launch_date="2026-09-11")
        status, changed_preview, _ = self.client.json("/api/preview", "POST", changed)
        self.assertEqual(status, "200 OK")
        self.assertEqual([step["decision"] for step in changed_preview["steps"]], ["reuse", "rerun", "pending_dependency"])
        self.assertEqual(changed_preview["steps"][0]["source"], "deterministic fixture")

        status, stale, _ = self.client.json("/api/execute", "POST", dict(changed, plan_id=preview["plan_id"]))
        self.assertEqual(status, "409 Conflict")
        self.assertIn("stale", stale["message"])

    def test_restore_uses_project_scope_and_unavailable_live_actions_are_honest(self) -> None:
        self.client.request("/")
        status, preview, _ = self.client.json("/api/preview", "POST", self.payload)
        self.assertEqual(status, "200 OK")
        self.client.json("/api/execute", "POST", dict(self.payload, plan_id=preview["plan_id"]))
        query = urlencode(self.payload)
        status, restored, _ = self.client.json(f"/api/state?{query}")
        self.assertEqual(status, "200 OK")
        self.assertEqual(restored["status"], "loaded")
        self.assertTrue(any(step["current_output"] for step in restored["steps"]))
        self.assertEqual(restored["recovery"]["source"], "Sibyl")
        status, blocked, _ = self.client.json("/api/reconcile", "POST", {})
        self.assertEqual(status, "409 Conflict")
        self.assertIn("unavailable", blocked["message"])

    def test_state_serializer_recovers_from_a_fresh_process(self) -> None:
        self.client.request("/")
        status, preview, _ = self.client.json("/api/preview", "POST", self.payload)
        self.assertEqual(status, "200 OK")
        status, executed, _ = self.client.json("/api/execute", "POST", dict(self.payload, plan_id=preview["plan_id"]))
        self.assertEqual(status, "200 OK")

        script = """
import json
import sys
from pathlib import Path

from delta.demo import demo_request
from delta.execute import DeltaEngine
from delta.store import SibylStore
from delta.web import DeltaWebApp

memory_path, project_id = sys.argv[1:]
values = {
    "description": "A compact solar charger for remote workdays",
    "brief": "Clean studio product shot, warm daylight",
    "launch_date": "2026-09-10",
    "target_language": "de",
}
request = demo_request(project_id, values)
store = SibylStore.local(Path(memory_path), request.scope)
plan = DeltaEngine(store).preview(request)
payload = DeltaWebApp(memory_path=memory_path)._state_payload(store, request, plan, status="loaded")
print(json.dumps(payload))
"""
        session = self.app.sessions.decode(self.client.cookie.split("=", 1)[1])
        child = subprocess.run(
            [sys.executable, "-c", script, str(self.app.memory_path), session.workspace_id],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
        restored = json.loads(child.stdout)
        self.assertEqual(restored["status"], "loaded")
        self.assertEqual(restored["recovery"]["source"], "Sibyl")
        self.assertTrue(all(step["current_output"] for step in restored["steps"]))
        self.assertEqual(restored["actual_cost_status"], "not_applicable_fixture")


if __name__ == "__main__":
    unittest.main()
