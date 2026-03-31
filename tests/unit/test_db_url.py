"""Unit tests for src.database.db_url — dialect URL builder and schema helpers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.database.db_url import get_db_url, get_valdo_schema, include_object


# ---------------------------------------------------------------------------
# get_db_url — Oracle (default)
# ---------------------------------------------------------------------------


class TestGetDbUrlOracle:
    """Tests for get_db_url() with the Oracle adapter."""

    def test_oracle_default_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default Oracle env vars produce a valid oracledb URL."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.setenv("ORACLE_USER", "CM3INT")
        monkeypatch.setenv("ORACLE_PASSWORD", "secret")
        monkeypatch.setenv("ORACLE_DSN", "localhost:1521/FREEPDB1")

        url = get_db_url()

        assert url == "oracle+oracledb://CM3INT:secret@localhost:1521/FREEPDB1"

    def test_oracle_dsn_parsing_host_port_service(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DSN with custom host, port, and service is parsed correctly."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.setenv("ORACLE_USER", "TESTUSER")
        monkeypatch.setenv("ORACLE_PASSWORD", "pw")
        monkeypatch.setenv("ORACLE_DSN", "dbhost:1522/TESTPDB")

        url = get_db_url()

        assert url == "oracle+oracledb://TESTUSER:pw@dbhost:1522/TESTPDB"

    def test_oracle_dsn_without_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DSN with no port defaults to 1521."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.setenv("ORACLE_USER", "U")
        monkeypatch.setenv("ORACLE_PASSWORD", "p")
        monkeypatch.setenv("ORACLE_DSN", "myhost/MYPDB")

        url = get_db_url()

        assert url == "oracle+oracledb://U:p@myhost:1521/MYPDB"

    def test_oracle_dsn_without_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DSN with no slash defaults service to FREEPDB1."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.setenv("ORACLE_USER", "U")
        monkeypatch.setenv("ORACLE_PASSWORD", "p")
        monkeypatch.setenv("ORACLE_DSN", "myhost:1521")

        url = get_db_url()

        assert url == "oracle+oracledb://U:p@myhost:1521/FREEPDB1"

    def test_oracle_is_default_when_no_adapter_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When DB_ADAPTER is not set, oracle is the default."""
        monkeypatch.delenv("DB_ADAPTER", raising=False)
        monkeypatch.setenv("ORACLE_USER", "CM3INT")
        monkeypatch.setenv("ORACLE_PASSWORD", "pw")
        monkeypatch.setenv("ORACLE_DSN", "localhost:1521/FREEPDB1")

        url = get_db_url()

        assert url.startswith("oracle+oracledb://")

    def test_oracle_empty_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty password is represented as an empty string in the URL."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.setenv("ORACLE_USER", "CM3INT")
        monkeypatch.delenv("ORACLE_PASSWORD", raising=False)
        monkeypatch.setenv("ORACLE_DSN", "localhost:1521/FREEPDB1")

        url = get_db_url()

        assert "CM3INT:@" in url


# ---------------------------------------------------------------------------
# get_db_url — PostgreSQL
# ---------------------------------------------------------------------------


