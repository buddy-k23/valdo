"""Generate draft mapping contracts from sample files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class InferenceOptions:
    """Options controlling mapping inference."""

    format: str = "fixed_width"
    delimiter: str = "|"
    sample_lines: int = 10


def _infer_data_type(value: str) -> tuple[str, str | None]:
    value = value.strip()
    if value.isdigit() and len(value) == 8 and value.startswith(("19", "20")):
        return "Date", "CCYYMMDD"
    if value.isdigit():
        return "Numeric", None
    return "String", None


def infer_mapping_from_sample(file_path: str, opts: InferenceOptions) -> dict[str, Any]:
    """Infer a universal mapping draft from a sample input file."""
    lines = [l.rstrip("\n") for l in Path(file_path).read_text(encoding="utf-8").splitlines()[: opts.sample_lines] if l.strip()]
    fields: list[dict[str, Any]] = []

    if opts.format == "pipe_delimited":
        max_cols = max((len(line.split(opts.delimiter)) for line in lines), default=0)
        for idx in range(max_cols):
            sample_val = ""
            for line in lines:
                parts = line.split(opts.delimiter)
                if idx < len(parts):
                    sample_val = parts[idx]
                    break
            dtype, fmt = _infer_data_type(sample_val)
            fld = {
                "name": f"FIELD_{idx+1:03d}",
                "position": idx + 1,
                "length": max((len(line.split(opts.delimiter)[idx]) for line in lines if idx < len(line.split(opts.delimiter))), default=0),
                "data_type": dtype,
                "_inferred": True,
            }
            if fmt:
                fld["format"] = fmt
            fields.append(fld)
    else:
        width = max((len(line) for line in lines), default=0)
        pos = 1
        for idx in range(0, width, 8):
            seg = [line[idx:idx+8] for line in lines]
            sample_val = next((s for s in seg if s.strip()), "")
            dtype, fmt = _infer_data_type(sample_val)
            fld = {
                "name": f"FIELD_{(idx//8)+1:03d}",
                "position": pos,
                "length": 8,
                "data_type": dtype,
                "_inferred": True,
            }
            if fmt:
                fld["format"] = fmt
            fields.append(fld)
            pos += 8

    return {
        "mapping_name": "inferred_draft",
        "_note": "DRAFT — review and rename fields before use",
        "source": {"format": opts.format},
        "fields": fields,
    }


def write_mapping_json(mapping: dict[str, Any], output_path: str) -> str:
    """Persist inferred mapping JSON to disk."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    return str(target)
