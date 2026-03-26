"""Cross-row validation engine — issue #149.

Validates rules that span multiple rows grouped by a key column.
Supported check types:

- ``unique``            -- no duplicate values in a single field
- ``unique_composite``  -- no duplicate combinations across a list of fields
- ``consistent``        -- all rows sharing a key must have the same target value
- ``sequential``        -- sequence_field must be 1,2,3,... within each key group
- ``group_count``       -- actual row count per key must match a declared count field
- ``group_sum``         -- sum of a numeric field per key must fall within bounds
"""

from __future__ import annotations

import logging
import warnings
from typing import List

import pandas as pd

from src.validators.rule_engine import RuleViolation

_logger = logging.getLogger(__name__)


class CrossRowValidator:
    """Validate rules that span multiple rows grouped by key columns.

    Each public ``_check_*`` method accepts a rule dict and a (possibly
    pre-filtered) DataFrame and returns a list of :class:`~src.validators.rule_engine.RuleViolation`
    objects — one per offending row.

    The entry point is :meth:`validate`, which dispatches to the correct
    check method based on ``rule['check']``.
    """

    # Map check-type strings to handler method names.
    _DISPATCH: dict[str, str] = {
        "unique":            "_check_unique",
        "unique_composite":  "_check_unique_composite",
        "consistent":        "_check_consistent",
        "sequential":        "_check_sequential",
        "group_count":       "_check_group_count",
        "group_sum":         "_check_group_sum",
    }

    def validate(self, rule: dict, df: pd.DataFrame) -> List[RuleViolation]:
        """Route to the correct check method based on ``rule['check']``.

        Args:
            rule: Rule configuration dict.  Must contain at least ``id``,
                ``name``, ``severity``, and ``check`` keys.
            df: DataFrame to validate (already filtered by any ``when``
                condition applied by :class:`~src.validators.rule_engine.RuleEngine`).

        Returns:
            List of :class:`~src.validators.rule_engine.RuleViolation` objects.
            Empty list when the DataFrame is empty or all rows pass.

        Raises:
            ValueError: When ``rule['check']`` is not a recognised check type.
        """
        if df.empty:
            return []

        check = rule.get("check", "")
        method_name = self._DISPATCH.get(check)
        if method_name is None:
            raise ValueError(
                f"Unknown cross_row check type: '{check}'. "
                f"Supported types: {sorted(self._DISPATCH)}"
            )
        return getattr(self, method_name)(rule, df)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_violation(
        self,
        rule: dict,
        idx: int,
        field: str,
        value: object,
        message: str,
    ) -> RuleViolation:
        """Build a :class:`~src.validators.rule_engine.RuleViolation` for *idx*.

        Args:
            rule: Rule configuration dict.
            idx: DataFrame index label for the offending row.
            field: Field name(s) for display.
            value: Observed value(s) for display.
            message: Human-readable violation message.

        Returns:
            Populated :class:`~src.validators.rule_engine.RuleViolation`.
        """
        rid = str(rule.get("id", "UNKNOWN")).upper().replace(" ", "_")
        issue_code = f"BR_{rid}_CROSS"
        return RuleViolation(
            rule_id=rule["id"],
            rule_name=rule["name"],
            severity=rule.get("severity", "error"),
            row_number=int(idx) + 1,  # 1-indexed for user display
            field=field,
            value=value,
            message=message,
            issue_code=issue_code,
        )

    def _warn_missing(self, rule: dict, *columns: str) -> None:
        """Emit a warning when expected columns are absent from the DataFrame.

        Args:
            rule: Rule configuration dict (used for context in the message).
            *columns: Column names that are missing.
        """
        for col in columns:
            warnings.warn(
                f"cross_row rule '{rule.get('id')}' (check={rule.get('check')}): "
                f"column '{col}' not found in DataFrame — rule skipped.",
                stacklevel=3,
            )

    # ------------------------------------------------------------------
    # Check implementations
    # ------------------------------------------------------------------

    def _check_unique(self, rule: dict, df: pd.DataFrame) -> List[RuleViolation]:
        """Return violations for duplicate values in ``rule['field']``.

        NaN values are excluded from duplicate detection (a NaN is not
        considered a duplicate of another NaN).

        Args:
            rule: Must contain ``field`` (str).
            df: DataFrame to inspect.

        Returns:
            One violation per row that participates in a duplicate group.
        """
        field = rule.get("field", "")
        if field not in df.columns:
            self._warn_missing(rule, field)
            return []

        series = df[field]
        # keep_False marks ALL occurrences of duplicated values
        dup_mask = series.duplicated(keep=False) & series.notna()
        violations: List[RuleViolation] = []
        description = rule.get("description", rule.get("name", ""))

        for idx in df[dup_mask].index:
            val = df.loc[idx, field]
            violations.append(
                self._make_violation(
                    rule,
                    idx,
                    field,
                    val,
                    f"{description}: duplicate value '{val}' in field '{field}'",
                )
            )
        return violations

    def _check_unique_composite(
        self, rule: dict, df: pd.DataFrame
    ) -> List[RuleViolation]:
        """Return violations for duplicate row combinations across ``rule['fields']``.

        Args:
            rule: Must contain ``fields`` (list of str).
            df: DataFrame to inspect.

        Returns:
            One violation per row that participates in a duplicate combination.
        """
        fields: list[str] = rule.get("fields", [])
        missing = [f for f in fields if f not in df.columns]
        if missing:
            self._warn_missing(rule, *missing)
            return []

        dup_mask = df.duplicated(subset=fields, keep=False)
        violations: List[RuleViolation] = []
        field_label = ", ".join(fields)
        description = rule.get("description", rule.get("name", ""))

        for idx in df[dup_mask].index:
            combo = tuple(df.loc[idx, f] for f in fields)
            violations.append(
                self._make_violation(
                    rule,
                    idx,
                    field_label,
                    str(combo),
                    f"{description}: duplicate combination {dict(zip(fields, combo))}",
                )
            )
        return violations

    def _check_consistent(self, rule: dict, df: pd.DataFrame) -> List[RuleViolation]:
        """Return violations where rows sharing a key have different target values.

        Groups by ``rule['key_field']`` and checks that ``rule['target_field']``
        has exactly one distinct non-null value within each group.

        Args:
            rule: Must contain ``key_field`` and ``target_field`` (str).
            df: DataFrame to inspect.

        Returns:
            One violation per row in any inconsistent group.
        """
        key_field = rule.get("key_field", "")
        target_field = rule.get("target_field", "")
        missing = [c for c in (key_field, target_field) if c not in df.columns]
        if missing:
            self._warn_missing(rule, *missing)
            return []

        description = rule.get("description", rule.get("name", ""))
        violations: List[RuleViolation] = []

        # Identify keys where the target_field has more than one distinct value.
        inconsistent_keys = (
            df.dropna(subset=[target_field])
            .groupby(key_field)[target_field]
            .nunique()
        )
        bad_keys = inconsistent_keys[inconsistent_keys > 1].index

        if len(bad_keys) == 0:
            return []

        bad_rows = df[df[key_field].isin(bad_keys)]
        for idx in bad_rows.index:
            key_val = df.loc[idx, key_field]
            target_val = df.loc[idx, target_field]
            violations.append(
                self._make_violation(
                    rule,
                    idx,
                    target_field,
                    target_val,
                    f"{description}: '{target_field}' is inconsistent within "
                    f"'{key_field}'='{key_val}' group",
                )
            )
        return violations

    def _check_sequential(
        self, rule: dict, df: pd.DataFrame
    ) -> List[RuleViolation]:
        """Return violations where sequence_field is not 1,2,3,… within key groups.

        The check is order-independent: it verifies that the *set* of integer
        values for the key group equals ``{1, 2, …, N}`` where ``N`` is the
        number of rows in the group.

        Args:
            rule: Must contain ``key_field`` and ``sequence_field`` (str).
            df: DataFrame to inspect.

        Returns:
            One violation per row in any non-sequential group.
        """
        key_field = rule.get("key_field", "")
        seq_field = rule.get("sequence_field", "")
        missing = [c for c in (key_field, seq_field) if c not in df.columns]
        if missing:
            self._warn_missing(rule, *missing)
            return []

        description = rule.get("description", rule.get("name", ""))
        violations: List[RuleViolation] = []

        # Work with a numeric copy of the sequence field.
        numeric_seq = pd.to_numeric(df[seq_field], errors="coerce")
        bad_index_labels: set[int] = set()

        for key_val, group in df.groupby(key_field):
            n = len(group)
            seq_vals = numeric_seq.loc[group.index]
            expected = set(range(1, n + 1))
            actual = set(seq_vals.dropna().astype(int))
            if actual != expected:
                bad_index_labels.update(group.index)

        for idx in bad_index_labels:
            seq_val = df.loc[idx, seq_field]
            key_val = df.loc[idx, key_field]
            violations.append(
                self._make_violation(
                    rule,
                    idx,
                    seq_field,
                    seq_val,
                    f"{description}: '{seq_field}' is not sequential "
                    f"within '{key_field}'='{key_val}' group",
                )
            )
        return violations

    def _check_group_count(
        self, rule: dict, df: pd.DataFrame
    ) -> List[RuleViolation]:
        """Return violations where actual row count per key mismatches declared count.

        Each row in a mismatched group is reported as a violation because any
        row in the group carries the incorrect header count.

        Args:
            rule: Must contain ``key_field`` and ``count_field`` (str).
                ``count_field`` holds the declared expected row count.
            df: DataFrame to inspect.

        Returns:
            One violation per row in any mismatched group.
        """
        key_field = rule.get("key_field", "")
        count_field = rule.get("count_field", "")
        missing = [c for c in (key_field, count_field) if c not in df.columns]
        if missing:
            self._warn_missing(rule, *missing)
            return []

        description = rule.get("description", rule.get("name", ""))
        violations: List[RuleViolation] = []

        for key_val, group in df.groupby(key_field):
            actual_count = len(group)
            declared_counts = pd.to_numeric(
                group[count_field], errors="coerce"
            ).dropna()
            if declared_counts.empty:
                continue
            # Use the first non-null declared count in the group.
            declared = int(declared_counts.iloc[0])
            if actual_count != declared:
                for idx in group.index:
                    violations.append(
                        self._make_violation(
                            rule,
                            idx,
                            count_field,
                            df.loc[idx, count_field],
                            f"{description}: expected {declared} rows for "
                            f"'{key_field}'='{key_val}' but found {actual_count}",
                        )
                    )
        return violations

    def _check_group_sum(
        self, rule: dict, df: pd.DataFrame
    ) -> List[RuleViolation]:
        """Return violations where the sum of sum_field per key is out of bounds.

        Both ``min_value`` and ``max_value`` are optional.  If absent the
        corresponding bound is not enforced.

        Args:
            rule: Must contain ``key_field`` and ``sum_field`` (str).
                Optional: ``min_value`` (numeric), ``max_value`` (numeric).
            df: DataFrame to inspect.

        Returns:
            One violation per row in any out-of-bounds group.
        """
        key_field = rule.get("key_field", "")
        sum_field = rule.get("sum_field", "")
        missing = [c for c in (key_field, sum_field) if c not in df.columns]
        if missing:
            self._warn_missing(rule, *missing)
            return []

        min_value = rule.get("min_value")
        max_value = rule.get("max_value")
        description = rule.get("description", rule.get("name", ""))
        violations: List[RuleViolation] = []

        numeric_sum = pd.to_numeric(df[sum_field], errors="coerce")

        for key_val, group in df.groupby(key_field):
            group_sum = numeric_sum.loc[group.index].sum()
            out_of_bounds = False
            if min_value is not None and group_sum < min_value:
                out_of_bounds = True
            if max_value is not None and group_sum > max_value:
                out_of_bounds = True
            if out_of_bounds:
                for idx in group.index:
                    violations.append(
                        self._make_violation(
                            rule,
                            idx,
                            sum_field,
                            numeric_sum.loc[idx],
                            f"{description}: sum of '{sum_field}' for "
                            f"'{key_field}'='{key_val}' is {group_sum} "
                            f"(allowed: {min_value} to {max_value})",
                        )
                    )
        return violations
