"""Hostname allowlist matching for outbound HTTP requests."""
from __future__ import annotations

from typing import Optional, Tuple


def parse_allowed_hosts(raw: Optional[str]) -> Tuple[str, ...]:
    """Parse a comma-separated hostname allowlist.

    Args:
        raw: Comma-separated hostnames. An entry starting with ``*.`` matches
            any subdomain of the rest (e.g. ``*.corp.com``). ``None`` or an
            empty string means no restriction.

    Returns:
        Lowercased, trimmed entries; an empty tuple when unrestricted.
    """
    if not raw:
        return ()
    return tuple(entry.strip().lower() for entry in raw.split(",") if entry.strip())


def is_host_allowed(host: str, allowed: Tuple[str, ...]) -> bool:
    """Return whether ``host`` matches the allowlist.

    Args:
        host: Hostname from the request URL.
        allowed: Entries from :func:`parse_allowed_hosts`. Empty allows all hosts.

    Returns:
        True if ``allowed`` is empty, ``host`` equals an entry, or ``host`` is
        a subdomain of a ``*.`` wildcard entry (the apex itself does not match).
    """
    if not allowed:
        return True
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return False
    for entry in allowed:
        if entry.startswith("*."):
            if host.endswith(entry[1:]):
                return True
        elif host == entry:
            return True
    return False
