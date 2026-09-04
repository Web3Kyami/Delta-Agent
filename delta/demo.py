"""Launch-package workflow configuration for the local demonstration."""

from __future__ import annotations

import re
import hashlib
import secrets
from typing import Mapping

from .core import InputSpec, RevisionRequest, Scope, Step, Workflow, step_output, workflow_input
from .fixtures import launch_package_fixtures


DEMO_TENANT_ID = "delta-local-demo"
DEMO_WORKFLOW_ID = "launch-package"
_PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_SCENARIO_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,15}$")
_GENERATION_PATTERN = re.compile(r"^g[a-z0-9]{1,15}$")


def validate_demo_project_id(project_id: str) -> str:
    """Validate the project identifier used to select a local Sibyl scope."""

    if not isinstance(project_id, str) or not _PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("Project ID must start with a letter or number and use at most 64 safe characters.")
    return project_id


def demo_scope(project_id: str) -> Scope:
    return Scope(DEMO_TENANT_ID, validate_demo_project_id(project_id))


def new_generation() -> str:
    """Create a short opaque generation identifier for one scenario reset."""

    return f"g{secrets.token_hex(6)}"


def workspace_scope(workspace_id: str, scenario_id: str, generation: str) -> Scope:
    """Encode workspace, scenario, and generation into the existing project axis.

    Phase 1 persisted records use the two-axis ``Scope`` contract. Keeping that
    contract avoids breaking their keys while the short workspace digest keeps
    the composite project ID inside the existing 64-character validation rule.
    """

    if not isinstance(workspace_id, str) or len(workspace_id) < 16:
        raise ValueError("Workspace identity is invalid.")
    if not _SCENARIO_PATTERN.fullmatch(scenario_id):
        raise ValueError("Scenario identity is invalid.")
    if not _GENERATION_PATTERN.fullmatch(generation):
        raise ValueError("Scenario generation is invalid.")
    workspace_digest = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()[:12]
    return Scope(DEMO_TENANT_ID, f"w{workspace_digest}-{scenario_id}-{generation}")


def launch_package_workflow(
    *,
    fixtures: Mapping[str, object] | None = None,
    implementation_versions: Mapping[str, str] | None = None,
    visual_freshness=None,
) -> Workflow:
    """Build the three-step workflow with explicitly labelled local fixtures."""

    active_fixtures = fixtures or launch_package_fixtures()
    versions = {
        "visual": "visual-fixture-v1",
        "announcement": "announcement-fixture-v1",
        "translation": "translation-fixture-v1",
    }
    versions.update(implementation_versions or {})
    visual_options = {
        "executor": active_fixtures["visual"],
    }
    if visual_freshness is not None:
        visual_options["freshness"] = visual_freshness
    return Workflow(
        id=DEMO_WORKFLOW_ID,
        version="1",
        inputs={
            "description": InputSpec("string"),
            "brief": InputSpec("string"),
            "launch_date": InputSpec("date"),
            "target_language": InputSpec("string"),
        },
        steps=(
            Step(
                "visual",
                versions["visual"],
                {"description": workflow_input("description"), "brief": workflow_input("brief")},
                **visual_options,
            ),
            Step(
                "announcement",
                versions["announcement"],
                {"description": workflow_input("description"), "launch_date": workflow_input("launch_date")},
                executor=active_fixtures["announcement"],
            ),
            Step(
                "translation",
                versions["translation"],
                {"announcement": step_output("announcement"), "target_language": workflow_input("target_language")},
                executor=active_fixtures["translation"],
            ),
        ),
    )


def demo_request(
    project_id: str,
    inputs: Mapping[str, object],
    *,
    fixtures: Mapping[str, object] | None = None,
    implementation_versions: Mapping[str, str] | None = None,
    visual_freshness=None,
) -> RevisionRequest:
    """Create a server-validated request for the local demonstration scope."""

    return RevisionRequest(
        demo_scope(project_id),
        launch_package_workflow(
            fixtures=fixtures,
            implementation_versions=implementation_versions,
            visual_freshness=visual_freshness,
        ),
        dict(inputs),
    )
