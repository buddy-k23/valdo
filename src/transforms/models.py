"""Dataclasses representing parsed field-level transforms.

Each transform type is a lightweight value object.  The base ``Transform``
carries ``type='noop'`` and acts as a pass-through sentinel.  Subclasses add
the parameters specific to their behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Transform:
    """Base transform — pass-through sentinel.

    Attributes:
        type: Machine-readable transform kind. Defaults to ``'noop'``.
    """

    type: str = "noop"


@dataclass
class DefaultTransform(Transform):
    """Return the source value when present; otherwise fall back to *value*.

    Attributes:
        value: The fallback/default string to use when source is absent.
        type: Always ``'default'``.
    """

    value: str = ""
    type: str = field(default="default", init=False)

    def __post_init__(self) -> None:
        self.type = "default"


@dataclass
class BlankTransform(Transform):
    """Always output a blank (space-padded or fixed fill) value.

    Attributes:
        fill_char: Character used to pad when no explicit ``fill_value`` is
            set and a ``field_length`` is provided.  Defaults to ``' '``.
        fill_value: Optional explicit fill string.  When set, this takes
            priority over ``fill_char`` padding.  Defaults to ``''``.
        type: Always ``'blank'``.
    """

    fill_char: str = " "
    fill_value: str = ""
    type: str = field(default="blank", init=False)

    def __post_init__(self) -> None:
        self.type = "blank"


@dataclass
class ConstantTransform(Transform):
    """Always output a fixed constant, ignoring the source value entirely.

    Attributes:
        value: The constant string to emit unconditionally.
        type: Always ``'constant'``.
    """

    value: str = ""
    type: str = field(default="constant", init=False)

    def __post_init__(self) -> None:
        self.type = "constant"


@dataclass
class ConcatPart:
    """One field reference within a :class:`ConcatTransform`.

    Attributes:
        field_name: Name of the source row field to read.
        lpad_width: Left-pad the field value to this width before concatenating.
            ``0`` means no padding.
        lpad_char: Character used for left-padding.  Defaults to ``' '``.
    """

    field_name: str
    lpad_width: int = 0
    lpad_char: str = " "


@dataclass
class ConcatTransform(Transform):
    """Concatenate multiple source fields, with optional per-field LPAD.

    Attributes:
        parts: Ordered list of :class:`ConcatPart` objects describing each
            field to include in the concatenation.
        type: Always ``'concat'``.
    """

    parts: list = field(default_factory=list)  # list[ConcatPart]
    type: str = field(default="concat", init=False)

    def __post_init__(self) -> None:
        self.type = "concat"


@dataclass
class FieldMapTransform(Transform):
    """Map a named source field directly to the target field.

    Attributes:
        source_field: Name of the source row field whose value should be used.
        type: Always ``'field_map'``.
    """

    source_field: str = ""
    type: str = field(default="field_map", init=False)

    def __post_init__(self) -> None:
        self.type = "field_map"


@dataclass
class NullCheckCondition:
    """Condition that tests whether a named field is null (absent or blank).

    A field is considered null when it is absent from the row dict, ``None``,
    or a whitespace-only string.  Set ``negate=True`` to invert the test to
    *IS NOT NULL*.

    Attributes:
        field: The row field name to inspect.
        negate: When ``False`` (default) the condition is *IS NULL*; when
            ``True`` the condition is *IS NOT NULL*.
        type: Always ``'null_check'``.
    """

    field: str
    negate: bool = False
    type: str = field(default="null_check", init=False)

    def __post_init__(self) -> None:
        self.type = "null_check"


@dataclass
class EqualityCondition:
    """Condition that tests whether a named field equals a given value.

    Both the field value and the comparison value are stripped of leading and
    trailing whitespace before comparison.  Matching is case-sensitive.  A
    field that is absent from the row dict is treated as an empty string.

    Set ``negate=True`` to invert the test to *field != value*.

    Attributes:
        field: The row field name to inspect.
        value: The string to compare against.
        negate: When ``False`` (default) the condition is *field == value*;
            when ``True`` the condition is *field != value*.
        type: Always ``'equality'``.

    Example::

        cond = EqualityCondition(field="status", value="ACTIVE")
        evaluate_condition(cond, {"status": "ACTIVE"})   # True
        evaluate_condition(cond, {"status": "INACTIVE"}) # False

        neg = EqualityCondition(field="status", value="ACTIVE", negate=True)
        evaluate_condition(neg, {"status": "INACTIVE"})  # True
    """

    field: str
    value: str = ""
    negate: bool = False
    type: str = field(default="equality", init=False)

    def __post_init__(self) -> None:
        self.type = "equality"


@dataclass
class InCondition:
    """Condition that tests whether a named field's value is in a list.

    The field value and every entry in *values* are stripped of leading and
    trailing whitespace before the membership test.  A field absent from the
    row dict is treated as an empty string.

    Set ``negate=True`` to invert the test to *field NOT IN values*.

    Attributes:
        field: The row field name to inspect.
        values: The list of candidate strings to check membership against.
        negate: When ``False`` (default) the condition is *field IN values*;
            when ``True`` the condition is *field NOT IN values*.
        type: Always ``'in_condition'``.

    Example::

        cond = InCondition(field="type", values=["A", "B", "C"])
        evaluate_condition(cond, {"type": "B"})  # True
        evaluate_condition(cond, {"type": "D"})  # False

        neg = InCondition(field="type", values=["A", "B"], negate=True)
        evaluate_condition(neg, {"type": "D"})   # True
    """

    field: str
    values: list = field(default_factory=list)  # list[str]
    negate: bool = False
    type: str = field(default="in_condition", init=False)

    def __post_init__(self) -> None:
        self.type = "in_condition"


@dataclass
class SequentialNumberTransform(Transform):
    """Assign an incrementing sequence number to each record processed.

    The counter is stateful and managed externally by a
    :class:`~src.transforms.sequential_counter.SequentialCounter`.  When no
    counter is supplied to :func:`~src.transforms.transform_engine.apply_transform`
    the transform falls back to returning ``str(start)`` on every call.

    Attributes:
        start: The value emitted for the first record.  Defaults to ``1``.
        step: Amount to add to the counter after each emission.  Defaults to ``1``.
        pad_length: When set, the numeric string is zero-padded (with ``'0'``)
            to this total width.  Values already at or exceeding ``pad_length``
            are never truncated.  Defaults to ``None`` (no padding).
        type: Always ``'sequential'``.

    Example::

        t = SequentialNumberTransform(start=1, step=1, pad_length=5)
        # First record  → "00001"
        # Second record → "00002"
    """

    start: int = 1
    step: int = 1
    pad_length: Optional[int] = None
    type: str = field(default="sequential", init=False)

    def __post_init__(self) -> None:
        self.type = "sequential"


@dataclass
class DateFormatTransform(Transform):
    """Convert a date string from one strptime format to another strftime format.

    When the source value is absent (``None``, empty, or whitespace-only) or
    cannot be parsed with *input_format*, *default_value* is returned instead.

    Attributes:
        input_format: :func:`datetime.strptime` format string for parsing the
            source value.  E.g. ``"%Y-%m-%d"``.
        output_format: :func:`datetime.strftime` format string for rendering
            the converted date.  E.g. ``"%Y%m%d"``.
        default_value: Value to return when the source is absent or
            unparseable.  Defaults to ``""`` (empty string).
        type: Always ``'date_format'``.

    Example::

        t = DateFormatTransform(input_format="%Y-%m-%d", output_format="%Y%m%d")
        apply_transform("2025-06-15", t)  # -> "20250615"
        apply_transform(None, t)          # -> ""
    """

    input_format: str = ""
    output_format: str = ""
    default_value: str = ""
    type: str = field(default="date_format", init=False)

    def __post_init__(self) -> None:
        self.type = "date_format"


@dataclass
class NumericFormatTransform(Transform):
    """Format a numeric value as a zero-padded (optionally signed) string.

    Attributes:
        length: Total output width including the sign character when
            *signed* is ``True``.
        signed: When ``True`` a leading ``'+'`` or ``'-'`` is included.
            Defaults to ``False``.
        type: Always ``'numeric_format'``.

    Example::

        t = NumericFormatTransform(length=9, signed=False)
        apply_transform("42", t)   # -> "000000042"

        s = NumericFormatTransform(length=10, signed=True)
        apply_transform("42", s)   # -> "+000000042"
    """

    length: int = 0
    signed: bool = False
    type: str = field(default="numeric_format", init=False)

    def __post_init__(self) -> None:
        self.type = "numeric_format"


@dataclass
class ScaleTransform(Transform):
    """Multiply a numeric value by *factor* and optionally round the result.

    Attributes:
        factor: Multiplier applied to the source value.  Use a fraction
            (e.g. ``0.01``) to divide.
        decimal_places: Number of decimal places in the output string.
            Defaults to ``0`` (integer output).
        type: Always ``'scale'``.

    Example::

        t = ScaleTransform(factor=100, decimal_places=0)
        apply_transform("1.23", t)  # -> "123"

        d = ScaleTransform(factor=0.01, decimal_places=0)
        apply_transform("12300", d)  # -> "123"
    """

    factor: float = 1.0
    decimal_places: int = 0
    type: str = field(default="scale", init=False)

    def __post_init__(self) -> None:
        self.type = "scale"


@dataclass
class PadTransform(Transform):
    """Pad a string value to a fixed *length* using *pad_char*.

    Attributes:
        length: Target output length after padding.
        pad_char: Character used to fill the padding.  Defaults to ``' '``.
        direction: ``'left'`` or ``'right'`` padding.  Defaults to
            ``'right'`` (equivalent to ``str.ljust``).
        type: Always ``'pad'``.

    Example::

        t = PadTransform(length=10, pad_char='0', direction='left')
        apply_transform("42", t)   # -> "0000000042"

        r = PadTransform(length=8, pad_char=' ', direction='right')
        apply_transform("HI", r)   # -> "HI      "
    """

    length: int = 0
    pad_char: str = " "
    direction: str = "right"
    type: str = field(default="pad", init=False)

    def __post_init__(self) -> None:
        self.type = "pad"


@dataclass
class TruncateTransform(Transform):
    """Truncate a string value to at most *max_length* characters.

    Attributes:
        max_length: Maximum number of characters to keep.  Values shorter
            than *max_length* are returned unchanged.
        type: Always ``'truncate'``.

    Example::

        t = TruncateTransform(max_length=5)
        apply_transform("ABCDEFGH", t)  # -> "ABCDE"
        apply_transform("AB", t)        # -> "AB"
    """

    max_length: int = 0
    type: str = field(default="truncate", init=False)

    def __post_init__(self) -> None:
        self.type = "truncate"


@dataclass
class ConditionalTransform(Transform):
    """Apply one of two transforms depending on whether a condition holds.

    When *condition* evaluates to ``True`` against the current row,
    *then_transform* is applied.  Otherwise *else_transform* is applied.
    Both branches are themselves full ``Transform`` objects, so nested
    conditionals are supported.

    Attributes:
        condition: A condition object to evaluate against the current row.
            Supported types: :class:`NullCheckCondition`,
            :class:`EqualityCondition`, :class:`InCondition`.
        then_transform: ``Transform`` to apply when *condition* is ``True``.
        else_transform: ``Transform`` to apply when *condition* is ``False``.
            Defaults to a noop pass-through (``Transform(type='noop')``).
        type: Always ``'conditional'``.

    Example::

        t = ConditionalTransform(
            condition=NullCheckCondition(field="amount"),
            then_transform=ConstantTransform(value="0"),
            else_transform=DefaultTransform(value="0"),
        )
        apply_transform(None, t, row={"amount": ""})   # -> "0" (then branch)
        apply_transform("99", t, row={"amount": "99"}) # -> "99" (else branch)
    """

    condition: object = field(default=None)
    then_transform: "Transform" = field(default_factory=lambda: Transform(type="noop"))
    else_transform: "Transform" = field(default_factory=lambda: Transform(type="noop"))
    type: str = field(default="conditional", init=False)

    def __post_init__(self) -> None:
        self.type = "conditional"