class TestGetDbUrlPostgresql:
    """Tests for get_db_url() with the PostgreSQL adapter."""

    def test_postgresql_default_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB_ADAPTER=postgresql builds a psycopg2 URL."""
        monkeypatch.setenv("DB_ADAPTER", "postgresql")
        monkeypatch.setenv("DB_USER", "pguser")
        monkeypatch.setenv("DB_PASSWORD", "pgpass")
        monkeypatch.setenv("DB_HOST", "pghost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "mydb")

        url = get_db_url()

        assert url == "postgresql+psycopg2://pguser:pgpass@pghost:5432/mydb"

    def test_postgresql_default_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB_PORT defaults to 5432 when not set."""
        monkeypatch.setenv("DB_ADAPTER", "postgresql")
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.delenv("DB_PORT", raising=False)
        monkeypatch.setenv("DB_NAME", "valdo")

        url = get_db_url()

        assert ":5432/" in url

    def test_postgresql_default_dbname(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB_NAME defaults to 'valdo' when not set."""
        monkeypatch.setenv("DB_ADAPTER", "postgresql")
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.delenv("DB_NAME", raising=False)

        url = get_db_url()

        assert url.endswith("/valdo")


# ---------------------------------------------------------------------------
# get_db_url — SQLite
# ---------------------------------------------------------------------------


class TestGetDbUrlSqlite:
    """Tests for get_db_url() with the SQLite adapter."""

    def test_sqlite_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB_ADAPTER=sqlite builds a sqlite URL with default path."""
        monkeypatch.setenv("DB_ADAPTER", "sqlite")
        monkeypatch.delenv("DB_PATH", raising=False)

        url = get_db_url()

        assert url == "sqlite:///valdo.db"

    def test_sqlite_custom_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB_PATH overrides the default SQLite path."""
        monkeypatch.setenv("DB_ADAPTER", "sqlite")
        monkeypatch.setenv("DB_PATH", "/tmp/test.db")

        url = get_db_url()

        assert url == "sqlite:////tmp/test.db"

    def test_sqlite_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB_PATH=:memory: produces sqlite:///:memory:."""
        monkeypatch.setenv("DB_ADAPTER", "sqlite")
        monkeypatch.setenv("DB_PATH", ":memory:")

        url = get_db_url()

        assert url == "sqlite:///:memory:"


# ---------------------------------------------------------------------------
# get_valdo_schema — per adapter
# ---------------------------------------------------------------------------


class TestGetValdoSchema:
    """Tests for get_valdo_schema() defaults and overrides."""

    def test_oracle_default_schema_from_oracle_schema(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Oracle adapter defaults VALDO_SCHEMA to ORACLE_SCHEMA."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.setenv("ORACLE_SCHEMA", "MYSCHEMA")
        monkeypatch.delenv("VALDO_SCHEMA", raising=False)

        schema = get_valdo_schema()

        assert schema == "MYSCHEMA"

    def test_oracle_default_schema_falls_back_to_oracle_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Oracle adapter falls back to ORACLE_USER when ORACLE_SCHEMA is not set."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.delenv("ORACLE_SCHEMA", raising=False)
        monkeypatch.setenv("ORACLE_USER", "CM3INT")
        monkeypatch.delenv("VALDO_SCHEMA", raising=False)

        schema = get_valdo_schema()

        assert schema == "CM3INT"

    def test_oracle_absolute_default_when_neither_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Oracle adapter falls back to CM3INT when no schema vars are set."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.delenv("ORACLE_SCHEMA", raising=False)
        monkeypatch.delenv("ORACLE_USER", raising=False)
        monkeypatch.delenv("VALDO_SCHEMA", raising=False)

        schema = get_valdo_schema()

        assert schema == "CM3INT"

    def test_postgresql_default_schema_is_public(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PostgreSQL adapter defaults VALDO_SCHEMA to 'public'."""
        monkeypatch.setenv("DB_ADAPTER", "postgresql")
        monkeypatch.delenv("VALDO_SCHEMA", raising=False)

        schema = get_valdo_schema()

        assert schema == "public"

    def test_sqlite_default_schema_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SQLite adapter defaults VALDO_SCHEMA to empty string."""
        monkeypatch.setenv("DB_ADAPTER", "sqlite")
        monkeypatch.delenv("VALDO_SCHEMA", raising=False)

        schema = get_valdo_schema()

        assert schema == ""

    def test_valdo_schema_override_oracle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VALDO_SCHEMA env var overrides the Oracle default."""
        monkeypatch.setenv("DB_ADAPTER", "oracle")
        monkeypatch.setenv("ORACLE_SCHEMA", "IGNORED")
        monkeypatch.setenv("VALDO_SCHEMA", "OVERRIDE")

        schema = get_valdo_schema()

        assert schema == "OVERRIDE"

    def test_valdo_schema_override_postgresql(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VALDO_SCHEMA env var overrides the PostgreSQL default."""
        monkeypatch.setenv("DB_ADAPTER", "postgresql")
        monkeypatch.setenv("VALDO_SCHEMA", "custom_schema")

        schema = get_valdo_schema()

        assert schema == "custom_schema"

    def test_valdo_schema_override_sqlite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VALDO_SCHEMA env var overrides the SQLite default."""
        monkeypatch.setenv("DB_ADAPTER", "sqlite")
        monkeypatch.setenv("VALDO_SCHEMA", "attached_db")

        schema = get_valdo_schema()

        assert schema == "attached_db"

    def test_no_adapter_defaults_to_oracle_behavior(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When DB_ADAPTER is not set, Oracle behavior applies."""
        monkeypatch.delenv("DB_ADAPTER", raising=False)
        monkeypatch.setenv("ORACLE_SCHEMA", "CM3INT")
        monkeypatch.delenv("VALDO_SCHEMA", raising=False)

        schema = get_valdo_schema()

        assert schema == "CM3INT"


# ---------------------------------------------------------------------------
# include_object filter (imported from alembic.env to keep logic testable)
# ---------------------------------------------------------------------------


class TestIncludeObject:
    """Tests for the include_object filter defined in src.database.db_url."""

    def test_cm3_table_is_included(self) -> None:
        """Tables starting with CM3_ are included."""
        assert include_object(None, "CM3_RUN_HISTORY", "table", False, None) is True

    def test_valdo_table_is_included(self) -> None:
        """Tables starting with VALDO_ are included."""
        assert include_object(None, "VALDO_ANYTHING", "table", False, None) is True

    def test_lowercase_cm3_table_is_included(self) -> None:
        """Table name check is case-insensitive for cm3_ prefix."""
        assert include_object(None, "cm3_run_history", "table", False, None) is True

    def test_lowercase_valdo_table_is_included(self) -> None:
        """Table name check is case-insensitive for valdo_ prefix."""
        assert include_object(None, "valdo_anything", "table", False, None) is True

    def test_customer_table_is_excluded(self) -> None:
        """Tables not matching CM3_ or VALDO_ prefix are excluded."""
        assert (
            include_object(None, "CUSTOMER_DATA", "table", False, None) is False
        )

    def test_shaw_trans_table_is_excluded(self) -> None:
        """SHAW_TRANS does not match either prefix and is excluded."""
        assert include_object(None, "SHAW_TRANS", "table", False, None) is False

    def test_non_table_objects_always_pass(self) -> None:
        """Non-table objects (index, sequence, etc.) always pass through."""
        assert include_object(None, "SOME_INDEX", "index", False, None) is True
        assert include_object(None, "SOME_SEQ", "sequence", False, None) is True
        assert include_object(None, "SOME_VIEW", "view", False, None) is True
