"""Small server-rendered local demonstration for Delta."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
from typing import Any, Callable
from urllib.parse import parse_qs

from .core import DecisionKind, InputValidationError, RevisionRequest
from .demo import DEMO_WORKFLOW_ID, demo_request
from .execute import DeltaEngine
from .store import SibylStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_PATH = PROJECT_ROOT / ".delta" / "demo-memory.db"
TEMPLATE_ROOT = Path(__file__).with_name("templates")
LANDING_TEMPLATE_PATH = TEMPLATE_ROOT / "landing.html"
APP_TEMPLATE_PATH = TEMPLATE_ROOT / "index.html"
STATIC_ROOT = Path(__file__).with_name("static")
MAX_BODY_BYTES = 32 * 1024
APP_VIEWS = {
    "/app/overview": ("overview", "Overview"),
    "/app/workflows/launch-package": ("overview", "Workflow"),
    "/app/workflows/launch-package/revise": ("revisions", "Change request"),
    "/app/workflows/launch-package/history": ("runs", "Workflow history"),
    "/app/revisions": ("revisions", "Revisions"),
    "/app/revisions/latest/preview": ("revisions", "Revision preview"),
    "/app/revisions/latest/execute": ("runs", "Execution"),
    "/app/revisions/latest": ("runs", "Revision complete"),
    "/app/runs": ("runs", "Runs"),
    "/app/continuity": ("continuity", "Continuity"),
    "/app/integrations": ("integrations", "Integrations"),
}


class DeltaWebApp:
    """WSGI application that keeps all state-changing work on the server."""

    def __init__(self, *, memory_path: str | Path | None = None) -> None:
        configured_path = memory_path or os.environ.get("DELTA_DEMO_MEMORY_PATH") or DEFAULT_MEMORY_PATH
        self.memory_path = Path(configured_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.csrf_token = secrets.token_urlsafe(24)

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        try:
            if path == "/" and method == "GET":
                return self._respond_landing(environ, start_response)
            if path == "/app" and method == "GET":
                return self._redirect(start_response, "/app/overview")
            if path.startswith("/app/jobs/") and method == "GET":
                return self._respond_app(environ, start_response, "continuity", "Reconciliation")
            if path in APP_VIEWS and method == "GET":
                return self._respond_app(environ, start_response, *APP_VIEWS[path])
            if path.startswith("/static/") and method == "GET":
                return self._respond_static(path, start_response)
            if path == "/api/state" and method == "GET":
                return self._handle_state(environ, start_response)
            if path == "/api/preview" and method == "POST":
                return self._handle_preview(environ, start_response)
            if path == "/api/execute" and method == "POST":
                return self._handle_execute(environ, start_response)
            if path in {"/api/reconcile", "/api/approve", "/api/settle"} and method == "POST":
                return self._handle_unavailable_action(environ, start_response, path)
            return self._json(start_response, {"status": "error", "message": "The requested route does not exist."}, 404)
        except (InputValidationError, ValueError) as error:
            return self._json(start_response, {"status": "error", "message": str(error)}, 422)
        except Exception:
            return self._json(
                start_response,
                {
                    "status": "error",
                    "message": "Delta could not complete this request. Check Sibyl availability and try again.",
                },
                503,
            )

    def _respond_landing(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        body = LANDING_TEMPLATE_PATH.read_bytes()
        headers = [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")]
        if self._cookie(environ, "delta_csrf") != self.csrf_token:
            headers.append(("Set-Cookie", f"delta_csrf={self.csrf_token}; Path=/; SameSite=Strict"))
        start_response("200 OK", headers)
        return [body]

    def _respond_app(self, environ: dict[str, Any], start_response: Callable[..., Any], view: str, title: str):
        document = APP_TEMPLATE_PATH.read_text()
        document = document.replace("{{VIEW}}", view).replace("{{PAGE_TITLE}}", title)
        nav_view = {
            "overview": "overview",
            "revisions": "overview",
            "runs": "runs",
            "continuity": "runs",
            "integrations": "integrations",
        }.get(view, view)
        for candidate in ("overview", "revisions", "runs", "continuity", "integrations"):
            document = document.replace(f"{{{{ACTIVE_{candidate.upper()}}}}}", "active" if candidate == nav_view else "")
            document = document.replace(f"{{{{CURRENT_{candidate.upper()}}}}}", 'aria-current="page"' if candidate == nav_view else "")
            document = document.replace(f"{{{{HIDDEN_{candidate.upper()}}}}}", "" if candidate == view else "hidden")
        body = document.encode()
        cookie = self._cookie(environ, "delta_csrf")
        headers = [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")]
        if cookie != self.csrf_token:
            headers.append(("Set-Cookie", f"delta_csrf={self.csrf_token}; Path=/; SameSite=Strict"))
        start_response("200 OK", headers)
        return [body]

    @staticmethod
    def _redirect(start_response: Callable[..., Any], location: str):
        start_response("302 Found", [("Location", location), ("Cache-Control", "no-store")])
        return [b""]

    def _respond_static(self, path: str, start_response: Callable[..., Any]):
        relative = path.removeprefix("/static/")
        content_types = {
            "styles.css": "text/css; charset=utf-8",
            "app.js": "text/javascript; charset=utf-8",
            "landing.css": "text/css; charset=utf-8",
            "landing.js": "text/javascript; charset=utf-8",
            "logo.svg": "image/svg+xml",
            "favicon.svg": "image/svg+xml",
            "solar-charger-campaign.png": "image/png",
        }
        if relative not in content_types:
            return self._json(start_response, {"status": "error", "message": "Static asset not found."}, 404)
        asset = STATIC_ROOT / relative
        if relative == "landing.css":
            body = asset.read_bytes() + b"\n" + (STATIC_ROOT / "hero.css").read_bytes()
        elif relative == "styles.css":
            body = asset.read_bytes() + b"\n" + (STATIC_ROOT / "app-overrides.css").read_bytes()
        else:
            body = asset.read_bytes()
        start_response("200 OK", [("Content-Type", content_types[relative]), ("Cache-Control", "no-cache")])
        return [body]

    def _handle_state(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        payload = {key: values[-1] for key, values in query.items() if values}
        request = self._request_from_payload(payload)
        store = self._store(request)
        plan = DeltaEngine(store).preview(request)
        return self._json(start_response, self._state_payload(store, request, plan, status="loaded"), 200)

    def _handle_preview(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        self._require_csrf(environ)
        payload = self._read_json(environ)
        request = self._request_from_payload(payload)
        store = self._store(request)
        engine = DeltaEngine(store)
        plan = engine.preview(request)
        store.save_plan(plan)
        return self._json(start_response, self._state_payload(store, request, plan, status="previewed"), 200)

    def _handle_execute(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        self._require_csrf(environ)
        payload = self._read_json(environ)
        request = self._request_from_payload(payload)
        requested_plan_id = payload.get("plan_id")
        if not isinstance(requested_plan_id, str) or not requested_plan_id:
            return self._json(start_response, {"status": "blocked", "message": "Preview this exact input before executing it."}, 409)
        store = self._store(request)
        engine = DeltaEngine(store)
        current_plan = engine.preview(request)
        if requested_plan_id != current_plan.plan_id:
            return self._json(
                start_response,
                {"status": "blocked", "message": "The preview is stale because the inputs or saved work changed. Preview the current inputs again before executing."},
                409,
            )
        if store.get_plan(requested_plan_id) is None:
            return self._json(
                start_response,
                {"status": "blocked", "message": "The preview is no longer available in Sibyl. Preview the current inputs again before executing."},
                409,
            )
        report = engine.execute(request)
        refreshed_plan = engine.preview(request)
        result = self._state_payload(store, request, refreshed_plan, status="executed")
        result["execution"] = {
            "mode": "deterministic_fixture",
            "message": "The configured local fixture path ran and persisted its input-sensitive outputs through Sibyl.",
            "outputs": report.outputs,
            "estimated_additional_service_cost": report.costs.estimated_additional_service_cost.amount if report.costs.estimated_additional_service_cost else None,
            "actual_service_cost": None,
            "actual_cost_status": "not_applicable_fixture",
        }
        return self._json(start_response, result, 200)

    def _handle_unavailable_action(self, environ: dict[str, Any], start_response: Callable[..., Any], path: str):
        self._require_csrf(environ)
        action = {"/api/reconcile": "reconciliation", "/api/approve": "spending approval", "/api/settle": "settlement"}[path]
        return self._json(
            start_response,
            {
                "status": "blocked",
                "message": f"{action.title()} is unavailable in local deterministic fixture mode. No live ACP job is attached.",
            },
            409,
        )

    def _state_payload(self, store: SibylStore, request: RevisionRequest, plan, *, status: str) -> dict[str, Any]:
        steps = []
        for decision in plan.decisions:
            result = None
            if decision.input_signature:
                result = store.get_work_result(request.workflow.id, decision.step_id, decision.input_signature)
            attempt = None
            active_id = store.get_active_attempt(decision.step_id)
            if active_id:
                attempt = store.get_attempt(active_id)
            current_state = decision.decision.value
            if attempt is not None:
                current_state = {
                    "submitting": "awaiting_quote",
                    "active": "funded_awaiting_provider",
                    "ambiguous": "ambiguous",
                    "reconciliation_required": "reconciliation_required",
                }.get(attempt.status, attempt.status)
            if result is not None and result.artifact is not None and not result.artifact.available:
                current_state = "artifact_unavailable"
            steps.append(
                {
                    "id": decision.step_id,
                    "label": {"visual": "Product visual", "announcement": "Announcement", "translation": "Translation"}.get(decision.step_id, decision.step_id),
                    "decision": decision.decision.value,
                    "state": current_state,
                    "reason": decision.reason,
                    "reason_code": decision.reason_code,
                    "estimated_cost": self._cost_payload(decision.estimated_cost),
                    "current_output": result.output if result is not None else None,
                    "completed_at": result.completed_at.isoformat() if result is not None else None,
                    "artifact": self._artifact_payload(result.artifact) if result is not None and result.artifact else None,
                    "provider": None,
                    "job_id": attempt.provider_job_id if attempt is not None else None,
                    "chain_id": attempt.provider_chain_id if attempt is not None else None,
                    "actual_cost": None,
                    "actual_cost_status": "not_applicable_fixture" if result is not None and self._is_fixture(result.output) else "unknown",
                    "source": "deterministic fixture" if result is not None and self._is_fixture(result.output) else "none",
                }
            )
        estimated = [item["estimated_cost"] for item in steps if item["estimated_cost"] is not None]
        return {
            "status": status,
            "mode": "deterministic_fixture",
            "project_id": request.scope.project_id,
            "workflow_id": request.workflow.id,
            "plan_id": plan.plan_id,
            "inputs": dict(request.inputs),
            "steps": steps,
            "estimated_additional_service_cost": sum((float(item["amount"]) for item in estimated if item.get("amount") is not None), 0.0) if estimated else None,
            "estimated_cost_currency": "USDC",
            "estimated_cost_source": "deterministic fixture" if estimated else "unknown",
            "actual_service_cost": None,
            "actual_cost_status": "not_applicable_fixture",
            "recovery": {"source": "Sibyl", "fresh_process_safe": True, "message": "Reloading this project reads persisted work from Sibyl."},
            "live_actions": {"available": False, "reason": "No live ACP job or spending approval is attached to this local fixture run."},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _is_fixture(output: Any) -> bool:
        return isinstance(output, dict) and output.get("fixture") is True

    @staticmethod
    def _cost_payload(cost: Any) -> dict[str, Any] | None:
        if cost is None:
            return None
        return {"amount": cost.amount, "currency": cost.currency, "source": cost.source}

    @staticmethod
    def _artifact_payload(artifact: Any) -> dict[str, Any]:
        return {
            "artifact_id": artifact.artifact_id,
            "content_hash": artifact.content_hash,
            "media_type": artifact.media_type,
            "byte_size": artifact.byte_size,
            "uri": artifact.uri,
            "available": artifact.available,
        }

    def _store(self, request: RevisionRequest) -> SibylStore:
        return SibylStore.local(self.memory_path, request.scope)

    @staticmethod
    def _request_from_payload(payload: dict[str, Any]) -> RevisionRequest:
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        project_id = payload.get("project_id")
        values = {key: payload.get(key) for key in ("description", "brief", "launch_date", "target_language")}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise InputValidationError("All four workflow inputs are required.")
        return demo_request(project_id, values)

    @staticmethod
    def _read_json(environ: dict[str, Any]) -> dict[str, Any]:
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError as error:
            raise ValueError("Request size is invalid.") from error
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request body must be between 1 byte and 32 KiB.")
        body = environ["wsgi.input"].read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise ValueError("Request body must contain valid JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _require_csrf(self, environ: dict[str, Any]) -> None:
        supplied = environ.get("HTTP_X_CSRF_TOKEN")
        cookie = self._cookie(environ, "delta_csrf")
        if not supplied or supplied != self.csrf_token or cookie != self.csrf_token:
            raise ValueError("This state-changing request is missing a valid CSRF token.")

    @staticmethod
    def _cookie(environ: dict[str, Any], name: str) -> str | None:
        raw = environ.get("HTTP_COOKIE", "")
        for item in raw.split(";"):
            key, _, value = item.strip().partition("=")
            if key == name:
                return value
        return None

    @staticmethod
    def _json(start_response: Callable[..., Any], payload: dict[str, Any], status: int):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        phrase = {200: "OK", 404: "Not Found", 409: "Conflict", 422: "Unprocessable Entity", 503: "Service Unavailable"}.get(status, "Error")
        start_response(f"{status} {phrase}", [("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "no-store")])
        return [body]


def main() -> None:
    """Serve the local demonstration on loopback only."""

    from wsgiref.simple_server import make_server

    host = os.environ.get("DELTA_DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("DELTA_DEMO_PORT", "8000"))
    with make_server(host, port, DeltaWebApp()) as server:
        print(f"Delta demo listening at http://{host}:{port}")
        server.serve_forever()
