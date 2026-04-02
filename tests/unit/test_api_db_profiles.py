"""Unit tests for GET /api/v1/system/db-profiles endpoint (TDD)."""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("API_KEYS", "test-key:admin")

import pytest
from fastapi.testclient import TestClient


def _make_client():
    from src.api.main import app
    return TestClient(app)


class TestGetDbProfiles:
    def test_endpoint_returns_200(self) -> None:
        client = _make_client()
        with patch("src.api.routers.system.load_profiles", return_value=[]):
            resp = client.get("/api/v1/system/db-profiles")
        assert resp.status_code == 200

    def test_no_auth_required(self) -> None:
        """Profiles list is non-sensitive — no API key needed."""
        client = _make_client()
        with patch("src.api.routers.system.load_profiles", return_value=[]):
            resp = client.get("/api/v1/system/db-profiles")
        assert resp.status_code == 200

    def test_returns_empty_list_when_no_profiles(self) -> None:
        client = _make_client()
        with patch("src.api.routers.system.load_profiles", return_value=[]):
            resp = client.get("/api/v1/system/db-profiles")
        assert resp.json() == {"profiles": []}

    def test_returns_profile_fields(self, monkeypatch) -> None:
        from src.api.models.db_profile import DbProfile
        monkeypatch.setenv("ORACLE_PASSWORD", "pw")
        client = _make_client()
        profile = DbProfile(
            name="Local Dev",
            adapter="oracle",
            host="localhost:1521/FREEPDB1",
            user="CM3INT",
            schema="CM3INT",
            password_env="ORACLE_PASSWORD",
        )
        with patch("src.api.routers.system.load_profiles", return_value=[profile]):
            resp = client.get("/api/v1/system/db-profiles")
        data = resp.json()
        assert len(data["profiles"]) == 1
        p = data["profiles"][0]
        assert p["name"] == "Local Dev"
        assert p["adapter"] == "oracle"
        assert p["host"] == "localhost:1521/FREEPDB1"
        assert p["user"] == "CM3INT"
        assert p["schema"] == "CM3INT"
        assert p["password_env"] == "ORACLE_PASSWORD"
        assert p["password_env_set"] is True
        assert "password" not in p

    def test_password_env_set_false_when_var_missing(self, monkeypatch) -> None:
        from src.api.models.db_profile import DbProfile
        monkeypatch.delenv("DB_NO_PW", raising=False)
        client = _make_client()
        profile = DbProfile(
            name="Prod",
            adapter="oracle",
            host="prod:1521/PROD",
            user="CM3INT",
            schema="CM3INT",
            password_env="DB_NO_PW",
        )
        with patch("src.api.routers.system.load_profiles", return_value=[profile]):
            resp = client.get("/api/v1/system/db-profiles")
        p = resp.json()["profiles"][0]
        assert p["password_env_set"] is False
