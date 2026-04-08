"""Synthetic test-data generation from mapping field definitions.

Provides pure functions for generating field values, rows, and complete files.
No file I/O — callers are responsible for writing output.

Functions:
    generate_field_value: Single field value from a field definition dict.
    generate_row: One row as {field_name: value} for all fields.
    generate_file: Multiple rows from a full mapping dict.
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timedelta

_DATE_ANCHOR = datetime(2026, 1, 15)  # Fixed reference date — keeps generated dates deterministic across runs
_DATE_RANGE_DAYS = 730  # +/- 2 years from anchor


def _get_rules(field_def: dict) -> list:
    """Return the rules list from either 'validation_rules' or 'rules' key.

    Args:
        field_def: A field definition dict from a mapping JSON.

    Returns:
        List of rule dicts (may be empty).
    """
    return field_def.get("validation_rules") or field_def.get("rules") or []


def _has_rule(field_def: dict, *rule_names: str) -> bool:
    """Check whether any rule in the field matches one of the given names.

    Checks both ``rule["type"]`` (real mappings) and ``rule["check"]``
    (test-fixture shorthand).

    Args:
        field_def: A field definition dict.
        rule_names: One or more rule type strings to match.

    Returns:
        True if at least one matching rule is found.
    """
    for rule in _get_rules(field_def):
        if rule.get("type") in rule_names or rule.get("check") in rule_names:
            return True
    return False


def _get_date_format(field_def: dict) -> str:
    """Extract the Python strftime format string from a field definition.

    Checks ``validation_rules`` (type=date_format with parameters.format)
    and ``rules`` shorthand (check=date_format with format key, using
    YYYYMMDD-style tokens converted to strftime).

    Args:
        field_def: A field definition dict.

    Returns:
        A strftime-compatible format string. Defaults to ``'%Y%m%d'``.
    """
    for rule in _get_rules(field_def):
        rule_type = rule.get("type") or rule.get("check") or ""
        if rule_type == "date_format":
            params = rule.get("parameters") or {}
            if params.get("format"):
                return params["format"]
            fmt = rule.get("format", "")
            if fmt:
                return _convert_date_token(fmt)
    return "%Y%m%d"


def _convert_date_token(token: str) -> str:
    """Convert YYYYMMDD-style token to strftime format.

    Args:
        token: Date format token (e.g. 'YYYYMMDD', 'YYYY-MM-DD', 'CCYYMMDD').

    Returns:
        Equivalent strftime string.
    """
    result = token
    result = result.replace("CCYY", "%Y").replace("YYYY", "%Y")
    result = result.replace("YY", "%y")
    result = result.replace("MM", "%m")
    result = result.replace("DD", "%d")
    return result


def _pad(value: str, length: int | None, data_type: str = "string") -> str:
    """Pad or truncate a value to the target length.

    Numeric types are right-justified with zero padding.
    String types are left-justified with space padding.

    Args:
        value: The raw value string.
        length: Target character width, or None for delimited fields.
        data_type: The field's data_type ('string', 'decimal', 'integer', 'date').

    Returns:
        Padded/truncated string, or original value if length is None.
    """
    if length is None:
        return value
    if data_type in ("decimal", "integer", "numeric"):
        return value[:length].rjust(length, "0")
    return value[:length].ljust(length)


def generate_field_value(field_def: dict, rng: random.Random) -> str:
    """Generate a synthetic value for a single mapping field definition.

    Priority order:
    1. ``default_value`` set -> use it (padded to length)
    2. ``valid_values`` non-empty -> ``rng.choice(valid_values)`` (padded)
    3. date type or ``date_format`` rule -> random date +/-2 years in declared format
    4. numeric type (decimal/integer) -> random integer, zero-padded to length
    5. ``not_null`` / ``not_empty`` rule -> random alphanumeric (at least 1 char)
    6. else -> random alphanumeric padded to length

    Args:
        field_def: One field dict from a mapping JSON.
        rng: Seeded Random instance for reproducibility.

    Returns:
        String value, padded/truncated to field length where applicable.
    """
    length = field_def.get("length")
    if length is not None:
        length = int(length)
    data_type = (field_def.get("data_type") or "string").lower()

    # 1. default_value
    default = field_def.get("default_value")
    if default is not None and str(default) != "":
        return _pad(str(default), length, data_type)

    # 2. valid_values
    valid_values = field_def.get("valid_values") or []
    if valid_values:
        chosen = str(rng.choice(valid_values))
        return _pad(chosen, length, data_type)

    # 3. date type
    is_date = data_type == "date" or _has_rule(field_def, "date_format")
    if is_date:
        fmt = _get_date_format(field_def)
        offset_days = rng.randint(-_DATE_RANGE_DAYS, _DATE_RANGE_DAYS)
        dt = _DATE_ANCHOR + timedelta(days=offset_days)
        val = dt.strftime(fmt)
        return _pad(val, length, "string")

    # 4. numeric type — generate value guaranteed to fit in length digits, then zero-pad
    if data_type in ("decimal", "integer", "numeric"):
        # Respect COBOL picture clause digit count when present (e.g. '9(12)' or 'S9(12)').
        # The digit count in the format may differ from the field length byte-width.
        import re as _re
        fmt_str = str(field_def.get("format") or "").upper()
        m_pic = _re.fullmatch(r"[S+]?9\((\d+)\)", fmt_str)
        if m_pic:
            digit_count = int(m_pic.group(1))
        else:
            digit_count = length or 8
        max_val = 10 ** digit_count - 1
        val = str(rng.randint(0, max_val)).rjust(digit_count, "0")
        # Then pad the full-width value to the declared field length
        if length is not None:
            val = val.rjust(length, "0")
        return val

    # 5. not_empty / not_null
    if _has_rule(field_def, "not_null", "not_empty"):
        effective_len = length or 10
        chars = string.ascii_uppercase + string.digits
        val_len = rng.randint(1, max(1, effective_len))
        val = "".join(rng.choice(chars) for _ in range(val_len))
        return _pad(val, length, data_type)

    # 6. fallback: random alphanumeric
    effective_len = length or 10
    chars = string.ascii_uppercase + string.digits + " "
    val = "".join(rng.choice(chars) for _ in range(effective_len))
    return _pad(val, length, data_type)


def generate_row(fields: list, rng: random.Random) -> dict:
    """Generate one row as {field_name: value} for all fields in a mapping.

    Args:
        fields: List of field definition dicts from mapping JSON.
        rng: Seeded Random instance.

    Returns:
        Dict mapping field name to generated string value.

    Raises:
        KeyError: If any field dict is missing the 'name' key.
    """
    return {f["name"]: generate_field_value(f, rng) for f in fields}


def generate_file(mapping: dict, row_count: int, seed: int = 42) -> list:
    """Generate *row_count* rows using field definitions from *mapping*.

    Args:
        mapping: Full mapping dict (must contain 'fields' key).
        row_count: Number of rows to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of dicts, each mapping field name to string value.
    """
    rng = random.Random(seed)
    fields = mapping.get("fields", [])
    return [generate_row(fields, rng) for _ in range(row_count)]
