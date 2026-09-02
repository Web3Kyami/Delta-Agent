"""Measured LangGraph comparison harness kept separate from the Delta runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping, TypedDict

from .core import FreshnessPolicy
from .demo import demo_request
from .execute import DeltaEngine
from .fixtures import DeterministicFixtureExecutor, launch_package_fixtures
from .store import SibylStore


BASELINE_WORKFLOW_ID = "launch-package"
BASELINE_NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)
DEFAULT_INPUTS = {
    "description": "A compact solar charger for remote workdays",
    "brief": "Clean studio product shot, warm daylight",
    "launch_date": "2026-09-10",
    "target_language": "de",
}


class BaselineState(TypedDict, total=False):
    project_id: str
    description: str
    brief: str
    launch_date: str
    target_language: str
    visual: dict[str, Any]
    announcement: dict[str, Any]
    translation: dict[str, Any]


@dataclass(frozen=True)
class BaselineRun:
    """One measured graph invocation, including actual node calls."""

    output: Mapping[str, Any]
    calls: Mapping[str, int]
    persisted_state: Mapping[str, Any]


def _cache_key(*keys: str, implementation: str):
    def make_key(state: Mapping[str, Any]) -> str:
        values = {key: state.get(key) for key in keys}
        values["implementation"] = implementation
        return json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)

    return make_key


class LangGraphBaseline:
    """Run a fair input-keyed, TTL-aware, SQLite-persisted LangGraph baseline."""

    def __init__(self, root: str | Path, *, ttl_seconds: int | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def run(
        self,
        project_id: str,
        inputs: Mapping[str, str],
        *,
        implementation_versions: Mapping[str, str] | None = None,
    ) -> BaselineRun:
        try:
            from langgraph.cache.sqlite import SqliteCache
            from langgraph.checkpoint.sqlite import SqliteSaver
            from langgraph.graph import END, START, StateGraph
            from langgraph.types import CachePolicy
        except ImportError as error:
            raise RuntimeError("Install the optional baseline dependencies with .venv/bin/python -m pip install -e '.[baseline]'.") from error

        versions = {
            "visual": "visual-fixture-v1",
            "announcement": "announcement-fixture-v1",
            "translation": "translation-fixture-v1",
        }
        versions.update(implementation_versions or {})
        fixtures: dict[str, DeterministicFixtureExecutor] = launch_package_fixtures()
        calls = {name: 0 for name in fixtures}

        def visual(state: BaselineState) -> dict[str, Any]:
            calls["visual"] += 1
            return {"visual": fixtures["visual"].execute({"description": state["description"], "brief": state["brief"]})}

        def announcement(state: BaselineState) -> dict[str, Any]:
            calls["announcement"] += 1
            return {"announcement": fixtures["announcement"].execute({"description": state["description"], "launch_date": state["launch_date"]})}

        def translation(state: BaselineState) -> dict[str, Any]:
            calls["translation"] += 1
            return {"translation": fixtures["translation"].execute({"announcement": state["announcement"], "target_language": state["target_language"]})}

        builder = StateGraph(BaselineState)
        policy = lambda *keys, implementation: CachePolicy(
            ttl=self.ttl_seconds,
            key_func=_cache_key(*keys, implementation=implementation),
        )
        builder.add_node("visual", visual, cache_policy=policy("project_id", "description", "brief", implementation=versions["visual"]))
        builder.add_node("announcement", announcement, cache_policy=policy("project_id", "description", "launch_date", implementation=versions["announcement"]))
        builder.add_node("translation", translation, cache_policy=policy("project_id", "announcement", "target_language", implementation=versions["translation"]))
        builder.add_edge(START, "visual")
        builder.add_edge(START, "announcement")
        builder.add_edge("visual", "translation")
        builder.add_edge("announcement", "translation")
        builder.add_edge("translation", END)

        cache = SqliteCache(path=str(self.root / "cache.db"))
        with SqliteSaver.from_conn_string(str(self.root / "checkpoints.db")) as checkpointer:
            checkpointer.setup()
            graph = builder.compile(cache=cache, checkpointer=checkpointer)
            config = {"configurable": {"thread_id": f"{BASELINE_WORKFLOW_ID}:{project_id}"}}
            state = {"project_id": project_id, **dict(inputs)}
            output = graph.invoke(state, config)
            persisted_state = graph.get_state(config).values
        return BaselineRun(output=output, calls=calls, persisted_state=persisted_state)


def run_once(
    root: str | Path,
    project_id: str,
    inputs: Mapping[str, str],
    *,
    ttl_seconds: int | None = None,
    implementation_versions: Mapping[str, str] | None = None,
) -> BaselineRun:
    """Run one baseline invocation for scripts and fresh-process checks."""

    return LangGraphBaseline(root, ttl_seconds=ttl_seconds).run(
        project_id,
        inputs,
        implementation_versions=implementation_versions,
    )


def run_delta_once(
    root: str | Path,
    project_id: str,
    inputs: Mapping[str, str],
    *,
    implementation_versions: Mapping[str, str] | None = None,
    now: datetime = BASELINE_NOW,
    visual_ttl_seconds: float | None = None,
) -> BaselineRun:
    """Measure the existing Delta path with the same deterministic services."""

    fixtures = launch_package_fixtures()
    workflow = demo_request(
        project_id,
        inputs,
        fixtures=fixtures,
        implementation_versions=implementation_versions,
        visual_freshness=FreshnessPolicy(visual_ttl_seconds) if visual_ttl_seconds is not None else None,
    )
    store = SibylStore.local(Path(root) / "sibyl.db", workflow.scope)
    report = DeltaEngine(store).execute(workflow, now=now)
    return BaselineRun(
        output=report.outputs,
        calls={name: fixture.call_count for name, fixture in fixtures.items()},
        persisted_state={"decisions": [decision.decision.value for decision in report.decisions]},
    )


def _scenario_inputs(**overrides: str) -> dict[str, str]:
    values = dict(DEFAULT_INPUTS)
    values.update(overrides)
    return values


def run_comparison_matrix(root: str | Path) -> dict[str, Any]:
    """Execute the measured overlap cases and return serializable evidence."""

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cases = {
        "unchanged": [({}, {}) , ({}, {})],
        "launch_date_only": [({}, {}), ({"launch_date": "2026-09-11"}, {})],
        "visual_brief_only": [({}, {}), ({"brief": "Outdoor product shot at blue hour"}, {})],
        "description_change": [({}, {}), ({"description": "A modular desk battery for studios"}, {})],
        "implementation_change": [({}, {}), ({}, {"visual": "visual-fixture-v2"})],
        "upstream_rerun_same_output": [({}, {}), ({}, {"announcement": "announcement-fixture-v2"})],
    }
    evidence: dict[str, Any] = {}
    for name, sequence in cases.items():
        baseline = LangGraphBaseline(root / f"langgraph-{name}")
        delta_root = root / f"delta-{name}"
        baseline_runs = []
        delta_runs = []
        for index, (overrides, versions) in enumerate(sequence):
            inputs = _scenario_inputs(**overrides)
            baseline_runs.append(dict(baseline.run(name, inputs, implementation_versions=versions).__dict__))
            delta_runs.append(dict(run_delta_once(delta_root, name, inputs, implementation_versions=versions).__dict__))
        evidence[name] = {"langgraph": baseline_runs, "delta": delta_runs}
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the measured LangGraph versus Delta baseline matrix.")
    parser.add_argument("--root", type=Path, help="Directory for disposable SQLite comparison state.")
    args = parser.parse_args()
    if args.root is None:
        with tempfile.TemporaryDirectory(prefix="delta-baseline-") as directory:
            print(json.dumps(run_comparison_matrix(directory), indent=2, default=str))
    else:
        print(json.dumps(run_comparison_matrix(args.root), indent=2, default=str))


if __name__ == "__main__":
    main()
