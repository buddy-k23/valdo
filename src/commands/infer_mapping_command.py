"""CLI command implementation for infer-mapping."""

from __future__ import annotations

from src.services.mapping_inference_service import InferenceOptions, infer_mapping_from_sample, write_mapping_json


def run_infer_mapping_command(file: str, format: str, output: str) -> str:
    """Infer mapping from sample file and write JSON output."""
    mapping = infer_mapping_from_sample(file, InferenceOptions(format=format))
    return write_mapping_json(mapping, output)
