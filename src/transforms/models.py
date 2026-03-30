"""Dataclasses representing parsed field-level transforms.

Each transform type is a lightweight value object.  The base ``Transform``
carries ``type='noop'`` and acts as a pass-through sentinel.  Subclasses add
the parameters specific to their behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
