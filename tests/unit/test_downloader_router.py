"""Unit tests for the file downloader API router."""

import os
from importlib import reload
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def _make_client(tmp_path: Path, env: dict, allowed_path: str = None):
    """Reload the FastAPI app and return (client, patch_ctx) tuple.

    The caller must use the patch context as a context manager to ensure
    environment variables are active when requests are made.

    Args:
        tmp_path: Temporary directory to use as the fd_config allowed path.
        env: Environment variables to apply via ``patch.dict``.
        allowed_path: Override for the single allowed path label entry.
            Defaults to ``str(tmp_path)``.

    Returns:
        Tuple of ``(TestClient, app_module)`` with env already patched in.
    """
    import src.api.main as m
    reload(m)
    path_str = allowed_path if allowed_path is not None else str(tmp_path)
    m.app.state.fd_config = {"paths": [{"label": "T", "path": path_str}]}
    return TestClient(m.app)


def test_get_paths(tmp_path):
    """GET /paths returns configured paths from app state."""
    env = {"ENABLE_FILE_DOWNLOADER": "true", "API_KEYS": "k"}
    with patch.dict(os.environ, env):
        client = _make_client(tmp_path, env)
        r = client.get("/api/v1/downloader/paths", headers={"X-API-Key": "k"})
    assert r.status_code == 200
    assert r.json()["paths"][0]["label"] == "T"


def test_browse_lists_files(tmp_path):
    """GET /browse returns file entries in the specified directory."""
    (tmp_path / "report.csv").write_text("a,b")
    env = {"ENABLE_FILE_DOWNLOADER": "true", "API_KEYS": "k"}
    with patch.dict(os.environ, env):
        client = _make_client(tmp_path, env)
        r = client.get(
            f"/api/v1/downloader/browse?path={tmp_path}",
            headers={"X-API-Key": "k"},
        )
    assert r.status_code == 200
    assert any(e["name"] == "report.csv" for e in r.json()["entries"])


def test_browse_rejects_unlisted_path(tmp_path):
    """GET /browse returns 403 for a path not in allowed_paths."""
    other = tmp_path / "other"
    other.mkdir()
    env = {"ENABLE_FILE_DOWNLOADER": "true", "API_KEYS": "k"}
    with patch.dict(os.environ, env):
        client = _make_client(tmp_path, env, allowed_path=str(tmp_path / "safe"))
        r = client.get(
            f"/api/v1/downloader/browse?path={other}",
            headers={"X-API-Key": "k"},
        )
    assert r.status_code == 403


def test_download_plain_file(tmp_path):
    """POST /download streams a plain file from disk."""
    (tmp_path / "r.csv").write_text("col1,col2\n")
    env = {"ENABLE_FILE_DOWNLOADER": "true", "API_KEYS": "k"}
    with patch.dict(os.environ, env):
        client = _make_client(tmp_path, env)
        r = client.post(
            "/api/v1/downloader/download",
            json={"path": str(tmp_path), "filename": "r.csv"},
            headers={"X-API-Key": "k"},
        )
    assert r.status_code == 200
    assert b"col1" in r.content


def test_download_rejects_absolute_filename(tmp_path):
    """POST /download returns 400 when filename is an absolute path."""
    env = {"ENABLE_FILE_DOWNLOADER": "true", "API_KEYS": "k"}
    with patch.dict(os.environ, env):
        client = _make_client(tmp_path, env)
        r = client.post(
            "/api/v1/downloader/download",
            json={"path": str(tmp_path), "filename": "/etc/passwd"},
            headers={"X-API-Key": "k"},
        )
    assert r.status_code == 400


def test_download_rejects_path_traversal_filename(tmp_path):
    """POST /download returns 400 when filename contains path traversal."""
    env = {"ENABLE_FILE_DOWNLOADER": "true", "API_KEYS": "k"}
    with patch.dict(os.environ, env):
        client = _make_client(tmp_path, env)
        r = client.post(
            "/api/v1/downloader/download",
            json={"path": str(tmp_path), "filename": "../secret.txt"},
            headers={"X-API-Key": "k"},
        )
    assert r.status_code == 400
