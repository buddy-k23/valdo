"""Authentication helpers for API key verification and role checks."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict

from fastapi import Depends, Header, HTTPException, Request, status


@dataclass(frozen=True)
class AuthContext:
    key_id: str
    role: str


def _parse_api_keys() -> Dict[str, str]:
    """Parse API key configuration into key->role mapping.

    Returns:
        Mapping of configured API keys to assigned role names.
    """
    raw = os.getenv("API_KEYS", "")
    keys: Dict[str, str] = {}
    for token in [x.strip() for x in raw.split(",") if x.strip()]:
        if ":" in token:
            key, role = token.split(":", 1)
            keys[key.strip()] = role.strip() or "tester"
        else:
            keys[token] = "tester"
    return keys


def _auth_disabled() -> bool:
    """Return True when ``API_AUTH_DISABLED`` explicitly opts out of authentication.

    Only consulted when ``API_KEYS`` is empty; configured keys are always enforced.

    Returns:
        True if ``API_AUTH_DISABLED`` is ``1``, ``true`` or ``yes`` (case-insensitive).
    """
    return os.getenv("API_AUTH_DISABLED", "").strip().lower() in {"1", "true", "yes"}


logger = logging.getLogger(__name__)


def log_auth_mode() -> str:
    """Log how the API will authenticate callers, warning on insecure setups.

    Intended to be called once at application startup.

    Returns:
        ``"api_keys"``, ``"disabled"`` or ``"unconfigured"``.
    """
    if _parse_api_keys():
        logger.info("API authentication: API_KEYS enforced")
        return "api_keys"
    if _auth_disabled():
        logger.warning("API authentication DISABLED (API_AUTH_DISABLED=true); use for local development only")
        return "disabled"
    logger.warning(
        "API_KEYS is not set: protected endpoints will return 503. "
        "Set API_KEYS, or API_AUTH_DISABLED=true for local development."
    )
    return "unconfigured"


def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthContext:
    """Validate caller API key and return auth context.

    Args:
        request: Current FastAPI request object.
        x_api_key: API key value from ``X-API-Key`` header.

    Returns:
        AuthContext containing key identifier and resolved role.

    Raises:
        HTTPException: 503 if no API keys are configured and auth is not
            explicitly disabled via ``API_AUTH_DISABLED``.
        HTTPException: 401 if header is missing.
        HTTPException: 403 if key is invalid.
    """
    keys = _parse_api_keys()

    # No keys configured: fail closed unless auth is explicitly disabled (local dev only)
    if not keys:
        if _auth_disabled():
            return AuthContext(key_id="noauth", role="admin")
        logger.error("api_auth_unconfigured path=%s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "API authentication is not configured. Set API_KEYS, or set "
                "API_AUTH_DISABLED=true for local development only."
            ),
        )

    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")

    role = keys.get(x_api_key)
    if role is None:
        logger.warning("api_auth_failed path=%s reason=invalid_api_key", request.url.path)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    return AuthContext(key_id=x_api_key[-6:], role=role)


ROLE_ORDER = {"tester": 10, "mapping_owner": 20, "admin": 30}


def require_api_key(_: AuthContext = Depends(verify_api_key)) -> AuthContext:
    """Require any valid API key and return auth context."""
    return _


def require_role(minimum_role: str):
    """Create a dependency enforcing a minimum role.

    Args:
        minimum_role: Required minimum role (tester, mapping_owner, admin).

    Returns:
        Dependency function that validates caller role.
    """

    if minimum_role not in ROLE_ORDER:
        raise ValueError(f"Unsupported role requirement: {minimum_role}")

    def _require_role(ctx: AuthContext = Depends(verify_api_key)) -> AuthContext:
        caller_rank = ROLE_ORDER.get(ctx.role, -1)
        required_rank = ROLE_ORDER[minimum_role]
        if caller_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role}' required",
            )
        return ctx

    return _require_role
