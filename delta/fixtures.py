"""Clearly labelled deterministic services for local Phase 1 tests only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .core import normalize_json


class FixtureExecutionError(RuntimeError):
    """A configured deterministic fixture failure."""


@dataclass
class DeterministicFixtureExecutor:
    """A test-only executor with observable calls and configurable behavior."""

    name: str
    output_factory: Callable[[Mapping[str, Any]], Any]
    failure_message: str | None = None
    call_count: int = 0
    is_fixture: bool = True

    def execute(self, effective_input: Mapping[str, Any]) -> Any:
        self.call_count += 1
        if self.failure_message is not None:
            raise FixtureExecutionError(self.failure_message)
        return normalize_json(self.output_factory(effective_input))

    def fail_with(self, message: str) -> None:
        self.failure_message = message

    def clear_failure(self) -> None:
        self.failure_message = None


def launch_package_fixtures() -> dict[str, DeterministicFixtureExecutor]:
    """Return fixture services whose outputs vary with their actual inputs."""

    return {
        "visual": DeterministicFixtureExecutor(
            "deterministic-fixture:product-visual:v1",
            lambda data: {
                "fixture": True,
                "kind": "product_visual",
                "description": data.get("description"),
                "brief": data.get("brief"),
            },
        ),
        "announcement": DeterministicFixtureExecutor(
            "deterministic-fixture:announcement:v1",
            lambda data: {
                "fixture": True,
                "kind": "announcement",
                "copy": f"Fixture announcement for {data.get('description')} on {data.get('launch_date')}",
            },
        ),
        "translation": DeterministicFixtureExecutor(
            "deterministic-fixture:translation:v1",
            lambda data: {
                "fixture": True,
                "kind": "translation",
                "language": data.get("target_language"),
                "source": data.get("announcement"),
            },
        ),
    }
