"""Signed, server-controlled sessions for the public demonstration.

The demo account is intentionally public. The signed cookie only identifies a
browser workspace and carries a short-lived CSRF token. It is not a spending
credential and is never accepted by the live ACP path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Mapping


DEMO_EMAIL = "demo@delta.local"
DEMO_PASSWORD = "delta-demo"
DEMO_DISPLAY_NAME = "Delta Dave"
SESSION_COOKIE = "delta_demo_session"
SESSION_TTL_SECONDS = 8 * 60 * 60


class SessionError(ValueError):
    """Raised when a browser session is absent, malformed, or expired."""


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class DemoSession:
    workspace_id: str
    csrf_token: str
    issued_at: int
    expires_at: int
    generations: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, *, now: datetime | None = None) -> "DemoSession":
        current = now or datetime.now(timezone.utc)
        issued = int(current.timestamp())
        ttl = int(os.environ.get("DELTA_DEMO_SESSION_TTL", SESSION_TTL_SECONDS))
        if ttl <= 0:
            ttl = SESSION_TTL_SECONDS
        return cls(
            workspace_id=secrets.token_hex(16),
            csrf_token=secrets.token_urlsafe(24),
            issued_at=issued,
            expires_at=issued + ttl,
            generations={},
        )

    def generation_for(self, scenario_id: str) -> str:
        value = self.generations.get(scenario_id)
        return value or "g0"

    def with_generation(self, scenario_id: str, generation: str) -> "DemoSession":
        values = dict(self.generations)
        values[scenario_id] = generation
        return DemoSession(
            self.workspace_id,
            self.csrf_token,
            self.issued_at,
            self.expires_at,
            values,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "csrf_token": self.csrf_token,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "generations": dict(self.generations),
        }


class SessionCodec:
    """Encode and verify a compact signed session cookie."""

    def __init__(self, secret: str | bytes | None = None) -> None:
        configured = secret or os.environ.get(
            "DELTA_DEMO_SESSION_SECRET",
            "delta-public-demo-session-signing-key-v1",
        )
        # The fallback keeps the disposable loopback demo restorable across
        # processes. Deployments outside loopback must configure a private
        # secret; DeltaWebApp rejects an unconfigured non-loopback host.
        self.secret = configured.encode("utf-8") if isinstance(configured, str) else configured
        if len(self.secret) < 16:
            raise ValueError("DELTA_DEMO_SESSION_SECRET must contain at least 16 bytes")

    def encode(self, session: DemoSession) -> str:
        body = _b64(json.dumps(session.payload(), sort_keys=True, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest()
        return f"{body}.{_b64(signature)}"

    def decode(self, value: str | None, *, now: datetime | None = None) -> DemoSession:
        if not value or "." not in value:
            raise SessionError("A signed demo session is required.")
        body, supplied_signature = value.split(".", 1)
        expected = hmac.new(self.secret, body.encode("ascii"), hashlib.sha256).digest()
        try:
            actual = _unb64(supplied_signature)
            payload = json.loads(_unb64(body))
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            raise SessionError("The demo session is invalid.") from error
        if not hmac.compare_digest(actual, expected):
            raise SessionError("The demo session signature is invalid.")
        if not isinstance(payload, dict):
            raise SessionError("The demo session payload is invalid.")
        try:
            session = DemoSession(
                workspace_id=payload["workspace_id"],
                csrf_token=payload["csrf_token"],
                issued_at=int(payload["issued_at"]),
                expires_at=int(payload["expires_at"]),
                generations=dict(payload.get("generations") or {}),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SessionError("The demo session payload is invalid.") from error
        if not session.workspace_id or not session.csrf_token or session.expires_at <= session.issued_at:
            raise SessionError("The demo session payload is invalid.")
        current = int((now or datetime.now(timezone.utc)).timestamp())
        if current >= session.expires_at:
            raise SessionError("The demo session has expired. Sign in again.")
        return session
