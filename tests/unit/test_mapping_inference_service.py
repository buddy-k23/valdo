import json
from pathlib import Path

from src.services.mapping_inference_service import InferenceOptions, infer_mapping_from_sample, write_mapping_json


def test_infers_pipe_delimited(tmp_path):
    sample = tmp_path / 'sample.txt'
    sample.write_text('123|20260301|ABC\n456|20251231|DEF\n', encoding='utf-8')
    mapping = infer_mapping_from_sample(str(sample), InferenceOptions(format='pipe_delimited'))
    assert mapping['source']['format'] == 'pipe_delimited'
    assert mapping['fields'][0]['data_type'] == 'Numeric'
    assert mapping['fields'][1]['data_type'] == 'Date'
    assert all(f['_inferred'] for f in mapping['fields'])


def test_writes_json(tmp_path):
    data = {'mapping_name': 'x', 'fields': []}
    out = tmp_path / 'out.json'
    write_mapping_json(data, str(out))
    assert json.loads(out.read_text())['mapping_name'] == 'x'
