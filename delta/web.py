"""Small server-rendered local demonstration for Delta."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import parse_qs, urlencode
from typing import Any, Callable

from .core import AgentPrincipal, DecisionKind, InputValidationError, RevisionRequest
from .demo import DEMO_WORKFLOW_ID, demo_request, demo_scope, new_generation, workspace_scope
from .execute import DeltaEngine
from .handoff import HandoffGate, HandoffRequest
from .scenarios import scenario_definition, SCENARIOS
from .session import (
    DEMO_DISPLAY_NAME,
    DEMO_EMAIL,
    DEMO_PASSWORD,
    SESSION_COOKIE,
    DemoSession,
    SessionCodec,
    SessionError,
)
from .store import SibylStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_PATH = PROJECT_ROOT / ".delta" / "demo-memory.db"
TEMPLATE_ROOT = Path(__file__).with_name("templates")
LANDING_TEMPLATE_PATH = TEMPLATE_ROOT / "landing.html"
APP_TEMPLATE_PATH = TEMPLATE_ROOT / "index.html"
LOGIN_TEMPLATE_PATH = TEMPLATE_ROOT / "login.html"
STATIC_ROOT = Path(__file__).with_name("static")
MAX_BODY_BYTES = 32 * 1024
_RESET_LOCK = threading.RLock()


class StaleScenarioError(ValueError):
    """Raised when a signed cookie points at a retired scenario generation."""


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
        host = os.environ.get("DELTA_DEMO_HOST", "127.0.0.1")
        if not os.environ.get("DELTA_DEMO_SESSION_SECRET") and host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("DELTA_DEMO_SESSION_SECRET is required when the demo is not loopback-only.")
        self.sessions = SessionCodec()

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        try:
            if path == "/login" and method == "GET":
                return self._respond_login(start_response)
            if path == "/api/login" and method == "POST":
                return self._handle_login(environ, start_response)
            if path == "/api/logout" and method == "POST":
                return self._handle_logout(environ, start_response)
            if path == "/" and method == "GET":
                return self._respond_landing(environ, start_response)
            if path == "/app" and method == "GET":
                if self._session_or_none(environ) is None:
                    return self._redirect(start_response, "/login")
                return self._redirect(start_response, "/app/overview")
            if path == "/app/scenarios" and method == "GET":
                return self._respond_app_auth(environ, start_response, "scenarios", "Choose a handoff")
            if path.startswith("/app/scenarios/") and method == "GET":
                scenario_id = path.removeprefix("/app/scenarios/").strip("/")
                scenario_definition(scenario_id)
                return self._respond_app_auth(environ, start_response, "scenario", "Handoff scenario")
            if path.startswith("/app/jobs/") and method == "GET":
                return self._respond_app_auth(environ, start_response, "continuity", "Reconciliation")
            if path in APP_VIEWS and method == "GET":
                return self._respond_app_auth(environ, start_response, *APP_VIEWS[path])
            if path.startswith("/static/") and method == "GET":
                return self._respond_static(path, start_response)
            if path == "/api/state" and method == "GET":
                return self._handle_state(environ, start_response)
            if path == "/api/preview" and method == "POST":
                return self._handle_preview(environ, start_response)
            if path == "/api/execute" and method == "POST":
                return self._handle_execute(environ, start_response)
            if path == "/api/scenarios" and method == "GET":
                return self._handle_scenarios(environ, start_response)
            if path.startswith("/api/scenarios/") and method == "GET":
                scenario_id = path.removeprefix("/api/scenarios/").strip("/")
                return self._handle_scenario_state(environ, start_response, scenario_id)
            if path.startswith("/api/scenarios/") and path.endswith("/handoff") and method == "POST":
                scenario_id = path.removeprefix("/api/scenarios/").removesuffix("/handoff").strip("/")
                return self._handle_scenario_handoff(environ, start_response, scenario_id)
            if path.startswith("/api/scenarios/") and path.endswith("/reset") and method == "POST":
                scenario_id = path.removeprefix("/api/scenarios/").removesuffix("/reset").strip("/")
                return self._handle_scenario_reset(environ, start_response, scenario_id)
            if path in {"/api/reconcile", "/api/approve", "/api/settle"} and method == "POST":
                return self._handle_unavailable_action(environ, start_response, path)
            return self._json(start_response, {"status": "error", "message": "The requested route does not exist."}, 404)
        except SessionError as error:
            return self._json(start_response, {"status": "unauthenticated", "message": str(error)}, 401)
        except StaleScenarioError as error:
            return self._json(start_response, {"status": "stale_generation", "message": str(error)}, 409)
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
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])
        return [body]

    def _respond_login(self, start_response: Callable[..., Any]):
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])
        return [LOGIN_TEMPLATE_PATH.read_bytes()]

    def _respond_app_auth(self, environ: dict[str, Any], start_response: Callable[..., Any], view: str, title: str):
        try:
            session = self._require_session(environ)
        except SessionError:
            return self._redirect(start_response, "/login")
        return self._respond_app(environ, start_response, view, title, session=session)

    def _handle_login(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        payload = self._read_form_or_json(environ)
        if payload.get("email") != DEMO_EMAIL or payload.get("password") != DEMO_PASSWORD:
            return self._json(start_response, {"status": "error", "message": "The demo email or password is incorrect."}, 401)
        session = DemoSession.create()
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Set-Cookie", self._session_cookie(session)),
            ("X-Delta-CSRF", session.csrf_token),
        ]
        body = json.dumps({"status": "authenticated", "display_name": DEMO_DISPLAY_NAME, "workspace_id": session.workspace_id}, separators=(",", ":")).encode()
        start_response("200 OK", headers)
        return [body]

    def _handle_logout(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        self._require_csrf(environ, allow_anonymous=True)
        start_response("200 OK", [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Set-Cookie", self._expired_session_cookie()),
        ])
        return [b'{"status":"signed_out"}']

    def _require_session(self, environ: dict[str, Any]) -> DemoSession:
        return self.sessions.decode(self._cookie(environ, SESSION_COOKIE))

    def _session_or_none(self, environ: dict[str, Any]) -> DemoSession | None:
        try:
            return self._require_session(environ)
        except SessionError:
            return None

    @staticmethod
    def _session_cookie(session: DemoSession) -> str:
        secure = "; Secure" if os.environ.get("DELTA_DEMO_SECURE_COOKIE") == "1" else ""
        return f"{SESSION_COOKIE}={SessionCodec().encode(session)}; Path=/; HttpOnly; SameSite=Strict{secure}"

    @staticmethod
    def _expired_session_cookie() -> str:
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"

    def _respond_app(self, environ: dict[str, Any], start_response: Callable[..., Any], view: str, title: str, *, session: DemoSession | None = None):
        session = session or self._require_session(environ)
        document = APP_TEMPLATE_PATH.read_text()
        document = document.replace("{{VIEW}}", view).replace("{{PAGE_TITLE}}", title)
        document = document.replace("{{CSRF_TOKEN}}", session.csrf_token)
        document = document.replace("{{DISPLAY_NAME}}", DEMO_DISPLAY_NAME)
        document = document.replace("{{WORKSPACE_ID}}", session.workspace_id[:8])
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
        headers = [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store"), ("X-Delta-CSRF", session.csrf_token)]
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

    def _scenario_session(self, environ: dict[str, Any], scenario_id: str) -> tuple[DemoSession, Any, SibylStore, Any, bool]:
        session = self._require_session(environ)
        definition = scenario_definition(scenario_id)
        generation = session.generation_for(scenario_id)
        assigned = scenario_id not in session.generations
        if assigned:
            generation = new_generation()
            session = session.with_generation(scenario_id, generation)
        scope = workspace_scope(session.workspace_id, scenario_id, generation)
        store = SibylStore.local(self.memory_path, scope)
        marker = store.get_demo_marker(scenario_id)
        if marker is not None and marker.get("generation") != generation:
            raise StaleScenarioError("This scenario generation is no longer active. Reload the current scenario.")
        initialized = bool(marker and marker.get("initialized"))
        if not initialized:
            workflow = definition.workflow()
            principal = AgentPrincipal("agent-a", f"{scenario_id}-{generation}-agent-a", "delta-fixture")
            report = DeltaEngine(store, principal=principal).execute(
                RevisionRequest(scope, workflow, dict(definition.initial_inputs)),
                now=datetime.now(timezone.utc),
            )
            if not report.outputs:
                raise RuntimeError("Scenario initialization did not produce work.")
            store.save_demo_marker(scenario_id, generation)
            initialized = True
        return session, definition, store, generation, assigned

    def _handle_scenarios(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        session = self._require_session(environ)
        scenarios = []
        for definition in SCENARIOS.values():
            scenarios.append({
                "id": definition.scenario_id,
                "title": definition.title,
                "audience": definition.audience,
                "description": definition.description,
                "opened": definition.scenario_id in session.generations,
            })
        return self._json(start_response, {
            "status": "ok",
            "display_name": DEMO_DISPLAY_NAME,
            "workspace_id": session.workspace_id[:8],
            "scenarios": scenarios,
        }, 200)

    def _handle_scenario_state(self, environ: dict[str, Any], start_response: Callable[..., Any], scenario_id: str):
        session, definition, store, generation, assigned = self._scenario_session(environ, scenario_id)
        payload = self._scenario_payload(session, definition, store, generation, status="initialized")
        if assigned:
            return self._json_with_headers(start_response, payload, 200, [("Set-Cookie", self._session_cookie(session))])
        return self._json(start_response, payload, 200)

    def _handle_scenario_handoff(self, environ: dict[str, Any], start_response: Callable[..., Any], scenario_id: str):
        self._require_csrf(environ)
        payload = self._read_json(environ)
        session, definition, store, generation, assigned = self._scenario_session(environ, scenario_id)
        requested_generation = payload.get("generation")
        if requested_generation is not None and requested_generation != generation:
            return self._json(start_response, {"status": "stale_generation", "message": "This handoff belongs to an older scenario generation. Reload the current scenario."}, 409)
        brief = payload.get("brief", definition.initial_inputs["brief"])
        revision = payload.get("revision", "constraint-change")
        if not isinstance(brief, str) or not brief.strip() or not isinstance(revision, str) or not revision.strip():
            raise InputValidationError("The handoff brief and changed constraint are required.")
        workflow = definition.workflow()
        recipient = AgentPrincipal("agent-b", f"{scenario_id}-{generation}-agent-b-{secrets.token_hex(4)}", "delta-fixture")
        evaluation = HandoffGate(store).evaluate(
            HandoffRequest(
                scope=store.scope,
                workflow=workflow,
                inputs={"brief": brief, "revision": revision},
                recipient=recipient,
                policies=definition.policies(store.scope),
            ),
        )
        HandoffGate(store).persist(evaluation)
        response = self._scenario_payload(session, definition, store, generation, status="gated")
        response["handoff"] = {
            "handoff_id": evaluation.handoff_id,
            "recipient": {"agent_id": recipient.agent_id, "session_id": recipient.session_id, "provider_id": recipient.provider_id},
            "decisions": [candidate.decision.payload() for candidate in evaluation.candidates],
            "receipt": evaluation.receipt.summary,
            "approved_context": evaluation.approved_context.prompt_payload(),
        }
        headers = [("Set-Cookie", self._session_cookie(session))] if assigned else []
        return self._json_with_headers(start_response, response, 200, headers)

    def _handle_scenario_reset(self, environ: dict[str, Any], start_response: Callable[..., Any], scenario_id: str):
        self._require_csrf(environ)
        session = self._require_session(environ)
        payload = self._read_json(environ)
        definition = scenario_definition(scenario_id)
        generation = session.generation_for(scenario_id)
        requested_generation = payload.get("generation")
        if requested_generation is not None and requested_generation != generation:
            return self._json(start_response, {"status": "stale_generation", "message": "This reset belongs to an older scenario generation. Reload the current scenario."}, 409)
        old_scope = workspace_scope(session.workspace_id, scenario_id, generation)
        with _RESET_LOCK:
            store = SibylStore.local(self.memory_path, old_scope)
            marker = store.get_demo_marker(scenario_id)
            if marker is not None and marker.get("generation") != generation:
                raise StaleScenarioError("This scenario generation is no longer active. Reload the current scenario.")
            next_generation = new_generation()
            store.save_demo_marker(scenario_id, next_generation, initialized=False)
            deleted = store.delete_scope_records(workflow_ids={definition.workflow_id})
            store.reset_active_heads(["shared_context", "private_notes", "dependent_summary", "revision_output"])
            updated = session.with_generation(scenario_id, next_generation)
            new_scope = workspace_scope(updated.workspace_id, scenario_id, next_generation)
            new_store = SibylStore.local(self.memory_path, new_scope)
            principal = AgentPrincipal("agent-a", f"{scenario_id}-{next_generation}-agent-a", "delta-fixture")
            report = DeltaEngine(new_store, principal=principal).execute(
                RevisionRequest(new_scope, definition.workflow(), dict(definition.initial_inputs)),
                now=datetime.now(timezone.utc),
            )
            if not report.outputs:
                raise RuntimeError("Scenario reset did not recreate Agent A work.")
            new_store.save_demo_marker(scenario_id, next_generation)
        response = self._scenario_payload(updated, definition, new_store, next_generation, status="reset")
        response["reset"] = {
            "deleted_entities": deleted,
            "journal_history": "retained_append_only",
            "message": "This scenario was reset. Its Sibyl journal remains retained audit history.",
        }
        return self._json_with_headers(start_response, response, 200, [("Set-Cookie", self._session_cookie(updated))])

    def _scenario_payload(self, session: DemoSession, definition: Any, store: SibylStore, generation: str, *, status: str) -> dict[str, Any]:
        workflow = definition.workflow()
        plan = DeltaEngine(store).preview(RevisionRequest(store.scope, workflow, dict(definition.initial_inputs)))
        steps = []
        for decision in plan.decisions:
            result = store.get_work_result(workflow.id, decision.step_id, decision.input_signature) if decision.input_signature else None
            browser_safe = decision.step_id in {"shared_context", "revision_output"}
            visible_output = result.output if result and browser_safe else None
            steps.append({
                "id": decision.step_id,
                "label": definition.work_labels.get(decision.step_id, decision.step_id),
                "decision": decision.decision.value,
                "reason": decision.reason,
                "reason_code": decision.reason_code,
                "current_output": visible_output,
                "source": "deterministic fixture" if visible_output is not None and self._is_fixture(visible_output) else ("withheld" if result else "none"),
                "visibility": "browser_safe" if visible_output is not None else ("withheld" if result else "pending"),
                "completed_at": result.completed_at.isoformat() if result else None,
            })
        return {
            "status": status,
            "mode": "deterministic_fixture",
            "display_name": DEMO_DISPLAY_NAME,
            "workspace_id": session.workspace_id[:8],
            "scenario_id": definition.scenario_id,
            "scenario_title": definition.title,
            "generation": generation,
            "project_id": store.scope.project_id,
            "workflow_id": workflow.id,
            "steps": steps,
            "reset_semantics": "entities_deleted_state_reset_journal_retained",
            "live_actions": {"available": False, "reason": "Public demo sessions cannot authorize live ACP or Base actions."},
        }

    def _handle_state(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        session = self._require_session(environ)
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        payload = {key: values[-1] for key, values in query.items() if values}
        request = self._request_from_payload(payload, session=session)
        store = self._store(request)
        plan = DeltaEngine(store).preview(request)
        return self._json(start_response, self._state_payload(store, request, plan, status="loaded"), 200)

    def _handle_preview(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        session = self._require_session(environ)
        self._require_csrf(environ)
        payload = self._read_json(environ)
        request = self._request_from_payload(payload, session=session)
        store = self._store(request)
        engine = DeltaEngine(store)
        plan = engine.preview(request)
        store.save_plan(plan)
        return self._json(start_response, self._state_payload(store, request, plan, status="previewed"), 200)

    def _handle_execute(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        session = self._require_session(environ)
        self._require_csrf(environ)
        payload = self._read_json(environ)
        request = self._request_from_payload(payload, session=session)
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
        self._require_session(environ)
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
    def _request_from_payload(payload: dict[str, Any], *, session: DemoSession | None = None) -> RevisionRequest:
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        project_id = payload.get("project_id")
        values = {key: payload.get(key) for key in ("description", "brief", "launch_date", "target_language")}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise InputValidationError("All four workflow inputs are required.")
        request = demo_request(project_id, values)
        if session is None:
            return request
        # Validate legacy payloads for compatibility, but never let the
        # browser choose the Sibyl scope. The signed session owns it.
        return RevisionRequest(demo_scope(session.workspace_id), request.workflow, request.inputs)

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

    @staticmethod
    def _read_form_or_json(environ: dict[str, Any]) -> dict[str, Any]:
        content_type = environ.get("CONTENT_TYPE", "")
        if "application/json" in content_type:
            return DeltaWebApp._read_json(environ)
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError as error:
            raise ValueError("Request size is invalid.") from error
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request body must be between 1 byte and 32 KiB.")
        from urllib.parse import parse_qs
        raw = environ["wsgi.input"].read(length).decode("utf-8")
        if raw.lstrip().startswith("{"):
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError("Request body must contain valid JSON.") from error
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload
        values = parse_qs(raw, keep_blank_values=True)
        return {key: items[-1] for key, items in values.items() if items}

    def _require_csrf(self, environ: dict[str, Any], *, allow_anonymous: bool = False) -> None:
        supplied = environ.get("HTTP_X_CSRF_TOKEN")
        session = self._session_or_none(environ)
        if session is None:
            if allow_anonymous:
                return
            raise SessionError("Sign in before changing demo state.")
        if not supplied or supplied != session.csrf_token:
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
    def _json_with_headers(start_response: Callable[..., Any], payload: dict[str, Any], status: int, extra_headers: list[tuple[str, str]]):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        phrase = {200: "OK", 404: "Not Found", 409: "Conflict", 422: "Unprocessable Entity", 503: "Service Unavailable"}.get(status, "Error")
        start_response(f"{status} {phrase}", [("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "no-store"), *extra_headers])
        return [body]

    @staticmethod
    def _json(start_response: Callable[..., Any], payload: dict[str, Any], status: int):
        return DeltaWebApp._json_with_headers(start_response, payload, status, [])


def main() -> None:
    """Serve the local demonstration on loopback only."""

    from wsgiref.simple_server import make_server

    host = os.environ.get("DELTA_DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("DELTA_DEMO_PORT", "8000"))
    with make_server(host, port, DeltaWebApp()) as server:
        print(f"Delta demo listening at http://{host}:{port}")
        server.serve_forever()
