"""Parse free-text mapping transformation descriptions into typed Transform objects.

Recognises patterns found in real Shaw→C360 mapping spreadsheets:

- ``Default to 'VALUE'`` / ``Default to VALUE`` / ``Default = VALUE``
- ``Nullable --> Leave Blank`` / ``Nullable --> 'FILL'``
- ``Leave Blank`` / ``Leave blank <spaces>``
- ``Pass Blank <spaces>``
- ``Initialize to spaces``
- ``Pass 'VALUE'``
- ``Hard-code to 'VALUE'`` / ``Hard-Code to 'VALUE'`` / ``Hardcode to 'VALUE'``

Anything else — including complex conditional expressions — returns a noop
``Transform`` so that downstream code can safely fall back to a direct
source-field copy.
"""

from __future__ import annotations

import re
from typing import Optional

from src.transforms.models import (
    BlankTransform,
    ConstantTransform,
    DefaultTransform,
    Transform,
)

# ---------------------------------------------------------------------------
# Pre-compiled patterns (order matters — more specific first)
# ---------------------------------------------------------------------------

# "Default to VALUE" or "Default = VALUE" (unquoted, single-token value)
# Captures a contiguous non-whitespace token immediately after "to" / "=".
_DEFAULT_UNQUOTED_RE = re.compile(
    r"^default\s*(?:to|=)\s*(\S+)",
    re.IGNORECASE,
)

# "Nullable --> Leave Blank" or "Nullable --> '<FILL>'"
_NULLABLE_LEAVE_BLANK_RE = re.compile(
    r"nullable\s*-->\s*leave\s+blank",
    re.IGNORECASE,
)
_NULLABLE_FILL_RE = re.compile(
    r"nullable\s*-->\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

# "Leave Blank" / "Leave blank <spaces>"
_LEAVE_BLANK_RE = re.compile(r"^leave\s+blank", re.IGNORECASE)

# "Pass Blank <spaces>"
_PASS_BLANK_RE = re.compile(r"^pass\s+blank", re.IGNORECASE)

# "Initialize to spaces"
_INIT_SPACES_RE = re.compile(r"^initialize\s+to\s+spaces", re.IGNORECASE)

# "Pass 'VALUE'" — quoted token after 'pass' only
_PASS_CONSTANT_RE = re.compile(
    r"^pass\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

# "Hard-code to 'VALUE'" / "Hard-Code to 'VALUE'" / "Hardcode to 'VALUE'"
# Accepts single or double quotes.
_HARDCODE_RE = re.compile(
    r"^hard-?code\s+to\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

# Simple "Default to 'VALUE'" with strict quoted capture (used as fallback
# to avoid the greedy unquoted branch swallowing trailing context).
_DEFAULT_QUOTED_RE = re.compile(
    r"^default\s*(?:to|=)\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def parse_transform(text: Optional[str]) -> Transform:
    """Parse a free-text transformation description into a typed Transform.

    Args:
        text: The raw transformation text from a mapping spreadsheet cell.
            May be ``None`` or empty.

    Returns:
        A ``Transform`` subclass instance whose type matches the recognised
        pattern, or a base ``Transform(type='noop')`` when the text is empty,
        ``None``, or unrecognised.

    Examples:
        >>> parse_transform("Default to '100030'")
        DefaultTransform(value='100030', type='default')

        >>> parse_transform("Nullable --> Leave Blank")
        BlankTransform(fill_char=' ', fill_value='', type='blank')

        >>> parse_transform("Pass '000'")
        ConstantTransform(value='000', type='constant')

        >>> parse_transform(None)
        Transform(type='noop')
    """
    if not text or not text.strip():
        return Transform(type="noop")

    t = text.strip()

    # --- Blank / space patterns (check before generic "pass" pattern) ---

    if _INIT_SPACES_RE.match(t):
        return BlankTransform(fill_char=" ")

    if _LEAVE_BLANK_RE.match(t):
        return BlankTransform()

    if _PASS_BLANK_RE.match(t):
        return BlankTransform()

    # --- Nullable patterns ---

    if _NULLABLE_LEAVE_BLANK_RE.search(t):
        return BlankTransform()

    m = _NULLABLE_FILL_RE.search(t)
    if m:
        return BlankTransform(fill_value=m.group(1))

    # --- Constant patterns ---

    m = _HARDCODE_RE.match(t)
    if m:
        return ConstantTransform(value=m.group(1))

    m = _PASS_CONSTANT_RE.match(t)
    if m:
        return ConstantTransform(value=m.group(1))

    # --- Default patterns (quoted first, then unquoted) ---

    m = _DEFAULT_QUOTED_RE.match(t)
    if m:
        return DefaultTransform(value=m.group(1))

    m = _DEFAULT_UNQUOTED_RE.match(t)
    if m:
        return DefaultTransform(value=m.group(1).strip())

    return Transform(type="noop")
