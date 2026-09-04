from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest

from delta.web import DeltaWebApp


class PhaseFourClient:
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

        environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body), "HTTP_COOKIE": self.cookie, "HTTP_X_CSRF_TOKEN": self.csrf}
        response = b"".join(self.app(environ, start_response))
        for key, value in captured["headers"]:
            if key.lower() == "set-cookie":
                self.cookie = value.split(";", 1)[0]
            if key.lower() == "x-delta-csrf":
                self.csrf = value
        return captured["status"], response.decode(), dict(captured["headers"])


class PhaseFourWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="delta-phase4-web-")
        self.client = PhaseFourClient(DeltaWebApp(memory_path=Path(self.tempdir.name) / "memory.db"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_landing_leads_with_handoff_boundary(self) -> None:
        status, body, _ = self.client.request("/")
        self.assertEqual(status, "200 OK")
        self.assertIn("The next agent gets", body)
        self.assertIn("Agent A", body)
        self.assertIn("Agent B", body)
        self.assertIn('href="/app/scenarios"', body)
        self.assertIn('href="#boundary"', body)
        self.assertNotIn("{{", body)

    def test_scenario_routes_require_authentication_and_render_without_placeholders(self) -> None:
        status, _, headers = self.client.request("/app/scenarios")
        self.assertEqual(status, "302 Found")
        self.assertEqual(headers["Location"], "/login")
        self.client.request("/api/login", "POST", {"email": "demo@delta.local", "password": "delta-demo"})
        for path, marker in (("/app/scenarios", "Choose the work Agent B should inherit."), ("/app/scenarios/software", "AI software-work handoff")):
            status, body, headers = self.client.request(path)
            self.assertEqual(status, "200 OK")
            self.assertIn(marker, body)
            self.assertIn("/static/scenario.css", body)
            self.assertIn("/static/scenario.js", body)
            self.assertNotIn("{{", body)
            self.assertEqual(headers["Cache-Control"], "no-store")

    def test_scenario_assets_and_sign_out_are_available(self) -> None:
        self.client.request("/api/login", "POST", {"email": "demo@delta.local", "password": "delta-demo"})
        css_status, css, _ = self.client.request("/static/scenario.css")
        js_status, js, _ = self.client.request("/static/scenario.js")
        self.assertEqual(css_status, "200 OK")
        self.assertIn("prefers-reduced-motion", css)
        self.assertEqual(js_status, "200 OK")
        self.assertIn("deterministic_fixture", js)
        status, body, _ = self.client.request("/api/logout", "POST", {})
        self.assertEqual(status, "200 OK")
        self.assertIn("signed_out", body)
        status, _, headers = self.client.request("/app/scenarios")
        self.assertEqual(status, "302 Found")
        self.assertEqual(headers["Location"], "/login")


if __name__ == "__main__":
    unittest.main()
