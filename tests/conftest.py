"""Pytest configuration and fixtures."""

import pytest
import tempfile
import os
import pandas as pd


@pytest.fixture(autouse=True)
def _api_auth_disabled_by_default(monkeypatch):
    """Run tests with API auth disabled unless a test configures API_KEYS.

    The API fails closed when no keys are configured; tests that exercise
    authentication set API_KEYS (or delete this variable) themselves.
    """
    monkeypatch.setenv("API_AUTH_DISABLED", "true")


@pytest.fixture
def sample_pipe_delimited_file():
    """Create a temporary pipe-delimited file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("id|name|value\n")
        f.write("1|Alice|100\n")
        f.write("2|Bob|200\n")
        f.write("3|Charlie|300\n")
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def sample_fixed_width_file():
    """Create a temporary fixed-width file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("001  Alice    100\n")
        f.write("002  Bob      200\n")
        f.write("003  Charlie  300\n")
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Edward'],
        'value': [100, 200, 300, 400, 500],
        'status': ['ACTIVE', 'ACTIVE', 'INACTIVE', 'ACTIVE', 'SUSPENDED']
    })


@pytest.fixture
def sample_mapping_dict():
    """Create a sample mapping dictionary."""
    return {
        'mapping_name': 'test_mapping',
        'version': '1.0.0',
        'description': 'Test mapping for unit tests',
        'source': {
            'type': 'file',
            'format': 'pipe_delimited'
        },
        'target': {
            'type': 'database',
            'table_name': 'TEST_TABLE'
        },
        'mappings': [
            {
                'source_column': 'id',
                'target_column': 'ID',
                'data_type': 'number',
                'required': True,
                'transformations': [],
                'validation_rules': [{'type': 'not_null'}]
            },
            {
                'source_column': 'name',
                'target_column': 'NAME',
                'data_type': 'string',
                'required': True,
                'transformations': [{'type': 'trim'}, {'type': 'upper'}],
                'validation_rules': [
                    {'type': 'not_null'},
                    {'type': 'max_length', 'parameters': {'length': 50}}
                ]
            }
        ],
        'key_columns': ['id']
    }
