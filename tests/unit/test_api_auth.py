"""API key authentication coverage for FastAPI routes."""

from fastapi.testclient import TestClient

from src.api.main import app


def test_health_endpoint_remains_public(monkeypatch):
    """Health endpoint should not require an API key."""
    monkeypatch.setenv("API_KEYS", "dev-key")
    client = TestClient(app)

    response = client.get("/api/v1/system/health")

    assert response.status_code == 200


def test_missing_api_key_returns_401(monkeypatch):
    """Protected route should reject requests without X-API-Key."""
    monkeypatch.setenv("API_KEYS", "dev-key")
    client = TestClient(app)

    response = client.get("/api/v1/system/info")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-API-Key"


def test_invalid_api_key_returns_403(monkeypatch):
    """Protected route should reject invalid API keys."""
    monkeypatch.setenv("API_KEYS", "dev-key")
    client = TestClient(app)

    response = client.get("/api/v1/system/info", headers={"X-API-Key": "wrong"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key"


def test_valid_api_key_allows_protected_route(monkeypatch):
    """Protected route should allow known API keys."""
    monkeypatch.setenv("API_KEYS", "dev-key")
    client = TestClient(app)

    response = client.get("/api/v1/system/info", headers={"X-API-Key": "dev-key"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "1.0.0"


def test_ui_referer_does_not_bypass_api_key(monkeypatch):
    """A client-supplied Referer must not substitute for an API key."""
    monkeypatch.setenv("API_KEYS", "dev-key")
    client = TestClient(app)

    response = client.get(
        "/api/v1/system/info",
        headers={"Referer": "http://attacker.example/ui"},
    )

    assert response.status_code == 401


def test_no_keys_configured_fails_closed(monkeypatch):
    """With no API_KEYS and auth not explicitly disabled, protected routes are refused."""
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_AUTH_DISABLED", raising=False)
    client = TestClient(app)

    response = client.get("/api/v1/system/info")

    assert response.status_code == 503
    assert "API_KEYS" in response.json()["detail"]


def test_auth_disabled_allows_requests_without_keys(monkeypatch):
    """API_AUTH_DISABLED=true restores open access for local development."""
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("API_AUTH_DISABLED", "true")
    client = TestClient(app)

    response = client.get("/api/v1/system/info")

    assert response.status_code == 200


def test_configured_keys_take_precedence_over_auth_disabled(monkeypatch):
    """When API_KEYS is set, API_AUTH_DISABLED is ignored and keys are enforced."""
    monkeypatch.setenv("API_KEYS", "dev-key")
    monkeypatch.setenv("API_AUTH_DISABLED", "true")
    client = TestClient(app)

    response = client.get("/api/v1/system/info")

    assert response.status_code == 401


def test_health_endpoint_public_when_auth_unconfigured(monkeypatch):
    """Health stays reachable even when authentication is not configured."""
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_AUTH_DISABLED", raising=False)
    client = TestClient(app)

    response = client.get("/api/v1/system/health")

    assert response.status_code == 200


def test_ui_loads_auth_script_before_main_script():
    """The UI must load ui-auth.js (API key handling) before ui.js."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[2] / "src" / "reports" / "static" / "ui.html").read_text()

    assert '<script src="/static/ui-auth.js"></script>' in html
    assert html.index("/static/ui-auth.js") < html.index("/static/ui.js")


def test_log_auth_mode_reports_each_configuration(monkeypatch):
    """Startup auth logging reflects keys, explicit opt-out, or missing config."""
    from src.api.auth import log_auth_mode

    monkeypatch.setenv("API_KEYS", "dev-key")
    assert log_auth_mode() == "api_keys"

    monkeypatch.delenv("API_KEYS")
    monkeypatch.setenv("API_AUTH_DISABLED", "true")
    assert log_auth_mode() == "disabled"

    monkeypatch.delenv("API_AUTH_DISABLED")
    assert log_auth_mode() == "unconfigured"
