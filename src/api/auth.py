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


logger = logging.getLogger(__name__)


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
        HTTPException: 401 if header is missing.
        HTTPException: 403 if key is invalid.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")

    keys = _parse_api_keys()
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
